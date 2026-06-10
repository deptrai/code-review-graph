"""Git lineage analysis for churn, co-change patterns, and author tracking.

Provides on-demand git history mining without requiring a persistent index.
Results are stored in the git_lineage table (migration v10) and used to
augment risk scoring in changes.py.

Usage:
    from code_review_graph.lineage import build_lineage_index
    build_lineage_index(repo_root, store)
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .graph import GraphStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FileLineage:
    """Git history summary for a single file."""
    file_path: str
    commit_count: int = 0
    churn_90d: int = 0
    last_commit_sha: str = ""
    last_commit_at: float = 0.0
    authors: list[str] = field(default_factory=list)
    co_changed_files: list[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run_git(args: list[str], repo_root: Path) -> str:
    """Run a git command and return stdout. Returns '' on error."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.debug("git %s failed: %s", " ".join(args), result.stderr.strip())
            return ""
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("git command failed: %s", e)
        return ""


def _cutoff_timestamp(days: int = 90) -> float:
    """Unix timestamp for N days ago."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()

# ---------------------------------------------------------------------------
# Per-file lineage computation
# ---------------------------------------------------------------------------

def compute_file_lineage(
    repo_root: Path,
    file_path: str,
    days: int = 90,
    max_co_change: int = 10,
) -> FileLineage:
    """Compute git history metrics for a single file.

    Args:
        repo_root: Repository root directory.
        file_path: Relative file path.
        days: Window for churn calculation (default 90 days).
        max_co_change: Max co-changed files to track per file.

    Returns:
        FileLineage with commit_count, churn_90d, authors, co_changed_files.
    """
    lineage = FileLineage(file_path=file_path)

    # --- All-time commit count + last commit + authors ---
    log_out = _run_git(
        ["log", "--follow", "--format=%H|%ae|%at", "--", file_path],
        repo_root,
    )
    if not log_out.strip():
        return lineage

    cutoff = _cutoff_timestamp(days)
    author_counter: Counter[str] = Counter()

    for line in log_out.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 3:
            continue
        sha, author, ts_str = parts[0], parts[1], parts[2]
        try:
            ts = float(ts_str)
        except ValueError:
            continue

        lineage.commit_count += 1
        author_counter[author] += 1

        if lineage.last_commit_sha == "":
            lineage.last_commit_sha = sha
            lineage.last_commit_at = ts

        if ts >= cutoff:
            lineage.churn_90d += 1

    # Top 5 authors by commit count
    lineage.authors = [a for a, _ in author_counter.most_common(5)]

    return lineage


def compute_co_changes(
    repo_root: Path,
    files: list[str],
    days: int = 90,
    max_per_file: int = 10,
) -> dict[str, list[str]]:
    """Compute co-change patterns across all tracked files.

    For each file, returns list of other files most frequently committed together.
    Uses a single git log pass for efficiency.

    Args:
        repo_root: Repository root directory.
        files: List of relative file paths to analyze.
        days: Time window for co-change analysis.
        max_per_file: Max co-changed files to return per file.

    Returns:
        Dict mapping file_path → list of co-changed file paths (most frequent first).
    """
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    # Get all commits in window with their changed files
    log_out = _run_git(
        ["log", f"--after={cutoff_date}", "--name-only", "--format=%H", "--diff-filter=AM"],
        repo_root,
    )
    if not log_out.strip():
        return {}

    files_set = set(files)
    # Parse commits: group files per commit SHA
    commits: list[list[str]] = []
    current: list[str] = []
    current_sha = ""

    for line in log_out.strip().splitlines():
        line = line.strip()
        if not line:
            if current:
                commits.append(current)
                current = []
            continue
        # SHA lines are 40 hex chars
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            if current:
                commits.append(current)
            current = []
            current_sha = line
        else:
            if line in files_set:
                current.append(line)

    if current:
        commits.append(current)

    # Count co-occurrences
    co_counts: dict[str, Counter] = defaultdict(Counter)
    for commit_files in commits:
        tracked = [f for f in commit_files if f in files_set]
        for i, fa in enumerate(tracked):
            for fb in tracked:
                if fa != fb:
                    co_counts[fa][fb] += 1

    return {
        fp: [f for f, _ in counter.most_common(max_per_file)]
        for fp, counter in co_counts.items()
    }

# ---------------------------------------------------------------------------
# Index build / update
# ---------------------------------------------------------------------------

def build_lineage_index(
    repo_root: Path,
    store: "GraphStore",
    days: int = 90,
) -> int:
    """Build full git lineage index for all tracked files.

    Args:
        repo_root: Repository root directory.
        store: GraphStore instance (must have git_lineage table via migration v10).
        days: Churn window in days.

    Returns:
        Number of files indexed.
    """
    all_files = store.get_all_files()
    if not all_files:
        logger.info("lineage: no files in graph, skipping")
        return 0

    logger.info("lineage: building index for %d files", len(all_files))

    # Compute co-changes in a single git log pass (efficient)
    co_changes = compute_co_changes(repo_root, all_files, days=days)

    count = 0
    for fp in all_files:
        lineage = compute_file_lineage(repo_root, fp, days=days)
        lineage.co_changed_files = co_changes.get(fp, [])
        store.upsert_file_lineage(lineage)
        count += 1

    logger.info("lineage: indexed %d files", count)
    return count


def update_lineage_for_files(
    repo_root: Path,
    store: "GraphStore",
    files: list[str],
    days: int = 90,
) -> int:
    """Incremental lineage update for a subset of files (e.g. after git diff).

    Args:
        repo_root: Repository root.
        store: GraphStore instance.
        files: List of relative file paths that changed.
        days: Churn window in days.

    Returns:
        Number of files updated.
    """
    if not files:
        return 0

    logger.info("lineage: updating %d changed files", len(files))

    # Re-compute co-changes only for changed files (cheaper than full rebuild)
    all_files = store.get_all_files()
    co_changes = compute_co_changes(repo_root, all_files, days=days)

    count = 0
    for fp in files:
        lineage = compute_file_lineage(repo_root, fp, days=days)
        lineage.co_changed_files = co_changes.get(fp, [])
        store.upsert_file_lineage(lineage)
        count += 1

    logger.info("lineage: updated %d files", count)
    return count
