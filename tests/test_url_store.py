"""Tests for the SQLite URL store."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from curiopilot.storage.url_store import URLStore


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    s = URLStore(tmp_path / "test.db")
    await s.open()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_open_creates_db(tmp_path: Path) -> None:
    db_path = tmp_path / "sub" / "test.db"
    s = URLStore(db_path)
    await s.open()
    assert db_path.exists()
    await s.close()


@pytest.mark.asyncio
async def test_is_visited_false_initially(store: URLStore) -> None:
    assert not await store.is_visited("https://example.com/1")


@pytest.mark.asyncio
async def test_mark_then_is_visited(store: URLStore) -> None:
    url = "https://example.com/article"
    await store.mark_visited(url, title="Test", source_name="HN")
    assert await store.is_visited(url)


@pytest.mark.asyncio
async def test_filter_new_urls(store: URLStore) -> None:
    await store.mark_visited("https://example.com/old")
    urls = ["https://example.com/old", "https://example.com/new"]
    new = await store.filter_new_urls(urls)
    assert new == {"https://example.com/new"}


@pytest.mark.asyncio
async def test_filter_new_urls_empty(store: URLStore) -> None:
    assert await store.filter_new_urls([]) == set()


@pytest.mark.asyncio
async def test_mark_batch_visited(store: URLStore) -> None:
    rows = [
        ("https://a.com", "A", "src", None, None),
        ("https://b.com", "B", "src", True, 8),
    ]
    await store.mark_batch_visited(rows)
    assert await store.is_visited("https://a.com")
    assert await store.is_visited("https://b.com")
    assert await store.count() == 2


@pytest.mark.asyncio
async def test_duplicate_insert_upserts(store: URLStore) -> None:
    await store.mark_visited("https://x.com", title="X")
    await store.mark_visited("https://x.com", title="X2")
    assert await store.count() == 1


# ── Dedup window tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_filter_new_urls_window_excludes_recent(store: URLStore) -> None:
    """A URL visited just now is excluded when a dedup window is active."""
    await store.mark_visited("https://example.com/recent", title="R", source_name="S")
    new = await store.filter_new_urls(
        ["https://example.com/recent"],
        dedup_window_days=7,
        briefed_dedup_window_days=60,
    )
    assert new == set()


@pytest.mark.asyncio
async def test_filter_new_urls_window_allows_old(store: URLStore) -> None:
    """A URL with first_seen older than the window is eligible for rediscovery."""
    url = "https://example.com/old"
    await store.mark_visited(url, title="O", source_name="S")
    # Backdate first_seen to 8 days ago
    await store._db.execute(
        "UPDATE visited_urls SET first_seen = datetime('now', '-8 days') WHERE url = ?",
        (url,),
    )
    await store._db.commit()
    new = await store.filter_new_urls(
        [url], dedup_window_days=7, briefed_dedup_window_days=60,
    )
    assert url in new


@pytest.mark.asyncio
async def test_briefed_urls_use_longer_window(store: URLStore) -> None:
    """Briefed URLs are excluded for briefed_dedup_window_days, not dedup_window_days."""
    url = "https://example.com/briefed"
    await store.mark_visited(url, title="B", source_name="S")
    await store.mark_batch_briefed([url])
    # Backdate to 8 days ago — still within the 60-day briefed window
    await store._db.execute(
        "UPDATE visited_urls SET first_seen = datetime('now', '-8 days') WHERE url = ?",
        (url,),
    )
    await store._db.commit()
    new = await store.filter_new_urls(
        [url], dedup_window_days=7, briefed_dedup_window_days=60,
    )
    assert new == set()  # Still excluded (within 60-day window)

    # Backdate to 61 days ago — past the briefed window
    await store._db.execute(
        "UPDATE visited_urls SET first_seen = datetime('now', '-61 days') WHERE url = ?",
        (url,),
    )
    await store._db.commit()
    new = await store.filter_new_urls(
        [url], dedup_window_days=7, briefed_dedup_window_days=60,
    )
    assert url in new  # Now eligible for rediscovery


@pytest.mark.asyncio
async def test_mark_batch_briefed(store: URLStore) -> None:
    """mark_batch_briefed correctly sets was_briefed=1."""
    await store.mark_visited("https://a.com", title="A", source_name="S")
    await store.mark_visited("https://b.com", title="B", source_name="S")
    await store.mark_batch_briefed(["https://a.com"])
    cursor = await store._db.execute(
        "SELECT was_briefed FROM visited_urls WHERE url = ?", ("https://a.com",)
    )
    row = await cursor.fetchone()
    assert row[0] == 1
    cursor = await store._db.execute(
        "SELECT was_briefed FROM visited_urls WHERE url = ?", ("https://b.com",)
    )
    row = await cursor.fetchone()
    assert row[0] == 0


@pytest.mark.asyncio
async def test_rediscovery_resets_first_seen(store: URLStore) -> None:
    """Re-marking a visited URL resets its first_seen timestamp."""
    url = "https://example.com/rediscovered"
    await store.mark_visited(url, title="Old", source_name="S")
    # Backdate
    await store._db.execute(
        "UPDATE visited_urls SET first_seen = datetime('now', '-30 days') WHERE url = ?",
        (url,),
    )
    await store._db.commit()
    cursor = await store._db.execute(
        "SELECT first_seen FROM visited_urls WHERE url = ?", (url,)
    )
    old_ts = (await cursor.fetchone())[0]
    # Re-mark (simulating rediscovery after dedup window expired)
    await store.mark_visited(url, title="New", source_name="S")
    cursor = await store._db.execute(
        "SELECT first_seen FROM visited_urls WHERE url = ?", (url,)
    )
    new_ts = (await cursor.fetchone())[0]
    assert new_ts > old_ts


@pytest.mark.asyncio
async def test_rediscovery_resets_was_briefed(store: URLStore) -> None:
    """Re-marking a briefed URL resets was_briefed to 0."""
    url = "https://example.com/rebriefed"
    await store.mark_visited(url, title="T", source_name="S")
    await store.mark_batch_briefed([url])
    # Confirm was_briefed=1
    cursor = await store._db.execute(
        "SELECT was_briefed FROM visited_urls WHERE url = ?", (url,)
    )
    assert (await cursor.fetchone())[0] == 1
    # Re-mark (simulating rediscovery)
    await store.mark_visited(url, title="T2", source_name="S")
    cursor = await store._db.execute(
        "SELECT was_briefed FROM visited_urls WHERE url = ?", (url,)
    )
    assert (await cursor.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_zero_window_is_permanent(store: URLStore) -> None:
    """With window=0, URLs are permanently excluded (backward compat)."""
    url = "https://example.com/permanent"
    await store.mark_visited(url, title="P", source_name="S")
    # Backdate to 1000 days ago
    await store._db.execute(
        "UPDATE visited_urls SET first_seen = datetime('now', '-1000 days') WHERE url = ?",
        (url,),
    )
    await store._db.commit()
    new = await store.filter_new_urls(
        [url], dedup_window_days=0, briefed_dedup_window_days=0,
    )
    assert new == set()  # Still excluded


@pytest.mark.asyncio
async def test_was_briefed_migration(store: URLStore) -> None:
    """The was_briefed column exists after open()."""
    cursor = await store._db.execute("PRAGMA table_info(visited_urls)")
    columns = {row[1] for row in await cursor.fetchall()}
    assert "was_briefed" in columns
