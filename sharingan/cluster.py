"""
sharingan.cluster — Graph Clustering via Leiden/Louvain algorithm.

Groups highly connected API symbols and guides into logical "communities"
(e.g., "Routing APIs", "Authentication Hooks").
Uses NetworkX Louvain communities (an approximation of Leiden) for pure-Python
compatibility, then uses the LLM to generate a descriptive name for the cluster.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
from rich.console import Console

from sharingan.extract import call_llm, detect_backend

console = Console()

CLUSTER_PROMPT = """You are an expert technical writer and software architect.
I am providing you with a list of API symbols and documentation guides that belong to a highly connected "community" or "cluster" within a library's knowledge graph.

Your task is to provide a concise, descriptive name and a short summary for this cluster.

Here are the items in the cluster:
{items}

Output ONLY valid JSON matching this schema:
{{
  "cluster_name": "string (e.g. 'Routing Hooks', 'Data Fetching', 'Core Types')",
  "summary": "string (1-2 sentences describing what this cluster of APIs handles)"
}}"""


async def detect_communities(
    G: nx.DiGraph,
    min_size: int = 3,
) -> list[list[str]]:
    """Detect communities in the graph using Louvain algorithm.
    
    Louvain is used here as a pure-Python compatible alternative to Leiden,
    which requires compiling C++ igraph bindings.
    """
    # Louvain requires an undirected graph
    G_undirected = G.to_undirected()
    
    # Remove nodes that don't have edges or are meta-nodes
    nodes_to_cluster = [
        n for n, attr in G_undirected.nodes(data=True)
        if attr.get("node_type") in ("symbol", "guide")
    ]
    subgraph = G_undirected.subgraph(nodes_to_cluster)
    
    if len(subgraph) < min_size:
        return []
        
    try:
        from networkx.algorithms.community import louvain_communities
        communities = louvain_communities(subgraph, resolution=1.0)
    except Exception as e:
        console.print(f"[red]Community detection failed: {e}[/]")
        return []
        
    # Filter out very small clusters
    return [list(c) for c in communities if len(c) >= min_size]


async def label_cluster(
    cluster_nodes: list[str],
    G: nx.DiGraph,
    backend: str | None = None,
) -> dict[str, Any]:
    """Use LLM to generate a name and summary for a cluster."""
    if backend == "none" or (backend is None and detect_backend() == "none"):
        return {
            "name": f"Cluster ({len(cluster_nodes)} nodes)",
            "summary": "Community of related API symbols.",
            "nodes": cluster_nodes,
        }

    items = []
    for node_id in cluster_nodes[:20]:  # limit to top 20 to save context
        data = G.nodes[node_id]
        kind = data.get("kind", data.get("node_type", "unknown"))
        name = data.get("name", data.get("title", node_id))
        items.append(f"- {name} ({kind})")
        
    prompt = CLUSTER_PROMPT.format(items="\n".join(items))
    
    try:
        response = await call_llm(prompt, system="", backend=backend)
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        result = json.loads(text)
        return {
            "name": result.get("cluster_name", "Unknown Cluster"),
            "summary": result.get("summary", ""),
            "nodes": cluster_nodes,
        }
    except Exception as e:
        console.print(f"[yellow]Failed to label cluster: {e}[/]")
        return {
            "name": f"Cluster ({len(cluster_nodes)} nodes)",
            "summary": "",
            "nodes": cluster_nodes,
        }


async def cluster_library(
    library_id: str,
    version_id: str,
    backend: str | None = None,
) -> None:
    """Run community detection and LLM labeling on an extracted library."""
    from sharingan.build import json_to_graph
    from sharingan.config import get_libraries_dir
    
    lib_id = version_id.split("@")[0] if "@" in version_id else version_id
    ver = version_id.split("@")[1] if "@" in version_id else ""
    
    version_dir = get_libraries_dir() / lib_id / "versions" / ver
    graph_path = version_dir / "graph.json"
    
    if not graph_path.exists():
        console.print(f"[red]Graph not found at {graph_path}[/]")
        return
        
    with open(graph_path, encoding="utf-8") as f:
        graph_data = json.load(f)
        
    G = json_to_graph(graph_data)
    
    console.print(f"[cyan]Detecting communities in {version_id}...[/]")
    communities = await detect_communities(G)
    console.print(f"[green]✓ Found {len(communities)} clusters[/]")
    
    if not communities:
        return
        
    llm_backend = backend or detect_backend()
    console.print(f"[cyan]Labeling clusters via LLM ({llm_backend})...[/]")
    
    clusters = []
    for i, comm in enumerate(communities):
        console.print(f"  [{i+1}/{len(communities)}] Labeling cluster of {len(comm)} nodes...", end="")
        labeled = await label_cluster(comm, G, llm_backend)
        clusters.append({
            "id": f"{version_id}::cluster::{i}",
            "library_id": lib_id,
            "version_id": version_id,
            "name": labeled["name"],
            "summary": labeled["summary"],
            "node_count": len(comm),
            "nodes": comm,
        })
        console.print(f" → {labeled['name']}")
        
    # Export clusters
    out_path = version_dir / "clusters.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(clusters, f, indent=2)
        
    console.print(f"[green]✓ Saved {len(clusters)} clusters to {out_path}[/]")
