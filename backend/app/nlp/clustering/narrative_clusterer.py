"""
Narrative clusterer.
Uses SBERT (all-MiniLM-L6-v2, ~80MB, fast CPU) to embed articles,
then HDBSCAN to find clusters without fixing k.

Full pipeline:
  1. Load recent articles (72h window) from DB with their analyses
  2. Embed with SBERT
  3. Reduce with UMAP (10 components) — improves HDBSCAN quality significantly
  4. Cluster with HDBSCAN (no fixed k, noise-aware)
  5. Label each cluster with TF-IDF keywords
  6. Detect drift vs previous run (stress delta over 7d)
  7. Write cluster assignments back to ArticleAnalysis rows
  8. Upsert NarrativeCluster rows (one per cluster)

Called by the NLP pipeline every CLUSTER_RERUN_THRESHOLD articles,
and can be triggered manually via POST /api/v1/narratives/recluster.
"""
import asyncio
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Article, ArticleAnalysis, NarrativeCluster

log = structlog.get_logger()

SBERT_MODEL = "all-MiniLM-L6-v2"   # 80MB, very fast on CPU, great quality
CLUSTER_WINDOW_HOURS = 72           # articles to include in each clustering run
MIN_TEXTS_TO_CLUSTER = 10           # don't bother clustering tiny batches


class NarrativeClusterer:
    def __init__(self):
        self._model: Optional[SentenceTransformer] = None

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            log.info("Loading SBERT", model=SBERT_MODEL)
            self._model = SentenceTransformer(
                SBERT_MODEL,
                cache_folder=settings.MODEL_CACHE_DIR,
            )
            log.info("SBERT ready")
        return self._model

    def _make_hdbscan(self):
        """Fresh HDBSCAN instance per run — avoids stale state across re-clusters."""
        import hdbscan
        return hdbscan.HDBSCAN(
            min_cluster_size=5,
            min_samples=3,
            cluster_selection_epsilon=0.3,
            metric="cosine",
            cluster_selection_method="eom",
            prediction_data=True,   # enables soft clustering / membership vectors
        )

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of texts. Returns (N, 384) float32 array."""
        model = self._load_model()
        return model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def _reduce(self, embeddings: np.ndarray) -> np.ndarray:
        """UMAP reduction to 10 dims before HDBSCAN. Falls back to raw on import error."""
        try:
            from umap import UMAP
            reducer = UMAP(
                n_components=min(10, embeddings.shape[0] - 1),
                n_neighbors=min(15, embeddings.shape[0] - 1),
                min_dist=0.0,
                metric="cosine",
                random_state=42,
                low_memory=True,
            )
            return reducer.fit_transform(embeddings)
        except ImportError:
            log.warning("UMAP not installed — skipping reduction")
            return embeddings

    def _extract_keywords(
        self,
        texts_by_cluster: dict[int, list[str]],
        n_keywords: int = 6,
    ) -> dict[int, list[str]]:
        """TF-IDF top-N keywords per cluster (excluding noise cluster -1)."""
        keywords: dict[int, list[str]] = {}
        for cid, docs in texts_by_cluster.items():
            if cid == -1 or len(docs) < 2:
                continue
            try:
                tfidf = TfidfVectorizer(
                    max_features=200,
                    stop_words="english",
                    ngram_range=(1, 2),
                    min_df=1,
                )
                mat = tfidf.fit_transform(docs)
                names = tfidf.get_feature_names_out()
                scores = np.asarray(mat.mean(axis=0)).flatten()
                top = scores.argsort()[-n_keywords:][::-1]
                keywords[cid] = [names[i] for i in top]
            except Exception as e:
                log.warning("TF-IDF failed", cluster=cid, error=str(e))
                keywords[cid] = []
        return keywords

    def _make_label(self, keywords: list[str]) -> str:
        if not keywords:
            return "Unlabelled narrative"
        return ", ".join(keywords[:4]).title()

    # ── Core algorithm (sync — called in thread pool) ──────────────────────

    def _run_clustering(
        self,
        article_ids: list,
        texts: list[str],
        analyses_by_article: dict,
    ) -> dict:
        """
        Pure computation — no DB. Returns a result dict that the async
        caller writes to the database.

        Returns:
          {
            'label_map': {article_id: cluster_id},   # -1 = noise
            'clusters': {
              cluster_id: {
                'label': str,
                'keywords': list[str],
                'article_ids': list,
                'avg_stress': float,
                'countries': list[str],
              }
            },
            'noise_count': int,
          }
        """
        if len(texts) < MIN_TEXTS_TO_CLUSTER:
            log.info("Too few texts for clustering", count=len(texts))
            return {}

        embeddings = self.embed_batch(texts)
        reduced    = self._reduce(embeddings)
        clusterer  = self._make_hdbscan()
        labels     = clusterer.fit_predict(reduced)

        # Group by cluster
        texts_by_cluster: dict[int, list[str]]  = defaultdict(list)
        ids_by_cluster:   dict[int, list]        = defaultdict(list)

        for aid, text_val, label in zip(article_ids, texts, labels):
            texts_by_cluster[int(label)].append(text_val)
            ids_by_cluster[int(label)].append(aid)

        keywords_by_cluster = self._extract_keywords(texts_by_cluster)

        # Build per-cluster metadata
        clusters = {}
        for cid, kws in keywords_by_cluster.items():
            cluster_article_ids = ids_by_cluster[cid]
            # Collect stress scores and countries from analyses
            stress_scores = []
            countries_set: set[str] = set()
            for aid in cluster_article_ids:
                an = analyses_by_article.get(aid)
                if an:
                    if an.geopolitical_stress is not None:
                        stress_scores.append(an.geopolitical_stress)
                    if an.countries:
                        countries_set.update(an.countries)

            clusters[cid] = {
                "label":       self._make_label(kws),
                "keywords":    kws,
                "article_ids": cluster_article_ids,
                "avg_stress":  float(np.mean(stress_scores)) if stress_scores else None,
                "countries":   sorted(countries_set),
            }

        noise_count = sum(1 for l in labels if l == -1)
        log.info(
            "Clustering complete",
            n_clusters=len(clusters),
            noise_articles=noise_count,
            total_articles=len(texts),
        )

        return {
            "label_map": {aid: int(lbl) for aid, lbl in zip(article_ids, labels)},
            "clusters":  clusters,
            "noise_count": noise_count,
        }

    # ── DB read/write (async) ──────────────────────────────────────────────

    async def _load_recent_articles(self, db: AsyncSession) -> tuple[list, list[str], dict]:
        """
        Load articles from the last CLUSTER_WINDOW_HOURS for clustering.
        Returns (article_ids, texts, analyses_by_article_id).
        """
        stmt = (
            select(Article, ArticleAnalysis)
            .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
            .where(
                Article.published_at >= text(
                    f"NOW() - INTERVAL '{CLUSTER_WINDOW_HOURS} hours'"
                ),
                Article.is_processed == True,  # noqa: E712
            )
            .order_by(Article.published_at.desc())
            .limit(2000)    # cap to keep UMAP fast on CPU
        )
        result = await db.execute(stmt)
        rows = result.all()

        article_ids = []
        texts       = []
        analyses_by_article: dict = {}

        for article, analysis in rows:
            text_val = article.title
            if article.body:
                text_val = f"{article.title}. {article.body[:500]}"
            article_ids.append(article.id)
            texts.append(text_val)
            analyses_by_article[article.id] = analysis

        log.info("Loaded articles for clustering", count=len(texts))
        return article_ids, texts, analyses_by_article

    async def _write_results(self, db: AsyncSession, result: dict) -> None:
        """
        Write clustering results back to the database:
          1. Update ArticleAnalysis.cluster_id and cluster_label for every article
          2. Upsert NarrativeCluster rows (one per cluster)
          3. Detect emerging clusters (stress rising faster than average)
          4. Compute stress drift vs 7 days ago
        """
        if not result:
            return

        label_map = result["label_map"]
        clusters  = result["clusters"]
        now       = datetime.now(timezone.utc)

        # 1. Bulk-update article analyses with their new cluster assignments
        for article_id, cluster_id in label_map.items():
            cluster_label = clusters.get(cluster_id, {}).get("label") if cluster_id != -1 else None
            await db.execute(
                update(ArticleAnalysis)
                .where(ArticleAnalysis.article_id == article_id)
                .values(cluster_id=cluster_id, cluster_label=cluster_label)
            )

        # 2. Fetch previous stress values for drift detection
        prev_stmt = (
            select(NarrativeCluster.cluster_id, NarrativeCluster.avg_stress)
            .where(
                NarrativeCluster.last_seen_at >= text("NOW() - INTERVAL '8 days'"),
                NarrativeCluster.last_seen_at <= text("NOW() - INTERVAL '6 days'"),
            )
        )
        prev_result = await db.execute(prev_stmt)
        prev_stress: dict[int, float] = {
            row.cluster_id: row.avg_stress
            for row in prev_result
            if row.avg_stress is not None
        }

        # 3. Upsert NarrativeCluster rows
        all_stresses = [
            c["avg_stress"] for c in clusters.values() if c["avg_stress"] is not None
        ]
        global_avg_stress = float(np.mean(all_stresses)) if all_stresses else 0.0

        for cid, meta in clusters.items():
            stress_7d_ago  = prev_stress.get(cid)
            stress_delta   = (
                (meta["avg_stress"] - stress_7d_ago)
                if (meta["avg_stress"] is not None and stress_7d_ago is not None)
                else None
            )
            # Emerging = stress rising faster than global average AND cluster is new or growing
            is_emerging = bool(
                stress_delta is not None
                and stress_delta > 0.1
                and (meta["avg_stress"] or 0) > global_avg_stress
            )

            # PostgreSQL upsert — update existing rows, insert new ones
            stmt = pg_insert(NarrativeCluster).values(
                cluster_id=cid,
                detected_at=now,
                last_seen_at=now,
                label=meta["label"],
                keywords=meta["keywords"],
                article_count=len(meta["article_ids"]),
                avg_stress=meta["avg_stress"],
                countries=meta["countries"],
                stress_7d_ago=stress_7d_ago,
                stress_delta_7d=stress_delta,
                is_emerging=is_emerging,
            ).on_conflict_do_update(
                index_elements=["cluster_id"],
                set_={
                    "last_seen_at":   now,
                    "label":          meta["label"],
                    "keywords":       meta["keywords"],
                    "article_count":  len(meta["article_ids"]),
                    "avg_stress":     meta["avg_stress"],
                    "countries":      meta["countries"],
                    "stress_7d_ago":  stress_7d_ago,
                    "stress_delta_7d": stress_delta,
                    "is_emerging":    is_emerging,
                },
            )
            await db.execute(stmt)

        await db.flush()
        log.info(
            "Cluster DB write complete",
            n_clusters=len(clusters),
            n_emerging=sum(1 for c in clusters.values() if c.get("is_emerging")),
        )

    # ── Public entry point ─────────────────────────────────────────────────

    async def recluster(self, db: AsyncSession) -> int:
        """
        Full async re-clustering run with DB read and write.
        Called by NLPPipeline._recluster() in a thread pool.
        Returns number of clusters found (excluding noise).
        """
        log.info("Starting narrative re-clustering")

        # Load data
        article_ids, texts, analyses_by_article = await self._load_recent_articles(db)

        if len(texts) < MIN_TEXTS_TO_CLUSTER:
            log.info("Insufficient articles for clustering", count=len(texts))
            return 0

        # Run CPU-heavy computation in thread pool (avoids blocking the event loop)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._run_clustering,
            article_ids,
            texts,
            analyses_by_article,
        )

        if not result:
            return 0

        # Write results back to DB
        await self._write_results(db, result)

        return len(result.get("clusters", {}))
