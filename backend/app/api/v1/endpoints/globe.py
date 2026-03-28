"""
GET /api/v1/globe
Returns per-country tension data for the 3D globe renderer.
Cached for 5 minutes — globe polls this endpoint on an interval.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import RegionSignal, ArticleAnalysis, Article
from app.schemas.schemas import GlobeDataPoint, GlobeResponse
from app.utils.geo import COUNTRY_CENTROIDS

router = APIRouter()


@router.get("", response_model=GlobeResponse)
async def get_globe_data(db: AsyncSession = Depends(get_db)):
    """
    Returns the latest tension signal for every country that has data,
    enriched with centroid lat/lon for globe placement.
    """
    # Latest tension per region (subquery to get most recent row per region_code)
    latest_signals_subq = (
        select(
            RegionSignal.region_code,
            func.max(RegionSignal.timestamp).label("max_ts"),
        )
        .group_by(RegionSignal.region_code)
        .subquery()
    )

    stmt = (
        select(RegionSignal)
        .join(
            latest_signals_subq,
            (RegionSignal.region_code == latest_signals_subq.c.region_code)
            & (RegionSignal.timestamp == latest_signals_subq.c.max_ts),
        )
    )
    result = await db.execute(stmt)
    signals = result.scalars().all()

    points: list[GlobeDataPoint] = []
    tension_sum = 0.0

    for sig in signals:
        centroid = COUNTRY_CENTROIDS.get(sig.region_code)
        if not centroid:
            continue  # skip regions we can't place on the globe

        # Most common event type in last 24h for this region
        event_stmt = (
            select(
                ArticleAnalysis.event_type,
                func.count(ArticleAnalysis.event_type).label("cnt"),
            )
            .join(Article, Article.id == ArticleAnalysis.article_id)
            .where(
                ArticleAnalysis.countries.any(sig.region_code),  # type: ignore[attr-defined]
                Article.published_at >= text("NOW() - INTERVAL '24 hours'"),
            )
            .group_by(ArticleAnalysis.event_type)
            .order_by(text("cnt DESC"))
            .limit(1)
        )
        event_result = await db.execute(event_stmt)
        top_event = event_result.scalar_one_or_none()

        points.append(
            GlobeDataPoint(
                region_code=sig.region_code,
                lat=centroid[0],
                lon=centroid[1],
                tension_index=sig.tension_index,
                tension_delta_24h=sig.tension_delta_24h,
                article_count=sig.article_count,
                top_event_type=top_event,
                top_cluster_label=None,  # populated by narratives join in v2
            )
        )
        tension_sum += sig.tension_index

    global_avg = tension_sum / len(points) if points else 0.0

    return GlobeResponse(
        points=points,
        generated_at=datetime.now(timezone.utc),
        global_tension_avg=global_avg,
    )


@router.get("/region/{region_code}", response_model=dict)
async def get_region_detail(region_code: str, db: AsyncSession = Depends(get_db)):
    """
    Full detail for a single region — called when user clicks a country on the globe.
    Returns tension history (7d), recent articles, active clusters, market predictions.
    """
    region_code = region_code.upper()

    # 7-day tension history
    history_stmt = (
        select(RegionSignal)
        .where(
            RegionSignal.region_code == region_code,
            RegionSignal.timestamp >= text("NOW() - INTERVAL '7 days'"),
        )
        .order_by(RegionSignal.timestamp.asc())
    )
    history_result = await db.execute(history_stmt)
    history = history_result.scalars().all()

    # Recent articles for this region
    articles_stmt = (
        select(Article, ArticleAnalysis)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(
            ArticleAnalysis.countries.any(region_code),  # type: ignore[attr-defined]
            Article.published_at >= text("NOW() - INTERVAL '48 hours'"),
        )
        .order_by(Article.published_at.desc())
        .limit(10)
    )
    articles_result = await db.execute(articles_stmt)
    articles_rows = articles_result.all()

    return {
        "region_code": region_code,
        "tension_history": [
            {"timestamp": s.timestamp.isoformat(), "tension_index": s.tension_index}
            for s in history
        ],
        "recent_articles": [
            {
                "title": a.title,
                "url": a.url,
                "published_at": a.published_at.isoformat(),
                "source": a.source,
                "event_type": an.event_type,
                "sentiment_score": an.sentiment_score,
                "geopolitical_stress": an.geopolitical_stress,
            }
            for a, an in articles_rows
        ],
    }
