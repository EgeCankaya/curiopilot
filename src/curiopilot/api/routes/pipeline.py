"""Pipeline run API routes with SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from curiopilot.api.schemas import RunResponse, RunStatus

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
async def trigger_run(request: Request):
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
    asyncio.create_task(_execute_pipeline(config_path, run_id))

    return RunResponse(run_id=run_id, status="started")


async def _execute_pipeline(config_path: str, run_id: str) -> None:
    from curiopilot.pipeline.run import run_pipeline

    async with _run_lock:
        try:
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
            )

            _run_state["status"] = "completed"
            _broadcast_event("complete", {
                "run_id": run_id,
                "articles_scanned": result.articles_scanned,
                "articles_briefed": len(result.summaries),
                "duration": round(result.duration_seconds, 1),
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
