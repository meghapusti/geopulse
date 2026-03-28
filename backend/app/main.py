"""
GeoPulse — FastAPI application entry point.
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine, Base
from app.ingestion.scheduler import start_scheduler, stop_scheduler

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    configure_logging()
    log.info("GeoPulse starting", env=settings.APP_ENV)

    # Create DB tables if they don't exist yet
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start ingestion scheduler
    await start_scheduler()
    log.info("Ingestion scheduler started")

    yield  # ← app is running

    await stop_scheduler()
    await engine.dispose()
    log.info("GeoPulse shut down cleanly")


app = FastAPI(
    title="GeoPulse API",
    description="Geopolitical intelligence signals API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)

# Mount versioned API router
app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
