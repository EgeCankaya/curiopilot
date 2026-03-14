"""Abstract base class for all CurioPilot scrapers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curiopilot.config import SourceConfig
    from curiopilot.models import ArticleEntry


class BaseScraper(ABC):
    """Every scraper receives its ``SourceConfig`` at init time."""

    def __init__(self, source: "SourceConfig") -> None:
        self.source = source

    @abstractmethod
    async def extract_articles(self) -> list["ArticleEntry"]:
        """Fetch and return article entries from this source."""
        ...
