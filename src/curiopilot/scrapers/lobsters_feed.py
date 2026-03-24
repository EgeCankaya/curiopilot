"""Lobste.rs scraper using the public JSON API."""

from __future__ import annotations

import logging

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

LOBSTERS_API = "https://lobste.rs/hottest.json"


@register_scraper("lobsters_feed")
class LobstersFeedScraper(BaseScraper):
    """Fetches hottest stories from Lobste.rs via the public JSON API."""

    async def extract_articles(self) -> list[ArticleEntry]:
        max_articles = self.source.max_articles

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(LOBSTERS_API)
                resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("Lobste.rs API request failed", exc_info=True)
                return []

        stories: list[dict] = resp.json()
        articles: list[ArticleEntry] = []

        for story in stories[:max_articles]:
            title = story.get("title", "")
            url = story.get("url") or story.get("comments_url", "")
            if not title or not url:
                continue

            desc = story.get("description", "")
            articles.append(
                ArticleEntry(
                    title=title,
                    url=url,
                    source_name=self.source.name,
                    snippet=desc[:400] if desc else None,
                    score=story.get("score"),
                )
            )

        log.info("Lobste.rs scraper found %d articles", len(articles))
        return articles
