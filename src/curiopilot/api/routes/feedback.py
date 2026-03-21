"""Feedback API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from curiopilot.api.deps import get_article_store, get_url_store
from curiopilot.api.schemas import FeedbackItem, FeedbackRequest
from curiopilot.storage.article_store import ArticleStore
from curiopilot.storage.url_store import URLStore

router = APIRouter(tags=["feedback"])


@router.get(
    "/briefings/{date}/feedback",
    response_model=list[FeedbackItem],
)
async def get_feedback(
    date: str,
    url_store: URLStore = Depends(get_url_store),
):
    cursor = await url_store._db.execute(
        "SELECT briefing_date, article_number, title, read, interest, quality, processed_at "
        "FROM article_feedback WHERE briefing_date = ? ORDER BY article_number",
        (date,),
    )
    rows = await cursor.fetchall()
    return [
        FeedbackItem(
            briefing_date=r[0],
            article_number=r[1],
            title=r[2],
            read=bool(r[3]) if r[3] is not None else None,
            interest=r[4],
            quality=r[5],
            processed_at=r[6],
        )
        for r in rows
    ]


@router.post(
    "/briefings/{date}/articles/{number}/feedback",
    response_model=dict,
)
async def submit_feedback(
    date: str,
    number: int,
    body: FeedbackRequest,
    url_store: URLStore = Depends(get_url_store),
    article_store: ArticleStore = Depends(get_article_store),
):
    article = await article_store.get_article(date, number)
    if article is None:
        raise HTTPException(status_code=404, detail=f"Article {number} not found for {date}")

    cursor = await url_store._db.execute(
        "SELECT read, interest, quality FROM article_feedback "
        "WHERE briefing_date = ? AND article_number = ?",
        (date, number),
    )
    existing = await cursor.fetchone()

    read_val = body.read if body.read is not None else (bool(existing[0]) if existing and existing[0] is not None else False)
    interest_val = body.interest if body.interest is not None else (existing[1] if existing else None)
    quality_val = body.quality if body.quality is not None else (existing[2] if existing else None)

    await url_store.record_feedback(
        briefing_date=date,
        article_number=number,
        title=article["title"],
        read=read_val,
        interest=interest_val,
        quality=quality_val,
        processed_at=datetime.now(timezone.utc).isoformat(),
    )

    return {"status": "ok", "briefing_date": date, "article_number": number}
