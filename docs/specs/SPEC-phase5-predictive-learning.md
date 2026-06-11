# Technical Spec: Phase 5 — Predictive Context & Self-Learning

## Overview

Add predictive capabilities: anticipate what context a developer needs based on patterns, and self-tune relevance weights from implicit feedback (which context was actually used by the LLM).

## Components

### 5a. Usage Tracker (`code_review_graph/usage_tracker.py`)

```python
from dataclasses import dataclass
import time

@dataclass
class ContextUsageEvent:
    session_id: str
    tool_name: str           # which MCP tool was called
    intent_classified: str   # from Phase 1 intent classifier
    nodes_offered: list[str] # QNs offered in context
    nodes_referenced: list[str]  # QNs the LLM actually referenced in output
    budget_used: int         # tokens consumed
    budget_total: int        # tokens available
    timestamp: float = 0.0
    
    def utilization_rate(self) -> float:
        """What fraction of offered nodes were actually used."""
        if not self.nodes_offered:
            return 0.0
        return len(self.nodes_referenced) / len(self.nodes_offered)

class UsageTracker:
    """Track which context nodes the LLM actually references."""
    
    def __init__(self, db_path: str):
        self._db_path = db_path
    
    def record(self, event: ContextUsageEvent) -> None:
        """Record a usage event for learning."""
        ...
    
    def get_utilization_stats(
        self, window_days: int = 30
    ) -> dict:
        """Aggregate utilization stats by intent type."""
        ...
    
    def get_high_value_nodes(
        self, intent: str, top_n: int = 20
    ) -> list[tuple[str, float]]:
        """Nodes most frequently referenced for a given intent."""
        ...
```

### 5b. Weight Tuner (`code_review_graph/weight_tuner.py`)

```python
@dataclass
class WeightProfile:
    intent: str
    weights: dict[str, float]  # factor_name -> weight
    updated_at: float
    sample_count: int

DEFAULT_WEIGHTS = {
    "review": {
        "structural_distance": 0.30,
        "churn_recency": 0.20,
        "community_cohesion": 0.20,
        "test_coverage_gap": 0.15,
        "hub_centrality": 0.15,
    },
    "debug": {
        "structural_distance": 0.35,
        "call_depth": 0.25,
        "error_proximity": 0.20,
        "churn_recency": 0.10,
        "community_cohesion": 0.10,
    },
}

class WeightTuner:
    """Self-tune relevance weights based on usage patterns."""
    
    def __init__(self, db_path: str, learning_rate: float = 0.1):
        self._db_path = db_path
        self._lr = learning_rate
    
    def get_weights(self, intent: str) -> dict[str, float]:
        """Return current weights for intent, or defaults."""
        ...
    
    def update_from_feedback(
        self, intent: str, event: ContextUsageEvent
    ) -> WeightProfile:
        """
        Adjust weights based on which nodes were used.
        
        Strategy: EMA (exponential moving average)
        - Nodes referenced → boost factors that scored them high
        - Nodes offered but not referenced → penalize contributing factors
        """
        ...
    
    def reset_to_defaults(self, intent: str) -> None:
        """Reset weights to defaults (escape local minima)."""
        ...
```

### 5c. Predictive Prefetch (`code_review_graph/predictor.py`)

```python
@dataclass
class PredictedContext:
    nodes: list[str]         # predicted-relevant QNs
    confidence: float        # 0-1
    reason: str              # why predicted
    intent_guess: str        # predicted intent

class ContextPredictor:
    """Predict likely next context needs from file open patterns."""
    
    def __init__(self, db_path: str):
        self._db_path = db_path
    
    def predict_from_file_open(
        self, file_path: str, repo_root: str
    ) -> PredictedContext:
        """
        When a file is opened, predict what context will be needed.
        
        Signals:
        - File's community → related files likely needed
        - File's flows → downstream likely needed
        - Historical patterns → co-queried nodes
        """
        ...
    
    def predict_from_edit_pattern(
        self, edited_files: list[str], repo_root: str
    ) -> PredictedContext:
        """
        After multiple edits, predict what review context to pre-warm.
        """
        ...
```

### 5d. Migration v14

```sql
CREATE TABLE IF NOT EXISTS context_usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    intent_classified TEXT NOT NULL,
    nodes_offered TEXT NOT NULL,      -- JSON array of QNs
    nodes_referenced TEXT NOT NULL,   -- JSON array of QNs
    budget_used INTEGER NOT NULL,
    budget_total INTEGER NOT NULL,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_intent 
    ON context_usage_events(intent_classified);
CREATE INDEX IF NOT EXISTS idx_usage_timestamp 
    ON context_usage_events(timestamp);

CREATE TABLE IF NOT EXISTS weight_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intent TEXT NOT NULL UNIQUE,
    weights TEXT NOT NULL,            -- JSON dict
    updated_at REAL NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0
);
```

## Feedback Loop Architecture

```
Request → Intent Classify → Score Nodes (with tuned weights)
                                    ↓
                             Assemble Context → Return to LLM
                                    ↓
                             Track: which nodes referenced?
                                    ↓
                             Update weights (async, non-blocking)
```

## Privacy & Safety

- All tracking is local (SQLite only)
- No context content stored — only QN references
- User can disable: `CRG_DISABLE_TRACKING=1`
- Data auto-expires after 90 days (cleanup on build)
- No PII in tracked data

## Testing

```
tests/test_usage_tracker.py:
  - test_record_and_retrieve_event
  - test_utilization_rate_calculation
  - test_high_value_nodes_ranking
  - test_auto_expire_old_events

tests/test_weight_tuner.py:
  - test_default_weights_returned_when_no_history
  - test_ema_update_boosts_used_factors
  - test_ema_update_penalizes_unused_factors
  - test_reset_to_defaults
  - test_weights_sum_to_one_invariant

tests/test_predictor.py:
  - test_predict_from_file_open_same_community
  - test_predict_from_edit_pattern
  - test_empty_history_returns_low_confidence
```
