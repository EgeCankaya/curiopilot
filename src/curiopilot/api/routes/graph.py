"""Knowledge graph API route for visualization."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query

from curiopilot.api.deps import get_config
from curiopilot.api.schemas import GraphEdge, GraphNode, GraphResponse

router = APIRouter(tags=["graph"])


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    max_nodes: int = Query(default=200, ge=1, le=2000),
    config=Depends(get_config),
):
    """Return knowledge graph data for visualization."""
    from curiopilot.storage.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph(config.paths.graph_path)
    kg.load()

    g = kg.graph
    total_nodes = g.number_of_nodes()
    total_edges = g.number_of_edges()

    # Select top nodes by degree
    degree_map = dict(g.degree())
    sorted_nodes = sorted(degree_map, key=degree_map.get, reverse=True)[:max_nodes]
    node_set = set(sorted_nodes)

    nodes = []
    for node_id in sorted_nodes:
        attrs = g.nodes[node_id]
        nodes.append(GraphNode(
            id=str(node_id),
            label=attrs.get("label", str(node_id)),
            familiarity=attrs.get("familiarity", 0.0),
            encounter_count=attrs.get("encounter_count", 0),
            degree=degree_map.get(node_id, 0),
        ))

    edges = []
    for u, v, data in g.edges(data=True):
        if u in node_set and v in node_set:
            edges.append(GraphEdge(
                source=str(u),
                target=str(v),
                relationship_type=data.get("relationship_type", "co_occurrence"),
            ))

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        total_nodes=total_nodes,
        total_edges=total_edges,
    )
