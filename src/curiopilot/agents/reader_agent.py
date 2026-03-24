"""Deep-reader agent -- fetches article body, extracts text, and produces an ArticleSummary via the 14B model."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
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


@dataclass
class ReaderFailure:
    """Record of a single article that failed during reading."""

    url: str
    title: str
    source_name: str
    phase: str  # 'fetch' or 'summarize'
    error_type: str
    error_message: str


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


async def _process_one_article(
    sa: ScoredArticle,
    context_holder: dict,
    context_lock: asyncio.Lock,
    browser: object,
    fetch_sem: asyncio.Semaphore,
    llm_sem: asyncio.Semaphore,
    config: AppConfig,
    client: OllamaClient,
    breaker: object | None,
) -> ArticleSummary | ReaderFailure:
    """Fetch and summarize a single article with bounded concurrency."""
    import random

    from curiopilot.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

    article = sa.article

    # ── Fetch phase (bounded by fetch_sem) ──
    html = None
    async with fetch_sem:
        try:
            html = await asyncio.wait_for(
                fetch_article_html(article.url, context=context_holder["ctx"]),
                timeout=config.ollama.fetch_timeout_seconds,
            )
        except asyncio.TimeoutError:
            log.warning("Fetch timeout for %s", article.url)

        if html is None:
            # Rotate context and retry
            async with context_lock:
                try:
                    await context_holder["ctx"].close()
                    context_holder["ctx"] = await create_stealth_context(browser)
                except Exception:
                    pass
            await asyncio.sleep(random.uniform(3.0, 6.0))
            try:
                html = await asyncio.wait_for(
                    fetch_article_html(article.url, context=context_holder["ctx"]),
                    timeout=config.ollama.fetch_timeout_seconds,
                )
            except asyncio.TimeoutError:
                log.warning("Fetch retry timeout for %s", article.url)

        # Add polite delay
        await asyncio.sleep(random.uniform(2.0, 5.0))

    if html is None:
        return ReaderFailure(
            url=article.url, title=article.title, source_name=article.source_name,
            phase="fetch", error_type="http_error",
            error_message="Could not fetch article body after retries",
        )

    body = extract_body_text(html, url=article.url)
    if len(body) < 100:
        return ReaderFailure(
            url=article.url, title=article.title, source_name=article.source_name,
            phase="fetch", error_type="parse_error",
            error_message=f"Extracted body too short ({len(body)} chars)",
        )

    # ── Summarize phase (bounded by llm_sem) ──
    if isinstance(breaker, CircuitBreaker):
        try:
            breaker.check()
        except CircuitBreakerOpen:
            return ReaderFailure(
                url=article.url, title=article.title, source_name=article.source_name,
                phase="summarize", error_type="circuit_breaker",
                error_message="Circuit breaker open — Ollama unresponsive",
            )

    async with llm_sem:
        try:
            summary = await asyncio.wait_for(
                _summarize_text(body, article.title, article.source_name, article.url, config, client),
                timeout=config.ollama.summarize_timeout_seconds,
            )
        except asyncio.TimeoutError:
            log.warning("Summarize timeout for %s", article.url)
            if isinstance(breaker, CircuitBreaker):
                breaker.record_failure()
            return ReaderFailure(
                url=article.url, title=article.title, source_name=article.source_name,
                phase="summarize", error_type="timeout",
                error_message=f"Timed out after {config.ollama.summarize_timeout_seconds}s",
            )

    if summary is None:
        if isinstance(breaker, CircuitBreaker):
            breaker.record_failure()
        return ReaderFailure(
            url=article.url, title=article.title, source_name=article.source_name,
            phase="summarize", error_type="parse_error",
            error_message="Failed to produce summary after retries",
        )

    if isinstance(breaker, CircuitBreaker):
        breaker.record_success()

    summary.body_content = body
    summary.body_content_type = "plaintext"
    log.info("  -> Summary: %d concepts, depth=%d", len(summary.key_concepts), summary.technical_depth)
    return summary


async def read_and_summarize(
    scored_articles: list[ScoredArticle],
    config: AppConfig,
    client: OllamaClient,
    *,
    progress_callback: ProgressCallback | None = None,
    breaker: object | None = None,
    fetch_concurrency: int = 1,
    llm_concurrency: int = 1,
    failures: list[ReaderFailure] | None = None,
) -> list[ArticleSummary]:
    """Fetch, extract, and summarize articles with optional concurrency.

    Uses a stealth Playwright context shared across fetches, with httpx and
    trafilatura as fallback tiers. Adds random delays between fetches and
    rotates the browser context when a bot challenge is detected.
    """
    summaries: list[ArticleSummary] = []
    _failures = failures if failures is not None else []

    fetch_sem = asyncio.Semaphore(fetch_concurrency)
    llm_sem = asyncio.Semaphore(llm_concurrency)
    context_lock = asyncio.Lock()

    completed = 0
    progress_lock = asyncio.Lock()

    async def _process_and_report(sa: ScoredArticle) -> ArticleSummary | ReaderFailure:
        nonlocal completed
        log.info("Reading: %s", sa.article.title[:70])
        result = await _process_one_article(
            sa, context_holder, context_lock, browser,
            fetch_sem, llm_sem, config, client, breaker,
        )
        async with progress_lock:
            completed += 1
            if progress_callback and callable(progress_callback):
                progress_callback(completed, len(scored_articles))
        return result

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await create_stealth_context(browser)
        context_holder = {"ctx": context}
        try:
            results = await asyncio.gather(
                *[_process_and_report(sa) for sa in scored_articles],
                return_exceptions=True,
            )

            for r in results:
                if isinstance(r, ArticleSummary):
                    summaries.append(r)
                elif isinstance(r, ReaderFailure):
                    _failures.append(r)
                elif isinstance(r, BaseException):
                    log.error("Unexpected exception in reader gather: %s", r)
        finally:
            try:
                await context_holder["ctx"].close()
            except Exception:
                pass
            await browser.close()

    return summaries
