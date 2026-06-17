# Sharingan 👁️

**Open-source documentation knowledge graph for AI coding assistants.**

Turn the latest documentation of popular tech stacks into a queryable knowledge graph — with plugins for Claude Code, Codex, Cursor, Gemini CLI, and more.

> Think of it as: **Context7, but fully open-source.** Or **Graphify, but for external library docs instead of your codebase.**

## Why Sharingan?

AI coding assistants hallucinate outdated APIs. Their training data has a cutoff. Sharingan solves this by maintaining a **live, version-aware knowledge graph** of the documentation for the frameworks you actually use.

| Feature | Context7 | Graphify | **Sharingan** |
|:--------|:---------|:---------|:--------------|
| Open-source backend | ❌ | ✅ | ✅ |
| Documentation focus | ✅ | ❌ (code) | ✅ |
| Version tracking | ✅ | ❌ | ✅ (last 3 majors) |
| Offline-first | ❌ | ✅ | ✅ |
| Graph relationships | ❌ (vectors) | ✅ | ✅ |
| Migration queries | ❌ | ❌ | ✅ |
| Confidence tagging | ❌ | ✅ | ✅ |

## Quick Start

```bash
# Install
pip install sharingan
# or
uv tool install sharingan

# Extract documentation for a library
sharingan extract zod
sharingan extract nextjs --version 15.3.2
sharingan extract react --skip-llm  # Pass 1 only (free, no API key needed)

# Query the knowledge graph
sharingan query "useRouter" --lib nextjs
sharingan query "z.string" --lib zod

# Install into your AI assistant
sharingan install --platform claude
sharingan install --platform codex
sharingan install --platform cursor
```

## How It Works

Sharingan uses a **two-pass extraction pipeline** (inspired by [Graphify](https://github.com/safishamsi/graphify)):

### Pass 1 — Deterministic (Free, No API Calls)
- Parses markdown/HTML documentation
- Extracts code blocks, API signatures, parameter tables
- Identifies heading structure and cross-references
- **Zero token cost** — runs entirely locally

### Pass 2 — Semantic (LLM-Assisted)
- Summarizes prose documentation
- Infers relationships between API symbols
- Detects deprecation patterns
- Scores confidence on inferred edges
- **Auto-detects backend**: Anthropic → OpenAI → Ollama

### Graph Building
- Merges Pass 1 + Pass 2 into a **NetworkX** directed graph
- Clusters related APIs into communities via **Leiden algorithm**
- Exports to JSON files in a git-friendly structure
- Every edge tagged with confidence: `EXTRACTED`, `INFERRED`, or `AMBIGUOUS`

## Covered Libraries

### Tier 1 (Available Now)
React, Next.js, TypeScript, Node.js, Python, FastAPI, PostgreSQL, Tailwind CSS, Prisma, Zod

### Tier 2 (Coming Soon)
Vue.js, Svelte, Django, Express.js, Docker, Supabase, Drizzle ORM, tRPC, Vite, shadcn/ui

### Tier 3 (Planned)
Angular, Rust, Go, Flask, LangChain, Vercel AI SDK, MongoDB, Redis, Stripe, AWS SDK

## CLI Commands

```bash
sharingan extract <library>     # Extract docs into knowledge graph
sharingan list                  # Show all libraries in registry
sharingan info <library>        # Show library details
sharingan query <question>      # Query the graph
sharingan status                # Show extraction statistics
sharingan install               # Install AI assistant skill
```

## For AI Assistant Plugin Developers

Sharingan exposes an **MCP server** for direct integration:

```bash
# Start MCP server (stdio transport)
python -m sharingan.serve

# Start MCP server (HTTP transport)
python -m sharingan.serve --transport http --port 8080
```

### MCP Tools Available

| Tool | Description |
|:-----|:------------|
| `resolve_library` | Find library by name |
| `get_symbol` | Get full API docs for a symbol |
| `search_docs` | Search guides and symbols |
| `get_migration` | Get migration guide between versions |
| `query_graph` | Free-form graph query |
| `get_neighbors` | Get related nodes |
| `shortest_path` | Find connection between symbols |

## Contributing

We welcome contributions! The most impactful ways to help:

1. **Add a library** — add an entry to `registry.json` and run the extraction pipeline
2. **Improve parsing** — better regex patterns for API signature extraction
3. **Report issues** — if extraction misses or misidentifies an API

```bash
# Dev setup
git clone https://github.com/sharingan-docs/sharingan
cd sharingan
uv sync --all-extras
uv run pytest tests/ -q
```

## License

MIT
