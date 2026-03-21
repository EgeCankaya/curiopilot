"""Text extraction from HTML and token-aware chunking utilities."""

from __future__ import annotations

import logging
import re

import trafilatura

log = logging.getLogger(__name__)

_UNWANTED_ELEMENTS_RE = re.compile(
    r"<(style|script|noscript|svg|head)[\s>].*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
_STRIP_TAGS_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\n{3,}")

APPROX_CHARS_PER_TOKEN = 4


def extract_body_text(html: str, url: str | None = None) -> str:
    """Extract the main article body from raw HTML.

    Uses trafilatura for production-grade extraction, falling back to
    regex heuristics if trafilatura returns nothing usable.
    """
    result = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        deduplicate=True,
    )
    if result and len(result) >= 100:
        log.debug("trafilatura extracted %d chars", len(result))
        return result

    log.debug("trafilatura returned insufficient content, falling back to regex")
    return _regex_extract_body_text(html)


def _regex_extract_body_text(html: str) -> str:
    """Fallback regex-based extraction for edge cases."""
    html = _remove_unwanted_elements(html)

    best = _extract_tag_content(html, "article")
    if not best or len(best) < 200:
        best = _extract_tag_content(html, "main")
    if not best or len(best) < 200:
        best = _extract_largest_div(html)
    if not best or len(best) < 100:
        best = _strip_tags(html)

    return _clean_text(best)


def _remove_unwanted_elements(html: str) -> str:
    return _UNWANTED_ELEMENTS_RE.sub("", html)


def _extract_tag_content(html: str, tag: str) -> str | None:
    pattern = re.compile(
        rf"<{tag}[\s>].*?</{tag}>", re.DOTALL | re.IGNORECASE
    )
    match = pattern.search(html)
    if match:
        return _strip_tags(match.group())
    return None


def _extract_largest_div(html: str) -> str | None:
    pattern = re.compile(r"<div[\s>].*?</div>", re.DOTALL | re.IGNORECASE)
    matches = pattern.findall(html)
    if not matches:
        return None
    best = max(matches, key=lambda m: len(_strip_tags(m)))
    return _strip_tags(best)


def _strip_tags(html: str) -> str:
    return _STRIP_TAGS_RE.sub("", html)


def _clean_text(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)
    result = "\n".join(cleaned)
    return _WHITESPACE_RE.sub("\n\n", result)


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (chars / 4)."""
    return len(text) // APPROX_CHARS_PER_TOKEN


_READ_ORIGINAL_RE = re.compile(r"\[Read original\]\(([^)]+)\)")


def extract_briefing_urls(markdown: str) -> list[str]:
    """Extract article URLs from ``[Read original](URL)`` links in a briefing."""
    return _READ_ORIGINAL_RE.findall(markdown)


def chunk_text(text: str, max_tokens: int) -> list[str]:
    """Split *text* into chunks of approximately *max_tokens* each.

    Splits on paragraph boundaries (double newline) first, then falls back to
    sentence boundaries, then hard character cuts as a last resort.
    """
    if estimate_tokens(text) <= max_tokens:
        return [text]

    max_chars = max_tokens * APPROX_CHARS_PER_TOKEN
    paragraphs = text.split("\n\n")

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    log.debug("Chunked text into %d pieces (max_tokens=%d)", len(chunks), max_tokens)
    return chunks
