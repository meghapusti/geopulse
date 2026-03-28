"""
Ingestion scheduler.
Uses APScheduler for lightweight cron-style scheduling that runs
inside the FastAPI process — no separate Celery worker needed for
the free-tier deployment on Railway.

Upgrade path: swap APScheduler jobs for Celery tasks when scale demands it.
"""
import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.ingestion.sources.rss import RSSIngestor
from app.ingestion.sources.gdelt import GDELTIngestor
from app.ingestion.sources.market import MarketDataIngestor
from app.nlp.pipeline import NLPPipeline
from app.signals.aggregators.tension import TensionAggregator
from app.signals.predictors.lgbm_predictor import LGBMPredictor
from app.db.session import AsyncSessionLocal

log = structlog.get_logger()
_scheduler = AsyncIOScheduler()


async def ingest_and_process() -> None:
    """
    Main pipeline job — runs every INGEST_INTERVAL_MINUTES minutes.
    1. Pull fresh articles from all sources
    2. Run NLP pipeline on unprocessed articles
    3. Re-cluster narratives (if batch size threshold met)
    4. Update region tension index
    5. Run LightGBM predictor and store market signals
    """
    log.info("Ingestion job starting")
    async with AsyncSessionLocal() as db:
        try:
            # 1. Ingest
            rss = RSSIngestor(db)
            gdelt = GDELTIngestor(db)
            new_articles = await asyncio.gather(
                rss.ingest(),
                gdelt.ingest(),
                return_exceptions=True,
            )
            total_new = sum(
                n for n in new_articles if isinstance(n, int)
            )
            log.info("Ingestion complete", new_articles=total_new)

            # 2. NLP
            nlp = NLPPipeline(db)
            processed = await nlp.process_pending(batch_size=settings.NLP_BATCH_SIZE)
            log.info("NLP processing complete", processed=processed)

            # 3. Tension index update
            aggregator = TensionAggregator(db)
            await aggregator.update_all_regions()
            log.info("Tension index updated")

            # 4. Market signal prediction
            predictor = LGBMPredictor()
            await predictor.run_and_store(db)
            log.info("Market signals stored")

            await db.commit()
        except Exception as e:
            log.error("Ingestion job failed", error=str(e))
            await db.rollback()


async def ingest_market_data() -> None:
    """Runs more frequently — market data updates every 5 min during trading hours."""
    async with AsyncSessionLocal() as db:
        try:
            market = MarketDataIngestor(db)
            await market.ingest()
            await db.commit()
        except Exception as e:
            log.error("Market ingest failed", error=str(e))


async def start_scheduler() -> None:
    _scheduler.add_job(
        ingest_and_process,
        trigger=IntervalTrigger(minutes=settings.INGEST_INTERVAL_MINUTES),
        id="main_pipeline",
        replace_existing=True,
        max_instances=1,          # never run overlapping instances
    )
    _scheduler.add_job(
        ingest_market_data,
        trigger=IntervalTrigger(minutes=5),
        id="market_data",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    log.info("Scheduler started", interval_minutes=settings.INGEST_INTERVAL_MINUTES)


async def stop_scheduler() -> None:
    _scheduler.shutdown(wait=False)
