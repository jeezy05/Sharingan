"""
sharingan.pipeline — Main extraction pipeline orchestrator.

Graphify-inspired linear pipeline:
  discover → fetch → parse (Pass 1) → extract (Pass 2) → build → export

Coordinates the full end-to-end extraction for a library.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sharingan.build import build_graph, export_graph, build_indexes
from sharingan.cache import CacheManifest
from sharingan.config import (
    get_data_dir,
    get_indexes_dir,
    get_libraries_dir,
    get_registry_path,
    migrate_legacy_data,
)
from sharingan.discover import DocSource, discover_library, load_registry
from sharingan.extract import (
    ExtractionResult,
    detect_backend,
    extract_page,
    merge_pass1_pass2,
)
from sharingan.fetch import FetchedPage, FetchResult, fetch_docs
from sharingan.parse import ParsedPage, parse_page

console = Console()


def _get_project_root() -> Path:
    """Get the user-local data directory (deprecated — use config.py functions)."""
    return get_data_dir()


async def extract_library(
    library_id: str,
    version: str | None = None,
    output_dir: Path | None = None,
    registry_path: Path | None = None,
    update_only: bool = False,
    skip_llm: bool = False,
    backend: str | None = None,
) -> dict[str, Any]:
    """Extract documentation for a single library.

    This is the main pipeline entry point.

    Args:
        library_id: Library identifier (e.g., "zod").
        version: Specific version. Defaults to latest.
        output_dir: Where to write output. Defaults to libraries/{lib_id}/.
        registry_path: Path to registry.json.
        update_only: If True, only re-extract changed pages (SHA256 cache).
        skip_llm: If True, skip Pass 2 (LLM extraction). Pass 1 only.
        backend: LLM backend override.

    Returns:
        Dict with extraction statistics.
    """
    # Ensure legacy data is migrated on first run
    migrate_legacy_data()
    project_root = _get_project_root()

    # ── Step 1: Discover ──────────────────────────────────────────────
    console.print(Panel(f"[bold cyan]Sharingan — Extracting {library_id}[/]"))

    source = discover_library(library_id, version, registry_path or get_registry_path())
    version_id = f"{source.library_id}@{source.version}"

    console.print(f"  Library: [bold]{source.library_name}[/] v{source.version}")
    console.print(f"  Source:  {source.source_type} → {source.repo or source.base_url}")

    if not skip_llm:
        llm_backend = backend or detect_backend()
        if llm_backend == "none":
            console.print("  LLM:     [yellow]None detected. Dynamically falling back to Pass 1 (deterministic) only.[/]")
            skip_llm = True
        else:
            console.print(f"  LLM:     {llm_backend}")
    else:
        console.print("  LLM:     [yellow]Skipped (Pass 1 only)[/]")

    # ── Step 2: Fetch ─────────────────────────────────────────────────
    console.print("\n[bold]Step 1/4: Fetching documentation...[/]")
    fetch_result = await fetch_docs(source)

    if fetch_result.errors:
        for err in fetch_result.errors:
            console.print(f"  [yellow]⚠ {err}[/]")

    if not fetch_result.pages:
        console.print("[red]✗ No pages fetched. Aborting.[/]")
        return {"status": "error", "message": "No pages fetched"}

    console.print(f"  Fetched {len(fetch_result.pages)} pages")

    # ── Step 3: Cache check ───────────────────────────────────────────
    if output_dir is None:
        output_dir = get_libraries_dir() / source.library_id

    version_dir = output_dir / "versions" / source.version
    cache_dir = version_dir / "cache"
    cache = CacheManifest(cache_dir)

    pages_to_process: list[FetchedPage] = []
    skipped_count = 0

    if update_only:
        for page in fetch_result.pages:
            if cache.is_changed(page.key, page.content):
                pages_to_process.append(page)
            else:
                skipped_count += 1
        console.print(
            f"  Cache: {skipped_count} unchanged, "
            f"{len(pages_to_process)} to process"
        )
    else:
        pages_to_process = fetch_result.pages

    if not pages_to_process:
        console.print("[green]✓ All pages up to date. Nothing to extract.[/]")
        return {"status": "up_to_date", "pages_checked": len(fetch_result.pages)}

    # ── Step 4: Parse (Pass 1) ────────────────────────────────────────
    console.print(f"\n[bold]Step 2/4: Parsing {len(pages_to_process)} pages (Pass 1)...[/]")

    parsed_pages: list[ParsedPage] = []
    total_signatures = 0
    total_code_blocks = 0

    for page in pages_to_process:
        parsed = parse_page(
            page_key=page.key,
            content=page.content,
            source_url=page.source_url,
            file_type=page.file_type,
        )
        parsed_pages.append(parsed)
        total_signatures += len(parsed.signatures)
        total_code_blocks += len(parsed.code_blocks)

    console.print(
        f"  Pass 1 results: {total_signatures} signatures, "
        f"{total_code_blocks} code blocks extracted (zero token cost)"
    )

    # ── Step 5: Extract (Pass 2) ──────────────────────────────────────
    extractions: list[ExtractionResult] = []

    if skip_llm:
        console.print("\n[bold]Step 3/4: Skipping Pass 2 (--skip-llm)[/]")
        for parsed in parsed_pages:
            # Create extraction with only Pass 1 data
            merged = merge_pass1_pass2(
                parsed,
                ExtractionResult(page_key=parsed.page_key),
                version_id,
                source_url=parsed.source_url,
            )
            extractions.append(merged)
    else:
        console.print(
            f"\n[bold]Step 3/4: LLM extraction on {len(parsed_pages)} pages (Pass 2)...[/]"
        )

        for i, parsed in enumerate(parsed_pages):
            console.print(
                f"  [{i+1}/{len(parsed_pages)}] {parsed.title or parsed.page_key}",
                end="",
            )
            try:
                llm_result = await extract_page(parsed, version_id, llm_backend)
                merged = merge_pass1_pass2(
                    parsed, llm_result, version_id, source_url=parsed.source_url
                )
                extractions.append(merged)
                console.print(
                    f" → {len(merged.nodes)} nodes, {len(merged.edges)} edges"
                )
            except Exception as e:
                console.print(f" → [red]Error: {e}[/]")
                # Still use Pass 1 data
                merged = merge_pass1_pass2(
                    parsed,
                    ExtractionResult(page_key=parsed.page_key, error=str(e)),
                    version_id,
                    source_url=parsed.source_url,
                )
                extractions.append(merged)

    # ── Step 6: Build graph ───────────────────────────────────────────
    console.print("\n[bold]Step 4/4: Building knowledge graph...[/]")

    # Load library metadata for the root node
    registry = load_registry(registry_path or get_registry_path())
    lib_meta = registry.get("libraries", {}).get(library_id, {})

    G = build_graph(extractions, source.library_id, version_id, lib_meta)

    # ── Step 7: Export ────────────────────────────────────────────────
    export_graph(G, version_dir, version_id)

    # ── Step 8: Clustering ────────────────────────────────────────────
    console.print("\n[bold]Step 5/5: Detecting API communities...[/]")
    from sharingan.cluster import cluster_library
    try:
        await cluster_library(library_id, version_id, backend)
    except Exception as e:
        console.print(f"[yellow]Clustering failed or skipped: {e}[/]")

    # Save library meta
    meta_path = output_dir / "meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(lib_meta, f, indent=2)

    # Update cache
    for page, parsed in zip(pages_to_process, parsed_pages):
        # Find the extraction result for this page
        extraction = next((e for e in extractions if e.page_key == parsed.page_key), None)
        
        # If there was an LLM error, do not cache the page so it is retried next time
        if extraction and getattr(extraction, "error", None):
            console.print(f"[dim]Skipping cache for {page.key} due to extraction error.[/dim]")
            continue
            
        node_count = len([
            _ for _ in (extraction.nodes if extraction else [])
        ])
        cache.update_entry(page.key, page.content, node_count=node_count)
    cache.save()

    # Build global indexes
    libraries_dir = get_libraries_dir()
    indexes_dir = get_indexes_dir()
    if libraries_dir.exists():
        build_indexes([libraries_dir], indexes_dir)

    # ── Summary ───────────────────────────────────────────────────────
    stats = {
        "status": "success",
        "library": source.library_name,
        "version": source.version,
        "pages_fetched": len(fetch_result.pages),
        "pages_processed": len(pages_to_process),
        "pages_skipped": skipped_count,
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "output_dir": str(version_dir),
    }

    table = Table(title="Extraction Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    for key, value in stats.items():
        table.add_row(key, str(value))
    console.print(table)

    return stats
