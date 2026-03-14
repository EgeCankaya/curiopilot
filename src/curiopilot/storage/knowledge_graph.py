"""NetworkX-backed knowledge graph with JSON persistence (FR-26 through FR-30)."""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

log = logging.getLogger(__name__)


@dataclass
class GraphUpdateStats:
    """Counts returned after a graph update so the briefing can report them."""

    nodes_added: int = 0
    edges_added: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    most_connected: str = ""
    most_connected_edges: int = 0
    new_concept_names: list[str] = field(default_factory=list)


@dataclass
class Exploration:
    """A suggested exploration item for the daily briefing."""

    topic: str
    reason: str


class KnowledgeGraph:
    """Persistent knowledge graph built on NetworkX with JSON serialization."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._graph: nx.Graph = nx.Graph()

    # ── Persistence ───────────────────────────────────────────────────────

    def load(self) -> None:
        if self._path.is_file():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._graph = nx.node_link_graph(data)
            log.info(
                "Knowledge graph loaded: %d nodes, %d edges",
                self._graph.number_of_nodes(),
                self._graph.number_of_edges(),
            )
        else:
            self._graph = nx.Graph()
            log.info("Starting fresh knowledge graph")

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._graph)
        self._path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        log.info("Knowledge graph saved to %s", self._path)

    # ── Queries ───────────────────────────────────────────────────────────

    @property
    def graph(self) -> nx.Graph:
        return self._graph

    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    def has_concept(self, concept: str) -> bool:
        return self._normalized(concept) in self._graph

    def concept_familiarity(self, concept: str) -> float:
        key = self._normalized(concept)
        if key not in self._graph:
            return 0.0
        return self._graph.nodes[key].get("familiarity", 0.0)

    def known_concepts(self, concepts: list[str]) -> int:
        return sum(1 for c in concepts if self.has_concept(c))

    # ── Graph update (FR-28) ──────────────────────────────────────────────

    def update_from_article(
        self,
        key_concepts: list[str],
        article_url: str,
        relationships: list[dict[str, str]] | None = None,
    ) -> GraphUpdateStats:
        """Incorporate concepts from one article.

        Returns stats about what was added/changed.
        """
        now = datetime.now(timezone.utc).isoformat()
        stats = GraphUpdateStats()
        normalized = [self._normalized(c) for c in key_concepts if c.strip()]
        if not normalized:
            return stats

        for concept in normalized:
            if concept not in self._graph:
                self._graph.add_node(
                    concept,
                    first_seen=now,
                    last_seen=now,
                    encounter_count=1,
                    familiarity=0.1,
                )
                stats.nodes_added += 1
                stats.new_concept_names.append(concept)
            else:
                attrs = self._graph.nodes[concept]
                attrs["last_seen"] = now
                count = attrs.get("encounter_count", 0) + 1
                attrs["encounter_count"] = count
                first_seen_str = attrs.get("first_seen", now)
                try:
                    first_seen = datetime.fromisoformat(first_seen_str)
                    if first_seen.tzinfo is None:
                        first_seen = first_seen.replace(tzinfo=timezone.utc)
                    days_since_first = max(1.0, (datetime.now(timezone.utc) - first_seen).total_seconds() / 86400.0)
                except (ValueError, TypeError):
                    days_since_first = 1.0
                recency_bonus = 1.0 / (1.0 + days_since_first / 7.0)
                attrs["familiarity"] = min(1.0, count * 0.1 + 0.05 * recency_bonus)

        rel_types: dict[tuple[str, str], str] = {}
        if relationships:
            for rel in relationships:
                src = self._normalized(rel.get("from", ""))
                dst = self._normalized(rel.get("to", ""))
                rtype = rel.get("type", "co_occurrence")
                if src and dst:
                    rel_types[(src, dst)] = rtype
                    rel_types[(dst, src)] = rtype

        for i, c1 in enumerate(normalized):
            for c2 in normalized[i + 1 :]:
                rtype = rel_types.get((c1, c2), "co_occurrence")
                if not self._graph.has_edge(c1, c2):
                    self._graph.add_edge(
                        c1,
                        c2,
                        relationship_type=rtype,
                        first_seen=now,
                        source_articles=[article_url],
                    )
                    stats.edges_added += 1
                else:
                    edge = self._graph.edges[c1, c2]
                    if rtype != "co_occurrence":
                        edge["relationship_type"] = rtype
                    sources = edge.get("source_articles", [])
                    if article_url not in sources:
                        sources.append(article_url)
                    edge["source_articles"] = sources

        stats.total_nodes = self._graph.number_of_nodes()
        stats.total_edges = self._graph.number_of_edges()

        if self._graph.number_of_nodes() > 0:
            top = max(self._graph.nodes, key=lambda n: self._graph.degree(n))
            stats.most_connected = top
            stats.most_connected_edges = self._graph.degree(top)

        return stats

    # ── Graph novelty (FR-23 signal 2) ────────────────────────────────────

    def compute_graph_novelty(self, key_concepts: list[str]) -> float:
        """Return graph-based structural novelty in [0, 1].

        ``graph_novelty = 1 - known_concepts / total_concepts``
        with a 1.3x bridge bonus when concepts connect separate clusters.
        """
        normalized = [self._normalized(c) for c in key_concepts if c.strip()]
        if not normalized:
            return 1.0

        known = sum(1 for c in normalized if c in self._graph)
        base = 1.0 - known / len(normalized)

        if self._graph.number_of_nodes() > 2 and self._bridges_clusters(normalized):
            base = min(1.0, base * 1.3)

        return round(base, 4)

    def _bridges_clusters(self, concepts: list[str]) -> bool:
        """Heuristic: do these concepts touch nodes in different connected components?"""
        if self._graph.number_of_nodes() < 4:
            return False

        components = {
            node: idx
            for idx, comp in enumerate(nx.connected_components(self._graph))
            for node in comp
        }

        existing = [c for c in concepts if c in self._graph]
        if len(existing) < 2:
            return False

        comp_ids = {components[c] for c in existing}
        return len(comp_ids) > 1

    # ── Knowledge gap detector (FR-29) ────────────────────────────────────

    def suggest_explorations(self, max_items: int = 5) -> list[Exploration]:
        """Identify concepts worth exploring based on graph structure."""
        explorations: list[Exploration] = []
        if self._graph.number_of_nodes() < 3:
            return explorations

        for node in self._graph.nodes:
            attrs = self._graph.nodes[node]
            familiarity = attrs.get("familiarity", 0.0)
            degree = self._graph.degree(node)

            # High-connectivity but low familiarity
            if degree >= 2 and familiarity < 0.3:
                neighbors = list(self._graph.neighbors(node))
                known = ", ".join(neighbors[:3])
                explorations.append(Exploration(
                    topic=node,
                    reason=f"Connected to {known}, but you have only "
                           f"{attrs.get('encounter_count', 0)} article(s) on it.",
                ))

        # Bridge concepts: low encounter, connect different clusters
        try:
            bridges = list(nx.bridges(self._graph))
        except nx.NetworkXError:
            bridges = []

        for u, v in bridges:
            for node in (u, v):
                attrs = self._graph.nodes[node]
                if attrs.get("encounter_count", 0) <= 2:
                    other = v if node == u else u
                    explorations.append(Exploration(
                        topic=node,
                        reason=f"Bridge concept connecting {other} to other clusters, "
                               f"with only {attrs.get('encounter_count', 0)} encounter(s).",
                    ))

        seen: set[str] = set()
        deduped: list[Exploration] = []
        for e in explorations:
            if e.topic not in seen:
                seen.add(e.topic)
                deduped.append(e)

        deduped.sort(key=lambda e: self._graph.degree(e.topic), reverse=True)
        return deduped[:max_items]

    # ── Memory decay / spaced repetition (Phase 5) ──────────────────────

    def apply_memory_decay(
        self,
        half_life_days: float = 14.0,
        prune_below: float = 0.02,
    ) -> int:
        """Apply exponential decay to familiarity scores based on time since last seen.

        ``familiarity *= 2^(-days_since_last_seen / half_life_days)``

        Nodes whose familiarity drops below *prune_below* and have only
        1 encounter are removed entirely to keep the graph lean.

        Returns the number of pruned nodes.
        """
        now = datetime.now(timezone.utc)
        to_prune: list[str] = []

        for node in list(self._graph.nodes):
            attrs = self._graph.nodes[node]
            last_seen_str = attrs.get("last_seen", "")
            if not last_seen_str:
                continue

            try:
                last_seen = datetime.fromisoformat(last_seen_str)
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            days_elapsed = (now - last_seen).total_seconds() / 86400.0
            if days_elapsed <= 0:
                continue

            decay_factor = 2.0 ** (-days_elapsed / half_life_days)
            old_fam = attrs.get("familiarity", 0.0)
            new_fam = old_fam * decay_factor

            # Encounters act as reinforcement -- more encounters = slower decay
            encounter_count = attrs.get("encounter_count", 1)
            reinforcement = min(1.0, encounter_count * 0.05)
            new_fam = max(new_fam, reinforcement)

            attrs["familiarity"] = round(new_fam, 4)

            if new_fam < prune_below and encounter_count <= 1:
                to_prune.append(node)

        for node in to_prune:
            self._graph.remove_node(node)

        if to_prune:
            log.info("Memory decay pruned %d low-familiarity nodes", len(to_prune))

        return len(to_prune)

    # ── User feedback application ────────────────────────────────────────

    def apply_feedback(
        self,
        concepts: list[str],
        *,
        read: bool = False,
        interest: int | None = None,
    ) -> None:
        """Apply user feedback to concept nodes in the knowledge graph.

        * ``read=True`` boosts familiarity (+0.15) and encounter_count (+1).
        * ``interest`` (1-5) sets/updates an ``interest_score`` running average
          and adjusts familiarity: high interest (4-5) adds a bonus, low
          interest (1-2) applies a small penalty.
        """
        now = datetime.now(timezone.utc).isoformat()

        for raw in concepts:
            key = self._normalized(raw)
            if key not in self._graph:
                continue
            attrs = self._graph.nodes[key]

            if read:
                attrs["familiarity"] = min(1.0, attrs.get("familiarity", 0.0) + 0.15)
                attrs["encounter_count"] = attrs.get("encounter_count", 0) + 1
                attrs["last_seen"] = now

            if interest is not None:
                prev_score = attrs.get("interest_score")
                prev_count = attrs.get("interest_count", 0)
                if prev_score is not None and prev_count > 0:
                    new_score = (prev_score * prev_count + interest) / (prev_count + 1)
                else:
                    new_score = float(interest)
                attrs["interest_score"] = round(new_score, 2)
                attrs["interest_count"] = prev_count + 1

                fam = attrs.get("familiarity", 0.0)
                if interest >= 4:
                    fam = min(1.0, fam + 0.05 * (interest - 3))
                elif interest <= 2:
                    fam = max(0.0, fam - 0.05 * (3 - interest))
                attrs["familiarity"] = round(fam, 4)

    # ── Most connected topic ──────────────────────────────────────────────

    def most_connected_topic(self) -> tuple[str, int]:
        if self._graph.number_of_nodes() == 0:
            return ("", 0)
        top = max(self._graph.nodes, key=lambda n: self._graph.degree(n))
        return (top, self._graph.degree(top))

    # ── Helpers ───────────────────────────────────────────────────────────

    _SYNONYM_MAP: dict[str, str] = {
        "large language model": "llm",
        "large language models": "llm",
        "retrieval augmented generation": "rag",
        "retrieval-augmented generation": "rag",
        "model context protocol": "mcp",
        "artificial intelligence": "ai",
        "machine learning": "ml",
        "natural language processing": "nlp",
        "reinforcement learning": "rl",
        "reinforcement learning from human feedback": "rlhf",
        "graph neural network": "gnn",
        "graph neural networks": "gnn",
        "convolutional neural network": "cnn",
        "convolutional neural networks": "cnn",
        "recurrent neural network": "rnn",
        "recurrent neural networks": "rnn",
        "generative adversarial network": "gan",
        "generative adversarial networks": "gan",
    }

    @classmethod
    def _normalized(cls, concept: str) -> str:
        text = concept.strip().lower()
        text = re.sub(r"[\-_/]", " ", text)
        if text in cls._SYNONYM_MAP:
            return cls._SYNONYM_MAP[text]
        text = re.sub(r"\s+", "", text)
        if text.endswith("s") and len(text) > 3:
            text = text[:-1]
        return text

    @classmethod
    def normalize_concepts(cls, concepts: list[str]) -> list[str]:
        """Deduplicate a list of concepts after normalization, preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for c in concepts:
            key = cls._normalized(c)
            if key not in seen:
                seen.add(key)
                result.append(key)
        return result
