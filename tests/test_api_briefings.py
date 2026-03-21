"""Tests for the CurioPilot API endpoints (briefings, articles, feedback, stats, search)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from curiopilot.agents.novelty_engine import NoveltyResult
from curiopilot.models import ArticleSummary
from curiopilot.storage.article_store import ArticleStore
from curiopilot.storage.url_store import URLStore


def _make_summary(idx: int = 1, url: str = "https://example.com/1") -> ArticleSummary:
    return ArticleSummary(
        title=f"Test Article {idx}",
        source_name="HackerNews",
        url=url,
        date_processed=datetime(2026, 3, 14, tzinfo=timezone.utc),
        key_concepts=["concept-a", "concept-b"],
        summary=f"Summary for article {idx}.",
        novel_insights="Some novel insight.",
        technical_depth=3,
        related_topics=["topic-x", "topic-y"],
        body_content=f"Body content for article {idx}.",
        body_content_type="plaintext",
    )


def _make_novelty(url: str = "https://example.com/1") -> NoveltyResult:
    return NoveltyResult(
        url=url,
        vector_novelty=0.8,
        graph_novelty=0.7,
        novelty_score=0.75,
        final_score=0.65,
        relevance_score=7,
    )


@pytest.fixture
def populated_db(tmp_path: Path):
    """Create and populate a test database, return path."""
    import asyncio

    db_path = tmp_path / "curiopilot.db"

    async def _setup():
        article_store = ArticleStore(db_path)
        await article_store.open()

        url_store = URLStore(db_path)
        await url_store.open()

        summaries = [
            _make_summary(1, "https://example.com/1"),
            _make_summary(2, "https://example.com/2"),
        ]
        novelty = [
            _make_novelty("https://example.com/1"),
            _make_novelty("https://example.com/2"),
        ]
        rel = {"https://example.com/1": 8, "https://example.com/2": 6}
        await article_store.insert_articles("2026-03-14", summaries, novelty, rel)

        s3 = _make_summary(1, "https://example.com/3")
        n3 = _make_novelty("https://example.com/3")
        await article_store.insert_articles("2026-03-13", [s3], [n3], {"https://example.com/3": 7})

        await url_store.record_feedback(
            briefing_date="2026-03-13",
            article_number=1,
            title="Test Article 1",
            read=True,
            interest=4,
            quality="like",
            processed_at=datetime.now(timezone.utc).isoformat(),
        )

        await article_store.close()
        await url_store.close()

    asyncio.run(_setup())
    return db_path


@pytest.fixture
def client(populated_db: Path, tmp_path: Path):
    """Create a TestClient with the test database."""
    config_file = tmp_path / "config.yaml"
    db_parent = str(populated_db.parent).replace("\\", "/")
    briefings = str(tmp_path / "briefings").replace("\\", "/")
    graph = str(tmp_path / "graph.json").replace("\\", "/")
    config_file.write_text(
        f"interests:\n  primary:\n    - AI\n"
        f"sources:\n  - name: Test\n    scraper: hackernews_api\n"
        f"paths:\n"
        f"  database_dir: {db_parent}\n"
        f"  briefings_dir: {briefings}\n"
        f"  graph_path: {graph}\n",
        encoding="utf-8",
    )
    (tmp_path / "briefings").mkdir(exist_ok=True)

    from curiopilot.api.app import create_app
    app = create_app(config_path=str(config_file))
    with TestClient(app) as c:
        yield c


class TestBriefingsList:
    def test_returns_dates(self, client: TestClient) -> None:
        resp = client.get("/api/briefings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        dates = {d["briefing_date"] for d in data}
        assert "2026-03-14" in dates
        assert "2026-03-13" in dates

    def test_article_counts(self, client: TestClient) -> None:
        resp = client.get("/api/briefings")
        data = resp.json()
        by_date = {d["briefing_date"]: d for d in data}
        assert by_date["2026-03-14"]["article_count"] == 2
        assert by_date["2026-03-13"]["article_count"] == 1

    def test_has_feedback_flag(self, client: TestClient) -> None:
        resp = client.get("/api/briefings")
        data = resp.json()
        by_date = {d["briefing_date"]: d for d in data}
        assert by_date["2026-03-13"]["has_feedback"] is True
        assert by_date["2026-03-14"]["has_feedback"] is False


class TestBriefingDetail:
    def test_returns_articles(self, client: TestClient) -> None:
        resp = client.get("/api/briefings/2026-03-14")
        assert resp.status_code == 200
        data = resp.json()
        assert data["briefing_date"] == "2026-03-14"
        assert len(data["articles"]) == 2

    def test_excludes_body_content(self, client: TestClient) -> None:
        resp = client.get("/api/briefings/2026-03-14")
        data = resp.json()
        for article in data["articles"]:
            assert "body_content" not in article

    def test_404_for_missing_date(self, client: TestClient) -> None:
        resp = client.get("/api/briefings/2099-01-01")
        assert resp.status_code == 404


class TestArticleDetail:
    def test_includes_body_content(self, client: TestClient) -> None:
        resp = client.get("/api/briefings/2026-03-14/articles/1")
        assert resp.status_code == 200
        data = resp.json()
        assert "body_content" in data
        assert data["body_content"] == "Body content for article 1."
        assert data["title"] == "Test Article 1"

    def test_404_for_missing_article(self, client: TestClient) -> None:
        resp = client.get("/api/briefings/2026-03-14/articles/99")
        assert resp.status_code == 404


class TestFeedback:
    def test_get_feedback(self, client: TestClient) -> None:
        resp = client.get("/api/briefings/2026-03-13/feedback")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["article_number"] == 1
        assert data[0]["read"] is True
        assert data[0]["interest"] == 4

    def test_post_feedback(self, client: TestClient) -> None:
        resp = client.post(
            "/api/briefings/2026-03-14/articles/1/feedback",
            json={"read": True, "interest": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        resp2 = client.get("/api/briefings/2026-03-14/feedback")
        data = resp2.json()
        assert len(data) == 1
        assert data[0]["read"] is True
        assert data[0]["interest"] == 5

    def test_post_feedback_partial_merge(self, client: TestClient) -> None:
        client.post(
            "/api/briefings/2026-03-14/articles/1/feedback",
            json={"read": True, "interest": 3},
        )
        client.post(
            "/api/briefings/2026-03-14/articles/1/feedback",
            json={"quality": "like"},
        )
        resp = client.get("/api/briefings/2026-03-14/feedback")
        data = resp.json()
        fb = data[0]
        assert fb["read"] is True
        assert fb["interest"] == 3
        assert fb["quality"] == "like"

    def test_post_feedback_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/briefings/2026-03-14/articles/99/feedback",
            json={"read": True},
        )
        assert resp.status_code == 404


class TestSearch:
    def test_search_by_title(self, client: TestClient) -> None:
        resp = client.get("/api/search", params={"q": "Test Article"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_search_by_summary(self, client: TestClient) -> None:
        resp = client.get("/api/search", params={"q": "Summary for article 1"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_search_no_results(self, client: TestClient) -> None:
        resp = client.get("/api/search", params={"q": "zzzznonexistent"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestStats:
    def test_returns_stats(self, client: TestClient) -> None:
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "urls_visited" in data
        assert "graph_nodes" in data
        assert "graph_edges" in data
        assert "article_embeddings" in data
