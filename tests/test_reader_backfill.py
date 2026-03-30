"""Tests for reserve article pool and reader-stage backfill logic."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from curiopilot.agents.reader_agent import ReaderFailure
from curiopilot.config import AppConfig, InterestsConfig, OllamaConfig, ScoringConfig, SourceConfig
from curiopilot.models import (
    ArticleEntry,
    ArticleSummary,
    RelevanceScore,
    ScoredArticle,
)
from curiopilot.pipeline.graph import deep_read_node, filter_node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scored(idx: int, score: int = 8) -> ScoredArticle:
    return ScoredArticle(
        article=ArticleEntry(
            title=f"Article {idx}",
            url=f"http://test.com/{idx}",
            source_name="TestSource",
        ),
        relevance=RelevanceScore(score=score, justification="test"),
    )


def _make_summary(idx: int) -> ArticleSummary:
    return ArticleSummary(
        title=f"Article {idx}",
        source_name="TestSource",
        url=f"http://test.com/{idx}",
        date_processed=datetime.now(timezone.utc),
        summary=f"Summary of article {idx}.",
        key_concepts=["test"],
        novel_insights="Some novel insight.",
        technical_depth=3,
        related_topics=["topic"],
    )


def _make_config(
    min_items: int = 5,
    max_items: int = 10,
    threshold: int = 6,
) -> AppConfig:
    """Build a minimal AppConfig with scoring overrides."""
    return AppConfig(
        interests=InterestsConfig(primary=["test"]),
        sources=[SourceConfig(name="test", scraper="hackernews_api")],
        scoring=ScoringConfig(
            min_briefing_items=min_items,
            max_briefing_items=max_items,
            relevance_threshold=threshold,
        ),
    )


# ---------------------------------------------------------------------------
# filter_node reserve tests
# ---------------------------------------------------------------------------

class TestFilterNodeReserves:
    @pytest.mark.asyncio
    async def test_populates_reserves_from_overflow(self) -> None:
        """When more articles pass than max_items, overflow becomes reserves."""
        config = _make_config(min_items=5, max_items=10)
        articles = [
            ArticleEntry(title=f"A{i}", url=f"http://t.com/{i}", source_name="S")
            for i in range(12)
        ]
        scored = [_make_scored(i, score=8) for i in range(12)]

        # Build minimal state
        store = AsyncMock()
        store.mark_batch_visited = AsyncMock()
        store.add_to_dlq = AsyncMock()

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "new_articles": articles,
            "no_filter": True,  # skip LLM scoring
            "dlq_failures": [],
        }

        result = await filter_node(state)
        assert len(result["passed"]) == 10
        assert len(result["reserve_articles"]) == 2

    @pytest.mark.asyncio
    async def test_no_reserves_when_few_articles(self) -> None:
        """When fewer articles than max_items, reserves are empty."""
        config = _make_config(min_items=5, max_items=10)
        articles = [
            ArticleEntry(title=f"A{i}", url=f"http://t.com/{i}", source_name="S")
            for i in range(4)
        ]

        store = AsyncMock()
        store.mark_batch_visited = AsyncMock()
        store.add_to_dlq = AsyncMock()

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "new_articles": articles,
            "no_filter": True,
            "dlq_failures": [],
        }

        result = await filter_node(state)
        assert len(result["passed"]) == 4
        assert len(result["reserve_articles"]) == 0


# ---------------------------------------------------------------------------
# deep_read_node backfill tests
# ---------------------------------------------------------------------------

class TestDeepReadBackfill:
    @pytest.mark.asyncio
    async def test_backfills_from_reserves(self) -> None:
        """When main read produces too few summaries, reserves are used."""
        config = _make_config(min_items=5, max_items=10)
        passed = [_make_scored(i) for i in range(5)]
        reserves = [_make_scored(i) for i in range(10, 15)]

        main_summaries = [_make_summary(0), _make_summary(1)]  # only 2 of 5
        reserve_summaries = [_make_summary(10), _make_summary(11), _make_summary(12)]

        store = AsyncMock()
        store.add_to_dlq = AsyncMock()

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "passed": passed,
            "reserve_articles": reserves,
            "dlq_failures": [],
            "run_id": "test-run",
        }

        call_count = 0

        async def mock_read(articles, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return main_summaries
            return reserve_summaries

        with patch(
            "curiopilot.agents.reader_agent.read_and_summarize",
            side_effect=mock_read,
        ):
            result = await deep_read_node(state)

        assert len(result["summaries"]) == 5  # 2 main + 3 reserve

    @pytest.mark.asyncio
    async def test_no_backfill_when_enough(self) -> None:
        """When main read produces enough summaries, reserves are not used."""
        config = _make_config(min_items=5, max_items=10)
        passed = [_make_scored(i) for i in range(5)]
        reserves = [_make_scored(i) for i in range(10, 15)]

        main_summaries = [_make_summary(i) for i in range(5)]

        store = AsyncMock()
        store.add_to_dlq = AsyncMock()

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "passed": passed,
            "reserve_articles": reserves,
            "dlq_failures": [],
            "run_id": "test-run",
        }

        call_count = 0

        async def mock_read(articles, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return main_summaries

        with patch(
            "curiopilot.agents.reader_agent.read_and_summarize",
            side_effect=mock_read,
        ):
            result = await deep_read_node(state)

        assert len(result["summaries"]) == 5
        assert call_count == 1  # reader called only once

    @pytest.mark.asyncio
    async def test_backfill_updates_passed(self) -> None:
        """Reserve articles that succeed are added to passed for novelty node."""
        config = _make_config(min_items=5, max_items=10)
        passed = [_make_scored(i) for i in range(5)]
        reserves = [_make_scored(i) for i in range(10, 15)]

        main_summaries = [_make_summary(0)]  # only 1
        reserve_summaries = [_make_summary(10), _make_summary(11)]

        store = AsyncMock()
        store.add_to_dlq = AsyncMock()

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "passed": passed,
            "reserve_articles": reserves,
            "dlq_failures": [],
            "run_id": "test-run",
        }

        call_count = 0

        async def mock_read(articles, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return main_summaries
            return reserve_summaries

        with patch(
            "curiopilot.agents.reader_agent.read_and_summarize",
            side_effect=mock_read,
        ):
            result = await deep_read_node(state)

        # passed should include original 5 + 2 used reserves
        result_urls = {sa.article.url for sa in result["passed"]}
        assert "http://test.com/10" in result_urls
        assert "http://test.com/11" in result_urls

    @pytest.mark.asyncio
    async def test_reserve_failures_go_to_dlq(self) -> None:
        """Reserve articles that fail reading are added to DLQ."""
        config = _make_config(min_items=5, max_items=10)
        passed = [_make_scored(i) for i in range(5)]
        reserves = [_make_scored(i) for i in range(10, 15)]

        main_summaries = [_make_summary(0)]  # only 1

        store = AsyncMock()
        store.add_to_dlq = AsyncMock()

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "passed": passed,
            "reserve_articles": reserves,
            "dlq_failures": [],
            "run_id": "test-run",
        }

        call_count = 0

        async def mock_read(articles, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            failures_list = kwargs.get("failures")
            if call_count == 1:
                return main_summaries
            # Simulate failures during reserve reading
            if failures_list is not None:
                failures_list.append(ReaderFailure(
                    url="http://test.com/10",
                    title="Article 10",
                    source_name="TestSource",
                    phase="fetch",
                    error_type="timeout",
                    error_message="Connection timed out",
                ))
            return [_make_summary(11)]

        with patch(
            "curiopilot.agents.reader_agent.read_and_summarize",
            side_effect=mock_read,
        ):
            result = await deep_read_node(state)

        # DLQ should have the failed reserve article
        dlq_urls = [d["url"] for d in result["dlq_failures"]]
        assert "http://test.com/10" in dlq_urls
        store.add_to_dlq.assert_called()

    @pytest.mark.asyncio
    async def test_graceful_with_exhausted_reserves(self) -> None:
        """If reserves also fail, briefing proceeds with fewer than min articles."""
        config = _make_config(min_items=5, max_items=10)
        passed = [_make_scored(i) for i in range(5)]
        reserves = [_make_scored(10)]

        main_summaries = [_make_summary(0)]  # only 1
        reserve_summaries = [_make_summary(10)]  # only 1 from reserve

        store = AsyncMock()
        store.add_to_dlq = AsyncMock()

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "passed": passed,
            "reserve_articles": reserves,
            "dlq_failures": [],
            "run_id": "test-run",
        }

        call_count = 0

        async def mock_read(articles, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return main_summaries
            return reserve_summaries

        with patch(
            "curiopilot.agents.reader_agent.read_and_summarize",
            side_effect=mock_read,
        ):
            result = await deep_read_node(state)

        # Only 2 total -- graceful degradation, no crash
        assert len(result["summaries"]) == 2


# ---------------------------------------------------------------------------
# Adaptive threshold tests
# ---------------------------------------------------------------------------

class TestAdaptiveThreshold:
    @pytest.mark.asyncio
    async def test_lowers_threshold_on_very_thin_pool(self) -> None:
        """When new_articles < min*2, threshold drops by 2."""
        config = _make_config(min_items=5, max_items=10, threshold=6)
        # 8 articles < min_items * 2 = 10
        articles = [
            ArticleEntry(title=f"A{i}", url=f"http://t.com/{i}", source_name="S")
            for i in range(8)
        ]
        # All articles score 4 — below normal threshold (6), but above adaptive (4)
        scored = [_make_scored(i, score=4) for i in range(8)]

        store = AsyncMock()
        store.mark_batch_visited = AsyncMock()
        store.add_to_dlq = AsyncMock()

        async def mock_score(articles_arg, *args, **kwargs):
            return scored

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "new_articles": articles,
            "no_filter": False,
            "dlq_failures": [],
        }

        with patch(
            "curiopilot.pipeline.graph.score_articles",
            side_effect=mock_score,
        ):
            result = await filter_node(state)

        # With normal threshold=6, all would be below. With adaptive=4, all pass.
        assert len(result["passed"]) == 8

    @pytest.mark.asyncio
    async def test_lowers_threshold_on_thin_pool(self) -> None:
        """When new_articles < min*3 but >= min*2, threshold drops by 1."""
        config = _make_config(min_items=5, max_items=10, threshold=6)
        # 12 articles: >= min*2=10, < min*3=15
        articles = [
            ArticleEntry(title=f"A{i}", url=f"http://t.com/{i}", source_name="S")
            for i in range(12)
        ]
        # All score 5 — below normal threshold (6), at adaptive (5)
        scored = [_make_scored(i, score=5) for i in range(12)]

        store = AsyncMock()
        store.mark_batch_visited = AsyncMock()
        store.add_to_dlq = AsyncMock()

        async def mock_score(articles_arg, *args, **kwargs):
            return scored

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "new_articles": articles,
            "no_filter": False,
            "dlq_failures": [],
        }

        with patch(
            "curiopilot.pipeline.graph.score_articles",
            side_effect=mock_score,
        ):
            result = await filter_node(state)

        # With adaptive threshold=5, all 12 pass (but capped at max=10)
        assert len(result["passed"]) == 10

    @pytest.mark.asyncio
    async def test_threshold_unchanged_on_large_pool(self) -> None:
        """When new_articles >= min*3, threshold stays at configured value."""
        config = _make_config(min_items=5, max_items=10, threshold=6)
        # 20 articles >= min*3=15
        articles = [
            ArticleEntry(title=f"A{i}", url=f"http://t.com/{i}", source_name="S")
            for i in range(20)
        ]
        # All score 5 — below normal threshold (6)
        scored = [_make_scored(i, score=5) for i in range(20)]

        store = AsyncMock()
        store.mark_batch_visited = AsyncMock()
        store.add_to_dlq = AsyncMock()

        async def mock_score(articles_arg, *args, **kwargs):
            return scored

        state = {
            "config": config,
            "client": AsyncMock(),
            "store": store,
            "new_articles": articles,
            "no_filter": False,
            "dlq_failures": [],
        }

        with patch(
            "curiopilot.pipeline.graph.score_articles",
            side_effect=mock_score,
        ):
            result = await filter_node(state)

        # Normal threshold=6, all score 5 → none pass.
        # But backfill logic pulls best below-threshold to reach min=5.
        assert len(result["passed"]) == 5
