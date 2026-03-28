"""
RSS feed ingestor.
Pulls from a curated list of high-quality news sources.
Source tier determines credibility weight in signal aggregation:
  Tier 1 = wire services (Reuters, AP)
  Tier 2 = major outlets (BBC, Al Jazeera, FT)
  Tier 3 = supplementary
"""
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.db.models import Article

log = structlog.get_logger()

RSS_SOURCES: list[dict] = [
    # Tier 1 — wire services
    {
        "name": "reuters_world",
        "url": "https://feeds.reuters.com/reuters/worldNews",
        "tier": 1,
    },
    {
        "name": "reuters_business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "tier": 1,
    },
    {
        "name": "ap_world",
        "url": "https://rsshub.app/apnews/topics/world-news",
        "tier": 1,
    },
    # Tier 2 — major outlets
    {
        "name": "bbc_world",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "tier": 2,
    },
    {
        "name": "aljazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "tier": 2,
    },
    {
        "name": "ft_world",
        "url": "https://www.ft.com/world?format=rss",
        "tier": 2,
    },
    {
        "name": "guardian_world",
        "url": "https://www.theguardian.com/world/rss",
        "tier": 2,
    },
    # Geopolitics / macro focused
    {
        "name": "foreignpolicy",
        "url": "https://foreignpolicy.com/feed/",
        "tier": 2,
    },
    {
        "name": "economist_world",
        "url": "https://www.economist.com/the-world-this-week/rss.xml",
        "tier": 2,
    },
]


def _parse_date(entry: feedparser.FeedParserDict) -> datetime:
    """Best-effort date parsing from RSS entry."""
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None)
        if val:
            import time
            return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
    # Fallback — current time
    return datetime.now(timezone.utc)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class RSSIngestor:
    def __init__(self, db: AsyncSession):
        self.db = db

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _fetch_feed(self, url: str) -> feedparser.FeedParserDict:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "GeoPulse/1.0"})
            resp.raise_for_status()
            return feedparser.parse(resp.text)

    async def _article_exists(self, url: str) -> bool:
        result = await self.db.execute(
            select(Article.id).where(Article.url == url).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def ingest(self) -> int:
        """Pull all RSS sources and insert new articles. Returns count of new articles."""
        new_count = 0

        for source in RSS_SOURCES:
            try:
                feed = await self._fetch_feed(source["url"])
            except Exception as e:
                log.warning("RSS fetch failed", source=source["name"], error=str(e))
                continue

            for entry in feed.entries:
                url: Optional[str] = getattr(entry, "link", None)
                title: Optional[str] = getattr(entry, "title", None)
                if not url or not title:
                    continue

                if await self._article_exists(url):
                    continue

                # Extract body from summary/content fields
                body: Optional[str] = None
                if hasattr(entry, "content") and entry.content:
                    body = entry.content[0].get("value", "")
                elif hasattr(entry, "summary"):
                    body = entry.summary

                article = Article(
                    source=source["name"],
                    source_tier=source["tier"],
                    url=url,
                    title=title,
                    body=body,
                    published_at=_parse_date(entry),
                    is_processed=False,
                )
                self.db.add(article)
                new_count += 1

            log.info("RSS source ingested", source=source["name"], new=new_count)

        await self.db.flush()
        return new_count
