"""
sharingan.discover — Discover documentation sources for libraries.

Reads the registry.json and resolves documentation locations for each library.
Handles GitHub repo docs, website docs, and package-level documentation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DocSource:
    """A documentation source to be fetched and parsed."""

    library_id: str
    library_name: str
    version: str
    source_type: str  # "github_markdown", "github_rst", "html"
    repo: str | None = None  # "owner/repo"
    branch: str | None = None
    docs_path: str | None = None
    extra_paths: list[str] = field(default_factory=list)
    base_url: str | None = None  # for HTML docs
    docs_url: str = ""
    npm_package: str | None = None
    pypi_package: str | None = None
    category: str = ""
    language: str = ""
    tags: list[str] = field(default_factory=list)


def load_registry(registry_path: Path | None = None) -> dict[str, Any]:
    """Load the library registry.

    Args:
        registry_path: Path to registry.json. Defaults to package-bundled registry.

    Returns:
        Parsed registry dict.
    """
    if registry_path is None:
        from sharingan.config import get_registry_path
        registry_path = get_registry_path()
    with open(registry_path, "r") as f:
        return json.load(f)


def discover_library(
    library_id: str,
    version: str | None = None,
    registry_path: Path | None = None,
) -> DocSource:
    """Discover documentation source for a specific library.

    Args:
        library_id: Library identifier (e.g., "nextjs").
        version: Specific version to extract. Defaults to latest.
        registry_path: Path to registry.json.

    Returns:
        DocSource with all metadata needed for fetching.

    Raises:
        KeyError: If library not found in registry.
    """
    registry = load_registry(registry_path)
    libraries = registry.get("libraries", {})

    if library_id not in libraries:
        available = ", ".join(sorted(libraries.keys()))
        raise KeyError(
            f"Library '{library_id}' not found in registry. "
            f"Available: {available}"
        )

    lib = libraries[library_id]
    docs_config = lib.get("docs_config", {})
    target_version = version or lib["latest_version"]

    return DocSource(
        library_id=lib["id"],
        library_name=lib["name"],
        version=target_version,
        source_type=docs_config.get("type", "github_markdown"),
        repo=docs_config.get("repo"),
        branch=docs_config.get("branch", "main"),
        docs_path=docs_config.get("docs_path"),
        extra_paths=docs_config.get("extra_paths", []),
        base_url=docs_config.get("base_url"),
        docs_url=lib.get("docs_url", ""),
        npm_package=lib.get("npm_package"),
        pypi_package=lib.get("pypi_package"),
        category=lib.get("category", ""),
        language=lib.get("language", ""),
        tags=lib.get("tags", []),
    )


def discover_all(
    registry_path: Path | None = None,
) -> list[DocSource]:
    """Discover documentation sources for all libraries in the registry.

    Args:
        registry_path: Path to registry.json.

    Returns:
        List of DocSource objects, one per library.
    """
    registry = load_registry(registry_path)
    libraries = registry.get("libraries", {})
    sources = []
    for library_id in sorted(libraries.keys()):
        try:
            source = discover_library(library_id, registry_path=registry_path)
            sources.append(source)
        except (KeyError, ValueError) as e:
            # Log but don't fail on individual library errors
            import sys
            sys.stderr.write(f"Warning: skipping {library_id}: {e}\n")
    return sources


def list_libraries(registry_path: Path | None = None) -> list[dict[str, str]]:
    """List all libraries in the registry with basic info.

    Returns:
        List of dicts with id, name, category, latest_version.
    """
    registry = load_registry(registry_path)
    libraries = registry.get("libraries", {})
    return [
        {
            "id": lib["id"],
            "name": lib["name"],
            "category": lib.get("category", ""),
            "language": lib.get("language", ""),
            "latest_version": lib.get("latest_version", ""),
        }
        for lib in sorted(libraries.values(), key=lambda x: x["id"])
    ]
