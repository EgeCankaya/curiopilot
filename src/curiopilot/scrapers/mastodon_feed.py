"""Mastodon scraper — fetches toots with links from public or authenticated timelines."""

from __future__ import annotations

import logging
import re

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

# Extract href URLs from <a> tags in HTML
_HREF_RE = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)

# Match URLs in plain text (fallback)
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")

# Strip HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@register_scraper("mastodon_feed")
class MastodonFeedScraper(BaseScraper):
    """Fetches toots containing links from a Mastodon instance.

    - ``source.url``: Instance URL (e.g., ``https://mastodon.social``)
    - ``source.query``: Hashtag to follow (e.g., ``machinelearning``)
    - ``source.api_key`` (optional): Bearer token for home timeline access
    """

    async def extract_articles(self) -> list[ArticleEntry]:
        instance = (self.source.url or "").rstrip("/")
        if not instance:
            log.warning("MastodonFeedScraper requires source.url (instance URL) for '%s'", self.source.name)
            return []

        max_articles = self.source.max_articles
        headers: dict[str, str] = {}

        if self.source.api_key:
            headers["Authorization"] = f"Bearer {self.source.api_key}"
            endpoint = f"{instance}/api/v1/timelines/home"
        elif self.source.query:
            hashtag = self.source.query.lstrip("#")
            endpoint = f"{instance}/api/v1/timelines/tag/{hashtag}"
        else:
            endpoint = f"{instance}/api/v1/timelines/public"

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    endpoint,
                    params={"limit": min(max_articles * 3, 40)},
                    headers=headers,
                )
                resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("Mastodon request failed for '%s'", self.source.name, exc_info=True)
                return []

        toots: list[dict] = resp.json()
        return self._extract_from_toots(toots, max_articles)

    def _extract_from_toots(self, toots: list[dict], max_articles: int) -> list[ArticleEntry]:
        """Extract articles from toots that contain external URLs."""
        articles: list[ArticleEntry] = []
        seen_urls: set[str] = set()

        for toot in toots:
            if len(articles) >= max_articles:
                break

            content_html = toot.get("content", "")
            plain_text = _HTML_TAG_RE.sub("", content_html).strip()

            # Prefer card/preview links (Mastodon auto-generates link previews)
            card = toot.get("card")
            if card and card.get("url"):
                url = card["url"]
                title = card.get("title") or plain_text[:120]
                snippet = card.get("description") or plain_text[:400]
            else:
                # Extract URLs from HTML href attributes first, then plain text
                urls = _HREF_RE.findall(content_html)
                if not urls:
                    urls = _URL_RE.findall(plain_text)
                # Filter out instance-internal links
                instance = (self.source.url or "").rstrip("/")
                external = [u for u in urls if not u.startswith(instance)]
                if not external:
                    continue
                url = external[0]
                title = plain_text[:120]
                snippet = plain_text[:400]

            if url in seen_urls:
                continue
            seen_urls.add(url)

            if len(title) > 120:
                title = title[:117] + "..."

            articles.append(
                ArticleEntry(
                    title=title,
                    url=url,
                    source_name=self.source.name,
                    snippet=snippet if snippet else None,
                )
            )

        log.info("Mastodon scraper found %d articles for '%s'", len(articles), self.source.name)
        return articles
