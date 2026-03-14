"""Relevance‑filter agent — scores articles against user interests via a 7B LLM."""

from __future__ import annotations

import json
import logging

import httpx
from pydantic import ValidationError

from curiopilot.config import AppConfig
from curiopilot.llm.ollama import OllamaClient
from curiopilot.models import ArticleEntry, RelevanceScore, ScoredArticle

log = logging.getLogger(__name__)

_MAX_PARSE_RETRIES = 2


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


async def score_articles(
    articles: list[ArticleEntry],
    config: AppConfig,
    client: OllamaClient,
    *,
    keep_alive: int | str | None = None,
) -> list[ScoredArticle]:
    """Score every article sequentially (concurrency=1) and return results."""
    model = config.models.filter_model
    scored: list[ScoredArticle] = []

    for idx, article in enumerate(articles, 1):
        prompt = _build_prompt(article, config)
        log.debug("Scoring article %d/%d: %s", idx, len(articles), article.title)

        parsed: RelevanceScore | None = None
        for attempt in range(_MAX_PARSE_RETRIES + 1):
            try:
                raw = await client.generate_json(model, prompt, keep_alive=keep_alive)
                parsed = RelevanceScore.model_validate(raw)
                break
            except (ValidationError, json.JSONDecodeError, httpx.HTTPError) as exc:
                log.warning(
                    "Parse attempt %d failed for '%s': %s",
                    attempt + 1,
                    article.title,
                    exc,
                )
            except Exception as exc:
                log.error(
                    "Unexpected error scoring '%s': %s", article.title, exc,
                    exc_info=True,
                )
                break

        if parsed is None:
            log.warning("Skipping article after %d retries: %s", _MAX_PARSE_RETRIES + 1, article.title)
            continue

        scored.append(ScoredArticle(article=article, relevance=parsed))
        log.info(
            "[%d/%d] %s -> %d/10 (%s)",
            idx,
            len(articles),
            article.title[:60],
            parsed.score,
            parsed.justification[:80],
        )

    return scored
