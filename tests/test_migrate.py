"""Tests for the briefing migration tool."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from curiopilot.migrate import ParsedArticle, migrate_briefings, parse_briefing
from curiopilot.storage.article_store import ArticleStore

_MINIMAL_BRIEFING = """\
# CurioPilot Daily Briefing -- 2026-03-20

**Articles Scanned**: 50 | **Passed Relevance**: 3 | **In Briefing**: 2
**Pipeline Runtime**: 5m 0s

---

## Top Articles

### 1. Test Article Alpha
**Source**: Hacker News | **Relevance**: 8/10 | **Novelty**: 75%
**Why it is new to you**: Introduces concepts not yet in your knowledge graph (graph novelty 80%)

This is the summary of the first article about interesting AI developments.

**Novel insights**: First article has novel insights about graph architectures.

**Key Concepts**: `concept-a`, `concept-b`, `concept-c`
**Related Topics**: topic-x, topic-y

[Read original](https://example.com/article-1)

---

### 2. Second Article Beta
**Source**: r/LocalLLaMA | **Relevance**: 6/10 | **Novelty**: 50%

A summary of the second article discussing model optimization techniques.

**Novel insights**: Second article reveals new optimization patterns.

**Key Concepts**: `concept-d`
**Related Topics**: topic-z

[Read original](https://example.com/article-2)

---

## Knowledge Graph Update
- **Nodes added**: 4 (concept-a, concept-b, concept-c, concept-d)
- **Edges added**: 6
- **Total knowledge nodes**: 50

## Your Feedback
> Rate articles after reading.

**1. Test Article Alpha**
- 1: read=, interest=, quality=
**2. Second Article Beta**
- 2: read=, interest=, quality=
"""

_EMPTY_BRIEFING = """\
# CurioPilot Daily Briefing -- 2026-03-21

**Articles Scanned**: 30 | **Passed Relevance**: 0 | **In Briefing**: 0
**Pipeline Runtime**: 2m 0s

---

*No articles to include in today's briefing.*
"""

_DEEPENING_BRIEFING = """\
# CurioPilot Daily Briefing -- 2026-03-22

**Articles Scanned**: 60 | **Passed Relevance**: 3 | **In Briefing**: 2
**Pipeline Runtime**: 8m 0s

---

## Top Articles

### 1. Novel Article
**Source**: ArXiv AI | **Relevance**: 9/10 | **Novelty**: 95%
**Why it is new to you**: Introduces concepts not yet in your knowledge graph (graph novelty 90%)

A groundbreaking paper on novel architectures.

**Novel insights**: Completely new approach to transformer design.

**Key Concepts**: `new-concept`
**Related Topics**: transformers

[Read original](https://example.com/novel)

---

## Deepening
> Articles on topics you know, but with a new angle.

### 2. Deeper Dive on Known Topic
**What you already know**: You have encountered `known-concept-a`, `known-concept-b` before.
**What is new here**: A fresh perspective on applying known-concept-a to edge devices.

[Read original](https://example.com/deepening)

---

## Knowledge Graph Update
- **Nodes added**: 1
- **Edges added**: 2
- **Total knowledge nodes**: 55
"""


class TestParseBriefing:
    def test_parses_minimal_briefing(self) -> None:
        articles = parse_briefing(_MINIMAL_BRIEFING)
        assert len(articles) == 2

    def test_article_fields(self) -> None:
        articles = parse_briefing(_MINIMAL_BRIEFING)
        a1 = articles[0]
        assert a1.article_number == 1
        assert a1.title == "Test Article Alpha"
        assert a1.source_name == "Hacker News"
        assert a1.relevance_score == 8
        assert a1.novelty_pct == 75
        assert "graph novelty 80%" in a1.novelty_explanation
        assert "summary" in a1.summary.lower() or "interesting" in a1.summary.lower()
        assert a1.novel_insights == "First article has novel insights about graph architectures."
        assert a1.key_concepts == ["concept-a", "concept-b", "concept-c"]
        assert a1.related_topics == ["topic-x", "topic-y"]
        assert a1.url == "https://example.com/article-1"
        assert a1.is_deepening is False

    def test_second_article_no_novelty_explanation(self) -> None:
        articles = parse_briefing(_MINIMAL_BRIEFING)
        a2 = articles[1]
        assert a2.article_number == 2
        assert a2.title == "Second Article Beta"
        assert a2.novelty_explanation == ""
        assert a2.url == "https://example.com/article-2"

    def test_empty_briefing(self) -> None:
        articles = parse_briefing(_EMPTY_BRIEFING)
        assert articles == []

    def test_deepening_section(self) -> None:
        articles = parse_briefing(_DEEPENING_BRIEFING)
        assert len(articles) == 2
        novel = articles[0]
        deep = articles[1]
        assert novel.is_deepening is False
        assert novel.title == "Novel Article"
        assert deep.is_deepening is True
        assert deep.title == "Deeper Dive on Known Topic"
        assert deep.novel_insights == "A fresh perspective on applying known-concept-a to edge devices."
        assert deep.url == "https://example.com/deepening"


class TestParseBriefingRealFiles:
    """Test the parser against actual briefing files from the project."""

    def test_parse_2026_03_14(self) -> None:
        path = Path(__file__).parent.parent / "briefings" / "2026-03-14.md"
        if not path.exists():
            pytest.skip("Briefing file not found")
        text = path.read_text(encoding="utf-8")
        articles = parse_briefing(text)
        assert len(articles) == 5
        assert articles[0].title == "How to fix prompt reprocessing in qwen3.5 models (instruct mode only)"
        assert articles[0].source_name == "r/LocalLLaMA"
        assert articles[0].relevance_score == 7
        assert articles[0].novelty_pct == 90
        assert articles[0].url.startswith("https://www.reddit.com/")
        assert len(articles[0].key_concepts) == 3

    def test_parse_2026_03_10(self) -> None:
        path = Path(__file__).parent.parent / "briefings" / "2026-03-10.md"
        if not path.exists():
            pytest.skip("Briefing file not found")
        text = path.read_text(encoding="utf-8")
        articles = parse_briefing(text)
        assert len(articles) == 9
        assert articles[0].article_number == 1
        assert articles[8].article_number == 9


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    s = ArticleStore(tmp_path / "test.db")
    await s.open()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_migrate_briefings(store: ArticleStore, tmp_path: Path) -> None:
    briefings_dir = tmp_path / "briefings"
    briefings_dir.mkdir()
    (briefings_dir / "2026-03-20.md").write_text(_MINIMAL_BRIEFING, encoding="utf-8")

    migrated = await migrate_briefings(briefings_dir, store)
    assert "2026-03-20" in migrated
    assert migrated["2026-03-20"] == 2

    articles = await store.get_articles_by_date("2026-03-20")
    assert len(articles) == 2
    assert articles[0]["title"] == "Test Article Alpha"


@pytest.mark.asyncio
async def test_migrate_idempotent(store: ArticleStore, tmp_path: Path) -> None:
    briefings_dir = tmp_path / "briefings"
    briefings_dir.mkdir()
    (briefings_dir / "2026-03-20.md").write_text(_MINIMAL_BRIEFING, encoding="utf-8")

    first = await migrate_briefings(briefings_dir, store)
    assert len(first) == 1

    second = await migrate_briefings(briefings_dir, store)
    assert len(second) == 0

    articles = await store.get_articles_by_date("2026-03-20")
    assert len(articles) == 2


@pytest.mark.asyncio
async def test_migrate_empty_briefing(store: ArticleStore, tmp_path: Path) -> None:
    briefings_dir = tmp_path / "briefings"
    briefings_dir.mkdir()
    (briefings_dir / "2026-03-21.md").write_text(_EMPTY_BRIEFING, encoding="utf-8")

    migrated = await migrate_briefings(briefings_dir, store)
    assert len(migrated) == 0


@pytest.mark.asyncio
async def test_migrate_nonexistent_dir(store: ArticleStore, tmp_path: Path) -> None:
    migrated = await migrate_briefings(tmp_path / "nope", store)
    assert migrated == {}
