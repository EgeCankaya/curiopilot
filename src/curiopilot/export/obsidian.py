"""Obsidian Markdown export with wikilink-style backlinks and category subfolders."""

from __future__ import annotations

import logging
import re
from datetime import date as date_cls
from pathlib import Path

from curiopilot.storage.knowledge_graph import KnowledgeGraph
from curiopilot.storage.taxonomy import CATEGORY_COLORS

log = logging.getLogger(__name__)


def export_obsidian_vault(
    kg: KnowledgeGraph,
    briefings_dir: str | Path,
    output_dir: str | Path,
) -> int:
    """Export the knowledge graph and briefings as an Obsidian-compatible vault.

    Creates:
    - ``Concepts/{Category}/{concept}.md`` — one file per node with YAML
      frontmatter and ``[[wikilinks]]`` to neighbors.
    - ``Concepts/{Category}/_Category.md`` — category overview page.
    - ``Briefings/{date}.md`` — copies of briefings with YAML frontmatter and
      key-concept backtick spans converted to ``[[wikilinks]]``.
    - ``Knowledge Graph.md`` — overview index with top-concepts tables and
      domain breakdown.

    Returns the number of concept files written.
    """
    out = Path(output_dir)
    concepts_dir = out / "Concepts"
    briefings_out = out / "Briefings"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    briefings_out.mkdir(parents=True, exist_ok=True)

    # Group nodes by category
    by_category: dict[str, list[str]] = {}
    for node in kg.graph.nodes:
        cat = kg.graph.nodes[node].get("category", "Uncategorized")
        by_category.setdefault(cat, []).append(node)

    written = 0

    # Export each concept node into category subfolders
    for cat, nodes in by_category.items():
        cat_dir = concepts_dir / _filename(cat)
        cat_dir.mkdir(parents=True, exist_ok=True)

        for node in nodes:
            attrs = kg.graph.nodes[node]
            neighbors = sorted(kg.graph.neighbors(node))
            familiarity = attrs.get("familiarity", 0.0)
            encounters = attrs.get("encounter_count", 0)
            first_seen = str(attrs.get("first_seen", ""))[:10]
            last_seen = str(attrs.get("last_seen", ""))[:10]
            degree = kg.graph.degree(node)

            lines: list[str] = []

            # YAML frontmatter
            lines.append("---")
            lines.append("tags:")
            lines.append("  - curiopilot/concept")
            lines.append(f"category: \"{cat}\"")
            lines.append(f"familiarity: {familiarity:.2f}")
            lines.append(f"encounters: {encounters}")
            lines.append(f"connections: {degree}")
            if first_seen:
                lines.append(f"first_seen: {first_seen}")
            if last_seen:
                lines.append(f"last_seen: {last_seen}")
            lines.append("---")
            lines.append("")

            lines.append(f"# {node}")
            lines.append("")
            lines.append(
                f"**Familiarity**: {familiarity * 100:.0f}% | "
                f"**Encounters**: {encounters} | "
                f"**Connections**: {degree}"
            )
            lines.append("")

            # Related concepts as short-form wikilinks (Obsidian resolves by filename)
            if neighbors:
                lines.append("## Related Concepts")
                lines.append("")
                for n in neighbors:
                    lines.append(f"- [[{_filename(n)}|{n}]]")
                lines.append("")

            # Source article URLs from edges
            sources = _collect_source_articles(kg, node)
            if sources:
                lines.append("## Source Articles")
                lines.append("")
                for url in sources[:20]:
                    lines.append(f"- {url}")
                lines.append("")

            fname = _filename(node) + ".md"
            (cat_dir / fname).write_text("\n".join(lines), encoding="utf-8")
            written += 1

    # Write _Category.md for each category
    for cat, nodes in by_category.items():
        cat_dir = concepts_dir / _filename(cat)
        color = CATEGORY_COLORS.get(cat, "#8E8E93")
        count = len(nodes)

        lines: list[str] = []
        lines.append("---")
        lines.append("tags:")
        lines.append("  - curiopilot/category")
        lines.append(f"category: \"{cat}\"")
        lines.append(f"color: \"{color}\"")
        lines.append(f"node_count: {count}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {cat}")
        lines.append("")
        lines.append(f"{count} concepts in this domain.")
        lines.append("")
        lines.append("## Concepts")
        lines.append("")
        for node in sorted(nodes):
            attrs = kg.graph.nodes[node]
            fam = attrs.get("familiarity", 0.0)
            enc = attrs.get("encounter_count", 0)
            lines.append(
                f"- [[{_filename(node)}|{node}]] "
                f"(familiarity: {fam * 100:.0f}%, {enc} encounters)"
            )
        lines.append("")
        (cat_dir / "_Category.md").write_text("\n".join(lines), encoding="utf-8")

    # Build a lookup for wikilink injection in briefings
    concept_lookup = {n.lower(): n for n in kg.graph.nodes}

    # Copy briefings with frontmatter + wikilinks
    src_briefings = Path(briefings_dir)
    briefing_count = 0
    if src_briefings.is_dir():
        for md_file in sorted(src_briefings.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            enhanced = _enhance_briefing(content, md_file.stem, concept_lookup)
            dest = briefings_out / md_file.name
            dest.write_text(enhanced, encoding="utf-8")
            briefing_count += 1

    # Generate knowledge graph index
    _write_index(kg, out, by_category)

    log.info(
        "Obsidian vault exported to %s: %d concept files, %d briefings",
        out, written, briefing_count,
    )
    return written


def _enhance_briefing(content: str, date_stem: str, concept_lookup: dict[str, str]) -> str:
    """Prepend YAML frontmatter and convert backtick key concepts to [[wikilinks]]."""
    date_str = date_stem if re.match(r"\d{4}-\d{2}-\d{2}", date_stem) else ""

    fm_lines = ["---", "tags:", "  - curiopilot/briefing"]
    if date_str:
        fm_lines.append(f"date: {date_str}")
    fm_lines.append("---")
    fm_lines.append("")
    frontmatter = "\n".join(fm_lines)

    if content.startswith("---"):
        enhanced = content
    else:
        enhanced = frontmatter + content

    # Convert Key Concepts lines: backtick concepts → short-form wikilinks
    def replace_concepts(m: re.Match) -> str:
        raw = m.group(1)
        parts = re.findall(r"`([^`]+)`", raw)
        if not parts:
            return m.group(0)
        linked: list[str] = []
        for part in parts:
            normalized = _normalize_for_lookup(part)
            node_key = concept_lookup.get(normalized, None)
            if node_key is None:
                node_key = concept_lookup.get(normalized.replace(" ", ""), None)
            if node_key:
                fname = _filename(node_key)
                linked.append(f"[[{fname}|{part}]]")
            else:
                linked.append(f"`{part}`")
        prefix = re.match(r"(\*\*Key Concepts\*\*:\s*)", raw)
        prefix_str = prefix.group(1) if prefix else "**Key Concepts**: "
        return prefix_str + ", ".join(linked)

    enhanced = re.sub(
        r"(\*\*Key Concepts\*\*:.*)",
        replace_concepts,
        enhanced,
    )

    return enhanced


def _normalize_for_lookup(concept: str) -> str:
    """Rough normalization matching KnowledgeGraph._normalized() output."""
    text = concept.strip().lower()
    text = re.sub(r"[-_/]", " ", text)
    return text


def _write_index(
    kg: KnowledgeGraph,
    vault_dir: Path,
    by_category: dict[str, list[str]],
) -> None:
    """Write ``Knowledge Graph.md`` — overview index for the vault."""
    today = date_cls.today().isoformat()
    lines: list[str] = []

    lines.append("---")
    lines.append("tags:")
    lines.append("  - curiopilot/index")
    lines.append(f"updated: {today}")
    lines.append(f"total_nodes: {kg.node_count()}")
    lines.append(f"total_edges: {kg.edge_count()}")
    lines.append("---")
    lines.append("")
    lines.append("# Knowledge Graph")
    lines.append("")
    lines.append(
        f"**{kg.node_count()} concepts** · **{kg.edge_count()} connections**"
    )
    lines.append("")

    # ── Concepts by Domain ──────────────────────────────────────────
    lines.append("## Concepts by Domain")
    lines.append("")
    lines.append("| Domain | Concepts | Top Concept |")
    lines.append("|--------|----------|-------------|")
    for cat in sorted(by_category.keys()):
        nodes = by_category[cat]
        count = len(nodes)
        # Find top concept by familiarity
        top_node = max(nodes, key=lambda n: kg.graph.nodes[n].get("familiarity", 0))
        top_fam = kg.graph.nodes[top_node].get("familiarity", 0)
        cat_fname = _filename(cat)
        lines.append(
            f"| [[Concepts/{cat_fname}/_Category\\|{cat}]] "
            f"| {count} "
            f"| [[{_filename(top_node)}\\|{top_node}]] ({top_fam * 100:.0f}%) |"
        )
    lines.append("")

    nodes_all = list(kg.graph.nodes)

    # Top by familiarity
    by_familiarity = sorted(
        nodes_all,
        key=lambda n: kg.graph.nodes[n].get("familiarity", 0),
        reverse=True,
    )[:20]

    lines.append("## Top Concepts by Familiarity")
    lines.append("")
    lines.append("| Concept | Familiarity | Encounters | Connections |")
    lines.append("|---------|------------|------------|-------------|")
    for node in by_familiarity:
        attrs = kg.graph.nodes[node]
        fam = attrs.get("familiarity", 0)
        enc = attrs.get("encounter_count", 0)
        deg = kg.graph.degree(node)
        lines.append(
            f"| [[{_filename(node)}\\|{node}]] "
            f"| {fam * 100:.0f}% | {enc} | {deg} |"
        )
    lines.append("")

    # Top by connections
    by_degree = sorted(nodes_all, key=lambda n: kg.graph.degree(n), reverse=True)[:20]

    lines.append("## Top Concepts by Connections")
    lines.append("")
    lines.append("| Concept | Connections | Familiarity |")
    lines.append("|---------|------------|------------|")
    for node in by_degree:
        attrs = kg.graph.nodes[node]
        fam = attrs.get("familiarity", 0)
        deg = kg.graph.degree(node)
        lines.append(
            f"| [[{_filename(node)}\\|{node}]] "
            f"| {deg} | {fam * 100:.0f}% |"
        )
    lines.append("")

    # All concepts alphabetically
    lines.append("## All Concepts")
    lines.append("")
    for node in sorted(nodes_all):
        attrs = kg.graph.nodes[node]
        enc = attrs.get("encounter_count", 0)
        lines.append(f"- [[{_filename(node)}|{node}]] ({enc} encounters)")
    lines.append("")

    vault_dir.joinpath("Knowledge Graph.md").write_text("\n".join(lines), encoding="utf-8")


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
