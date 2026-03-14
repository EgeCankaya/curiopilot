"""Novelty scoring engine -- combines vector similarity and graph novelty (FR-23/24/25)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from curiopilot.config import AppConfig
from curiopilot.llm.ollama import OllamaClient
from curiopilot.models import ArticleSummary, ProgressCallback
from curiopilot.storage.knowledge_graph import KnowledgeGraph
from curiopilot.storage.vector_store import VectorStore

log = logging.getLogger(__name__)


@dataclass
class NoveltyResult:
    """Per-article novelty breakdown."""

    url: str
    vector_novelty: float
    graph_novelty: float
    novelty_score: float
    final_score: float
    relevance_score: int
    is_near_duplicate: bool = False


async def score_novelty(
    summaries: list[ArticleSummary],
    relevance_by_url: dict[str, int],
    config: AppConfig,
    client: OllamaClient,
    vector_store: VectorStore,
    knowledge_graph: KnowledgeGraph,
    *,
    progress_callback: ProgressCallback | None = None,
) -> list[NoveltyResult]:
    """Compute novelty + final ranking score for each article summary.

    Steps per article:
      1. Embed ``key_concepts + summary`` via Ollama.
      2. Query ChromaDB for vector similarity -> ``vector_novelty``.
      3. Query knowledge graph for structural novelty -> ``graph_novelty``.
      4. Combine into ``novelty_score``.
      5. Compute ``final_score`` from novelty + relevance.
      6. Store the embedding in ChromaDB for future runs.

    Returns results sorted by ``final_score`` descending.
    """
    scoring = config.scoring
    model = config.models.embedding_model
    results: list[NoveltyResult] = []

    for idx, summary in enumerate(summaries):
        try:
            embed_text = _build_embed_text(summary)
            embedding = await client.embed(model, embed_text, keep_alive="5m")

            # Signal 1: vector similarity
            vector_novelty = _compute_vector_novelty(
                embedding,
                vector_store,
                near_dup=scoring.near_duplicate_threshold,
                related=scoring.related_threshold,
            )

            # Signal 2: graph novelty
            graph_novelty = knowledge_graph.compute_graph_novelty(summary.key_concepts)

            novelty = (
                vector_novelty * scoring.vector_novelty_weight
                + graph_novelty * scoring.graph_novelty_weight
            )

            relevance = relevance_by_url.get(summary.url, 5)
            final = (
                novelty * scoring.novelty_weight
                + (relevance / 10.0) * scoring.relevance_weight
            )

            is_dup = vector_novelty <= 0.15

            results.append(NoveltyResult(
                url=summary.url,
                vector_novelty=round(vector_novelty, 4),
                graph_novelty=round(graph_novelty, 4),
                novelty_score=round(novelty, 4),
                final_score=round(final, 4),
                relevance_score=relevance,
                is_near_duplicate=is_dup,
            ))

            # Persist embedding for future runs
            vector_store.add(
                doc_id=summary.url,
                embedding=embedding,
                metadata={
                    "title": summary.title,
                    "source": summary.source_name,
                },
                document=embed_text[:500],
            )

        except Exception as exc:
            log.error(
                "Novelty scoring failed for %s (%s: %s), assigning defaults",
                summary.url, type(exc).__name__, exc,
                exc_info=True,
            )
            relevance = relevance_by_url.get(summary.url, 5)
            results.append(NoveltyResult(
                url=summary.url,
                vector_novelty=0.5,
                graph_novelty=0.5,
                novelty_score=0.5,
                final_score=round(
                    0.5 * scoring.novelty_weight + (relevance / 10.0) * scoring.relevance_weight, 4
                ),
                relevance_score=relevance,
            ))

        if progress_callback and callable(progress_callback):
            try:
                progress_callback(idx + 1, len(summaries))
            except Exception:
                pass

    results.sort(key=lambda r: r.final_score, reverse=True)
    return results


def _build_embed_text(summary: ArticleSummary) -> str:
    concepts = ", ".join(summary.key_concepts)
    return f"{concepts}. {summary.summary}"


def _compute_vector_novelty(
    embedding: list[float],
    store: VectorStore,
    *,
    near_dup: float,
    related: float,
) -> float:
    """Map max cosine similarity to a vector novelty score per FR-23."""
    neighbors = store.query_similar(embedding, k=5)
    if not neighbors:
        return 1.0

    s_max = max(n["similarity"] for n in neighbors)

    if s_max > near_dup:
        return 0.1
    if s_max >= related:
        t = (s_max - related) / (near_dup - related)
        return round(0.6 - t * 0.3, 4)  # 0.6 -> 0.3
    # Genuinely novel
    t = s_max / related if related > 0 else 0.0
    return round(1.0 - t * 0.2, 4)  # 1.0 -> 0.8
