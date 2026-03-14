"""Configuration loading and validation for CurioPilot."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

log = logging.getLogger(__name__)

KNOWN_SCRAPERS = {
    "hackernews_api",
    "reddit_json",
    "arxiv_feed",
    "huggingface_scrape",
    "generic_scrape",
}


# ── Section models ───────────────────────────────────────────────────────────


class InterestsConfig(BaseModel):
    primary: list[str] = Field(min_length=1)
    secondary: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)


class SourceConfig(BaseModel):
    name: str
    scraper: str
    url: str | None = None
    query: str | None = None
    max_articles: int = Field(default=30, ge=1)
    request_delay_seconds: float = Field(default=3.0, ge=0)

    @field_validator("scraper")
    @classmethod
    def _validate_scraper(cls, v: str) -> str:
        if v not in KNOWN_SCRAPERS:
            raise ValueError(
                f"Unknown scraper {v!r}. Choose from: {sorted(KNOWN_SCRAPERS)}"
            )
        return v


class ModelsConfig(BaseModel):
    filter_model: str = "qwen2.5:7b-instruct-q8_0"
    reader_model: str = "qwen2.5:14b-instruct-q4_K_M"
    embedding_model: str = "nomic-embed-text"


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = Field(default=120, ge=1)
    max_retries: int = Field(default=3, ge=0)


class ScoringConfig(BaseModel):
    relevance_threshold: int = Field(default=6, ge=0, le=10)
    novelty_weight: float = Field(default=0.6, ge=0, le=1)
    relevance_weight: float = Field(default=0.4, ge=0, le=1)
    min_briefing_items: int = Field(default=5, ge=0)
    max_briefing_items: int = Field(default=10, ge=1)
    near_duplicate_threshold: float = Field(default=0.92, ge=0, le=1)
    related_threshold: float = Field(default=0.75, ge=0, le=1)
    vector_novelty_weight: float = Field(default=0.5, ge=0, le=1)
    graph_novelty_weight: float = Field(default=0.5, ge=0, le=1)


class ChunkingConfig(BaseModel):
    max_tokens_per_chunk: int = Field(default=28000, ge=1000)


class PathsConfig(BaseModel):
    briefings_dir: str = "./briefings"
    database_dir: str = "./data"
    graph_path: str = "./data/knowledge_graph.json"

    def resolve(self, root: Path) -> PathsConfig:
        """Return a copy with paths resolved against *root*."""
        return self.model_copy(
            update={
                "briefings_dir": str((root / self.briefings_dir).resolve()),
                "database_dir": str((root / self.database_dir).resolve()),
                "graph_path": str((root / self.graph_path).resolve()),
            }
        )


# ── Root config ──────────────────────────────────────────────────────────────


CURRENT_CONFIG_VERSION = 1


class AppConfig(BaseModel):
    config_version: int = Field(default=CURRENT_CONFIG_VERSION)
    interests: InterestsConfig
    sources: list[SourceConfig] = Field(min_length=1)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    @field_validator("config_version")
    @classmethod
    def _check_version(cls, v: int) -> int:
        if v > CURRENT_CONFIG_VERSION:
            log.warning(
                "Config version %d is newer than supported version %d; "
                "some features may not work correctly",
                v, CURRENT_CONFIG_VERSION,
            )
        return v

    @model_validator(mode="after")
    def _check_weight_sums(self) -> "AppConfig":
        s = self.scoring
        total = s.novelty_weight + s.relevance_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"novelty_weight + relevance_weight should equal 1.0, got {total}"
            )
        total_n = s.vector_novelty_weight + s.graph_novelty_weight
        if abs(total_n - 1.0) > 0.01:
            raise ValueError(
                f"vector_novelty_weight + graph_novelty_weight should equal 1.0, got {total_n}"
            )
        return self


# ── Loader ───────────────────────────────────────────────────────────────────


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """Load and validate a YAML configuration file.

    Raises ``SystemExit`` with a human‑readable message on failure so that CLI
    callers get a clean error rather than a traceback.
    """
    config_path = Path(path)
    if not config_path.is_file():
        raise SystemExit(f"Config file not found: {config_path.resolve()}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SystemExit(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise SystemExit(f"Expected a YAML mapping in {config_path}, got {type(raw).__name__}")

    try:
        cfg = AppConfig.model_validate(raw)
    except Exception as exc:
        raise SystemExit(f"Config validation error: {exc}") from exc

    cfg.paths = cfg.paths.resolve(config_path.parent.resolve())
    log.info("Config loaded from %s", config_path)
    return cfg
