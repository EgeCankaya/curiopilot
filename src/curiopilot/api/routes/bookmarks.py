"""Bookmarks & Collections API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from curiopilot.api.deps import get_url_store
from curiopilot.storage.url_store import URLStore

router = APIRouter(tags=["bookmarks"])


class BookmarkRequest(BaseModel):
    briefing_date: str
    article_number: int
    collection_id: int | None = None


class CollectionRequest(BaseModel):
    name: str


@router.get("/bookmarks")
async def list_bookmarks(
    collection_id: int | None = None,
    url_store: URLStore = Depends(get_url_store),
):
    return await url_store.list_bookmarks(collection_id)


@router.post("/bookmarks")
async def add_bookmark(
    body: BookmarkRequest,
    url_store: URLStore = Depends(get_url_store),
):
    bid = await url_store.add_bookmark(body.briefing_date, body.article_number, body.collection_id)
    return {"status": "bookmarked", "id": bid}


@router.delete("/bookmarks/{date}/{number}")
async def remove_bookmark(
    date: str,
    number: int,
    url_store: URLStore = Depends(get_url_store),
):
    await url_store.remove_bookmark(date, number)
    return {"status": "removed"}


@router.get("/bookmarks/check/{date}/{number}")
async def check_bookmark(
    date: str,
    number: int,
    url_store: URLStore = Depends(get_url_store),
):
    is_bm = await url_store.is_bookmarked(date, number)
    return {"bookmarked": is_bm}


@router.get("/collections")
async def list_collections(url_store: URLStore = Depends(get_url_store)):
    return await url_store.list_collections()


@router.post("/collections")
async def create_collection(
    body: CollectionRequest,
    url_store: URLStore = Depends(get_url_store),
):
    cid = await url_store.create_collection(body.name)
    return {"status": "created", "id": cid}


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: int,
    url_store: URLStore = Depends(get_url_store),
):
    await url_store.delete_collection(collection_id)
    return {"status": "deleted"}
