"""Cross-repo dependency impact analysis (Phase 5, v2.5.0).

On-demand, name-based cross-repo impact: given a symbol changed in one
registered repo, find which OTHER registered repos import or reference it.

Design (preserves zero-index moat):
- NO persisted cross-DB edges. Each repo keeps its own graph.db.
- Matching is name-based (symbol name + qualified name suffix), the same
  philosophy as the rest of the lexical engine — no global symbol resolution.
- Uses the existing Registry + per-repo GraphStore. Read-only.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .registry import Registry

logger = logging.getLogger(__name__)


def _bare_name(symbol: str) -> str:
    """Return the last dotted/qualified component of a symbol name."""
    s = symbol.strip()
    # Strip call-style parens and trailing punctuation
    s = s.split("(")[0].strip()
    for sep in (".", "::", "/"):
        if sep in s:
            s = s.split(sep)[-1]
    return s


def find_cross_repo_dependents(
    symbol: str,
    source_repo_path: str,
    registry: "Registry",
    limit_per_repo: int = 10,
) -> dict[str, Any]:
    """Find registered repos (other than source) that reference *symbol*.

    Args:
        symbol: Symbol name (bare or qualified) changed in the source repo.
        source_repo_path: Absolute path of the repo where the change is.
        registry: Registry instance listing candidate repos.
        limit_per_repo: Max matches to report per dependent repo.

    Returns:
        Dict with ``symbol``, ``source_repo``, ``dependents`` (list), and
        ``repos_scanned``. Each dependent: {repo, repo_path, matches[]}.
    """
    from .graph import GraphStore
    from .incremental import get_db_path
    from .search import hybrid_search

    bare = _bare_name(symbol)
    if len(bare) < 3:
        return {
            "symbol": symbol,
            "source_repo": source_repo_path,
            "dependents": [],
            "repos_scanned": 0,
            "note": "symbol too short for reliable name matching (min 3 chars)",
        }

    src_resolved = str(Path(source_repo_path).resolve())
    dependents: list[dict[str, Any]] = []
    scanned = 0

    for entry in registry.list_repos():
        repo_path = entry["path"]
        if str(Path(repo_path).resolve()) == src_resolved:
            continue  # skip the source repo itself

        db_path = get_db_path(Path(repo_path))
        if not db_path.exists():
            continue

        try:
            store = GraphStore(str(db_path))
            try:
                matches = _scan_repo_for_symbol(store, bare, limit_per_repo)
                scanned += 1
                if matches:
                    dependents.append({
                        "repo": entry.get("alias", Path(repo_path).name),
                        "repo_path": repo_path,
                        "match_count": len(matches),
                        "matches": matches,
                    })
            finally:
                store.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("cross-repo scan failed for %s: %s", repo_path, exc)

    return {
        "symbol": symbol,
        "bare_name": bare,
        "source_repo": source_repo_path,
        "dependents": dependents,
        "repos_scanned": scanned,
    }


def _scan_repo_for_symbol(
    store: Any,
    bare: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Scan one repo's graph for references to *bare* symbol name.

    Two signals (name-based, no resolution):
    1. IMPORTS_FROM edges whose target name matches the symbol.
    2. CALLS edges whose target name matches the symbol.

    Returns up to *limit* match dicts.
    """
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()

    for edge_kind in ("IMPORTS_FROM", "CALLS"):
        try:
            edges = store.search_edges_by_target_name(bare, kind=edge_kind)
        except Exception:
            edges = []
        for e in edges:
            key = f"{e.source_qualified}|{edge_kind}|{e.file_path}:{e.line}"
            if key in seen:
                continue
            seen.add(key)
            matches.append({
                "via": edge_kind,
                "source": e.source_qualified,
                "file": e.file_path,
                "line": e.line,
            })
            if len(matches) >= limit:
                return matches

    return matches
