"""
sharingan.build — Build NetworkX knowledge graph from extractions.

Graphify-inspired: takes a list of extraction dicts and merges them
into a single nx.Graph with typed nodes and edges.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
from rich.console import Console

from sharingan.extract import ExtractedEdge, ExtractedNode, ExtractionResult

console = Console()


def build_graph(
    extractions: list[ExtractionResult],
    library_id: str,
    version_id: str,
    library_meta: dict[str, Any] | None = None,
) -> nx.DiGraph:
    """Build a NetworkX directed graph from extraction results.

    Args:
        extractions: List of ExtractionResult from all pages.
        library_id: Library identifier (e.g., "nextjs").
        version_id: Version identifier (e.g., "nextjs@15.3.2").
        library_meta: Optional library metadata to include as root node.

    Returns:
        NetworkX DiGraph with all nodes and edges.
    """
    G = nx.DiGraph()

    # Add library root node
    if library_meta:
        G.add_node(
            library_id,
            node_type="library",
            **{k: v for k, v in library_meta.items() if k not in ("docs_config", "node_type")},
        )

    # Add version node
    G.add_node(
        version_id,
        node_type="version",
        id=version_id,
        library_id=library_id,
        is_latest=True,
    )
    G.add_edge(library_id, version_id, type="HAS_VERSION", confidence="EXTRACTED")

    # Name → ID mapping for resolving edge references
    name_to_id: dict[str, str] = {}

    # Collect all nodes from all pages
    all_nodes: list[ExtractedNode] = []
    all_edges: list[ExtractedEdge] = []

    for extraction in extractions:
        all_nodes.extend(extraction.nodes)
        all_edges.extend(extraction.edges)

    # Add nodes to graph
    for node in all_nodes:
        node_id = node.id
        G.add_node(node_id, **node.data)

        # Track name → ID mapping
        name = node.data.get("name", "")
        if name:
            name_to_id[name] = node_id

        # Add structural edges based on node type
        if node.node_type == "symbol":
            G.add_edge(version_id, node_id, type="EXPORTS", confidence="EXTRACTED")
        elif node.node_type == "guide":
            G.add_edge(version_id, node_id, type="HAS_GUIDE", confidence="EXTRACTED")
            # Add REFERENCES edges from guide to related symbols
            for sym_id in node.data.get("related_symbols", []):
                if G.has_node(sym_id):
                    G.add_edge(
                        node_id, sym_id,
                        type="REFERENCES",
                        confidence="EXTRACTED",
                    )
        elif node.node_type == "config":
            G.add_edge(version_id, node_id, type="HAS_CONFIG", confidence="EXTRACTED")

    # Resolve and add semantic edges
    for edge in all_edges:
        source_id = name_to_id.get(edge.source, edge.source)
        target_id = name_to_id.get(edge.target, edge.target)

        # Only add edge if both nodes exist
        if G.has_node(source_id) and G.has_node(target_id):
            G.add_edge(
                source_id,
                target_id,
                type=edge.edge_type,
                confidence=edge.confidence,
                confidence_score=edge.confidence_score,
                description=edge.description,
            )
        elif source_id != edge.source or target_id != edge.target:
            # At least one was resolved, skip if target not found
            pass

    console.print(
        f"[green]✓ Graph built: {G.number_of_nodes()} nodes, "
        f"{G.number_of_edges()} edges[/]"
    )

    return G


def graph_to_json(G: nx.DiGraph) -> dict[str, Any]:
    """Convert NetworkX graph to JSON-serializable dict.

    Format compatible with Graphify's graph.json.
    """
    nodes = []
    for node_id, data in G.nodes(data=True):
        node_data = dict(data)
        node_data["id"] = node_id
        nodes.append(node_data)

    edges = []
    for source, target, data in G.edges(data=True):
        edge_data = dict(data)
        edge_data["source"] = source
        edge_data["target"] = target
        edges.append(edge_data)

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "format": "sharingan_v1",
        },
    }


def json_to_graph(data: dict[str, Any]) -> nx.DiGraph:
    """Load a graph from JSON dict."""
    G = nx.DiGraph()
    for node in data.get("nodes", []):
        node_id = node.pop("id")
        G.add_node(node_id, **node)
    for edge in data.get("edges", []):
        source = edge.pop("source")
        target = edge.pop("target")
        G.add_edge(source, target, **edge)
    return G


def export_graph(
    G: nx.DiGraph,
    output_dir: Path,
    version_id: str,
) -> None:
    """Export graph to JSON files in the standard Sharingan directory structure.

    Writes:
    - graph.json — full graph
    - symbols.json — all API symbol nodes
    - guides.json — all guide nodes
    - config.json — all config option nodes
    - edges.json — all edges with confidence
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Full graph
    graph_data = graph_to_json(G)
    with open(output_dir / "graph.json", "w") as f:
        json.dump(graph_data, f, indent=2)

    # Split by node type
    symbols = []
    guides = []
    configs = []
    edges = []

    for node_id, data in G.nodes(data=True):
        node_data = dict(data)
        node_data["id"] = node_id
        node_type = data.get("node_type", "")
        if node_type == "symbol":
            symbols.append(node_data)
        elif node_type == "guide":
            guides.append(node_data)
        elif node_type == "config":
            configs.append(node_data)

    for source, target, data in G.edges(data=True):
        edge_data = dict(data)
        edge_data["source"] = source
        edge_data["target"] = target
        edges.append(edge_data)

    with open(output_dir / "symbols.json", "w") as f:
        json.dump(symbols, f, indent=2)

    with open(output_dir / "guides.json", "w") as f:
        json.dump(guides, f, indent=2)

    with open(output_dir / "config.json", "w") as f:
        json.dump(configs, f, indent=2)

    with open(output_dir / "edges.json", "w") as f:
        json.dump(edges, f, indent=2)

    # Version metadata
    version_data = {
        "id": version_id,
        "library_id": version_id.split("@")[0] if "@" in version_id else "",
        "semver": version_id.split("@")[1] if "@" in version_id else version_id,
        "is_latest": True,
        "node_type": "version",
        "stats": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "symbols": len(symbols),
            "guides": len(guides),
            "configs": len(configs),
        },
    }
    with open(output_dir / "version.json", "w") as f:
        json.dump(version_data, f, indent=2)

    console.print(
        f"[green]✓ Exported to {output_dir}: "
        f"{len(symbols)} symbols, {len(guides)} guides, "
        f"{len(configs)} configs, {len(edges)} edges[/]"
    )


def build_indexes(
    libraries_dir: Path,
    indexes_dir: Path,
) -> None:
    """Build global search indexes across all libraries.

    Creates:
    - by-symbol-name.json — symbol name → list of full IDs
    - by-category.json — category → list of library IDs
    - by-language.json — language → list of library IDs
    """
    indexes_dir.mkdir(parents=True, exist_ok=True)

    by_symbol: dict[str, list[str]] = {}
    by_category: dict[str, list[str]] = {}
    by_language: dict[str, list[str]] = {}

    if not libraries_dir.exists():
        return

    for lib_dir in sorted(libraries_dir.iterdir()):
        if not lib_dir.is_dir():
            continue

        # Read library meta
        meta_path = lib_dir / "meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            lib_id = meta.get("id", lib_dir.name)
            category = meta.get("category", "")
            language = meta.get("language", "")

            if category:
                by_category.setdefault(category, []).append(lib_id)
            if language:
                by_language.setdefault(language, []).append(lib_id)

        # Read symbols from all versions
        versions_dir = lib_dir / "versions"
        if not versions_dir.exists():
            continue

        for ver_dir in sorted(versions_dir.iterdir()):
            if not ver_dir.is_dir():
                continue
            symbols_path = ver_dir / "symbols.json"
            if symbols_path.exists():
                with open(symbols_path) as f:
                    symbols = json.load(f)
                for sym in symbols:
                    name = sym.get("name", "")
                    sym_id = sym.get("id", "")
                    if name and sym_id:
                        by_symbol.setdefault(name, []).append(sym_id)

    with open(indexes_dir / "by-symbol-name.json", "w") as f:
        json.dump(by_symbol, f, indent=2, sort_keys=True)

    with open(indexes_dir / "by-category.json", "w") as f:
        json.dump(by_category, f, indent=2, sort_keys=True)

    with open(indexes_dir / "by-language.json", "w") as f:
        json.dump(by_language, f, indent=2, sort_keys=True)

    console.print(
        f"[green]✓ Indexes built: {len(by_symbol)} symbol names, "
        f"{len(by_category)} categories, {len(by_language)} languages[/]"
    )
