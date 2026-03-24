"""Bluesky scraper — searches public posts via the AT Protocol API."""

from __future__ import annotations

import logging
import re

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

PUBLIC_API = "https://public.api.bsky.app/xrpc"
AUTH_API = "https://bsky.social/xrpc"

# Match URLs in post text (simplified — covers http/https links)
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")


@register_scraper("bluesky_feed")
class BlueskyFeedScraper(BaseScraper):
    """Fetches posts containing links from Bluesky.

    Uses ``source.query`` as a search term for public post search.
    Optionally uses ``source.api_key`` (format: ``handle:app_password``)
    for authenticated timeline access.
    """

    async def extract_articles(self) -> list[ArticleEntry]:
        max_articles = self.source.max_articles

        if self.source.api_key:
            return await self._fetch_authenticated(max_articles)
        return await self._fetch_public_search(max_articles)

    async def _fetch_public_search(self, max_articles: int) -> list[ArticleEntry]:
        query = self.source.query
        if not query:
            log.warning("BlueskyFeedScraper requires source.query for public search on '%s'", self.source.name)
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    f"{PUBLIC_API}/app.bsky.feed.searchPosts",
                    params={"q": query, "limit": min(max_articles * 3, 100)},
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("Bluesky search failed for '%s'", self.source.name, exc_info=True)
                return []

        data = resp.json()
        return self._extract_from_posts(data.get("posts", []), max_articles)

    async def _fetch_authenticated(self, max_articles: int) -> list[ArticleEntry]:
        api_key = self.source.api_key or ""
        if ":" not in api_key:
            log.warning("Bluesky api_key must be 'handle:app_password' for '%s'", self.source.name)
            return []

        handle, password = api_key.split(":", 1)

        async with httpx.AsyncClient(timeout=30) as client:
            # Create session
            try:
                session_resp = await client.post(
                    f"{AUTH_API}/com.atproto.server.createSession",
                    json={"identifier": handle, "password": password},
                )
                session_resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("Bluesky auth failed for '%s'", self.source.name, exc_info=True)
                return []

            token = session_resp.json().get("accessJwt", "")

            # Fetch timeline
            try:
                resp = await client.get(
                    f"{AUTH_API}/app.bsky.feed.getTimeline",
                    params={"limit": min(max_articles * 3, 100)},
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("Bluesky timeline fetch failed for '%s'", self.source.name, exc_info=True)
                return []

        data = resp.json()
        posts = [item.get("post", {}) for item in data.get("feed", [])]
        return self._extract_from_posts(posts, max_articles)

    def _extract_from_posts(self, posts: list[dict], max_articles: int) -> list[ArticleEntry]:
        """Extract articles from posts that contain URLs."""
        articles: list[ArticleEntry] = []
        seen_urls: set[str] = set()

        for post in posts:
            if len(articles) >= max_articles:
                break

            record = post.get("record", {})
            text = record.get("text", "")

            # Look for URLs in the post text
            urls = _URL_RE.findall(text)

            # Also check for link facets (structured URL embeds)
            for facet in record.get("facets", []):
                for feature in facet.get("features", []):
                    if feature.get("$type") == "app.bsky.richtext.facet#link":
                        uri = feature.get("uri", "")
                        if uri:
                            urls.append(uri)

            # Also check embeds for external links
            embed = post.get("embed", {})
            if embed.get("$type") == "app.bsky.embed.external#view":
                ext = embed.get("external", {})
                if ext.get("uri"):
                    urls.append(ext["uri"])

            for url in urls:
                # Skip Bluesky-internal links
                if "bsky.app" in url or "bsky.social" in url:
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Use first ~120 chars of post text as title
                title = text[:120].replace("\n", " ").strip()
                if len(text) > 120:
                    title += "..."

                articles.append(
                    ArticleEntry(
                        title=title,
                        url=url,
                        source_name=self.source.name,
                        snippet=text[:400] if text else None,
                    )
                )
                break  # one article per post

        log.info("Bluesky scraper found %d articles for '%s'", len(articles), self.source.name)
        return articles
