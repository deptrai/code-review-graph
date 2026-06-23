---
baseline_commit: 7d216a02597ee3de5908981f4b9e4c914f276110
---
# Story 1.1: Relevance Ranking

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer using Claude Code,
I want context results ranked by relevance to my query,
so that I get the most useful code first without scrolling through noise.

## Acceptance Criteria

1. Intent classifier categorizes queries into ≥5 intents (SECURITY, PERFORMANCE, DEBUG, REVIEW, REFACTOR, with GENERAL as fallback). [Source: docs/specs/SPEC-phase1-relevance-budget.md#1a. Relevance Scorer]
2. `classify_intent(query)` matches signal phrases from the intent table and returns `Intent.GENERAL` when no signals match. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Intent Classification Signal Phrases]
3. `score_node(...)` produces a relevance score clamped to `[0.0, 1.0]` for a single graph node using the documented scoring formula (graph_distance 0.5, churn 0.2, semantic_similarity 0.2, test_gap_penalty 0.1). [Source: docs/specs/SPEC-phase1-relevance-budget.md#Scoring Formula]
4. Intent boost multiplies a node's score by 1.3 when the node matches the active intent category, before clamping. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Scoring Formula]
5. `score_candidates(...)` returns `(node, score)` pairs sorted by score descending. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1a. Relevance Scorer]
6. Custom `ScoringWeights` can be supplied and override the defaults. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1a. Relevance Scorer]
7. No new third-party dependencies are introduced; existing MCP tool signatures remain unchanged. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Rollout]

## Tasks / Subtasks

- [x] Task 1: Create `code_review_graph/relevance.py` module scaffold (AC: #1, #3, #5)
  - [x] Define `Intent` enum with SECURITY, PERFORMANCE, DEBUG, REVIEW, REFACTOR, GENERAL
  - [x] Define `ScoringWeights` dataclass with documented defaults
  - [x] Add module docstring citing the spec
- [x] Task 2: Implement `classify_intent(query)` (AC: #1, #2)
  - [x] Encode signal-phrase table (case-insensitive substring match)
  - [x] Return first matching intent by priority; fall back to `Intent.GENERAL`
  - [x] Consolidate signal phrases in `hints.py` if that is the existing home for keyword tables; otherwise keep local
- [x] Task 3: Implement `score_node(...)` (AC: #3, #4)
  - [x] Apply scoring formula with weights
  - [x] Apply 1.3 intent boost via `intent_matches(node, intent)` helper
  - [x] Clamp result to [0, 1]
- [x] Task 4: Implement `score_candidates(...)` (AC: #5, #6)
  - [x] Accept optional `query_embedding` and `weights`
  - [x] Compute per-node `semantic_sim` from embedding when available, else 0.0
  - [x] Sort descending and return `(node, score)` tuples
- [x] Task 5: Tests in `tests/test_relevance.py` (AC: #1–#6)
  - [x] test_classify_intent_security
  - [x] test_classify_intent_performance
  - [x] test_classify_intent_debug
  - [x] test_classify_intent_general_fallback
  - [x] test_score_node_basic
  - [x] test_score_node_intent_boost
  - [x] test_score_candidates_ordering
  - [x] test_custom_weights
- [x] Task 6: Verify (AC: #7)
  - [x] Run full test suite; confirm no MCP tool signatures changed
  - [x] Confirm no new dependencies added to project config

## Dev Notes

- This story delivers the **scorer only**. Token budget (`budget.py`), query-aware context shaping in `tools/review.py`/`tools/context.py`, and migration v11 (`relevance_cache`) are separate stories (1-2, 1-3) and must NOT be implemented here beyond the scorer's public API. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Components]
- `score_candidates` consumes `graph_distance` (from existing BFS in `graph.py`), `churn_score`, `semantic_sim` (from `embeddings.py` similarity), and `has_tests`. For this story, the scorer takes these as inputs — wiring them from real graph data happens in story 1-3. Provide sensible defaults so unit tests can exercise the formula directly. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Integration Points]
- `intent_matches(node, intent)` uses the Intent → Node Type boosting table (e.g. SECURITY → functions containing auth/token/session/permission). Keep this a pure function over node metadata. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Intent → Node Type Boosting]
- Testing standard: pytest, tests live in `tests/`, one test file per module. Follow existing test patterns in `tests/test_search.py`.

### Project Structure Notes

- New module: `code_review_graph/relevance.py` (greenfield, no conflict).
- New test: `tests/test_relevance.py`.
- Signal-phrase tables may belong in `hints.py` (spec lists `hints.py` as an integration point: "expanded with intent signal phrases"). Decide during Task 2; if added to `hints.py`, import into `relevance.py` to keep one source of truth. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Integration Points]
- ⚠️ Migration version conflict (out of scope for this story, flagged for story 1-3): the epic/spec call for "Migration v11: relevance_cache", but `code_review_graph/migrations.py` already uses `_migrate_v11` for the `nodes.body` column. The relevance_cache migration must therefore use the next free version (v12+), not v11. Resolve in story 1-3.

### References

- [Source: docs/specs/SPEC-phase1-relevance-budget.md#1a. Relevance Scorer]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#Scoring Formula]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#Intent Classification Signal Phrases]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#Intent → Node Type Boosting]
- [Source: docs/specs/EPIC-context-engine.md#Epic 1: Relevance Ranking + Token Budget] (CE-E1-S1)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5 (via Kiro/Claude Code)

### Debug Log References

None — implementation completed without failures.

### Completion Notes List

- Implemented `code_review_graph/relevance.py` as a standalone scorer module (no new dependencies; stdlib `math` only for cosine similarity).
- Signal phrases kept local to `relevance.py` rather than `hints.py` — `hints.py` operates on tool-call history (session intent), not query text. The two concerns are orthogonal.
- `score_node` accepts an optional `node: dict` for intent boosting; when omitted, a minimal `{"qualified_name": node_qn}` dict is synthesised so name-based SECURITY boosting still works without a full node dict.
- `_cosine_sim` uses pure stdlib (no numpy) to satisfy the no-new-dependencies constraint.
- All 17 tests pass (8 named from spec + 9 additional edge-case tests). Zero regressions in the 258 tests that can run in this environment (23 test modules fail to collect due to pre-existing `tree_sitter_language_pack` missing from dev machine — confirmed pre-existing by checking baseline).
- Ruff I001 (import ordering) auto-fixed; lint clean.
- No MCP tool signatures were modified.

### Implementation Plan

1. Wrote `tests/test_relevance.py` first (RED — import error confirmed).
2. Wrote `code_review_graph/relevance.py` (GREEN — 17/17 pass).
3. Auto-fixed ruff I001 lint warning (import block ordering).
4. Ran full suite — zero regressions introduced.

### File List

- `code_review_graph/relevance.py` (new)
- `tests/test_relevance.py` (new)

### Change Log

- 2026-06-12: Implemented Story 1.1 — relevance scorer (`Intent`, `ScoringWeights`, `classify_intent`, `intent_matches`, `score_node`, `score_candidates`). 17 tests added, all passing. No new dependencies.
