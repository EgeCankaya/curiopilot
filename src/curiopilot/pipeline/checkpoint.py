"""Pipeline checkpoint store — saves/loads phase results for resume support."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

log = logging.getLogger(__name__)


def _serialize(obj: Any) -> Any:
    """Recursively convert Pydantic models, dataclasses, and Paths to dicts."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    return obj


class CheckpointStore:
    """File-based checkpoint store for pipeline resume support.

    Each phase's output is saved as a JSON file under
    ``{checkpoint_dir}/{run_id}/{phase}.json``. Only serializable data
    fields are stored — runtime objects like clients and stores are
    reconstructed on resume.
    """

    def __init__(self, checkpoint_dir: Path, run_id: str) -> None:
        self._dir = checkpoint_dir / run_id
        self._run_id = run_id

    async def save(self, phase: str, state_data: dict) -> None:
        """Persist the result dict from a phase node."""
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{phase}.json"

        # Filter out non-serializable values (objects, callables, connections)
        serializable = {}
        for key, value in state_data.items():
            try:
                converted = _serialize(value)
                json.dumps(converted)  # Test serializability
                serializable[key] = converted
            except (TypeError, ValueError, OverflowError):
                log.debug("Skipping non-serializable key '%s' in checkpoint for phase '%s'", key, phase)

        path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        log.debug("Checkpoint saved: %s", path)

    async def load(self, phase: str) -> dict | None:
        """Load checkpoint data for a phase, or None if not found."""
        path = self._dir / f"{phase}.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to load checkpoint %s: %s", path, exc)
            return None

    async def get_last_completed_phase(self) -> str | None:
        """Return the name of the last phase that has a checkpoint file."""
        from curiopilot.pipeline.graph import PHASE_ORDER

        if not self._dir.is_dir():
            return None

        last = None
        for phase in PHASE_ORDER:
            if (self._dir / f"{phase}.json").is_file():
                last = phase
        return last

    async def get_completed_phases(self) -> list[str]:
        """Return all phases that have checkpoint files, in order."""
        from curiopilot.pipeline.graph import PHASE_ORDER

        if not self._dir.is_dir():
            return []

        return [p for p in PHASE_ORDER if (self._dir / f"{p}.json").is_file()]

    async def load_all(self) -> dict:
        """Load and merge all checkpoint data into a single dict."""
        merged: dict = {}
        for phase in await self.get_completed_phases():
            data = await self.load(phase)
            if data:
                merged.update(data)
        return merged

    async def clear(self) -> None:
        """Remove all checkpoint files for this run."""
        if self._dir.is_dir():
            for f in self._dir.iterdir():
                f.unlink(missing_ok=True)
            self._dir.rmdir()
            log.info("Cleared checkpoints for run %s", self._run_id)
