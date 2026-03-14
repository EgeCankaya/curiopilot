"""Tests for LangGraph pipeline routing and graph construction."""

from __future__ import annotations

import pytest

from langgraph.graph import END

from curiopilot.pipeline.graph import (
    _should_stop_after_dedup,
    _should_stop_after_filter,
    _should_stop_after_read,
    build_pipeline_graph,
)


class TestShouldStopAfterDedup:
    def test_dry_run_returns_end(self) -> None:
        state = {"dry_run": True, "new_articles": [1, 2]}
        assert _should_stop_after_dedup(state) == END

    def test_empty_articles_returns_end(self) -> None:
        state = {"dry_run": False, "new_articles": []}
        assert _should_stop_after_dedup(state) == END

    def test_has_articles_returns_filter(self) -> None:
        state = {"dry_run": False, "new_articles": [1]}
        assert _should_stop_after_dedup(state) == "filter"

    def test_missing_key_returns_end(self) -> None:
        state = {"dry_run": False}
        assert _should_stop_after_dedup(state) == END


class TestShouldStopAfterFilter:
    def test_no_passed_returns_end(self) -> None:
        state = {"passed": []}
        assert _should_stop_after_filter(state) == END

    def test_has_passed_returns_swap(self) -> None:
        state = {"passed": [1]}
        assert _should_stop_after_filter(state) == "swap_to_reader"

    def test_missing_key_returns_end(self) -> None:
        state = {}
        assert _should_stop_after_filter(state) == END


class TestShouldStopAfterRead:
    def test_no_summaries_returns_end(self) -> None:
        state = {"summaries": []}
        assert _should_stop_after_read(state) == END

    def test_has_summaries_returns_novelty(self) -> None:
        state = {"summaries": [1]}
        assert _should_stop_after_read(state) == "novelty"


class TestBuildPipelineGraph:
    def test_compiles_without_error(self) -> None:
        graph = build_pipeline_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_has_expected_nodes(self) -> None:
        graph = build_pipeline_graph()
        expected_nodes = {
            "ingest_feedback", "discover", "dedup", "filter",
            "swap_to_reader", "deep_read", "novelty",
            "graph_update", "briefing",
        }
        node_names = set(graph.nodes.keys())
        assert expected_nodes.issubset(node_names)
