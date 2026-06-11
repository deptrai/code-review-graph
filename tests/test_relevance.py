"""Tests for the relevance scoring module.

Covers: Intent classification, node scoring formula, candidate ranking,
custom weights, intent boost, and score clamping.

Source: docs/specs/SPEC-phase1-relevance-budget.md#1a. Relevance Scorer
"""

import pytest
from code_review_graph.relevance import (
    Intent,
    ScoringWeights,
    classify_intent,
    intent_matches,
    score_node,
    score_candidates,
)


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------


class TestClassifyIntent:
    def test_classify_intent_security(self):
        """Signal phrase 'auth' maps to Intent.SECURITY."""
        assert classify_intent("check the auth token validation") == Intent.SECURITY

    def test_classify_intent_performance(self):
        """Signal phrase 'slow' maps to Intent.PERFORMANCE."""
        assert classify_intent("why is this query so slow?") == Intent.PERFORMANCE

    def test_classify_intent_debug(self):
        """Signal phrase 'exception' maps to Intent.DEBUG."""
        assert classify_intent("there is a null pointer exception here") == Intent.DEBUG

    def test_classify_intent_general_fallback(self):
        """Query with no recognised signals falls back to Intent.GENERAL."""
        assert classify_intent("list all the user endpoints") == Intent.GENERAL

    def test_classify_intent_case_insensitive(self):
        """Intent matching is case-insensitive."""
        assert classify_intent("AUTH token check") == Intent.SECURITY
        assert classify_intent("SLOW database call") == Intent.PERFORMANCE

    def test_classify_intent_review(self):
        """Signal phrase 'review' maps to Intent.REVIEW."""
        assert classify_intent("please review this PR") == Intent.REVIEW

    def test_classify_intent_refactor(self):
        """Signal phrase 'refactor' maps to Intent.REFACTOR."""
        assert classify_intent("refactor this module to simplify it") == Intent.REFACTOR

    def test_classify_intent_empty_query(self):
        """Empty query falls back to Intent.GENERAL."""
        assert classify_intent("") == Intent.GENERAL

    def test_classify_intent_review_change_not_debug(self):
        """'change' must map to REVIEW, not DEBUG via 'hang' substring.

        Regression: substring matching let DEBUG's 'hang' match inside
        'change'/'changed', making REVIEW unreachable for the most common
        review phrasing. Word-boundary matching fixes this (AC2).
        """
        assert classify_intent("review this change") == Intent.REVIEW
        assert classify_intent("what changed in this diff") == Intent.REVIEW

    def test_classify_intent_no_midword_false_positives(self):
        """Signal phrases must not match mid-word.

        'move' (REFACTOR) must not match inside 'remove'; with no other
        signal present the query falls back to GENERAL.
        """
        assert classify_intent("remove dead code") == Intent.GENERAL

    def test_classify_intent_matches_word_start_stem(self):
        """Word-boundary anchoring still matches word-start stems."""
        # 'profil' -> 'profiling' at a word start still triggers PERFORMANCE
        assert classify_intent("profiling the hot path") == Intent.PERFORMANCE
        # 'auth' -> 'authenticate' at a word start still triggers SECURITY
        assert classify_intent("authenticate the request") == Intent.SECURITY


# ---------------------------------------------------------------------------
# score_node
# ---------------------------------------------------------------------------


class TestScoreNode:
    def test_score_node_basic(self):
        """Scoring formula produces expected result with default weights."""
        # graph_distance=0  → 0.5 * (1/(1+0)) = 0.5
        # churn_score=0.5   → 0.2 * 0.5      = 0.1
        # semantic_sim=0.0  → 0.2 * 0.0      = 0.0
        # has_tests=True    → 0.1 * 0.0      = 0.0
        # total = 0.6, no boost (GENERAL intent)
        score = score_node(
            node_qn="some_function",
            query="review this",
            intent=Intent.GENERAL,
            graph_distance=0,
            churn_score=0.5,
            semantic_sim=0.0,
            has_tests=True,
        )
        assert abs(score - 0.6) < 1e-9

    def test_score_node_intent_boost(self):
        """Node name containing 'auth' gets 1.3x boost for SECURITY intent."""
        base_score = score_node(
            node_qn="authenticate_user",
            query="review auth",
            intent=Intent.GENERAL,
            graph_distance=0,
            churn_score=0.0,
            semantic_sim=0.0,
            has_tests=True,
        )
        boosted_score = score_node(
            node_qn="authenticate_user",
            query="check auth token",
            intent=Intent.SECURITY,
            graph_distance=0,
            churn_score=0.0,
            semantic_sim=0.0,
            has_tests=True,
        )
        # base = 0.5 * 1.0 = 0.5 → boosted = 0.5 * 1.3 = 0.65
        assert boosted_score > base_score
        assert abs(boosted_score - 0.65) < 1e-9
        assert boosted_score <= 1.0

    def test_score_node_clamp_upper(self):
        """Score is clamped to 1.0 even when boost would exceed it."""
        score = score_node(
            node_qn="authenticate_session",
            query="auth token check",
            intent=Intent.SECURITY,
            graph_distance=0,
            churn_score=1.0,
            semantic_sim=1.0,
            has_tests=True,
        )
        assert score <= 1.0

    def test_score_node_clamp_lower(self):
        """Score is clamped to 0.0 and never goes negative."""
        score = score_node(
            node_qn="some_func",
            query="test",
            intent=Intent.GENERAL,
            graph_distance=1000,
            churn_score=0.0,
            semantic_sim=0.0,
            has_tests=False,
        )
        assert score >= 0.0

    def test_score_node_test_gap_penalty(self):
        """Missing tests incur a small negative contribution."""
        score_with_tests = score_node(
            node_qn="func",
            query="q",
            intent=Intent.GENERAL,
            graph_distance=1,
            churn_score=0.0,
            semantic_sim=0.0,
            has_tests=True,
        )
        score_without_tests = score_node(
            node_qn="func",
            query="q",
            intent=Intent.GENERAL,
            graph_distance=1,
            churn_score=0.0,
            semantic_sim=0.0,
            has_tests=False,
        )
        assert score_with_tests > score_without_tests


# ---------------------------------------------------------------------------
# score_candidates
# ---------------------------------------------------------------------------


class TestScoreCandidates:
    def _make_node(
        self,
        name: str,
        graph_distance: int = 0,
        churn: float = 0.0,
        has_tests: bool = True,
    ) -> dict:
        return {
            "qualified_name": name,
            "graph_distance": graph_distance,
            "churn_score": churn,
            "has_tests": has_tests,
        }

    def test_score_candidates_ordering(self):
        """score_candidates returns pairs sorted by score descending."""
        candidates = [
            self._make_node("far_function", graph_distance=10),
            self._make_node("close_function", graph_distance=0),
        ]
        results = score_candidates(candidates, "review", Intent.GENERAL)
        assert len(results) == 2
        # close_function (distance=0) must rank above far_function (distance=10)
        assert results[0][0]["qualified_name"] == "close_function"
        assert results[0][1] >= results[1][1]

    def test_score_candidates_returns_tuples(self):
        """Each element in the result is a (dict, float) tuple."""
        candidates = [self._make_node("func_a")]
        results = score_candidates(candidates, "test query", Intent.GENERAL)
        assert len(results) == 1
        node, score = results[0]
        assert isinstance(node, dict)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_score_candidates_empty(self):
        """Empty candidate list returns empty list."""
        results = score_candidates([], "query", Intent.GENERAL)
        assert results == []

    def test_custom_weights(self):
        """Custom ScoringWeights override defaults and influence ranking."""
        weights = ScoringWeights(
            graph_distance=0.0,
            churn_weight=1.0,
            semantic_similarity=0.0,
            test_gap_penalty=0.0,
        )
        candidates = [
            {**self._make_node("high_churn", graph_distance=10), "churn_score": 0.9},
            {**self._make_node("low_churn", graph_distance=0), "churn_score": 0.1},
        ]
        results = score_candidates(
            candidates, "optimize", Intent.GENERAL, weights=weights
        )
        # With graph_distance weight=0, high_churn wins despite its large distance
        assert results[0][0]["qualified_name"] == "high_churn"
        assert abs(results[0][1] - 0.9) < 1e-9

    def test_embedding_increases_score(self):
        """A node whose embedding matches the query gets a semantic boost."""
        weights = ScoringWeights(
            graph_distance=0.0,
            churn_weight=0.0,
            semantic_similarity=1.0,
            test_gap_penalty=0.0,
        )
        candidates = [
            {**self._make_node("aligned"), "embedding": [1.0, 0.0, 0.0]},
            {**self._make_node("orthogonal"), "embedding": [0.0, 1.0, 0.0]},
        ]
        results = score_candidates(
            candidates,
            "query",
            Intent.GENERAL,
            query_embedding=[1.0, 0.0, 0.0],
            weights=weights,
        )
        assert results[0][0]["qualified_name"] == "aligned"
        # cosine([1,0,0],[1,0,0]) == 1.0 with full semantic weight
        assert abs(results[0][1] - 1.0) < 1e-9
        # orthogonal vector contributes zero semantic signal
        assert abs(results[1][1] - 0.0) < 1e-9

    def test_embedding_dimension_mismatch_is_zero(self):
        """Mismatched embedding dimensions yield 0 semantic_sim, not a crash.

        Guards against zip() silently truncating to the shorter vector when
        two different embedding models are mixed.
        """
        weights = ScoringWeights(
            graph_distance=0.0,
            churn_weight=0.0,
            semantic_similarity=1.0,
            test_gap_penalty=0.0,
        )
        candidates = [{**self._make_node("mismatch"), "embedding": [1.0, 0.0]}]
        results = score_candidates(
            candidates,
            "query",
            Intent.GENERAL,
            query_embedding=[1.0, 0.0, 0.0],
            weights=weights,
        )
        assert abs(results[0][1] - 0.0) < 1e-9

    def test_no_query_embedding_skips_semantic(self):
        """Without a query embedding, node embeddings are ignored (sim=0)."""
        weights = ScoringWeights(
            graph_distance=0.0,
            churn_weight=0.0,
            semantic_similarity=1.0,
            test_gap_penalty=0.0,
        )
        candidates = [{**self._make_node("has_emb"), "embedding": [1.0, 0.0, 0.0]}]
        results = score_candidates(candidates, "query", Intent.GENERAL, weights=weights)
        assert abs(results[0][1] - 0.0) < 1e-9
