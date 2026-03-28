"""
NLP Pipeline orchestrator.
Pulls unprocessed articles from DB and runs them through:
  1. Event classifier (DeBERTa-v3-small zero-shot, quantized to ONNX)
  2. Sentiment + geopolitical stress (FinBERT / custom)
  3. NER for country/actor extraction (spaCy)
  4. SBERT embedding for clustering (runs in batches)

Clustering (HDBSCAN) is a separate step — runs after embeddings accumulate.
"""
import asyncio
from typing import Optional

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Article, ArticleAnalysis
from app.nlp.classifiers.event_classifier import EventClassifier
from app.nlp.sentiment.sentiment_analyser import SentimentAnalyser
from app.nlp.ner.entity_extractor import EntityExtractor
from app.nlp.clustering.narrative_clusterer import NarrativeClusterer

log = structlog.get_logger()

# Lazily loaded singletons — models load once on first use
_classifier: Optional[EventClassifier] = None
_sentiment: Optional[SentimentAnalyser] = None
_ner: Optional[EntityExtractor] = None
_clusterer: Optional[NarrativeClusterer] = None

CLUSTER_RERUN_THRESHOLD = 100  # re-cluster after every N new articles


def _get_classifier() -> EventClassifier:
    global _classifier
    if _classifier is None:
        _classifier = EventClassifier()
    return _classifier


def _get_sentiment() -> SentimentAnalyser:
    global _sentiment
    if _sentiment is None:
        _sentiment = SentimentAnalyser()
    return _sentiment


def _get_ner() -> EntityExtractor:
    global _ner
    if _ner is None:
        _ner = EntityExtractor()
    return _ner


def _get_clusterer() -> NarrativeClusterer:
    global _clusterer
    if _clusterer is None:
        _clusterer = NarrativeClusterer()
    return _clusterer


def _build_text(article: Article) -> str:
    """Combine title + body for NLP input. Fall back to title-only if no body."""
    if article.body:
        # Truncate to 512 tokens worth of chars — plenty for classification
        combined = f"{article.title}. {article.body}"
        return combined[:2000]
    return article.title


class NLPPipeline:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.classifier = _get_classifier()
        self.sentiment = _get_sentiment()
        self.ner = _get_ner()
        self.clusterer = _get_clusterer()

    async def process_pending(self, batch_size: int = 32) -> int:
        """
        Fetch unprocessed articles and run the full NLP stack.
        Returns number of articles processed.
        """
        stmt = (
            select(Article)
            .where(Article.is_processed == False)  # noqa: E712
            .order_by(Article.fetched_at.asc())
            .limit(batch_size)
        )
        result = await self.db.execute(stmt)
        articles = result.scalars().all()

        if not articles:
            return 0

        texts = [_build_text(a) for a in articles]

        # Run CPU-heavy tasks in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()

        event_results = await loop.run_in_executor(
            None, self.classifier.classify_batch, texts
        )
        sentiment_results = await loop.run_in_executor(
            None, self.sentiment.analyse_batch, texts
        )
        ner_results = await loop.run_in_executor(
            None, self.ner.extract_batch, texts
        )
        embeddings = await loop.run_in_executor(
            None, self.clusterer.embed_batch, texts
        )

        for i, article in enumerate(articles):
            ev = event_results[i]
            se = sentiment_results[i]
            ne = ner_results[i]

            analysis = ArticleAnalysis(
                article_id=article.id,
                # Event classification
                event_type=ev["label"],
                event_confidence=ev["score"],
                # Sentiment
                sentiment_label=se["label"],
                sentiment_score=se["score"],
                geopolitical_stress=se["stress"],
                # NER
                countries=ne["countries"],
                actors=ne["actors"],
                locations=ne["locations"],
                # Embedding (stored as JSON list for now — move to pgvector later)
                embedding_model="all-MiniLM-L6-v2",
            )
            self.db.add(analysis)
            article.is_processed = True

        await self.db.flush()

        # Re-cluster if enough new data
        if len(articles) >= CLUSTER_RERUN_THRESHOLD:
            await self._recluster()

        log.info("NLP batch processed", count=len(articles))
        return len(articles)

    async def _recluster(self) -> None:
        """Trigger a full re-clustering run on recent articles."""
        n = await self.clusterer.recluster(self.db)
        log.info("Narrative clustering complete", n_clusters=n)
