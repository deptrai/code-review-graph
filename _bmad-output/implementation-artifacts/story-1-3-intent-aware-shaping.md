---
baseline_commit: a73e0b44b6223ef46aa63487a2ba81b1ef69a378
---
# Story 1.3: Intent-Aware Context Shaping

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer reviewing changes,
I want intent-aware context shaping,
so that review context focuses on what matters for my specific question.

## Acceptance Criteria

1. In `get_review_context` (`tools/review.py`), the `standard` detail_level path scores the impacted nodes with `score_candidates(...)` using `Intent.REVIEW` and then applies `budget_fill(...)`, so the returned graph nodes are ordered by descending relevance and trimmed to the token budget. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1c. Query-Aware Context Shaping]
2. The standard path attaches a `_budget_metadata` dict (serialized from `BudgetMetadata` via `dataclasses.asdict`) to the response for observability. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Rollout]
3. `detail_level="minimal"` continues to bypass all scoring/budget logic and returns the same structure as before this story (backward compatibility). [Source: docs/specs/EPIC-context-engine.md#Acceptance Criteria]
4. Each impacted node is mapped to scorer inputs: `graph_distance` from the impact-radius BFS depth, `churn_score` from the `git_lineage` table, `has_tests` from `TESTED_BY` edges, and `semantic_sim = 0.0` (the review path has no free-text query embedding). Missing data falls back to safe defaults (large distance, churn `0.0`, `has_tests=False`). [Source: docs/specs/SPEC-phase1-relevance-budget.md#Integration Points]
5. Intent → node-type boosting is applied through the existing `intent_matches(node, intent)` helper from story 1-1; the review path uses `Intent.REVIEW`. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Intent → Node Type Boosting]
6. Migration **v12** creates `relevance_cache` (PK `(query_hash, node_qn)`; columns `score REAL`, `intent TEXT`, `computed_at REAL`) plus `idx_relevance_cache_time` on `computed_at`; `_migrate_v11` (the `nodes.body` column) is left untouched and `LATEST_VERSION` becomes 12. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1d. Migration v11: Relevance Cache]
7. A cache helper reads cached scores by `query_hash` when fresh (`computed_at` within 300s), writes freshly computed scores, and deletes stale rows (`computed_at < now - 300`) on each query (best-effort TTL cleanup). [Source: docs/specs/SPEC-phase1-relevance-budget.md#1d. Migration v11: Relevance Cache]
8. The relevance cache is cleared on incremental graph update via a hook in `incremental.py`. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Integration Points]
9. `get_minimal_context` (`tools/context.py`) computes `classify_intent(task)` and exposes the result as an additive `intent` response field, without changing any existing field or its signature. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1c. Query-Aware Context Shaping]
10. No new third-party dependencies are introduced and every existing MCP tool signature is unchanged (no new params on `get_review_context` or `get_minimal_context`). [Source: docs/specs/SPEC-phase1-relevance-budget.md#Rollout]

## Tasks / Subtasks

- [ ] Task 1: Migration v12 — `relevance_cache` (AC: #6)
  - [ ] Add `_migrate_v12(conn)` in `code_review_graph/migrations.py` creating the `relevance_cache` table + `idx_relevance_cache_time` (use `CREATE TABLE/INDEX IF NOT EXISTS`, idempotent)
  - [ ] Register `12: _migrate_v12` in the `MIGRATIONS` dict; confirm `LATEST_VERSION` resolves to 12
  - [ ] Add `relevance_cache` to `_KNOWN_TABLES` so `_table_exists` / `_has_column` accept it
  - [ ] Do NOT modify `_migrate_v11` (owns `nodes.body`)
- [ ] Task 2: Relevance cache helper module (AC: #7, #8)
  - [ ] Create `code_review_graph/relevance_cache.py` with `compute_query_hash(...)`, `read_cached_scores(conn, query_hash)`, `write_scores(conn, query_hash, intent, scores)`, `cleanup_stale(conn, ttl=300)`, and `clear_relevance_cache(conn)`
  - [ ] `query_hash` is a deterministic hash of `(intent, sorted(changed_files), base)` for the review path — document the exact composition in the module docstring
  - [ ] Call `cleanup_stale` on each query (best-effort; swallow `sqlite3.OperationalError` if table absent)
  - [ ] Wire `clear_relevance_cache(conn)` into the incremental-update path in `incremental.py`
- [ ] Task 3: Scored assembly in `get_review_context` (AC: #1, #2, #4, #5)
  - [ ] Add a private helper `_assemble_scored_context(store, impact, changed_files, base)` that builds candidate dicts, derives `graph_distance` / `churn_score` / `has_tests` (semantic_sim=0.0), calls `classify_intent` is not needed (intent fixed to `Intent.REVIEW`), then `score_candidates(..., intent=Intent.REVIEW)` and `budget_fill(...)`
  - [ ] Replace the unordered `impacted_nodes` list in the standard-path `context["graph"]` with the budget-filled, relevance-ordered node dicts
  - [ ] Attach `_budget_metadata = asdict(meta)` to the standard-path result
  - [ ] Consult the relevance cache before scoring and persist results after (Task 2 helper)
- [ ] Task 4: Map BFS depth → `graph_distance` (AC: #4)
  - [ ] Source per-node depth from the impact-radius traversal (the SQL recursive CTE already tracks `MIN(depth)`); changed (seed) nodes get distance 0
  - [ ] If depth is unavailable for a node, default to a large distance so its distance term ≈ 0
- [ ] Task 5: Wire `classify_intent` into `get_minimal_context` (AC: #9)
  - [ ] Compute `intent = classify_intent(task)` and add `intent=intent.value` to the response (additive; keep all existing fields + the keyword-based `next_tool_suggestions` logic unchanged)
- [ ] Task 6: Tests in `tests/test_integration_relevance.py` (AC: #1–#9)
  - [ ] test_review_context_with_scoring (standard path returns relevance-ordered nodes + `_budget_metadata`)
  - [ ] test_minimal_detail_level_bypasses_scoring (minimal output unchanged, no `_budget_metadata`)
  - [ ] test_relevance_cache_hit (second identical call reads cache)
  - [ ] test_relevance_cache_invalidation (`clear_relevance_cache` empties the table)
  - [ ] test_migration_v12_creates_relevance_cache (fresh DB + upgrade path)
  - [ ] test_minimal_context_exposes_intent
- [ ] Task 7: Verify (AC: #3, #10)
  - [ ] Run full suite: `uv run pytest tests/ --tb=short -q`
  - [ ] Lint: `uv run ruff check code_review_graph/`
  - [ ] Types: `uv run mypy code_review_graph/ --ignore-missing-imports`
  - [ ] Confirm no MCP tool signatures changed and `pyproject.toml` has no new deps
  - [ ] Confirm fresh-DB build still works: `uv run code-review-graph build --full-rebuild`

## Dev Notes

- **Migration version is v12, NOT v11.** Both story 1-1 and story 1-2 flagged this: the spec heading literally says "Migration v11: Relevance Cache", but `_migrate_v11` already exists in `code_review_graph/migrations.py` for the `nodes.body` column (`LATEST_VERSION = 11`). The cache migration must take the next free slot, **v12**. Do not renumber or alter the existing v11. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1d. Migration v11: Relevance Cache]
- **Signature constraint shapes the review path.** Epic AC requires "All existing MCP tool signatures unchanged", and `get_review_context` has no `query` parameter. Therefore the review path cannot accept free-text and must use a **fixed `Intent.REVIEW`** with **`semantic_sim = 0.0`** (no query embedding). The spec's §1c pseudocode shows a `query` argument; that generality is not available here and is intentionally narrowed for this tool. Flag for PO only if a future story needs a query-bearing review entry point. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1c. Query-Aware Context Shaping; docs/specs/EPIC-context-engine.md#Acceptance Criteria]
- **This story is the integration that 1-1/1-2 deferred.** Story 1-1 left scorer inputs (`graph_distance`, `churn_score`, `semantic_sim`, `has_tests`) as caller-supplied; story 1-2 kept `budget_fill` a pure function over scored tuples and explicitly said wiring into `tools/review.py`/`tools/context.py` is story 1-3. This story wires real graph data into those inputs. Do not change the public APIs of `relevance.py` / `budget.py`; consume them as-is. [Source: _bmad-output/implementation-artifacts/story-1-1-relevance-ranking.md; story-1-2-token-budget.md]
- **Consumed public APIs (already merged, do not modify):**
  - `relevance.py`: `Intent`, `ScoringWeights`, `classify_intent(query)`, `intent_matches(node, intent)`, `score_node(...)`, `score_candidates(candidates, query, intent, query_embedding=None, weights=None) -> list[tuple[dict, float]]`
  - `budget.py`: `DEFAULT_BUDGET=8000`, `BudgetMetadata`, `get_budget()`, `estimate_tokens(text)`, `budget_fill(scored_candidates, budget=None) -> (included_nodes, dropped_nodes, BudgetMetadata)`
- **`graph_distance` source.** `Store.get_impact_radius` has a SQL variant (`get_impact_radius_sql`) whose recursive CTE already computes `MIN(depth)` per node; seeds are depth 0. Prefer threading that depth through rather than re-running BFS. The NetworkX variant returns nodes without depth — if that path is used, fall back to a large default distance (distance term ≈ 0) instead of guessing. [Source: code_review_graph/graph.py#get_impact_radius_sql]
- **`churn_score` and `has_tests`.** Churn comes from the `git_lineage` table (migration v10): map a node's `file_path` → `churn_90d` and normalize to `[0,1]` (e.g. divide by a cap). `has_tests` is `True` when a node's `qualified_name` is the source of a `TESTED_BY` edge (the standard-path `impact["edges"]` already carries these). When `git_lineage` has no row, churn defaults to `0.0`. [Source: code_review_graph/migrations.py#_migrate_v10; tools/review.py#_generate_review_guidance]
- **`_budget_metadata` always attached on the standard path** for observability; the minimal path must NOT include it (keeps the minimal contract byte-stable). [Source: docs/specs/SPEC-phase1-relevance-budget.md#Rollout]
- **Cache invalidation** belongs in `incremental.py` on the update path (the spec lists `incremental.py → invalidates relevance_cache on update`). Keep the hook a single call to `clear_relevance_cache(conn)`; do not couple cache logic into incremental parsing internals. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Integration Points]
- **`get_minimal_context` change is additive only.** Add an `intent` field from `classify_intent(task)`; leave the existing keyword-driven `next_tool_suggestions` blocks and all other fields untouched so existing tests stay green. Do not refactor the suggestion logic in this story. [Source: code_review_graph/tools/context.py#get_minimal_context]
- **Default budget remains 8000** (spec §1b code block). The epic text mentions "default 4096 tokens"; the spec's 8000 governs, consistent with story 1-2. Do not introduce a second default. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
- **Testing standard:** pytest, `asyncio_mode = "auto"`, tests in `tests/`, one file per concern. New integration file `tests/test_integration_relevance.py` per the spec's Testing Strategy. CI requires ≥65% coverage. For cache tests, build the table via `run_migrations` on an in-memory or temp SQLite connection; isolate `CRG_CONTEXT_BUDGET` with `monkeypatch.setenv` if exercised. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Testing Strategy; _bmad-output/project-context.md#Tooling]

### Project Structure Notes

- New module: `code_review_graph/relevance_cache.py` (greenfield).
- New test: `tests/test_integration_relevance.py` (greenfield per spec).
- Modified: `code_review_graph/migrations.py` (add v12 + registry + `_KNOWN_TABLES`), `code_review_graph/tools/review.py` (scored assembly on standard path), `code_review_graph/tools/context.py` (additive `intent` field), `code_review_graph/incremental.py` (invalidation hook).
- Unchanged: `relevance.py`, `budget.py`, `pyproject.toml`, all MCP tool signatures.

### References

- [Source: docs/specs/SPEC-phase1-relevance-budget.md#1c. Query-Aware Context Shaping]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#1d. Migration v11: Relevance Cache]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#Intent → Node Type Boosting]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#Integration Points]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#Testing Strategy]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#Rollout]
- [Source: docs/specs/EPIC-context-engine.md#Epic 1: Relevance Ranking + Token Budget] (CE-E1-S3)
- [Source: _bmad-output/implementation-artifacts/story-1-1-relevance-ranking.md]
- [Source: _bmad-output/implementation-artifacts/story-1-2-token-budget.md]

## Dev Agent Record

### Agent Model Used

_TBD by dev agent._

### Debug Log References

_None yet._

### Completion Notes List

_None yet._

### Implementation Plan

_To be filled by dev agent._

### File List

_To be filled by dev agent._

### Change Log

- 2026-06-12: Story 1.3 drafted (ready-for-dev) — Intent-Aware Context Shaping scope defined from SPEC-phase1-relevance-budget.md §1c/§1d. Integrates the story 1-1 scorer + story 1-2 budget manager into `get_review_context`, adds migration v12 `relevance_cache` + cache helper + incremental invalidation, and wires `classify_intent` into `get_minimal_context`. Migration confirmed as v12 (v11 owns `nodes.body`).
