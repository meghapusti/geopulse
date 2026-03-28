"""
Tension index aggregator.
Computes a 0–100 tension score per country by fusing:
  - Article-level geopolitical stress scores (from NLP)
  - Event type severity weights
  - Source credibility tier weights
  - Exponential time decay (recent events matter more)
  - Article volume (more coverage = higher signal weight)

Formula per region R at time T:
  raw_score = Σ (stress_i × event_weight_i × tier_weight_i × decay(T - t_i))
              ─────────────────────────────────────────────────────────────────
              Σ (tier_weight_i × decay(T - t_i))

  tension_index = min(100, raw_score × 100)

Component breakdown is stored separately for explainability.
"""
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Article, ArticleAnalysis, RegionSignal

log = structlog.get_logger()

# Event type severity weights (0–1)
EVENT_SEVERITY: dict[str, float] = {
    "armed_conflict":   1.00,
    "terrorism":        0.90,
    "political_crisis": 0.70,
    "sanctions":        0.65,
    "humanitarian":     0.60,
    "economic_shock":   0.55,
    "energy":           0.45,
    "protest":          0.35,
    "diplomacy":        0.10,   # de-escalatory
    "other":            0.30,
}

# Source tier weights
TIER_WEIGHT: dict[int, float] = {
    1: 1.0,    # wire services — highest credibility
    2: 0.8,    # major outlets
    3: 0.5,    # supplementary
}

DECAY_HALF_LIFE_HOURS = 24   # signal halves every 24 hours


def _time_decay(hours_ago: float) -> float:
    """Exponential decay: 1.0 at t=0, 0.5 at t=24h, ~0.06 at t=72h."""
    return math.exp(-math.log(2) * hours_ago / DECAY_HALF_LIFE_HOURS)


class TensionAggregator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_recent_analyses(self, hours: int = 72) -> list[tuple]:
        """
        Fetch recent article analyses joined with article metadata.
        Returns list of (region, stress, event_type, tier, published_at) tuples.
        """
        stmt = (
            select(
                ArticleAnalysis.countries,
                ArticleAnalysis.geopolitical_stress,
                ArticleAnalysis.event_type,
                ArticleAnalysis.conflict_score if hasattr(ArticleAnalysis, "conflict_score") else text("NULL"),
                Article.source_tier,
                Article.published_at,
            )
            .join(Article, Article.id == ArticleAnalysis.article_id)
            .where(
                Article.published_at >= text(f"NOW() - INTERVAL '{hours} hours'"),
                ArticleAnalysis.countries.isnot(None),
                ArticleAnalysis.geopolitical_stress.isnot(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.all()

    def _compute_region_scores(self, rows: list) -> dict[str, dict]:
        """
        Core aggregation logic — pure Python, no DB calls.
        Returns {region_code: {tension_index, component_scores, article_count}}
        """
        now = datetime.now(timezone.utc)
        region_data: dict[str, list[dict]] = defaultdict(list)

        for row in rows:
            countries = row[0] or []
            stress = row[1] or 0.0
            event_type = row[2] or "other"
            tier = row[4] or 2
            published_at = row[5]

            if not countries:
                continue

            hours_ago = (now - published_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            decay = _time_decay(hours_ago)
            event_weight = EVENT_SEVERITY.get(event_type, 0.3)
            tier_weight = TIER_WEIGHT.get(tier, 0.5)

            weighted_stress = stress * event_weight * tier_weight * decay
            normaliser = tier_weight * decay

            for country in countries:
                region_data[country].append({
                    "weighted_stress": weighted_stress,
                    "normaliser": normaliser,
                    "event_type": event_type,
                    "stress": stress,
                })

        results: dict[str, dict] = {}
        for region, data_points in region_data.items():
            if not data_points:
                continue

            total_weighted = sum(d["weighted_stress"] for d in data_points)
            total_norm = sum(d["normaliser"] for d in data_points)
            raw_score = total_weighted / total_norm if total_norm > 0 else 0.0
            tension_index = min(100.0, raw_score * 100)

            # Component breakdown
            by_type: dict[str, list[float]] = defaultdict(list)
            for d in data_points:
                by_type[d["event_type"]].append(d["stress"])

            results[region] = {
                "tension_index": tension_index,
                "article_count": len(data_points),
                "conflict_score": float(sum(by_type.get("armed_conflict", [0])) / max(1, len(by_type.get("armed_conflict", [1])))),
                "sanctions_score": float(sum(by_type.get("sanctions", [0])) / max(1, len(by_type.get("sanctions", [1])))),
                "political_instability_score": float(sum(by_type.get("political_crisis", [0])) / max(1, len(by_type.get("political_crisis", [1])))),
                "economic_stress_score": float(sum(by_type.get("economic_shock", [0])) / max(1, len(by_type.get("economic_shock", [1])))),
            }

        return results

    async def update_all_regions(self) -> int:
        """
        Recompute tension index for all regions and write new snapshot rows.
        Returns number of regions updated.
        """
        rows = await self._get_recent_analyses(hours=72)
        region_scores = self._compute_region_scores(rows)
        now = datetime.now(timezone.utc)

        # Fetch previous snapshot for delta calculation
        prev_stmt = (
            select(RegionSignal)
            .where(
                RegionSignal.timestamp >= text("NOW() - INTERVAL '25 hours'"),
                RegionSignal.timestamp <= text("NOW() - INTERVAL '23 hours'"),
            )
        )
        prev_result = await self.db.execute(prev_stmt)
        prev_by_region = {s.region_code: s.tension_index for s in prev_result.scalars()}

        for region, scores in region_scores.items():
            if len(region) != 3:
                continue  # skip non-ISO3 codes

            prev_tension = prev_by_region.get(region)
            delta = (scores["tension_index"] - prev_tension) if prev_tension is not None else None

            signal = RegionSignal(
                region_code=region,
                timestamp=now,
                tension_index=scores["tension_index"],
                tension_delta_24h=delta,
                conflict_score=scores["conflict_score"],
                sanctions_score=scores["sanctions_score"],
                political_instability_score=scores["political_instability_score"],
                economic_stress_score=scores["economic_stress_score"],
                article_count=scores["article_count"],
            )
            self.db.add(signal)

        await self.db.flush()
        log.info("Tension index updated", regions=len(region_scores))
        return len(region_scores)
