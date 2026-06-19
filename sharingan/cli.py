"""
sharingan.cli — Command-line interface for Sharingan.

Usage:
    sharingan extract <library> [--version VER] [--update] [--skip-llm] [--backend BACKEND]
    sharingan list
    sharingan info <library>
    sharingan query <question> [--lib LIBRARY]
    sharingan install [--platform PLATFORM]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from sharingan.config import get_data_dir, get_indexes_dir, get_libraries_dir

console = Console()


@click.group()
@click.version_option(version=None, prog_name="sharingan", package_name="sharingan-ai")
def main() -> None:
    """Sharingan — Open-source documentation knowledge graph.

    Turn the latest documentation of popular tech stacks into a queryable
    knowledge graph. Plugin for Claude Code, Codex, Cursor, and more.
    """


@main.command()
@click.argument("library")
@click.option("--version", "-v", default=None, help="Specific version to extract.")
@click.option("--update", is_flag=True, help="Only re-extract changed pages.")
@click.option("--skip-llm", is_flag=True, help="Skip Pass 2 (LLM extraction).")
@click.option(
    "--backend",
    type=click.Choice(["anthropic", "openai", "ollama"]),
    default=None,
    help="LLM backend (auto-detected if not specified).",
)
@click.option("--output", "-o", type=click.Path(), default=None, help="Output directory.")
def extract(
    library: str,
    version: str | None,
    update: bool,
    skip_llm: bool,
    backend: str | None,
    output: str | None,
) -> None:
    """Extract documentation for a library into the knowledge graph.

    Examples:
        sharingan extract zod
        sharingan extract nextjs --version 15.3.2
        sharingan extract react --skip-llm
        sharingan extract fastapi --backend ollama --update
    """
    from sharingan.pipeline import extract_library

    output_path = Path(output) if output else None

    result = asyncio.run(
        extract_library(
            library_id=library,
            version=version,
            output_dir=output_path,
            update_only=update,
            skip_llm=skip_llm,
            backend=backend,
        )
    )

    if result.get("status") == "error":
        console.print(f"[red]✗ Extraction failed: {result.get('message')}[/]")
        sys.exit(1)


@main.command("list")
def list_libraries() -> None:
    """List all libraries in the registry."""
    from sharingan.discover import list_libraries as _list

    libraries = _list()

    table = Table(title="Sharingan Library Registry")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Category", style="green")
    table.add_column("Language", style="yellow")
    table.add_column("Latest Version")

    for lib in libraries:
        table.add_row(
            lib["id"],
            lib["name"],
            lib["category"],
            lib["language"],
            lib["latest_version"],
        )

    console.print(table)


@main.command()
@click.argument("library")
def info(library: str) -> None:
    """Show detailed info for a library."""
    from sharingan.discover import discover_library

    try:
        source = discover_library(library)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)

    console.print(f"[bold cyan]{source.library_name}[/] v{source.version}")
    console.print(f"  Category:  {source.category}")
    console.print(f"  Language:  {source.language}")
    console.print(f"  Docs URL:  {source.docs_url}")
    console.print(f"  Repo:      {source.repo}")
    console.print(f"  Source:    {source.source_type}")
    console.print(f"  Tags:      {', '.join(source.tags)}")

    # Check if already extracted
    lib_dir = get_libraries_dir() / source.library_id
    if lib_dir.exists():
        versions = []
        versions_dir = lib_dir / "versions"
        if versions_dir.exists():
            versions = sorted(
                [d.name for d in versions_dir.iterdir() if d.is_dir()],
                reverse=True,
            )
        if versions:
            console.print(f"  Extracted: {', '.join(versions)}")
        else:
            console.print("  Extracted: [yellow]Not yet[/]")
    else:
        console.print("  Extracted: [yellow]Not yet[/]")


@main.command()
@click.argument("question")
@click.option("--lib", "-l", default=None, help="Filter to specific library.")
@click.option("--version", "-v", default=None, help="Specific version.")
def query(question: str, lib: str | None, version: str | None) -> None:
    """Query the knowledge graph.

    Examples:
        sharingan query "useRouter signature"
        sharingan query "server components" --lib react
        sharingan query "z.string methods" --lib zod
    """
    indexes_dir = get_indexes_dir()

    # Simple keyword search across symbol names
    symbol_index_path = indexes_dir / "by-symbol-name.json"
    if not symbol_index_path.exists():
        console.print("[yellow]No indexes found. Run 'sharingan extract' first.[/]")
        sys.exit(1)

    with open(symbol_index_path) as f:
        symbol_index = json.load(f)

    # Search for matching symbol names
    query_lower = question.lower()
    matches = []
    for name, ids in symbol_index.items():
        if query_lower in name.lower():
            for sym_id in ids:
                if lib and not sym_id.startswith(lib):
                    continue
                matches.append({"name": name, "id": sym_id})

    if not matches:
        console.print(f"[yellow]No results found for '{question}'[/]")
        return

    # Load and display matching symbols
    table = Table(title=f"Results for: {question}")
    table.add_column("Name", style="cyan")
    table.add_column("Kind", style="green")
    table.add_column("Signature")
    table.add_column("Library", style="yellow")

    for match in matches[:20]:
        # Try to load the full symbol data
        sym_id = match["id"]
        parts = sym_id.split("::")
        lib_ver = parts[0] if parts else ""
        lib_id = lib_ver.split("@")[0] if "@" in lib_ver else lib_ver
        ver = lib_ver.split("@")[1] if "@" in lib_ver else ""

        symbols_path = (
            get_libraries_dir() / lib_id / "versions" / ver / "symbols.json"
        )
        if symbols_path.exists():
            with open(symbols_path) as f:
                symbols = json.load(f)
            for sym in symbols:
                if sym.get("id") == sym_id:
                    table.add_row(
                        sym.get("name", match["name"]),
                        sym.get("kind", ""),
                        sym.get("signature", "")[:60],
                        f"{lib_id}@{ver}",
                    )
                    break
        else:
            table.add_row(match["name"], "", "", lib_ver)

    console.print(table)


@main.command()
@click.option(
    "--platform",
    type=click.Choice([
        "claude", "codex", "cursor", "gemini", "antigravity",
        "opencode", "copilot", "aider",
    ]),
    default=None,
    help="Target platform (auto-detect if not specified).",
)
@click.option("--project", is_flag=True, hidden=True, help="Deprecated — all installs are project-scoped.")
def install(platform: str | None, project: bool) -> None:
    """Install Sharingan skill into your AI coding assistant.

    Installs into the current project directory. Run this from your project root.

    Examples:
        sharingan install
        sharingan install --platform claude
        sharingan install --platform cursor
    """
    from sharingan.skills import install_skill

    install_skill(platform)


@main.command()
@click.argument("library")
@click.option("--version", "-v", default=None, help="Specific version to cluster (uses latest if not set).")
@click.option(
    "--backend",
    type=click.Choice(["anthropic", "openai", "ollama"]),
    default=None,
    help="LLM backend for naming clusters.",
)
def cluster(library: str, version: str | None, backend: str | None) -> None:
    """Detect and label API communities in an extracted graph.

    Examples:
        sharingan cluster nodejs
        sharingan cluster fastapi --version 0.115.0
    """
    from sharingan.cluster import cluster_library
    from sharingan.discover import discover_library

    try:
        source = discover_library(library, version)
        version_id = f"{source.library_id}@{source.version}"
        import asyncio
        asyncio.run(cluster_library(source.library_id, version_id, backend))
    except Exception as e:
        console.print(f"[red]✗ Clustering failed: {e}[/]")
        import sys
        sys.exit(1)


@main.command()
def status() -> None:
    """Show Sharingan status — extracted libraries, graph stats."""
    libraries_dir = get_libraries_dir()

    if not libraries_dir.exists():
        console.print("[yellow]No libraries extracted yet. Run 'sharingan extract <library>'.[/]")
        return

    table = Table(title="Sharingan Knowledge Graph Status")
    table.add_column("Library", style="cyan")
    table.add_column("Versions", style="green")
    table.add_column("Symbols", style="yellow")
    table.add_column("Guides")
    table.add_column("Edges")

    total_symbols = 0
    total_guides = 0
    total_edges = 0

    for lib_dir in sorted(libraries_dir.iterdir()):
        if not lib_dir.is_dir():
            continue
        versions_dir = lib_dir / "versions"
        if not versions_dir.exists():
            continue

        versions = sorted([d.name for d in versions_dir.iterdir() if d.is_dir()])
        lib_symbols = 0
        lib_guides = 0
        lib_edges = 0

        for ver in versions:
            ver_dir = versions_dir / ver
            for fname, counter in [
                ("symbols.json", "symbols"),
                ("guides.json", "guides"),
                ("edges.json", "edges"),
            ]:
                fpath = ver_dir / fname
                if fpath.exists():
                    with open(fpath) as f:
                        data = json.load(f)
                    count = len(data)
                    if counter == "symbols":
                        lib_symbols += count
                    elif counter == "guides":
                        lib_guides += count
                    elif counter == "edges":
                        lib_edges += count

        total_symbols += lib_symbols
        total_guides += lib_guides
        total_edges += lib_edges

        table.add_row(
            lib_dir.name,
            ", ".join(versions),
            str(lib_symbols),
            str(lib_guides),
            str(lib_edges),
        )

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/]", "", str(total_symbols), str(total_guides), str(total_edges)
    )

    console.print(table)


@main.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", help="Transport mechanism.")
@click.option("--port", type=int, default=8000, help="Port for SSE transport.")
def serve(transport: str, port: int) -> None:
    """Start the Sharingan MCP server for AI assistants.

    Examples:
        sharingan serve
        sharingan serve --transport sse --port 8000
    """
    from sharingan.serve import mcp
    
    if transport == "stdio":
        console.print("[cyan]Starting Sharingan MCP Server (stdio)...[/]")
        mcp.run(transport="stdio")
    elif transport == "sse":
        console.print(f"[cyan]Starting Sharingan MCP Server (sse on port {port})...[/]")
        mcp.run(transport="sse", port=port)


if __name__ == "__main__":
    main()
