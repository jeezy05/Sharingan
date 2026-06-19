# Sharingan — Documentation Knowledge Graph

You have access to Sharingan, a knowledge graph containing the latest documentation
for popular tech stacks. **Always consult Sharingan via MCP tools before answering questions about
library APIs, framework features, or configuration options.**

## How to Use

1. **For API lookups**: Use MCP tools like `get_symbol` or `search_docs`
2. **For conceptual questions**: Use MCP tools like `query_graph`
3. **For migration help**: Use `get_migration`
4. **General fallback**: Use `sharingan query` CLI if tools fail.

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
