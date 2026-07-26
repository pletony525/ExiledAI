# POE2 Advisor — v1 Build Plan

## Context

[[POE2 Build & Trade Advisor]] had "Build v1" as a single, vague Next Step. With the [[Decision - RAG Stack for POE2 Advisor|RAG stack]] and Electron overlay UI both decided, this note breaks that into a concrete, ordered sequence. The guiding principle: **validate the RAG loop as a plain script before investing in the Electron shell** — the overlay is chrome around a backend that doesn't exist yet, so building it first risks polishing a UI around an untested retrieval pipeline.

## Steps

### 1. Infra: stand up pgvector
- Create a free-tier Postgres instance (Supabase or Neon)
- Enable the `pgvector` extension
- Schema: a chunks table — `id, source, content, embedding vector, metadata jsonb` (metadata holds item name, source URL, content type)

### 2. Scrape poe2db (v1 dataset only)
- Target: items, mods, uniques, skills pages — per the cleared ToS check in [[POE2 Build & Trade Advisor]]
- Keep request rate modest (robots.txt specifies no crawl-delay, but be conservative — e.g. ~1 req/sec)
- Store raw scraped content locally first (JSON or markdown files) before chunking, so scraping and embedding stay decoupled and re-runnable independently
- Hold off on poe2.dev/ascendancies for this pass — keep the v1 dataset small on purpose, per the original "small indexed dataset" scope

### 3. Chunk + embed
- Chunking strategy: poe2db content is already naturally atomic (one item/skill per page), so per-entry chunking is the likely starting point — revisit if retrieval quality suffers
- Call the OpenAI embeddings API per chunk
- Insert into the pgvector table with source metadata attached

### 4. Core RAG loop — CLI only, no UI yet
- Plain script: question → embed query → pgvector similarity search (top-k, e.g. 5) → stuff retrieved chunks into prompt → call the cheap LLM tier (Claude Haiku or GPT-4o-mini) → print the answer
- Test manually against real build/trading questions
- **This is the actual go/no-go gate.** Don't move to Step 5 until retrieval quality is genuinely useful, not just "it runs"

### 5. Electron overlay shell
- Always-on-top window, global hotkey to toggle visibility
- Confirm it renders correctly with the game in Borderless/Windowed Fullscreen (Exclusive Fullscreen won't allow overlays to draw on top)
- Chat UI: input box + scrollback, reusing React per the overlap with [[Full Stack Job Prep]]
- Wire to the backend — simplest version is a small local API server the Electron renderer calls over localhost

### 6. Clipboard item-context hotkey — optional enhancement
- Global hotkey simulates Ctrl+C on the hovered item (POE2's native clipboard-copy feature)
- Read the clipboard, parse the item text into structured mod data — reference [Awakened PoE Trade](https://github.com/SnosMe/awakened-poe-trade)'s parser as prior art
- Inject the parsed item as context into the next chat message

## Open Questions / Risks

- Chunking granularity for poe2db content is a guess until tested against real queries
- Python (FastAPI backend) + Electron (JS frontend) is a two-language split — Python fits because AI tooling is Python-first, but worth reconsidering if the split adds friction disproportionate to v1's size
- Retrieval quality is unknown until Step 4 runs — treat that step as the actual milestone, not "having a script"

## Related

- [[POE2 Build & Trade Advisor]]
- [[Decision - RAG Stack for POE2 Advisor]]
- [[RAG Pipeline Fundamentals]]
- [[AI Engineering Skill Gap]]
