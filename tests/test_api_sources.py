"""Tests for the OPML import API endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient


_SAMPLE_OPML = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>My Feeds</title></head>
  <body>
    <outline text="Tech" title="Tech">
      <outline text="Hacker News" xmlUrl="https://hnrss.org/frontpage" htmlUrl="https://news.ycombinator.com" />
      <outline text="Lobsters" xmlUrl="https://lobste.rs/rss" htmlUrl="https://lobste.rs" />
    </outline>
    <outline text="AI Blogs">
      <outline text="Lilian Weng" xmlUrl="https://lilianweng.github.io/index.xml" htmlUrl="https://lilianweng.github.io" />
    </outline>
  </body>
</opml>
"""

_INVALID_XML = "<not valid <xml"


@pytest.fixture
def client(tmp_path: Path):
    """Create a TestClient with a minimal config."""
    import asyncio

    from curiopilot.storage.article_store import ArticleStore
    from curiopilot.storage.url_store import URLStore

    db_path = tmp_path / "curiopilot.db"

    async def _setup():
        store = ArticleStore(db_path)
        await store.open()
        await store.close()
        url_store = URLStore(db_path)
        await url_store.open()
        await url_store.close()

    asyncio.run(_setup())

    config_file = tmp_path / "config.yaml"
    db_parent = str(db_path.parent).replace("\\", "/")
    briefings = str(tmp_path / "briefings").replace("\\", "/")
    graph = str(tmp_path / "graph.json").replace("\\", "/")
    config_file.write_text(
        f"interests:\n  primary:\n    - AI\n"
        f"sources:\n  - name: Test\n    scraper: hackernews_api\n"
        f"paths:\n"
        f"  database_dir: {db_parent}\n"
        f"  briefings_dir: {briefings}\n"
        f"  graph_path: {graph}\n",
        encoding="utf-8",
    )
    (tmp_path / "briefings").mkdir(exist_ok=True)

    from curiopilot.api.app import create_app

    app = create_app(config_path=str(config_file))
    with TestClient(app) as c:
        yield c


class TestOPMLImport:
    def test_import_opml_adds_sources(self, client: TestClient) -> None:
        resp = client.post(
            "/api/sources/import-opml",
            files={"file": ("feeds.opml", _SAMPLE_OPML, "application/xml")},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["added"]) == 3
        assert len(data["skipped_duplicates"]) == 0

        # Verify names
        names = {s["name"] for s in data["added"]}
        assert "Hacker News" in names
        assert "Lobsters" in names
        assert "Lilian Weng" in names

        # Verify config was actually updated
        config_resp = client.get("/api/config")
        sources = config_resp.json()["sources"]
        urls = {s["url"] for s in sources if s.get("url")}
        assert "https://hnrss.org/frontpage" in urls
        assert "https://lobste.rs/rss" in urls
        assert "https://lilianweng.github.io/index.xml" in urls

    def test_import_deduplicates(self, client: TestClient) -> None:
        # Import once
        client.post(
            "/api/sources/import-opml",
            files={"file": ("feeds.opml", _SAMPLE_OPML, "application/xml")},
        )

        # Import again — should all be duplicates
        resp = client.post(
            "/api/sources/import-opml",
            files={"file": ("feeds.opml", _SAMPLE_OPML, "application/xml")},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["added"]) == 0
        assert len(data["skipped_duplicates"]) == 3

    def test_import_invalid_xml(self, client: TestClient) -> None:
        resp = client.post(
            "/api/sources/import-opml",
            files={"file": ("bad.opml", _INVALID_XML, "application/xml")},
        )

        assert resp.status_code == 422
        assert "Invalid OPML/XML" in resp.json()["detail"]

    def test_import_empty_opml(self, client: TestClient) -> None:
        empty_opml = '<?xml version="1.0"?><opml><body></body></opml>'
        resp = client.post(
            "/api/sources/import-opml",
            files={"file": ("empty.opml", empty_opml, "application/xml")},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["added"]) == 0
        assert len(data["skipped_duplicates"]) == 0
