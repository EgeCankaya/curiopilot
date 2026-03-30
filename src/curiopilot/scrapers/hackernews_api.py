"""Hacker News scraper using the official Firebase/Algolia API."""

from __future__ import annotations

import asyncio
import logging

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

HN_API = "https://hacker-news.firebaseio.com/v0"


@register_scraper("hackernews_api")
class HackerNewsApiScraper(BaseScraper):
    """Fetches top stories from Hacker News via the Firebase API."""

    async def extract_articles(self) -> list[ArticleEntry]:
        max_articles = self.source.max_articles
        delay = self.source.request_delay_seconds

        async with httpx.AsyncClient(timeout=30) as client:
            endpoint = self.source.url or f"{HN_API}/topstories.json"
            resp = await client.get(endpoint)
            resp.raise_for_status()
            story_ids: list[int] = resp.json()[:max_articles]

            articles: list[ArticleEntry] = []
            for story_id in story_ids:
                try:
                    item_resp = await client.get(f"{HN_API}/item/{story_id}.json")
                    item_resp.raise_for_status()
                    item = item_resp.json()

                    if not item or item.get("type") != "story":
                        continue

                    url = item.get("url")
                    title = item.get("title", "")
                    if not url:
                        # Ask HN / Show HN posts without external URL
                        url = f"https://news.ycombinator.com/item?id={story_id}"

                    articles.append(
                        ArticleEntry(
                            title=title,
                            url=url,
                            source_name=self.source.name,
                            snippet=item.get("text"),
                            score=item.get("score"),
                        )
                    )
                except httpx.HTTPError:
                    log.warning("Failed to fetch HN item %s, skipping", story_id)

                await asyncio.sleep(delay)

        log.info("HN scraper found %d articles", len(articles))
        return articles
