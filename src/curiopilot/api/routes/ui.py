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


@router.post("/ui/open-reader", response_model=OpenReaderResponse)
async def open_reader(body: OpenReaderRequest, request: Request):
    parsed = urlparse(body.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return OpenReaderResponse(ok=False, opened=False)

    bridge = getattr(request.app.state, "ui_bridge", None)
    if bridge is None:
        return OpenReaderResponse(ok=True, opened=False)

    try:
        opened = bool(bridge.open_reader(body.url, body.title))
        return OpenReaderResponse(ok=True, opened=opened)
    except Exception:
        log.exception("ui_bridge.open_reader failed")
        return OpenReaderResponse(ok=True, opened=False)
