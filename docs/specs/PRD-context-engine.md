# PRD: Context Engine — code-review-graph Evolution

## Vision

Transform code-review-graph từ structural analysis tool thành **full Context Engine** — đạt parity với Augment Code's context system. Cung cấp ranked, budget-aware, LLM-enriched context cho AI coding tools qua MCP protocol.

## Problem Statement

code-review-graph hiện đạt ~30-40% capability so với Augment Code's Context Engine:
- ✅ Structural graph (nodes, edges, BFS)
- ✅ Execution flows, communities, churn
- ✅ Embeddings (local + cloud)
- ✅ Watch mode, incremental updates
- ❌ **Relevance ranking** — flat BFS dumps, no scoring
- ❌ **Token budgeting** — no dynamic budget management
- ❌ **LLM knowledge** — no commit summaries, no convention learning
- ❌ **External sources** — no Jira/Linear/GitHub Issues integration
- ❌ **Cross-service flows** — single-repo only
- ❌ **Enterprise scale** — degrades at >500k nodes

## Target Users

1. **Individual developers** using Claude Code / Cursor / Windsurf
2. **Teams** needing cross-repo context in code reviews
3. **Enterprise** with large monorepos and external tool integrations

## Success Criteria (End State)

| Metric | Current | Target |
|--------|---------|--------|
| Context token efficiency | Baseline | ≥20% reduction at same recall |
| Impact accuracy F1 | Baseline | +10% |
| Cross-service trace | 0 hops | 3 hops |
| Max repo size | ~100k nodes | 1M+ nodes |
| External source integration | 0 | 4 connectors |
| LLM judge improvement | 0% | ≥25% vs raw source |

## Phases

| # | Phase | Duration | Key Deliverable |
|---|-------|----------|-----------------|
| 1 | Relevance Ranking + Token Budget | 3 weeks | Scored, budget-aware context assembly |
| 2 | LLM Knowledge Layer | 3 weeks | Commit summaries + convention extraction |
| 3 | Real-Time Push | 2 weeks | SSE events, sub-100ms indexing |
| 4 | External Source Integration | 4 weeks | Jira/Linear/GitHub/Notion connectors |
| 5 | Cross-Service Flow Tracing | 4 weeks | Multi-repo flow stitching + compression |
| 6 | Enterprise Scale | 5 weeks | Sharding, permissions, LLM judge eval |

## Constraints

- **Backward compatible**: All existing MCP tool signatures unchanged
- **Optional features**: New capabilities gated behind env vars
- **Local-first**: No mandatory cloud dependencies
- **Graceful degradation**: LLM features fallback when unconfigured
- **Python 3.10+**: Maintain current compatibility

## Non-Goals

- Replacing IDE-native LSP features (go-to-definition, etc.)
- Building a full CI/CD pipeline
- Real-time collaborative editing
- GUI/web dashboard (VS Code extension stays separate)

## Dependencies

- `httpx>=0.27,<1` (Phase 4, optional extra)
- `duckdb>=0.10,<1` (Phase 6, optional for 1M+ scale)
- Existing: Tree-sitter, SQLite, sentence-transformers

## Risks

| Risk | Mitigation |
|------|-----------|
| LLM latency in hot path | Cache + async enrichment, never block MCP response |
| SQLite contention at scale | WAL mode + sharding (Phase 6) |
| External API rate limits | Exponential backoff + offline cache |
| Breaking existing users | detail_level="minimal" bypasses all new logic |
