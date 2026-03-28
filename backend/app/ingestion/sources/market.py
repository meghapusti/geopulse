"""
Market data ingestor.
Pulls commodity and volatility data from free sources:
  - Yahoo Finance (yfinance): VIX, gold, oil, wheat, LNG proxies
  - FRED API: macro indicators (DXY, 10Y yield, CPI etc.)

Data is stored in a separate market_prices table (not shown in MVP ORM
but you'd add it — for now we write to a simple JSON cache file
that the predictor reads, to keep the MVP simple).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
import structlog
import yfinance as yf

from app.core.config import settings

log = structlog.get_logger()

CACHE_PATH = Path(settings.MODEL_CACHE_DIR) / "market_cache.json"

# Commodity tickers and their GeoPulse internal names
TICKERS = {
    "^VIX":    "vix",          # CBOE Volatility Index
    "GC=F":    "gold",         # Gold futures
    "CL=F":    "oil_wti",      # WTI crude oil futures
    "BZ=F":    "oil_brent",    # Brent crude oil futures
    "ZW=F":    "wheat",        # Wheat futures
    "DX-Y.NYB": "dxy",         # US Dollar Index
    "^TNX":    "us10y",        # US 10Y Treasury yield
    "SPY":     "sp500",        # S&P 500 proxy
}


class MarketDataIngestor:
    def __init__(self, db=None):
        self.db = db  # not used directly — market data cached to file

    async def ingest(self) -> dict:
        """
        Pull latest prices for all tickers.
        Returns dict of {name: price} and writes to cache.
        Async-friendly but yfinance is sync — runs in thread pool in prod.
        """
        snapshot: dict = {"timestamp": datetime.now(timezone.utc).isoformat()}

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        for ticker, name in TICKERS.items():
            try:
                data = yf.download(ticker, period="5d", interval="1h", progress=False, auto_adjust=True, session=session)
                if data.empty:
                    log.warning("No market data", ticker=ticker)
                    continue

                latest = data["Close"].iloc[-1]
                prev_close = data["Close"].iloc[-2] if len(data) > 1 else latest
                pct_change = float((latest - prev_close) / prev_close * 100)

                snapshot[name] = {
                    "price": float(latest),
                    "pct_change_1h": pct_change,
                    "high_5d": float(data["High"].max()),
                    "low_5d": float(data["Low"].min()),
                }
                log.info("Market data fetched", ticker=ticker, price=float(latest))

            except Exception as e:
                log.warning("Market fetch failed", ticker=ticker, error=str(e))

        # Write to cache file for predictor to consume
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(snapshot, f, indent=2)

        return snapshot

    @staticmethod
    def load_cache() -> dict:
        """Synchronous cache read — used by predictor."""
        if not CACHE_PATH.exists():
            return {}
        with open(CACHE_PATH) as f:
            return json.load(f)