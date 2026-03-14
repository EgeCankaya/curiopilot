"""Async SQLite URL store for deduplication and history tracking."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS visited_urls (
    url TEXT PRIMARY KEY,
    title TEXT,
    source_name TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    passed_relevance BOOLEAN,
    relevance_score INTEGER
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    articles_scanned INTEGER,
    articles_relevant INTEGER,
    articles_briefed INTEGER,
    new_concepts_added INTEGER
);

CREATE TABLE IF NOT EXISTS article_feedback (
    briefing_date TEXT,
    article_number INTEGER,
    title TEXT,
    read BOOLEAN,
    interest INTEGER,
    quality TEXT,
    processed_at TIMESTAMP,
    PRIMARY KEY (briefing_date, article_number)
);
"""


class URLStore:
    """Thin async wrapper around an SQLite database for URL history."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._db_path))
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        log.info("URL store opened at %s", self._db_path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("URLStore is not open; call .open() first")
        return self._conn

    async def is_visited(self, url: str) -> bool:
        cursor = await self._db.execute(
            "SELECT 1 FROM visited_urls WHERE url = ?", (url,)
        )
        return (await cursor.fetchone()) is not None

    async def filter_new_urls(self, urls: list[str]) -> set[str]:
        """Return the subset of *urls* that have NOT been visited."""
        if not urls:
            return set()
        placeholders = ",".join("?" for _ in urls)
        cursor = await self._db.execute(
            f"SELECT url FROM visited_urls WHERE url IN ({placeholders})", urls
        )
        known = {row[0] for row in await cursor.fetchall()}
        return set(urls) - known

    async def mark_visited(
        self,
        url: str,
        title: str | None = None,
        source_name: str | None = None,
        passed_relevance: bool | None = None,
        relevance_score: int | None = None,
    ) -> None:
        await self._db.execute(
            """\
            INSERT OR IGNORE INTO visited_urls
                (url, title, source_name, passed_relevance, relevance_score)
            VALUES (?, ?, ?, ?, ?)
            """,
            (url, title, source_name, passed_relevance, relevance_score),
        )
        await self._db.commit()

    async def mark_batch_visited(
        self,
        rows: list[tuple[str, str | None, str | None, bool | None, int | None]],
    ) -> None:
        """Insert many rows at once (url, title, source, passed, score)."""
        await self._db.executemany(
            """\
            INSERT OR IGNORE INTO visited_urls
                (url, title, source_name, passed_relevance, relevance_score)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        await self._db.commit()

    async def count(self) -> int:
        cursor = await self._db.execute("SELECT COUNT(*) FROM visited_urls")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def record_run(
        self,
        run_id: str,
        started_at: str,
        completed_at: str,
        articles_scanned: int,
        articles_relevant: int,
        articles_briefed: int,
        new_concepts_added: int,
    ) -> None:
        """Insert a pipeline run record."""
        await self._db.execute(
            """\
            INSERT OR REPLACE INTO pipeline_runs
                (run_id, started_at, completed_at, articles_scanned,
                 articles_relevant, articles_briefed, new_concepts_added)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, started_at, completed_at,
                articles_scanned, articles_relevant, articles_briefed,
                new_concepts_added,
            ),
        )
        await self._db.commit()

    async def recent_runs(self, limit: int = 10) -> list[dict]:
        """Return the most recent pipeline runs, newest first."""
        cursor = await self._db.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        cols = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    async def url_stats(self) -> dict:
        """Return aggregate statistics about visited URLs."""
        total = await self.count()
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM visited_urls WHERE passed_relevance = 1"
        )
        passed = (await cursor.fetchone())[0]
        cursor = await self._db.execute(
            "SELECT COUNT(DISTINCT source_name) FROM visited_urls"
        )
        sources = (await cursor.fetchone())[0]
        return {"total_urls": total, "passed_relevance": passed, "sources": sources}

    # ── Feedback tracking ─────────────────────────────────────────────────

    async def is_feedback_processed(self, briefing_date: str) -> bool:
        """Check whether feedback for a given briefing date was already ingested."""
        cursor = await self._db.execute(
            "SELECT 1 FROM article_feedback WHERE briefing_date = ? LIMIT 1",
            (briefing_date,),
        )
        return (await cursor.fetchone()) is not None

    async def record_feedback(
        self,
        briefing_date: str,
        article_number: int,
        title: str,
        read: bool,
        interest: int | None,
        quality: str | None,
        processed_at: str,
    ) -> None:
        """Store a single article's feedback row."""
        await self._db.execute(
            """\
            INSERT OR REPLACE INTO article_feedback
                (briefing_date, article_number, title, read,
                 interest, quality, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (briefing_date, article_number, title, read,
             interest, quality, processed_at),
        )
        await self._db.commit()
