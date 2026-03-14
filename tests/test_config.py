"""Tests for config loading and validation."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from curiopilot.config import AppConfig, load_config


# ── Helpers ──────────────────────────────────────────────────────────────────

MINIMAL_YAML = dedent("""\
    interests:
      primary:
        - "AI agents"

    sources:
      - name: "Hacker News"
        scraper: "hackernews_api"
        max_articles: 10
""")

FULL_YAML = dedent("""\
    interests:
      primary:
        - "AI agents"
      secondary:
        - "local inference"
      excluded:
        - "crypto"

    sources:
      - name: "Hacker News"
        scraper: "hackernews_api"
        max_articles: 5
        request_delay_seconds: 1

    models:
      filter_model: "test-7b"
      reader_model: "test-14b"
      embedding_model: "test-embed"

    ollama:
      base_url: "http://127.0.0.1:11434"
      timeout_seconds: 60
      max_retries: 2

    scoring:
      relevance_threshold: 7
      novelty_weight: 0.5
      relevance_weight: 0.5
      max_briefing_items: 10
      vector_novelty_weight: 0.5
      graph_novelty_weight: 0.5

    paths:
      briefings_dir: "./out/briefings"
      database_dir: "./out/data"
""")


def _write_config(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ── Tests ────────────────────────────────────────────────────────────────────


def test_minimal_config(tmp_path: Path) -> None:
    cfg = load_config(_write_config(tmp_path, MINIMAL_YAML))
    assert len(cfg.sources) == 1
    assert cfg.sources[0].scraper == "hackernews_api"
    assert cfg.scoring.relevance_threshold == 6  # default


def test_full_config(tmp_path: Path) -> None:
    cfg = load_config(_write_config(tmp_path, FULL_YAML))
    assert cfg.models.filter_model == "test-7b"
    assert cfg.ollama.timeout_seconds == 60
    assert cfg.scoring.relevance_threshold == 7


def test_missing_interests(tmp_path: Path) -> None:
    bad = dedent("""\
        sources:
          - name: "X"
            scraper: "hackernews_api"
    """)
    with pytest.raises(SystemExit, match="(?i)validation"):
        load_config(_write_config(tmp_path, bad))


def test_unknown_scraper(tmp_path: Path) -> None:
    bad = dedent("""\
        interests:
          primary: ["AI"]
        sources:
          - name: "X"
            scraper: "does_not_exist"
    """)
    with pytest.raises(SystemExit, match="(?i)validation"):
        load_config(_write_config(tmp_path, bad))


def test_bad_weight_sum(tmp_path: Path) -> None:
    bad = dedent("""\
        interests:
          primary: ["AI"]
        sources:
          - name: "X"
            scraper: "hackernews_api"
        scoring:
          novelty_weight: 0.8
          relevance_weight: 0.8
    """)
    with pytest.raises(SystemExit, match="(?i)validation"):
        load_config(_write_config(tmp_path, bad))


def test_missing_file() -> None:
    with pytest.raises(SystemExit, match="(?i)not found"):
        load_config("/nonexistent/config.yaml")


def test_paths_resolved_relative_to_config_dir(tmp_path: Path) -> None:
    cfg = load_config(_write_config(tmp_path, MINIMAL_YAML))
    assert Path(cfg.paths.database_dir).is_absolute()
    assert str(tmp_path.resolve()) in cfg.paths.database_dir


def test_pydantic_roundtrip() -> None:
    """Ensure AppConfig can be serialized and deserialized."""
    raw = {
        "interests": {"primary": ["AI"]},
        "sources": [{"name": "HN", "scraper": "hackernews_api"}],
    }
    cfg = AppConfig.model_validate(raw)
    dumped = cfg.model_dump()
    cfg2 = AppConfig.model_validate(dumped)
    assert cfg2.interests.primary == cfg.interests.primary
