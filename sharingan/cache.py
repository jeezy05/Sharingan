"""
sharingan.cache — SHA256-based caching for incremental documentation updates.

Graphify-inspired pattern: each documentation page is hashed with SHA256.
On --update, only pages whose hash has changed are re-extracted.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CacheManifest:
    """Manages SHA256 hashes for documentation pages to enable incremental updates."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.manifest_path = cache_dir / "manifest.json"
        self._manifest: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load existing manifest from disk."""
        if self.manifest_path.exists():
            with open(self.manifest_path, "r") as f:
                self._manifest = json.load(f)

    def save(self) -> None:
        """Persist manifest to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w") as f:
            json.dump(self._manifest, f, indent=2, sort_keys=True)

    @staticmethod
    def compute_sha256(content: str | bytes) -> str:
        """Compute SHA256 hash of content."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def is_changed(self, page_key: str, content: str | bytes) -> bool:
        """Check if a page has changed since last extraction.

        Args:
            page_key: Unique identifier for the page (e.g., relative path).
            content: Current content of the page.

        Returns:
            True if the page is new or has changed, False if unchanged.
        """
        current_hash = self.compute_sha256(content)
        cached = self._manifest.get(page_key)
        if cached is None:
            return True
        return cached.get("sha256") != current_hash

    def get_changed_pages(
        self, pages: dict[str, str | bytes]
    ) -> tuple[dict[str, str | bytes], dict[str, str | bytes]]:
        """Split pages into changed and unchanged.

        Args:
            pages: Dict mapping page_key to content.

        Returns:
            Tuple of (changed_pages, unchanged_pages).
        """
        changed: dict[str, str | bytes] = {}
        unchanged: dict[str, str | bytes] = {}
        for key, content in pages.items():
            if self.is_changed(key, content):
                changed[key] = content
            else:
                unchanged[key] = content
        return changed, unchanged

    def update_entry(
        self,
        page_key: str,
        content: str | bytes,
        node_count: int = 0,
        edge_count: int = 0,
    ) -> None:
        """Update the cache entry for a page after successful extraction.

        Args:
            page_key: Unique identifier for the page.
            content: Content that was extracted.
            node_count: Number of nodes extracted from this page.
            edge_count: Number of edges extracted from this page.
        """
        self._manifest[page_key] = {
            "sha256": self.compute_sha256(content),
            "last_extracted": datetime.now(timezone.utc).isoformat(),
            "node_count": node_count,
            "edge_count": edge_count,
        }

    def remove_entry(self, page_key: str) -> None:
        """Remove a page from the cache (e.g., page was deleted upstream)."""
        self._manifest.pop(page_key, None)

    def get_all_keys(self) -> list[str]:
        """Get all cached page keys."""
        return list(self._manifest.keys())

    @property
    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
        total_nodes = sum(e.get("node_count", 0) for e in self._manifest.values())
        total_edges = sum(e.get("edge_count", 0) for e in self._manifest.values())
        return {
            "total_pages": len(self._manifest),
            "total_nodes": total_nodes,
            "total_edges": total_edges,
        }
