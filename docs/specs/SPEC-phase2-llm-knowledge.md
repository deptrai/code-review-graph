# Technical Spec: Phase 2 — LLM Knowledge Layer

## Overview

Add LLM-generated knowledge (commit summaries, convention extraction) to enrich context beyond structural analysis. All LLM calls are offline/async — never in MCP hot path.

## Components

### 2a. LLM Provider Abstraction (`code_review_graph/llm.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class LLMConfig:
    provider: str  # "openai", "anthropic", "local"
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.0

class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, prompt: str, system: str = "") -> str: ...
    
    @abstractmethod
    async def complete_json(self, prompt: str, schema: dict, system: str = "") -> dict: ...

class OpenAIProvider(LLMProvider): ...
class AnthropicProvider(LLMProvider): ...

def get_llm_provider() -> Optional[LLMProvider]:
    """Return configured provider or None if unconfigured."""
    provider = os.environ.get("CRG_LLM_PROVIDER")
    if not provider:
        return None
    ...
```

**Env vars:**
- `CRG_LLM_PROVIDER` — "openai" | "anthropic" | "local"
- `CRG_LLM_MODEL` — model name
- `CRG_LLM_API_KEY` — API key
- `CRG_LLM_BASE_URL` — custom endpoint (optional)

### 2b. Commit Summarizer (`code_review_graph/summarizer.py`)

```python
@dataclass
class CommitSummary:
    commit_range: str         # "abc123..def456"
    summary: str              # 1-3 sentence summary
    key_changes: list[str]    # bullet points
    affected_domains: list[str]  # community names
    generated_at: float

async def summarize_commit_window(
    repo_root: str,
    since: str = "7 days ago",
    llm: Optional[LLMProvider] = None,
) -> Optional[CommitSummary]:
    """Summarize recent commits. Returns None if no LLM configured."""
    ...

async def batch_summarize(
    repo_root: str,
    window_size: int = 20,
    llm: Optional[LLMProvider] = None,
) -> list[CommitSummary]:
    """Summarize commit history in sliding windows."""
    ...
```

### 2c. Convention Extractor (`code_review_graph/conventions.py`)

```python
@dataclass
class Convention:
    category: str        # "naming", "error_handling", "testing", "imports", "architecture"
    rule: str            # human-readable rule
    confidence: float    # 0-1
    evidence: list[str]  # file paths supporting this
    generated_at: float

async def extract_conventions(
    repo_root: str,
    sample_files: list[str],
    llm: Optional[LLMProvider] = None,
) -> list[Convention]:
    """Extract coding conventions from sample files."""
    ...

def get_conventions(db_path: str) -> list[Convention]:
    """Read cached conventions from DB."""
    ...
```

### 2d. Migration v12

```sql
CREATE TABLE IF NOT EXISTS commit_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_range TEXT NOT NULL UNIQUE,
    summary TEXT NOT NULL,
    key_changes TEXT NOT NULL,  -- JSON array
    affected_domains TEXT NOT NULL,  -- JSON array
    generated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS conventions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    rule TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence TEXT NOT NULL,  -- JSON array
    generated_at REAL NOT NULL,
    UNIQUE(category, rule)
);
```

## Integration

- `tools/review.py` → inject relevant commit summaries into context
- `wiki.py` → use LLM to enrich community descriptions
- Convention data available via new tool `get_conventions_tool`

## Testing

```
tests/test_llm.py:
  - test_provider_factory_returns_none_when_unconfigured
  - test_openai_provider_complete (mocked)
  - test_anthropic_provider_complete (mocked)

tests/test_summarizer.py:
  - test_summarize_commit_window (mocked LLM)
  - test_batch_summarize_sliding_window
  - test_returns_none_without_llm

tests/test_conventions.py:
  - test_extract_conventions (mocked LLM)
  - test_get_conventions_from_db
  - test_confidence_filtering
```

## Graceful Degradation

When `CRG_LLM_PROVIDER` is unset:
- All LLM functions return `None` or empty lists
- No errors raised
- Context assembly works exactly as Phase 1
- Wiki generation falls back to template-based summaries
