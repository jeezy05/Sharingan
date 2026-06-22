"""
sharingan.skills — Multi-platform skill installer.

Installs Sharingan skill files into AI coding assistant configurations:
- Claude Code: CLAUDE.md + PreToolUse hook (project-scoped)
- Codex: AGENTS.md + hooks.json (project-scoped)
- Cursor: .cursor/rules/sharingan.mdc
- Gemini CLI: GEMINI.md (project-scoped)
- Antigravity: .agents/rules/sharingan.md
- And more...
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
from rich.console import Console

console = Console()

# ─── SKILL CONTENT ────────────────────────────────────────────────────


def _get_data_dir_display() -> str:
    """Get the data directory path for display in skill content."""
    from sharingan.config import get_data_dir
    return str(get_data_dir())


def get_skill_content(project_dir: Path) -> str:
    """Generate the skill/rules content for AI assistant skill files.

    Always project-scoped: includes detected deps from the project directory.
    References the CORRECT MCP tool names that actually exist in serve.py.
    """
    from sharingan.dependencies import scan_project_dependencies

    deps = scan_project_dependencies(project_dir)
    data_dir = _get_data_dir_display()

    context_section = ""
    if deps:
        context_section = "\n## Project Dependencies Detected\n\nThis project uses the following libraries tracked by Sharingan:\n"
        for lib_id, ver in deps:
            context_section += f"- **{lib_id}** v{ver}\n"
        context_section += (
            "\n**CRITICAL**: Always use the Sharingan MCP tools below to look up "
            "documentation for these exact versions. Do NOT guess APIs from your "
            "training data — the knowledge graph has the latest docs.\n"
        )

    return f"""# Sharingan — Documentation Knowledge Graph

You have access to **Sharingan**, a knowledge graph containing the latest, version-accurate
documentation for popular tech stacks. **Always consult Sharingan via MCP tools before
answering questions about library APIs, framework features, or configuration options.**

## MCP Tools Available

Use these EXACT tool names (they are registered as MCP tools on the Sharingan server):

| Tool | What It Does | When to Use |
|:-----|:-------------|:------------|
| `list_libraries` | Lists all extracted libraries with IDs and versions | To see what docs are available |
| `search_symbols` | Search for API symbols by name (functions, hooks, classes) | When user asks about a specific API |
| `get_symbol_details` | Get full documentation for a symbol by its exact ID | After finding a symbol via search |
| `get_neighbors` | Get all related symbols/guides connected to a node | To understand relationships |

### Usage Flow

1. **User asks about an API** → Call `search_symbols` with the name (e.g., "useRouter")
2. **Get full details** → Call `get_symbol_details` with the symbol ID from search results
3. **Explore related APIs** → Call `get_neighbors` with the same symbol ID
4. **List available libraries** → Call `list_libraries` to see what's extracted

### Example

If the user asks "How does useRouter work in Next.js 15?":
1. Call `search_symbols(query="useRouter", library_id="nextjs")`
2. From the results, get the symbol ID (e.g., `nextjs@15.3.2::next/navigation::useRouter`)
3. Call `get_symbol_details(symbol_id="nextjs@15.3.2::next/navigation::useRouter")`
4. Call `get_neighbors(node_id="nextjs@15.3.2::next/navigation::useRouter")` for related APIs
{context_section}
## Covered Libraries

React, Next.js, TypeScript, Node.js, Python, FastAPI, Tailwind CSS, Prisma, Zod — and growing.

## Rules

- **ALWAYS use Sharingan MCP tools first** for any documentation lookup. Do not use web search or training data for library APIs when Sharingan has the data.
- Every edge in the knowledge graph has a confidence tag: `EXTRACTED` (structural fact from docs) vs `INFERRED` (AI-generated inference). Prefer EXTRACTED data.
- If Sharingan returns no results for a query, fall back to your training data but explicitly tell the user: "Sharingan didn't have this — using training data (may be outdated)."

## Extraction Assistance

If the user wants to extract documentation for a library not yet in Sharingan:
1. Run: `sharingan extract <library_name> --skip-llm` (this runs Pass 1: free, deterministic extraction)
2. The extracted data will be stored in: `{data_dir}/libraries/<lib>/versions/<ver>/`
3. If you have LLM capability, you can enrich the extraction by reading `symbols.json` and adding descriptions, then writing back to the same file.

## Data Location

All knowledge graph data is stored in: `{data_dir}/`
"""


def get_cursor_rule(project_dir: Path) -> str:
    """Generate Cursor-specific .mdc rule file content."""
    from sharingan.dependencies import scan_project_dependencies

    deps = scan_project_dependencies(project_dir)
    context_section = ""
    if deps:
        context_section = "\n## Project Dependencies\n"
        for lib_id, ver in deps:
            context_section += f"- {lib_id}: v{ver}\n"
        context_section += "\nAlways use Sharingan MCP tools for these libraries.\n"

    return f"""---
description: Sharingan documentation knowledge graph integration
alwaysApply: true
---

# Sharingan Integration

You have access to Sharingan, a knowledge graph of up-to-date documentation for popular tech stacks.

When the user asks about library APIs, framework features, or configuration:
1. Call `search_symbols` with the API name to find it in the knowledge graph.
2. Call `get_symbol_details` with the symbol ID from search results to get full docs.
3. Call `get_neighbors` to find related APIs and guides.
4. Call `list_libraries` to see all available documentation.

Use these tools INSTEAD of guessing from training data. Note confidence tags: EXTRACTED (fact) vs INFERRED (inference).
{context_section}
Covered: React, Next.js, TypeScript, Node.js, Python, FastAPI, Tailwind CSS, Prisma, Zod
"""


PRETOOLUSE_HOOK = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Read|Glob|Grep",
                "command": (
                    'echo "💡 Sharingan tip: Consider using Sharingan MCP tools '
                    'for documentation lookups instead of reading raw files."'
                ),
            }
        ]
    }
}


# ─── PLATFORM DETECTION ──────────────────────────────────────────────


def _detect_platform() -> str | list[str] | None:
    """Auto-detect the current AI coding assistant platform.

    Checks project-local indicators first, then global user configs.
    If multiple platforms are detected, prompts the user to choose.
    """
    detected = []
    checks = [
        # Project-local configurations (strongest signal)
        ("cursor", Path.cwd() / ".cursor"),
        ("antigravity", Path.cwd() / ".agents"),
        # Global user configurations
        ("claude", Path.home() / ".claude"),
        ("codex", Path.home() / ".codex"),
        ("gemini", Path.home() / ".gemini"),
    ]
    for platform, path in checks:
        if path.exists():
            detected.append(platform)

    if not detected:
        return None
    if len(detected) == 1:
        return detected[0]

    # Multiple platforms detected — ask user
    console.print("\n[yellow]Multiple platforms detected:[/]")
    for i, p in enumerate(detected, 1):
        console.print(f"  {i}. {p}")
    console.print(f"  {len(detected) + 1}. Install for ALL detected platforms")

    choice = click.prompt(
        "\nSelect platform number",
        type=int,
        default=1,
    )

    if choice == len(detected) + 1:
        return detected  # Return list → install_skill handles multi
    if 1 <= choice <= len(detected):
        return detected[choice - 1]
    return detected[0]


# ─── MAIN INSTALLER ──────────────────────────────────────────────────


def install_skill(platform: str | None = None, project_scope: bool = True) -> None:
    """Install Sharingan skill for the specified platform.

    Args:
        platform: Target platform. Auto-detected if None.
        project_scope: Always True — skills are project-scoped.
    """
    if platform is None:
        result = _detect_platform()
        if result is None:
            console.print(
                "[yellow]Could not auto-detect platform. "
                "Use --platform (claude|cursor|codex|gemini|antigravity).[/]"
            )
            return
        if isinstance(result, list):
            # Install for all detected platforms
            for p in result:
                _install_for_platform(p)
            _auto_extract_deps()
            return
        platform = result
        console.print(f"[cyan]Auto-detected platform: {platform}[/]")

    _install_for_platform(platform)
    _auto_extract_deps()


def _install_for_platform(platform: str) -> None:
    """Run the appropriate installer for a platform."""
    installers = {
        "claude": _install_claude,
        "codex": _install_codex,
        "cursor": _install_cursor,
        "gemini": _install_gemini,
        "antigravity": _install_antigravity,
        "opencode": _install_agents_md,
        "copilot": _install_agents_md,
        "aider": _install_agents_md,
    }

    installer = installers.get(platform)
    if installer is None:
        console.print(f"[red]Unknown platform: {platform}[/]")
        return

    installer()
    console.print(f"[green]✓ Sharingan installed for {platform}[/]")


def _auto_extract_deps() -> None:
    """Scan project dependencies and auto-extract any that are missing."""
    project_dir = Path.cwd()
    from sharingan.dependencies import scan_project_dependencies

    try:
        deps = scan_project_dependencies(project_dir)
        if deps:
            import asyncio
            from sharingan.config import get_libraries_dir
            from sharingan.pipeline import extract_library

            libraries_dir = get_libraries_dir()

            for lib_id, ver in deps:
                version_dir = libraries_dir / lib_id / "versions" / ver
                if not version_dir.exists():
                    console.print(
                        f"[cyan]Auto-extracting docs for {lib_id} v{ver} "
                        f"(Pass 1 — deterministic, no API key needed)...[/]"
                    )
                    try:
                        asyncio.run(extract_library(
                            library_id=lib_id,
                            version=ver,
                            skip_llm=True,
                        ))
                        console.print(f"[green]  ✓ Extracted {lib_id} v{ver}[/]")
                    except Exception as ex:
                        console.print(f"[yellow]  ⚠ Failed to auto-extract {lib_id}: {ex}[/]")
    except Exception as e:
        console.print(f"[yellow]⚠ Dependency scan failed: {e}[/]")


# ─── PLATFORM-SPECIFIC INSTALLERS ────────────────────────────────────


def _install_claude() -> None:
    """Install for Claude Code — CLAUDE.md + PreToolUse hook (project-scoped)."""
    base = Path.cwd()

    # Write skill content to CLAUDE.md in project root
    claude_md = base / "CLAUDE.md"
    _write_skill_file(claude_md, get_skill_content(base))

    # Write PreToolUse hook
    settings_dir = base / ".claude"
    settings_dir.mkdir(exist_ok=True)
    settings_path = settings_dir / "settings.json"

    settings = {}
    if settings_path.exists():
        try:
            with open(settings_path, encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            pass

    # Merge hooks
    if "hooks" not in settings:
        settings["hooks"] = {}
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    existing_hooks = settings["hooks"]["PreToolUse"]
    if not any("sharingan" in str(h).lower() for h in existing_hooks):
        existing_hooks.extend(PRETOOLUSE_HOOK["hooks"]["PreToolUse"])
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        console.print(f"  → Updated {settings_path}")


def _install_codex() -> None:
    """Install for Codex — AGENTS.md + hooks.json (project-scoped)."""
    base = Path.cwd()

    agents_md = base / "AGENTS.md"
    _write_skill_file(agents_md, get_skill_content(base))

    # Write hooks.json
    codex_dir = base / ".codex"
    codex_dir.mkdir(exist_ok=True)
    hooks_path = codex_dir / "hooks.json"

    hooks = {}
    if hooks_path.exists():
        try:
            with open(hooks_path, encoding="utf-8") as f:
                hooks = json.load(f)
        except Exception:
            pass

    if "PreToolUse" not in hooks:
        hooks.update(PRETOOLUSE_HOOK)
        with open(hooks_path, "w", encoding="utf-8") as f:
            json.dump(hooks, f, indent=2)
        console.print(f"  → Updated {hooks_path}")


def _install_cursor() -> None:
    """Install for Cursor — .cursor/rules/sharingan.mdc (always project-scoped)."""
    base = Path.cwd()
    rules_dir = base / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    rule_path = rules_dir / "sharingan.mdc"
    rule_path.write_text(get_cursor_rule(base), encoding="utf-8")
    console.print(f"  → Created {rule_path}")


def _install_gemini() -> None:
    """Install for Gemini CLI — GEMINI.md (project-scoped)."""
    base = Path.cwd()
    gemini_md = base / "GEMINI.md"
    _write_skill_file(gemini_md, get_skill_content(base))


def _install_antigravity() -> None:
    """Install for Google Antigravity — .agents/rules/sharingan.md."""
    base = Path.cwd()
    rules_dir = base / ".agents" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    rule_path = rules_dir / "sharingan.md"
    rule_path.write_text(get_skill_content(base), encoding="utf-8")
    console.print(f"  → Created {rule_path}")


def _install_agents_md() -> None:
    """Generic AGENTS.md installer for platforms that use it (project-scoped)."""
    base = Path.cwd()
    agents_md = base / "AGENTS.md"
    _write_skill_file(agents_md, get_skill_content(base))


# ─── HELPERS ──────────────────────────────────────────────────────────


def _write_skill_file(path: Path, content: str) -> None:
    """Write or update a skill file. Replaces existing Sharingan section if present."""
    if path.exists():
        existing = path.read_text()
        if "# Sharingan" in existing:
            # Replace existing Sharingan section entirely
            # Find the start of the Sharingan section
            start = existing.index("# Sharingan")
            # Write everything before the Sharingan section + new content
            before = existing[:start].rstrip()
            new_content = before + "\n\n" + content if before else content
            path.write_text(new_content, encoding="utf-8")
            console.print(f"  → Updated (replaced) {path}")
            return
        else:
            # Append to existing file
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n\n" + content)
            console.print(f"  → Updated (appended) {path}")
    else:
        path.write_text(content, encoding="utf-8")
        console.print(f"  → Created {path}")
