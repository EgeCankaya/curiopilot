"""Generic HTML/RSS scraper for simple pages and feeds."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

_USER_AGENT = "CurioPilot/0.1 (knowledge-discovery bot)"


@register_scraper("generic_scrape")
class GenericScrapeScraper(BaseScraper):
    """Scrapes links from a generic HTML page, or parses an RSS/Atom feed.

    Expects ``source.url`` to be a URL to either:
    - An RSS/Atom feed (auto-detected by content type or XML structure)
    - An HTML page containing ``<a>`` links to articles

    This is a best-effort scraper for sources without dedicated implementations.
    """

    async def extract_articles(self) -> list[ArticleEntry]:
        url = self.source.url
        if not url:
            log.warning("GenericScraper requires source.url, none provided for '%s'", self.source.name)
            return []

        max_articles = self.source.max_articles

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("Generic scraper request failed for %s", url, exc_info=True)
                return []

        content_type = resp.headers.get("content-type", "")
        text = resp.text

        if _looks_like_feed(content_type, text):
            return self._parse_feed(text, max_articles)
        return self._parse_html(text, url, max_articles)

    def _parse_feed(self, xml_text: str, max_articles: int) -> list[ArticleEntry]:
        articles: list[ArticleEntry] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            log.warning("Failed to parse XML feed for '%s'", self.source.name)
            return articles

        # RSS 2.0: <channel><item>
        items = root.findall(".//item")
        if items:
            for item in items[:max_articles]:
                title = _text(item, "title")
                link = _text(item, "link")
                desc = _text(item, "description")
                if title and link:
                    articles.append(ArticleEntry(
                        title=title,
                        url=link,
                        source_name=self.source.name,
                        snippet=desc[:400] if desc else None,
                    ))
            log.info("Generic scraper (RSS) found %d items for '%s'", len(articles), self.source.name)
            return articles

        # Atom: <feed><entry>
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        for entry in entries[:max_articles]:
            title_el = entry.find("atom:title", ns)
            title = (title_el.text or "").strip() if title_el is not None else ""
            link_el = entry.find("atom:link[@rel='alternate']", ns)
            if link_el is None:
                link_el = entry.find("atom:link", ns)
            link = (link_el.get("href", "") or "").strip() if link_el is not None else ""
            summary_el = entry.find("atom:summary", ns)
            summary = (summary_el.text or "").strip()[:400] if summary_el is not None else None
            if title and link:
                articles.append(ArticleEntry(
                    title=title,
                    url=link,
                    source_name=self.source.name,
                    snippet=summary,
                ))

        log.info("Generic scraper (Atom) found %d items for '%s'", len(articles), self.source.name)
        return articles

    def _parse_html(self, html: str, base_url: str, max_articles: int) -> list[ArticleEntry]:
        """Naive HTML link extraction -- finds <a> tags with href containing '/article', '/post', '/blog', etc."""
        import re

        articles: list[ArticleEntry] = []
        seen_urls: set[str] = set()

        link_pattern = re.compile(
            r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )

        for match in link_pattern.finditer(html):
            if len(articles) >= max_articles:
                break

            href = match.group(1).strip()
            text = re.sub(r"<[^>]+>", "", match.group(2)).strip()

            if not text or len(text) < 10 or len(text) > 300:
                continue
            if href.startswith("#") or href.startswith("javascript:"):
                continue

            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            articles.append(ArticleEntry(
                title=text,
                url=full_url,
                source_name=self.source.name,
            ))

        log.info("Generic scraper (HTML) found %d links for '%s'", len(articles), self.source.name)
        return articles


def _looks_like_feed(content_type: str, text: str) -> bool:
    if "xml" in content_type or "rss" in content_type or "atom" in content_type:
        return True
    stripped = text.lstrip()[:200]
    return stripped.startswith("<?xml") or stripped.startswith("<rss") or stripped.startswith("<feed")


def _text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""
