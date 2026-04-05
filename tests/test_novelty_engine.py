"""Tests for novelty scoring engine."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from curiopilot.agents.novelty_engine import (
    NoveltyResult,
    _build_embed_text,
    _compute_vector_novelty,
    score_novelty,
)
from curiopilot.models import ArticleSummary


def _make_summary(**overrides) -> ArticleSummary:
    defaults = {
        "title": "Test Article",
        "source_name": "TestSource",
        "url": "http://test.com/1",
        "date_processed": datetime.now(timezone.utc),
        "key_concepts": ["AI", "agents"],
        "summary": "A test summary about AI agents.",
        "novel_insights": "Something new.",
        "technical_depth": 3,
        "related_topics": ["ML"],
    }
    defaults.update(overrides)
    return ArticleSummary(**defaults)


# ── _compute_vector_novelty ──────────────────────────────────────────────────


class TestComputeVectorNovelty:
    def test_no_neighbors_returns_one(self) -> None:
        store = MagicMock()
        store.query_similar.return_value = []
        result = _compute_vector_novelty([0.1] * 10, store, near_dup=0.92, related=0.75)
        assert result == 1.0

    def test_exact_duplicate_above_threshold(self) -> None:
        store = MagicMock()
        store.query_similar.return_value = [{"similarity": 0.95}]
        result = _compute_vector_novelty([0.1] * 10, store, near_dup=0.92, related=0.75)
        assert result == 0.1

    def test_related_range(self) -> None:
        store = MagicMock()
        store.query_similar.return_value = [{"similarity": 0.80}]
        result = _compute_vector_novelty([0.1] * 10, store, near_dup=0.92, related=0.75)
        assert 0.3 <= result <= 0.6

    def test_genuinely_novel(self) -> None:
        store = MagicMock()
        store.query_similar.return_value = [{"similarity": 0.3}]
        result = _compute_vector_novelty([0.1] * 10, store, near_dup=0.92, related=0.75)
        assert result >= 0.8


# ── _build_embed_text ────────────────────────────────────────────────────────


class TestBuildEmbedText:
    def test_format(self) -> None:
        summary = _make_summary(key_concepts=["AI", "ML"], summary="Test summary.")
        result = _build_embed_text(summary)
        assert "AI" in result
        assert "ML" in result
        assert "Test summary." in result


# ── score_novelty (integration with mocks) ───────────────────────────────────


class TestScoreNovelty:
    @pytest.mark.asyncio
    async def test_full_scoring_pipeline(self, tmp_path: Path) -> None:
        from curiopilot.config import AppConfig
        from curiopilot.storage.knowledge_graph import KnowledgeGraph

        config = AppConfig.model_validate({
            "interests": {"primary": ["AI"]},
            "sources": [{"name": "X", "scraper": "hackernews_api"}],
            "scoring": {
                "novelty_weight": 0.6,
                "relevance_weight": 0.4,
                "near_duplicate_threshold": 0.92,
                "related_threshold": 0.75,
                "vector_novelty_weight": 0.5,
                "graph_novelty_weight": 0.5,
            },
        })

        client = AsyncMock()
        client.embed = AsyncMock(return_value=[0.1] * 10)

        vector_store = MagicMock()
        vector_store.query_similar.return_value = []
        vector_store.query_batch.return_value = [[]]
        vector_store.add = MagicMock()
        vector_store.add_batch = MagicMock()

        kg = KnowledgeGraph(tmp_path / "kg.json")
        kg.load()

        summaries = [_make_summary()]
        relevance_by_url = {"http://test.com/1": 8}

        results = await score_novelty(
            summaries, relevance_by_url, config, client,
            vector_store, kg,
        )
        assert len(results) == 1
        assert results[0].vector_novelty == 1.0
        assert results[0].relevance_score == 8
        assert results[0].final_score > 0

    @pytest.mark.asyncio
    async def test_scoring_exception_gives_defaults(self, tmp_path: Path) -> None:
        from curiopilot.config import AppConfig
        from curiopilot.storage.knowledge_graph import KnowledgeGraph

        config = AppConfig.model_validate({
            "interests": {"primary": ["AI"]},
            "sources": [{"name": "X", "scraper": "hackernews_api"}],
        })

        client = AsyncMock()
        client.embed = AsyncMock(side_effect=RuntimeError("fail"))

        vector_store = MagicMock()
        kg = KnowledgeGraph(tmp_path / "kg.json")
        kg.load()

        summaries = [_make_summary()]
        results = await score_novelty(
            summaries, {}, config, client, vector_store, kg,
        )
        assert len(results) == 1
        assert results[0].vector_novelty == 0.5
