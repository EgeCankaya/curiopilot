"""Source management API routes — includes OPML import."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Request, UploadFile

from curiopilot.api.deps import get_config
from curiopilot.api.schemas import ImportedSource, OPMLImportResponse
from curiopilot.config import AppConfig

router = APIRouter(tags=["sources"])
log = logging.getLogger(__name__)


@router.post("/sources/import-opml", response_model=OPMLImportResponse)
async def import_opml(file: UploadFile, request: Request):
    """Import RSS feed sources from an OPML file.

    Parses the uploaded OPML/XML file, extracts feed URLs from
    ``<outline>`` elements with ``xmlUrl`` attributes, and creates
    ``generic_scrape`` source entries in config.yaml.
    """
    config = request.app.state.config
    config_path = Path(request.app.state.config_path)

    # Read and parse OPML
    try:
        content = await file.read()
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid OPML/XML: {exc}")

    # Collect existing source URLs for dedup
    existing_urls = {s.url for s in config.sources if s.url}

    added: list[ImportedSource] = []
    skipped: list[ImportedSource] = []

    # Walk all <outline> elements with xmlUrl (feed URL)
    for outline in root.iter("outline"):
        xml_url = outline.get("xmlUrl")
        if not xml_url:
            continue

        name = outline.get("text") or outline.get("title") or xml_url
        source_info = ImportedSource(name=name, url=xml_url)

        if xml_url in existing_urls:
            skipped.append(source_info)
            continue

        existing_urls.add(xml_url)
        added.append(source_info)

    if not added:
        return OPMLImportResponse(added=[], skipped_duplicates=skipped)

    # Read raw config, add new sources, validate, write back
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {exc}")

    if "sources" not in raw:
        raw["sources"] = []

    for source in added:
        raw["sources"].append({
            "name": source.name,
            "scraper": "generic_scrape",
            "url": source.url,
            "max_articles": 15,
        })

    # Validate merged config
    try:
        new_config = AppConfig.model_validate(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Config validation failed: {exc}")

    # Write config
    try:
        config_path.write_text(
            yaml.safe_dump(raw, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="No write permission to config file")

    # Reload in app state
    request.app.state.config = new_config
    log.info("OPML import: added %d sources, skipped %d duplicates", len(added), len(skipped))

    return OPMLImportResponse(added=added, skipped_duplicates=skipped)
