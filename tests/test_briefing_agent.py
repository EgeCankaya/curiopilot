"""Tests for the briefing agent."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from curiopilot.agents.briefing_agent import (
    BriefingContext,
    _format_duration,
    generate_briefing,
    save_briefing,
)
from curiopilot.agents.novelty_engine import NoveltyResult
from curiopilot.models import ArticleSummary, RelevanceScore, ScoredArticle
from curiopilot.storage.knowledge_graph import GraphUpdateStats


def _make_summary(idx: int = 1, graph_novelty: float = 0.8) -> ArticleSummary:
    return ArticleSummary(
        title=f"Article {idx}",
        source_name="TestSource",
        url=f"http://test.com/{idx}",
        date_processed=datetime.now(timezone.utc),
        key_concepts=[f"concept_{idx}", "AI"],
        summary=f"Summary for article {idx}.",
        novel_insights=f"Insight {idx}.",
        technical_depth=3,
        related_topics=["ML"],
    )


def _make_scored(idx: int = 1, score: int = 8) -> ScoredArticle:
    return ScoredArticle(
        article=_make_summary(idx).__dict__ | {"snippet": None, "score": None},
        relevance=RelevanceScore(score=score, justification="Relevant"),
    )


def _make_novelty(idx: int = 1, graph_novelty: float = 0.8) -> NoveltyResult:
    return NoveltyResult(
        url=f"http://test.com/{idx}",
        vector_novelty=0.9,
        graph_novelty=graph_novelty,
        novelty_score=0.85,
        final_score=0.75,
        relevance_score=8,
    )


def _build_context(
    n_articles: int = 3, graph_novelty: float = 0.8
) -> BriefingContext:
    summaries = [_make_summary(i, graph_novelty) for i in range(1, n_articles + 1)]
    scored = []
    novelty_results = []
    for i in range(1, n_articles + 1):
        scored.append(ScoredArticle(
            article={
                "title": f"Article {i}",
                "url": f"http://test.com/{i}",
                "source_name": "TestSource",
            },
            relevance=RelevanceScore(score=8, justification="Relevant"),
        ))
        novelty_results.append(_make_novelty(i, graph_novelty))

    return BriefingContext(
        summaries=summaries,
        scored=scored,
        novelty_results=novelty_results,
        graph_stats=GraphUpdateStats(
            nodes_added=3, edges_added=5, total_nodes=20, total_edges=40,
            most_connected="AI", most_connected_edges=10,
            new_concept_names=["concept_1", "concept_2"],
        ),
        explorations=[],
        new_concepts=[("concept_1", "Article 1"), ("concept_2", "Article 2")],
        articles_scanned=100,
        articles_relevant=10,
        pipeline_duration_s=45.5,
        briefing_date=date(2026, 3, 9),
    )


# ── generate_briefing ───────────────────────────────────────────────────────


class TestGenerateBriefing:
    def test_produces_valid_markdown(self) -> None:
        ctx = _build_context()
        md = generate_briefing(ctx)
        assert "# CurioPilot Daily Briefing" in md
        assert "2026-03-09" in md
        assert "## Top Articles" in md or "## Deepening" in md

    def test_contains_expected_sections(self) -> None:
        ctx = _build_context()
        md = generate_briefing(ctx)
        assert "## New Concepts" in md
        assert "## Knowledge Graph Update" in md
        assert "## Your Feedback" in md

    def test_empty_summaries(self) -> None:
        ctx = BriefingContext(briefing_date=date(2026, 3, 9))
        md = generate_briefing(ctx)
        assert "No articles" in md

    def test_novel_vs_deepening_classification(self) -> None:
        novel_ctx = _build_context(n_articles=1, graph_novelty=0.8)
        md_novel = generate_briefing(novel_ctx)
        assert "## Top Articles" in md_novel

        deep_ctx = _build_context(n_articles=1, graph_novelty=0.2)
        md_deep = generate_briefing(deep_ctx)
        assert "## Deepening" in md_deep

    def test_feedback_section_article_count(self) -> None:
        ctx = _build_context(n_articles=5)
        md = generate_briefing(ctx)
        assert "- 5: read=" in md


# ── save_briefing ────────────────────────────────────────────────────────────


class TestSaveBriefing:
    def test_writes_to_correct_path(self, tmp_path: Path) -> None:
        md = "# Test briefing"
        path = save_briefing(md, tmp_path, briefing_date=date(2026, 3, 9))
        assert path == tmp_path / "2026-03-09.md"
        assert path.read_text(encoding="utf-8") == md

    def test_creates_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "subdir" / "briefings"
        path = save_briefing("test", out, briefing_date=date(2026, 1, 1))
        assert path.is_file()


# ── _format_duration ─────────────────────────────────────────────────────────


class TestFormatDuration:
    def test_seconds(self) -> None:
        assert _format_duration(45.3) == "45.3s"

    def test_minutes(self) -> None:
        result = _format_duration(125.7)
        assert result == "2m 6s"
