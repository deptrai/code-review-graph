# Epic: Context Engine — code-review-graph Evolution

## Epic Overview

| Field | Value |
|-------|-------|
| Epic ID | CE-EPIC-001 |
| Title | Context Engine Evolution |
| PRD Reference | `docs/specs/PRD-context-engine.md` |
| Architecture | `docs/specs/ARCHITECTURE-context-engine.md` |
| Status | Draft |
| Owner | TBD |
| Start Date | TBD |
| Target Completion | ~21 weeks from start |

## Business Value

Transform code-review-graph from a structural analysis tool into a full Context Engine that delivers ranked, budget-aware, LLM-enriched context to AI coding tools via MCP protocol — achieving parity with Augment Code's context system.

## Epic Decomposition

### Epic 1: Relevance Ranking + Token Budget

| Field | Value |
|-------|-------|
| Epic ID | CE-E1 |
| Duration | 3 weeks |
| Priority | P0 — Foundation |
| Spec | `docs/specs/SPEC-phase1-relevance-budget.md` |
| Depends On | — |
| Blocks | CE-E2, CE-E3, CE-E4, CE-E5, CE-E6 |

#### User Stories

| Story ID | As a... | I want... | So that... | Points |
|----------|---------|-----------|------------|--------|
| CE-E1-S1 | Developer using Claude Code | context results ranked by relevance to my query | I get the most useful code first without scrolling through noise | 5 |
| CE-E1-S2 | MCP tool consumer | dynamic token budget management | responses fit my context window without truncation | 3 |
| CE-E1-S3 | Developer reviewing changes | intent-aware context shaping | review context focuses on what matters for my specific question | 5 |
| CE-E1-S4 | Existing user | backward-compatible behavior with `detail_level="minimal"` | my workflows don't break after upgrading | 2 |

#### Acceptance Criteria

- [ ] Intent classifier categorizes queries into ≥5 intents (review, debug, understand, refactor, test)
- [ ] Relevance scorer produces 0.0–1.0 scores for graph nodes given a query
- [ ] Token budget manager respects configurable limits (default 4096 tokens)
- [ ] Context assembly returns results sorted by relevance score
- [ ] ≥20% token reduction at same recall vs current flat BFS
- [ ] All existing MCP tool signatures unchanged
- [ ] `detail_level="minimal"` bypasses all new scoring logic
- [ ] Migration v11 creates `relevance_cache` table cleanly

---

### Epic 2: LLM Knowledge Layer

| Field | Value |
|-------|-------|
| Epic ID | CE-E2 |
| Duration | 3 weeks |
| Priority | P1 |
| Spec | `docs/specs/SPEC-phase2-llm-knowledge.md` |
| Depends On | CE-E1 |
| Blocks | CE-E5 |

#### User Stories

| Story ID | As a... | I want... | So that... | Points |
|----------|---------|-----------|------------|--------|
| CE-E2-S1 | Developer | LLM-generated summaries of recent commits | I understand what changed without reading every diff | 5 |
| CE-E2-S2 | Team lead | automatically extracted coding conventions | new team members learn patterns from the codebase itself | 8 |
| CE-E2-S3 | Developer | enriched context with semantic descriptions | AI tools give better answers with richer context | 5 |
| CE-E2-S4 | User without LLM API key | graceful fallback to raw source | the tool still works without cloud dependencies | 2 |

#### Acceptance Criteria

- [ ] Async commit summarization pipeline (never blocks MCP response)
- [ ] Convention extraction identifies ≥3 patterns per community
- [ ] Summaries cached in SQLite, invalidated on relevant file changes
- [ ] LLM judge rates enriched context ≥25% better than raw source
- [ ] Fallback to raw source when `CRG_LLM_*` env vars not configured
- [ ] Configurable LLM provider (OpenAI-compatible endpoint)

---

### Epic 3: Real-Time Push

| Field | Value |
|-------|-------|
| Epic ID | CE-E3 |
| Duration | 2 weeks |
| Priority | P1 |
| Spec | `docs/specs/SPEC-phase3-realtime-push.md` |
| Depends On | CE-E1 |
| Blocks | CE-E5 |

#### User Stories

| Story ID | As a... | I want... | So that... | Points |
|----------|---------|-----------|------------|--------|
| CE-E3-S1 | Developer | real-time graph updates when I save files | context is always current without manual rebuild | 5 |
| CE-E3-S2 | IDE integration | SSE push events for graph changes | I can update UI instantly on file changes | 5 |
| CE-E3-S3 | Developer | sub-100ms indexing for single file changes | there's no perceptible lag in my workflow | 3 |

#### Acceptance Criteria

- [ ] FS watcher detects file changes within 50ms
- [ ] Incremental re-parse of single file completes in <100ms
- [ ] SSE endpoint streams structured change events
- [ ] Clients can subscribe to specific file/community changes
- [ ] Debouncing prevents excessive re-parses during rapid edits
- [ ] Graceful shutdown of watcher on process exit

---

### Epic 4: External Source Integration

| Field | Value |
|-------|-------|
| Epic ID | CE-E4 |
| Duration | 4 weeks |
| Priority | P2 |
| Spec | `docs/specs/SPEC-phase4-multi-repo.md` |
| Depends On | CE-E1 |
| Blocks | CE-E5 |

#### User Stories

| Story ID | As a... | I want... | So that... | Points |
|----------|---------|-----------|------------|--------|
| CE-E4-S1 | Developer | Jira/Linear tickets linked to code changes | I understand the business context of modifications | 8 |
| CE-E4-S2 | Developer | GitHub Issues/PRs as context sources | related discussions appear alongside code | 5 |
| CE-E4-S3 | Team | Notion/Confluence docs enriching context | architectural decisions are surfaced during review | 5 |
| CE-E4-S4 | Developer | cross-repo dependency tracing | I see impact across service boundaries | 8 |

#### Acceptance Criteria

- [ ] ≥4 connector implementations (Jira, Linear, GitHub, Notion)
- [ ] Connector interface allows custom implementations
- [ ] External data cached with configurable TTL
- [ ] Rate limiting with exponential backoff
- [ ] Cross-repo flow stitching resolves 3-hop dependencies
- [ ] `httpx` dependency optional (installed via `pip install code-review-graph[external]`)

---

### Epic 5: Predictive Learning + Self-Tuning

| Field | Value |
|-------|-------|
| Epic ID | CE-E5 |
| Duration | 4 weeks |
| Priority | P2 |
| Spec | `docs/specs/SPEC-phase5-predictive-learning.md` |
| Depends On | CE-E2, CE-E3, CE-E4 |
| Blocks | CE-E6 |

#### User Stories

| Story ID | As a... | I want... | So that... | Points |
|----------|---------|-----------|------------|--------|
| CE-E5-S1 | Developer | relevance weights that improve over time | context quality gets better the more I use the tool | 8 |
| CE-E5-S2 | Developer | predictive pre-fetching of likely-needed context | responses are faster because context is pre-cached | 5 |
| CE-E5-S3 | Team | team-level learning from collective usage | the tool adapts to our team's codebase patterns | 8 |

#### Acceptance Criteria

- [ ] Feedback loop: user interactions adjust relevance weights
- [ ] Weight convergence within 50 queries on a new codebase
- [ ] Pre-fetch accuracy ≥60% (predicted context actually used)
- [ ] Per-user and per-team weight profiles
- [ ] No performance degradation from learning overhead
- [ ] Learning data stored locally (privacy-first)

---

### Epic 6: Enterprise Scale

| Field | Value |
|-------|-------|
| Epic ID | CE-E6 |
| Duration | 5 weeks |
| Priority | P3 |
| Spec | TBD |
| Depends On | CE-E5 |
| Blocks | — |

#### User Stories

| Story ID | As a... | I want... | So that... | Points |
|----------|---------|-----------|------------|--------|
| CE-E6-S1 | Enterprise admin | support for 1M+ node repositories | our monorepo works without degradation | 13 |
| CE-E6-S2 | Enterprise admin | permission-aware context filtering | developers only see code they have access to | 8 |
| CE-E6-S3 | Enterprise admin | sharded storage for large graphs | horizontal scaling is possible | 8 |
| CE-E6-S4 | QA | automated eval harness with LLM judge | we can measure quality regression continuously | 5 |

#### Acceptance Criteria

- [ ] Graph operations performant at 1M+ nodes (query <500ms p95)
- [ ] SQLite sharding by community/file-prefix
- [ ] Optional DuckDB backend for analytical queries
- [ ] Permission model integrates with GitHub/GitLab RBAC
- [ ] LLM judge eval scores >80% agreement with human reviewers
- [ ] CI integration for quality regression detection

---

## Dependency Graph

```
CE-E1 (Relevance + Budget)
  ├── CE-E2 (LLM Knowledge)
  ├── CE-E3 (Real-Time Push)
  ├── CE-E4 (External Sources)
  │
  └── CE-E5 (Predictive Learning)  ← depends on E2, E3, E4
        │
        └── CE-E6 (Enterprise Scale) ← depends on E5
```

## Total Story Points

| Epic | Points | Duration |
|------|--------|----------|
| CE-E1 | 15 | 3 weeks |
| CE-E2 | 20 | 3 weeks |
| CE-E3 | 13 | 2 weeks |
| CE-E4 | 26 | 4 weeks |
| CE-E5 | 21 | 4 weeks |
| CE-E6 | 34 | 5 weeks |
| **Total** | **129** | **~21 weeks** |

## Risk Registry

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|-----------|
| LLM latency in hot path | High | Medium | Cache + async enrichment, never block MCP |
| SQLite contention at scale | High | Low | WAL mode + sharding (Phase 6) |
| External API rate limits | Medium | High | Exponential backoff + offline cache |
| Breaking existing users | Critical | Low | `detail_level="minimal"` bypass |
| Scope creep in connectors | Medium | High | Fixed connector interface, community plugins |
| Learning loop instability | Medium | Medium | Weight bounds + rollback mechanism |

## Quality Gates (Phase Transitions)

Each phase must pass before starting the next:

1. **All tests pass** — `uv run pytest tests/ --tb=short -q`
2. **Lint clean** — `uv run ruff check code_review_graph/`
3. **Type safe** — `uv run mypy code_review_graph/ --ignore-missing-imports`
4. **Backward compat** — Existing MCP tools produce identical output for `detail_level="minimal"`
5. **Graph self-builds** — `uv run code-review-graph build --full-rebuild` succeeds
6. **Migration clean** — Fresh DB + upgrade path both work
7. **Eval passes** — Phase-specific eval metrics meet targets (see `EVAL-framework.md`)
