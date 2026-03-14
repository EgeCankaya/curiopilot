"""Pipeline entry point -- delegates to the LangGraph StateGraph."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from curiopilot.agents.novelty_engine import NoveltyResult
from curiopilot.config import load_config
from curiopilot.llm.ollama import OllamaClient
from curiopilot.models import ArticleEntry, ArticleSummary, ProgressCallback, ScoredArticle
from curiopilot.storage.knowledge_graph import GraphUpdateStats
from curiopilot.storage.url_store import URLStore

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Aggregated outcome of a single pipeline run."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    articles_scanned: int = 0
    articles_new: int = 0
    articles_filtered: int = 0
    new_articles: list[ArticleEntry] = field(default_factory=list)
    scored: list[ScoredArticle] = field(default_factory=list)
    summaries: list[ArticleSummary] = field(default_factory=list)
    novelty_results: list[NoveltyResult] = field(default_factory=list)
    graph_stats: GraphUpdateStats = field(default_factory=GraphUpdateStats)
    briefing_path: Path | None = None
    briefing_markdown: str = ""
    duration_seconds: float = 0.0


async def run_pipeline(
    config_path: str | Path = "config.yaml",
    *,
    dry_run: bool = False,
    no_filter: bool = False,
    source_names: list[str] | None = None,
    verbose: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> RunResult:
    """Execute the CurioPilot pipeline via LangGraph StateGraph.

    The graph follows the PRD Section 6.3 design with conditional edges
    for dry-run (stop after dedup) and empty-result short-circuits.
    """
    from curiopilot.logging_config import setup_logging

    t0 = time.monotonic()
    setup_logging(verbose=verbose)

    config = load_config(config_path)
    result = RunResult()

    client = OllamaClient(
        base_url=config.ollama.base_url,
        timeout_seconds=config.ollama.timeout_seconds,
        max_retries=config.ollama.max_retries,
    )
    await client.open()

    db_dir = Path(config.paths.database_dir)
    store = URLStore(db_dir / "curiopilot.db")
    await store.open()

    try:
        from curiopilot.pipeline.graph import build_pipeline_graph

        graph = build_pipeline_graph()
        compiled = graph.compile()

        initial_state = {
            "config": config,
            "client": client,
            "store": store,
            "db_dir": db_dir,
            "dry_run": dry_run,
            "no_filter": no_filter,
            "source_names": source_names,
            "progress_callback": progress_callback,
            "t0": t0,
            "run_id": result.run_id,
            "started_at": result.started_at,
        }

        final_state = await compiled.ainvoke(initial_state)

        # Extract results from final graph state
        result.articles_scanned = len(final_state.get("all_articles", []))
        result.new_articles = final_state.get("new_articles", [])
        result.articles_new = len(result.new_articles)
        result.scored = final_state.get("passed", [])
        result.articles_filtered = len(result.scored)
        result.summaries = final_state.get("summaries", [])
        result.novelty_results = final_state.get("novelty_results", [])
        result.graph_stats = final_state.get("graph_stats", GraphUpdateStats())
        result.briefing_path = final_state.get("briefing_path")
        result.briefing_markdown = final_state.get("briefing_markdown", "")

    finally:
        try:
            completed = datetime.now(timezone.utc).isoformat()
            await store.record_run(
                run_id=result.run_id,
                started_at=result.started_at,
                completed_at=completed,
                articles_scanned=result.articles_scanned,
                articles_relevant=result.articles_filtered,
                articles_briefed=len(result.summaries),
                new_concepts_added=result.graph_stats.nodes_added,
            )
        except Exception:
            log.debug("Failed to record pipeline run", exc_info=True)

        await store.close()
        await client.close()
        result.duration_seconds = time.monotonic() - t0

    return result
