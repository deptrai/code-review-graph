# Technical Spec: Phase 4 — Multi-Repo Intelligence

## Overview

Extend context engine to reason across repository boundaries. When a symbol changes in repo A, surface impact in repos B, C that depend on it — with scored relevance and budget-aware assembly.

## Components

### 4a. Cross-Repo Registry Enhancement (`code_review_graph/registry.py`)

```python
@dataclass
class RepoRelation:
    source_repo: str        # repo providing the symbol
    target_repo: str        # repo consuming the symbol
    relation_type: str      # "imports", "api_client", "shared_types", "submodule"
    interface_symbols: list[str]  # symbols at the boundary
    confidence: float       # 0-1

def discover_repo_relations(registry_path: str) -> list[RepoRelation]:
    """Scan registered repos to discover dependency relationships."""
    ...

def get_cross_repo_impact(
    symbol: str,
    source_repo: str,
    relations: list[RepoRelation],
) -> list[dict]:
    """Find all repos + symbols affected by a change to `symbol`."""
    ...
```

### 4b. Cross-Repo Context Assembly (`code_review_graph/cross_context.py`)

```python
def assemble_cross_repo_context(
    changed_symbols: list[str],
    source_repo: str,
    intent: Intent,
    budget: int,
) -> dict:
    """
    Assemble context spanning multiple repos.
    
    Strategy:
    1. Score local impact (Phase 1 scorer)
    2. Find cross-repo consumers via registry
    3. Score remote nodes with distance penalty (x0.7 per repo hop)
    4. Budget-fill across all repos, local-first
    """
    ...
```

### 4c. Interface Contract Tracking

```python
@dataclass
class InterfaceContract:
    repo: str
    symbol_qn: str
    signature_hash: str     # hash of function signature
    return_type: str
    param_types: list[str]
    last_verified: float

def detect_contract_breaks(
    source_repo: str,
    base: str = "HEAD~1",
) -> list[dict]:
    """Detect signature changes that may break downstream repos."""
    ...
```

### 4d. Migration v13

```sql
CREATE TABLE IF NOT EXISTS repo_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_repo TEXT NOT NULL,
    target_repo TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    interface_symbols TEXT NOT NULL,  -- JSON array
    confidence REAL NOT NULL,
    discovered_at REAL NOT NULL,
    UNIQUE(source_repo, target_repo, relation_type)
);

CREATE TABLE IF NOT EXISTS interface_contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    symbol_qn TEXT NOT NULL,
    signature_hash TEXT NOT NULL,
    return_type TEXT,
    param_types TEXT,  -- JSON array
    last_verified REAL NOT NULL,
    UNIQUE(repo, symbol_qn)
);
```

## Integration

- `cross_repo_impact_tool` → enhanced with scored results
- `detect_changes_tool` → optionally includes cross-repo impact
- `get_review_context_tool` → can span repos when requested

## Scoring Adjustments

| Factor | Modifier |
|--------|----------|
| Same repo | 1.0x |
| Direct dependency repo | 0.7x |
| Transitive dependency | 0.5x |
| Interface boundary symbol | +0.2 boost |
| Contract break detected | +0.4 boost |

## Testing

```
tests/test_cross_context.py:
  - test_cross_repo_impact_single_consumer
  - test_cross_repo_impact_multiple_repos
  - test_distance_penalty_applied
  - test_budget_fill_local_first
  - test_contract_break_detection
  - test_no_registered_repos_graceful
```
