"""Migration tool -- parses existing briefing Markdown files into the articles table."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from curiopilot.storage.article_store import ArticleStore, _INSERT_SQL

log = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^### (\d+)\.\s+(.+)$")
_META_RE = re.compile(
    r"\*\*Source\*\*:\s*(.+?)\s*\|\s*"
    r"\*\*Relevance\*\*:\s*(\d+)/10\s*\|\s*"
    r"\*\*Novelty\*\*:\s*(\d+)%"
)
_WHY_NEW_RE = re.compile(r"\*\*Why it is new to you\*\*:\s*(.+)")
_WHAT_NEW_RE = re.compile(r"\*\*What is new here\*\*:\s*(.+)")
_KEY_CONCEPTS_RE = re.compile(r"\*\*Key Concepts\*\*:\s*(.+)")
_RELATED_RE = re.compile(r"\*\*Related Topics\*\*:\s*(.+)")
_NOVEL_INSIGHTS_RE = re.compile(r"\*\*Novel insights\*\*:\s*(.+)")
_URL_RE = re.compile(r"\[Read original\]\((.+?)\)")
_SECTION_RE = re.compile(r"^## (.+)$")


@dataclass
class ParsedArticle:
    """A single article extracted from a briefing Markdown file."""

    article_number: int = 0
    title: str = ""
    source_name: str = ""
    url: str = ""
    relevance_score: int = 0
    novelty_pct: int = 0
    novelty_explanation: str = ""
    summary: str = ""
    novel_insights: str = ""
    key_concepts: list[str] = field(default_factory=list)
    related_topics: list[str] = field(default_factory=list)
    is_deepening: bool = False


def _parse_concepts(raw: str) -> list[str]:
    """Extract backtick-wrapped concepts from a Key Concepts line."""
    return [m.strip() for m in re.findall(r"`([^`]+)`", raw)]


def _parse_comma_list(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


def parse_briefing(text: str) -> list[ParsedArticle]:
    """Parse a briefing Markdown string into a list of ParsedArticle objects."""
    articles: list[ParsedArticle] = []
    current: ParsedArticle | None = None
    in_deepening = False
    summary_lines: list[str] = []

    def _flush_summary() -> None:
        nonlocal summary_lines
        if current is not None and summary_lines and not current.summary:
            current.summary = " ".join(summary_lines).strip()
        summary_lines = []

    for line in text.splitlines():
        section_m = _SECTION_RE.match(line)
        if section_m:
            section_name = section_m.group(1).strip()
            if section_name == "Deepening":
                _flush_summary()
                in_deepening = True
                continue
            elif section_name in (
                "Top Articles", "New Concepts", "Knowledge Graph Update",
                "Suggested Explorations", "Your Feedback",
            ):
                _flush_summary()
                in_deepening = False
                continue

        heading_m = _HEADING_RE.match(line)
        if heading_m:
            _flush_summary()
            if current is not None:
                articles.append(current)
            current = ParsedArticle(
                article_number=int(heading_m.group(1)),
                title=heading_m.group(2).strip(),
                is_deepening=in_deepening,
            )
            continue

        if current is None:
            continue

        meta_m = _META_RE.search(line)
        if meta_m:
            current.source_name = meta_m.group(1).strip()
            current.relevance_score = int(meta_m.group(2))
            current.novelty_pct = int(meta_m.group(3))
            continue

        why_m = _WHY_NEW_RE.search(line)
        if why_m:
            current.novelty_explanation = why_m.group(1).strip()
            continue

        what_new_m = _WHAT_NEW_RE.search(line)
        if what_new_m:
            current.novel_insights = what_new_m.group(1).strip()
            continue

        insights_m = _NOVEL_INSIGHTS_RE.search(line)
        if insights_m:
            current.novel_insights = insights_m.group(1).strip()
            continue

        concepts_m = _KEY_CONCEPTS_RE.search(line)
        if concepts_m:
            _flush_summary()
            current.key_concepts = _parse_concepts(concepts_m.group(1))
            continue

        related_m = _RELATED_RE.search(line)
        if related_m:
            current.related_topics = _parse_comma_list(related_m.group(1))
            continue

        url_m = _URL_RE.search(line)
        if url_m:
            current.url = url_m.group(1)
            continue

        if line.strip() == "---":
            _flush_summary()
            continue

        # Lines between the metadata block and key_concepts are the summary
        stripped = line.strip()
        if stripped and not current.summary and not current.key_concepts:
            summary_lines.append(stripped)

    _flush_summary()
    if current is not None:
        articles.append(current)

    return articles


async def migrate_briefings(
    briefings_dir: str | Path,
    article_store: ArticleStore,
) -> dict[str, int]:
    """Parse all briefing Markdown files and insert into the article store.

    Returns a dict mapping briefing_date -> article count for newly migrated dates.
    Dates that already exist in the store are skipped (idempotent).
    """
    briefings_path = Path(briefings_dir)
    if not briefings_path.is_dir():
        log.warning("Briefings directory does not exist: %s", briefings_path)
        return {}

    existing_dates = {
        d["briefing_date"] for d in await article_store.list_briefing_dates()
    }

    migrated: dict[str, int] = {}
    for md_file in sorted(briefings_path.glob("*.md")):
        briefing_date = md_file.stem
        if briefing_date in existing_dates:
            log.debug("Skipping already-migrated date: %s", briefing_date)
            continue

        text = md_file.read_text(encoding="utf-8")
        articles = parse_briefing(text)
        if not articles:
            log.info("No articles parsed from %s, skipping", md_file.name)
            continue

        rows: list[tuple] = []
        for art in articles:
            rows.append((
                briefing_date,
                art.article_number,
                art.title,
                art.source_name,
                art.url,
                art.summary,
                art.novel_insights,
                json.dumps(art.key_concepts),
                json.dumps(art.related_topics),
                art.relevance_score,
                art.novelty_pct / 100.0,  # novelty_score
                0.0,   # graph_novelty not recoverable from markdown
                0.0,   # vector_novelty not recoverable
                art.novelty_explanation,
                0,     # technical_depth not in markdown
                art.is_deepening,
                "",    # body_content not available for migrated articles
                "plaintext",
            ))

        await article_store._db.executemany(_INSERT_SQL, rows)
        await article_store._db.commit()
        migrated[briefing_date] = len(articles)
        log.info("Migrated %s: %d articles", briefing_date, len(articles))

    return migrated


_CSS_PATTERN = re.compile(r"\{--[a-zA-Z]")


async def refetch_articles(
    article_store: ArticleStore,
    *,
    progress_callback=None,
) -> dict[str, int]:
    """Re-fetch and re-extract body_content for corrupted or empty articles.

    Identifies articles where body_content is empty, too short, or contains
    CSS/JS artifacts, then re-fetches from the original URL using the stealth
    fetch pipeline and trafilatura extraction.

    Returns a dict: ``{"updated": N, "skipped": N, "failed": N}``.
    """
    from playwright.async_api import async_playwright

    from curiopilot.utils.fetch import create_stealth_context, fetch_article_html
    from curiopilot.utils.text import extract_body_text

    cursor = await article_store._db.execute(
        "SELECT id, url, body_content FROM articles ORDER BY briefing_date DESC, article_number"
    )
    rows = await cursor.fetchall()

    candidates = []
    for row_id, url, body in rows:
        if not body or len(body) < 100 or _CSS_PATTERN.search(body[:500]):
            candidates.append((row_id, url))

    if not candidates:
        log.info("No corrupted articles found")
        return {"updated": 0, "skipped": 0, "failed": 0}

    log.info("Found %d articles to re-fetch", len(candidates))
    stats = {"updated": 0, "skipped": 0, "failed": 0}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await create_stealth_context(browser)
        try:
            for i, (row_id, url) in enumerate(candidates):
                log.info("[%d/%d] Re-fetching: %s", i + 1, len(candidates), url[:80])

                html = await fetch_article_html(url, context=context)
                if html is None:
                    log.warning("  -> fetch failed, skipping")
                    stats["failed"] += 1
                    if progress_callback:
                        progress_callback(i + 1, len(candidates))
                    continue

                body = extract_body_text(html, url=url)
                if len(body) < 100:
                    log.warning("  -> extracted body too short (%d chars), skipping", len(body))
                    stats["skipped"] += 1
                    if progress_callback:
                        progress_callback(i + 1, len(candidates))
                    continue

                await article_store._db.execute(
                    "UPDATE articles SET body_content = ?, body_content_type = ? WHERE id = ?",
                    (body, "plaintext", row_id),
                )
                await article_store._db.commit()
                stats["updated"] += 1
                log.info("  -> updated (%d chars)", len(body))

                if progress_callback:
                    progress_callback(i + 1, len(candidates))

                await asyncio.sleep(1)
        finally:
            await context.close()
            await browser.close()

    return stats
