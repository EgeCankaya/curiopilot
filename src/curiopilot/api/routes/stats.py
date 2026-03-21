"""Stats API route."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from curiopilot.api.deps import get_config, get_url_store
from curiopilot.api.schemas import StatsResponse
from curiopilot.storage.url_store import URLStore

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    url_store: URLStore = Depends(get_url_store),
    config=Depends(get_config),
):
    from curiopilot.storage.knowledge_graph import KnowledgeGraph
    from curiopilot.storage.vector_store import VectorStore

    url_stats = await url_store.url_stats()

    db_dir = Path(config.paths.database_dir)
    chroma_dir = db_dir / "chromadb"
    vec_count = 0
    if chroma_dir.exists():
        vs = VectorStore(chroma_dir)
        vs.open()
        vec_count = vs.count()

    kg = KnowledgeGraph(config.paths.graph_path)
    kg.load()

    result = StatsResponse(
        urls_visited=url_stats["total_urls"],
        urls_passed_relevance=url_stats["passed_relevance"],
        sources_seen=url_stats["sources"],
        article_embeddings=vec_count,
        graph_nodes=kg.node_count(),
        graph_edges=kg.edge_count(),
    )

    if kg.node_count() > 0:
        topic, edges = kg.most_connected_topic()
        result.most_connected_topic = topic
        result.most_connected_edges = edges

    return result
