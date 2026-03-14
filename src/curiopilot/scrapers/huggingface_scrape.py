"""Hugging Face Papers scraper using Playwright to scrape huggingface.co/papers."""

from __future__ import annotations

import logging

import httpx

from curiopilot.models import ArticleEntry
from curiopilot.scrapers import register_scraper
from curiopilot.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

HF_PAPERS_URL = "https://huggingface.co/papers"
HF_API_URL = "https://huggingface.co/api/daily_papers"


@register_scraper("huggingface_scrape")
class HuggingFaceScraper(BaseScraper):
    """Fetches trending papers from Hugging Face.

    Tries the lightweight JSON API first (``/api/daily_papers``),
    falling back to Playwright-based HTML scraping if that fails.
    """

    async def extract_articles(self) -> list[ArticleEntry]:
        max_articles = self.source.max_articles

        articles = await self._try_api(max_articles)
        if articles is not None:
            return articles[:max_articles]

        articles = await self._try_playwright(max_articles)
        return articles[:max_articles]

    async def _try_api(self, max_articles: int) -> list[ArticleEntry] | None:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(
                    HF_API_URL,
                    headers={"User-Agent": "CurioPilot/0.1"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            log.debug("HF daily_papers API unavailable, will try Playwright")
            return None

        if not isinstance(data, list):
            return None

        articles: list[ArticleEntry] = []
        for item in data[:max_articles]:
            paper = item.get("paper", {})
            title = paper.get("title", "").strip()
            paper_id = paper.get("id", "")
            if not title or not paper_id:
                continue

            url = f"https://huggingface.co/papers/{paper_id}"
            summary = paper.get("summary", "")
            snippet = summary[:400] if summary else None
            upvotes = item.get("numUpvotes")

            articles.append(ArticleEntry(
                title=title,
                url=url,
                source_name=self.source.name,
                snippet=snippet,
                score=upvotes,
            ))

        log.info("HF scraper (API) found %d papers", len(articles))
        return articles

    async def _try_playwright(self, max_articles: int) -> list[ArticleEntry]:
        articles: list[ArticleEntry] = []
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(HF_PAPERS_URL, wait_until="domcontentloaded", timeout=30000)

                cards = await page.query_selector_all("article a[href*='/papers/']")
                seen_urls: set[str] = set()
                for card in cards[:max_articles * 2]:
                    href = await card.get_attribute("href")
                    text = (await card.inner_text()).strip()
                    if not href or not text:
                        continue
                    url = f"https://huggingface.co{href}" if href.startswith("/") else href
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    articles.append(ArticleEntry(
                        title=text,
                        url=url,
                        source_name=self.source.name,
                    ))
                    if len(articles) >= max_articles:
                        break

                await browser.close()
        except Exception:
            log.warning("HF Playwright scraper failed", exc_info=True)

        log.info("HF scraper (Playwright) found %d papers", len(articles))
        return articles
