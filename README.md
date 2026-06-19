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
pip install sharingan-ai
# or
uv tool install sharingan-ai

# Extract documentation for a library
sharingan extract zod
sharingan extract nextjs --version 15.3.2
sharingan extract react --skip-llm  # Pass 1 only (free, no API key needed)

# Query the knowledge graph
sharingan query "useRouter" --lib nextjs
sharingan query "z.string" --lib zod

# Install into your AI assistant (run from your project root!)
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
- **Auto-detects backend**: Anthropic → OpenAI → Ollama → None (self-healing fallback to Pass 1)

### Graph Building
- Merges Pass 1 + Pass 2 into a **NetworkX** directed graph
- Clusters related APIs into communities via **Louvain community detection**
- Exports to JSON files in a git-friendly structure
- Every edge tagged with confidence: `EXTRACTED`, `INFERRED`, or `AMBIGUOUS`

### Data Storage

All extracted knowledge graphs are stored in `~/.sharingan/` (survives pip upgrades):
```
~/.sharingan/
├── libraries/
│   ├── nextjs/versions/15.3.2/
│   │   ├── graph.json
│   │   ├── symbols.json
│   │   ├── edges.json
│   │   └── ...
│   └── react/versions/19.1.0/
└── indexes/
    └── by-symbol-name.json
```

## Covered Libraries

### Tier 1 (Available Now)
React, Next.js, TypeScript, Node.js, Python, FastAPI, Tailwind CSS, Prisma, Zod

### Tier 2 (Coming Soon)
PostgreSQL, Vue.js, Svelte, Django, Express.js, Docker, Supabase, Drizzle ORM, tRPC, Vite, shadcn/ui

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
sharingan serve                 # Start MCP server
sharingan cluster <library>     # Detect API communities
```

## Model Context Protocol (MCP) Setup

Sharingan exposes a **Model Context Protocol (MCP)** server to connect your knowledge graph directly to AI coding assistants like Claude Desktop, Cursor, or Google Antigravity.

### 1. Start the Server

Sharingan supports both standard input/output (`stdio`) and network-based (`sse`) transports:

```bash
# Start the default stdio server (best for local configurations)
sharingan serve --transport stdio

# Start the network-based SSE server (best for cross-device queries)
sharingan serve --transport sse --port 8000
```

### 2. Register with Clients

Add Sharingan to your AI assistant's configuration:

#### 🤖 Claude Desktop / Claude Code
Add to your `claude_desktop_config.json` (located at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):
```json
{
  "mcpServers": {
    "sharingan": {
      "command": "sharingan",
      "args": ["serve"]
    }
  }
}
```

#### 📐 Google Antigravity
Add to your `mcp_config.json` file inside the `.gemini/config` directory:
```json
{
  "mcpServers": {
    "sharingan": {
      "command": "sharingan",
      "args": ["serve"]
    }
  }
}
```

#### 🚀 Cursor
1. Go to **Settings > Features > MCP**.
2. Click **+ Add New MCP Server**.
3. Fill out the fields:
   - **Name**: `sharingan`
   - **Type**: `command` (or `sse` if using network transport)
   - **Command/URL**: 
     - For `command`: `sharingan serve`
     - For `sse`: `http://localhost:8000/sse`

### 3. MCP Tools Available

Once registered, your AI assistant will dynamically call these tools to look up documentation:

| Tool | Description |
|:-----|:------------|
| `list_libraries` | List all available libraries in the graph |
| `search_symbols` | Search for API symbols (functions, classes, etc.) |
| `get_symbol_details` | Get full detailed documentation for a symbol |
| `get_neighbors` | Retrieve connected nodes and relations |

## Contributing

We welcome contributions! The most impactful ways to help:

1. **Add a library** — add an entry to `registry.json` and run the extraction pipeline
2. **Improve parsing** — better regex patterns for API signature extraction
3. **Report issues** — if extraction misses or misidentifies an API

```bash
# Dev setup
git clone https://github.com/jeezy05/Sharingan
cd Sharingan
uv sync --all-extras
uv run pytest tests/ -q
```

## License

MIT
