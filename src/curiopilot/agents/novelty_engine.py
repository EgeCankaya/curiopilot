"""Novelty scoring engine -- combines vector similarity and graph novelty (FR-23/24/25)."""

from __future__ import annotations

import asyncio
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


@dataclass
class NoveltyFailure:
    """Record of a single article that failed during novelty scoring."""

    url: str
    title: str
    source_name: str
    error_type: str
    error_message: str


async def _score_one_article(
    summary: ArticleSummary,
    relevance: int,
    config: AppConfig,
    client: OllamaClient,
    vector_store: VectorStore,
    knowledge_graph: KnowledgeGraph,
    llm_sem: asyncio.Semaphore,
    vector_lock: asyncio.Lock,
    breaker: object | None,
) -> NoveltyResult | NoveltyFailure:
    """Score novelty for a single article with bounded concurrency."""
    from curiopilot.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

    scoring = config.scoring
    model = config.models.embedding_model

    # Check circuit breaker
    if isinstance(breaker, CircuitBreaker):
        try:
            breaker.check()
        except CircuitBreakerOpen:
            return NoveltyFailure(
                url=summary.url, title=summary.title,
                source_name=summary.source_name,
                error_type="circuit_breaker",
                error_message="Circuit breaker open — Ollama unresponsive",
            )

    try:
        embed_text = _build_embed_text(summary)

        # Embed with LLM semaphore and timeout
        async with llm_sem:
            embedding = await asyncio.wait_for(
                client.embed(model, embed_text, keep_alive="5m"),
                timeout=config.ollama.embed_timeout_seconds,
            )

        if isinstance(breaker, CircuitBreaker):
            breaker.record_success()

        # Vector store access serialized
        async with vector_lock:
            vector_novelty = _compute_vector_novelty(
                embedding, vector_store,
                near_dup=scoring.near_duplicate_threshold,
                related=scoring.related_threshold,
            )

        # Graph novelty (CPU only, safe to call concurrently with lock just in case)
        graph_novelty = knowledge_graph.compute_graph_novelty(summary.key_concepts)

        novelty = (
            vector_novelty * scoring.vector_novelty_weight
            + graph_novelty * scoring.graph_novelty_weight
        )

        final = (
            novelty * scoring.novelty_weight
            + (relevance / 10.0) * scoring.relevance_weight
        )

        is_dup = vector_novelty <= 0.15

        result = NoveltyResult(
            url=summary.url,
            vector_novelty=round(vector_novelty, 4),
            graph_novelty=round(graph_novelty, 4),
            novelty_score=round(novelty, 4),
            final_score=round(final, 4),
            relevance_score=relevance,
            is_near_duplicate=is_dup,
        )

        # Persist embedding
        async with vector_lock:
            vector_store.add(
                doc_id=summary.url,
                embedding=embedding,
                metadata={
                    "title": summary.title,
                    "source": summary.source_name,
                },
                document=embed_text[:500],
            )

        return result

    except asyncio.TimeoutError:
        log.warning("Embed timeout for %s", summary.url)
        if isinstance(breaker, CircuitBreaker):
            breaker.record_failure()
        return NoveltyFailure(
            url=summary.url, title=summary.title,
            source_name=summary.source_name,
            error_type="timeout",
            error_message=f"Embed timed out after {config.ollama.embed_timeout_seconds}s",
        )
    except Exception as exc:
        log.error(
            "Novelty scoring failed for %s (%s: %s), assigning defaults",
            summary.url, type(exc).__name__, exc, exc_info=True,
        )
        if isinstance(breaker, CircuitBreaker):
            breaker.record_failure()
        return NoveltyFailure(
            url=summary.url, title=summary.title,
            source_name=summary.source_name,
            error_type="unexpected",
            error_message=str(exc),
        )


def _make_default_result(
    url: str, relevance: int, scoring: object,
) -> NoveltyResult:
    """Create a default NoveltyResult for articles that failed scoring."""
    return NoveltyResult(
        url=url,
        vector_novelty=0.5,
        graph_novelty=0.5,
        novelty_score=0.5,
        final_score=round(
            0.5 * scoring.novelty_weight + (relevance / 10.0) * scoring.relevance_weight, 4
        ),
        relevance_score=relevance,
    )


async def score_novelty(
    summaries: list[ArticleSummary],
    relevance_by_url: dict[str, int],
    config: AppConfig,
    client: OllamaClient,
    vector_store: VectorStore,
    knowledge_graph: KnowledgeGraph,
    *,
    progress_callback: ProgressCallback | None = None,
    breaker: object | None = None,
    concurrency: int = 1,
    failures: list[NoveltyFailure] | None = None,
) -> list[NoveltyResult]:
    """Compute novelty + final ranking score for each article summary.

    Operates in four batched phases to minimise ChromaDB round-trips:
      A. Embed all articles concurrently (bounded by *concurrency*).
      B. Single batch query to ChromaDB for vector similarity.
      C. Compute graph novelty + final scores (pure CPU).
      D. Single batch upsert of all embeddings into ChromaDB.

    Returns results sorted by ``final_score`` descending.
    """
    from curiopilot.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

    # Deduplicate by URL, preserving first occurrence
    seen_urls: set[str] = set()
    summaries = [s for s in summaries if not (s.url in seen_urls or seen_urls.add(s.url))]  # type: ignore[func-returns-value]

    scoring = config.scoring
    results: list[NoveltyResult] = []
    _failures = failures if failures is not None else []
    model = config.models.embedding_model

    llm_sem = asyncio.Semaphore(concurrency)
    completed = 0
    progress_lock = asyncio.Lock()

    # -- Phase A: embed all articles concurrently --------------------------------

    async def _embed_one(idx: int) -> list[float] | NoveltyFailure:
        nonlocal completed
        summary = summaries[idx]

        if isinstance(breaker, CircuitBreaker):
            try:
                breaker.check()
            except CircuitBreakerOpen:
                return NoveltyFailure(
                    url=summary.url, title=summary.title,
                    source_name=summary.source_name,
                    error_type="circuit_breaker",
                    error_message="Circuit breaker open — Ollama unresponsive",
                )

        try:
            embed_text = _build_embed_text(summary)
            async with llm_sem:
                embedding = await asyncio.wait_for(
                    client.embed(model, embed_text, keep_alive="5m"),
                    timeout=config.ollama.embed_timeout_seconds,
                )
            if isinstance(breaker, CircuitBreaker):
                breaker.record_success()
            return embedding
        except asyncio.TimeoutError:
            log.warning("Embed timeout for %s", summary.url)
            if isinstance(breaker, CircuitBreaker):
                breaker.record_failure()
            return NoveltyFailure(
                url=summary.url, title=summary.title,
                source_name=summary.source_name,
                error_type="timeout",
                error_message=f"Embed timed out after {config.ollama.embed_timeout_seconds}s",
            )
        except Exception as exc:
            log.error(
                "Embedding failed for %s (%s: %s), assigning defaults",
                summary.url, type(exc).__name__, exc, exc_info=True,
            )
            if isinstance(breaker, CircuitBreaker):
                breaker.record_failure()
            return NoveltyFailure(
                url=summary.url, title=summary.title,
                source_name=summary.source_name,
                error_type="unexpected",
                error_message=str(exc),
            )
        finally:
            async with progress_lock:
                completed += 1
                if progress_callback and callable(progress_callback):
                    try:
                        progress_callback(completed, len(summaries))
                    except Exception:
                        pass

    embed_results = await asyncio.gather(
        *[_embed_one(i) for i in range(len(summaries))],
        return_exceptions=True,
    )

    # Separate successful embeddings from failures
    # Maps original index → embedding; failed indices get default results later
    valid_indices: list[int] = []
    valid_embeddings: list[list[float]] = []

    for i, r in enumerate(embed_results):
        if isinstance(r, list):
            valid_indices.append(i)
            valid_embeddings.append(r)
        elif isinstance(r, NoveltyFailure):
            _failures.append(r)
            relevance = relevance_by_url.get(summaries[i].url, 5)
            results.append(_make_default_result(summaries[i].url, relevance, scoring))
        elif isinstance(r, BaseException):
            log.error("Unexpected exception in embed gather: %s", r)
            relevance = relevance_by_url.get(summaries[i].url, 5)
            results.append(_make_default_result(summaries[i].url, relevance, scoring))

    if not valid_embeddings:
        results.sort(key=lambda r: r.final_score, reverse=True)
        return results

    # -- Phase B: batch query ChromaDB -------------------------------------------

    batch_neighbors = vector_store.query_batch(valid_embeddings, k=5)

    # -- Phase C: compute scores (pure CPU) --------------------------------------

    upsert_ids: list[str] = []
    upsert_embeddings: list[list[float]] = []
    upsert_metadatas: list[dict[str, str]] = []
    upsert_documents: list[str] = []

    for pos, orig_idx in enumerate(valid_indices):
        summary = summaries[orig_idx]
        embedding = valid_embeddings[pos]
        neighbors = batch_neighbors[pos]
        relevance = relevance_by_url.get(summary.url, 5)

        # Vector novelty from neighbors (same logic as _compute_vector_novelty)
        if not neighbors:
            vector_novelty = 1.0
        else:
            s_max = max(n["similarity"] for n in neighbors)
            if s_max > scoring.near_duplicate_threshold:
                vector_novelty = 0.1
            elif s_max >= scoring.related_threshold:
                t = (s_max - scoring.related_threshold) / (
                    scoring.near_duplicate_threshold - scoring.related_threshold
                )
                vector_novelty = round(0.6 - t * 0.3, 4)
            else:
                t = s_max / scoring.related_threshold if scoring.related_threshold > 0 else 0.0
                vector_novelty = round(1.0 - t * 0.2, 4)

        graph_novelty = knowledge_graph.compute_graph_novelty(summary.key_concepts)

        novelty = (
            vector_novelty * scoring.vector_novelty_weight
            + graph_novelty * scoring.graph_novelty_weight
        )
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

        # Collect data for batch upsert
        embed_text = _build_embed_text(summary)
        upsert_ids.append(summary.url)
        upsert_embeddings.append(embedding)
        upsert_metadatas.append({"title": summary.title, "source": summary.source_name})
        upsert_documents.append(embed_text[:500])

    # -- Phase D: batch upsert all embeddings ------------------------------------

    if upsert_ids:
        vector_store.add_batch(upsert_ids, upsert_embeddings, upsert_metadatas, upsert_documents)

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
