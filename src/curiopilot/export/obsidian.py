"""Obsidian Markdown export with wikilink-style backlinks."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from curiopilot.storage.knowledge_graph import KnowledgeGraph

log = logging.getLogger(__name__)


def export_obsidian_vault(
    kg: KnowledgeGraph,
    briefings_dir: str | Path,
    output_dir: str | Path,
) -> int:
    """Export the knowledge graph and briefings as an Obsidian-compatible vault.

    Creates:
    - One Markdown file per concept node with metadata and backlinks.
    - A ``_Index.md`` with all concepts.
    - Copies existing briefings into a ``Briefings/`` subfolder.

    Returns the number of concept files written.
    """
    out = Path(output_dir)
    concepts_dir = out / "Concepts"
    briefings_out = out / "Briefings"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    briefings_out.mkdir(parents=True, exist_ok=True)

    written = 0

    # Export each concept node
    for node in kg.graph.nodes:
        attrs = kg.graph.nodes[node]
        neighbors = list(kg.graph.neighbors(node))
        sources = _collect_source_articles(kg, node)

        lines: list[str] = []
        lines.append(f"# {node}")
        lines.append("")

        # Frontmatter-style metadata
        lines.append(f"**First seen**: {attrs.get('first_seen', 'unknown')}")
        lines.append(f"**Last seen**: {attrs.get('last_seen', 'unknown')}")
        lines.append(f"**Encounters**: {attrs.get('encounter_count', 0)}")
        lines.append(f"**Familiarity**: {attrs.get('familiarity', 0):.2f}")
        lines.append("")

        # Related concepts as wikilinks
        if neighbors:
            lines.append("## Related Concepts")
            lines.append("")
            for n in sorted(neighbors):
                lines.append(f"- [[{_filename(n)}|{n}]]")
            lines.append("")

        # Source articles
        if sources:
            lines.append("## Source Articles")
            lines.append("")
            for url in sources[:20]:
                lines.append(f"- {url}")
            lines.append("")

        fname = _filename(node) + ".md"
        (concepts_dir / fname).write_text("\n".join(lines), encoding="utf-8")
        written += 1

    # Generate index
    _write_index(kg, concepts_dir, out)

    # Copy briefings
    src_briefings = Path(briefings_dir)
    if src_briefings.is_dir():
        for md_file in sorted(src_briefings.glob("*.md")):
            dest = briefings_out / md_file.name
            dest.write_text(md_file.read_text(encoding="utf-8"), encoding="utf-8")

    log.info(
        "Obsidian vault exported to %s: %d concept files, %d briefings",
        out, written, len(list(briefings_out.glob("*.md"))),
    )
    return written


def _write_index(kg: KnowledgeGraph, concepts_dir: Path, vault_dir: Path) -> None:
    """Write a ``_Index.md`` that links to every concept."""
    lines = ["# CurioPilot Knowledge Index", ""]

    nodes = sorted(
        kg.graph.nodes,
        key=lambda n: kg.graph.nodes[n].get("encounter_count", 0),
        reverse=True,
    )

    lines.append(f"**Total concepts**: {len(nodes)}")
    lines.append(f"**Total connections**: {kg.edge_count()}")
    lines.append("")

    lines.append("## Concepts (by encounter count)")
    lines.append("")
    for node in nodes:
        attrs = kg.graph.nodes[node]
        count = attrs.get("encounter_count", 0)
        lines.append(f"- [[Concepts/{_filename(node)}|{node}]] ({count} encounters)")

    lines.append("")
    vault_dir.joinpath("_Index.md").write_text("\n".join(lines), encoding="utf-8")


def _collect_source_articles(kg: KnowledgeGraph, node: str) -> list[str]:
    """Collect all source article URLs from edges touching this node."""
    urls: list[str] = []
    for _, _, data in kg.graph.edges(node, data=True):
        for url in data.get("source_articles", []):
            if url not in urls:
                urls.append(url)
    return urls


def _filename(concept: str) -> str:
    """Convert a concept name to a safe filename (no extension)."""
    safe = re.sub(r'[<>:"/\\|?*]', "_", concept)
    safe = safe.strip(". ")
    return safe or "unnamed"
