"""Articles API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from curiopilot.api.deps import get_article_store
from curiopilot.api.schemas import ArticleFull
from curiopilot.storage.article_store import ArticleStore

router = APIRouter(tags=["articles"])


@router.get("/briefings/{date}/articles/{number}", response_model=ArticleFull)
async def get_article(
    date: str,
    number: int,
    article_store: ArticleStore = Depends(get_article_store),
):
    article = await article_store.get_article(date, number)
    if article is None:
        raise HTTPException(
            status_code=404,
            detail=f"Article {number} not found for {date}",
        )
    return ArticleFull(**article)
