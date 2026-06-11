# Context Engine Evaluation Framework

## Overview

Automated evaluation harness to measure context quality across phases. Runs as CI check and local benchmarking tool.

## Metrics

### Primary Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| **Relevance Precision** | % of context nodes actually referenced by LLM | ≥ 70% |
| **Relevance Recall** | % of needed nodes included in context | ≥ 85% |
| **Token Efficiency** | useful_tokens / total_tokens_sent | ≥ 0.6 |
| **Latency P95** | 95th percentile context assembly time | ≤ 200ms |
| **Budget Adherence** | % of responses within token budget | ≥ 95% |

### Secondary Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| **Intent Accuracy** | Correct intent classification rate | ≥ 90% |
| **Rank Correlation** | Spearman ρ between predicted and ideal ranking | ≥ 0.7 |
| **Cross-Repo Coverage** | % of impacted downstream repos surfaced | ≥ 80% |
| **Cold Start Latency** | First query after build | ≤ 500ms |

## Test Corpus

### Structure

```
tests/eval/
├── corpus/
│   ├── review_simple/      # single-file change, clear scope
│   │   ├── diff.patch
│   │   ├── query.txt       # natural language query
│   │   ├── expected.json   # ideal context nodes + ranking
│   │   └── metadata.json   # intent, difficulty, repo snapshot
│   ├── review_complex/     # multi-file, cross-community
│   ├── debug_trace/        # tracing a bug through call chain
│   ├── understand_arch/    # architecture exploration
│   └── multi_repo/         # cross-repo impact scenario
├── fixtures/
│   ├── small_repo.tar.gz   # 50 files, pre-built graph
│   ├── medium_repo.tar.gz  # 500 files, pre-built graph
│   └── large_repo.tar.gz   # 5000 files, pre-built graph
├── conftest.py
├── test_eval_relevance.py
├── test_eval_budget.py
├── test_eval_latency.py
└── run_eval.py             # CLI entry point
```

### Corpus Entry Schema (`expected.json`)

```json
{
  "intent": "review",
  "ideal_nodes": [
    {"qn": "AuthService.validate_token", "rank": 1, "required": true},
    {"qn": "TokenStore.get", "rank": 2, "required": true},
    {"qn": "middleware.auth_check", "rank": 3, "required": false}
  ],
  "max_acceptable_budget": 4000,
  "min_required_nodes": ["AuthService.validate_token", "TokenStore.get"],
  "irrelevant_nodes": ["utils.format_date", "config.load"]
}
```

## Evaluation Runner

### CLI

```bash
# Run full eval suite
uv run python tests/eval/run_eval.py

# Run specific scenario
uv run python tests/eval/run_eval.py --scenario review_simple

# Run with specific budget
uv run python tests/eval/run_eval.py --budget 4000

# Output machine-readable results
uv run python tests/eval/run_eval.py --format json > eval_results.json

# Compare two runs
uv run python tests/eval/run_eval.py --compare baseline.json current.json
```

### Runner Implementation (`tests/eval/run_eval.py`)

```python
"""Context Engine evaluation runner."""
import argparse
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict

@dataclass
class EvalResult:
    scenario: str
    precision: float
    recall: float
    token_efficiency: float
    latency_ms: float
    budget_adherence: bool
    rank_correlation: float
    intent_correct: bool
    
    @property
    def passed(self) -> bool:
        return (
            self.precision >= 0.70
            and self.recall >= 0.85
            and self.token_efficiency >= 0.60
            and self.latency_ms <= 200
            and self.budget_adherence
        )

def evaluate_scenario(scenario_dir: Path, budget: int = 4000) -> EvalResult:
    """Run a single eval scenario and return metrics."""
    ...

def run_all(corpus_dir: Path, budget: int = 4000) -> list[EvalResult]:
    """Run all scenarios in corpus."""
    ...

def compare_runs(baseline: list[EvalResult], current: list[EvalResult]) -> dict:
    """Compare two eval runs, flag regressions."""
    ...

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Context Engine Eval")
    parser.add_argument("--scenario", type=str, default=None)
    parser.add_argument("--budget", type=int, default=4000)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "CURRENT"))
    args = parser.parse_args()
    ...
```

## CI Integration

### GitHub Actions (`.github/workflows/eval.yml`)

```yaml
name: Context Engine Eval
on:
  pull_request:
    paths:
      - 'code_review_graph/relevance.py'
      - 'code_review_graph/budget.py'
      - 'code_review_graph/context_assembler.py'
      - 'code_review_graph/weight_tuner.py'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run python tests/eval/run_eval.py --format json > eval_current.json
      - run: |
          # Compare against baseline
          uv run python tests/eval/run_eval.py \
            --compare tests/eval/baseline.json eval_current.json
      - uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: eval_current.json
```

## Regression Detection

A regression is flagged when:
- Any primary metric drops below threshold
- Any primary metric drops > 5% from baseline
- A previously-passing scenario now fails

## Phase-Specific Eval Criteria

| Phase | Added Metrics |
|-------|--------------|
| Phase 1 | Precision, recall, budget adherence, latency |
| Phase 2 | Summary quality score (ROUGE-L vs reference), convention accuracy |
| Phase 3 | Event latency (time from fs change to SSE delivery) ≤ 100ms |
| Phase 4 | Cross-repo coverage, contract break detection rate |
| Phase 5 | Weight convergence (Δ < 0.01 after 100 events), prediction accuracy |

## Creating New Eval Scenarios

1. Pick a real repo state (or use fixture)
2. Define a query/task in `query.txt`
3. Manually annotate ideal context in `expected.json`
4. Run `uv run python tests/eval/run_eval.py --scenario <name>` to verify
5. Add to corpus, commit, update baseline

## Baseline Management

```bash
# Generate new baseline after intentional improvements
uv run python tests/eval/run_eval.py --format json > tests/eval/baseline.json
git add tests/eval/baseline.json
git commit -m "eval: update baseline after Phase N improvements"
```
