"""
sharingan.extract — Pass 2: LLM-assisted semantic extraction.

Uses an LLM to:
- Summarize prose documentation into concise descriptions
- Infer relationships between API symbols
- Detect deprecation patterns
- Score confidence on inferred edges
- Discover cross-library connections

Backend auto-detection: Anthropic → OpenAI → Ollama (Graphify pattern).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from sharingan.parse import ParsedPage, ParsedSignature

console = Console()


@dataclass
class ExtractedNode:
    """A node extracted by the LLM from documentation."""

    id: str
    node_type: str  # "symbol", "guide", "config"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedEdge:
    """An edge extracted by the LLM."""

    source: str
    target: str
    edge_type: str
    confidence: str = "INFERRED"
    confidence_score: float = 0.8
    description: str = ""


@dataclass
class ExtractionResult:
    """Result of Pass 2 LLM extraction for a page."""

    page_key: str
    nodes: list[ExtractedNode] = field(default_factory=list)
    edges: list[ExtractedEdge] = field(default_factory=list)
    summary: str = ""
    error: str | None = None


# ─── LLM BACKEND AUTO-DETECTION ──────────────────────────────────────


def detect_backend() -> str:
    """Auto-detect available LLM backend (Graphify-style priority).

    Priority: Anthropic → OpenAI → Ollama → None
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    
    # Check if ollama is running locally and has at least one model
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    if os.environ.get("OLLAMA_MODEL"):
        return "ollama"
        
    try:
        import httpx
        resp = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            if models:
                return "ollama"
    except Exception:
        pass
    return "none"


# ─── EXTRACTION PROMPTS ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are Sharingan, a documentation analysis engine. Your task is to extract
structured knowledge from technical documentation pages.

Given a documentation page, extract:

1. **API Symbols** — functions, classes, types, interfaces, hooks, components, constants
   that are being documented (not just mentioned in examples).
   For each symbol, provide:
   - name, kind, module_path, signature, description (1-3 sentences)
   - parameters with types and descriptions
   - return type
   - whether it's deprecated and what replaces it

2. **Relationships** between symbols:
   - RELATED_TO: symbols that work together or are commonly used together
   - DEPRECATED_BY: if a symbol replaces an older one
   - EXTENDS/IMPLEMENTS: class hierarchy relationships

3. **Guide Summary** — a concise 200-500 word summary of what this page covers,
   focusing on practical usage patterns.

Output ONLY valid JSON matching this schema:
{
  "symbols": [
    {
      "name": "string",
      "kind": "function|class|type|interface|hook|component|constant|decorator",
      "module_path": "string (import path)",
      "signature": "string (full signature)",
      "description": "string (1-3 sentences)",
      "parameters": [{"name": "string", "type": "string", "required": true, "description": "string"}],
      "return_type": "string",
      "deprecated": false,
      "deprecated_by": "string|null"
    }
  ],
  "relationships": [
    {
      "source": "symbol_name",
      "target": "symbol_name",
      "type": "RELATED_TO|DEPRECATED_BY|EXTENDS|IMPLEMENTS",
      "confidence_score": 0.8,
      "description": "string"
    }
  ],
  "summary": "string (200-500 word summary of this page)"
}"""


def _build_extraction_prompt(parsed: ParsedPage) -> str:
    """Build the extraction prompt for a parsed documentation page."""
    parts = [f"# Documentation Page: {parsed.title}\n"]

    if parsed.frontmatter:
        parts.append(f"Frontmatter: {json.dumps(parsed.frontmatter)}\n")

    # Include heading structure
    if parsed.headings:
        parts.append("## Heading Structure:")
        for h in parsed.headings:
            indent = "  " * (h.level - 1)
            parts.append(f"{indent}- {h.text}")
        parts.append("")

    # Include signatures already found in Pass 1
    if parsed.signatures:
        parts.append("## API Signatures Found (Pass 1):")
        for sig in parsed.signatures:
            parts.append(f"- {sig.kind}: {sig.name} — {sig.signature}")
        parts.append("")

    # Include tables (often contain parameter info)
    if parsed.tables:
        parts.append("## Tables Found:")
        for table in parsed.tables:
            if table.context_heading:
                parts.append(f"Context: {table.context_heading}")
            parts.append(f"Headers: {' | '.join(table.headers)}")
            for row in table.rows[:5]:  # limit rows to save tokens
                parts.append(f"  {' | '.join(row)}")
        parts.append("")

    # Include prose text (limited to save tokens)
    prose = parsed.raw_text.strip()
    if len(prose) > 8000:
        prose = prose[:8000] + "\n...[truncated]"
    parts.append("## Page Content:\n")
    parts.append(prose)

    return "\n".join(parts)


# ─── BACKEND-SPECIFIC CALLERS ─────────────────────────────────────────


async def _call_anthropic(prompt: str, system: str) -> str:
    """Call Anthropic Claude API."""
    try:
        import anthropic
    except ImportError:
        raise ImportError("Install anthropic: pip install sharingan[anthropic]")

    client = anthropic.AsyncAnthropic()
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    message = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def _call_openai(prompt: str, system: str) -> str:
    """Call OpenAI API."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise ImportError("Install openai: pip install sharingan[openai]")

    client = AsyncOpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or "{}"


async def _call_ollama(prompt: str, system: str) -> str:
    """Call local Ollama instance."""
    import httpx

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL")
    if not model:
        try:
            resp = httpx.get(f"{base_url}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                tags = resp.json()
                models = tags.get("models", [])
                if models:
                    model = models[0]["name"]
                    console.print(f"[cyan]Auto-detected local Ollama model: '{model}'[/]")
        except Exception:
            pass
    if not model:
        model = "llama3.2"

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": "json",
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                try:
                    err_detail = e.response.json().get("error", "")
                except Exception:
                    err_detail = ""
                raise RuntimeError(
                    f"Ollama model '{model}' not found or API error: {err_detail or e}. "
                    f"Please make sure you have pulled this model locally (e.g. run 'ollama pull {model}') or set OLLAMA_MODEL."
                ) from e
            raise e


async def call_llm(prompt: str, system: str = SYSTEM_PROMPT, backend: str | None = None) -> str:
    """Call the LLM with auto-detected backend.

    Args:
        prompt: User prompt.
        system: System prompt.
        backend: Override backend detection.

    Returns:
        LLM response text.
    """
    if backend is None:
        backend = detect_backend()

    if backend == "anthropic":
        return await _call_anthropic(prompt, system)
    elif backend == "openai":
        return await _call_openai(prompt, system)
    elif backend == "ollama":
        return await _call_ollama(prompt, system)
    elif backend == "none":
        raise RuntimeError(
            "No LLM backend available. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
            "or start Ollama locally. Pass 2 (semantic extraction) requires an LLM."
        )
    else:
        raise ValueError(f"Unknown backend: {backend}")


# ─── MAIN EXTRACTION ─────────────────────────────────────────────────


def _parse_llm_response(
    response: str, version_id: str, page_key: str
) -> ExtractionResult:
    """Parse LLM JSON response into ExtractionResult."""
    result = ExtractionResult(page_key=page_key)

    try:
        # Try to extract JSON from the response
        text = response.strip()
        print(f"[LLM RAW RESPONSE]\n{text}\n[/LLM RAW RESPONSE]")
        # Handle markdown-wrapped JSON
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        data = json.loads(text)
    except json.JSONDecodeError as e:
        result.error = f"Failed to parse LLM response: {e}"
        return result

    result.summary = data.get("summary", "")

    # Parse symbols into nodes
    for sym in data.get("symbols", []):
        name = sym.get("name", "")
        if not name:
            continue
        module_path = sym.get("module_path", "")
        node_id = f"{version_id}::{module_path}::{name}" if module_path else f"{version_id}::{name}"

        result.nodes.append(
            ExtractedNode(
                id=node_id,
                node_type="symbol",
                data={
                    "id": node_id,
                    "version_id": version_id,
                    "module_path": module_path,
                    "name": name,
                    "kind": sym.get("kind", "function"),
                    "signature": sym.get("signature", ""),
                    "description": sym.get("description", ""),
                    "parameters": sym.get("parameters", []),
                    "return_type": sym.get("return_type", ""),
                    "deprecated": sym.get("deprecated", False),
                    "deprecated_by": sym.get("deprecated_by"),
                    "source_url": "",
                    "confidence": "INFERRED",
                    "node_type": "symbol",
                },
            )
        )

    # Parse relationships into edges
    for rel in data.get("relationships", []):
        source_name = rel.get("source", "")
        target_name = rel.get("target", "")
        if not source_name or not target_name:
            continue
        result.edges.append(
            ExtractedEdge(
                source=source_name,  # will be resolved to full IDs later
                target=target_name,
                edge_type=rel.get("type", "RELATED_TO"),
                confidence="INFERRED",
                confidence_score=rel.get("confidence_score", 0.8),
                description=rel.get("description", ""),
            )
        )

    return result


async def extract_page(
    parsed: ParsedPage,
    version_id: str,
    backend: str | None = None,
) -> ExtractionResult:
    """Run Pass 2 (LLM semantic extraction) on a parsed page.

    Args:
        parsed: Output from Pass 1 (parse.py).
        version_id: Version identifier (e.g., "nextjs@15.3.2").
        backend: LLM backend override.

    Returns:
        ExtractionResult with nodes and edges.
    """
    # Skip pages with too little content
    if parsed.word_count < 50 and not parsed.signatures:
        return ExtractionResult(
            page_key=parsed.page_key,
            summary="Page too short for meaningful extraction.",
        )

    prompt = _build_extraction_prompt(parsed)

    try:
        response = await call_llm(prompt, SYSTEM_PROMPT, backend)
        return _parse_llm_response(response, version_id, parsed.page_key)
    except Exception as e:
        console.print(f"[red]LLM extraction failed for {parsed.page_key}: {e}[/]")
        return ExtractionResult(
            page_key=parsed.page_key,
            error=str(e),
        )


def merge_pass1_pass2(
    parsed: ParsedPage,
    extracted: ExtractionResult,
    version_id: str,
    source_url: str = "",
) -> ExtractionResult:
    """Merge Pass 1 (deterministic) and Pass 2 (LLM) results.

    Pass 1 signatures take priority (EXTRACTED confidence).
    Pass 2 fills in descriptions, relationships, and additional symbols.
    """
    merged = ExtractionResult(page_key=parsed.page_key, summary=extracted.summary)

    # Track names from Pass 1
    pass1_names: set[str] = set()

    # Add Pass 1 signatures as EXTRACTED nodes
    for sig in parsed.signatures:
        node_id = f"{version_id}::{sig.module_path}::{sig.name}" if sig.module_path else f"{version_id}::{sig.name}"
        pass1_names.add(sig.name)

        # Try to find matching Pass 2 data for richer description
        p2_match = None
        for node in extracted.nodes:
            if node.data.get("name") == sig.name:
                p2_match = node
                break

        merged.nodes.append(
            ExtractedNode(
                id=node_id,
                node_type="symbol",
                data={
                    "id": node_id,
                    "version_id": version_id,
                    "module_path": sig.module_path,
                    "name": sig.name,
                    "kind": sig.kind,
                    "signature": sig.signature,
                    "description": (
                        p2_match.data.get("description", sig.description)
                        if p2_match
                        else sig.description
                    ),
                    "parameters": sig.parameters or (
                        p2_match.data.get("parameters", []) if p2_match else []
                    ),
                    "return_type": sig.return_type or (
                        p2_match.data.get("return_type", "") if p2_match else ""
                    ),
                    "deprecated": (
                        p2_match.data.get("deprecated", False) if p2_match else False
                    ),
                    "deprecated_by": (
                        p2_match.data.get("deprecated_by") if p2_match else None
                    ),
                    "source_url": source_url,
                    "confidence": "EXTRACTED",
                    "node_type": "symbol",
                },
            )
        )

    # Add Pass 2 symbols not found in Pass 1
    for node in extracted.nodes:
        name = node.data.get("name", "")
        if name and name not in pass1_names:
            node.data["source_url"] = source_url
            merged.nodes.append(node)

    # Add all edges from Pass 2
    merged.edges = extracted.edges

    # Add guide node for this page
    if parsed.title and (parsed.word_count > 100 or parsed.code_blocks):
        guide_id = f"{version_id}::guides/{parsed.page_key}"
        code_examples = [
            {
                "code": block.code,
                "language": block.language,
                "title": block.title,
            }
            for block in parsed.code_blocks[:5]  # limit to 5 examples
        ]
        merged.nodes.append(
            ExtractedNode(
                id=guide_id,
                node_type="guide",
                data={
                    "id": guide_id,
                    "version_id": version_id,
                    "title": parsed.title,
                    "slug": parsed.page_key,
                    "content_summary": extracted.summary or "",
                    "code_examples": code_examples,
                    "related_symbols": [n.id for n in merged.nodes if n.node_type == "symbol"],
                    "source_url": source_url,
                    "node_type": "guide",
                },
            )
        )

    return merged
