"""Tests for the dynamic token budget manager.

Covers: budget resolution from env var, token estimation heuristic, greedy
budget fill (within/exceeds/empty), metadata accuracy, and explicit-budget
override.

Source: docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager
"""

from code_review_graph.budget import (
    DEFAULT_BUDGET,
    BudgetMetadata,
    budget_fill,
    estimate_tokens,
    get_budget,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(qn: str, body: str = "", score: float = 0.0):
    """Build a (node_dict, score) candidate tuple."""
    node = {"qualified_name": qn}
    if body:
        node["body"] = body
    return (node, score)


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_estimate_tokens(self):
        """len // 4 heuristic."""
        assert estimate_tokens("a" * 400) == 100
        assert estimate_tokens("abcd") == 1
        assert estimate_tokens("abc") == 0  # 3 // 4 == 0

    def test_estimate_tokens_empty(self):
        """Empty/None input estimates to zero."""
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0


# ---------------------------------------------------------------------------
# get_budget
# ---------------------------------------------------------------------------


class TestGetBudget:
    def test_default_when_unset(self, monkeypatch):
        """Falls back to DEFAULT_BUDGET when env var is unset."""
        monkeypatch.delenv("CRG_CONTEXT_BUDGET", raising=False)
        assert get_budget() == DEFAULT_BUDGET == 8000

    def test_env_var_override(self, monkeypatch):
        """CRG_CONTEXT_BUDGET overrides the default."""
        monkeypatch.setenv("CRG_CONTEXT_BUDGET", "2048")
        assert get_budget() == 2048

    def test_invalid_env_var_falls_back(self, monkeypatch):
        """Unparseable env var falls back to DEFAULT_BUDGET."""
        monkeypatch.setenv("CRG_CONTEXT_BUDGET", "not-a-number")
        assert get_budget() == DEFAULT_BUDGET

    def test_empty_env_var_falls_back(self, monkeypatch):
        """Empty env var falls back to DEFAULT_BUDGET."""
        monkeypatch.setenv("CRG_CONTEXT_BUDGET", "")
        assert get_budget() == DEFAULT_BUDGET


# ---------------------------------------------------------------------------
# budget_fill
# ---------------------------------------------------------------------------


class TestBudgetFill:
    def test_budget_fill_within_budget(self):
        """All candidates fit; nothing dropped."""
        # Each body is 40 chars -> 10 tokens. 3 nodes -> 30 tokens.
        candidates = [
            _node("a", "x" * 40, 0.9),
            _node("b", "x" * 40, 0.8),
            _node("c", "x" * 40, 0.7),
        ]
        included, dropped, meta = budget_fill(candidates, budget=100)

        assert [n["qualified_name"] for n in included] == ["a", "b", "c"]
        assert dropped == []
        assert meta.budget_used == 30
        assert meta.nodes_included == 3
        assert meta.nodes_dropped == 0

    def test_budget_fill_exceeds_budget(self):
        """Nodes beyond the ceiling are dropped, order preserved."""
        # Each body 40 chars -> 10 tokens. Budget 25 fits 2, drops 1.
        candidates = [
            _node("a", "x" * 40, 0.9),
            _node("b", "x" * 40, 0.8),
            _node("c", "x" * 40, 0.7),
        ]
        included, dropped, meta = budget_fill(candidates, budget=25)

        assert [n["qualified_name"] for n in included] == ["a", "b"]
        assert [n["qualified_name"] for n in dropped] == ["c"]
        assert meta.budget_used == 20
        assert meta.budget_total == 25
        assert meta.nodes_included == 2
        assert meta.nodes_dropped == 1

    def test_budget_fill_continues_after_drop(self):
        """Best-effort fill: a cheap node after an expensive drop is included."""
        # "big" costs 20 tokens, "small" costs 1. Budget 15 drops "big" but
        # the scan continues and still includes "small".
        candidates = [
            _node("big", "x" * 80, 0.9),
            _node("small", "x" * 4, 0.8),
        ]
        included, dropped, meta = budget_fill(candidates, budget=15)

        assert [n["qualified_name"] for n in included] == ["small"]
        assert [n["qualified_name"] for n in dropped] == ["big"]
        assert meta.budget_used == 1
        assert meta.budget_total == 15
        assert meta.nodes_included == 1
        assert meta.nodes_dropped == 1

    def test_budget_fill_empty_candidates(self):
        """Empty input yields empty lists and zero usage, no error."""
        included, dropped, meta = budget_fill([], budget=100)
        assert included == []
        assert dropped == []
        assert meta.budget_used == 0
        assert meta.budget_total == 100
        assert meta.nodes_included == 0
        assert meta.nodes_dropped == 0

    def test_budget_fill_returns_node_dicts_not_tuples(self):
        """included/dropped are node dicts, not (node, score) tuples."""
        candidates = [_node("a", "x" * 40, 0.9)]
        included, dropped, _ = budget_fill(candidates, budget=100)
        assert isinstance(included[0], dict)
        assert included[0]["qualified_name"] == "a"

    def test_budget_fill_preserves_given_order(self):
        """budget_fill must NOT re-sort; it respects the caller's order."""
        # Deliberately pass ascending score order; fill must keep it as-is.
        candidates = [
            _node("low", "x" * 4, 0.1),
            _node("mid", "x" * 4, 0.5),
            _node("high", "x" * 4, 0.9),
        ]
        included, _, _ = budget_fill(candidates, budget=100)
        assert [n["qualified_name"] for n in included] == ["low", "mid", "high"]

    def test_budget_fill_uses_get_budget_when_none(self, monkeypatch):
        """budget=None resolves via get_budget() (env var)."""
        monkeypatch.setenv("CRG_CONTEXT_BUDGET", "15")
        # Each body 40 chars -> 10 tokens. Budget 15 fits exactly 1.
        candidates = [
            _node("a", "x" * 40, 0.9),
            _node("b", "x" * 40, 0.8),
        ]
        included, dropped, meta = budget_fill(candidates)
        assert meta.budget_total == 15
        assert meta.nodes_included == 1
        assert meta.nodes_dropped == 1

    def test_budget_fill_explicit_overrides_env(self, monkeypatch):
        """Explicit budget arg overrides the env var."""
        monkeypatch.setenv("CRG_CONTEXT_BUDGET", "5")
        candidates = [_node("a", "x" * 40, 0.9)]  # 10 tokens
        included, dropped, meta = budget_fill(candidates, budget=100)
        assert meta.budget_total == 100
        assert meta.nodes_included == 1

    def test_token_cost_fallback_to_qualified_name(self):
        """A node lacking body/source/signature costs by qualified_name."""
        # No body -> cost derived from qualified_name "abcdefgh" (8 chars -> 2).
        candidates = [({"qualified_name": "abcdefgh"}, 0.9)]
        included, dropped, meta = budget_fill(candidates, budget=100)
        assert meta.budget_used == 2
        assert meta.nodes_included == 1


# ---------------------------------------------------------------------------
# BudgetMetadata
# ---------------------------------------------------------------------------


class TestBudgetMetadata:
    def test_metadata_accuracy(self):
        """Metadata fields match the fill result exactly."""
        candidates = [
            _node("a", "x" * 40, 0.9),  # 10
            _node("b", "x" * 80, 0.8),  # 20
            _node("c", "x" * 40, 0.7),  # 10 -> would exceed 25
        ]
        included, dropped, meta = budget_fill(candidates, budget=25)

        used = sum(estimate_tokens(n["body"]) for n in included)
        assert isinstance(meta, BudgetMetadata)
        assert meta.budget_used == used
        assert meta.budget_total == 25
        assert meta.nodes_included == len(included)
        assert meta.nodes_dropped == len(dropped)
