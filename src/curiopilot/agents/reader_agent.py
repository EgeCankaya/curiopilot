"""Deep‑reader agent — fetches article body, extracts text, and produces an ArticleSummary via the 14B model."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx
from playwright.async_api import async_playwright
from pydantic import ValidationError

from curiopilot.config import AppConfig
from curiopilot.llm.ollama import OllamaClient
from curiopilot.models import ArticleSummary, ProgressCallback, ScoredArticle
from curiopilot.utils.text import chunk_text, estimate_tokens, extract_body_text

log = logging.getLogger(__name__)

_MAX_PARSE_RETRIES = 2


def _build_summary_prompt(
    article_text: str,
    title: str,
    source_name: str,
    url: str,
) -> str:
    return (
        "You are a research‑summarization assistant. Read the article text below "
        "and produce a structured JSON summary.\n\n"
        f"Title: {title}\n"
        f"Source: {source_name}\n"
        f"URL: {url}\n\n"
        "--- ARTICLE TEXT ---\n"
        f"{article_text}\n"
        "--- END ---\n\n"
        "Respond with ONLY a JSON object containing these fields:\n"
        '{\n'
        '  "title": "<article title>",\n'
        '  "source_name": "<source>",\n'
        '  "url": "<url>",\n'
        '  "date_processed": "<ISO datetime>",\n'
        '  "key_concepts": ["concept1", "concept2", ...],  // 3-8 concepts\n'
        '  "summary": "<3-5 sentence summary>",\n'
        '  "novel_insights": "<what is genuinely new or interesting>",\n'
        '  "technical_depth": <1-5>,\n'
        '  "related_topics": ["topic1", "topic2", ...],\n'
        '  "relationships": [{"from": "conceptA", "to": "conceptB", "type": "uses/extends/enables/requires"}, ...]\n'
        '}'
    )


def _build_chunk_summary_prompt(chunk: str, chunk_idx: int, total_chunks: int) -> str:
    return (
        f"You are summarizing part {chunk_idx}/{total_chunks} of a long article. "
        "Produce a concise summary (3-5 sentences) of this section, focusing on "
        "key facts, concepts, and insights.\n\n"
        "--- TEXT ---\n"
        f"{chunk}\n"
        "--- END ---\n\n"
        "Respond with ONLY your summary text (no JSON needed)."
    )


def _build_merge_prompt(
    chunk_summaries: list[str],
    title: str,
    source_name: str,
    url: str,
) -> str:
    merged = "\n\n".join(
        f"[Part {i}] {s}" for i, s in enumerate(chunk_summaries, 1)
    )
    return (
        "You are a research‑summarization assistant. Below are summaries of "
        "different sections of the same article. Merge them into a single "
        "structured JSON summary.\n\n"
        f"Title: {title}\n"
        f"Source: {source_name}\n"
        f"URL: {url}\n\n"
        "--- SECTION SUMMARIES ---\n"
        f"{merged}\n"
        "--- END ---\n\n"
        "Respond with ONLY a JSON object containing these fields:\n"
        '{\n'
        '  "title": "<article title>",\n'
        '  "source_name": "<source>",\n'
        '  "url": "<url>",\n'
        '  "date_processed": "<ISO datetime>",\n'
        '  "key_concepts": ["concept1", "concept2", ...],  // 3-8 concepts\n'
        '  "summary": "<3-5 sentence summary>",\n'
        '  "novel_insights": "<what is genuinely new or interesting>",\n'
        '  "technical_depth": <1-5>,\n'
        '  "related_topics": ["topic1", "topic2", ...],\n'
        '  "relationships": [{"from": "conceptA", "to": "conceptB", "type": "uses/extends/enables/requires"}, ...]\n'
        '}'
    )


async def _fetch_article_html(
    url: str, timeout_ms: int = 30_000, *, browser: object | None = None
) -> str | None:
    """Use Playwright to load a URL and return the page HTML.

    If *browser* is provided, opens a new page on that browser instance
    instead of launching a fresh Chromium process.
    """
    try:
        if browser is not None:
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                return await page.content()
            finally:
                await page.close()
        else:
            async with async_playwright() as pw:
                br = await pw.chromium.launch(headless=True)
                page = await br.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                html = await page.content()
                await br.close()
                return html
    except Exception:
        log.warning("Playwright failed to load %s", url, exc_info=True)
        return None


async def _fetch_article_httpx(url: str) -> str | None:
    """Fallback: fetch via plain HTTP for simple pages or APIs."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "CurioPilot/0.1"})
            resp.raise_for_status()
            return resp.text
    except Exception:
        log.warning("httpx fallback failed for %s", url, exc_info=True)
        return None


async def _summarize_text(
    text: str,
    title: str,
    source_name: str,
    url: str,
    config: AppConfig,
    client: OllamaClient,
) -> ArticleSummary | None:
    """Summarize article text, using map-reduce if it exceeds the chunk threshold."""
    model = config.models.reader_model
    max_tokens = config.chunking.max_tokens_per_chunk

    if estimate_tokens(text) <= max_tokens:
        prompt = _build_summary_prompt(text, title, source_name, url)
        return await _call_summary(prompt, model, client)

    # Map phase: summarize each chunk independently
    chunks = chunk_text(text, max_tokens)
    log.info("Article too long (%d tokens est.), splitting into %d chunks", estimate_tokens(text), len(chunks))

    chunk_summaries: list[str] = []
    for idx, chunk in enumerate(chunks, 1):
        prompt = _build_chunk_summary_prompt(chunk, idx, len(chunks))
        summary_text = await client.generate_text(model, prompt)
        if summary_text.strip():
            chunk_summaries.append(summary_text.strip())

    if not chunk_summaries:
        log.warning("All chunk summaries empty for %s", url)
        return None

    # Reduce phase: merge chunk summaries into one structured summary
    merge_prompt = _build_merge_prompt(chunk_summaries, title, source_name, url)
    return await _call_summary(merge_prompt, model, client)


async def _call_summary(
    prompt: str,
    model: str,
    client: OllamaClient,
) -> ArticleSummary | None:
    """Call the LLM and parse into ArticleSummary with retries."""
    for attempt in range(_MAX_PARSE_RETRIES + 1):
        try:
            raw = await client.generate_json(model, prompt)
            if "date_processed" not in raw or not raw["date_processed"]:
                raw["date_processed"] = datetime.now(timezone.utc).isoformat()
            return ArticleSummary.model_validate(raw)
        except (ValidationError, json.JSONDecodeError, httpx.HTTPError) as exc:
            log.warning("Summary parse attempt %d failed: %s", attempt + 1, exc)
        except Exception as exc:
            log.error("Unexpected error in summary generation: %s", exc, exc_info=True)
            break
    return None


async def read_and_summarize(
    scored_articles: list[ScoredArticle],
    config: AppConfig,
    client: OllamaClient,
    *,
    progress_callback: ProgressCallback | None = None,
) -> list[ArticleSummary]:
    """Fetch, extract, and summarize each article. Returns summaries in order.

    Shares a single Playwright browser instance across all fetches to avoid
    the overhead of launching Chromium per article.
    """
    summaries: list[ArticleSummary] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for idx, sa in enumerate(scored_articles, 1):
                article = sa.article
                log.info("[%d/%d] Reading: %s", idx, len(scored_articles), article.title[:70])

                html = await _fetch_article_html(article.url, browser=browser)
                if html is None:
                    html = await _fetch_article_httpx(article.url)
                if html is None:
                    log.warning("Could not fetch article body, skipping: %s", article.url)
                    continue

                body = extract_body_text(html)
                if len(body) < 100:
                    log.warning("Extracted body too short (%d chars), skipping: %s", len(body), article.url)
                    continue

                summary = await _summarize_text(
                    body, article.title, article.source_name, article.url, config, client
                )
                if summary:
                    summaries.append(summary)
                    log.info(
                        "  -> Summary: %d concepts, depth=%d",
                        len(summary.key_concepts),
                        summary.technical_depth,
                    )
                else:
                    log.warning("  -> Failed to produce summary for: %s", article.url)

                if progress_callback and callable(progress_callback):
                    progress_callback(idx, len(scored_articles))
        finally:
            await browser.close()

    return summaries
