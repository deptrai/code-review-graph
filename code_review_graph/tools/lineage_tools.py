"""MCP tool wrappers for git lineage features (Phase 1, v2.4.0)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._common import _get_store


def get_file_lineage_func(
    file_path: str,
    repo_root: str | None = None,
) -> dict[str, Any]:
    """Get git history summary for a specific file.

    Returns commit count, churn (last 90 days), top authors,
    and files frequently changed together (co-change patterns).

    Args:
        file_path: Relative file path to query.
        repo_root: Repository root (auto-detected if omitted).

    Returns:
        Dict with commit_count, churn_90d, authors, co_changed_files,
        last_commit_sha, last_commit_at. Empty dict if not indexed.
    """
    store = _get_store(repo_root)
    lineage = store.get_file_lineage(file_path)
    if not lineage:
        return {
            "file_path": file_path,
            "indexed": False,
            "message": "No lineage data. Run build_lineage_index_tool first.",
        }
    return {**lineage, "indexed": True}


def get_hotspot_files_func(
    limit: int = 20,
    repo_root: str | None = None,
) -> dict[str, Any]:
    """Return files with highest commit churn in the last 90 days.

    High-churn files are frequently modified and carry elevated risk —
    they are more likely to have bugs introduced and merge conflicts.

    Args:
        limit: Maximum files to return (default 20).
        repo_root: Repository root (auto-detected if omitted).

    Returns:
        Dict with hotspots list sorted by churn_90d descending.
    """
    store = _get_store(repo_root)
    hotspots = store.get_hotspot_files(limit=limit)
    if not hotspots:
        return {
            "hotspots": [],
            "message": "No lineage data. Run build_lineage_index_tool first.",
        }
    return {
        "hotspots": hotspots,
        "total": len(hotspots),
        "note": "churn_90d = commits touching this file in last 90 days",
    }


def build_lineage_index_func(
    repo_root: str | None = None,
    days: int = 90,
) -> dict[str, Any]:
    """Build or rebuild the git lineage index.

    Mines git history to populate churn, co-change patterns, and author
    data for all tracked files. Typically takes 5-30 seconds depending
    on repo size and history depth.

    Args:
        repo_root: Repository root (auto-detected if omitted).
        days: Churn window in days (default 90).

    Returns:
        Dict with files_indexed count and status.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    resolved_root = Path(repo_root).resolve() if repo_root else Path.cwd().resolve()
    store = _get_store(repo_root)

    try:
        from ..lineage import build_lineage_index
        count = build_lineage_index(resolved_root, store, days=days)
        return {
            "status": "ok",
            "files_indexed": count,
            "days": days,
            "message": f"Lineage index built for {count} files (churn window: {days}d)",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to build lineage index",
        }
