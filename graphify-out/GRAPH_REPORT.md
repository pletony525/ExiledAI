# Graph Report - /Users/Tonyb/VsCode/ExiledAI  (2026-07-26)

## Corpus Check
- 3 files · ~3,269 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 83 nodes · 122 edges · 11 communities (10 shown, 1 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.82)
- Token cost: 48,043 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Dependencies & Infra Overview|Dependencies & Infra Overview]]
- [[_COMMUNITY_poe2db Scraper|poe2db Scraper]]
- [[_COMMUNITY_Chunking & Embedding Pipeline|Chunking & Embedding Pipeline]]
- [[_COMMUNITY_Build Plan & Project Decisions|Build Plan & Project Decisions]]
- [[_COMMUNITY_RAG Loop CLI Script|RAG Loop CLI Script]]
- [[_COMMUNITY_RAG Test Cross-Referencing Cases|RAG Test: Cross-Referencing Cases]]
- [[_COMMUNITY_RAG Test Direct Lookup & Precision Cases|RAG Test: Direct Lookup & Precision Cases]]
- [[_COMMUNITY_GoNo-Go Gate Concept|Go/No-Go Gate Concept]]
- [[_COMMUNITY_RAG Test Out-of-Scope Traps|RAG Test: Out-of-Scope Traps]]
- [[_COMMUNITY_Project README|Project README]]

## God Nodes (most connected - your core abstractions)
1. `scrape_unique_page()` - 6 edges
2. `scrape_category_mods()` - 6 edges
3. `POE2 Advisor — v1 Build Plan` - 6 edges
4. `Step 2: Scrape poe2db (v1 dataset only)` - 6 edges
5. `answer_question()` - 6 edges
6. `Cross-Referencing (Q4-7)` - 6 edges
7. `build_all_chunks()` - 5 edges
8. `fetch()` - 5 edges
9. `scrape_gem_page()` - 5 edges
10. `Step 3: Chunk + embed` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Step 1: Infra — stand up pgvector` --conceptually_related_to--> `python-dotenv`  [INFERRED]
  docs/v1-build-plan.md → backend/requirements.txt
- `Step 2: Scrape poe2db (v1 dataset only)` --conceptually_related_to--> `beautifulsoup4`  [INFERRED]
  docs/v1-build-plan.md → backend/requirements.txt
- `Step 2: Scrape poe2db (v1 dataset only)` --conceptually_related_to--> `lxml`  [INFERRED]
  docs/v1-build-plan.md → backend/requirements.txt
- `Step 2: Scrape poe2db (v1 dataset only)` --conceptually_related_to--> `requests`  [INFERRED]
  docs/v1-build-plan.md → backend/requirements.txt
- `Step 3: Chunk + embed` --conceptually_related_to--> `psycopg (PostgreSQL driver)`  [INFERRED]
  docs/v1-build-plan.md → backend/requirements.txt

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Web Scraping Pipeline** — backend_requirements_requests, backend_requirements_beautifulsoup4, backend_requirements_lxml, docs_step4_test_questions_scraped_corpus [INFERRED 0.85]
- **RAG Test Question Framework** — docs_step4_test_questions_direct_lookups, docs_step4_test_questions_cross_referencing, docs_step4_test_questions_precision_tier_checks, docs_step4_test_questions_out_of_scope_traps [EXTRACTED 1.00]
- **RAG Pipeline Stack (embed + store + retrieve)** — backend_requirements_openai, backend_requirements_psycopg, docs_step4_test_questions_semantic_retrieval [INFERRED 0.75]

## Communities (11 total, 1 thin omitted)

### Community 0 - "Dependencies & Infra Overview"
Cohesion: 0.27
Nodes (13): beautifulsoup4, lxml, psycopg (PostgreSQL driver), python-dotenv, requests, CLI Script (test runner), Scraped Corpus (uniques, skill gems, support gems, mods), Step 3: Chunk + embed (+5 more)

### Community 1 - "poe2db Scraper"
Cohesion: 0.37
Nodes (12): already_scraped(), extract_balanced_json(), extract_links(), fetch(), Find `marker` then extract the first balanced {...} JSON object that follows,, run(), safe_call(), save_json() (+4 more)

### Community 2 - "Chunking & Embedding Pipeline"
Cohesion: 0.33
Nodes (10): build_all_chunks(), clean_html(), clean_text(), format_values(), gem_to_chunk(), load_deduped_mods(), mod_to_chunk(), Mods repeat across category files (e.g. the same affix can spawn on     both Cla (+2 more)

### Community 3 - "Build Plan & Project Decisions"
Cohesion: 0.18
Nodes (12): POE2 Advisor — v1 Build Plan, AI Engineering Skill Gap, Awakened PoE Trade, Step 6: Clipboard item-context hotkey (optional), Step 4: Core RAG loop (CLI only), Decision - RAG Stack for POE2 Advisor, Step 5: Electron overlay shell, Full Stack Job Prep (+4 more)

### Community 4 - "RAG Loop CLI Script"
Cohesion: 0.33
Nodes (9): answer_question(), build_prompt(), fetch_chunk_by_source(), find_named_entity_match(), load_entity_names(), main(), Names of uniques/gems for the exact-match fallback below. Mods are excluded -, Dense vector search alone can miss a specific named entity even when its chunk (+1 more)

### Community 5 - "RAG Test: Cross-Referencing Cases"
Cohesion: 0.25
Nodes (8): openai, Boots Resistance Affixes, Cross-Referencing (Q4-7), Minion Build Support Gems, Per-Entry Chunking (Step 3 assumption), Ring Mods (spawn_no metadata), Semantic Retrieval (embedding-based), Spell Damage Unique Gloves

### Community 6 - "RAG Test: Direct Lookup & Precision Cases"
Cohesion: 0.29
Nodes (7): Ab Aeterno (unique item), Abyssal Pact (gem), Boneshatter (skill gem), Direct Lookups (Q1-3), Hallucination Check (numeric precision), 'of the Brute' Suffix, Precision/Tier Checks (Q8-9)

### Community 7 - "Go/No-Go Gate Concept"
Cohesion: 0.67
Nodes (3): Go/No-Go Gate, POE2 Advisor — v1 Build Plan, RAG Loop

### Community 8 - "RAG Test: Out-of-Scope Traps"
Cohesion: 0.67
Nodes (3): Headhunter (unique item, trade pricing), Honesty Behavior (out-of-scope handling), Out-of-Scope Traps (Q10-12)

## Knowledge Gaps
- **17 isolated node(s):** `ExiledAI README`, `Decision - RAG Stack for POE2 Advisor`, `RAG Pipeline Fundamentals`, `AI Engineering Skill Gap`, `OpenAI Embeddings API` (+12 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `python-dotenv` connect `Dependencies & Infra Overview` to `RAG Test: Cross-Referencing Cases`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `openai` connect `RAG Test: Cross-Referencing Cases` to `Dependencies & Infra Overview`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `FastAPI backend` connect `Dependencies & Infra Overview` to `Build Plan & Project Decisions`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Step 2: Scrape poe2db (v1 dataset only)` (e.g. with `Step 1: Infra — stand up pgvector` and `beautifulsoup4`) actually correct?**
  _`Step 2: Scrape poe2db (v1 dataset only)` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Mods repeat across category files (e.g. the same affix can spawn on     both Cla`, `Find `marker` then extract the first balanced {...} JSON object that follows,`, `ExiledAI README` to the rest of the system?**
  _24 weakly-connected nodes found - possible documentation gaps or missing edges._