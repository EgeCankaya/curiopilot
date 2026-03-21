"""Pydantic request/response models for the CurioPilot API."""

from __future__ import annotations

from pydantic import BaseModel


class BriefingListItem(BaseModel):
    briefing_date: str
    article_count: int
    has_feedback: bool = False


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


class RunResponse(BaseModel):
    run_id: str
    status: str


class RunStatus(BaseModel):
    status: str
    run_id: str | None = None
    error: str | None = None


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
