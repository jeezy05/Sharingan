"""
sharingan.fetch — Fetch documentation from upstream sources.

Supports:
- GitHub repos (sparse checkout of /docs directory)
- GitHub raw content API
- Website HTML docs
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from sharingan.discover import DocSource

console = Console()

# GitHub API base
GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"

# File extensions we care about for docs
DOC_EXTENSIONS = {".md", ".mdx", ".txt", ".rst", ".html", ".htm", ".qmd"}

# Max concurrent requests
MAX_CONCURRENT = 10


@dataclass
class FetchedPage:
    """A documentation page that has been fetched."""

    key: str  # relative path or URL slug (used as cache key)
    content: str  # raw content
    source_url: str  # full URL for reference
    file_type: str  # "md", "mdx", "rst", "html", "txt"


@dataclass
class FetchResult:
    """Result of fetching all documentation for a library version."""

    library_id: str
    version: str
    pages: list[FetchedPage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def _github_get_tree(
    client: httpx.AsyncClient,
    repo: str,
    branch: str,
    path: str,
) -> list[dict[str, Any]]:
    """Get file tree from GitHub API for a specific path.

    Uses the Trees API for efficient listing of all files.
    Handles both directory paths and single file paths.
    """
    # First get the tree SHA for the branch
    url = f"{GITHUB_API}/repos/{repo}/git/trees/{branch}?recursive=1"
    resp = await client.get(url)
    resp.raise_for_status()
    tree = resp.json()

    # Check if path points to a single file (has a doc extension)
    path_obj = Path(path) if path else None
    if path_obj and path_obj.suffix.lower() in DOC_EXTENSIONS:
        # Single file mode — match exact path
        return [
            item
            for item in tree.get("tree", [])
            if item["type"] == "blob" and item["path"] == path
        ]

    # Directory mode — filter to files under the docs path
    prefix = path.rstrip("/") + "/" if path else ""
    return [
        item
        for item in tree.get("tree", [])
        if item["type"] == "blob"
        and (item["path"].startswith(prefix) or (not prefix and True))
        and Path(item["path"]).suffix.lower() in DOC_EXTENSIONS
    ]


async def _github_fetch_file(
    client: httpx.AsyncClient,
    repo: str,
    branch: str,
    file_path: str,
    semaphore: asyncio.Semaphore,
) -> FetchedPage | None:
    """Fetch a single file from GitHub raw content."""
    async with semaphore:
        url = f"{GITHUB_RAW}/{repo}/{branch}/{file_path}"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            suffix = Path(file_path).suffix.lower().lstrip(".")
            return FetchedPage(
                key=file_path,
                content=resp.text,
                source_url=url,
                file_type=suffix or "md",
            )
        except httpx.HTTPError as e:
            console.print(f"[yellow]Warning: failed to fetch {file_path}: {e}[/]")
            return None


async def fetch_github_docs(
    source: DocSource,
) -> FetchResult:
    """Fetch documentation from a GitHub repository.

    Uses the GitHub API to list all doc files, then fetches them in parallel.

    Args:
        source: DocSource with repo, branch, and docs_path.

    Returns:
        FetchResult with all fetched pages.
    """
    result = FetchResult(library_id=source.library_id, version=source.version)

    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"Accept": "application/vnd.github.v3+json"},
        follow_redirects=True,
    ) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Discover all doc files
            task = progress.add_task(
                f"[cyan]Discovering docs for {source.library_name}...",
                total=None,
            )

            all_files: list[dict[str, Any]] = []
            paths_to_scan = [source.docs_path] if source.docs_path else [""]
            paths_to_scan.extend(source.extra_paths)

            for scan_path in paths_to_scan:
                try:
                    files = await _github_get_tree(
                        client, source.repo, source.branch, scan_path or ""
                    )
                    all_files.extend(files)
                except httpx.HTTPError as e:
                    result.errors.append(f"Failed to list {scan_path}: {e}")

            progress.update(
                task,
                description=f"[cyan]Found {len(all_files)} doc files for {source.library_name}",
            )

            if not all_files:
                result.errors.append("No documentation files found")
                return result

            # Fetch all files in parallel
            progress.update(
                task,
                description=f"[cyan]Fetching {len(all_files)} pages for {source.library_name}...",
            )
            semaphore = asyncio.Semaphore(MAX_CONCURRENT)
            tasks = [
                _github_fetch_file(
                    client, source.repo, source.branch, f["path"], semaphore
                )
                for f in all_files
            ]
            pages = await asyncio.gather(*tasks)

            for page in pages:
                if page is not None:
                    result.pages.append(page)

            progress.update(
                task,
                description=(
                    f"[green]✓ Fetched {len(result.pages)}/{len(all_files)} pages "
                    f"for {source.library_name}"
                ),
            )

    return result


async def fetch_single_file(
    repo: str,
    branch: str,
    file_path: str,
) -> str | None:
    """Fetch a single file from GitHub. Utility for README-only libraries like Zod."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        url = f"{GITHUB_RAW}/{repo}/{branch}/{file_path}"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError:
            return None


async def fetch_docs(source: DocSource) -> FetchResult:
    """Fetch documentation for a library from its configured source.

    Dispatches to the appropriate fetcher based on source_type.

    Args:
        source: DocSource describing where to fetch docs from.

    Returns:
        FetchResult with all fetched pages.
    """
    if source.source_type in ("github_markdown", "github_rst"):
        return await fetch_github_docs(source)
    elif source.source_type == "html":
        # HTML fetching (for PostgreSQL, etc.) — placeholder for now
        console.print(
            f"[yellow]HTML doc fetching not yet implemented for {source.library_name}[/]"
        )
        return FetchResult(
            library_id=source.library_id,
            version=source.version,
            errors=["HTML doc fetching not yet implemented"],
        )
    else:
        raise ValueError(f"Unknown source type: {source.source_type}")
