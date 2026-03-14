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
async def test_duplicate_insert_ignored(store: URLStore) -> None:
    await store.mark_visited("https://x.com", title="X")
    await store.mark_visited("https://x.com", title="X2")
    assert await store.count() == 1
