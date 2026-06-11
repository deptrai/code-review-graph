"""Relevance scorer for query-aware context ranking.

Implements the scoring formula from:
docs/specs/SPEC-phase1-relevance-budget.md#1a. Relevance Scorer

This module is SCORER ONLY. Token budget (budget.py), context shaping,
and migration v11+ are separate stories (1-2, 1-3) and are NOT implemented here.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class Intent(Enum):
    """Query intent categories for context scoring.

    Source: SPEC-phase1-relevance-budget.md#1a. Relevance Scorer
    """

    SECURITY = "security"
    PERFORMANCE = "performance"
    DEBUG = "debug"
    REVIEW = "review"
    REFACTOR = "refactor"
    GENERAL = "general"


@dataclass
class ScoringWeights:
    """Weight parameters for the relevance scoring formula.

    Defaults from SPEC-phase1-relevance-budget.md#Scoring Formula.
    Pass a custom instance to ``score_node`` / ``score_candidates`` to override.
    """

    graph_distance: float = 0.5
    churn_weight: float = 0.2
    semantic_similarity: float = 0.2
    test_gap_penalty: float = 0.1


# ---------------------------------------------------------------------------
# Intent signal phrases
# Source: SPEC-phase1-relevance-budget.md#Intent Classification Signal Phrases
# ---------------------------------------------------------------------------

_INTENT_SIGNALS: list[tuple[Intent, list[str]]] = [
    (
        Intent.SECURITY,
        [
            "auth", "token", "password", "permission", "access control",
            "vulnerability", "injection", "xss", "csrf", "sanitize", "encrypt",
        ],
    ),
    (
        Intent.PERFORMANCE,
        [
            "slow", "latency", "cache", "optimize", "memory", "cpu",
            "bottleneck", "n+1", "query plan", "index", "profil",
        ],
    ),
    (
        Intent.DEBUG,
        [
            "bug", "error", "crash", "exception", "stack trace", "undefined",
            "null", "race condition", "deadlock", "timeout", "hang",
        ],
    ),
    (
        Intent.REVIEW,
        ["review", "change", "diff", "pr", "merge", "approve", "comment", "quality"],
    ),
    (
        Intent.REFACTOR,
        [
            "refactor", "rename", "extract", "move", "split", "decompose",
            "clean up", "dry", "simplify",
        ],
    ),
]

# Precompiled, word-boundary-anchored matchers for each intent.
# Anchoring with a leading \b prevents mid-word false positives
# (e.g. "hang" inside "change", "move" inside "remove") while still
# matching word-start stems (e.g. "profil" -> "profiling", "auth" ->
# "authenticate"). re.escape keeps phrases like "n+1" / "access control"
# literal. Matching is case-insensitive.
_INTENT_PATTERNS: list[tuple[Intent, "re.Pattern[str]"]] = [
    (
        intent,
        re.compile(
            r"\b(?:" + "|".join(re.escape(p) for p in signals) + r")",
            re.IGNORECASE,
        ),
    )
    for intent, signals in _INTENT_SIGNALS
]

# Node name substrings that trigger the SECURITY intent boost.
# Source: SPEC-phase1-relevance-budget.md#Intent -> Node Type Boosting
_SECURITY_BOOST_KEYWORDS = frozenset({"auth", "token", "session", "permission"})

# Nodes with churn_score >= this threshold receive the PERFORMANCE intent boost.
_PERFORMANCE_CHURN_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_intent(query: str) -> Intent:
    """Classify query intent via case-insensitive, word-boundary matching.

    Iterates ``_INTENT_PATTERNS`` in priority order and returns the intent
    whose pattern first matches.  Each signal phrase is anchored with a
    leading word boundary (``\\b``) so a phrase only matches at a word start
    (e.g. "auth" -> "authenticate" yes, but "change" -> "hang" no).  Falls
    back to ``Intent.GENERAL`` when no signal phrase matches.

    Source: SPEC-phase1-relevance-budget.md#Intent Classification Signal Phrases
    """
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(query):
            return intent
    return Intent.GENERAL


def intent_matches(node: dict, intent: Intent) -> bool:
    """Return True when a node's metadata qualifies it for the intent boost.

    Pure function over node dict keys:
      - ``qualified_name`` / ``name``  (str)
      - ``churn_score``               (float, PERFORMANCE)
      - ``recently_modified``         (bool,  DEBUG)
      - ``is_changed``                (bool,  REVIEW)
      - ``is_hub``                    (bool,  REFACTOR)

    Source: SPEC-phase1-relevance-budget.md#Intent -> Node Type Boosting
    """
    if intent == Intent.GENERAL:
        return False

    name = (node.get("qualified_name") or node.get("name") or "").lower()

    if intent == Intent.SECURITY:
        return any(kw in name for kw in _SECURITY_BOOST_KEYWORDS)

    if intent == Intent.PERFORMANCE:
        return float(node.get("churn_score", 0.0)) >= _PERFORMANCE_CHURN_THRESHOLD

    if intent == Intent.DEBUG:
        return bool(node.get("recently_modified", False))

    if intent == Intent.REVIEW:
        return bool(node.get("is_changed", False))

    if intent == Intent.REFACTOR:
        return bool(node.get("is_hub", False))

    return False  # pragma: no cover


def score_node(
    node_qn: str,
    query: str,
    intent: Intent,
    graph_distance: int,
    churn_score: float,
    semantic_sim: float,
    has_tests: bool,
    weights: Optional[ScoringWeights] = None,
    node: Optional[dict] = None,
) -> float:
    """Return relevance score clamped to [0.0, 1.0] for a single node.

    Formula::

        score = (
            w.graph_distance * (1.0 / (1 + graph_distance))
            + w.churn_weight * churn_score
            + w.semantic_similarity * semantic_sim
            + w.test_gap_penalty * (0.0 if has_tests else -0.1)
        )
        if intent_matches(node, intent):
            score *= 1.3
        score = max(0.0, min(1.0, score))

    ``node`` (optional) supplies extra metadata for intent boosting.  When
    omitted, a minimal dict ``{"qualified_name": node_qn}`` is synthesised so
    that name-based boosting (e.g. SECURITY) still works.

    Source: SPEC-phase1-relevance-budget.md#Scoring Formula
    """
    w = weights or ScoringWeights()

    score = (
        w.graph_distance * (1.0 / (1 + graph_distance))
        + w.churn_weight * churn_score
        + w.semantic_similarity * semantic_sim
        + w.test_gap_penalty * (0.0 if has_tests else -0.1)
    )

    _node = node if node is not None else {"qualified_name": node_qn}
    if intent_matches(_node, intent):
        score *= 1.3

    return max(0.0, min(1.0, score))


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors using stdlib math only.

    Returns 0.0 for zero-magnitude vectors and for dimension mismatches.
    Guarding the length prevents ``zip`` from silently truncating to the
    shorter vector (which yields a wrong, often inflated, similarity when
    two different embedding models are mixed). No new dependencies.
    """
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def score_candidates(
    candidates: list[dict],
    query: str,
    intent: Intent,
    query_embedding: Optional[list[float]] = None,
    weights: Optional[ScoringWeights] = None,
) -> list[tuple[dict, float]]:
    """Score and sort all candidates by relevance. Returns (node, score) pairs desc.

    Each candidate dict may supply:
      - ``qualified_name`` / ``name``    — node identifier
      - ``graph_distance`` (int)         — BFS hops from query root
      - ``churn_score``    (float)       — normalised churn frequency [0, 1]
      - ``has_tests``      (bool)        — whether tests cover this node
      - ``embedding``      (list[float]) — optional vector for semantic_sim
      - any additional keys consulted by ``intent_matches``

    When ``query_embedding`` is supplied, ``semantic_sim`` is computed as
    cosine similarity against each node's ``embedding`` field; otherwise 0.0.

    Source: SPEC-phase1-relevance-budget.md#1a. Relevance Scorer
    """
    results: list[tuple[dict, float]] = []

    for node in candidates:
        node_emb = node.get("embedding")
        if query_embedding is not None and node_emb is not None:
            semantic_sim = _cosine_sim(query_embedding, node_emb)
        else:
            semantic_sim = 0.0

        s = score_node(
            node_qn=node.get("qualified_name") or node.get("name") or "",
            query=query,
            intent=intent,
            graph_distance=int(node.get("graph_distance", 0)),
            churn_score=float(node.get("churn_score", 0.0)),
            semantic_sim=semantic_sim,
            has_tests=bool(node.get("has_tests", False)),
            weights=weights,
            node=node,
        )
        results.append((node, s))

    results.sort(key=lambda x: x[1], reverse=True)
    return results
