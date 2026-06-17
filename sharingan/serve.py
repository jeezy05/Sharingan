"""
sharingan.serve — Model Context Protocol (MCP) Server for Sharingan.

Exposes the knowledge graph to AI coding assistants (Claude Code, Cursor, etc).
Uses FastMCP to define tools and resources.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from rich.console import Console

console = Console()

# Initialize FastMCP server
mcp = FastMCP("Sharingan")


def _get_project_root() -> Path:
    return Path(__file__).parent / "data"


def _get_indexes_dir() -> Path:
    return _get_project_root() / "indexes"


def _get_libraries_dir() -> Path:
    return _get_project_root() / "libraries"


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


@mcp.tool()
def list_libraries() -> str:
    """List all documentation libraries currently available in the Sharingan knowledge graph.
    
    Use this to see which libraries you can query.
    """
    libraries_dir = _get_libraries_dir()
    if not libraries_dir.exists():
        return "No libraries extracted yet. Please run 'sharingan extract <lib>' first."
    
    results = []
    for lib_dir in sorted(libraries_dir.iterdir()):
        if not lib_dir.is_dir():
            continue
        meta = _load_json(lib_dir / "meta.json")
        if meta and isinstance(meta, dict):
            name = meta.get("name", lib_dir.name)
            latest = meta.get("latest_version", "unknown")
            results.append(f"- {name} (ID: {lib_dir.name}, Latest: {latest})")
    
    if not results:
        return "No libraries found."
    return "Libraries available in Sharingan:\n" + "\n".join(results)


@mcp.tool()
def search_symbols(query: str, library_id: str | None = None) -> str:
    """Search for API symbols (functions, classes, types, components) across the knowledge graph.
    
    Args:
        query: The symbol name or keyword to search for (e.g., 'useRouter', 'createServer').
        library_id: (Optional) Filter results to a specific library (e.g., 'nextjs', 'nodejs').
    """
    indexes_dir = _get_indexes_dir()
    symbol_index_path = indexes_dir / "by-symbol-name.json"
    
    symbol_index = _load_json(symbol_index_path)
    if not symbol_index or not isinstance(symbol_index, dict):
        return "Indexes not found. Please run 'sharingan extract' first."

    query_lower = query.lower()
    matches = []
    for name, ids in symbol_index.items():
        if query_lower in name.lower():
            for sym_id in ids:
                if library_id and not sym_id.startswith(f"{library_id}@"):
                    continue
                matches.append({"name": name, "id": sym_id})

    if not matches:
        lib_filter = f" in library '{library_id}'" if library_id else ""
        return f"No symbols found matching '{query}'{lib_filter}."

    # Load and format the top 10 matching symbols
    libraries_dir = _get_libraries_dir()
    results = []
    
    for match in matches[:10]:
        sym_id = match["id"]
        parts = sym_id.split("::")
        lib_ver = parts[0] if parts else ""
        lib_id = lib_ver.split("@")[0] if "@" in lib_ver else lib_ver
        ver = lib_ver.split("@")[1] if "@" in lib_ver else ""

        symbols_path = libraries_dir / lib_id / "versions" / ver / "symbols.json"
        symbols = _load_json(symbols_path)
        
        found = False
        if symbols and isinstance(symbols, list):
            for sym in symbols:
                if sym.get("id") == sym_id:
                    results.append(
                        f"## {sym.get('name')} ({sym.get('kind', 'symbol')})\n"
                        f"**Library**: {lib_id} v{ver}\n"
                        f"**Signature**: `{sym.get('signature', '')}`\n"
                        f"**Description**: {sym.get('description', '')}\n"
                    )
                    found = True
                    break
        
        if not found:
            results.append(f"- {match['name']} ({sym_id})")

    response = f"Found {len(matches)} results for '{query}'. Showing top 10:\n\n"
    return response + "\n".join(results)


@mcp.tool()
def get_symbol_details(symbol_id: str) -> str:
    """Get the full, detailed documentation for a specific API symbol using its exact ID.
    
    Args:
        symbol_id: The exact ID of the symbol (e.g., 'nextjs@15.3.2::next/router::useRouter').
    """
    parts = symbol_id.split("::")
    if not parts:
        return f"Invalid symbol ID format: {symbol_id}"
        
    lib_ver = parts[0]
    lib_id = lib_ver.split("@")[0] if "@" in lib_ver else lib_ver
    ver = lib_ver.split("@")[1] if "@" in lib_ver else ""

    libraries_dir = _get_libraries_dir()
    symbols_path = libraries_dir / lib_id / "versions" / ver / "symbols.json"
    symbols = _load_json(symbols_path)
    
    if not symbols or not isinstance(symbols, list):
        return f"Could not find library data for {lib_id} v{ver}"

    for sym in symbols:
        if sym.get("id") == symbol_id:
            # Format the full symbol detail
            out = [
                f"# {sym.get('name')} ({sym.get('kind', 'symbol')})",
                f"**Library**: {lib_id} v{ver}",
                f"**Module**: {sym.get('module_path', '')}",
                f"\n## Signature\n```typescript\n{sym.get('signature', '')}\n```",
                f"\n## Description\n{sym.get('description', '')}",
            ]
            
            params = sym.get("parameters", [])
            if params:
                out.append("\n## Parameters")
                for p in params:
                    req = "" if p.get("required", True) else "(Optional) "
                    out.append(f"- **{p.get('name')}**: `{p.get('type', 'any')}` - {req}{p.get('description', '')}")
                    
            ret = sym.get("return_type", "")
            if ret:
                out.append(f"\n## Returns\n`{ret}`")
                
            dep = sym.get("deprecated")
            if dep:
                dep_by = sym.get("deprecated_by")
                by_str = f" Use {dep_by} instead." if dep_by else ""
                out.append(f"\n> ⚠️ **DEPRECATED**{by_str}")
                
            return "\n".join(out)

    return f"Symbol {symbol_id} not found."


@mcp.tool()
def get_neighbors(node_id: str) -> str:
    """Get all related symbols and guides connected to a specific node in the knowledge graph.
    
    Args:
        node_id: The exact ID of the node (symbol or guide) to find relations for.
    """
    parts = node_id.split("::")
    if not parts:
        return f"Invalid node ID format: {node_id}"
        
    lib_ver = parts[0]
    lib_id = lib_ver.split("@")[0] if "@" in lib_ver else lib_ver
    ver = lib_ver.split("@")[1] if "@" in lib_ver else ""

    libraries_dir = _get_libraries_dir()
    edges_path = libraries_dir / lib_id / "versions" / ver / "edges.json"
    edges = _load_json(edges_path)
    
    if not edges or not isinstance(edges, list):
        return f"Could not find edge data for {lib_id} v{ver}"

    relations = []
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        edge_type = edge.get("type", "RELATED_TO")
        
        if source == node_id:
            relations.append(f"- **{edge_type}** → {target}")
        elif target == node_id:
            relations.append(f"- ← **{edge_type}** from {source}")

    if not relations:
        return f"No known relationships found for {node_id}."
        
    return f"Relationships for {node_id}:\n\n" + "\n".join(relations)


def start() -> None:
    """Start the FastMCP server with stdio transport."""
    console.print("[cyan]Starting Sharingan MCP Server (stdio)...[/]")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    start()
