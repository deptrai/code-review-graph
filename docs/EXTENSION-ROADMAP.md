# Extension Roadmap — chainlens/code-review-graph fork

## Upstream base: tirth8205/code-review-graph v2.3.6 (schema v9)
## Fork version: 2.5.0 (schema v11)
## Branch: develop
## Path: /Users/luisphan/Documents/chainlens/code-review-graph

## Status (2026-06-10)
- ✅ Phase 1 (v2.4.0): Git lineage — churn, co-change, hotspots, authors
- ✅ Phase 2 (v2.4.1): Body indexing — full code bodies in embeddings
- ✅ Phase 3 (v2.4.2): Search quality — camelCase/snake FTS tokenization
- ✅ Phase 4 (v2.4.3): NestJS + Go flow detection (+ parser decorator fix)
- ✅ Phase 5 (v2.5.0): Cross-repo dependency impact (name-based, on-demand)

All phases e2e-tested. 2 pre-existing bugs found+fixed via real-repo testing:
lineage co-change path matching, parser decorator persistence.

---

## Phân tích gaps cần extend (không conflict upstream roadmap)

Upstream planned: GitHub App mode, team sync, performance >50k files.
Những gì chúng ta build: git lineage, body indexing, better search, JS/Go flows.

---

## Phase 1: Git Lineage Layer (v2.4.0)
**Gap:** Upstream dùng git diff chỉ để detect changed files. Không có historical signals.
**Value:** Augment Context Engine feature quan trọng nhất. Improve risk scoring + reviewer suggestion.

### Migration v10 — git_lineage table
```sql
CREATE TABLE IF NOT EXISTS git_lineage (
    file_path TEXT NOT NULL,
    commit_count INTEGER DEFAULT 0,      -- total commits touching this file
    churn_90d INTEGER DEFAULT 0,          -- commits in last 90 days
    last_commit_sha TEXT,
    last_commit_at REAL,
    authors TEXT DEFAULT '[]',            -- JSON array of top authors
    co_changed_files TEXT DEFAULT '[]',  -- JSON array of frequently co-changed files
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lineage_file ON git_lineage(file_path);
CREATE INDEX IF NOT EXISTS idx_lineage_churn ON git_lineage(churn_90d DESC);
```

### New edge type: CO_CHANGES
Files thường được changed cùng nhau trong cùng commit → edge CO_CHANGES với weight = co-occurrence count.
```
git log --name-only --format="%H" → group files per commit → count co-occurrences → insert CO_CHANGES edges
```

### New module: code_review_graph/lineage.py
```python
def compute_file_lineage(repo_root: Path, file_path: str, days: int = 90) -> dict:
    """Run git log to extract churn, authors, co-change patterns."""
    # git log --follow --format="%H|%ae|%at" -- file_path
    # Returns: {commit_count, churn_90d, last_commit_sha, authors, co_changed}

def build_lineage_index(repo_root: Path, store: GraphStore) -> int:
    """Build full lineage index for all tracked files."""

def update_lineage_for_files(repo_root: Path, store: GraphStore, files: list[str]) -> int:
    """Incremental update - only files that changed."""
```

### Updated compute_risk_score
Add churn signal (up to 0.15 weight):
```python
# Git churn signal (cap 0.15)
lineage = store.get_file_lineage(node.file_path)
if lineage:
    churn_score = min(lineage.churn_90d / 20.0, 1.0) * 0.15
    score += churn_score
```

### New MCP tools (via tools/ wrapper)
- `get_file_lineage_tool` — git history for a file: commits, authors, co-changes
- `get_hotspot_files_tool` — files with highest churn_90d (likely risky to change)
- `get_co_change_suggestions_tool` — given changed file, suggest other files to review

---

## Phase 2: Body Indexing (v2.4.1)
**Gap:** NodeInfo không có body field. Embeddings chỉ trên signatures (~10 tokens/node).
**Value:** Semantic search recall sẽ tăng đáng kể khi embed actual code.

### Migration v11 — add body column to nodes
```sql
ALTER TABLE nodes ADD COLUMN body TEXT;  -- raw source code of the node
```

### Update NodeInfo (parser.py)
```python
@dataclass
class NodeInfo:
    # ... existing fields ...
    body: Optional[str] = None  # raw source code body (functions/classes only)
```

### Update _node_to_text (embeddings.py)
```python
def _node_to_text(node: GraphNode) -> str:
    parts = [...]  # existing signature-based parts
    # Add body summary for richer semantic signal
    if node.body and len(node.body) < 2000:
        # Truncate very long bodies, keep first 500 chars
        body_preview = node.body[:500].replace("
", " ")
        parts.append(body_preview)
    return " ".join(parts)
```

### Update parser extraction
For Function/Class nodes: extract source text from tree-sitter node.
```python
# In extract_function_node():
body = source_bytes[ts_node.start_byte:ts_node.end_byte].decode("utf-8", errors="replace")
return NodeInfo(..., body=body)
```

### Size considerations
- Average function body: ~500 chars
- 10k functions × 500 chars = 5MB — acceptable for SQLite
- Truncate at 2000 chars max per node
- Body stored in DB, but embeddings still use truncated version

---

## Phase 3: Better Search Quality (v2.4.2)
**Gap:** Keyword MRR = 0.35 (documented weakness). Express queries → 0 hits.
**Value:** Closes the biggest documented gap in upstream.

### Fix 1: camelCase / module-pattern tokenization
Express uses patterns like `app.get`, `router.use` — FTS5 tokenizer splits on `.` but not camelCase.
```python
# In rebuild_fts_index(): expand tokens
def _expand_tokens(text: str) -> str:
    # "getUserById" → "getUserById get User By Id"
    # "app.get" → "app.get app get"
    import re
    camel = re.sub(r'([A-Z])', r' ', text)
    dotted = text.replace('.', ' ')
    return f"{text} {camel} {dotted}"
```

### Fix 2: Query expansion for code terms
```python
# In hybrid_search(): before FTS5 query
CODE_SYNONYMS = {
    "handler": ["handler", "route", "controller", "endpoint"],
    "middleware": ["middleware", "interceptor", "hook"],
    "auth": ["auth", "authentication", "authorize", "token", "jwt"],
}
def expand_query(query: str) -> str:
    for term, synonyms in CODE_SYNONYMS.items():
        if term in query.lower():
            query = query + " " + " ".join(synonyms)
    return query
```

### Fix 3: Cross-encoder reranking (optional, requires sentence-transformers)
```python
# After RRF merge, rerank top-20 with cross-encoder
from sentence_transformers import CrossEncoder
_cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank_results(query: str, candidates: list[dict]) -> list[dict]:
    pairs = [(query, c["name"] + " " + c.get("signature", "")) for c in candidates]
    scores = _cross_encoder.predict(pairs)
    return sorted(zip(scores, candidates), reverse=True)
```

---

## Phase 4: JS/Go Flow Detection (v2.4.3)
**Gap:** Flow detection 33% recall — only works well on Python. JS/Go needs framework patterns.
**Value:** Closes documented gap; upstream acknowledged but not in roadmap.

### Express.js patterns
```python
# In flows.py: add Express patterns
EXPRESS_PATTERNS = [
    # app.METHOD(path, handler)
    r"app\.(get|post|put|delete|patch|use)\s*\(",
    # router.METHOD(path, handler)
    r"router\.(get|post|put|delete|patch|use)\s*\(",
    # express.Router()
    r"express\.Router\s*\(",
]
```

### NestJS patterns
```python
NESTJS_PATTERNS = [
    "@Controller", "@Get", "@Post", "@Put", "@Delete", "@Patch",
    "@Injectable", "@Module", "@Guard", "@Interceptor",
]
```

### Gin (Go) patterns
```python
GIN_PATTERNS = [
    r"r\.(GET|POST|PUT|DELETE|PATCH|Use)\s*\(",
    r"gin\.New\s*\(", r"gin\.Default\s*\(",
    r"func.*gin\.Context\s*\)",
]
```

---

## Không làm (preserve upstream compatibility)

- Không thay đổi MCP tool names hay interfaces hiện có
- Không break schema v1-v9 migrations
- Không thay đổi NodeInfo/EdgeInfo fields hiện có (chỉ ADD optional fields)
- Không thay đổi FastMCP server registration pattern
- Không thêm required dependencies mới (chỉ optional extras)

---

## Git branching strategy

```
main          ← upstream sync (git fetch upstream; git merge upstream/main)
develop       ← integration branch
  └── feat/git-lineage     (Phase 1)
  └── feat/body-indexing   (Phase 2)
  └── feat/search-quality  (Phase 3)
  └── feat/flow-js-go      (Phase 4)
```

Sync upstream periodically:
```bash
git fetch upstream
git checkout main && git merge upstream/main
git checkout develop && git rebase main
```

---

## Version plan

| Version | Phase | New modules |
|---------|-------|-------------|
| 2.4.0 | Git lineage + churn | lineage.py, migration v10, 3 new MCP tools |
| 2.4.1 | Body indexing | parser.py update, migration v11, embeddings.py update |
| 2.4.2 | Search quality | search.py fixes (tokenization, query expansion) |
| 2.4.3 | JS/Go flows | flows.py framework patterns |
| 2.5.0 | Cross-repo unified graph | registry.py cross-edge support |
