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

CREATE TABLE IF NOT EXISTS dead_letter_queue (
    url TEXT NOT NULL,
    title TEXT,
    source_name TEXT,
    phase TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT,
    failed_at TEXT NOT NULL,
    run_id TEXT,
    retry_count INTEGER DEFAULT 0,
    PRIMARY KEY (url, phase)
);

CREATE TABLE IF NOT EXISTS source_run_history (
    source_name TEXT PRIMARY KEY,
    last_run_at TEXT NOT NULL,
    articles_found INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_date TEXT NOT NULL,
    article_number INTEGER NOT NULL,
    collection_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(briefing_date, article_number, collection_id),
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE SET NULL
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

    async def clear_date_data(self, briefing_date: str) -> None:
        """Remove visited URLs discovered on the given date, plus that date's feedback."""
        await self._db.execute(
            "DELETE FROM visited_urls WHERE date(first_seen) = ?", (briefing_date,)
        )
        await self._db.execute(
            "DELETE FROM article_feedback WHERE briefing_date = ?", (briefing_date,)
        )
        await self._db.commit()

    async def is_feedback_processed(self, briefing_date: str) -> bool:
        """Check whether feedback for a given briefing date was already ingested."""
        cursor = await self._db.execute(
            "SELECT 1 FROM article_feedback WHERE briefing_date = ? LIMIT 1",
            (briefing_date,),
        )
        return (await cursor.fetchone()) is not None

    async def get_read_count(self, briefing_date: str) -> int:
        """Count articles marked as read for a briefing date."""
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM article_feedback WHERE briefing_date = ? AND read = 1",
            (briefing_date,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

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

    # ── Dead letter queue ─────────────────────────────────────────────────

    async def add_to_dlq(
        self,
        url: str,
        title: str | None,
        source_name: str | None,
        phase: str,
        error_type: str,
        error_message: str,
        run_id: str | None,
    ) -> None:
        """Insert or update a failed article in the dead letter queue."""
        await self._db.execute(
            """\
            INSERT INTO dead_letter_queue
                (url, title, source_name, phase, error_type, error_message, failed_at, run_id, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, 0)
            ON CONFLICT(url, phase) DO UPDATE SET
                error_type = excluded.error_type,
                error_message = excluded.error_message,
                failed_at = excluded.failed_at,
                run_id = excluded.run_id,
                retry_count = retry_count + 1
            """,
            (url, title, source_name, phase, error_type, error_message, run_id),
        )
        await self._db.commit()

    async def add_batch_to_dlq(
        self,
        items: list[tuple[str, str | None, str | None, str, str, str, str | None]],
    ) -> None:
        """Batch-insert failures into the DLQ (url, title, source, phase, err_type, err_msg, run_id)."""
        for url, title, source_name, phase, error_type, error_message, run_id in items:
            await self.add_to_dlq(url, title, source_name, phase, error_type, error_message, run_id)

    async def get_dlq_pending(self, max_retries: int = 3) -> list[dict]:
        """Return DLQ items that haven't exceeded max retries."""
        cursor = await self._db.execute(
            "SELECT * FROM dead_letter_queue WHERE retry_count < ? ORDER BY failed_at",
            (max_retries,),
        )
        cols = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    async def remove_from_dlq(self, url: str) -> None:
        """Remove all DLQ entries for a URL (all phases)."""
        await self._db.execute("DELETE FROM dead_letter_queue WHERE url = ?", (url,))
        await self._db.commit()

    async def clear_dlq(self) -> None:
        """Remove all entries from the dead letter queue."""
        await self._db.execute("DELETE FROM dead_letter_queue")
        await self._db.commit()

    async def dlq_stats(self) -> dict:
        """Return aggregate statistics about the dead letter queue."""
        cursor = await self._db.execute("SELECT COUNT(*) FROM dead_letter_queue")
        total = (await cursor.fetchone())[0]
        cursor = await self._db.execute(
            "SELECT phase, COUNT(*) FROM dead_letter_queue GROUP BY phase"
        )
        by_phase = {row[0]: row[1] for row in await cursor.fetchall()}
        cursor = await self._db.execute(
            "SELECT error_type, COUNT(*) FROM dead_letter_queue GROUP BY error_type"
        )
        by_error = {row[0]: row[1] for row in await cursor.fetchall()}
        return {"total": total, "by_phase": by_phase, "by_error_type": by_error}

    # ── Source run history (incremental runs) ─────────────────────────────

    async def record_source_run(self, source_name: str, articles_found: int) -> None:
        """Record that a source was scraped, with a timestamp."""
        await self._db.execute(
            """\
            INSERT INTO source_run_history (source_name, last_run_at, articles_found)
            VALUES (?, datetime('now'), ?)
            ON CONFLICT(source_name) DO UPDATE SET
                last_run_at = excluded.last_run_at,
                articles_found = excluded.articles_found
            """,
            (source_name, articles_found),
        )
        await self._db.commit()

    async def last_successful_run(self) -> dict | None:
        """Return the most recent completed pipeline run, or None."""
        cursor = await self._db.execute(
            "SELECT * FROM pipeline_runs WHERE completed_at IS NOT NULL "
            "ORDER BY completed_at DESC LIMIT 1"
        )
        cols = [d[0] for d in cursor.description]
        row = await cursor.fetchone()
        return dict(zip(cols, row)) if row else None

    async def sources_scraped_since(self, since: str) -> set[str]:
        """Return source names that were scraped after the given timestamp."""
        cursor = await self._db.execute(
            "SELECT source_name FROM source_run_history WHERE last_run_at > ?",
            (since,),
        )
        return {row[0] for row in await cursor.fetchall()}

    # ── Bookmarks & Collections ───────────────────────────────────────────

    async def add_bookmark(
        self, briefing_date: str, article_number: int, collection_id: int | None = None
    ) -> int:
        """Bookmark an article. Returns the bookmark id."""
        cursor = await self._db.execute(
            """\
            INSERT OR IGNORE INTO bookmarks (briefing_date, article_number, collection_id)
            VALUES (?, ?, ?)
            """,
            (briefing_date, article_number, collection_id),
        )
        await self._db.commit()
        return cursor.lastrowid or 0

    async def remove_bookmark(self, briefing_date: str, article_number: int) -> None:
        """Remove all bookmarks for an article."""
        await self._db.execute(
            "DELETE FROM bookmarks WHERE briefing_date = ? AND article_number = ?",
            (briefing_date, article_number),
        )
        await self._db.commit()

    async def list_bookmarks(self, collection_id: int | None = None) -> list[dict]:
        """List bookmarks, optionally filtered by collection."""
        if collection_id is not None:
            cursor = await self._db.execute(
                "SELECT * FROM bookmarks WHERE collection_id = ? ORDER BY created_at DESC",
                (collection_id,),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM bookmarks ORDER BY created_at DESC"
            )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in await cursor.fetchall()]

    async def is_bookmarked(self, briefing_date: str, article_number: int) -> bool:
        """Check if an article is bookmarked."""
        cursor = await self._db.execute(
            "SELECT 1 FROM bookmarks WHERE briefing_date = ? AND article_number = ? LIMIT 1",
            (briefing_date, article_number),
        )
        return (await cursor.fetchone()) is not None

    async def list_collections(self) -> list[dict]:
        """List all bookmark collections."""
        cursor = await self._db.execute(
            "SELECT * FROM collections ORDER BY name"
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in await cursor.fetchall()]

    async def create_collection(self, name: str) -> int:
        """Create a new collection. Returns its id."""
        cursor = await self._db.execute(
            "INSERT INTO collections (name) VALUES (?)", (name,)
        )
        await self._db.commit()
        return cursor.lastrowid or 0

    async def delete_collection(self, collection_id: int) -> None:
        """Delete a collection. Bookmarks are kept with null collection_id."""
        await self._db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        await self._db.commit()
