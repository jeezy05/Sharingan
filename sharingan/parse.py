"""
sharingan.parse — Pass 1: Deterministic documentation parsing (zero LLM cost).

Extracts structured information from documentation files using rule-based
parsing. This is the "free" pass — no API calls, no token costs.

Extracts:
- Heading structure (h1-h6 hierarchy)
- Fenced code blocks with language tags
- API signature patterns (function/class/type definitions)
- Markdown tables (parameter tables, config tables)
- Internal links / cross-references
- JSDoc/TypeDoc style annotations
- Markdown frontmatter (YAML)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class ParsedCodeBlock:
    """A fenced code block extracted from documentation."""

    code: str
    language: str
    title: str = ""
    line_number: int = 0


@dataclass
class ParsedHeading:
    """A heading extracted from documentation."""

    text: str
    level: int  # 1-6
    slug: str = ""
    line_number: int = 0


@dataclass
class ParsedSignature:
    """An API signature extracted from documentation."""

    name: str
    kind: str  # function, class, type, interface, hook, component, constant, etc.
    signature: str  # full signature string
    module_path: str = ""
    description: str = ""
    parameters: list[dict[str, Any]] = field(default_factory=list)
    return_type: str = ""
    line_number: int = 0
    confidence: str = "EXTRACTED"


@dataclass
class ParsedTable:
    """A markdown table extracted from documentation."""

    headers: list[str]
    rows: list[list[str]]
    context_heading: str = ""  # nearest heading above the table
    line_number: int = 0


@dataclass
class ParsedLink:
    """A cross-reference link extracted from documentation."""

    text: str
    url: str
    is_internal: bool = False
    line_number: int = 0


@dataclass
class ParsedPage:
    """Complete parsed output for a single documentation page.

    This is the output of Pass 1 (deterministic extraction).
    """

    page_key: str
    source_url: str
    file_type: str
    title: str = ""
    frontmatter: dict[str, Any] = field(default_factory=dict)
    headings: list[ParsedHeading] = field(default_factory=list)
    code_blocks: list[ParsedCodeBlock] = field(default_factory=list)
    signatures: list[ParsedSignature] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    links: list[ParsedLink] = field(default_factory=list)
    raw_text: str = ""  # prose text with code blocks stripped (for Pass 2)
    word_count: int = 0


# ─── REGEX PATTERNS ───────────────────────────────────────────────────

# Frontmatter (YAML between --- markers)
RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Fenced code blocks (``` or ~~~)
RE_CODE_BLOCK = re.compile(
    r"^(?P<fence>`{3,}|~{3,})(?P<lang>[^\s`~]*)(?:\s+(?P<title>[^\n]*))?\n"
    r"(?P<code>.*?)\n(?P=fence)\s*$",
    re.MULTILINE | re.DOTALL,
)

# Headings (# to ######)
RE_HEADING = re.compile(r"^(?P<level>#{1,6})\s+(?P<text>.+?)(?:\s*#*)?$", re.MULTILINE)

# Markdown links [text](url)
RE_LINK = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<url>[^)]+)\)")

# Markdown tables
RE_TABLE_ROW = re.compile(r"^\|(.+)\|$", re.MULTILINE)
RE_TABLE_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$", re.MULTILINE)

# API signature patterns in code blocks
# TypeScript/JavaScript
RE_TS_FUNCTION = re.compile(
    r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(?P<name>\w+)"
    r"(?:<[^>]+>)?\s*\((?P<params>[^)]*)\)(?:\s*:\s*(?P<return>\S+))?",
)
RE_TS_CONST_FN = re.compile(
    r"(?:export\s+)?(?:const|let|var)\s+(?P<name>\w+)\s*"
    r"(?::\s*[^=]+)?\s*=\s*(?:async\s+)?"
    r"(?:\([^)]*\)|[^=])\s*=>",
)
RE_TS_CLASS = re.compile(
    r"(?:export\s+)?(?:abstract\s+)?class\s+(?P<name>\w+)"
    r"(?:<[^>]+>)?(?:\s+extends\s+(?P<extends>\w+))?"
    r"(?:\s+implements\s+(?P<implements>[^{]+))?",
)
RE_TS_INTERFACE = re.compile(
    r"(?:export\s+)?interface\s+(?P<name>\w+)(?:<[^>]+>)?",
)
RE_TS_TYPE = re.compile(
    r"(?:export\s+)?type\s+(?P<name>\w+)(?:<[^>]+>)?\s*=",
)
RE_TS_ENUM = re.compile(
    r"(?:export\s+)?(?:const\s+)?enum\s+(?P<name>\w+)",
)

# Python
RE_PY_FUNCTION = re.compile(
    r"(?:async\s+)?def\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
    r"(?:\s*->\s*(?P<return>\S+))?",
)
RE_PY_CLASS = re.compile(
    r"class\s+(?P<name>\w+)(?:\((?P<bases>[^)]*)\))?:",
)
RE_PY_DECORATOR = re.compile(
    r"@(?P<name>[\w.]+)(?:\((?P<args>[^)]*)\))?",
)

# React hooks pattern
RE_REACT_HOOK = re.compile(
    r"(?:export\s+)?(?:function\s+)?(?P<name>use[A-Z]\w+)\s*\(",
)

# React component
RE_REACT_COMPONENT = re.compile(
    r"(?:export\s+)?(?:default\s+)?(?:function|const)\s+(?P<name>[A-Z]\w+)"
    r"\s*(?:\(|=\s*\()",
)


# ─── PARSING FUNCTIONS ────────────────────────────────────────────────


def _slugify(text: str) -> str:
    """Convert heading text to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug.strip("-")


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter from markdown content.

    Returns:
        Tuple of (frontmatter_dict, content_without_frontmatter).
    """
    match = RE_FRONTMATTER.match(content)
    if match:
        try:
            fm = yaml.safe_load(match.group(1)) or {}
            remaining = content[match.end():]
            return fm, remaining
        except yaml.YAMLError:
            return {}, content
    return {}, content


def parse_headings(content: str) -> list[ParsedHeading]:
    """Extract all headings from markdown content."""
    headings = []
    for match in RE_HEADING.finditer(content):
        line_num = content[:match.start()].count("\n") + 1
        text = match.group("text").strip()
        headings.append(
            ParsedHeading(
                text=text,
                level=len(match.group("level")),
                slug=_slugify(text),
                line_number=line_num,
            )
        )
    return headings


def parse_code_blocks(content: str) -> list[ParsedCodeBlock]:
    """Extract all fenced code blocks from markdown content."""
    blocks = []
    for match in RE_CODE_BLOCK.finditer(content):
        line_num = content[:match.start()].count("\n") + 1
        lang = match.group("lang") or ""
        # Normalize language aliases
        lang = lang.lower().strip()
        lang_map = {
            "js": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "jsx": "javascript",
            "py": "python",
            "rb": "ruby",
            "yml": "yaml",
            "sh": "bash",
            "shell": "bash",
        }
        lang = lang_map.get(lang, lang)

        blocks.append(
            ParsedCodeBlock(
                code=match.group("code"),
                language=lang,
                title=match.group("title") or "",
                line_number=line_num,
            )
        )
    return blocks


def parse_tables(content: str) -> list[ParsedTable]:
    """Extract markdown tables from content."""
    tables = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Look for table header row
        if line.startswith("|") and line.endswith("|"):
            # Check if next line is separator
            if i + 1 < len(lines) and RE_TABLE_SEPARATOR.match(lines[i + 1].strip()):
                # Found a table
                headers = [
                    cell.strip() for cell in line.strip("|").split("|")
                ]
                rows = []
                j = i + 2  # skip header + separator
                while j < len(lines):
                    row_line = lines[j].strip()
                    if row_line.startswith("|") and row_line.endswith("|"):
                        cells = [
                            cell.strip() for cell in row_line.strip("|").split("|")
                        ]
                        rows.append(cells)
                        j += 1
                    else:
                        break

                # Find nearest heading above
                context = ""
                for k in range(i - 1, -1, -1):
                    heading_match = RE_HEADING.match(lines[k])
                    if heading_match:
                        context = heading_match.group("text").strip()
                        break

                tables.append(
                    ParsedTable(
                        headers=headers,
                        rows=rows,
                        context_heading=context,
                        line_number=i + 1,
                    )
                )
                i = j
                continue
        i += 1
    return tables


def parse_links(content: str) -> list[ParsedLink]:
    """Extract markdown links from content."""
    links = []
    for match in RE_LINK.finditer(content):
        url = match.group("url")
        is_internal = (
            url.startswith("/")
            or url.startswith("./")
            or url.startswith("../")
            or url.startswith("#")
        )
        line_num = content[:match.start()].count("\n") + 1
        links.append(
            ParsedLink(
                text=match.group("text"),
                url=url,
                is_internal=is_internal,
                line_number=line_num,
            )
        )
    return links


def extract_signatures_from_code(
    code_blocks: list[ParsedCodeBlock],
) -> list[ParsedSignature]:
    """Extract API signatures from code blocks.

    This is the core of Pass 1 — identifying function, class, type, and
    interface definitions from code examples in documentation.
    """
    signatures = []
    seen_names: set[str] = set()

    for block in code_blocks:
        code = block.code
        lang = block.language

        if lang in ("typescript", "javascript"):
            # React hooks
            for m in RE_REACT_HOOK.finditer(code):
                name = m.group("name")
                if name not in seen_names:
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="hook",
                            signature=_extract_full_line(code, m.start()),
                            line_number=block.line_number,
                        )
                    )

            # React components
            for m in RE_REACT_COMPONENT.finditer(code):
                name = m.group("name")
                if name not in seen_names and not name.startswith("use"):
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="component",
                            signature=_extract_full_line(code, m.start()),
                            line_number=block.line_number,
                        )
                    )

            # Functions
            for m in RE_TS_FUNCTION.finditer(code):
                name = m.group("name")
                if name not in seen_names:
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="function",
                            signature=_extract_full_line(code, m.start()),
                            parameters=_parse_ts_params(m.group("params")),
                            return_type=m.group("return") or "",
                            line_number=block.line_number,
                        )
                    )

            # Classes
            for m in RE_TS_CLASS.finditer(code):
                name = m.group("name")
                if name not in seen_names:
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="class",
                            signature=_extract_full_line(code, m.start()),
                            line_number=block.line_number,
                        )
                    )

            # Interfaces
            for m in RE_TS_INTERFACE.finditer(code):
                name = m.group("name")
                if name not in seen_names:
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="interface",
                            signature=_extract_full_line(code, m.start()),
                            line_number=block.line_number,
                        )
                    )

            # Type aliases
            for m in RE_TS_TYPE.finditer(code):
                name = m.group("name")
                if name not in seen_names:
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="type",
                            signature=_extract_full_line(code, m.start()),
                            line_number=block.line_number,
                        )
                    )

            # Enums
            for m in RE_TS_ENUM.finditer(code):
                name = m.group("name")
                if name not in seen_names:
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="enum",
                            signature=_extract_full_line(code, m.start()),
                            line_number=block.line_number,
                        )
                    )

        elif lang == "python":
            # Functions
            for m in RE_PY_FUNCTION.finditer(code):
                name = m.group("name")
                if name not in seen_names and not name.startswith("_"):
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="function",
                            signature=_extract_full_line(code, m.start()),
                            parameters=_parse_py_params(m.group("params")),
                            return_type=m.group("return") or "",
                            line_number=block.line_number,
                        )
                    )

            # Classes
            for m in RE_PY_CLASS.finditer(code):
                name = m.group("name")
                if name not in seen_names:
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="class",
                            signature=_extract_full_line(code, m.start()),
                            line_number=block.line_number,
                        )
                    )

            # Decorators
            for m in RE_PY_DECORATOR.finditer(code):
                name = m.group("name")
                if name not in seen_names and "." not in name:
                    seen_names.add(name)
                    signatures.append(
                        ParsedSignature(
                            name=name,
                            kind="decorator",
                            signature=_extract_full_line(code, m.start()),
                            line_number=block.line_number,
                        )
                    )

    return signatures


def _extract_full_line(code: str, pos: int) -> str:
    """Extract the full line containing position `pos`."""
    start = code.rfind("\n", 0, pos) + 1
    end = code.find("\n", pos)
    if end == -1:
        end = len(code)
    return code[start:end].strip()


def _parse_ts_params(params_str: str) -> list[dict[str, Any]]:
    """Parse TypeScript parameter string into structured params."""
    params = []
    if not params_str.strip():
        return params

    # Simple split on commas (doesn't handle nested generics perfectly)
    for param_str in params_str.split(","):
        param_str = param_str.strip()
        if not param_str:
            continue
        # Handle destructured params
        if param_str.startswith("{") or param_str.startswith("["):
            params.append({
                "name": param_str.split(":")[0].strip() if ":" in param_str else param_str,
                "type": param_str.split(":", 1)[1].strip() if ":" in param_str else "unknown",
                "required": "?" not in param_str,
            })
        else:
            parts = param_str.split(":")
            name = parts[0].strip().rstrip("?")
            type_str = parts[1].strip() if len(parts) > 1 else "unknown"
            required = "?" not in parts[0]
            # Check for default value
            default = None
            if "=" in type_str:
                type_str, default = type_str.split("=", 1)
                type_str = type_str.strip()
                default = default.strip()
                required = False
            params.append({
                "name": name,
                "type": type_str,
                "required": required,
                "default": default,
            })
    return params


def _parse_py_params(params_str: str) -> list[dict[str, Any]]:
    """Parse Python parameter string into structured params."""
    params = []
    if not params_str.strip():
        return params

    for param_str in params_str.split(","):
        param_str = param_str.strip()
        if not param_str or param_str in ("self", "cls"):
            continue

        default = None
        required = True
        if "=" in param_str:
            param_str, default = param_str.split("=", 1)
            default = default.strip()
            required = False

        if ":" in param_str:
            name, type_str = param_str.split(":", 1)
            params.append({
                "name": name.strip().lstrip("*"),
                "type": type_str.strip(),
                "required": required,
                "default": default,
            })
        else:
            params.append({
                "name": param_str.strip().lstrip("*"),
                "type": "unknown",
                "required": required,
                "default": default,
            })
    return params


def _strip_code_blocks(content: str) -> str:
    """Remove fenced code blocks, leaving only prose text."""
    return RE_CODE_BLOCK.sub("", content)


def parse_page(
    page_key: str,
    content: str,
    source_url: str = "",
    file_type: str = "md",
) -> ParsedPage:
    """Parse a single documentation page (Pass 1).

    Performs deterministic extraction of all structured information
    with zero LLM cost.

    Args:
        page_key: Unique identifier for this page.
        content: Raw content of the page.
        source_url: URL where this page was fetched from.
        file_type: File extension (md, mdx, rst, html).

    Returns:
        ParsedPage with all extracted structural information.
    """
    # Parse frontmatter
    frontmatter, content_body = parse_frontmatter(content)

    # Extract title from frontmatter or first heading
    title = frontmatter.get("title", "")

    # Parse structural elements
    headings = parse_headings(content_body)
    code_blocks = parse_code_blocks(content_body)
    tables = parse_tables(content_body)
    links = parse_links(content_body)

    # Extract API signatures from code blocks
    signatures = extract_signatures_from_code(code_blocks)

    # Use first h1 as title if not in frontmatter
    if not title and headings:
        for h in headings:
            if h.level == 1:
                title = h.text
                break
        if not title:
            title = headings[0].text

    # Strip code blocks to get prose-only text for Pass 2
    raw_text = _strip_code_blocks(content_body)
    word_count = len(raw_text.split())

    return ParsedPage(
        page_key=page_key,
        source_url=source_url,
        file_type=file_type,
        title=title,
        frontmatter=frontmatter,
        headings=headings,
        code_blocks=code_blocks,
        signatures=signatures,
        tables=tables,
        links=links,
        raw_text=raw_text,
        word_count=word_count,
    )
