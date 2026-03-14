"""ArXiv scraper using Atom/RSS feeds via the ArXiv API."""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom"}


@register_scraper("arxiv_feed")
class ArxivFeedScraper(BaseScraper):
    """Fetches recent papers from ArXiv via the Atom feed API.

    Expects ``source.query`` to contain an ArXiv search query, e.g.
    ``cat:cs.AI`` or ``all:"large language models"``.
    ``source.url`` is optional; if provided it is used as the full API URL.
    """

    async def extract_articles(self) -> list[ArticleEntry]:
        max_articles = self.source.max_articles
        delay = self.source.request_delay_seconds
        query = self.source.query or "cat:cs.AI"

        if self.source.url:
            url = self.source.url
            params: dict[str, str | int] = {}
        else:
            url = ARXIV_API
            params = {
                "search_query": query,
                "start": 0,
                "max_results": max_articles,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }

        articles: list[ArticleEntry] = []

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                await asyncio.sleep(delay)
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                xml_text = resp.text
            except httpx.HTTPError:
                log.warning("ArXiv feed request failed for query=%s", query, exc_info=True)
                return articles

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            log.warning("Failed to parse ArXiv XML response")
            return articles

        entries = root.findall("atom:entry", _NS)
        for entry in entries[:max_articles]:
            title_el = entry.find("atom:title", _NS)
            title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""

            link_el = entry.find("atom:id", _NS)
            entry_url = (link_el.text or "").strip() if link_el is not None else ""

            summary_el = entry.find("atom:summary", _NS)
            summary = (summary_el.text or "").strip()[:500] if summary_el is not None else None

            if not title or not entry_url:
                continue

            # Prefer the abstract page URL
            if entry_url.startswith("http://arxiv.org/abs/"):
                entry_url = entry_url.replace("http://", "https://")

            articles.append(ArticleEntry(
                title=title,
                url=entry_url,
                source_name=self.source.name,
                snippet=summary,
                score=None,
            ))

        log.info("ArXiv scraper found %d papers for query=%s", len(articles), query)
        return articles
