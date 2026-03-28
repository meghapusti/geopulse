"""API v1 router — mounts all endpoint modules."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    articles,
    globe,
    signals,
    narratives,
    alerts,
    counterfactual,
    backtesting,
)

router = APIRouter()

router.include_router(articles.router,       prefix="/articles",       tags=["articles"])
router.include_router(globe.router,          prefix="/globe",          tags=["globe"])
router.include_router(signals.router,        prefix="/signals",        tags=["signals"])
router.include_router(narratives.router,     prefix="/narratives",     tags=["narratives"])
router.include_router(alerts.router,         prefix="/alerts",         tags=["alerts"])
router.include_router(counterfactual.router, prefix="/counterfactual", tags=["counterfactual"])
router.include_router(backtesting.router,    prefix="/backtesting",    tags=["backtesting"])
