"""
Market data ingestor.
Uses Twelve Data API (free tier: 800 req/day, no cloud IP blocking).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
import structlog

from app.core.config import settings

log = structlog.get_logger()

CACHE_PATH = Path(settings.MODEL_CACHE_DIR) / "market_cache.json"

# Twelve Data symbols — same instruments, just standard ticker format
TICKERS = {
    "VXX":  "vix",       # VIX proxy ETF
    "GLD":  "gold",      # Gold ETF
    "USO":  "oil_wti",   # WTI crude oil ETF
    "BNO":  "oil_brent", # Brent crude oil ETF
    "WEAT": "wheat",     # Wheat ETF
    "UUP":  "dxy",       # US Dollar Index ETF
    "TLT":  "us10y",     # Treasury ETF (10Y proxy)
    "SPY":  "sp500",     # S&P 500 ETF
}

TD_BASE = "https://api.twelvedata.com"


class MarketDataIngestor:
    def __init__(self, db=None):
        self.db = db
        self.api_key = getattr(settings, "TWELVE_DATA_KEY", "")

    async def ingest(self) -> dict:
        if not self.api_key:
            log.warning("TWELVE_DATA_KEY not set — skipping market data fetch")
            return self.load_cache()

        snapshot: dict = {"timestamp": datetime.now(timezone.utc).isoformat()}
        session = requests.Session()
        session.headers.update({"User-Agent": "GeoPulse/1.0"})

        # Batch all tickers in one request — Twelve Data supports comma-separated symbols
        symbols = ",".join(TICKERS.keys())
        try:
            resp = session.get(f"{TD_BASE}/quote", params={
                "symbol": symbols,
                "apikey": self.api_key,
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # If only one symbol, API returns the quote directly (not wrapped)
            # For multiple symbols it returns {SYMBOL: quote, ...}
            if len(TICKERS) == 1:
                data = {list(TICKERS.keys())[0]: data}

            for symbol, name in TICKERS.items():
                quote = data.get(symbol, {})
                if quote.get("status") == "error" or "close" not in quote:
                    log.warning("No quote data", symbol=symbol, response=quote)
                    continue

                price = float(quote["close"])
                prev_close = float(quote["previous_close"])
                pct_change = ((price - prev_close) / prev_close * 100) if prev_close else 0.0

                snapshot[name] = {
                    "price": price,
                    "pct_change_1h": pct_change,
                    "high_5d": float(quote.get("fifty_two_week", {}).get("high", quote["high"])),
                    "low_5d": float(quote.get("fifty_two_week", {}).get("low", quote["low"])),
                }
                log.info("Market data fetched", symbol=symbol, price=price)

        except Exception as e:
            log.warning("Market batch fetch failed", error=str(e))

        # Write to cache
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(snapshot, f, indent=2)

        return snapshot

    @staticmethod
    def load_cache() -> dict:
        if not CACHE_PATH.exists():
            return {}
        with open(CACHE_PATH) as f:
            return json.load(f)