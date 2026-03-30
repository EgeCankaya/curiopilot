"""Briefing generator -- compiles ArticleSummaries into a Markdown daily briefing.

Phase 3 template includes: New Concepts, Top Articles (with novelty %), Deepening,
Knowledge Graph Update, and Suggested Explorations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from curiopilot.agents.novelty_engine import NoveltyResult
from curiopilot.models import ArticleSummary, ScoredArticle
from curiopilot.storage.knowledge_graph import Exploration, GraphUpdateStats

log = logging.getLogger(__name__)


@dataclass
class BriefingContext:
    """All the data needed by the Phase 3 briefing template."""

    summaries: list[ArticleSummary] = field(default_factory=list)
    scored: list[ScoredArticle] = field(default_factory=list)
    novelty_results: list[NoveltyResult] = field(default_factory=list)
    graph_stats: GraphUpdateStats = field(default_factory=GraphUpdateStats)
    explorations: list[Exploration] = field(default_factory=list)
    new_concepts: list[tuple[str, str]] = field(default_factory=list)
    articles_scanned: int = 0
    articles_relevant: int = 0
    pipeline_duration_s: float = 0.0
    briefing_date: date | None = None


def generate_briefing(ctx: BriefingContext) -> str:
    """Return the full Markdown text for the daily briefing (Phase 3 template)."""
    today = ctx.briefing_date or date.today()
    duration = _format_duration(ctx.pipeline_duration_s)

    novelty_by_url: dict[str, NoveltyResult] = {nr.url: nr for nr in ctx.novelty_results}
    relevance_by_url: dict[str, int] = {
        sa.article.url: sa.relevance.score for sa in ctx.scored
    }

    lines: list[str] = []
    lines.append(f"# CurioPilot Daily Briefing -- {today.isoformat()}")
    lines.append("")
    lines.append(
        f"**Articles Scanned**: {ctx.articles_scanned} | "
        f"**Passed Relevance**: {ctx.articles_relevant} | "
        f"**In Briefing**: {len(ctx.summaries)}"
    )
    lines.append(f"**Pipeline Runtime**: {duration}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not ctx.summaries:
        lines.append("*No articles to include in today's briefing.*")
        return "\n".join(lines)

    # ── Top Articles ─────────────────────────────────────────────────────
    # Separate "genuinely novel" from "deepening" articles
    novel_summaries: list[ArticleSummary] = []
    deepening_summaries: list[ArticleSummary] = []

    for s in ctx.summaries:
        nr = novelty_by_url.get(s.url)
        if nr and nr.graph_novelty < 0.4:
            deepening_summaries.append(s)
        else:
            novel_summaries.append(s)

    article_counter = 0
    article_titles: list[str] = []

    if novel_summaries:
        lines.append("## Top Articles")
        lines.append("")
        for idx, summary in enumerate(novel_summaries, 1):
            article_counter += 1
            article_titles.append(summary.title)
            nr = novelty_by_url.get(summary.url)
            rel_score = relevance_by_url.get(summary.url, 0)
            novelty_pct = int((nr.novelty_score if nr else 0.5) * 100)
            concepts = ", ".join(f"`{c}`" for c in summary.key_concepts)

            lines.append(f"### {article_counter}. {summary.title}")
            lines.append(
                f"**Source**: {summary.source_name} | "
                f"**Relevance**: {rel_score}/10 | "
                f"**Novelty**: {novelty_pct}%"
            )
            if nr and nr.graph_novelty >= 0.6:
                lines.append(f"**Why it is new to you**: Introduces concepts not yet in your knowledge graph (graph novelty {int(nr.graph_novelty * 100)}%)")
            lines.append("")
            lines.append(summary.summary)
            lines.append("")
            if summary.novel_insights:
                lines.append(f"**Novel insights**: {summary.novel_insights}")
                lines.append("")
            lines.append(f"**Key Concepts**: {concepts}")
            if summary.related_topics:
                topics = ", ".join(summary.related_topics)
                lines.append(f"**Related Topics**: {topics}")
            lines.append("")
            lines.append(f"[Read original]({summary.url})")
            lines.append("")
            lines.append("---")
            lines.append("")

    # ── Deepening ────────────────────────────────────────────────────────
    if deepening_summaries:
        lines.append("## Deepening")
        lines.append("> Articles on topics you know, but with a new angle.")
        lines.append("")
        for summary in deepening_summaries:
            article_counter += 1
            article_titles.append(summary.title)
            lines.append(f"### {article_counter}. {summary.title}")
            lines.append(
                f"**What you already know**: You have encountered "
                f"{', '.join(f'`{c}`' for c in summary.key_concepts[:3])} before."
            )
            if summary.novel_insights:
                lines.append(f"**What is new here**: {summary.novel_insights}")
            lines.append("")
            lines.append(f"[Read original]({summary.url})")
            lines.append("")
            lines.append("---")
            lines.append("")

    # ── New Concepts ─────────────────────────────────────────────────────
    if ctx.new_concepts:
        lines.append("## New Concepts")
        lines.append("> Topics appearing for the first time in your knowledge graph.")
        lines.append("")
        for concept, article_title in ctx.new_concepts:
            lines.append(f"- **{concept}**: First encountered in \"{article_title}\"")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Knowledge Graph Update ───────────────────────────────────────────
    gs = ctx.graph_stats
    lines.append("## Knowledge Graph Update")
    node_names = ", ".join(gs.new_concept_names[:10]) if gs.new_concept_names else "none"
    lines.append(f"- **Nodes added**: {gs.nodes_added} ({node_names})")
    lines.append(f"- **Edges added**: {gs.edges_added}")
    lines.append(f"- **Total knowledge nodes**: {gs.total_nodes}")
    if gs.most_connected:
        lines.append(
            f"- **Most connected topic**: {gs.most_connected} "
            f"({gs.most_connected_edges} connections)"
        )
    lines.append("")

    # ── Suggested Explorations ───────────────────────────────────────────
    if ctx.explorations:
        lines.append("## Suggested Explorations")
        lines.append("> Topics adjacent to your knowledge that you have not explored yet.")
        lines.append("")
        for i, exp in enumerate(ctx.explorations, 1):
            lines.append(f"{i}. **{exp.topic}** -- {exp.reason}")
        lines.append("")

    # ── Your Feedback ─────────────────────────────────────────────────────
    if article_counter > 0:
        lines.append("---")
        lines.append("")
        lines.append("## Your Feedback")
        lines.append("> Rate articles after reading. Processed automatically on next `curiopilot run`.")
        lines.append("> read: yes/no | interest: 1-5 | quality: like/meh/dislike/broken")
        lines.append("")
        for n in range(1, article_counter + 1):
            title = article_titles[n - 1] if n <= len(article_titles) else ""
            lines.append(f"**{n}. {title}**")
            lines.append(f"- {n}: read=, interest=, quality=")
        lines.append("")

    return "\n".join(lines)


def save_briefing(
    markdown: str,
    briefings_dir: str | Path,
    briefing_date: date | None = None,
) -> Path:
    """Write the briefing Markdown to disk and return the file path."""
    today = briefing_date or date.today()
    out_dir = Path(briefings_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{today.isoformat()}.md"
    path.write_text(markdown, encoding="utf-8")
    log.info("Briefing saved to %s", path)
    return path


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.0f}s"
