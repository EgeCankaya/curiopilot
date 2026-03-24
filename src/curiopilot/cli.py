"""CurioPilot CLI -- entry point registered as ``curiopilot``."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

app = typer.Typer(
    name="curiopilot",
    help="Autonomous knowledge discovery agent.",
    add_completion=False,
)

# On Windows, force ANSI terminal mode so Rich bypasses the legacy Win32
# renderer which cannot encode Unicode spinner/braille characters on cp1252.
_FORCE_TERMINAL = True if sys.platform == "win32" else None
console = Console(force_terminal=_FORCE_TERMINAL)

_PHASE_LABELS = {
    "feedback": "Ingesting feedback",
    "discover": "Discovering articles",
    "dedup": "Deduplicating URLs",
    "filter": "Filtering relevance (7B)",
    "model_swap": "Swapping models (7B -> 14B)",
    "read": "Deep reading (14B)",
    "model_swap_embed": "Loading embedding model",
    "novelty": "Scoring novelty",
    "graph_update": "Updating knowledge graph",
    "briefing": "Generating briefing",
}


def _safe(text: str) -> str:
    """Replace characters that the console codec can't encode."""
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


# ── run ──────────────────────────────────────────────────────────────────────


@app.command()
def run(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Crawl and dedup only, skip all LLM work")
    ] = False,
    no_filter: Annotated[
        bool, typer.Option("--no-filter", help="Skip 7B relevance filter, still do deep reading")
    ] = False,
    source: Annotated[
        Optional[list[str]],
        typer.Option("--source", "-s", help="Only run these sources (by name)"),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable debug logging")
    ] = False,
    incremental: Annotated[
        bool, typer.Option("--incremental", help="Only scrape sources updated since last successful run")
    ] = False,
    resume: Annotated[
        Optional[str], typer.Option("--resume", help="Resume a previous run by its run_id")
    ] = None,
) -> None:
    """Run the CurioPilot discovery pipeline."""
    from curiopilot.display import print_run_summary
    from curiopilot.pipeline.run import run_pipeline

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )

    task_ids: dict[str, object] = {}

    def _progress_callback(phase: str, current: int, total: int) -> None:
        label = _PHASE_LABELS.get(phase, phase)
        if phase not in task_ids:
            task_ids[phase] = progress.add_task(label, total=max(total, 1))
        tid = task_ids[phase]
        progress.update(tid, completed=current, total=max(total, 1))

    with progress:
        result = asyncio.run(
            run_pipeline(
                config_path=config,
                dry_run=dry_run,
                no_filter=no_filter,
                source_names=source,
                verbose=verbose,
                progress_callback=_progress_callback,
                incremental=incremental,
                resume_run_id=resume,
            )
        )

    print_run_summary(result, dry_run=dry_run)


# ── query ────────────────────────────────────────────────────────────────────


@app.command()
def query(
    question: Annotated[str, typer.Argument(help="Your question about past knowledge")],
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    top_k: Annotated[
        int, typer.Option("--top-k", "-k", help="Number of articles to retrieve")
    ] = 10,
) -> None:
    """Query your knowledge base and get a synthesized answer."""
    asyncio.run(_query_impl(question, config, top_k))


async def _query_impl(question: str, config_path: Path, top_k: int) -> None:
    from rich.markdown import Markdown
    from rich.panel import Panel

    from curiopilot.agents.query_agent import query_knowledge
    from curiopilot.config import load_config
    from curiopilot.llm.ollama import OllamaClient
    from curiopilot.logging_config import setup_logging
    from curiopilot.storage.knowledge_graph import KnowledgeGraph
    from curiopilot.storage.vector_store import VectorStore

    setup_logging()

    config = load_config(config_path)
    db_dir = Path(config.paths.database_dir)

    chroma_dir = db_dir / "chromadb"
    if not chroma_dir.exists():
        console.print("[yellow]No vector store found. Run the pipeline first to build knowledge.[/yellow]")
        return

    vs = VectorStore(chroma_dir)
    vs.open()

    if vs.count() == 0:
        console.print("[yellow]Vector store is empty. Run the pipeline first.[/yellow]")
        return

    kg = KnowledgeGraph(config.paths.graph_path)
    kg.load()

    client = OllamaClient(
        base_url=config.ollama.base_url,
        timeout_seconds=config.ollama.timeout_seconds,
        max_retries=config.ollama.max_retries,
    )

    console.print()
    console.print(f"[bold]Querying:[/bold] {_safe(question)}")
    console.print()

    with console.status("[bold blue]Searching knowledge base..."):
        result = await query_knowledge(question, config, client, vs, kg, top_k=top_k)

    console.print(Panel(Markdown(_safe(result.answer)), title="Answer", expand=True))

    if result.source_articles:
        console.print()
        console.print("[bold]Sources referenced:[/bold]")
        for i, art in enumerate(result.source_articles[:5], 1):
            title = art.get("title", "Unknown")
            url = art.get("url", "")
            sim = art.get("similarity", 0)
            console.print(f"  {i}. {_safe(title)} (similarity: {sim:.2f}) - {url}")

    if result.related_concepts:
        console.print()
        concepts = ", ".join(result.related_concepts[:10])
        console.print(f"[bold]Related concepts:[/bold] {_safe(concepts)}")

    console.print()


# ── dive ─────────────────────────────────────────────────────────────────────


@app.command()
def dive(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
) -> None:
    """Interactive deep-dive into the most recent briefing."""
    asyncio.run(_dive_impl(config))


async def _dive_impl(config_path: Path) -> None:
    from rich.markdown import Markdown
    from rich.panel import Panel

    from curiopilot.agents.query_agent import query_knowledge
    from curiopilot.config import load_config
    from curiopilot.llm.ollama import OllamaClient
    from curiopilot.logging_config import setup_logging
    from curiopilot.storage.knowledge_graph import KnowledgeGraph
    from curiopilot.storage.vector_store import VectorStore

    setup_logging()

    config = load_config(config_path)
    db_dir = Path(config.paths.database_dir)
    briefings_dir = Path(config.paths.briefings_dir)

    # Find latest briefing
    briefings = sorted(briefings_dir.glob("*.md"), reverse=True)
    if not briefings:
        console.print("[yellow]No briefings found. Run the pipeline first.[/yellow]")
        return

    latest = briefings[0]
    content = latest.read_text(encoding="utf-8")

    console.print()
    console.print(Panel(f"[green]Latest briefing:[/green] {latest.name}", expand=False))
    console.print()

    # Extract article titles from the briefing for numbered references
    import re
    article_titles = re.findall(r"^### \d+\.\s+(.+)$", content, re.MULTILINE)

    if article_titles:
        console.print("[bold]Articles in this briefing:[/bold]")
        for i, title in enumerate(article_titles, 1):
            console.print(f"  {i}. {_safe(title)}")
        console.print()

    chroma_dir = db_dir / "chromadb"
    if not chroma_dir.exists():
        console.print("[yellow]No vector store found. Cannot deep-dive.[/yellow]")
        return

    vs = VectorStore(chroma_dir)
    vs.open()

    kg = KnowledgeGraph(config.paths.graph_path)
    kg.load()

    client = OllamaClient(
        base_url=config.ollama.base_url,
        timeout_seconds=config.ollama.timeout_seconds,
        max_retries=config.ollama.max_retries,
    )

    console.print("[bold]Enter a question or article number to explore (type 'quit' to exit):[/bold]")

    while True:
        console.print()
        user_input = console.input("[bold cyan]> [/bold cyan]").strip()

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        # If they typed a number, turn it into a question
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(article_titles):
                user_input = f"Tell me more about: {article_titles[idx]}"
                console.print(f"[dim]Querying: {_safe(user_input)}[/dim]")
            else:
                console.print(f"[yellow]Article number out of range (1-{len(article_titles)})[/yellow]")
                continue

        with console.status("[bold blue]Thinking..."):
            result = await query_knowledge(user_input, config, client, vs, kg, top_k=5)

        console.print()
        console.print(Panel(Markdown(_safe(result.answer)), title="Answer", expand=True))

        if result.related_concepts:
            concepts = ", ".join(result.related_concepts[:8])
            console.print(f"[dim]Related: {_safe(concepts)}[/dim]")


# ── export ───────────────────────────────────────────────────────────────────


@app.command(name="export")
def export_cmd(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output directory (Obsidian vault root or subfolder)")
    ] = Path("./obsidian-export"),
) -> None:
    """Export knowledge graph and briefings as Obsidian-compatible Markdown.

    Each concept becomes its own note with [[wikilinks]] to related concepts,
    so Obsidian's built-in graph view visualises your knowledge graph natively.

    Briefings are copied with YAML frontmatter and key concepts linked.

    Example — export directly into your vault:

        curiopilot export --output "F:\\Coding\\Obisidan\\CurioPilot"
    """
    from curiopilot.config import load_config
    from curiopilot.export.obsidian import export_obsidian_vault
    from curiopilot.storage.knowledge_graph import KnowledgeGraph

    config_obj = load_config(config)

    kg = KnowledgeGraph(config_obj.paths.graph_path)
    kg.load()

    if kg.node_count() == 0:
        console.print("[yellow]Knowledge graph is empty. Run the pipeline first.[/yellow]")
        return

    briefing_count = len(list(Path(config_obj.paths.briefings_dir).glob("*.md")))

    count = export_obsidian_vault(
        kg=kg,
        briefings_dir=config_obj.paths.briefings_dir,
        output_dir=output,
    )

    out_abs = output.resolve()
    console.print()
    console.print(f"[green]Export complete:[/green] {out_abs}")
    console.print(f"  Concept notes : {count}")
    console.print(f"  Briefings     : {briefing_count}")
    console.print()
    console.print("[dim]Vault structure:[/dim]")
    console.print(f"  [dim]{out_abs / 'Knowledge Graph.md'}[/dim]")
    console.print(f"  [dim]{out_abs / 'Concepts'}/  ({count} notes)[/dim]")
    console.print(f"  [dim]{out_abs / 'Briefings'}/  ({briefing_count} notes)[/dim]")
    console.print()
    console.print("[dim]Open the folder as a vault in Obsidian.[/dim]")
    console.print("[dim]Obsidian's graph view will show your concept network automatically.[/dim]")


# ── add-source ───────────────────────────────────────────────────────────────


@app.command(name="add-source")
def add_source(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
) -> None:
    """Interactive assistant to add a new source to config.yaml."""
    import yaml

    from curiopilot.config import KNOWN_SCRAPERS

    console.print()
    console.print("[bold]Add a new source to CurioPilot[/bold]")
    console.print()

    # Name
    name = console.input("[bold]Source name[/bold] (e.g., 'r/LocalLLaMA'): ").strip()
    if not name:
        console.print("[red]Name is required.[/red]")
        raise typer.Exit(1)

    # Scraper type
    scraper_list = sorted(KNOWN_SCRAPERS)
    console.print()
    console.print("[bold]Available scrapers:[/bold]")
    for i, s in enumerate(scraper_list, 1):
        console.print(f"  {i}. {s}")
    scraper_input = console.input("[bold]Scraper[/bold] (name or number): ").strip()

    if scraper_input.isdigit():
        idx = int(scraper_input) - 1
        if 0 <= idx < len(scraper_list):
            scraper = scraper_list[idx]
        else:
            console.print("[red]Invalid selection.[/red]")
            raise typer.Exit(1)
    elif scraper_input in KNOWN_SCRAPERS:
        scraper = scraper_input
    else:
        console.print(f"[red]Unknown scraper: {scraper_input}[/red]")
        raise typer.Exit(1)

    # URL (optional for some scrapers)
    url: str | None = None
    if scraper in ("reddit_json", "generic_scrape"):
        url = console.input("[bold]URL[/bold] (e.g., 'r/MachineLearning' or full URL): ").strip() or None
    elif scraper == "arxiv_feed":
        pass
    else:
        url_input = console.input("[bold]URL[/bold] (optional, press Enter to skip): ").strip()
        url = url_input or None

    # Query (for arxiv)
    query_str: str | None = None
    if scraper == "arxiv_feed":
        query_str = console.input("[bold]ArXiv query[/bold] (e.g., 'cat:cs.AI'): ").strip() or None

    # Max articles
    max_str = console.input("[bold]Max articles[/bold] (default 20): ").strip()
    max_articles = int(max_str) if max_str.isdigit() else 20

    # Delay
    delay_str = console.input("[bold]Request delay seconds[/bold] (default 3): ").strip()
    try:
        delay = float(delay_str) if delay_str else 3.0
    except ValueError:
        delay = 3.0

    # Build the source entry
    new_source: dict = {
        "name": name,
        "scraper": scraper,
        "max_articles": max_articles,
        "request_delay_seconds": delay,
    }
    if url:
        new_source["url"] = url
    if query_str:
        new_source["query"] = query_str

    # Read existing config and append
    config_path = Path(config)
    raw_text = config_path.read_text(encoding="utf-8")
    raw = yaml.safe_load(raw_text)

    if "sources" not in raw:
        raw["sources"] = []
    raw["sources"].append(new_source)

    config_path.write_text(yaml.dump(raw, default_flow_style=False, sort_keys=False), encoding="utf-8")

    console.print()
    console.print(f"[green]Added source '{name}' (scraper: {scraper}) to {config_path}[/green]")


# ── stats ────────────────────────────────────────────────────────────────────


@app.command()
def stats(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
) -> None:
    """Show knowledge base and pipeline statistics."""
    asyncio.run(_stats_impl(config))


async def _stats_impl(config_path: Path) -> None:
    from rich.table import Table

    from curiopilot.config import load_config
    from curiopilot.storage.knowledge_graph import KnowledgeGraph
    from curiopilot.storage.url_store import URLStore
    from curiopilot.storage.vector_store import VectorStore

    config = load_config(config_path)
    db_dir = Path(config.paths.database_dir)

    store = URLStore(db_dir / "curiopilot.db")
    await store.open()
    url_stats = await store.url_stats()
    await store.close()

    chroma_dir = db_dir / "chromadb"
    vec_count = 0
    if chroma_dir.exists():
        vs = VectorStore(chroma_dir)
        vs.open()
        vec_count = vs.count()

    kg = KnowledgeGraph(config.paths.graph_path)
    kg.load()

    table = Table(title="CurioPilot Statistics", show_lines=True)
    table.add_column("Metric", min_width=30)
    table.add_column("Value", justify="right", min_width=12)

    table.add_row("Total URLs visited", str(url_stats["total_urls"]))
    table.add_row("URLs passed relevance", str(url_stats["passed_relevance"]))
    table.add_row("Distinct sources seen", str(url_stats["sources"]))
    table.add_row("Article embeddings (ChromaDB)", str(vec_count))
    table.add_row("Knowledge graph nodes", str(kg.node_count()))
    table.add_row("Knowledge graph edges", str(kg.edge_count()))

    if kg.node_count() > 0:
        topic, edges = kg.most_connected_topic()
        table.add_row("Most connected topic", f"{_safe(topic)} ({edges} edges)")

    console.print()
    console.print(table)

    if kg.node_count() > 0:
        console.print()
        top_table = Table(title="Top Concepts (by familiarity)", show_lines=True)
        top_table.add_column("Concept", min_width=25)
        top_table.add_column("Familiarity", justify="right", width=12)
        top_table.add_column("Encounters", justify="right", width=10)
        top_table.add_column("Connections", justify="right", width=12)

        nodes = sorted(
            kg.graph.nodes,
            key=lambda n: kg.graph.nodes[n].get("familiarity", 0),
            reverse=True,
        )
        for node in nodes[:15]:
            attrs = kg.graph.nodes[node]
            top_table.add_row(
                _safe(node),
                f"{attrs.get('familiarity', 0):.2f}",
                str(attrs.get("encounter_count", 0)),
                str(kg.graph.degree(node)),
            )
        console.print(top_table)


# ── history ──────────────────────────────────────────────────────────────────


@app.command()
def history(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Number of recent runs to show")
    ] = 10,
    date: Annotated[
        Optional[str], typer.Option("--date", "-d", help="View briefing for a specific date (YYYY-MM-DD)")
    ] = None,
) -> None:
    """Show recent pipeline run history, or view a specific briefing by date."""
    if date:
        _show_briefing_by_date(config, date)
    else:
        asyncio.run(_history_impl(config, limit))


def _show_briefing_by_date(config_path: Path, date_str: str) -> None:
    from rich.markdown import Markdown

    from curiopilot.config import load_config

    config = load_config(config_path)
    briefings_dir = Path(config.paths.briefings_dir)
    briefing_file = briefings_dir / f"{date_str}.md"

    if not briefing_file.is_file():
        available = sorted(briefings_dir.glob("*.md"), reverse=True)
        console.print(f"[red]No briefing found for date: {date_str}[/red]")
        if available:
            dates = ", ".join(f.stem for f in available[:5])
            console.print(f"[dim]Available: {dates}[/dim]")
        return

    content = briefing_file.read_text(encoding="utf-8")
    console.print()
    console.print(Markdown(_safe(content)))


async def _history_impl(config_path: Path, limit: int) -> None:
    from rich.table import Table

    from curiopilot.config import load_config
    from curiopilot.storage.url_store import URLStore

    config = load_config(config_path)
    db_dir = Path(config.paths.database_dir)

    store = URLStore(db_dir / "curiopilot.db")
    await store.open()
    runs = await store.recent_runs(limit=limit)
    await store.close()

    if not runs:
        console.print("[yellow]No pipeline runs recorded yet.[/yellow]")
        return

    table = Table(title=f"Recent Pipeline Runs (last {limit})", show_lines=True)
    table.add_column("Run ID", width=14)
    table.add_column("Started", min_width=20)
    table.add_column("Scanned", justify="right", width=8)
    table.add_column("Relevant", justify="right", width=9)
    table.add_column("Briefed", justify="right", width=8)
    table.add_column("New Concepts", justify="right", width=13)

    for r in runs:
        table.add_row(
            str(r.get("run_id", ""))[:12],
            str(r.get("started_at", ""))[:19],
            str(r.get("articles_scanned", 0)),
            str(r.get("articles_relevant", 0)),
            str(r.get("articles_briefed", 0)),
            str(r.get("new_concepts_added", 0)),
        )

    console.print()
    console.print(table)


# ── decay ────────────────────────────────────────────────────────────────────


@app.command()
def decay(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    half_life: Annotated[
        float, typer.Option("--half-life", help="Half-life in days for familiarity decay")
    ] = 14.0,
) -> None:
    """Apply memory decay to the knowledge graph familiarity scores."""
    from curiopilot.config import load_config
    from curiopilot.storage.knowledge_graph import KnowledgeGraph

    config_obj = load_config(config)

    kg = KnowledgeGraph(config_obj.paths.graph_path)
    kg.load()

    if kg.node_count() == 0:
        console.print("[yellow]Knowledge graph is empty.[/yellow]")
        return

    before = kg.node_count()
    pruned = kg.apply_memory_decay(half_life_days=half_life)
    kg.save()

    console.print()
    console.print(f"[green]Memory decay applied (half-life: {half_life} days)[/green]")
    console.print(f"  Nodes before: {before}")
    console.print(f"  Nodes pruned: {pruned}")
    console.print(f"  Nodes after : {kg.node_count()}")


# ── reset ────────────────────────────────────────────────────────────────────


@app.command()
def reset(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Required flag to confirm destructive reset")
    ] = False,
) -> None:
    """Reset all memory (destructive). Deletes SQLite, ChromaDB, and knowledge graph."""
    import shutil

    if not confirm:
        console.print(
            "[red]This will permanently delete all CurioPilot memory "
            "(visited URLs, embeddings, knowledge graph).[/red]"
        )
        console.print("Re-run with [bold]--confirm[/bold] to proceed.")
        raise typer.Exit(1)

    from curiopilot.config import load_config

    config_obj = load_config(config)
    db_dir = Path(config_obj.paths.database_dir)
    graph_path = Path(config_obj.paths.graph_path)

    removed: list[str] = []

    db_file = db_dir / "curiopilot.db"
    if db_file.is_file():
        db_file.unlink()
        removed.append(str(db_file))

    chroma_dir = db_dir / "chromadb"
    if chroma_dir.is_dir():
        shutil.rmtree(chroma_dir)
        removed.append(str(chroma_dir))

    if graph_path.is_file():
        graph_path.unlink()
        removed.append(str(graph_path))

    console.print()
    if removed:
        console.print("[green]Memory reset complete. Removed:[/green]")
        for r in removed:
            console.print(f"  - {r}")
    else:
        console.print("[yellow]Nothing to reset (no data files found).[/yellow]")


# ── schedule ──────────────────────────────────────────────────────────────────


_TASK_NAME = "CurioPilotDaily"


@app.command()
def schedule(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    time_str: Annotated[
        str, typer.Option("--time", "-t", help="Time to run daily (HH:MM, 24-hour)")
    ] = "08:00",
) -> None:
    """Schedule CurioPilot to run automatically every day."""
    import shutil
    import subprocess

    curiopilot_bin = shutil.which("curiopilot")
    if not curiopilot_bin:
        console.print("[red]Could not find `curiopilot` on PATH.[/red]")
        raise typer.Exit(1)

    config_abs = str(config.resolve())
    cmd_line = f'{curiopilot_bin} run --config "{config_abs}"'

    if sys.platform == "win32":
        result = subprocess.run(
            [
                "schtasks", "/Create", "/F",
                "/SC", "DAILY",
                "/TN", _TASK_NAME,
                "/TR", cmd_line,
                "/ST", time_str,
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print(f"[green]Scheduled daily task '{_TASK_NAME}' at {time_str}.[/green]")
        else:
            console.print(f"[red]Failed to create scheduled task:[/red]\n{result.stderr}")
            raise typer.Exit(1)
    else:
        cron_line = _build_cron_line(time_str, cmd_line)
        console.print(f"Add this line to your crontab (`crontab -e`):\n")
        console.print(f"  [bold]{cron_line}[/bold]\n")

        install = typer.confirm("Install it now?", default=False)
        if install:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            existing = result.stdout if result.returncode == 0 else ""
            if cron_line in existing:
                console.print("[yellow]Cron entry already exists.[/yellow]")
                return
            new_crontab = existing.rstrip("\n") + "\n" + cron_line + "\n"
            proc = subprocess.run(
                ["crontab", "-"], input=new_crontab, capture_output=True, text=True,
            )
            if proc.returncode == 0:
                console.print("[green]Crontab updated successfully.[/green]")
            else:
                console.print(f"[red]Failed to update crontab:[/red]\n{proc.stderr}")
                raise typer.Exit(1)


def _build_cron_line(time_str: str, cmd: str) -> str:
    parts = time_str.split(":")
    hour = parts[0] if len(parts) > 0 else "8"
    minute = parts[1] if len(parts) > 1 else "0"
    return f"{minute} {hour} * * * {cmd}"


@app.command()
def unschedule() -> None:
    """Remove the CurioPilot daily scheduled task."""
    import subprocess

    if sys.platform == "win32":
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", _TASK_NAME, "/F"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print(f"[green]Removed scheduled task '{_TASK_NAME}'.[/green]")
        else:
            console.print(f"[yellow]Could not remove task (may not exist):[/yellow]\n{result.stderr}")
    else:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            console.print("[yellow]No crontab found.[/yellow]")
            return
        lines = result.stdout.splitlines()
        filtered = [l for l in lines if "curiopilot run" not in l]
        if len(filtered) == len(lines):
            console.print("[yellow]No CurioPilot cron entry found.[/yellow]")
            return
        new_crontab = "\n".join(filtered) + "\n"
        proc = subprocess.run(
            ["crontab", "-"], input=new_crontab, capture_output=True, text=True,
        )
        if proc.returncode == 0:
            console.print("[green]Removed CurioPilot cron entry.[/green]")
        else:
            console.print(f"[red]Failed to update crontab:[/red]\n{proc.stderr}")


# ── open ──────────────────────────────────────────────────────────────────────


@app.command(name="open")
def open_cmd(
    date: Annotated[
        Optional[str], typer.Argument(help="Briefing date: YYYY-MM-DD, 'today', 'yesterday', or 'latest' (default)")
    ] = None,
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Max number of tabs to open")
    ] = 0,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Just print URLs without opening")
    ] = False,
) -> None:
    """Open briefing article URLs in the browser.

    DATE can be a YYYY-MM-DD string, or one of the shortcuts:
    'today', 'yesterday', 'latest' (most recent briefing).
    If omitted, defaults to the latest briefing.
    """
    from datetime import date as date_cls, timedelta

    from curiopilot.config import load_config
    from curiopilot.utils.text import extract_briefing_urls

    config_obj = load_config(config)
    briefings_dir = Path(config_obj.paths.briefings_dir)

    resolved_date: str | None = None
    if date is not None:
        keyword = date.strip().lower()
        if keyword in ("today", "latest"):
            resolved_date = None  # fall through to "pick latest file"
        elif keyword == "yesterday":
            resolved_date = (date_cls.today() - timedelta(days=1)).isoformat()
        else:
            resolved_date = date.strip()

    if resolved_date:
        briefing_file = briefings_dir / f"{resolved_date}.md"
    else:
        briefings = sorted(briefings_dir.glob("*.md"), reverse=True)
        if not briefings:
            console.print("[yellow]No briefings found. Run the pipeline first.[/yellow]")
            return
        briefing_file = briefings[0]

    if not briefing_file.is_file():
        console.print(f"[red]Briefing not found: {briefing_file}[/red]")
        return

    text = briefing_file.read_text(encoding="utf-8")
    urls = extract_briefing_urls(text)

    if not urls:
        console.print("[yellow]No article URLs found in the briefing.[/yellow]")
        return

    if limit > 0:
        urls = urls[:limit]

    console.print(f"[bold]Briefing:[/bold] {briefing_file.name}")
    console.print(f"[bold]Articles:[/bold] {len(urls)}")
    console.print()

    for i, url in enumerate(urls, 1):
        console.print(f"  {i}. {url}")

    if dry_run:
        return

    import webbrowser

    for url in urls:
        webbrowser.open(url)

    briefing_date_str = briefing_file.stem
    console.print()
    console.print(
        f"[dim]Tip: Select all new tabs > right-click > "
        f"'Add tabs to group' > name it 'CurioPilot {briefing_date_str}' "
        f"for cross-device sync[/dim]"
    )


# ── migrate ──────────────────────────────────────────────────────────────────


@app.command()
def migrate(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
) -> None:
    """Migrate existing briefing Markdown files into the articles database."""
    asyncio.run(_migrate_impl(config))


async def _migrate_impl(config_path: Path) -> None:
    from curiopilot.config import load_config
    from curiopilot.migrate import migrate_briefings
    from curiopilot.storage.article_store import ArticleStore

    config = load_config(config_path)
    db_dir = Path(config.paths.database_dir)

    article_store = ArticleStore(db_dir / "curiopilot.db")
    await article_store.open()

    try:
        migrated = await migrate_briefings(config.paths.briefings_dir, article_store)
    finally:
        await article_store.close()

    if migrated:
        total = sum(migrated.values())
        console.print(f"[green]Migrated {len(migrated)} briefing(s), {total} article(s) total.[/green]")
        for date_str, count in sorted(migrated.items()):
            console.print(f"  {date_str}: {count} articles")
    else:
        console.print("[yellow]No new briefings to migrate (all dates already in DB).[/yellow]")


# ── refetch ──────────────────────────────────────────────────────────────────


@app.command()
def refetch(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
) -> None:
    """Re-fetch and re-extract article bodies that are empty or corrupted."""
    asyncio.run(_refetch_impl(config))


async def _refetch_impl(config_path: Path) -> None:
    from curiopilot.config import load_config
    from curiopilot.migrate import refetch_articles
    from curiopilot.storage.article_store import ArticleStore

    config = load_config(config_path)
    db_dir = Path(config.paths.database_dir)

    article_store = ArticleStore(db_dir / "curiopilot.db")
    await article_store.open()

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )

    task_id = None

    def _progress_callback(current: int, total: int) -> None:
        nonlocal task_id
        if task_id is None:
            task_id = progress.add_task("Re-fetching articles", total=total)
        progress.update(task_id, completed=current, total=total)

    try:
        with progress:
            stats = await refetch_articles(
                article_store,
                progress_callback=_progress_callback,
            )
    finally:
        await article_store.close()

    console.print()
    console.print(f"[green]Re-fetch complete:[/green]")
    console.print(f"  Updated:  {stats['updated']}")
    console.print(f"  Skipped:  {stats['skipped']}")
    console.print(f"  Failed:   {stats['failed']}")


# ── serve ────────────────────────────────────────────────────────────────────


@app.command()
def serve(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    port: Annotated[
        int, typer.Option("--port", "-p", help="Port to listen on")
    ] = 19231,
    host: Annotated[
        str, typer.Option("--host", help="Host to bind to")
    ] = "127.0.0.1",
) -> None:
    """Start the CurioPilot API server (headless mode)."""
    import uvicorn

    from curiopilot.api.app import create_app

    app_instance = create_app(config_path=str(config))
    console.print(f"[bold]Starting CurioPilot API server on {host}:{port}[/bold]")
    uvicorn.run(app_instance, host=host, port=port, log_level="info")


# ── app (desktop) ────────────────────────────────────────────────────────────


@app.command(name="app")
def desktop(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config.yaml")
    ] = Path("config.yaml"),
    port: Annotated[
        int, typer.Option("--port", "-p", help="Port to listen on")
    ] = 19231,
    debug: Annotated[
        bool, typer.Option("--debug", help="Enable debug mode")
    ] = False,
) -> None:
    """Launch CurioPilot as a desktop application."""
    from curiopilot.desktop import launch_app

    console.print("[bold]Launching CurioPilot desktop app…[/bold]")
    launch_app(config_path=config, port=port, debug=debug)


if __name__ == "__main__":
    app()
