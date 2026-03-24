"""Configuration API routes for settings management."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from curiopilot.api.deps import get_config

router = APIRouter(tags=["config"])
log = logging.getLogger(__name__)


@router.get("/config")
async def get_configuration(config=Depends(get_config)):
    """Return the current app configuration (excluding paths for safety)."""
    data = config.model_dump()
    data.pop("paths", None)
    return data


@router.put("/config")
async def update_configuration(body: dict, request: Request):
    """Apply a partial config update. Validates and writes to config.yaml."""
    from curiopilot.config import AppConfig

    config_path = Path(request.app.state.config_path)

    # Read current config
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {exc}")

    # Don't allow path changes via API
    body.pop("paths", None)
    body.pop("config_version", None)

    # Deep merge
    _deep_merge(raw, body)

    # Validate
    try:
        new_config = AppConfig.model_validate(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Write back
    try:
        config_path.write_text(
            yaml.safe_dump(raw, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="No write permission to config file")

    # Reload in app state
    request.app.state.config = new_config

    return {"status": "updated"}


@router.get("/config/models")
async def list_available_models(config=Depends(get_config)):
    """List available Ollama models."""
    base_url = config.ollama.base_url
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [
                {
                    "name": m["name"],
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                }
                for m in data.get("models", [])
            ]
            return {"models": models}
    except Exception as exc:
        log.warning("Failed to list Ollama models: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": f"Ollama unreachable: {exc}", "models": []},
        )


def _deep_merge(base: dict, updates: dict) -> None:
    """Recursively merge updates into base dict."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
