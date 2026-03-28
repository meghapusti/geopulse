"""Market signals endpoint."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import MarketSignal
from app.schemas.schemas import MarketSignalOut

router = APIRouter()


@router.get("/latest", response_model=list[MarketSignalOut])
async def get_latest_signals(
    horizon: int = Query(24, description="Prediction horizon in hours"),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MarketSignal)
        .where(MarketSignal.horizon_hours == horizon)
        .order_by(MarketSignal.timestamp.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    signals = result.scalars().all()
    return signals


@router.get("/history", response_model=list[MarketSignalOut])
async def get_signal_history(
    horizon: int = Query(24),
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MarketSignal)
        .where(
            MarketSignal.horizon_hours == horizon,
            MarketSignal.timestamp >= text(f"NOW() - INTERVAL '{days} days'"),
        )
        .order_by(MarketSignal.timestamp.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()
