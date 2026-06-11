# Technical Spec: Phase 1 — Relevance Ranking + Dynamic Token Budget

## Overview

Replace flat BFS context dumps with scored, budget-aware context assembly. This is the foundation all later phases build on.

## Components

### 1a. Relevance Scorer (`code_review_graph/relevance.py`)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import numpy as np

class Intent(Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    DEBUG = "debug"
    REVIEW = "review"
    REFACTOR = "refactor"
    GENERAL = "general"

@dataclass
class ScoringWeights:
    graph_distance: float = 0.5
    churn_weight: float = 0.2
    semantic_similarity: float = 0.2
    test_gap_penalty: float = 0.1

def classify_intent(query: str) -> Intent:
    """Classify query intent from signal phrases."""
    ...

def score_node(
    node_qn: str,
    query: str,
    intent: Intent,
    graph_distance: int,
    churn_score: float,
    semantic_sim: float,
    has_tests: bool,
    weights: Optional[ScoringWeights] = None,
) -> float:
    """Return relevance score 0-1 for a single node."""
    ...

def score_candidates(
    candidates: list[dict],
    query: str,
    intent: Intent,
    query_embedding: Optional[list[float]] = None,
    weights: Optional[ScoringWeights] = None,
) -> list[tuple[dict, float]]:
    """Score and sort all candidates. Returns (node, score) pairs desc."""
    ...
```

#### Intent Classification Signal Phrases

| Intent | Signals |
|--------|---------|
| SECURITY | auth, token, password, permission, access control, vulnerability, injection, XSS, CSRF, sanitize, encrypt |
| PERFORMANCE | slow, latency, cache, optimize, memory, CPU, bottleneck, N+1, query plan, index, profil |
| DEBUG | bug, error, crash, exception, stack trace, undefined, null, race condition, deadlock, timeout, hang |
| REVIEW | review, change, diff, PR, merge, approve, comment, quality |
| REFACTOR | refactor, rename, extract, move, split, decompose, clean up, DRY, simplify |

#### Scoring Formula

```
score = (
    weights.graph_distance * (1.0 / (1 + graph_distance)) +
    weights.churn_weight * churn_score +
    weights.semantic_similarity * semantic_sim +
    weights.test_gap_penalty * (0.0 if has_tests else -0.1)
)

# Intent boost: multiply by 1.3 if node matches intent category
if intent_matches(node, intent):
    score *= 1.3

# Clamp to [0, 1]
score = max(0.0, min(1.0, score))
```

### 1b. Dynamic Token Budget Manager (`code_review_graph/budget.py`)

```python
from dataclasses import dataclass
from typing import Optional
import os

DEFAULT_BUDGET = 8000

@dataclass
class BudgetMetadata:
    budget_used: int
    budget_total: int
    nodes_included: int
    nodes_dropped: int

def get_budget() -> int:
    """Read from CRG_CONTEXT_BUDGET env var or return default."""
    return int(os.environ.get("CRG_CONTEXT_BUDGET", DEFAULT_BUDGET))

def estimate_tokens(text: str) -> int:
    """Estimate token count. Heuristic: len // 4."""
    return len(text) // 4

def budget_fill(
    scored_candidates: list[tuple[dict, float]],
    budget: Optional[int] = None,
) -> tuple[list[dict], list[dict], BudgetMetadata]:
    """
    Greedy fill: iterate scored candidates desc, add until budget exhausted.
    
    Returns: (included_nodes, dropped_nodes, metadata)
    """
    ...
```

### 1c. Query-Aware Context Shaping

Update `tools/review.py` and `tools/context.py`:

```python
# In get_review_context_tool handler:
def _assemble_context(candidates, query, detail_level, max_depth, ...):
    if detail_level == "minimal":
        # Bypass scoring entirely (backward compat)
        return existing_logic(candidates)
    
    intent = classify_intent(query or "")
    scored = score_candidates(candidates, query, intent, query_embedding)
    included, dropped, meta = budget_fill(scored)
    
    # Attach metadata to response
    response["_budget_metadata"] = asdict(meta)
    return response
```

#### Intent → Node Type Boosting

| Intent | Boosted Node Types |
|--------|-------------------|
| SECURITY | Functions containing "auth", "token", "session", "permission" |
| PERFORMANCE | High-churn nodes, nodes in hot flows |
| DEBUG | Recently modified nodes (last 7 days), error-handling functions |
| REVIEW | Changed nodes + their callers/callees |
| REFACTOR | High-degree hub nodes, cross-community edges |

### 1d. Migration v11: Relevance Cache

```sql
CREATE TABLE IF NOT EXISTS relevance_cache (
    query_hash TEXT NOT NULL,
    node_qn TEXT NOT NULL,
    score REAL NOT NULL,
    intent TEXT NOT NULL,
    computed_at REAL NOT NULL,
    PRIMARY KEY (query_hash, node_qn)
);

CREATE INDEX idx_relevance_cache_time ON relevance_cache(computed_at);
```

- TTL: 5 minutes (300 seconds)
- Invalidation: Clear when NetworkX cache resets (on graph update)
- Cleanup: DELETE WHERE computed_at < now - 300 on each query

## Integration Points

- `tools/review.py` → calls `score_candidates()` + `budget_fill()`
- `tools/context.py` → calls `classify_intent()` for shaping
- `hints.py` → expanded with intent signal phrases
- `graph.py` → provides `graph_distance` via existing BFS
- `embeddings.py` → provides `semantic_sim` via existing similarity
- `incremental.py` → invalidates relevance_cache on update

## Testing Strategy

```
tests/test_relevance.py:
  - test_classify_intent_security
  - test_classify_intent_performance
  - test_classify_intent_debug
  - test_classify_intent_general_fallback
  - test_score_node_basic
  - test_score_node_intent_boost
  - test_score_candidates_ordering
  - test_custom_weights

tests/test_budget.py:
  - test_budget_fill_within_budget
  - test_budget_fill_exceeds_budget
  - test_budget_fill_empty_candidates
  - test_estimate_tokens
  - test_env_var_override
  - test_metadata_accuracy

tests/test_integration_relevance.py:
  - test_review_context_with_scoring
  - test_minimal_detail_level_bypasses_scoring
  - test_relevance_cache_hit
  - test_relevance_cache_invalidation
```

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|---------------|
| Token efficiency | ≥20% reduction | Compare context size at same recall vs baseline |
| Impact F1 | +10% | eval framework with ground-truth annotations |
| p95 latency | <200ms | Benchmark on 50k-node repo |
| Cache hit rate | >60% | Log cache hits during typical review session |

## Rollout

1. Feature-gated behind scoring logic (detail_level check)
2. Metadata always attached for observability
3. No new dependencies required
4. Migration v11 runs automatically on first use
