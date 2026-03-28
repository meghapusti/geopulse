"""Narrative clusters endpoint."""
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import NarrativeCluster
from app.schemas.schemas import NarrativeClusterOut
from app.nlp.clustering.narrative_clusterer import NarrativeClusterer

router = APIRouter()
_clusterer = NarrativeClusterer()


@router.get("", response_model=list[NarrativeClusterOut])
async def get_narratives(
    emerging_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(NarrativeCluster).order_by(NarrativeCluster.article_count.desc())
    if emerging_only:
        stmt = stmt.where(NarrativeCluster.is_emerging == True)  # noqa: E712
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/recluster", status_code=202)
async def trigger_recluster(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a re-clustering run.
    Runs in the background — returns 202 immediately.
    """
    async def _run():
        n = await _clusterer.recluster(db)
        await db.commit()

    background_tasks.add_task(_run)
    return {"status": "accepted", "message": "Re-clustering started in background"}
