"""Async SQLite store for structured article records."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import aiosqlite

from curiopilot.agents.novelty_engine import NoveltyResult
from curiopilot.models import ArticleSummary

log = logging.getLogger(__name__)

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_date TEXT NOT NULL,
    article_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    url TEXT NOT NULL,
    summary TEXT NOT NULL,
    novel_insights TEXT NOT NULL DEFAULT '',
    key_concepts TEXT NOT NULL DEFAULT '[]',
    related_topics TEXT NOT NULL DEFAULT '[]',
    relevance_score INTEGER NOT NULL DEFAULT 0,
    novelty_score REAL NOT NULL DEFAULT 0.0,
    graph_novelty REAL NOT NULL DEFAULT 0.0,
    vector_novelty REAL NOT NULL DEFAULT 0.0,
    novelty_explanation TEXT NOT NULL DEFAULT '',
    technical_depth INTEGER NOT NULL DEFAULT 1,
    is_deepening BOOLEAN NOT NULL DEFAULT 0,
    body_content TEXT NOT NULL DEFAULT '',
    body_content_type TEXT NOT NULL DEFAULT 'plaintext',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(briefing_date, article_number)
);

CREATE INDEX IF NOT EXISTS idx_articles_briefing_date
    ON articles(briefing_date);
CREATE INDEX IF NOT EXISTS idx_articles_url
    ON articles(url);
"""

_INSERT_SQL = """\
INSERT OR REPLACE INTO articles (
    briefing_date, article_number, title, source_name, url,
    summary, novel_insights, key_concepts, related_topics,
    relevance_score, novelty_score, graph_novelty, vector_novelty,
    novelty_explanation, technical_depth, is_deepening,
    body_content, body_content_type
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_COLUMNS_WITHOUT_BODY = (
    "id, briefing_date, article_number, title, source_name, url, "
    "summary, novel_insights, key_concepts, related_topics, "
    "relevance_score, novelty_score, graph_novelty, vector_novelty, "
    "novelty_explanation, technical_depth, is_deepening, "
    "body_content_type, created_at"
)

_COLUMNS_WITH_BODY = (
    "id, briefing_date, article_number, title, source_name, url, "
    "summary, novel_insights, key_concepts, related_topics, "
    "relevance_score, novelty_score, graph_novelty, vector_novelty, "
    "novelty_explanation, technical_depth, is_deepening, "
    "body_content, body_content_type, created_at"
)


def _row_to_dict(row: aiosqlite.Row, columns: str) -> dict:
    col_names = [c.strip() for c in columns.split(",")]
    d = dict(zip(col_names, row))
    for json_field in ("key_concepts", "related_topics"):
        if json_field in d and isinstance(d[json_field], str):
            try:
                d[json_field] = json.loads(d[json_field])
            except (json.JSONDecodeError, TypeError):
                d[json_field] = []
    d["is_deepening"] = bool(d.get("is_deepening", False))
    return d


class ArticleStore:
    """Thin async wrapper around an SQLite database for article records."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._db_path))
        await self.ensure_schema()
        log.info("Article store opened at %s", self._db_path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("ArticleStore is not open; call .open() first")
        return self._conn

    async def ensure_schema(self) -> None:
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def insert_articles(
        self,
        briefing_date: str,
        summaries: list[ArticleSummary],
        novelty_results: list[NoveltyResult],
        relevance_by_url: dict[str, int],
    ) -> int:
        """Insert article records for a briefing. Returns the number of rows inserted.

        Correlates summaries with novelty_results by URL. Articles are numbered
        sequentially starting at 1. Uses INSERT OR REPLACE for idempotency.
        """
        novelty_by_url: dict[str, NoveltyResult] = {
            nr.url: nr for nr in novelty_results
        }

        rows: list[tuple] = []
        for idx, summary in enumerate(summaries, 1):
            nr = novelty_by_url.get(summary.url)
            rel_score = relevance_by_url.get(summary.url, 0)

            is_deepening = bool(nr and nr.graph_novelty < 0.4)
            novelty_explanation = ""
            if nr and nr.graph_novelty >= 0.6:
                novelty_explanation = (
                    f"Introduces concepts not yet in your knowledge graph "
                    f"(graph novelty {int(nr.graph_novelty * 100)}%)"
                )

            rows.append((
                briefing_date,
                idx,
                summary.title,
                summary.source_name,
                summary.url,
                summary.summary,
                summary.novel_insights,
                json.dumps(summary.key_concepts),
                json.dumps(summary.related_topics),
                rel_score,
                nr.novelty_score if nr else 0.0,
                nr.graph_novelty if nr else 0.0,
                nr.vector_novelty if nr else 0.0,
                novelty_explanation,
                summary.technical_depth,
                is_deepening,
                summary.body_content,
                summary.body_content_type,
            ))

        await self._db.executemany(_INSERT_SQL, rows)
        await self._db.commit()
        return len(rows)

    async def get_articles_by_date(self, briefing_date: str) -> list[dict]:
        """Return all articles for a date, excluding body_content."""
        cursor = await self._db.execute(
            f"SELECT {_COLUMNS_WITHOUT_BODY} FROM articles "
            "WHERE briefing_date = ? ORDER BY article_number",
            (briefing_date,),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row, _COLUMNS_WITHOUT_BODY) for row in rows]

    async def get_article(
        self, briefing_date: str, article_number: int
    ) -> dict | None:
        """Return a single article with body_content included."""
        cursor = await self._db.execute(
            f"SELECT {_COLUMNS_WITH_BODY} FROM articles "
            "WHERE briefing_date = ? AND article_number = ?",
            (briefing_date, article_number),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_dict(row, _COLUMNS_WITH_BODY)

    async def list_briefing_dates(self) -> list[dict]:
        """Return briefing dates with article counts, newest first."""
        cursor = await self._db.execute(
            "SELECT briefing_date, COUNT(*) as article_count "
            "FROM articles GROUP BY briefing_date "
            "ORDER BY briefing_date DESC"
        )
        rows = await cursor.fetchall()
        return [
            {"briefing_date": row[0], "article_count": row[1]} for row in rows
        ]

    async def search_articles(self, query: str) -> list[dict]:
        """Search articles by title, summary, or body_content using LIKE."""
        pattern = f"%{query}%"
        cursor = await self._db.execute(
            f"SELECT {_COLUMNS_WITHOUT_BODY} FROM articles "
            "WHERE title LIKE ? OR summary LIKE ? OR body_content LIKE ? "
            "ORDER BY briefing_date DESC, article_number",
            (pattern, pattern, pattern),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row, _COLUMNS_WITHOUT_BODY) for row in rows]
