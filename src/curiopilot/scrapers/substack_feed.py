"""Substack scraper — fetches articles from a Substack newsletter's RSS feed."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)


@register_scraper("substack_feed")
class SubstackFeedScraper(BaseScraper):
    """Fetches articles from a Substack newsletter RSS feed.

    Expects ``source.url`` to be a Substack URL (e.g. ``https://example.substack.com``).
    Automatically appends ``/feed`` if not already present.
    """

    async def extract_articles(self) -> list[ArticleEntry]:
        url = self.source.url
        if not url:
            log.warning("SubstackFeedScraper requires source.url for '%s'", self.source.name)
            return []

        # Auto-append /feed for bare Substack URLs
        if not url.rstrip("/").endswith("/feed"):
            url = url.rstrip("/") + "/feed"

        max_articles = self.source.max_articles

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("Substack feed request failed for '%s'", self.source.name, exc_info=True)
                return []

        return self._parse_rss(resp.text, max_articles)

    def _parse_rss(self, xml_text: str, max_articles: int) -> list[ArticleEntry]:
        articles: list[ArticleEntry] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            log.warning("Failed to parse Substack RSS for '%s'", self.source.name)
            return articles

        for item in root.findall(".//item")[:max_articles]:
            title = _text(item, "title")
            link = _text(item, "link")
            desc = _text(item, "description")
            if not title or not link:
                continue

            articles.append(
                ArticleEntry(
                    title=title,
                    url=link,
                    source_name=self.source.name,
                    snippet=desc[:400] if desc else None,
                )
            )

        log.info("Substack scraper found %d articles for '%s'", len(articles), self.source.name)
        return articles


def _text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""
