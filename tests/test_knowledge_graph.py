"""Comprehensive tests for KnowledgeGraph."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from curiopilot.storage.knowledge_graph import Exploration, GraphUpdateStats, KnowledgeGraph


@pytest.fixture
def kg(tmp_path: Path) -> KnowledgeGraph:
    g = KnowledgeGraph(tmp_path / "kg.json")
    g.load()
    return g


# ── update_from_article ──────────────────────────────────────────────────────


class TestUpdateFromArticle:
    def test_new_concepts_added(self, kg: KnowledgeGraph) -> None:
        stats = kg.update_from_article(["LangGraph", "agents"], "http://a.com")
        assert stats.nodes_added == 2
        assert stats.edges_added == 1
        assert kg.node_count() == 2
        assert kg.edge_count() == 1

    def test_new_concept_names_populated(self, kg: KnowledgeGraph) -> None:
        stats = kg.update_from_article(["Alpha", "Beta"], "http://a.com")
        normalized_names = stats.new_concept_names
        assert len(normalized_names) == 2

    def test_existing_concepts_incremented(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["LLM"], "http://a.com")
        kg.update_from_article(["LLM"], "http://b.com")
        attrs = kg.graph.nodes[kg._normalized("LLM")]
        assert attrs["encounter_count"] == 2
        assert attrs["familiarity"] > 0.1

    def test_edges_created_between_concepts(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["A", "B", "C"], "http://x.com")
        assert kg.edge_count() == 3  # A-B, A-C, B-C

    def test_edge_source_articles_accumulated(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["A", "B"], "http://1.com")
        kg.update_from_article(["A", "B"], "http://2.com")
        na = kg._normalized("A")
        nb = kg._normalized("B")
        edge = kg.graph.edges[na, nb]
        assert len(edge["source_articles"]) == 2

    def test_empty_concepts(self, kg: KnowledgeGraph) -> None:
        stats = kg.update_from_article([], "http://x.com")
        assert stats.nodes_added == 0
        assert kg.node_count() == 0

    def test_whitespace_only_concepts_ignored(self, kg: KnowledgeGraph) -> None:
        stats = kg.update_from_article(["  ", "  A  "], "http://x.com")
        assert stats.nodes_added == 1

    def test_relationships_set_edge_type(self, kg: KnowledgeGraph) -> None:
        rels = [{"from": "LangGraph", "to": "state machines", "type": "uses"}]
        kg.update_from_article(["LangGraph", "state machines"], "http://x.com", relationships=rels)
        nfrom = kg._normalized("LangGraph")
        nto = kg._normalized("state machines")
        assert kg.graph.edges[nfrom, nto]["relationship_type"] == "uses"


# ── compute_graph_novelty ────────────────────────────────────────────────────


class TestGraphNovelty:
    def test_all_new_concepts(self, kg: KnowledgeGraph) -> None:
        novelty = kg.compute_graph_novelty(["brand_new_1", "brand_new_2"])
        assert novelty == 1.0

    def test_all_known_concepts(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["AI", "ML"], "http://x.com")
        novelty = kg.compute_graph_novelty(["AI", "ML"])
        assert novelty == 0.0

    def test_mixed_concepts(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["known"], "http://x.com")
        novelty = kg.compute_graph_novelty(["known", "new_concept"])
        assert 0.0 < novelty < 1.0

    def test_empty_concepts(self, kg: KnowledgeGraph) -> None:
        assert kg.compute_graph_novelty([]) == 1.0


# ── _bridges_clusters ────────────────────────────────────────────────────────


class TestBridgesClusters:
    def test_multi_component_graph(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["A", "B"], "http://1.com")
        kg.update_from_article(["C", "D"], "http://2.com")
        assert kg._bridges_clusters([kg._normalized("A"), kg._normalized("C")])

    def test_single_component(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["A", "B", "C"], "http://1.com")
        assert not kg._bridges_clusters([kg._normalized("A"), kg._normalized("C")])

    def test_too_few_nodes(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["A", "B"], "http://1.com")
        assert not kg._bridges_clusters([kg._normalized("A")])


# ── suggest_explorations ─────────────────────────────────────────────────────


class TestSuggestExplorations:
    def test_empty_graph_returns_empty(self, kg: KnowledgeGraph) -> None:
        assert kg.suggest_explorations() == []

    def test_low_familiarity_high_degree_suggested(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["hub", "a", "b", "c"], "http://1.com")
        explorations = kg.suggest_explorations()
        topics = [e.topic for e in explorations]
        assert len(topics) >= 1

    def test_max_items_respected(self, kg: KnowledgeGraph) -> None:
        for i in range(10):
            kg.update_from_article([f"concept_{i}", "common"], f"http://{i}.com")
        explorations = kg.suggest_explorations(max_items=3)
        assert len(explorations) <= 3


# ── apply_memory_decay ───────────────────────────────────────────────────────


class TestMemoryDecay:
    def test_familiarity_decreases(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["topic"], "http://x.com")
        old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        kg.graph.nodes[kg._normalized("topic")]["last_seen"] = old_ts

        kg.apply_memory_decay(half_life_days=14.0)
        fam = kg.graph.nodes[kg._normalized("topic")]["familiarity"]
        assert fam < 0.1

    def test_stale_single_encounter_pruned(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["ephemeral"], "http://x.com")
        old_ts = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        n = kg._normalized("ephemeral")
        kg.graph.nodes[n]["last_seen"] = old_ts
        kg.graph.nodes[n]["familiarity"] = 0.001
        kg.graph.nodes[n]["encounter_count"] = 0

        pruned = kg.apply_memory_decay(half_life_days=14.0, prune_below=0.02)
        assert pruned == 1
        assert kg.node_count() == 0

    def test_high_encounter_not_pruned(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["solid"], "http://x.com")
        n = kg._normalized("solid")
        kg.graph.nodes[n]["encounter_count"] = 10
        old_ts = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        kg.graph.nodes[n]["last_seen"] = old_ts

        pruned = kg.apply_memory_decay(half_life_days=14.0)
        assert pruned == 0
        assert kg.node_count() == 1


# ── apply_feedback ───────────────────────────────────────────────────────────


class TestFeedback:
    def test_read_boosts_familiarity(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["topic"], "http://x.com")
        n = kg._normalized("topic")
        old_fam = kg.graph.nodes[n]["familiarity"]
        kg.apply_feedback(["topic"], read=True)
        assert kg.graph.nodes[n]["familiarity"] > old_fam

    def test_read_increments_encounter(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["topic"], "http://x.com")
        n = kg._normalized("topic")
        old_count = kg.graph.nodes[n]["encounter_count"]
        kg.apply_feedback(["topic"], read=True)
        assert kg.graph.nodes[n]["encounter_count"] == old_count + 1

    def test_high_interest_boosts(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["topic"], "http://x.com")
        n = kg._normalized("topic")
        old_fam = kg.graph.nodes[n]["familiarity"]
        kg.apply_feedback(["topic"], interest=5)
        assert kg.graph.nodes[n]["familiarity"] >= old_fam
        assert kg.graph.nodes[n]["interest_score"] == 5.0

    def test_low_interest_penalizes(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["topic"], "http://x.com")
        n = kg._normalized("topic")
        kg.graph.nodes[n]["familiarity"] = 0.5
        kg.apply_feedback(["topic"], interest=1)
        assert kg.graph.nodes[n]["familiarity"] < 0.5

    def test_interest_running_average(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["topic"], "http://x.com")
        kg.apply_feedback(["topic"], interest=5)
        kg.apply_feedback(["topic"], interest=3)
        n = kg._normalized("topic")
        assert kg.graph.nodes[n]["interest_score"] == 4.0
        assert kg.graph.nodes[n]["interest_count"] == 2

    def test_feedback_on_unknown_concept_ignored(self, kg: KnowledgeGraph) -> None:
        kg.apply_feedback(["nonexistent"], read=True, interest=5)
        assert kg.node_count() == 0


# ── most_connected_topic ─────────────────────────────────────────────────────


class TestMostConnected:
    def test_empty_graph(self, kg: KnowledgeGraph) -> None:
        topic, edges = kg.most_connected_topic()
        assert topic == ""
        assert edges == 0

    def test_populated_graph(self, kg: KnowledgeGraph) -> None:
        kg.update_from_article(["hub", "a", "b", "c"], "http://x.com")
        topic, edges = kg.most_connected_topic()
        assert edges >= 3


# ── Persistence ──────────────────────────────────────────────────────────────


class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "kg.json"
        kg1 = KnowledgeGraph(path)
        kg1.load()
        kg1.update_from_article(["alpha", "beta"], "http://test.com")
        kg1.save()

        kg2 = KnowledgeGraph(path)
        kg2.load()
        assert kg2.node_count() == kg1.node_count()
        assert kg2.edge_count() == kg1.edge_count()
        assert kg2.has_concept("alpha")

    def test_load_nonexistent_starts_fresh(self, tmp_path: Path) -> None:
        kg = KnowledgeGraph(tmp_path / "doesnotexist.json")
        kg.load()
        assert kg.node_count() == 0


# ── Normalization ────────────────────────────────────────────────────────────


class TestNormalization:
    def test_basic_lowercase(self) -> None:
        assert KnowledgeGraph._normalized("LangGraph") == "langgraph"

    def test_strip_whitespace(self) -> None:
        assert KnowledgeGraph._normalized("  AI Agents  ") == "aiagent"

    def test_synonym_map(self) -> None:
        assert KnowledgeGraph._normalized("Large Language Model") == "llm"
        assert KnowledgeGraph._normalized("retrieval augmented generation") == "rag"

    def test_separator_collapse(self) -> None:
        assert KnowledgeGraph._normalized("multi-agent") == KnowledgeGraph._normalized("multi agent")

    def test_pluralization(self) -> None:
        assert KnowledgeGraph._normalized("agents") == KnowledgeGraph._normalized("agent")

    def test_normalize_concepts_dedup(self) -> None:
        result = KnowledgeGraph.normalize_concepts(["agents", "Agents", "AGENTS", "LLM"])
        assert len(result) == 2
