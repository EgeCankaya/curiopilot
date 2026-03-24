"""Relevance‑filter agent — scores articles against user interests via a 7B LLM."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import httpx
from pydantic import ValidationError

from curiopilot.config import AppConfig
from curiopilot.llm.ollama import OllamaClient
from curiopilot.models import ArticleEntry, RelevanceScore, ScoredArticle

log = logging.getLogger(__name__)

_MAX_PARSE_RETRIES = 2


@dataclass
class FilterFailure:
    """Record of a single article that failed during filtering."""

    url: str
    title: str
    source_name: str
    error_type: str
    error_message: str


def _build_prompt(article: ArticleEntry, config: AppConfig) -> str:
    interests = config.interests
    primary = ", ".join(interests.primary)
    secondary = ", ".join(interests.secondary) if interests.secondary else "none"
    excluded = ", ".join(interests.excluded) if interests.excluded else "none"

    text = article.title
    if article.snippet:
        text += f"\n{article.snippet}"

    return (
        "You are a relevance‑scoring assistant. Given the user's interests, "
        "rate the article's relevance from 0 to 10 and give a one‑sentence "
        "justification.\n\n"
        f"Primary interests: {primary}\n"
        f"Secondary interests: {secondary}\n"
        f"Excluded topics: {excluded}\n\n"
        f"Article:\n{text}\n\n"
        'Respond with ONLY a JSON object: {"score": <int 0-10>, "justification": "<string>"}'
    )


async def _score_one(
    article: ArticleEntry,
    config: AppConfig,
    client: OllamaClient,
    *,
    keep_alive: int | str | None = None,
    breaker: object | None = None,
) -> ScoredArticle | FilterFailure:
    """Score a single article. Returns ScoredArticle on success or FilterFailure on error."""
    from curiopilot.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

    model = config.models.filter_model
    prompt = _build_prompt(article, config)

    # Check circuit breaker before attempting
    if isinstance(breaker, CircuitBreaker):
        try:
            breaker.check()
        except CircuitBreakerOpen:
            return FilterFailure(
                url=article.url,
                title=article.title,
                source_name=article.source_name,
                error_type="circuit_breaker",
                error_message="Circuit breaker open — Ollama unresponsive",
            )

    parsed: RelevanceScore | None = None
    last_error = ""
    error_type = "parse_error"

    for attempt in range(_MAX_PARSE_RETRIES + 1):
        try:
            raw = await asyncio.wait_for(
                client.generate_json(model, prompt, keep_alive=keep_alive),
                timeout=config.ollama.filter_timeout_seconds,
            )
            parsed = RelevanceScore.model_validate(raw)
            if isinstance(breaker, CircuitBreaker):
                breaker.record_success()
            break
        except asyncio.TimeoutError:
            error_type = "timeout"
            last_error = f"Timed out after {config.ollama.filter_timeout_seconds}s"
            log.warning("Timeout scoring '%s' (attempt %d)", article.title, attempt + 1)
            if isinstance(breaker, CircuitBreaker):
                breaker.record_failure()
            break  # Don't retry timeouts
        except (ValidationError, json.JSONDecodeError, httpx.HTTPError) as exc:
            error_type = "http_error" if isinstance(exc, httpx.HTTPError) else "parse_error"
            last_error = str(exc)
            log.warning(
                "Parse attempt %d failed for '%s': %s",
                attempt + 1,
                article.title,
                exc,
            )
            if isinstance(exc, httpx.HTTPError) and isinstance(breaker, CircuitBreaker):
                breaker.record_failure()
        except Exception as exc:
            error_type = "unexpected"
            last_error = str(exc)
            log.error(
                "Unexpected error scoring '%s': %s", article.title, exc,
                exc_info=True,
            )
            break

    if parsed is None:
        log.warning("Skipping article after retries: %s", article.title)
        return FilterFailure(
            url=article.url,
            title=article.title,
            source_name=article.source_name,
            error_type=error_type,
            error_message=last_error,
        )

    return ScoredArticle(article=article, relevance=parsed)


async def score_articles(
    articles: list[ArticleEntry],
    config: AppConfig,
    client: OllamaClient,
    *,
    keep_alive: int | str | None = None,
    breaker: object | None = None,
    concurrency: int = 1,
    failures: list[FilterFailure] | None = None,
) -> list[ScoredArticle]:
    """Score articles with optional concurrency, circuit breaker, and failure tracking."""
    sem = asyncio.Semaphore(concurrency)
    scored: list[ScoredArticle] = []
    _failures = failures if failures is not None else []

    completed = 0
    lock = asyncio.Lock()

    async def _bounded(article: ArticleEntry) -> ScoredArticle | FilterFailure:
        nonlocal completed
        async with sem:
            result = await _score_one(
                article, config, client, keep_alive=keep_alive, breaker=breaker,
            )
        async with lock:
            completed += 1
            if isinstance(result, ScoredArticle):
                log.info(
                    "[%d/%d] %s -> %d/10 (%s)",
                    completed,
                    len(articles),
                    result.article.title[:60],
                    result.relevance.score,
                    result.relevance.justification[:80],
                )
        return result

    results = await asyncio.gather(
        *[_bounded(a) for a in articles], return_exceptions=True,
    )

    for r in results:
        if isinstance(r, ScoredArticle):
            scored.append(r)
        elif isinstance(r, FilterFailure):
            _failures.append(r)
        elif isinstance(r, BaseException):
            log.error("Unexpected exception in filter gather: %s", r)

    return scored
