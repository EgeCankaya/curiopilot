"""Obsidian vault integration endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from curiopilot.api.schemas import ObsidianExportResponse, ObsidianStatusResponse
from curiopilot.export.obsidian import export_obsidian_vault
from curiopilot.storage.knowledge_graph import KnowledgeGraph

log = logging.getLogger(__name__)

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


class ExportRequest(BaseModel):
    vault_path: str | None = None


@router.get("/status", response_model=ObsidianStatusResponse)
async def obsidian_status(request: Request) -> ObsidianStatusResponse:
    """Return current Obsidian vault status and category breakdown."""
    config = request.app.state.config
    vault_path = config.paths.obsidian_vault_path

    kg = KnowledgeGraph(config.paths.graph_path)
    kg.load()

    # Count briefings
    briefings_dir = Path(config.paths.briefings_dir)
    total_briefings = len(list(briefings_dir.glob("*.md"))) if briefings_dir.is_dir() else 0

    # Check last export time from Knowledge Graph.md mtime
    last_exported: str | None = None
    if vault_path:
        index_file = Path(vault_path) / "Knowledge Graph.md"
        if index_file.is_file():
            mtime = index_file.stat().st_mtime
            last_exported = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    return ObsidianStatusResponse(
        vault_path=vault_path,
        configured=bool(vault_path),
        total_concepts=kg.node_count(),
        total_briefings=total_briefings,
        category_summary=kg.category_summary(),
        last_exported=last_exported,
    )


@router.post("/export", response_model=ObsidianExportResponse)
async def obsidian_export(request: Request, body: ExportRequest | None = None) -> ObsidianExportResponse:
    """Trigger an Obsidian vault export. Optionally override vault_path."""
    config = request.app.state.config

    vault_path = (body.vault_path if body and body.vault_path else None) or config.paths.obsidian_vault_path
    if not vault_path:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No vault path configured. Set obsidian_vault_path in config or provide vault_path in request.")

    # Update config with new vault path if provided
    if body and body.vault_path:
        config.paths.obsidian_vault_path = body.vault_path

    kg = KnowledgeGraph(config.paths.graph_path)
    kg.load()

    briefings_dir = Path(config.paths.briefings_dir)
    total_briefings = len(list(briefings_dir.glob("*.md"))) if briefings_dir.is_dir() else 0

    exported_concepts = export_obsidian_vault(kg, briefings_dir, vault_path)

    return ObsidianExportResponse(
        exported_concepts=exported_concepts,
        exported_briefings=total_briefings,
        vault_path=vault_path,
    )
