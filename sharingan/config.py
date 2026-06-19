"""
sharingan.config — Centralized path resolution for Sharingan.

All user-generated data (extracted knowledge graphs, indexes, caches)
is stored in ~/.sharingan/ so it survives pip upgrades.

The library registry (registry.json) and schema definitions stay
inside the package since they are part of the codebase.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from rich.console import Console

console = Console()

# ─── DATA DIRECTORY RESOLUTION ────────────────────────────────────────


def get_data_dir() -> Path:
    """Get the user-local data directory for Sharingan.

    Priority:
    1. SHARINGAN_DATA_DIR env var (for CI/Docker/custom setups)
    2. ~/.sharingan/ (simple, discoverable — like ~/.ollama/)

    Returns:
        Path to the data directory. Creates it if it doesn't exist.
    """
    if env := os.environ.get("SHARINGAN_DATA_DIR"):
        p = Path(env)
    else:
        p = Path.home() / ".sharingan"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_libraries_dir() -> Path:
    """Get the directory where extracted library knowledge graphs are stored."""
    p = get_data_dir() / "libraries"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_indexes_dir() -> Path:
    """Get the directory where global search indexes are stored."""
    p = get_data_dir() / "indexes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_registry_path() -> Path:
    """Get the path to the library registry.

    The registry is part of the package (code), not user data.
    It stays inside the installed package directory.
    """
    return Path(__file__).parent / "data" / "registry.json"


def get_schema_dir() -> Path:
    """Get the path to the JSON schema definitions (package-bundled)."""
    return Path(__file__).parent / "data" / "schema"


# ─── MIGRATION FROM OLD IN-PACKAGE DATA ──────────────────────────────


def migrate_legacy_data() -> None:
    """One-time migration: copy extracted data from old in-package location
    to the new ~/.sharingan/ user-local directory.

    The old location was: sharingan/data/libraries/ and sharingan/data/indexes/
    The new location is:  ~/.sharingan/libraries/ and ~/.sharingan/indexes/
    """
    old_data_root = Path(__file__).parent / "data"
    old_libraries = old_data_root / "libraries"
    old_indexes = old_data_root / "indexes"

    new_data_dir = get_data_dir()
    migration_marker = new_data_dir / ".migrated_from_package"

    # Skip if already migrated or no old data exists
    if migration_marker.exists():
        return
    if not old_libraries.exists() or not any(old_libraries.iterdir()):
        return

    console.print("[cyan]Migrating Sharingan data to ~/.sharingan/ (one-time)...[/]")

    # Migrate libraries
    new_libraries = get_libraries_dir()
    for lib_dir in old_libraries.iterdir():
        if not lib_dir.is_dir():
            continue
        dest = new_libraries / lib_dir.name
        if not dest.exists():
            try:
                shutil.copytree(lib_dir, dest)
                console.print(f"  → Migrated {lib_dir.name}")
            except Exception as e:
                console.print(f"  [yellow]⚠ Failed to migrate {lib_dir.name}: {e}[/]")

    # Migrate indexes
    if old_indexes.exists():
        new_indexes = get_indexes_dir()
        for idx_file in old_indexes.iterdir():
            dest = new_indexes / idx_file.name
            if not dest.exists():
                try:
                    shutil.copy2(idx_file, dest)
                except Exception:
                    pass

    # Mark as migrated
    migration_marker.write_text("migrated")
    console.print("[green]✓ Data migrated to ~/.sharingan/[/]")
