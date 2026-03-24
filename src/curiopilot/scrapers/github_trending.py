"""GitHub Trending scraper — parses the public trending page HTML."""

from __future__ import annotations

import logging
import re

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

GITHUB_TRENDING = "https://github.com/trending"


@register_scraper("github_trending")
class GitHubTrendingScraper(BaseScraper):
    """Scrapes trending repositories from GitHub's trending page."""

    async def extract_articles(self) -> list[ArticleEntry]:
        max_articles = self.source.max_articles
        language = self.source.query  # optional language filter

        url = GITHUB_TRENDING
        params = {}
        if language:
            params["language"] = language

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            except httpx.HTTPError:
                log.warning("GitHub Trending request failed", exc_info=True)
                return []

        return self._parse_trending(resp.text, max_articles)

    def _parse_trending(self, html: str, max_articles: int) -> list[ArticleEntry]:
        articles: list[ArticleEntry] = []

        # Each trending repo is in an <article class="Box-row"> element.
        # Extract the repo link (h2 > a with href like /owner/repo).
        row_pattern = re.compile(
            r'<article\s[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
            re.DOTALL | re.IGNORECASE,
        )
        link_pattern = re.compile(
            r'<h2[^>]*>\s*<a\s[^>]*href="(/[^"]+)"[^>]*>',
            re.DOTALL | re.IGNORECASE,
        )
        desc_pattern = re.compile(
            r'<p\s[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>',
            re.DOTALL | re.IGNORECASE,
        )
        stars_pattern = re.compile(
            r'(\d[\d,]*)\s*stars\s+today',
            re.IGNORECASE,
        )

        for match in row_pattern.finditer(html):
            if len(articles) >= max_articles:
                break

            row_html = match.group(1)

            link_match = link_pattern.search(row_html)
            if not link_match:
                continue

            repo_path = link_match.group(1).strip()
            repo_name = repo_path.lstrip("/")
            repo_url = f"https://github.com{repo_path}"

            # Description
            snippet = None
            desc_match = desc_pattern.search(row_html)
            if desc_match:
                snippet = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()[:400]

            # Stars today
            score = None
            stars_match = stars_pattern.search(row_html)
            if stars_match:
                score = int(stars_match.group(1).replace(",", ""))

            articles.append(
                ArticleEntry(
                    title=repo_name,
                    url=repo_url,
                    source_name=self.source.name,
                    snippet=snippet,
                    score=score,
                )
            )

        log.info("GitHub Trending scraper found %d repos", len(articles))
        return articles
