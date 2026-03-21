"""Tests for the pipeline run API endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from curiopilot.storage.article_store import ArticleStore
from curiopilot.storage.url_store import URLStore


@pytest.fixture
def client(tmp_path: Path):
    """Create a TestClient with a minimal test database."""
    import asyncio

    db_path = tmp_path / "curiopilot.db"

    async def _setup():
        article_store = ArticleStore(db_path)
        await article_store.open()
        await article_store.close()
        url_store = URLStore(db_path)
        await url_store.open()
        await url_store.close()

    asyncio.run(_setup())

    config_file = tmp_path / "config.yaml"
    db_dir = str(tmp_path).replace("\\", "/")
    briefings = str(tmp_path / "briefings").replace("\\", "/")
    graph = str(tmp_path / "graph.json").replace("\\", "/")
    config_file.write_text(
        f"interests:\n  primary:\n    - AI\n"
        f"sources:\n  - name: Test\n    scraper: hackernews_api\n"
        f"paths:\n"
        f"  database_dir: {db_dir}\n"
        f"  briefings_dir: {briefings}\n"
        f"  graph_path: {graph}\n",
        encoding="utf-8",
    )
    (tmp_path / "briefings").mkdir(exist_ok=True)

    from curiopilot.api.app import create_app
    app = create_app(config_path=str(config_file))
    with TestClient(app) as c:
        yield c


class TestRunStatus:
    def test_initial_status_idle(self, client: TestClient) -> None:
        resp = client.get("/api/run/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("idle", "completed", "failed")


class TestRunTrigger:
    def test_trigger_returns_started(self, client: TestClient) -> None:
        from unittest.mock import AsyncMock, patch

        mock_result = AsyncMock()
        mock_result.articles_scanned = 0
        mock_result.summaries = []
        mock_result.duration_seconds = 1.0

        with patch("curiopilot.pipeline.run.run_pipeline", new=AsyncMock(return_value=mock_result)) as mock_run:
            resp = client.post("/api/run")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "started"
            assert "run_id" in data
