"""Parse user feedback from briefing Markdown files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_FEEDBACK_LINE = re.compile(
    r"^-\s*(\d+)\s*:\s*(.*)$"
)
_KV_PAIR = re.compile(r"(\w+)\s*=\s*([^,]*)")
_ARTICLE_HEADING = re.compile(r"^###\s+(\d+)\.\s+(.+)$")
_KEY_CONCEPTS = re.compile(r"^\*\*Key Concepts\*\*:\s*(.+)$")
_CONCEPT_TICK = re.compile(r"`([^`]+)`")


@dataclass
class ArticleFeedback:
    """Parsed feedback for a single article in a briefing."""

    article_number: int
    title: str = ""
    concepts: list[str] = field(default_factory=list)
    read: bool = False
    interest: int | None = None
    quality: str | None = None  # "like", "dislike", "broken", or None

    @property
    def has_feedback(self) -> bool:
        return self.read or self.interest is not None or self.quality is not None


def parse_briefing_feedback(path: Path) -> list[ArticleFeedback]:
    """Parse a briefing .md file and return feedback entries that have data.

    Returns only articles where the user filled in at least one field.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    articles = _extract_article_metadata(lines)
    feedback_map = _extract_feedback_section(lines)

    results: list[ArticleFeedback] = []
    for num, fb_fields in feedback_map.items():
        meta = articles.get(num, {})
        af = ArticleFeedback(
            article_number=num,
            title=meta.get("title", ""),
            concepts=meta.get("concepts", []),
            read=fb_fields.get("read", False),
            interest=fb_fields.get("interest"),
            quality=fb_fields.get("quality"),
        )
        if af.has_feedback:
            results.append(af)

    return results


def has_feedback_section(path: Path) -> bool:
    """Check whether a briefing file contains a 'Your Feedback' section."""
    text = path.read_text(encoding="utf-8")
    return "## Your Feedback" in text


def _extract_article_metadata(lines: list[str]) -> dict[int, dict]:
    """Extract article number -> {title, concepts} from headings and Key Concepts lines."""
    articles: dict[int, dict] = {}
    current_num: int | None = None

    for line in lines:
        heading_match = _ARTICLE_HEADING.match(line)
        if heading_match:
            current_num = int(heading_match.group(1))
            articles[current_num] = {
                "title": heading_match.group(2).strip(),
                "concepts": [],
            }
            continue

        if current_num is not None:
            concepts_match = _KEY_CONCEPTS.match(line)
            if concepts_match:
                raw = concepts_match.group(1)
                articles[current_num]["concepts"] = _CONCEPT_TICK.findall(raw)

    return articles


def _extract_feedback_section(lines: list[str]) -> dict[int, dict]:
    """Extract the 'Your Feedback' section and parse each line."""
    in_feedback = False
    feedback: dict[int, dict] = {}

    for line in lines:
        if line.strip() == "## Your Feedback":
            in_feedback = True
            continue

        if in_feedback and line.startswith("## "):
            break

        if not in_feedback:
            continue

        m = _FEEDBACK_LINE.match(line.strip())
        if not m:
            continue

        num = int(m.group(1))
        rest = m.group(2).strip()
        fields: dict = {"read": False, "interest": None, "quality": None}

        for key, val in _KV_PAIR.findall(rest):
            val = val.strip()
            if not val:
                continue
            key = key.lower()
            if key == "read":
                fields["read"] = val.lower() in ("yes", "y", "true", "1", "x")
            elif key == "interest":
                try:
                    score = int(val.split("/")[0])
                    if 1 <= score <= 5:
                        fields["interest"] = score
                except (ValueError, IndexError):
                    pass
            elif key == "quality":
                val_lower = val.lower()
                if val_lower in ("like", "dislike", "broken"):
                    fields["quality"] = val_lower

        feedback[num] = fields

    return feedback
