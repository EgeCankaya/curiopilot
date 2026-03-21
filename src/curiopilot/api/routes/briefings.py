"""Briefings API routes."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from curiopilot.api.deps import get_article_store, get_config, get_url_store
from curiopilot.api.schemas import ArticleListItem, BriefingDetail, BriefingListItem
from curiopilot.storage.article_store import ArticleStore
from curiopilot.storage.url_store import URLStore

router = APIRouter(tags=["briefings"])


@router.get("/briefings", response_model=list[BriefingListItem])
async def list_briefings(
    article_store: ArticleStore = Depends(get_article_store),
    url_store: URLStore = Depends(get_url_store),
):
    dates = await article_store.list_briefing_dates()
    result: list[BriefingListItem] = []
    for d in dates:
        has_fb = await url_store.is_feedback_processed(d["briefing_date"])
        result.append(BriefingListItem(
            briefing_date=d["briefing_date"],
            article_count=d["article_count"],
            has_feedback=has_fb,
        ))
    return result


@router.get("/briefings/{date}", response_model=BriefingDetail)
async def get_briefing(
    date: str,
    article_store: ArticleStore = Depends(get_article_store),
    config=Depends(get_config),
):
    articles = await article_store.get_articles_by_date(date)
    if not articles:
        raise HTTPException(status_code=404, detail=f"No briefing found for {date}")

    article_items = [ArticleListItem(**a) for a in articles]

    briefing_md = _load_briefing_markdown(config, date)
    meta = _parse_briefing_metadata(briefing_md) if briefing_md else {}

    return BriefingDetail(
        briefing_date=date,
        articles=article_items,
        articles_scanned=meta.get("articles_scanned"),
        articles_relevant=meta.get("articles_relevant"),
        articles_briefed=meta.get("articles_briefed"),
        pipeline_runtime=meta.get("pipeline_runtime"),
        new_concepts=meta.get("new_concepts", []),
        graph_stats=meta.get("graph_stats"),
        explorations=meta.get("explorations", []),
    )


def _load_briefing_markdown(config, date: str) -> str | None:
    briefings_dir = Path(config.paths.briefings_dir)
    path = briefings_dir / f"{date}.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


_STATS_RE = re.compile(
    r"\*\*Articles Scanned\*\*:\s*(\d+)\s*\|\s*"
    r"\*\*Passed Relevance\*\*:\s*(\d+)\s*\|\s*"
    r"\*\*In Briefing\*\*:\s*(\d+)"
)
_RUNTIME_RE = re.compile(r"\*\*Pipeline Runtime\*\*:\s*(.+)")
_NEW_CONCEPT_RE = re.compile(r"^- \*\*(.+?)\*\*:", re.MULTILINE)
_GRAPH_NODES_RE = re.compile(r"\*\*Nodes added\*\*:\s*(\d+)")
_GRAPH_EDGES_RE = re.compile(r"\*\*Edges added\*\*:\s*(\d+)")
_GRAPH_TOTAL_RE = re.compile(r"\*\*Total knowledge nodes\*\*:\s*(\d+)")
_GRAPH_CONNECTED_RE = re.compile(
    r"\*\*Most connected topic\*\*:\s*(.+?)\s*\((\d+)\s*connections?\)"
)
_EXPLORATION_RE = re.compile(r"^\d+\.\s+\*\*(.+?)\*\*\s*--\s*(.+)$", re.MULTILINE)


def _parse_briefing_metadata(md: str) -> dict:
    meta: dict = {}

    stats_m = _STATS_RE.search(md)
    if stats_m:
        meta["articles_scanned"] = int(stats_m.group(1))
        meta["articles_relevant"] = int(stats_m.group(2))
        meta["articles_briefed"] = int(stats_m.group(3))

    runtime_m = _RUNTIME_RE.search(md)
    if runtime_m:
        meta["pipeline_runtime"] = runtime_m.group(1).strip()

    concepts_section = _extract_section(md, "New Concepts")
    if concepts_section:
        meta["new_concepts"] = _NEW_CONCEPT_RE.findall(concepts_section)

    graph_section = _extract_section(md, "Knowledge Graph Update")
    if graph_section:
        graph_stats: dict = {}
        m = _GRAPH_NODES_RE.search(graph_section)
        if m:
            graph_stats["nodes_added"] = int(m.group(1))
        m = _GRAPH_EDGES_RE.search(graph_section)
        if m:
            graph_stats["edges_added"] = int(m.group(1))
        m = _GRAPH_TOTAL_RE.search(graph_section)
        if m:
            graph_stats["total_nodes"] = int(m.group(1))
        m = _GRAPH_CONNECTED_RE.search(graph_section)
        if m:
            graph_stats["most_connected"] = m.group(1)
            graph_stats["most_connected_edges"] = int(m.group(2))
        if graph_stats:
            meta["graph_stats"] = graph_stats

    explorations_section = _extract_section(md, "Suggested Explorations")
    if explorations_section:
        meta["explorations"] = [
            f"{topic} -- {reason}"
            for topic, reason in _EXPLORATION_RE.findall(explorations_section)
        ]

    return meta


def _extract_section(md: str, heading: str) -> str | None:
    """Extract text between a ## heading and the next ## heading (or end of file)."""
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(md)
    return m.group(1) if m else None
