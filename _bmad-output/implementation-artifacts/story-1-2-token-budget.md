---
baseline_commit: a73e0b44b6223ef46aa63487a2ba81b1ef69a378
---
# Story 1.2: Dynamic Token Budget

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an MCP tool consumer,
I want dynamic token budget management,
so that responses fit my context window without truncation.

## Acceptance Criteria

1. `get_budget()` reads the budget from the `CRG_CONTEXT_BUDGET` env var, falling back to `DEFAULT_BUDGET` (8000) when unset or unparseable. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
2. `estimate_tokens(text)` returns a token estimate using the documented heuristic `len(text) // 4`. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
3. `budget_fill(scored_candidates, budget=None)` greedily iterates candidates in the given (descending-score) order and includes each node whose cost keeps the running total within budget; a node that would exceed the budget is dropped, but the scan continues so a later cheaper candidate can still be included (best-effort fill). [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
4. `budget_fill` returns a 3-tuple `(included_nodes, dropped_nodes, BudgetMetadata)` where `included_nodes` and `dropped_nodes` are lists of node dicts (not score tuples). [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
5. `BudgetMetadata` accurately reports `budget_used`, `budget_total`, `nodes_included`, and `nodes_dropped` for the fill result. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
6. When `budget` is `None`, `budget_fill` uses `get_budget()`; when supplied explicitly it overrides the env/default. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
7. Empty candidate input yields empty included/dropped lists and `budget_used == 0` without error. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Testing Strategy]
8. No new third-party dependencies are introduced; existing MCP tool signatures remain unchanged. [Source: docs/specs/SPEC-phase1-relevance-budget.md#Rollout]

## Tasks / Subtasks

- [x] Task 1: Create `code_review_graph/budget.py` module scaffold (AC: #1, #2, #4, #5)
  - [x] Add module docstring citing the spec
  - [x] Define `DEFAULT_BUDGET = 8000`
  - [x] Define `BudgetMetadata` dataclass (`budget_used`, `budget_total`, `nodes_included`, `nodes_dropped`)
- [x] Task 2: Implement `get_budget()` (AC: #1, #6)
  - [x] Read `CRG_CONTEXT_BUDGET` from env
  - [x] Parse to int; fall back to `DEFAULT_BUDGET` on missing or invalid value (guard `ValueError`)
- [x] Task 3: Implement `estimate_tokens(text)` (AC: #2)
  - [x] Return `len(text) // 4`
  - [x] Decide token-source field for a node dict (e.g. `body` / `source` / `signature`) and document the fallback when absent
- [x] Task 4: Implement `budget_fill(...)` (AC: #3, #4, #5, #6, #7)
  - [x] Resolve effective budget via `budget if budget is not None else get_budget()`
  - [x] Iterate scored candidates in given order, estimate per-node cost; include each node whose cost keeps the running total within budget, drop any node that would exceed it but continue scanning (best-effort fill)
  - [x] Append dropped (over-budget) candidates to `dropped_nodes`
  - [x] Build and return `(included_nodes, dropped_nodes, BudgetMetadata)`
- [x] Task 5: Tests in `tests/test_budget.py` (AC: #1–#7)
  - [x] test_budget_fill_within_budget
  - [x] test_budget_fill_exceeds_budget
  - [x] test_budget_fill_empty_candidates
  - [x] test_estimate_tokens
  - [x] test_env_var_override
  - [x] test_metadata_accuracy
- [x] Task 6: Verify (AC: #8)
  - [x] Run full test suite; confirm no MCP tool signatures changed
  - [x] Confirm no new dependencies added to project config
  - [x] Lint clean (`ruff check code_review_graph/`)

### Review Findings

- [x] [Review][Decision] `budget_fill` skip-and-continue vs stop-on-overflow semantics — RESOLVED: kept continue-fill (best-effort, better budget utilization) and aligned the contract to match. Updated AC #3 wording and the `budget_fill` docstring to state that a node exceeding the remaining budget is dropped but the scan continues so a later cheaper candidate can still be included. Added regression test `test_budget_fill_continues_after_drop` (small node after a dropped expensive node is included). All 16 budget tests pass; ruff clean.
- [x] [Review][Patch] `estimate_tokens` type hint understates accepted input [code_review_graph/budget.py:89] — RESOLVED: widened the signature to `text: str | None` so it matches the body (`if not text: return 0`) and the `test_estimate_tokens_empty` contract that passes `None`. Tests pass; ruff clean.
- [x] [Review][Defer] Negative `CRG_CONTEXT_BUDGET` silently drops all nodes [code_review_graph/budget.py:80-86] — deferred, out of AC scope. A negative value is parseable, so `get_budget()` returns it and `budget_fill` drops every candidate with no signal. AC #1 only requires fallback on unset/unparseable, so not actionable now; noted as a latent footgun.

## Dev Notes

- This story delivers the **budget manager only** (`budget.py` + tests). It must NOT wire budget filling into `tools/review.py` / `tools/context.py` — that query-aware context shaping is story 1-3. Keep `budget_fill` a pure function over scored-candidate tuples. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1c. Query-Aware Context Shaping]
- `budget_fill` consumes the `list[tuple[dict, float]]` produced by `score_candidates` from story 1-1 (already merged). It only needs the node dict from each tuple to estimate cost; the score is used purely as ordering (already sorted desc by the caller). Do not re-sort inside `budget_fill` — respect the given order. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
- Token cost per node should be derived from whatever textual payload the node will contribute to the response. Use `estimate_tokens` over the node's source/body text; when a node dict lacks that field, fall back to estimating over its `qualified_name` so cost is never zero-by-omission. Document the chosen field in the module docstring. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
- DEFAULT_BUDGET is **8000** per the spec code block (note: the EPIC acceptance criteria mentions "default 4096 tokens" — the spec's 8000 governs this implementation; flagged for PO if the discrepancy matters). [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
- Migration v11 / `relevance_cache` is **out of scope** here and belongs to story 1-3. `_migrate_v11` is already taken by the `nodes.body` column, so the cache migration must use v12+. Do not add any migration in this story. [Source: docs/specs/SPEC-phase1-relevance-budget.md#1d. Migration v11: Relevance Cache]
- Testing standard: pytest, tests live in `tests/`, one test file per module. Follow existing patterns in `tests/test_relevance.py`. For `test_env_var_override`, set/restore `CRG_CONTEXT_BUDGET` via `monkeypatch.setenv` so the test is isolated.

### Project Structure Notes

- New module: `code_review_graph/budget.py` (greenfield, no conflict — confirmed absent).
- New test: `tests/test_budget.py` (confirmed absent).
- No changes to `tools/`, `migrations.py`, or `pyproject.toml`.

### References

- [Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#Testing Strategy]
- [Source: docs/specs/SPEC-phase1-relevance-budget.md#Rollout]
- [Source: docs/specs/EPIC-context-engine.md#Epic 1: Relevance Ranking + Token Budget] (CE-E1-S2)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (Kiro)

### Debug Log References

_None._

### Completion Notes List

- Implemented `code_review_graph/budget.py` with `DEFAULT_BUDGET = 8000`, `BudgetMetadata` dataclass, `get_budget()`, `estimate_tokens()`, and `budget_fill()`.
- `get_budget()` reads `CRG_CONTEXT_BUDGET` and falls back to `DEFAULT_BUDGET` on missing/empty/unparseable values (guards `ValueError`).
- `estimate_tokens()` uses the `len // 4` heuristic and treats `None`/empty as 0 tokens.
- Token cost per node draws from `body`, falling back to `source`, then `signature`, then `qualified_name` when earlier fields are absent.
- `budget_fill()` preserves the caller-supplied order (no re-sort), greedily includes each node whose cost keeps the running total within the ceiling, drops any node that would exceed it but continues scanning so later cheaper candidates can still fit (best-effort fill), and returns `(included_nodes, dropped_nodes, BudgetMetadata)` as node dicts (not tuples).
- 15 unit tests added in `tests/test_budget.py`; all pass.
- Full suite green: 1423 passed, 2 xpassed. No MCP tool signatures changed; no new dependencies (`pyproject.toml` unchanged). Ruff clean after auto-fixing import order + unused import.

### Implementation Plan

Followed the task breakdown above: scaffold → `get_budget()` → `estimate_tokens()` → `budget_fill()` → tests → verify.

### File List

- `code_review_graph/budget.py` (new)
- `tests/test_budget.py` (new)

### Change Log

- 2026-06-12: Story 1.2 drafted (ready-for-dev) — Dynamic Token Budget manager scope defined from SPEC-phase1-relevance-budget.md §1b.
- 2026-06-12: Story 1.2 implemented (review) — added `budget.py` + `test_budget.py`; full suite green (1423 passed, 2 xpassed), ruff clean, no new deps.
