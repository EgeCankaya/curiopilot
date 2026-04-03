"""Pipeline run API routes with SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from curiopilot.api.schemas import DLQItem, DLQStats, RunRequest, RunResponse, RunStatus

router = APIRouter(tags=["pipeline"])
log = logging.getLogger(__name__)

_run_lock = asyncio.Lock()
_run_state: dict = {"status": "idle", "run_id": None, "error": None}
_event_queues: list[asyncio.Queue] = []


def _broadcast_event(event_type: str, data: dict) -> None:
    for q in _event_queues:
        try:
            q.put_nowait({"event": event_type, "data": data})
        except asyncio.QueueFull:
            pass


@router.post("/run", response_model=RunResponse)
async def trigger_run(request: Request, body: RunRequest | None = None):
    if _run_lock.locked():
        return JSONResponse(
            status_code=409,
            content={"detail": "A pipeline run is already in progress"},
        )

    run_id = uuid.uuid4().hex[:12]
    _run_state["status"] = "running"
    _run_state["run_id"] = run_id
    _run_state["error"] = None

    config_path = request.app.state.config_path
    incremental = body.incremental if body else False
    resume_run_id = body.resume_run_id if body else None
    rerun_date = body.rerun_date if body else None

    asyncio.create_task(_execute_pipeline(
        config_path, run_id,
        incremental=incremental,
        resume_run_id=resume_run_id,
        rerun_date=rerun_date,
    ))

    return RunResponse(run_id=run_id, status="started")


async def _execute_pipeline(
    config_path: str,
    run_id: str,
    *,
    incremental: bool = False,
    resume_run_id: str | None = None,
    rerun_date: str | None = None,
) -> None:
    from curiopilot.config import load_config
    from curiopilot.pipeline.run import run_pipeline
    from curiopilot.storage.article_store import ArticleStore
    from curiopilot.storage.url_store import URLStore

    async with _run_lock:
        try:
            if rerun_date:
                config = load_config(config_path)
                db_path = Path(config.paths.database_dir) / "curiopilot.db"

                article_store = ArticleStore(db_path)
                await article_store.open()
                try:
                    deleted = await article_store.delete_articles_by_date(rerun_date)
                    log.info("Re-run: deleted %d article(s) for %s", deleted, rerun_date)
                finally:
                    await article_store.close()

                url_store = URLStore(db_path)
                await url_store.open()
                try:
                    await url_store.clear_date_data(rerun_date)
                    log.info("Re-run: cleared visited URLs and feedback for %s", rerun_date)
                finally:
                    await url_store.close()

                briefing_file = Path(config.paths.briefings_dir) / f"{rerun_date}.md"
                if briefing_file.exists():
                    briefing_file.unlink()
                    log.info("Re-run: deleted briefing file %s", briefing_file)

            def _progress_cb(phase: str, current: int, total: int) -> None:
                _broadcast_event("progress", {
                    "phase": phase,
                    "current": current,
                    "total": total,
                })

            _broadcast_event("started", {"run_id": run_id})
            result = await run_pipeline(
                config_path=config_path,
                progress_callback=_progress_cb,
                incremental=incremental,
                resume_run_id=resume_run_id,
            )

            _run_state["status"] = "completed"
            _broadcast_event("complete", {
                "run_id": run_id,
                "articles_scanned": result.articles_scanned,
                "articles_briefed": len(result.summaries),
                "duration": round(result.duration_seconds, 1),
                "dlq_failures": len(result.dlq_failures),
            })

        except Exception as exc:
            log.error("Pipeline run failed: %s", exc, exc_info=True)
            _run_state["status"] = "failed"
            _run_state["error"] = str(exc)
            _broadcast_event("error", {"run_id": run_id, "error": str(exc)})

        finally:
            if _run_state["status"] == "running":
                _run_state["status"] = "idle"


@router.get("/run/status", response_model=RunStatus)
async def run_status():
    return RunStatus(
        status=_run_state["status"],
        run_id=_run_state["run_id"],
        error=_run_state["error"],
    )


@router.get("/run/stream")
async def run_stream(request: Request):
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _event_queues.append(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = event["event"]
                    data = json.dumps(event["data"])
                    yield f"event: {event_type}\ndata: {data}\n\n"
                    if event_type in ("complete", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if queue in _event_queues:
                _event_queues.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ── Dead Letter Queue endpoints ─────────────────────────────────────────────


@router.get("/dlq", response_model=list[DLQItem])
async def list_dlq(request: Request):
    """List pending items in the dead letter queue."""
    from curiopilot.config import load_config
    from curiopilot.storage.url_store import URLStore

    config = load_config(request.app.state.config_path)
    db_path = Path(config.paths.database_dir) / "curiopilot.db"
    store = URLStore(db_path)
    await store.open()
    try:
        items = await store.get_dlq_pending()
        return [DLQItem(**item) for item in items]
    finally:
        await store.close()


@router.get("/dlq/stats", response_model=DLQStats)
async def dlq_stats(request: Request):
    """Get aggregate statistics about the dead letter queue."""
    from curiopilot.config import load_config
    from curiopilot.storage.url_store import URLStore

    config = load_config(request.app.state.config_path)
    db_path = Path(config.paths.database_dir) / "curiopilot.db"
    store = URLStore(db_path)
    await store.open()
    try:
        stats = await store.dlq_stats()
        return DLQStats(**stats)
    finally:
        await store.close()


@router.delete("/dlq/{url:path}")
async def remove_dlq_item(url: str, request: Request):
    """Remove a specific URL from the dead letter queue."""
    from curiopilot.config import load_config
    from curiopilot.storage.url_store import URLStore

    config = load_config(request.app.state.config_path)
    db_path = Path(config.paths.database_dir) / "curiopilot.db"
    store = URLStore(db_path)
    await store.open()
    try:
        await store.remove_from_dlq(url)
        return {"status": "removed", "url": url}
    finally:
        await store.close()


@router.delete("/dlq")
async def clear_dlq(request: Request):
    """Clear all items from the dead letter queue."""
    from curiopilot.config import load_config
    from curiopilot.storage.url_store import URLStore

    config = load_config(request.app.state.config_path)
    db_path = Path(config.paths.database_dir) / "curiopilot.db"
    store = URLStore(db_path)
    await store.open()
    try:
        await store.clear_dlq()
        return {"status": "cleared"}
    finally:
        await store.close()
