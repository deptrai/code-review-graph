# Architecture: Context Engine

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Clients                              │
│  (Claude Code, Cursor, Windsurf, Kiro, Copilot, etc.)       │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol (stdio/SSE)
┌─────────────────────▼───────────────────────────────────────┐
│                   FastMCP Server (main.py)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │  Tools   │ │ Prompts  │ │  SSE     │ │ Permissions  │   │
│  │  (30+)   │ │  (5)     │ │ Events   │ │ Filter       │   │
│  └────┬─────┘ └──────────┘ └──────────┘ └──────────────┘   │
└───────┼─────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────┐
│                  Context Assembly Pipeline                    │
│                                                              │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ Intent   │→ │  Relevance   │→ │  Budget Manager      │   │
│  │Classifier│  │  Scorer      │  │  (greedy fill)       │   │
│  └──────────┘  └──────────────┘  └─────────────────────┘   │
│       │              │                      │                │
│       │         scores 0-1            token budget           │
│       │              │                      │                │
│  ┌────▼─────────────▼──────────────────────▼────────────┐   │
│  │              Context Shaper                           │   │
│  │  - Intent-boosted node types                         │   │
│  │  - LLM-compressed overflow                           │   │
│  │  - External source injection                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────┐
│                    Data Layer                                 │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐   │
│  │ Graph DB   │  │ Embeddings │  │ LLM Knowledge       │   │
│  │ (SQLite)   │  │ (vectors)  │  │ (summaries/convn)   │   │
│  ├────────────┤  ├────────────┤  ├─────────────────────┤   │
│  │ nodes      │  │ local      │  │ commit_summaries    │   │
│  │ edges      │  │ openai     │  │ conventions         │   │
│  │ flows      │  │ google     │  │ external_nodes      │   │
│  │ communities│  │ minimax    │  │                     │   │
│  │ churn      │  │            │  │                     │   │
│  └────────────┘  └────────────┘  └─────────────────────┘   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Incremental Update Pipeline                  │ │
│  │  FS watcher → debounce → parse → graph → postprocess   │ │
│  │  (fast: 50ms)           (full: communities/flows/FTS)   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            External Connectors                          │ │
│  │  GitHub Issues │ Jira │ Linear │ Notion                │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Cross-Service Flow Engine                     │ │
│  │  exit points (HTTP calls) → entry points (services)     │ │
│  │  stitched via CALLS_SERVICE synthetic edges             │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Module Map (New + Modified)

### Phase 1 — Relevance + Budget
| Module | Status | Description |
|--------|--------|-------------|
| `code_review_graph/relevance.py` | NEW | Relevance scorer (graph_distance, churn, semantic, test_gap) |
| `code_review_graph/budget.py` | NEW | Dynamic token budget manager |
| `code_review_graph/tools/review.py` | MOD | Integrate scoring + budget into context assembly |
| `code_review_graph/tools/context.py` | MOD | Query-aware context shaping |
| `code_review_graph/hints.py` | MOD | Extended intent classifier |
| `code_review_graph/migrations.py` | MOD | v11: relevance_cache table |

### Phase 2 — LLM Knowledge
| Module | Status | Description |
|--------|--------|-------------|
| `code_review_graph/llm.py` | NEW | LLM provider abstraction (ABC) |
| `code_review_graph/summarizer.py` | NEW | Commit window summarizer |
| `code_review_graph/conventions.py` | NEW | Convention extractor + store |
| `code_review_graph/wiki.py` | MOD | LLM-enhanced community summaries |
| `code_review_graph/migrations.py` | MOD | v12: commit_summaries + conventions tables |

### Phase 3 — Real-Time Push
| Module | Status | Description |
|--------|--------|-------------|
| `code_review_graph/push.py` | NEW | Event bus (asyncio.Queue per subscriber) |
| `code_review_graph/main.py` | MOD | SSE endpoint /graph-events |
| `code_review_graph/incremental.py` | MOD | Split fast/full update pipeline |

### Phase 4 — External Sources
| Module | Status | Description |
|--------|--------|-------------|
| `code_review_graph/connectors/base.py` | NEW | Connector ABC + ExternalNode |
| `code_review_graph/connectors/github_issues.py` | NEW | GitHub Issues connector |
| `code_review_graph/connectors/jira.py` | NEW | Jira connector |
| `code_review_graph/connectors/linear.py` | NEW | Linear connector |
| `code_review_graph/connectors/notion.py` | NEW | Notion connector |
| `code_review_graph/connectors/indexer.py` | NEW | External node indexer |
| `code_review_graph/migrations.py` | MOD | v13: external_id, source_url |

### Phase 5 — Cross-Service
| Module | Status | Description |
|--------|--------|-------------|
| `code_review_graph/cross_service_flows.py` | NEW | Cross-service flow engine |
| `code_review_graph/tools/cross_service_tools.py` | NEW | trace_cross_service_flow tool |
| `code_review_graph/compression.py` | NEW | LLM context compressor |
| `code_review_graph/migrations.py` | MOD | v14: cross_service flag |

### Phase 6 — Enterprise Scale
| Module | Status | Description |
|--------|--------|-------------|
| `code_review_graph/scale/sharding.py` | NEW | Sharded graph store |
| `code_review_graph/permissions.py` | NEW | Permission-aware retrieval |
| `eval/benchmarks/llm_judge.py` | NEW | LLM judge benchmark |
| `eval/benchmarks/context_quality.py` | NEW | Automated context quality benchmark |

## Data Flow

### Context Assembly (Hot Path)

```
query → classify_intent(query)
     → BFS/traverse graph (existing)
     → score_nodes(candidates, intent, query_embedding)
     → sort by relevance desc
     → budget_fill(sorted_nodes, token_budget)
     → inject_external_docs(top-3 by recency)
     → compress_overflow(dropped_nodes)  [if LLM available]
     → return shaped context + metadata
```

### Incremental Update (Background)

```
fs_event → debounce(50ms single-file, 200ms batch)
        → parse_changed_files()
        → update_nodes_edges()       ← FAST PATH (emit SSE event here)
        → [timer/threshold]
        → recompute_communities()
        → recompute_flows()
        → rebuild_fts()              ← FULL POSTPROCESS
```

## Key Design Decisions

1. **Greedy fill over knapsack** — O(n log n) sort + linear scan beats knapsack optimality at our scale; simpler to debug
2. **Token estimation via `len//4`** — Good enough heuristic, avoids tiktoken dependency
3. **Relevance cache with 5-min TTL** — Prevents re-scoring same query within editing session
4. **LLM calls never in hot path** — All LLM enrichment is offline/async; MCP tools always respond fast
5. **Cross-service flows on demand** — Never persisted, computed at query time to avoid stale stitching
6. **Sharding by path prefix** — Mirrors filesystem locality, good cache behavior

## Security Model

- All new env vars follow existing pattern (`CRG_*` prefix)
- External connector auth via env vars only
- Permission filter applied BEFORE returning any results
- No new `eval()`/`exec()`/`shell=True` patterns
- External node content sanitized via `_sanitize_name()`
