"""
Backtester.
Validates the tension index against historical VIX spikes.
Loads historical tension signals from DB and actual VIX from Yahoo Finance,
then computes accuracy metrics and identifies hits/misses.
"""
from datetime import datetime, timezone

import numpy as np
import structlog
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MarketSignal, RegionSignal
from app.schemas.schemas import BacktestResult

log = structlog.get_logger()

VIX_SPIKE_THRESHOLD = 20.0  # VIX > 20 = elevated volatility regime


async def run_backtest(
    start_date: datetime,
    end_date: datetime,
    horizon_hours: int,
    db: AsyncSession,
) -> BacktestResult:
    """
    Compare stored MarketSignal predictions against actual VIX outcomes.
    """
    log.info("Running backtest", start=start_date, end=end_date)

    # Load stored predictions
    pred_stmt = (
        select(MarketSignal)
        .where(
            MarketSignal.timestamp >= start_date,
            MarketSignal.timestamp <= end_date,
            MarketSignal.horizon_hours == horizon_hours,
        )
        .order_by(MarketSignal.timestamp.asc())
    )
    pred_result = await db.execute(pred_stmt)
    predictions = pred_result.scalars().all()

    if not predictions:
        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            correlation_with_vix=0.0,
            notable_hits=[],
            notable_misses=[],
        )

    # Fetch actual VIX history from Yahoo Finance
    vix_data = yf.download(
        "^VIX",
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        interval="1d",
        progress=False,
        auto_adjust=True,
    )

    if vix_data.empty:
        log.warning("No VIX data available for backtest period")
        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            correlation_with_vix=0.0,
            notable_hits=[],
            notable_misses=[],
        )

    # Align predictions to actual outcomes
    y_true = []
    y_pred = []
    tension_values = []
    notable_hits = []
    notable_misses = []

    for pred in predictions:
        # Find VIX value ~horizon_hours after prediction
        target_date = pred.timestamp + __import__("datetime").timedelta(hours=horizon_hours)
        target_str = target_date.strftime("%Y-%m-%d")

        try:
            actual_vix = float(vix_data["Close"].asof(target_date))
        except (KeyError, TypeError):
            continue

        # Ground truth: did VIX go up?
        actual_up = actual_vix > VIX_SPIKE_THRESHOLD
        predicted_up = pred.vix_direction == "up"

        y_true.append(int(actual_up))
        y_pred.append(int(predicted_up))

        # Collect feature snapshot tension for correlation
        if pred.feature_snapshot:
            tension_values.append(pred.feature_snapshot.get("global_tension_mean", 50.0))

        # Notable hits and misses
        if actual_up and predicted_up:
            notable_hits.append({
                "date": pred.timestamp.isoformat(),
                "vix_actual": actual_vix,
                "prediction": "up",
                "macro_risk_quartile": pred.macro_risk_quartile,
            })
        elif actual_up and not predicted_up:
            notable_misses.append({
                "date": pred.timestamp.isoformat(),
                "vix_actual": actual_vix,
                "prediction": "down/neutral",
                "macro_risk_quartile": pred.macro_risk_quartile,
            })

    if not y_true:
        return BacktestResult(
            start_date=start_date, end_date=end_date,
            accuracy=0.0, precision=0.0, recall=0.0, f1=0.0,
            correlation_with_vix=0.0, notable_hits=[], notable_misses=[],
        )

    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    arr_true = np.array(y_true)
    arr_pred = np.array(y_pred)

    # Correlation between tension index and VIX
    vix_close = vix_data["Close"].values
    tension_arr = np.array(tension_values) if tension_values else np.zeros(1)
    correlation = float(np.corrcoef(tension_arr[:len(vix_close)], vix_close[:len(tension_arr)])[0, 1]) if len(tension_arr) > 1 else 0.0

    return BacktestResult(
        start_date=start_date,
        end_date=end_date,
        accuracy=float(accuracy_score(arr_true, arr_pred)),
        precision=float(precision_score(arr_true, arr_pred, zero_division=0)),
        recall=float(recall_score(arr_true, arr_pred, zero_division=0)),
        f1=float(f1_score(arr_true, arr_pred, zero_division=0)),
        correlation_with_vix=correlation,
        notable_hits=notable_hits[:10],
        notable_misses=notable_misses[:10],
    )
