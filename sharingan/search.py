"""
sharingan.search — Hybrid Deterministic Graph RAG for the MCP master tool.

Routes queries through either Full Context Injection (small libraries)
or Deterministic Graph RAG (large libraries) based on a token threshold.
"""

import json
import re
from pathlib import Path
from typing import Any

from sharingan.config import get_libraries_dir, get_cache_dir

# ─── Module-level cache ──────────────────────────────────────────────
_cache: dict[str, Any] = {}

MIN_MATCH_LEN = 4  # Symbols shorter than this are skipped to avoid false positives


def _find_library_dir(lib_id: str) -> Path | None:
    for base in [get_cache_dir() / "libraries", get_libraries_dir()]:
        p = base / lib_id
        if p.exists() and (p / "meta.json").exists():
            return p
    return None


def _load_json(path: Path):
    """Load JSON from disk with module-level caching."""
    key = str(path)
    if key in _cache:
        return _cache[key]
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _cache[key] = data
                return data
    except Exception:
        pass
    _cache[key] = None
    return None


def _format_node(node: dict) -> str:
    """Format a single node (symbol or guide) into readable Markdown."""
    is_guide = node.get("node_type") == "guide" or "title" in node and "kind" not in node
    lines = []

    if is_guide:
        lines.append(f"## {node.get('title', 'Guide')} (guide)")
        summary = node.get("content_summary", "")
        if summary:
            lines.append(summary)
        for ex in node.get("code_examples", []):
            lang = ex.get("language", "")
            code = ex.get("code", "")
            title = ex.get("title", "")
            if code:
                if title:
                    lines.append(f"**{title}**")
                lines.append(f"```{lang}\n{code}\n```")
    else:
        name = node.get("name", "Symbol")
        kind = node.get("kind", "symbol")
        lines.append(f"## {name} ({kind})")
        if node.get("signature"):
            lines.append(f"```\n{node['signature']}\n```")
        if node.get("description"):
            lines.append(node["description"])

    lines.append("---\n")
    return "\n".join(lines)


# ─── Main entry point ────────────────────────────────────────────────

def hybrid_graph_search(query: str, library_id: str) -> str:
    """The master search router: hybrid between Full Context and Graph RAG."""
    lib_dir = _find_library_dir(library_id)
    if not lib_dir:
        return f"Library '{library_id}' is not extracted locally. Run 'sharingan extract {library_id}' first."

    meta = _load_json(lib_dir / "meta.json")
    version = meta.get("latest_version") if meta else None
    if not version:
        return f"Could not determine latest version for {library_id}."

    ver_dir = lib_dir / "versions" / version
    symbols_path = ver_dir / "symbols.json"
    guides_path = ver_dir / "guides.json"
    edges_path = ver_dir / "edges.json"
    clusters_path = ver_dir / "clusters.json"

    # 1. Hybrid Threshold Bypass
    total_size = 0
    if symbols_path.exists(): total_size += symbols_path.stat().st_size
    if guides_path.exists(): total_size += guides_path.stat().st_size

    # Threshold: ~60,000 bytes ≈ 15,000 tokens
    if total_size < 60_000:
        return _full_context_injection(symbols_path, guides_path)

    # 2. Deterministic Graph RAG
    return _deterministic_graph_rag(query, symbols_path, guides_path, edges_path, clusters_path)


def _full_context_injection(symbols_path: Path, guides_path: Path) -> str:
    symbols = _load_json(symbols_path) or []
    guides = _load_json(guides_path) or []

    out = ["# Comprehensive Library Documentation (Full Context Injection)\n"]
    if guides:
        out.append("## Guides & Tutorials")
        for g in guides:
            out.append(_format_node(g))
    if symbols:
        out.append("## API Reference")
        for s in symbols:
            out.append(_format_node(s))

    return "\n".join(out)


def _deterministic_graph_rag(query: str, symbols_path: Path, guides_path: Path, edges_path: Path, clusters_path: Path) -> str:
    symbols = _load_json(symbols_path) or []
    guides = _load_json(guides_path) or []
    edges = _load_json(edges_path) or []

    node_lookup = {}
    for s in symbols:
        node_lookup[s["id"]] = s
    for g in guides:
        node_lookup[g["id"]] = g

    seed_ids = set()

    # A. Exact Symbol Matching — word-boundary, minimum-length guard
    for s in symbols:
        name = s.get("name", "")
        if name and len(name) >= MIN_MATCH_LEN and re.search(rf'\b{re.escape(name)}\b', query, re.IGNORECASE):
            seed_ids.add(s["id"])

    for g in guides:
        title = g.get("title", "")
        if title and len(title) >= MIN_MATCH_LEN and re.search(rf'\b{re.escape(title)}\b', query, re.IGNORECASE):
            seed_ids.add(g["id"])

    # B. No Matches → Deterministic Fallback (return clusters ToC)
    if not seed_ids:
        clusters = _load_json(clusters_path) or []
        out = ["# ⚠️ No Exact Symbols Found in Query\n"]
        out.append("Please specify an exact symbol or module from the architectural outline below:\n")
        for c in clusters:
            out.append(f"### Cluster: {c.get('name')}")
            out.append(c.get("description", ""))
            out.append(f"Contains symbols: {', '.join(c.get('nodes', [])[:15])}...\n")
        return "\n".join(out)

    # Limit seeds to prevent massive fanout
    seed_ids = set(list(seed_ids)[:5])

    # C. Explicit Edge Traversal (1-Hop)
    neighbor_ids = set()
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src in seed_ids:
            neighbor_ids.add(tgt)
        if tgt in seed_ids:
            neighbor_ids.add(src)

    # Limit neighbors
    neighbor_ids = set(list(neighbor_ids)[:15])
    all_node_ids = seed_ids.union(neighbor_ids)

    # D. Context Bundling
    out = ["# Deterministic Graph Context\n"]
    out.append(f"Found {len(seed_ids)} exact seed matches and {len(neighbor_ids)} explicitly linked neighbors.\n")

    for nid in all_node_ids:
        node = node_lookup.get(nid)
        if not node:
            continue
        out.append(_format_node(node))

    return "\n".join(out)
