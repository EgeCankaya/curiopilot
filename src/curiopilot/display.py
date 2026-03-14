"""Rich-based terminal display helpers for CurioPilot."""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from curiopilot.models import ArticleEntry, ArticleSummary, ScoredArticle
from curiopilot.pipeline.run import RunResult

_FORCE_TERMINAL = True if sys.platform == "win32" else None
console = Console(force_terminal=_FORCE_TERMINAL)


def _safe(text: str) -> str:
    """Replace characters that can't be encoded by the console's codec."""
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)

_PHASE_LABELS = {
    "discover": "Discovering articles",
    "dedup": "Deduplicating URLs",
    "filter": "Filtering relevance (7B)",
    "model_swap": "Swapping models (7B -> 14B)",
    "read": "Deep reading articles (14B)",
    "model_swap_embed": "Loading embedding model",
    "novelty": "Scoring novelty",
    "graph_update": "Updating knowledge graph",
    "briefing": "Generating briefing",
}


def print_run_summary(result: RunResult, *, dry_run: bool = False) -> None:
    """Print a concise summary of the pipeline run to the terminal."""
    console.print()
    console.rule("[bold]CurioPilot Run Summary[/bold]")

    duration = _fmt_duration(result.duration_seconds)
    console.print(
        f"  Articles scanned  : [cyan]{result.articles_scanned}[/cyan]\n"
        f"  New (not visited)  : [cyan]{result.articles_new}[/cyan]\n"
        f"  Passed filter      : [cyan]{result.articles_filtered}[/cyan]\n"
        f"  Summaries produced : [cyan]{len(result.summaries)}[/cyan]\n"
        f"  Pipeline runtime   : [cyan]{duration}[/cyan]"
    )

    # Graph stats (Phase 3)
    gs = result.graph_stats
    if gs.total_nodes > 0:
        console.print(
            f"  Graph nodes added  : [green]{gs.nodes_added}[/green]\n"
            f"  Graph edges added  : [green]{gs.edges_added}[/green]\n"
            f"  Total graph nodes  : [green]{gs.total_nodes}[/green]"
        )
        if gs.most_connected:
            console.print(
                f"  Most connected     : [green]{gs.most_connected}[/green] "
                f"({gs.most_connected_edges} edges)"
            )

    console.print()

    if dry_run or not result.scored:
        _print_article_list(result.new_articles)
    elif not result.summaries:
        _print_scored_list(result.scored)
    else:
        _print_briefing_summary(result)

    if result.briefing_path:
        console.print()
        console.print(
            Panel(
                f"[green]Briefing saved to:[/green] {result.briefing_path}",
                title="Briefing",
                expand=False,
            )
        )


def _print_article_list(articles: list[ArticleEntry]) -> None:
    if not articles:
        console.print("[yellow]No new articles found.[/yellow]")
        return

    table = Table(title="Discovered Articles", show_lines=True)
    table.add_column("#", justify="right", width=4)
    table.add_column("Title", min_width=40)
    table.add_column("Source")
    table.add_column("Score", justify="right", width=6)

    for idx, a in enumerate(articles, 1):
        score_str = str(a.score) if a.score is not None else "-"
        table.add_row(str(idx), f"[link={a.url}]{_safe(a.title)}[/link]", a.source_name, score_str)

    console.print(table)


def _print_scored_list(scored: list[ScoredArticle]) -> None:
    if not scored:
        console.print("[yellow]No articles passed the relevance filter.[/yellow]")
        return

    table = Table(title="Relevant Articles", show_lines=True)
    table.add_column("#", justify="right", width=4)
    table.add_column("Title", min_width=40)
    table.add_column("Rel.", justify="right", width=5)
    table.add_column("Justification", min_width=30)

    for idx, sa in enumerate(scored, 1):
        table.add_row(
            str(idx),
            f"[link={sa.article.url}]{_safe(sa.article.title)}[/link]",
            f"{sa.relevance.score}/10",
            _safe(sa.relevance.justification),
        )

    console.print(table)


def _print_briefing_summary(result: RunResult) -> None:
    """Print the top 5 articles with novelty scores as a terminal preview."""
    scored = result.scored
    summaries = result.summaries
    novelty_results = result.novelty_results

    rel_by_url = {sa.article.url: sa.relevance.score for sa in scored}
    novelty_by_url = {nr.url: nr for nr in novelty_results}

    table = Table(title="Briefing Preview (top 5)", show_lines=True)
    table.add_column("#", justify="right", width=4)
    table.add_column("Title", min_width=30)
    table.add_column("Rel.", justify="right", width=5)
    table.add_column("Nov.", justify="right", width=5)
    table.add_column("Final", justify="right", width=6)
    table.add_column("Summary", min_width=35)

    for idx, s in enumerate(summaries[:5], 1):
        rel = rel_by_url.get(s.url, 0)
        nr = novelty_by_url.get(s.url)
        novelty_str = f"{int(nr.novelty_score * 100)}%" if nr else "-"
        final_str = f"{nr.final_score:.2f}" if nr else "-"
        short_summary = s.summary[:100] + "..." if len(s.summary) > 100 else s.summary
        table.add_row(
            str(idx),
            f"[link={s.url}]{_safe(s.title)}[/link]",
            f"{rel}/10",
            novelty_str,
            final_str,
            _safe(short_summary),
        )

    console.print(table)


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}m {s:.0f}s"
