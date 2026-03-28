"""Articles endpoint — recent articles with NLP metadata."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Article, ArticleAnalysis
from app.schemas.schemas import ArticleBase

router = APIRouter()


@router.get("", response_model=list[ArticleBase])
async def list_articles(
    region: str | None = Query(None, description="Filter by ISO-3 country code"),
    event_type: str | None = Query(None),
    hours: int = Query(24, le=168),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Article, ArticleAnalysis)
        .join(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
        .where(Article.published_at >= text(f"NOW() - INTERVAL '{hours} hours'"))
        .order_by(Article.published_at.desc())
        .limit(limit)
    )
    if region:
        stmt = stmt.where(ArticleAnalysis.countries.any(region.upper()))  # type: ignore
    if event_type:
        stmt = stmt.where(ArticleAnalysis.event_type == event_type)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        ArticleBase(
            id=a.id,
            source=a.source,
            source_tier=a.source_tier,
            url=a.url,
            title=a.title,
            published_at=a.published_at,
            countries=an.countries,
            event_type=an.event_type,
            sentiment_label=an.sentiment_label,
            sentiment_score=an.sentiment_score,
            geopolitical_stress=an.geopolitical_stress,
            cluster_id=an.cluster_id,
            cluster_label=an.cluster_label,
        )
        for a, an in rows
    ]
