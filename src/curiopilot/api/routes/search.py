"""Search API route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from curiopilot.api.deps import get_article_store
from curiopilot.api.schemas import SearchResult
from curiopilot.storage.article_store import ArticleStore

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[SearchResult])
async def search_articles(
    q: str = Query(..., min_length=1, description="Search query"),
    article_store: ArticleStore = Depends(get_article_store),
):
    rows = await article_store.search_articles(q)
    return [
        SearchResult(
            briefing_date=r["briefing_date"],
            article_number=r["article_number"],
            title=r["title"],
            source_name=r["source_name"],
            summary=r["summary"],
            relevance_score=r["relevance_score"],
            novelty_score=r["novelty_score"],
        )
        for r in rows
    ]
