"""YouTube RSS scraper — extracts video metadata from YouTube channel Atom feeds."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


@register_scraper("youtube_rss")
class YouTubeRssScraper(BaseScraper):
    """Fetches recent videos from a YouTube channel RSS/Atom feed.

    Expects ``source.url`` to be a YouTube channel feed URL like
    ``https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID``.
    """

    async def extract_articles(self) -> list[ArticleEntry]:
        url = self.source.url
        if not url:
            log.warning("YouTubeRssScraper requires source.url for '%s'", self.source.name)
            return []

        max_articles = self.source.max_articles

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("YouTube RSS request failed for '%s'", self.source.name, exc_info=True)
                return []

        return self._parse_feed(resp.text, max_articles)

    def _parse_feed(self, xml_text: str, max_articles: int) -> list[ArticleEntry]:
        articles: list[ArticleEntry] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            log.warning("Failed to parse YouTube Atom feed for '%s'", self.source.name)
            return articles

        for entry in root.findall("atom:entry", _NS)[:max_articles]:
            title = _atom_text(entry, "atom:title")
            if not title:
                continue

            link = _atom_link(entry)
            if not link:
                continue

            desc = _media_description(entry)
            snippet = _strip_html(desc)[:500] if desc else None

            articles.append(
                ArticleEntry(
                    title=title,
                    url=link,
                    source_name=self.source.name,
                    snippet=snippet,
                )
            )

        log.info("YouTube RSS scraper found %d videos for '%s'", len(articles), self.source.name)
        return articles


def _atom_text(entry: ET.Element, tag: str) -> str:
    """Extract text from a namespaced Atom element."""
    child = entry.find(tag, _NS)
    return (child.text or "").strip() if child is not None else ""


def _atom_link(entry: ET.Element) -> str:
    """Extract the alternate link href from an Atom entry."""
    for link in entry.findall("atom:link", _NS):
        if link.get("rel") == "alternate":
            return link.get("href", "")
    # Fallback: first link element
    first = entry.find("atom:link", _NS)
    return first.get("href", "") if first is not None else ""


def _media_description(entry: ET.Element) -> str:
    """Extract the media:description from a media:group element."""
    group = entry.find("media:group", _NS)
    if group is None:
        return ""
    desc = group.find("media:description", _NS)
    return (desc.text or "").strip() if desc is not None else ""


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text).strip()
