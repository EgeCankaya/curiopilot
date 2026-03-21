"""Reddit scraper using public JSON listings (no auth required)."""

from __future__ import annotations

import asyncio
import logging

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

from curiopilot.utils.fetch import random_user_agent


@register_scraper("reddit_json")
class RedditJsonScraper(BaseScraper):
    """Fetches posts from a subreddit via Reddit's public JSON endpoint.

    Expects ``source.url`` to be something like
    ``https://www.reddit.com/r/MachineLearning/hot.json`` or just
    ``r/MachineLearning`` (in which case we build the URL).
    """

    async def extract_articles(self) -> list[ArticleEntry]:
        max_articles = self.source.max_articles
        delay = self.source.request_delay_seconds

        url = self._build_url()
        headers = {"User-Agent": random_user_agent()}

        articles: list[ArticleEntry] = []
        after: str | None = None
        fetched = 0

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            while fetched < max_articles:
                params: dict[str, str | int] = {"limit": min(25, max_articles - fetched)}
                if after:
                    params["after"] = after

                try:
                    resp = await client.get(url, headers=headers, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError:
                    log.warning("Reddit request failed for %s", url, exc_info=True)
                    break

                listing = data.get("data", {})
                children = listing.get("children", [])
                if not children:
                    break

                for child in children:
                    post = child.get("data", {})
                    if post.get("stickied"):
                        continue

                    post_url = post.get("url", "")
                    title = post.get("title", "")
                    if not post_url or not title:
                        continue

                    # Self-posts link to the Reddit thread
                    if post.get("is_self"):
                        post_url = f"https://www.reddit.com{post.get('permalink', '')}"

                    selftext = post.get("selftext", "")
                    snippet = selftext[:300] if selftext else None

                    articles.append(ArticleEntry(
                        title=title,
                        url=post_url,
                        source_name=self.source.name,
                        snippet=snippet,
                        score=post.get("score"),
                    ))
                    fetched += 1
                    if fetched >= max_articles:
                        break

                after = listing.get("after")
                if not after:
                    break

                await asyncio.sleep(delay)

        log.info("Reddit scraper found %d articles from %s", len(articles), url)
        return articles

    def _build_url(self) -> str:
        raw = self.source.url or ""
        if raw.startswith("http"):
            u = raw.rstrip("/")
            return u if u.endswith(".json") else u + ".json"

        # Accept shorthand like "r/MachineLearning"
        sub = raw.strip("/")
        if not sub.startswith("r/"):
            sub = f"r/{sub}"
        return f"https://www.reddit.com/{sub}/hot.json"
