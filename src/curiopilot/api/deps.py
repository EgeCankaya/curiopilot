"""FastAPI dependency injection -- retrieves store singletons from app.state."""

from __future__ import annotations

from fastapi import Request

from curiopilot.storage.article_store import ArticleStore
from curiopilot.storage.url_store import URLStore


def get_article_store(request: Request) -> ArticleStore:
    return request.app.state.article_store


def get_url_store(request: Request) -> URLStore:
    return request.app.state.url_store


def get_config(request: Request):
    return request.app.state.config
