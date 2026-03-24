"""Pydantic request/response models for the CurioPilot API."""

from __future__ import annotations

from pydantic import BaseModel


class BriefingListItem(BaseModel):
    briefing_date: str
    article_count: int
    has_feedback: bool = False
    read_count: int = 0


class ArticleListItem(BaseModel):
    id: int
    article_number: int
    title: str
    source_name: str
    url: str
    summary: str
    novel_insights: str
    key_concepts: list[str]
    related_topics: list[str]
    relevance_score: int
    novelty_score: float
    graph_novelty: float
    vector_novelty: float
    novelty_explanation: str
    technical_depth: int
    is_deepening: bool
    body_content_type: str
    created_at: str | None = None


class BriefingDetail(BaseModel):
    briefing_date: str
    articles: list[ArticleListItem]
    articles_scanned: int | None = None
    articles_relevant: int | None = None
    articles_briefed: int | None = None
    pipeline_runtime: str | None = None
    new_concepts: list[str] = []
    graph_stats: dict | None = None
    explorations: list[str] = []


class ArticleFull(ArticleListItem):
    body_content: str


class FeedbackItem(BaseModel):
    briefing_date: str
    article_number: int
    title: str | None = None
    read: bool | None = None
    interest: int | None = None
    quality: str | None = None
    processed_at: str | None = None


class FeedbackRequest(BaseModel):
    read: bool | None = None
    interest: int | None = None
    quality: str | None = None


class RunRequest(BaseModel):
    incremental: bool = False
    resume_run_id: str | None = None
    rerun_date: str | None = None


class RunResponse(BaseModel):
    run_id: str
    status: str


class RunStatus(BaseModel):
    status: str
    run_id: str | None = None
    error: str | None = None


class DLQItem(BaseModel):
    url: str
    title: str | None = None
    source_name: str | None = None
    phase: str
    error_type: str
    error_message: str | None = None
    failed_at: str
    run_id: str | None = None
    retry_count: int = 0


class DLQStats(BaseModel):
    total: int
    by_phase: dict[str, int] = {}
    by_error_type: dict[str, int] = {}


class StatsResponse(BaseModel):
    urls_visited: int
    urls_passed_relevance: int
    sources_seen: int
    article_embeddings: int
    graph_nodes: int
    graph_edges: int
    most_connected_topic: str | None = None
    most_connected_edges: int | None = None


class SearchResult(BaseModel):
    briefing_date: str
    article_number: int
    title: str
    source_name: str
    summary: str
    relevance_score: int
    novelty_score: float


class ObsidianStatusResponse(BaseModel):
    vault_path: str
    configured: bool
    total_concepts: int
    total_briefings: int
    category_summary: dict[str, int]
    last_exported: str | None = None


class ObsidianExportResponse(BaseModel):
    exported_concepts: int
    exported_briefings: int
    vault_path: str


class GraphNode(BaseModel):
    id: str
    label: str
    familiarity: float = 0.0
    encounter_count: int = 0
    degree: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship_type: str = "co_occurrence"


class GraphResponse(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    total_nodes: int = 0
    total_edges: int = 0


class ImportedSource(BaseModel):
    name: str
    url: str


class OPMLImportResponse(BaseModel):
    added: list[ImportedSource] = []
    skipped_duplicates: list[ImportedSource] = []
