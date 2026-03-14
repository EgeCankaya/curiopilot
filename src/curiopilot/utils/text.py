"""Text extraction from HTML and token-aware chunking utilities."""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

_STRIP_TAGS_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\n{3,}")

APPROX_CHARS_PER_TOKEN = 4


def extract_body_text(html: str) -> str:
    """Extract the main article body from raw HTML.

    Uses a hierarchy of heuristics:
    1. Look for ``<article>`` tag content
    2. Fall back to ``<main>`` tag
    3. Fall back to the largest ``<div>`` by text length
    4. Last resort: strip all tags from full HTML

    This is intentionally simple; a production system would use a library like
    ``readability-lxml``, but we avoid extra native deps for now.
    """
    from html.parser import HTMLParser

    best = _extract_tag_content(html, "article")
    if not best or len(best) < 200:
        best = _extract_tag_content(html, "main")
    if not best or len(best) < 200:
        best = _extract_largest_div(html)
    if not best or len(best) < 100:
        best = _strip_tags(html)

    text = _clean_text(best)
    log.debug("Extracted %d chars of body text", len(text))
    return text


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
