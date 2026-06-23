"""Dynamic token budget manager for context assembly.

Implements the greedy budget-fill logic from:
docs/specs/SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager

This module is the BUDGET MANAGER ONLY. It is a set of pure functions over
the scored-candidate tuples produced by ``relevance.score_candidates``. It
does NOT wire into the MCP tool handlers (``tools/review.py`` /
``tools/context.py``) — that query-aware context shaping is story 1-3.
No migration is added here (the ``relevance_cache`` table is also story 1-3).

Token cost per node
-------------------
A node's token cost is estimated from the textual payload it will contribute
to the response. We look up, in order, the first present non-empty field of:
``body`` -> ``source`` -> ``signature``. When none of those is present, we
fall back to estimating over the node's ``qualified_name`` (or ``name``) so a
node's cost is never zero-by-omission (a zero-cost node could let an unbounded
number of payload-less candidates slip past the budget gate).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# Source: SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager
# ---------------------------------------------------------------------------

DEFAULT_BUDGET = 8000

# Environment variable that overrides the default budget.
_BUDGET_ENV_VAR = "CRG_CONTEXT_BUDGET"

# Node-dict fields consulted, in priority order, to estimate token cost.
_TOKEN_SOURCE_FIELDS = ("body", "source", "signature")


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class BudgetMetadata:
    """Observability metadata describing a single ``budget_fill`` result.

    Attributes:
        budget_used: Sum of estimated token costs of all included nodes.
        budget_total: The effective budget ceiling used for the fill.
        nodes_included: Count of nodes that fit within the budget.
        nodes_dropped: Count of nodes dropped after the budget was exhausted.

    Source: SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager
    """

    budget_used: int
    budget_total: int
    nodes_included: int
    nodes_dropped: int


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_budget() -> int:
    """Return the context token budget.

    Reads the ``CRG_CONTEXT_BUDGET`` environment variable and parses it as an
    integer. Falls back to ``DEFAULT_BUDGET`` when the variable is unset, empty,
    or not a valid integer.

    Source: SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager
    """
    raw = os.environ.get(_BUDGET_ENV_VAR)
    if raw is None:
        return DEFAULT_BUDGET
    try:
        return int(raw)
    except (ValueError, TypeError):
        return DEFAULT_BUDGET


def estimate_tokens(text: str | None) -> int:
    """Estimate the token count of ``text`` using the ``len // 4`` heuristic.

    A coarse, dependency-free approximation: English text and source code
    average roughly four characters per token. Returns 0 for empty/None input.

    Source: SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager
    """
    if not text:
        return 0
    return len(text) // 4


def _node_token_cost(node: dict) -> int:
    """Estimate the token cost a single node contributes to the response.

    Uses the first present non-empty field of ``body`` -> ``source`` ->
    ``signature``; falls back to ``qualified_name`` / ``name`` so the cost is
    never zero purely because a payload field is missing.
    """
    for field in _TOKEN_SOURCE_FIELDS:
        value = node.get(field)
        if value:
            return estimate_tokens(str(value))

    fallback = node.get("qualified_name") or node.get("name") or ""
    return estimate_tokens(str(fallback))


def budget_fill(
    scored_candidates: list[tuple[dict, float]],
    budget: Optional[int] = None,
) -> tuple[list[dict], list[dict], BudgetMetadata]:
    """Greedily fill a token budget from pre-sorted scored candidates.

    Iterates ``scored_candidates`` in the order given — which the caller
    (``relevance.score_candidates``) has already sorted by descending score —
    and includes each node whose estimated cost keeps the running total within
    ``budget``. A node that would exceed the remaining budget is dropped, but
    the scan **continues**: a later, cheaper candidate can still be included
    after a costlier one was dropped (best-effort fill for higher budget
    utilization). This function never re-sorts; it respects the given order.

    Args:
        scored_candidates: ``(node_dict, score)`` pairs, highest score first.
            Only the node dict is used here; the score serves purely as the
            ordering the caller already applied.
        budget: Optional explicit token ceiling. When ``None``, ``get_budget()``
            supplies the effective budget (env var or default).

    Returns:
        ``(included_nodes, dropped_nodes, metadata)`` where the first two are
        lists of node dicts (NOT score tuples).

    Source: SPEC-phase1-relevance-budget.md#1b. Dynamic Token Budget Manager
    """
    effective_budget = budget if budget is not None else get_budget()

    included: list[dict] = []
    dropped: list[dict] = []
    used = 0

    for node, _score in scored_candidates:
        cost = _node_token_cost(node)
        if used + cost <= effective_budget:
            included.append(node)
            used += cost
        else:
            dropped.append(node)

    metadata = BudgetMetadata(
        budget_used=used,
        budget_total=effective_budget,
        nodes_included=len(included),
        nodes_dropped=len(dropped),
    )
    return included, dropped, metadata
