"""UI bridge routes — desktop-only actions exposed over HTTP."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(tags=["ui"])


class OpenReaderRequest(BaseModel):
    url: str
    title: str | None = None


class OpenReaderResponse(BaseModel):
    ok: bool
    opened: bool
    reason: str


@router.post("/ui/open-reader", response_model=OpenReaderResponse)
async def open_reader(body: OpenReaderRequest, request: Request):
    parsed = urlparse(body.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return OpenReaderResponse(ok=False, opened=False, reason="invalid_url")

    bridge = getattr(request.app.state, "ui_bridge", None)
    if bridge is None:
        return OpenReaderResponse(ok=True, opened=False, reason="bridge_unavailable")

    try:
        success, reason = bridge.open_reader(body.url, body.title)
        return OpenReaderResponse(ok=True, opened=success, reason=reason)
    except Exception:
        log.exception("ui_bridge.open_reader failed")
        return OpenReaderResponse(ok=True, opened=False, reason="reader_open_failed")
