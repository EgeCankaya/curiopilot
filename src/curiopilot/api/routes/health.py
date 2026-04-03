"""Health check endpoint."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str
    ollama: str
    briefings_count: int = 0


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Return health status of backend services."""
    db_status = "ok"
    ollama_status = "unknown"
    briefings_count = 0

    # Check database
    try:
        store = request.app.state.article_store
        await store._db.execute("SELECT 1")
    except Exception:
        db_status = "unavailable"

    # Check Ollama
    try:
        import httpx

        config = request.app.state.config
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{config.ollama.base_url}/api/tags")
            ollama_status = "ok" if resp.status_code == 200 else "unavailable"
    except Exception:
        ollama_status = "unavailable"

    # Count briefings
    try:
        config = request.app.state.config
        briefings_dir = Path(config.paths.briefings_dir)
        if briefings_dir.is_dir():
            briefings_count = len(list(briefings_dir.glob("*.md")))
    except Exception:
        pass

    overall = "ok" if db_status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        database=db_status,
        ollama=ollama_status,
        briefings_count=briefings_count,
    )
