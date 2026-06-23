# Deferred Work

Tracking of real-but-not-now items surfaced during reviews.

## Deferred from: code review of story-1-2-token-budget (2026-06-12)

- Negative `CRG_CONTEXT_BUDGET` silently drops all nodes [code_review_graph/budget.py:80-86]. A negative env value is parseable, so `get_budget()` returns it as-is and `budget_fill` then drops every candidate with no signal to the caller. AC #1 only requires fallback on unset/unparseable values, so this is out of scope for story 1.2 — but it is a latent footgun worth guarding (clamp to `>= 0`, or fall back to default on non-positive) in a future hardening pass.
