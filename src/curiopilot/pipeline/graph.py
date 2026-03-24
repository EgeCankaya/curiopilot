"""LangGraph-based pipeline orchestration for CurioPilot (PRD Section 6.3).

Defines the pipeline as a StateGraph with typed state and conditional edges
for dry-run and no-filter modes.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from curiopilot.agents.filter_agent import FilterFailure, score_articles
from curiopilot.agents.novelty_engine import NoveltyFailure, NoveltyResult, score_novelty
from curiopilot.config import AppConfig, load_config
from curiopilot.llm.circuit_breaker import CircuitBreaker
from curiopilot.llm.ollama import OllamaClient
from curiopilot.models import ArticleEntry, ArticleSummary, ProgressCallback, RelevanceScore, ScoredArticle
from curiopilot.scrapers import get_scraper
from curiopilot.storage.article_store import ArticleStore
from curiopilot.storage.knowledge_graph import GraphUpdateStats, KnowledgeGraph
from curiopilot.storage.url_store import URLStore
from curiopilot.storage.vector_store import VectorStore

log = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Normalize a source name for fuzzy matching ('Hacker News' -> 'hackernews')."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# ── Pipeline State ───────────────────────────────────────────────────────────

class PipelineState(TypedDict, total=False):
    """Shared state passed between LangGraph nodes."""

    # Inputs (set once at start)
    config: AppConfig
    client: OllamaClient
    store: URLStore
    article_store: ArticleStore | None
    db_dir: Path
    dry_run: bool
    no_filter: bool
    source_names: list[str] | None
    progress_callback: ProgressCallback | None
    t0: float
    incremental: bool

    # Checkpoint store (optional)
    checkpoint_store: Any  # CheckpointStore | None

    # Discover phase
    all_articles: list[ArticleEntry]

    # Dedup phase
    new_articles: list[ArticleEntry]

    # Filter phase
    passed: list[ScoredArticle]

    # Deep read phase
    summaries: list[ArticleSummary]

    # Novelty phase
    novelty_results: list[NoveltyResult]
    relevance_by_url: dict[str, int]

    # Shared knowledge graph (loaded once, reused across nodes)
    knowledge_graph: KnowledgeGraph | None

    # Graph update phase
    graph_stats: GraphUpdateStats
    new_concepts: list[tuple[str, str]]
    explorations: list

    # Briefing phase
    briefing_markdown: str
    briefing_path: Path | None

    # Bookkeeping
    run_id: str
    started_at: str

    # DLQ tracking (accumulated across phases)
    dlq_failures: list[dict]


# ── Node functions ───────────────────────────────────────────────────────────


async def ingest_feedback_node(state: PipelineState) -> dict:
    """Parse user feedback from past briefings and apply to the knowledge graph."""
    from curiopilot.feedback import has_feedback_section, parse_briefing_feedback

    config = state["config"]
    store = state["store"]
    cb = state.get("progress_callback")

    briefings_dir = Path(config.paths.briefings_dir)
    if not briefings_dir.is_dir():
        return {}

    briefing_files = sorted(briefings_dir.glob("*.md"))
    if not briefing_files:
        return {}

    _notify(cb, "feedback", 0, len(briefing_files))
    total_applied = 0

    kg = KnowledgeGraph(config.paths.graph_path)
    kg.load()

    for i, bf in enumerate(briefing_files):
        briefing_date = bf.stem
        if await store.is_feedback_processed(briefing_date):
            _notify(cb, "feedback", i + 1, len(briefing_files))
            continue

        if not has_feedback_section(bf):
            _notify(cb, "feedback", i + 1, len(briefing_files))
            continue

        entries = parse_briefing_feedback(bf)
        if not entries:
            _notify(cb, "feedback", i + 1, len(briefing_files))
            continue

        now_str = datetime.now(timezone.utc).isoformat()
        for af in entries:
            kg.apply_feedback(
                af.concepts, read=af.read, interest=af.interest,
            )
            await store.record_feedback(
                briefing_date=briefing_date,
                article_number=af.article_number,
                title=af.title,
                read=af.read,
                interest=af.interest,
                quality=af.quality,
                processed_at=now_str,
            )
            total_applied += 1

        _notify(cb, "feedback", i + 1, len(briefing_files))

    if total_applied > 0:
        kg.save()
        log.info("Ingested feedback for %d article(s) from past briefings", total_applied)

    return {"knowledge_graph": kg}


async def discover_node(state: PipelineState) -> dict:
    """Crawl all configured sources and collect article entries."""
    config = state["config"]
    store = state["store"]
    cb = state.get("progress_callback")
    source_names = state.get("source_names")
    incremental = state.get("incremental", False)

    _notify(cb, "discover", 0, 1)
    all_articles: list[ArticleEntry] = []
    sources = config.sources
    if source_names:
        slugs = {_slugify(n) for n in source_names}
        sources = [s for s in sources if _slugify(s.name) in slugs]
        if not sources:
            available = [s.name for s in config.sources]
            log.warning(
                "No configured sources matched: %s (available: %s)",
                source_names, available,
            )

    # Incremental: skip sources already scraped since last successful run
    skip_sources: set[str] = set()
    if incremental:
        last_run = await store.last_successful_run()
        if last_run and last_run.get("completed_at"):
            skip_sources = await store.sources_scraped_since(last_run["completed_at"])
            if skip_sources:
                log.info("Incremental: skipping %d already-scraped source(s): %s", len(skip_sources), skip_sources)

    import asyncio

    import httpx

    for i, source in enumerate(sources):
        if source.name in skip_sources:
            log.info("Incremental: skipping source '%s'", source.name)
            _notify(cb, "discover", i + 1, len(sources))
            continue

        try:
            scraper = get_scraper(source)
            articles = await scraper.extract_articles()
            log.info("Source '%s': fetched %d articles", source.name, len(articles))
            all_articles.extend(articles)
            # Record source run for incremental tracking
            await store.record_source_run(source.name, len(articles))
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            log.warning("Source '%s' failed due to network error: %s", source.name, exc)
        except Exception:
            log.exception("Source '%s' failed unexpectedly, skipping", source.name)
        _notify(cb, "discover", i + 1, len(sources))

    return {"all_articles": all_articles}


async def dedup_node(state: PipelineState) -> dict:
    """Deduplicate URLs against SQLite; mark visited for dry-run."""
    store = state["store"]
    all_articles = state.get("all_articles", [])
    dry_run = state.get("dry_run", False)
    cb = state.get("progress_callback")

    _notify(cb, "dedup", 0, 1)
    urls = [a.url for a in all_articles]
    new_urls = await store.filter_new_urls(urls)
    new_articles = [a for a in all_articles if a.url in new_urls]
    log.info(
        "Dedup: %d scanned -> %d new (skipped %d already visited)",
        len(all_articles), len(new_articles), len(all_articles) - len(new_articles),
    )
    _notify(cb, "dedup", 1, 1)

    if dry_run:
        rows = [(a.url, a.title, a.source_name, None, None) for a in new_articles]
        await store.mark_batch_visited(rows)

    return {"new_articles": new_articles}


async def filter_node(state: PipelineState) -> dict:
    """Score articles for relevance using the 7B model."""
    config = state["config"]
    client = state["client"]
    store = state["store"]
    new_articles = state.get("new_articles", [])
    no_filter = state.get("no_filter", False)
    cb = state.get("progress_callback")
    run_id = state.get("run_id")

    dlq_failures = list(state.get("dlq_failures", []))

    if no_filter:
        passed = [
            ScoredArticle(
                article=a,
                relevance=RelevanceScore(score=10, justification="filter skipped"),
            )
            for a in new_articles
        ]
        rows = [(a.url, a.title, a.source_name, True, 10) for a in new_articles]
        await store.mark_batch_visited(rows)
    else:
        _notify(cb, "filter", 0, len(new_articles))

        # Create circuit breaker for this phase
        breaker = CircuitBreaker(
            failure_threshold=config.ollama.circuit_breaker_threshold,
            reset_timeout=config.ollama.circuit_breaker_reset_seconds,
        )
        failures: list[FilterFailure] = []

        scored = await score_articles(
            new_articles, config, client,
            keep_alive="5m",
            breaker=breaker,
            concurrency=config.ollama.llm_concurrency,
            failures=failures,
        )

        # Record failures in DLQ
        for f in failures:
            dlq_failures.append({
                "url": f.url, "title": f.title, "source_name": f.source_name,
                "phase": "filter", "error_type": f.error_type,
                "error_message": f.error_message, "run_id": run_id,
            })
            await store.add_to_dlq(
                f.url, f.title, f.source_name,
                "filter", f.error_type, f.error_message, run_id,
            )

        threshold = config.scoring.relevance_threshold

        passed = []
        below = []
        batch_rows: list[tuple[str, str | None, str | None, bool | None, int | None]] = []
        for sa in scored:
            above = sa.relevance.score >= threshold
            batch_rows.append((
                sa.article.url, sa.article.title, sa.article.source_name,
                above, sa.relevance.score,
            ))
            if above:
                passed.append(sa)
            else:
                below.append(sa)

        min_items = config.scoring.min_briefing_items
        if len(passed) < min_items and below:
            below.sort(key=lambda s: s.relevance.score, reverse=True)
            backfill = below[: min_items - len(passed)]
            log.info(
                "Filter: only %d above threshold, backfilling %d to reach minimum %d",
                len(passed), len(backfill), min_items,
            )
            passed.extend(backfill)

        scored_urls = {sa.article.url for sa in scored}
        for a in new_articles:
            if a.url not in scored_urls:
                batch_rows.append((a.url, a.title, a.source_name, False, None))

        await store.mark_batch_visited(batch_rows)
        _notify(cb, "filter", len(new_articles), len(new_articles))

    passed.sort(key=lambda s: s.relevance.score, reverse=True)
    max_items = config.scoring.max_briefing_items
    passed = passed[:max_items]
    log.info("Filter: %d passed (capped to %d)", len(passed), max_items)

    return {"passed": passed, "dlq_failures": dlq_failures}


async def swap_to_reader_node(state: PipelineState) -> dict:
    """Unload the 7B filter model and warm up the 14B reader model."""
    config = state["config"]
    client = state["client"]
    no_filter = state.get("no_filter", False)
    cb = state.get("progress_callback")

    if not no_filter:
        _notify(cb, "model_swap", 0, 1)
        await client.swap_model(config.models.filter_model, config.models.reader_model)
        _notify(cb, "model_swap", 1, 1)

    return {}


async def deep_read_node(state: PipelineState) -> dict:
    """Fetch, extract, and summarize each article using the 14B model."""
    from curiopilot.agents.reader_agent import ReaderFailure, read_and_summarize

    config = state["config"]
    client = state["client"]
    store = state["store"]
    passed = state.get("passed", [])
    cb = state.get("progress_callback")
    run_id = state.get("run_id")

    dlq_failures = list(state.get("dlq_failures", []))

    # Create circuit breaker for this phase
    breaker = CircuitBreaker(
        failure_threshold=config.ollama.circuit_breaker_threshold,
        reset_timeout=config.ollama.circuit_breaker_reset_seconds,
    )
    failures: list[ReaderFailure] = []

    def _reader_progress(current: int, total: int) -> None:
        _notify(cb, "read", current, total)

    _notify(cb, "read", 0, len(passed))
    summaries = await read_and_summarize(
        passed, config, client,
        progress_callback=_reader_progress,
        breaker=breaker,
        fetch_concurrency=config.ollama.fetch_concurrency,
        llm_concurrency=config.ollama.llm_concurrency,
        failures=failures,
    )

    # Record failures in DLQ
    for f in failures:
        dlq_failures.append({
            "url": f.url, "title": f.title, "source_name": f.source_name,
            "phase": f.phase, "error_type": f.error_type,
            "error_message": f.error_message, "run_id": run_id,
        })
        await store.add_to_dlq(
            f.url, f.title, f.source_name,
            f.phase, f.error_type, f.error_message, run_id,
        )

    log.info("Deep read: %d summaries produced from %d articles", len(summaries), len(passed))

    return {"summaries": summaries, "dlq_failures": dlq_failures}


async def novelty_node(state: PipelineState) -> dict:
    """Swap to embedding model, score novelty, and filter near-duplicates."""
    config = state["config"]
    client = state["client"]
    store = state["store"]
    db_dir = state["db_dir"]
    passed = state.get("passed", [])
    summaries = state.get("summaries", [])
    cb = state.get("progress_callback")
    run_id = state.get("run_id")

    dlq_failures = list(state.get("dlq_failures", []))

    _notify(cb, "model_swap_embed", 0, 1)
    await client.swap_model(
        config.models.reader_model, config.models.embedding_model, embedding=True
    )
    _notify(cb, "model_swap_embed", 1, 1)

    chroma_dir = db_dir / "chromadb"
    vector_store = VectorStore(chroma_dir)
    vector_store.open()

    kg = state.get("knowledge_graph")
    if kg is None:
        kg = KnowledgeGraph(config.paths.graph_path)
        kg.load()

    if kg.node_count() > 0:
        pruned = kg.apply_memory_decay()
        if pruned:
            log.info("Memory decay pruned %d stale nodes", pruned)

    relevance_by_url = {sa.article.url: sa.relevance.score for sa in passed}

    # Create circuit breaker for this phase
    breaker = CircuitBreaker(
        failure_threshold=config.ollama.circuit_breaker_threshold,
        reset_timeout=config.ollama.circuit_breaker_reset_seconds,
    )
    novelty_failures: list[NoveltyFailure] = []

    def _novelty_progress(current: int, total: int) -> None:
        _notify(cb, "novelty", current, total)

    _notify(cb, "novelty", 0, len(summaries))
    novelty_results = await score_novelty(
        summaries, relevance_by_url, config, client,
        vector_store, kg,
        progress_callback=_novelty_progress,
        breaker=breaker,
        concurrency=config.ollama.llm_concurrency,
        failures=novelty_failures,
    )

    # Record failures in DLQ
    for f in novelty_failures:
        dlq_failures.append({
            "url": f.url, "title": f.title, "source_name": f.source_name,
            "phase": "novelty", "error_type": f.error_type,
            "error_message": f.error_message, "run_id": run_id,
        })
        await store.add_to_dlq(
            f.url, f.title, f.source_name,
            "novelty", f.error_type, f.error_message, run_id,
        )

    dup_urls = {nr.url for nr in novelty_results if nr.is_near_duplicate}
    if dup_urls:
        log.info("Filtered %d near-duplicate article(s)", len(dup_urls))

    score_by_url = {nr.url: nr.final_score for nr in novelty_results}
    non_dup = [s for s in summaries if s.url not in dup_urls]
    non_dup.sort(key=lambda s: score_by_url.get(s.url, 0), reverse=True)

    min_items = config.scoring.min_briefing_items
    if len(non_dup) < min_items:
        # Backfill from near-duplicates (best-scoring first) to meet minimum
        dup_summaries = [s for s in summaries if s.url in dup_urls]
        dup_summaries.sort(key=lambda s: score_by_url.get(s.url, 0), reverse=True)
        backfill = dup_summaries[: min_items - len(non_dup)]
        if backfill:
            log.info(
                "Novelty: only %d non-duplicate article(s), backfilling %d near-duplicate(s) "
                "to reach minimum %d",
                len(non_dup), len(backfill), min_items,
            )
        non_dup.extend(backfill)
        non_dup.sort(key=lambda s: score_by_url.get(s.url, 0), reverse=True)

    summaries = non_dup

    return {
        "summaries": summaries,
        "novelty_results": novelty_results,
        "relevance_by_url": relevance_by_url,
        "knowledge_graph": kg,
        "dlq_failures": dlq_failures,
    }


async def graph_update_node(state: PipelineState) -> dict:
    """Update the knowledge graph with concepts from summarized articles."""
    config = state["config"]
    summaries = state.get("summaries", [])
    cb = state.get("progress_callback")

    kg = state.get("knowledge_graph")
    if kg is None:
        kg = KnowledgeGraph(config.paths.graph_path)
        kg.load()

    _notify(cb, "graph_update", 0, len(summaries))
    cumulative = GraphUpdateStats()
    new_concepts: list[tuple[str, str]] = []

    for idx, summary in enumerate(summaries):
        stats = kg.update_from_article(
            summary.key_concepts, summary.url,
            relationships=summary.relationships if summary.relationships else None,
        )
        cumulative.nodes_added += stats.nodes_added
        cumulative.edges_added += stats.edges_added
        for concept in stats.new_concept_names:
            new_concepts.append((concept, summary.title))
        _notify(cb, "graph_update", idx + 1, len(summaries))

    cumulative.total_nodes = kg.node_count()
    cumulative.total_edges = kg.edge_count()
    top_topic, top_edges = kg.most_connected_topic()
    cumulative.most_connected = top_topic
    cumulative.most_connected_edges = top_edges
    cumulative.new_concept_names = [c for c, _ in new_concepts]

    kg.save()
    explorations = kg.suggest_explorations(max_items=5)

    log.info(
        "Graph update: +%d nodes, +%d edges, %d total nodes",
        cumulative.nodes_added, cumulative.edges_added, cumulative.total_nodes,
    )

    return {
        "graph_stats": cumulative,
        "new_concepts": new_concepts,
        "explorations": explorations,
    }


async def briefing_node(state: PipelineState) -> dict:
    """Generate and save the daily Markdown briefing."""
    from curiopilot.agents.briefing_agent import BriefingContext, generate_briefing, save_briefing

    config = state["config"]
    cb = state.get("progress_callback")
    t0 = state.get("t0", time.monotonic())

    _notify(cb, "briefing", 0, 1)

    duration = time.monotonic() - t0
    ctx = BriefingContext(
        summaries=state.get("summaries", []),
        scored=state.get("passed", []),
        novelty_results=state.get("novelty_results", []),
        graph_stats=state.get("graph_stats", GraphUpdateStats()),
        explorations=state.get("explorations", []),
        new_concepts=state.get("new_concepts", []),
        articles_scanned=len(state.get("all_articles", [])),
        articles_relevant=len(state.get("passed", [])),
        pipeline_duration_s=duration,
    )
    md = generate_briefing(ctx)
    path = save_briefing(md, config.paths.briefings_dir)

    article_store = state.get("article_store")
    if article_store is not None:
        summaries = state.get("summaries", [])
        novelty_results = state.get("novelty_results", [])
        relevance_by_url = state.get("relevance_by_url", {})
        today_str = (ctx.briefing_date or __import__("datetime").date.today()).isoformat()
        try:
            count = await article_store.insert_articles(
                today_str, summaries, novelty_results, relevance_by_url,
            )
            log.info("Inserted %d article(s) into article store for %s", count, today_str)
        except Exception:
            log.warning("Failed to insert articles into article store", exc_info=True)

    _notify(cb, "briefing", 1, 1)

    return {"briefing_markdown": md, "briefing_path": path}


# ── Routing functions ────────────────────────────────────────────────────────


def _should_stop_after_dedup(state: PipelineState) -> str:
    if state.get("dry_run", False):
        return END
    if not state.get("new_articles"):
        return END
    return "filter"


def _should_stop_after_filter(state: PipelineState) -> str:
    if not state.get("passed"):
        return END
    return "swap_to_reader"


def _should_stop_after_read(state: PipelineState) -> str:
    if not state.get("summaries"):
        return END
    return "novelty"


# ── Checkpoint wrapper ───────────────────────────────────────────────────────


def checkpointed(phase: str, fn):
    """Wrap a node function to save checkpoint data after execution."""
    async def wrapper(state: PipelineState) -> dict:
        result = await fn(state)
        cs = state.get("checkpoint_store")
        if cs is not None:
            try:
                await cs.save(phase, result)
            except Exception:
                log.warning("Failed to save checkpoint for phase '%s'", phase, exc_info=True)
        return result
    wrapper.__name__ = fn.__name__
    return wrapper


# ── Graph builder ────────────────────────────────────────────────────────────


# Phase ordering for resume support
PHASE_ORDER = [
    "ingest_feedback", "discover", "dedup", "filter",
    "swap_to_reader", "deep_read", "novelty", "graph_update", "briefing",
]


def build_pipeline_graph(*, start_from: str | None = None) -> StateGraph:
    """Construct the LangGraph StateGraph for the CurioPilot pipeline."""
    graph = StateGraph(PipelineState)

    graph.add_node("ingest_feedback", checkpointed("ingest_feedback", ingest_feedback_node))
    graph.add_node("discover", checkpointed("discover", discover_node))
    graph.add_node("dedup", checkpointed("dedup", dedup_node))
    graph.add_node("filter", checkpointed("filter", filter_node))
    graph.add_node("swap_to_reader", swap_to_reader_node)
    graph.add_node("deep_read", checkpointed("deep_read", deep_read_node))
    graph.add_node("novelty", checkpointed("novelty", novelty_node))
    graph.add_node("graph_update", checkpointed("graph_update", graph_update_node))
    graph.add_node("briefing", checkpointed("briefing", briefing_node))

    entry = start_from if start_from and start_from in PHASE_ORDER else "ingest_feedback"
    graph.set_entry_point(entry)

    graph.add_edge("ingest_feedback", "discover")
    graph.add_edge("discover", "dedup")
    graph.add_conditional_edges("dedup", _should_stop_after_dedup, {"filter": "filter", END: END})
    graph.add_conditional_edges("filter", _should_stop_after_filter, {"swap_to_reader": "swap_to_reader", END: END})
    graph.add_edge("swap_to_reader", "deep_read")
    graph.add_conditional_edges("deep_read", _should_stop_after_read, {"novelty": "novelty", END: END})
    graph.add_edge("novelty", "graph_update")
    graph.add_edge("graph_update", "briefing")
    graph.add_edge("briefing", END)

    return graph


def _notify(callback: ProgressCallback | None, phase: str, current: int, total: int) -> None:
    if callback is not None:
        try:
            callback(phase, current, total)
        except Exception:
            pass
