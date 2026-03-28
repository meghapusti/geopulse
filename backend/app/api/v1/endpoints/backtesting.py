"""
Backtesting endpoint — shows how the tension index correlated with
real VIX spikes historically. Used for the portfolio 'proof' view.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import BacktestResult
from app.signals.backtesting.backtester import run_backtest

router = APIRouter()


@router.get("", response_model=BacktestResult)
async def backtest(
    start_date: datetime = Query(..., description="ISO datetime"),
    end_date: datetime = Query(..., description="ISO datetime"),
    horizon_hours: int = Query(24),
    db: AsyncSession = Depends(get_db),
):
    return await run_backtest(start_date, end_date, horizon_hours, db)
