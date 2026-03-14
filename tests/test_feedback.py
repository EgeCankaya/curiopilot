"""Tests for briefing feedback parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from curiopilot.feedback import (
    _extract_article_metadata,
    _extract_feedback_section,
    has_feedback_section,
    parse_briefing_feedback,
)


SAMPLE_BRIEFING = """\
# CurioPilot Daily Briefing -- 2026-03-09

**Articles Scanned**: 100 | **Passed Relevance**: 10 | **In Briefing**: 3

---

## Top Articles

### 1. AI Agents Are Great
**Source**: HN | **Relevance**: 9/10 | **Novelty**: 80%

A summary of the article.

**Key Concepts**: `AI agents`, `LangGraph`, `MCP`

[Read original](http://example.com/1)

---

### 2. Multi-Agent Systems
**Source**: Reddit | **Relevance**: 8/10 | **Novelty**: 70%

Summary here.

**Key Concepts**: `multi-agent`, `orchestration`

[Read original](http://example.com/2)

---

### 3. Local LLMs
**Source**: ArXiv | **Relevance**: 7/10 | **Novelty**: 60%

Local LLM summary.

**Key Concepts**: `quantization`, `inference`

[Read original](http://example.com/3)

---

## Your Feedback
> Rate articles after reading.
> read: yes/no | interest: 1-5 | quality: like/dislike/broken

**1. AI Agents Are Great**
- 1: read=yes, interest=5/5, quality=like
**2. Multi-Agent Systems**
- 2: read=no, interest=, quality=
**3. Local LLMs**
- 3: read=yes, interest=3/5, quality=dislike
"""

BRIEFING_NO_FEEDBACK = """\
# CurioPilot Daily Briefing -- 2026-03-09

### 1. Some Article
**Key Concepts**: `AI`

No feedback section here.
"""


@pytest.fixture
def briefing_file(tmp_path: Path) -> Path:
    p = tmp_path / "2026-03-09.md"
    p.write_text(SAMPLE_BRIEFING, encoding="utf-8")
    return p


@pytest.fixture
def no_feedback_file(tmp_path: Path) -> Path:
    p = tmp_path / "2026-03-10.md"
    p.write_text(BRIEFING_NO_FEEDBACK, encoding="utf-8")
    return p


# ── parse_briefing_feedback ──────────────────────────────────────────────────


class TestParseBriefingFeedback:
    def test_with_sample_briefing(self, briefing_file: Path) -> None:
        entries = parse_briefing_feedback(briefing_file)
        assert len(entries) == 2  # articles 1 and 3 have feedback; 2 has nothing

        entry1 = next(e for e in entries if e.article_number == 1)
        assert entry1.read is True
        assert entry1.interest == 5
        assert entry1.quality == "like"
        assert entry1.title == "AI Agents Are Great"
        assert "AI agents" in entry1.concepts

        entry3 = next(e for e in entries if e.article_number == 3)
        assert entry3.read is True
        assert entry3.interest == 3
        assert entry3.quality == "dislike"

    def test_partial_feedback_read_only(self, tmp_path: Path) -> None:
        text = """\
# Briefing

### 1. Article One
**Key Concepts**: `topic`

## Your Feedback

- 1: read=yes, interest=, quality=
"""
        p = tmp_path / "partial.md"
        p.write_text(text, encoding="utf-8")
        entries = parse_briefing_feedback(p)
        assert len(entries) == 1
        assert entries[0].read is True
        assert entries[0].interest is None

    @pytest.mark.parametrize("val,expected", [
        ("y", True), ("Y", True), ("n", False), ("N", False),
        ("yes", True), ("no", False),
    ])
    def test_read_shorthand_y_n(self, tmp_path: Path, val: str, expected: bool) -> None:
        text = f"""\
# Briefing

### 1. Article One
**Key Concepts**: `topic`

## Your Feedback

- 1: read={val}, interest=, quality=
"""
        p = tmp_path / "shorthand.md"
        p.write_text(text, encoding="utf-8")
        entries = parse_briefing_feedback(p)
        if expected:
            assert len(entries) == 1
            assert entries[0].read is True
        else:
            assert len(entries) == 0 or entries[0].read is False

    def test_empty_feedback_section(self, tmp_path: Path) -> None:
        text = """\
# Briefing

### 1. Article One

## Your Feedback

"""
        p = tmp_path / "empty.md"
        p.write_text(text, encoding="utf-8")
        entries = parse_briefing_feedback(p)
        assert entries == []


# ── has_feedback_section ─────────────────────────────────────────────────────


class TestHasFeedbackSection:
    def test_true_for_sample(self, briefing_file: Path) -> None:
        assert has_feedback_section(briefing_file) is True

    def test_false_for_no_feedback(self, no_feedback_file: Path) -> None:
        assert has_feedback_section(no_feedback_file) is False


# ── _extract_article_metadata ────────────────────────────────────────────────


class TestExtractArticleMetadata:
    def test_parses_headings_and_concepts(self) -> None:
        lines = SAMPLE_BRIEFING.splitlines()
        articles = _extract_article_metadata(lines)
        assert 1 in articles
        assert articles[1]["title"] == "AI Agents Are Great"
        assert "AI agents" in articles[1]["concepts"]
        assert 2 in articles
        assert 3 in articles


# ── Edge cases ───────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_malformed_feedback_line_ignored(self, tmp_path: Path) -> None:
        text = """\
# Briefing

## Your Feedback

- not a valid line
- also invalid: blah
- 1: read=yes
"""
        p = tmp_path / "malformed.md"
        p.write_text(text, encoding="utf-8")
        entries = parse_briefing_feedback(p)
        assert len(entries) == 1
        assert entries[0].article_number == 1

    def test_out_of_range_interest_ignored(self, tmp_path: Path) -> None:
        text = """\
# Briefing

### 1. Article
**Key Concepts**: `AI`

## Your Feedback

- 1: read=yes, interest=99/5, quality=
"""
        p = tmp_path / "outrange.md"
        p.write_text(text, encoding="utf-8")
        entries = parse_briefing_feedback(p)
        assert len(entries) == 1
        assert entries[0].interest is None  # out of range should be rejected
