"""Core data models shared across CurioPilot modules."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field


class ProgressCallback(Protocol):
    """Callable that receives pipeline progress updates."""

    def __call__(self, phase: str, current: int, total: int) -> None: ...


class ArticleEntry(BaseModel):
    """Lightweight article descriptor returned by scrapers."""

    title: str
    url: str
    source_name: str
    snippet: str | None = None
    score: int | None = None


class RelevanceScore(BaseModel):
    """Structured output from the relevance‑filter LLM call."""

    score: int = Field(ge=0, le=10)
    justification: str


class ScoredArticle(BaseModel):
    """An article together with its relevance score."""

    article: ArticleEntry
    relevance: RelevanceScore


class ArticleSummary(BaseModel):
    """Structured summary produced by the deep‑reader agent (Phase 2+)."""

    title: str
    source_name: str
    url: str
    date_processed: datetime
    key_concepts: list[str]
    summary: str
    novel_insights: str
    technical_depth: int = Field(ge=1, le=5)
    related_topics: list[str]
    relationships: list[dict[str, str]] = Field(default_factory=list)
