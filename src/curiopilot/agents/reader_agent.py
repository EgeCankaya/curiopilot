"""Deep-reader agent -- fetches article body, extracts text, and produces an ArticleSummary via the 14B model."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
from playwright.async_api import async_playwright
from pydantic import ValidationError

from curiopilot.config import AppConfig
from curiopilot.llm.ollama import OllamaClient
from curiopilot.models import ArticleSummary, ProgressCallback, ScoredArticle
from curiopilot.utils.fetch import create_stealth_context, fetch_article_html
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
        "You are a research\u2011summarization assistant. Read the article text below "
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
        "You are a research\u2011summarization assistant. Below are summaries of "
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
    """Fetch, extract, and summarize each article.

    Uses a stealth Playwright context shared across fetches, with httpx and
    trafilatura as fallback tiers. Adds random delays between fetches and
    rotates the browser context when a bot challenge is detected.
    """
    import random

    summaries: list[ArticleSummary] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await create_stealth_context(browser)
        try:
            for idx, sa in enumerate(scored_articles, 1):
                article = sa.article
                log.info("[%d/%d] Reading: %s", idx, len(scored_articles), article.title[:70])

                html = await fetch_article_html(article.url, context=context)

                if html is None:
                    log.info("Primary fetch failed, rotating context and retrying: %s", article.url)
                    await context.close()
                    context = await create_stealth_context(browser)
                    await asyncio.sleep(random.uniform(3.0, 6.0))
                    html = await fetch_article_html(article.url, context=context)

                if html is None:
                    log.warning("Could not fetch article body, skipping: %s", article.url)
                    if progress_callback and callable(progress_callback):
                        progress_callback(idx, len(scored_articles))
                    continue

                body = extract_body_text(html, url=article.url)
                if len(body) < 100:
                    log.warning("Extracted body too short (%d chars), skipping: %s", len(body), article.url)
                    if progress_callback and callable(progress_callback):
                        progress_callback(idx, len(scored_articles))
                    continue

                summary = await _summarize_text(
                    body, article.title, article.source_name, article.url, config, client
                )
                if summary:
                    summary.body_content = body
                    summary.body_content_type = "plaintext"
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

                if idx < len(scored_articles):
                    delay = random.uniform(2.0, 5.0)
                    log.debug("Waiting %.1fs before next fetch", delay)
                    await asyncio.sleep(delay)
        finally:
            await context.close()
            await browser.close()

    return summaries
