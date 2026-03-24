"""Podcast RSS scraper — extracts episode metadata and show notes from podcast feeds."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)


@register_scraper("podcast_rss")
class PodcastRssScraper(BaseScraper):
    """Fetches episode show notes from a podcast RSS feed.

    Only extracts text metadata (title, link, description) — does not
    download or transcribe audio files.
    """

    async def extract_articles(self) -> list[ArticleEntry]:
        url = self.source.url
        if not url:
            log.warning("PodcastRssScraper requires source.url for '%s'", self.source.name)
            return []

        max_articles = self.source.max_articles

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("Podcast RSS request failed for '%s'", self.source.name, exc_info=True)
                return []

        return self._parse_feed(resp.text, max_articles)

    def _parse_feed(self, xml_text: str, max_articles: int) -> list[ArticleEntry]:
        articles: list[ArticleEntry] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            log.warning("Failed to parse podcast RSS for '%s'", self.source.name)
            return articles

        for item in root.findall(".//item")[:max_articles]:
            title = _text(item, "title")
            link = _text(item, "link")
            desc = _text(item, "description")

            if not title:
                continue
            # Some podcast feeds lack <link> per episode; fall back to enclosure URL
            if not link:
                enclosure = item.find("enclosure")
                if enclosure is not None:
                    link = enclosure.get("url", "")
            if not link:
                continue

            # Strip HTML tags from description (show notes often contain HTML)
            snippet = _strip_html(desc)[:500] if desc else None

            articles.append(
                ArticleEntry(
                    title=title,
                    url=link,
                    source_name=self.source.name,
                    snippet=snippet,
                )
            )

        log.info("Podcast RSS scraper found %d episodes for '%s'", len(articles), self.source.name)
        return articles


def _text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text).strip()
