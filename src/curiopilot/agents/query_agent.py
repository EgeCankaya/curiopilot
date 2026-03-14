"""Knowledge query agent -- synthesizes past knowledge in response to a question (FR-35/36)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from curiopilot.config import AppConfig
from curiopilot.llm.ollama import OllamaClient
from curiopilot.storage.knowledge_graph import KnowledgeGraph
from curiopilot.storage.vector_store import VectorStore

log = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Structured answer returned by the query agent."""

    answer: str
    source_articles: list[dict] = field(default_factory=list)
    related_concepts: list[str] = field(default_factory=list)
    graph_context: str = ""


async def query_knowledge(
    question: str,
    config: AppConfig,
    client: OllamaClient,
    vector_store: VectorStore,
    knowledge_graph: KnowledgeGraph,
    *,
    top_k: int = 10,
) -> QueryResult:
    """Embed a user question, retrieve relevant past knowledge, and synthesize an answer.

    Steps:
      1. Embed the query via Ollama.
      2. Retrieve top-k most relevant past article summaries from ChromaDB.
      3. Retrieve related graph nodes and connections.
      4. Pass everything to the reader model with a synthesis prompt.
      5. Return a structured knowledge snapshot with source references.
    """
    model = config.models.embedding_model
    reader_model = config.models.reader_model

    # 1. Embed the query
    log.info("Embedding query: %s", question[:80])
    query_embedding = await client.embed(model, question, keep_alive="5m")

    # 2. Retrieve similar articles from ChromaDB
    neighbors = vector_store.query_similar(query_embedding, k=top_k)
    log.info("Found %d relevant past articles", len(neighbors))

    source_articles = []
    context_snippets: list[str] = []
    for i, n in enumerate(neighbors):
        meta = n.get("metadata", {})
        title = meta.get("title", "Unknown")
        source = meta.get("source", "")
        doc = n.get("document", "")
        similarity = n.get("similarity", 0)

        source_articles.append({
            "title": title,
            "url": n.get("id", ""),
            "source": source,
            "similarity": round(similarity, 3),
        })

        context_snippets.append(
            f"[Article {i + 1}] \"{title}\" (similarity: {similarity:.2f})\n{doc}"
        )

    # 3. Retrieve graph context
    graph_context = _build_graph_context(question, knowledge_graph)

    # 4. Synthesize with the reader model
    if not context_snippets:
        return QueryResult(
            answer="No relevant articles found in your knowledge base yet. "
                   "Run the pipeline first to build up your knowledge.",
            source_articles=source_articles,
            related_concepts=[],
            graph_context=graph_context,
        )

    # Swap to reader model for synthesis
    log.info("Swapping to reader model for synthesis")
    await client.swap_model(model, reader_model)

    prompt = _build_synthesis_prompt(question, context_snippets, graph_context)
    answer = await client.generate_text(reader_model, prompt, keep_alive="5m")

    related_concepts = _extract_related_concepts(question, knowledge_graph)

    return QueryResult(
        answer=answer.strip(),
        source_articles=source_articles,
        related_concepts=related_concepts,
        graph_context=graph_context,
    )


def _build_graph_context(question: str, kg: KnowledgeGraph) -> str:
    """Extract relevant knowledge graph information for the query."""
    if kg.node_count() == 0:
        return ""

    words = [w.strip().lower() for w in question.split() if len(w.strip()) > 3]
    relevant_nodes: list[str] = []

    for node in kg.graph.nodes:
        node_lower = node.lower()
        if any(w in node_lower or node_lower in w for w in words):
            relevant_nodes.append(node)

    if not relevant_nodes:
        return ""

    lines: list[str] = []
    for node in relevant_nodes[:8]:
        attrs = kg.graph.nodes[node]
        neighbors = list(kg.graph.neighbors(node))[:5]
        neighbor_str = ", ".join(neighbors) if neighbors else "none"
        lines.append(
            f"- {node}: encountered {attrs.get('encounter_count', 0)} time(s), "
            f"familiarity {attrs.get('familiarity', 0):.1f}, "
            f"connected to [{neighbor_str}]"
        )

    return "\n".join(lines)


def _build_synthesis_prompt(
    question: str,
    context_snippets: list[str],
    graph_context: str,
) -> str:
    articles_block = "\n\n".join(context_snippets)

    graph_block = ""
    if graph_context:
        graph_block = (
            "\n\n--- KNOWLEDGE GRAPH CONTEXT ---\n"
            f"{graph_context}\n"
            "--- END GRAPH ---"
        )

    return (
        "You are a knowledgeable research assistant. The user has been building "
        "a personal knowledge base by reading articles daily. Based on what they "
        "have read before (provided below), answer their question with a comprehensive "
        "synthesis.\n\n"
        "Rules:\n"
        "- Reference specific articles by their number (e.g., [Article 1]).\n"
        "- If the knowledge base doesn't cover something, say so honestly.\n"
        "- Be concise but thorough -- aim for 3-6 paragraphs.\n"
        "- Highlight connections between different articles.\n\n"
        f"QUESTION: {question}\n\n"
        "--- RELEVANT ARTICLES FROM YOUR KNOWLEDGE BASE ---\n"
        f"{articles_block}\n"
        "--- END ARTICLES ---"
        f"{graph_block}\n\n"
        "Provide your synthesis:"
    )


def _extract_related_concepts(question: str, kg: KnowledgeGraph) -> list[str]:
    """Find graph concepts related to the query."""
    if kg.node_count() == 0:
        return []

    words = {w.strip().lower() for w in question.split() if len(w.strip()) > 3}
    related: set[str] = set()

    for node in kg.graph.nodes:
        if any(w in node.lower() or node.lower() in w for w in words):
            related.add(node)
            for neighbor in kg.graph.neighbors(node):
                related.add(neighbor)

    return sorted(related)[:15]
