"""Tests for the SQLite article store."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from curiopilot.agents.novelty_engine import NoveltyResult
from curiopilot.models import ArticleSummary
from curiopilot.storage.article_store import ArticleStore


def _make_summary(
    idx: int = 1,
    title: str = "Test Article",
    url: str = "https://example.com/1",
    body: str = "Full article body text here.",
) -> ArticleSummary:
    return ArticleSummary(
        title=title,
        source_name="HackerNews",
        url=url,
        date_processed=datetime(2026, 3, 14, tzinfo=timezone.utc),
        key_concepts=["concept-a", "concept-b"],
        summary=f"Summary for article {idx}.",
        novel_insights="Some novel insight.",
        technical_depth=3,
        related_topics=["topic-x", "topic-y"],
        body_content=body,
        body_content_type="plaintext",
    )


def _make_novelty(url: str = "https://example.com/1", **overrides) -> NoveltyResult:
    defaults = dict(
        url=url,
        vector_novelty=0.8,
        graph_novelty=0.7,
        novelty_score=0.75,
        final_score=0.65,
        relevance_score=7,
    )
    defaults.update(overrides)
    return NoveltyResult(**defaults)


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    s = ArticleStore(tmp_path / "test.db")
    await s.open()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_open_creates_db(tmp_path: Path) -> None:
    db_path = tmp_path / "sub" / "test.db"
    s = ArticleStore(db_path)
    await s.open()
    assert db_path.exists()
    await s.close()


@pytest.mark.asyncio
async def test_insert_single_article(store: ArticleStore) -> None:
    summary = _make_summary()
    nr = _make_novelty()
    count = await store.insert_articles(
        "2026-03-14", [summary], [nr], {"https://example.com/1": 7}
    )
    assert count == 1


@pytest.mark.asyncio
async def test_insert_bulk(store: ArticleStore) -> None:
    summaries = [
        _make_summary(idx=1, url="https://example.com/1"),
        _make_summary(idx=2, url="https://example.com/2", title="Second Article"),
    ]
    novelty = [
        _make_novelty("https://example.com/1"),
        _make_novelty("https://example.com/2", graph_novelty=0.3),
    ]
    rel = {"https://example.com/1": 8, "https://example.com/2": 6}
    count = await store.insert_articles("2026-03-14", summaries, novelty, rel)
    assert count == 2


@pytest.mark.asyncio
async def test_get_articles_by_date_excludes_body(store: ArticleStore) -> None:
    summary = _make_summary(body="This is the body text.")
    nr = _make_novelty()
    await store.insert_articles(
        "2026-03-14", [summary], [nr], {"https://example.com/1": 7}
    )
    articles = await store.get_articles_by_date("2026-03-14")
    assert len(articles) == 1
    assert "body_content" not in articles[0]
    assert articles[0]["title"] == "Test Article"
    assert articles[0]["body_content_type"] == "plaintext"


@pytest.mark.asyncio
async def test_get_article_includes_body(store: ArticleStore) -> None:
    body_text = "Full body content here."
    summary = _make_summary(body=body_text)
    nr = _make_novelty()
    await store.insert_articles(
        "2026-03-14", [summary], [nr], {"https://example.com/1": 7}
    )
    article = await store.get_article("2026-03-14", 1)
    assert article is not None
    assert article["body_content"] == body_text
    assert article["title"] == "Test Article"


@pytest.mark.asyncio
async def test_get_article_not_found(store: ArticleStore) -> None:
    result = await store.get_article("2099-01-01", 1)
    assert result is None


@pytest.mark.asyncio
async def test_json_roundtrip(store: ArticleStore) -> None:
    summary = _make_summary()
    nr = _make_novelty()
    await store.insert_articles(
        "2026-03-14", [summary], [nr], {"https://example.com/1": 7}
    )
    article = await store.get_article("2026-03-14", 1)
    assert article is not None
    assert article["key_concepts"] == ["concept-a", "concept-b"]
    assert article["related_topics"] == ["topic-x", "topic-y"]


@pytest.mark.asyncio
async def test_list_briefing_dates(store: ArticleStore) -> None:
    s1 = _make_summary(url="https://example.com/1")
    s2 = _make_summary(url="https://example.com/2")
    nr1 = _make_novelty("https://example.com/1")
    nr2 = _make_novelty("https://example.com/2")

    await store.insert_articles(
        "2026-03-14", [s1], [nr1], {"https://example.com/1": 7}
    )
    await store.insert_articles(
        "2026-03-13", [s2], [nr2], {"https://example.com/2": 6}
    )

    dates = await store.list_briefing_dates()
    assert len(dates) == 2
    assert dates[0]["briefing_date"] == "2026-03-14"
    assert dates[0]["article_count"] == 1
    assert dates[1]["briefing_date"] == "2026-03-13"


@pytest.mark.asyncio
async def test_search_articles_by_title(store: ArticleStore) -> None:
    summary = _make_summary(title="Advances in LLM Fine-Tuning")
    nr = _make_novelty()
    await store.insert_articles(
        "2026-03-14", [summary], [nr], {"https://example.com/1": 7}
    )
    results = await store.search_articles("LLM")
    assert len(results) == 1
    assert results[0]["title"] == "Advances in LLM Fine-Tuning"


@pytest.mark.asyncio
async def test_search_articles_by_summary(store: ArticleStore) -> None:
    summary = _make_summary()
    nr = _make_novelty()
    await store.insert_articles(
        "2026-03-14", [summary], [nr], {"https://example.com/1": 7}
    )
    results = await store.search_articles("Summary for article")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_articles_by_body(store: ArticleStore) -> None:
    summary = _make_summary(body="Unique body content for searching.")
    nr = _make_novelty()
    await store.insert_articles(
        "2026-03-14", [summary], [nr], {"https://example.com/1": 7}
    )
    results = await store.search_articles("Unique body content")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_no_results(store: ArticleStore) -> None:
    results = await store.search_articles("nonexistent query xyz")
    assert results == []


@pytest.mark.asyncio
async def test_upsert_idempotent(store: ArticleStore) -> None:
    summary = _make_summary()
    nr = _make_novelty()
    rel = {"https://example.com/1": 7}

    await store.insert_articles("2026-03-14", [summary], [nr], rel)
    await store.insert_articles("2026-03-14", [summary], [nr], rel)

    articles = await store.get_articles_by_date("2026-03-14")
    assert len(articles) == 1


@pytest.mark.asyncio
async def test_novelty_explanation_populated(store: ArticleStore) -> None:
    summary = _make_summary()
    nr = _make_novelty(graph_novelty=0.8)
    await store.insert_articles(
        "2026-03-14", [summary], [nr], {"https://example.com/1": 7}
    )
    article = await store.get_article("2026-03-14", 1)
    assert article is not None
    assert "graph novelty 80%" in article["novelty_explanation"]


@pytest.mark.asyncio
async def test_is_deepening_flag(store: ArticleStore) -> None:
    summary = _make_summary()
    nr = _make_novelty(graph_novelty=0.2)
    await store.insert_articles(
        "2026-03-14", [summary], [nr], {"https://example.com/1": 7}
    )
    article = await store.get_article("2026-03-14", 1)
    assert article is not None
    assert article["is_deepening"] is True


@pytest.mark.asyncio
async def test_empty_insert(store: ArticleStore) -> None:
    count = await store.insert_articles("2026-03-14", [], [], {})
    assert count == 0
    dates = await store.list_briefing_dates()
    assert dates == []
