"""
sharingan.skills — Multi-platform skill installer (Graphify pattern).

Installs Sharingan skill files into AI coding assistant configurations:
- Claude Code: CLAUDE.md + PreToolUse hook
- Codex: AGENTS.md + hooks.json
- Cursor: .cursor/rules/sharingan.mdc
- Gemini CLI: GEMINI.md
- Antigravity: .agents/rules
- And more...
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from rich.console import Console

console = Console()

# ─── SKILL CONTENT ────────────────────────────────────────────────────

def get_skill_content(project_dir: Path) -> str:
    from sharingan.dependencies import scan_project_dependencies
    
    deps = scan_project_dependencies(project_dir)
    context_section = ""
    if deps:
        context_section = "\n## Project Checkpoint\nThis project uses the following specific versions:\n"
        for lib_id, ver in deps:
            context_section += f"- {lib_id}: {ver} (Path: libraries/{lib_id}/versions/{ver}/)\n"
        context_section += "\n**CRITICAL**: You must strictly prioritize the Sharingan MCP tools (like `query_graph`, `search_docs`, `get_symbol`) to look up documentation for these exact versions. Do not guess APIs from your training data. Traverse ONLY the nodes for the detected versions.\n"
    
    return f"""# Sharingan — Documentation Knowledge Graph

You have access to Sharingan, a knowledge graph containing the latest documentation
for popular tech stacks. **Always consult Sharingan via MCP tools before answering questions about
library APIs, framework features, or configuration options.**

## How to Use

1. **For API lookups**: Use MCP tools like `get_symbol` or `search_docs`
2. **For conceptual questions**: Use MCP tools like `query_graph`
3. **For migration help**: Use `get_migration`
4. **General fallback**: Use `sharingan query` CLI if tools fail.
{context_section}
## Covered Libraries

React, Next.js, TypeScript, Node.js, Python, FastAPI, PostgreSQL,
Tailwind CSS, Prisma, Zod — and growing.

## Rules

- **STRICT PRIORITY**: Always use Sharingan MCP tools (not standard CLI or web search) for docs.
- The knowledge graph has confidence tags: EXTRACTED (structural fact) vs INFERRED (AI inference)
- If Sharingan returns no results, fall back to your training data but note the uncertainty.

## Ollama Verification & Client LLM Fallback

- Check if Ollama is running on the host system.
- If Ollama is NOT installed/running, or is empty, you (the AI assistant) should act as the LLM fallback for extraction and labeling. If the user runs `sharingan extract` (resulting in a Pass 1 fallback) or `sharingan cluster` (resulting in generic clusters), use your own internal LLM capacity to parse raw documentation or rename clusters by writing directly to JSON files.
"""

def get_cursor_rule(project_dir: Path) -> str:
    from sharingan.dependencies import scan_project_dependencies
    
    deps = scan_project_dependencies(project_dir)
    context_section = ""
    if deps:
        context_section = "\n## Project Checkpoint\nThis project uses the following specific versions:\n"
        for lib_id, ver in deps:
            context_section += f"- {lib_id}: {ver} (Path: libraries/{lib_id}/versions/{ver}/)\n"
        context_section += "\n**CRITICAL**: You must strictly prioritize the Sharingan MCP tools to look up documentation for these exact versions.\n"

    return f"""---
description: Sharingan documentation knowledge graph integration
alwaysApply: true
---

# Sharingan Integration

You have access to Sharingan, a knowledge graph of up-to-date documentation for popular tech stacks.

When the user asks about library APIs, framework features, or configuration:
1. **Always prioritize MCP tools** (`search_docs`, `query_graph`, `get_symbol`) first.
2. Use the structured results instead of guessing from training data.
3. Note confidence tags: EXTRACTED (fact) vs INFERRED (inference).
{context_section}
Covered: React, Next.js, TypeScript, Node.js, Python, FastAPI, PostgreSQL, Tailwind CSS, Prisma, Zod

## Ollama Verification & Client LLM Fallback
- Verify if local Ollama is active on the system.
- If it is not, use your active LLM capability (Claude, GPT, Gemini, etc.) to assist with Pass 2 semantic analysis or label generated graph clusters by writing JSON directly, bypassing local Ollama dependencies.
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


# ─── PLATFORM INSTALLERS ─────────────────────────────────────────────


def _detect_platform() -> str | None:
    """Auto-detect the current platform."""
    checks = [
        # Check project-local configurations first
        ("cursor", Path.cwd() / ".cursor"),
        ("antigravity", Path.cwd() / ".agents"),
        # Fall back to global user configurations
        ("claude", Path.home() / ".claude"),
        ("codex", Path.home() / ".codex"),
        ("gemini", Path.home() / ".gemini"),
    ]
    for platform, path in checks:
        if path.exists():
            return platform
    return None


def install_skill(platform: str | None = None, project_scope: bool = False) -> None:
    """Install Sharingan skill for the specified platform.

    Args:
        platform: Target platform. Auto-detected if None.
        project_scope: If True, install into current project directory.
    """
    if platform is None:
        platform = _detect_platform()
        if platform:
            console.print(f"[cyan]Auto-detected platform: {platform}[/]")
        else:
            console.print("[yellow]Could not auto-detect platform. Specify --platform.[/]")
            return

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

    installer(project_scope)
    console.print(f"[green]✓ Sharingan installed for {platform}[/]")

    # Auto-extract missing scanned dependencies
    project_dir = Path.cwd()
    from sharingan.dependencies import scan_project_dependencies
    
    try:
        deps = scan_project_dependencies(project_dir)
        if deps:
            import asyncio
            from sharingan.pipeline import extract_library
            libraries_dir = Path(__file__).parent / "data" / "libraries"

            for lib_id, ver in deps:
                version_dir = libraries_dir / lib_id / "versions" / ver
                if not version_dir.exists():
                    console.print(f"[cyan]Auto-extracting documentation for {lib_id} v{ver} (Pass 1 - deterministic)...[/]")
                    try:
                        asyncio.run(extract_library(
                            library_id=lib_id,
                            version=ver,
                            skip_llm=True
                        ))
                        console.print(f"[green]✓ Extracted {lib_id} v{ver}[/]")
                    except Exception as ex:
                        console.print(f"[yellow]Failed to auto-extract {lib_id}: {ex}[/]")
    except Exception as e:
        console.print(f"[yellow]Failed scanning or extracting dependencies: {e}[/]")



def _install_claude(project_scope: bool) -> None:
    """Install for Claude Code — CLAUDE.md + PreToolUse hook."""
    if project_scope:
        base = Path.cwd()
    else:
        base = Path.home()

    # Write skill content to CLAUDE.md
    claude_md = base / "CLAUDE.md"
    existing = ""
    if claude_md.exists():
        existing = claude_md.read_text()

    if "Sharingan" not in existing:
        with open(claude_md, "a") as f:
            f.write("\n\n" + get_skill_content(base))
        console.print(f"  → Updated {claude_md}")
    else:
        # Might need to force update in real life, but appending or skipping if exists is original logic
        pass

    # Write PreToolUse hook
    settings_dir = base / ".claude"
    settings_dir.mkdir(exist_ok=True)
    settings_path = settings_dir / "settings.json"

    settings = {}
    if settings_path.exists():
        with open(settings_path) as f:
            settings = json.load(f)

    # Merge hooks
    if "hooks" not in settings:
        settings["hooks"] = {}
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    # Check if already installed
    existing_hooks = settings["hooks"]["PreToolUse"]
    if not any("sharingan" in str(h).lower() for h in existing_hooks):
        existing_hooks.extend(PRETOOLUSE_HOOK["hooks"]["PreToolUse"])
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)
        console.print(f"  → Updated {settings_path}")


def _install_codex(project_scope: bool) -> None:
    """Install for Codex — AGENTS.md + hooks.json."""
    base = Path.cwd() if project_scope else Path.home()

    # Write AGENTS.md
    agents_md = base / "AGENTS.md"
    existing = ""
    if agents_md.exists():
        existing = agents_md.read_text()

    if "Sharingan" not in existing:
        with open(agents_md, "a") as f:
            f.write("\n\n" + get_skill_content(base))
        console.print(f"  → Updated {agents_md}")

    # Write hooks.json
    codex_dir = base / ".codex"
    codex_dir.mkdir(exist_ok=True)
    hooks_path = codex_dir / "hooks.json"

    hooks = {}
    if hooks_path.exists():
        with open(hooks_path) as f:
            hooks = json.load(f)

    if "PreToolUse" not in hooks:
        hooks.update(PRETOOLUSE_HOOK)
        with open(hooks_path, "w") as f:
            json.dump(hooks, f, indent=2)
        console.print(f"  → Updated {hooks_path}")


def _install_cursor(project_scope: bool) -> None:
    """Install for Cursor — .cursor/rules/sharingan.mdc."""
    base = Path.cwd()  # Cursor rules are always project-scoped
    rules_dir = base / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    rule_path = rules_dir / "sharingan.mdc"
    rule_path.write_text(get_cursor_rule(base))
    console.print(f"  → Created {rule_path}")


def _install_gemini(project_scope: bool) -> None:
    """Install for Gemini CLI — GEMINI.md."""
    base = Path.cwd() if project_scope else Path.home()
    gemini_md = base / "GEMINI.md"

    existing = ""
    if gemini_md.exists():
        existing = gemini_md.read_text()

    if "Sharingan" not in existing:
        with open(gemini_md, "a") as f:
            f.write("\n\n" + get_skill_content(base))
        console.print(f"  → Updated {gemini_md}")


def _install_antigravity(project_scope: bool) -> None:
    """Install for Google Antigravity — .agents/rules."""
    base = Path.cwd()
    rules_dir = base / ".agents" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    rule_path = rules_dir / "sharingan.md"
    rule_path.write_text(get_skill_content(base))
    console.print(f"  → Created {rule_path}")


def _install_agents_md(project_scope: bool) -> None:
    """Generic AGENTS.md installer for platforms that use it."""
    base = Path.cwd() if project_scope else Path.home()
    agents_md = base / "AGENTS.md"

    existing = ""
    if agents_md.exists():
        existing = agents_md.read_text()

    if "Sharingan" not in existing:
        with open(agents_md, "a") as f:
            f.write("\n\n" + get_skill_content(base))
        console.print(f"  → Updated {agents_md}")
