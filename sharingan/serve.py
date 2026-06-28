"""
sharingan.serve — Model Context Protocol (MCP) Server for Sharingan.

Exposes the knowledge graph to AI coding assistants (Claude Code, Cursor, etc).
Uses FastMCP to define tools and resources.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from sharingan.config import get_libraries_dir, get_cache_dir, migrate_legacy_data
from sharingan.search import hybrid_graph_search, _find_library_dir, _load_json
from sharingan.scanner import scan_project_dependencies

# Ensure legacy data is migrated
migrate_legacy_data()

# Initialize FastMCP server
mcp = FastMCP("Sharingan")


def _get_all_library_dirs() -> list[Path]:
    dirs = []
    for base in [get_libraries_dir(), get_cache_dir() / "libraries"]:
        if base.exists():
            dirs.extend([d for d in base.iterdir() if d.is_dir()])
    return dirs


@mcp.tool()
def list_libraries() -> str:
    """List all documentation libraries available in the Sharingan knowledge graph.

    Use this to see which libraries you can query. If a library is listed as 
    (Not Downloaded), you MUST use the `extract_library_docs` tool to fetch it 
    from the cloud before querying it.
    """
    from sharingan.discover import load_registry
    
    registry = load_registry()
    available_libs = registry.get("libraries", {})
    
    # Get locally cached ones
    local_dirs = {d.name: d for d in _get_all_library_dirs()}
    
    results = []
    for lib_id, info in sorted(available_libs.items()):
        name = info.get("name", lib_id)
        latest = info.get("latest_version", "unknown")
        
        status = "✅ Cached Locally" if lib_id in local_dirs else "☁️ Cloud (Requires extract_library_docs)"
        results.append(f"- {name} (ID: {lib_id}, Latest: {latest}) - {status}")
        
    if not results:
        return "No libraries found in registry."
        
    return "Libraries available in Sharingan ecosystem:\n" + "\n".join(results)


@mcp.tool()
def ask_sharingan(query: str, library_id: str) -> str:
    """MASTER TOOL: Get comprehensive documentation for a library.

    If the user's project (package.json/pyproject.toml) uses a specific
    framework, ALWAYS call this tool first to get the official rules
    and syntax before attempting to write code for it.

    For small libraries, this returns the entire documentation.
    For large libraries, provide explicit keywords or symbol names
    (e.g., 'AppRouter', 'middleware') to deterministically fetch
    the exact API references and their related tutorials.
    """
    return hybrid_graph_search(query, library_id)


@mcp.tool()
def scan_dependencies(directory: str = ".") -> str:
    """Scan the user's project directory to find which dependencies are available in Sharingan.

    Call this tool FIRST whenever you start working on a new repository or project.
    It will tell you exactly which libraries you can query via `ask_sharingan`, and
    which ones you need to fall back to web search for.
    """
    return scan_project_dependencies(directory)


@mcp.tool()
async def extract_library_docs(library_id: str, version: str | None = None) -> str:
    """Extract documentation for a library on-the-fly if it is missing.

    Use this if you need documentation for a library that is not yet extracted locally.
    Args:
        library_id: The ID of the library from the Sharingan registry (e.g., 'zod', 'fastapi').
        version: Optional specific version (defaults to latest).
    """
    import asyncio

    cmd = ["sharingan", "extract", library_id, "--skip-llm"]
    if version:
        cmd.extend(["--version", version])

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        return f"Successfully extracted documentation for {library_id}."
    else:
        return f"Failed to extract {library_id}. Exit code {process.returncode}.\nError:\n{stderr.decode()}"


def start() -> None:
    """Start the FastMCP server with stdio transport.

    CRITICAL: For stdio transport, absolutely NOTHING except valid JSON-RPC
    may be written to stdout. All status messages go to stderr.
    """
    sys.stderr.write("Starting Sharingan MCP Server (stdio)...\n")
    logging.disable(logging.CRITICAL)
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    start()
