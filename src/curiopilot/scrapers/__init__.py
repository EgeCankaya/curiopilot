"""Scraper registry — maps config scraper names to classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curiopilot.config import SourceConfig
    from curiopilot.scrapers.base import BaseScraper

_REGISTRY: dict[str, type["BaseScraper"]] = {}


def register_scraper(name: str):
    """Class decorator that registers a scraper under *name*."""

    def decorator(cls: type["BaseScraper"]):
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_scraper(source: "SourceConfig") -> "BaseScraper":
    """Return an instantiated scraper for the given source config."""
    # Lazy-import concrete scrapers so they register themselves.
    import curiopilot.scrapers.arxiv_feed  # noqa: F401
    import curiopilot.scrapers.generic_scrape  # noqa: F401
    import curiopilot.scrapers.hackernews_api  # noqa: F401
    import curiopilot.scrapers.huggingface_scrape  # noqa: F401
    import curiopilot.scrapers.reddit_json  # noqa: F401

    cls = _REGISTRY.get(source.scraper)
    if cls is None:
        raise ValueError(
            f"No scraper registered for {source.scraper!r}. "
            f"Available: {sorted(_REGISTRY)}"
        )
    return cls(source)
