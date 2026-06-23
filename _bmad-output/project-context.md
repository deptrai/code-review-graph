---
project_name: 'code-review-graph'
user_name: 'Luisphan'
date: '2026-06-12'
sections_completed: ['technology_stack']
existing_patterns_found: 0
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

> **Nguồn rule khác (không lặp lại ở đây):** `CLAUDE.md` (conventions + security invariants + session protocol), `AGENTS.md`, `GEMINI.md`, `.mcp.json`. File này chỉ bổ sung các điểm dễ bị bỏ sót khi sinh code.

---

## Technology Stack & Versions

- **Ngôn ngữ:** Python `>=3.10` (target ruff `py310`); CI test ma trận 3.10 / 3.11 / 3.12 / 3.13.
- **Build backend:** `hatchling`. Quản lý môi trường bằng **`uv`** (`uv run ...`, `uv sync`).
- **Lõi runtime deps:** `mcp>=1.0,<2`, `fastmcp>=3.2.4,<4` (vá CVE-2025-62800/62801/66416), `tree-sitter>=0.23,<1`, `tree-sitter-language-pack>=0.3,<1`, `networkx>=3.2,<4`, `watchdog>=4,<6`, `tomli` (chỉ <3.11).
- **Optional extras:** `embeddings` (sentence-transformers, numpy), `google-embeddings`, `communities` (igraph), `eval` (matplotlib, pyyaml), `wiki` (ollama).
- **Lưu trữ:** SQLite (WAL mode) tại `.code-review-graph/graph.db`.
- **Entry points:** `code-review-graph` → `cli:main`, `crg-daemon` → `daemon_cli:main`.
- **Subproject riêng:** `code-review-graph-vscode/` (TypeScript, có `package.json`/`tsconfig.json` riêng).

### Tooling (cấu hình chính xác)
- **ruff:** `line-length = 100`, `select = ["E","F","I","N","W"]`. Per-file ignores: `visualization.py` (E501 vì HTML/JS nhúng), một số fixture.
- **mypy:** `--ignore-missing-imports --no-strict-optional`.
- **bandit:** skip `B101, B404, B603, B607, B608` (assert, subprocess-git, SQL f-string false-positive). Skip này là **chủ ý** — đừng "sửa" code để né warning đã được whitelist.
- **pytest:** `asyncio_mode = "auto"`, `testpaths = ["tests"]`, `norecursedirs = ["tests/fixtures"]`. CI yêu cầu **coverage tối thiểu 65%**.

## Critical Implementation Rules

_Documented after discovery phase — sẽ điền chi tiết ở bước generate (step-02)._
