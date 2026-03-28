"""
GDELT ingestor.
GDELT (Global Database of Events, Language, and Tone) is a free,
real-time open-data platform monitoring world events.
It already has event codes, actor extraction, and geo-coordinates —
which means we get structured geopolitical data for free.

We use the GDELT DOC 2.0 API to pull recent articles mentioning
geopolitical themes, then normalise them into our Article schema.

GDELT event codes (CAMEO codes) we care about:
  1x = Verbal conflict  14 = Protest  18 = Assault
  19 = Fight           20 = Use of conventional force
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.db.models import Article

log = structlog.get_logger()

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Geopolitical themes we want to track
GDELT_THEMES = [
    "CRISISLEX_CRISISLEXREC",    # crisis
    "WB_696_POLITICAL_VIOLENCE",  # political violence
    "TAX_FNCACT_REBEL",           # rebels/insurgents
    "SANCTIONS",                   # economic sanctions
    "ECON_OILPRICE",              # oil prices
    "ECON_GOLD",                  # gold markets
    "WB_2350_NATURAL_DISASTER",   # natural disasters (macro risk)
]


class GDELTIngestor:
    def __init__(self, db: AsyncSession):
        self.db = db

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def _query_gdelt(self, query: str, max_records: int = 50) -> list[dict]:
        """Query GDELT DOC API and return article list."""
        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": max_records,
            "format": "json",
            "timespan": "15min",  # last 15 minutes — matches our scheduler interval
            "sort": "datedesc",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(GDELT_DOC_API, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("articles", [])

    async def _article_exists(self, url: str) -> bool:
        result = await self.db.execute(
            select(Article.id).where(Article.url == url).limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _parse_gdelt_date(self, date_str: Optional[str]) -> datetime:
        if not date_str:
            return datetime.now(timezone.utc)
        try:
            return datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)

    async def ingest(self) -> int:
        """Pull GDELT articles for all tracked themes. Returns new article count."""
        new_count = 0

        for theme in GDELT_THEMES:
            try:
                articles = await self._query_gdelt(f"theme:{theme}")
            except Exception as e:
                log.warning("GDELT fetch failed", theme=theme, error=str(e))
                continue

            for art in articles:
                url: Optional[str] = art.get("url")
                title: Optional[str] = art.get("title")
                if not url or not title:
                    continue

                if await self._article_exists(url):
                    continue

                article = Article(
                    source="gdelt",
                    source_tier=2,
                    url=url,
                    title=title,
                    body=None,  # GDELT doesn't give body — NLP runs on title only
                    published_at=self._parse_gdelt_date(art.get("seendate")),
                    language=art.get("language", "English")[:8],
                    is_processed=False,
                )
                self.db.add(article)
                new_count += 1

        log.info("GDELT ingestion complete", new_articles=new_count)
        await self.db.flush()
        return new_count
