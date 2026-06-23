---
project_name: code-review-graph
date: 2026-06-12
stepsCompleted: ['document-discovery', 'prd-analysis', 'epic-coverage', 'ux-alignment', 'epic-quality', 'final-assessment']
documentsIncluded:
  prd: '_bmad-output/planning-artifacts/prd.md -> docs/specs/PRD-context-engine.md'
  architecture: '_bmad-output/planning-artifacts/architecture.md -> docs/specs/ARCHITECTURE-context-engine.md'
  epics: '_bmad-output/planning-artifacts/epics.md -> docs/specs/EPIC-context-engine.md'
  ux: 'NONE (backend/MCP project — UX not applicable)'
  supporting:
    - 'eval-framework.md -> docs/specs/EVAL-framework.md'
    - 'spec-phase1-relevance-budget.md'
    - 'spec-phase2-llm-knowledge.md'
    - 'spec-phase3-realtime-push.md'
    - 'spec-phase4-multi-repo.md'
    - 'spec-phase5-predictive-learning.md'
---

# Implementation Readiness Assessment Report

**Date:** 2026-06-12
**Project:** code-review-graph (Context Engine Evolution — CE-EPIC-001)

## Document Inventory

| Loại | File (qua symlink) | Nguồn canonical | Kích thước | Trạng thái |
|------|--------------------|-----------------|------------|------------|
| PRD | `prd.md` | `docs/specs/PRD-context-engine.md` | 3.2 KB | ✅ Found |
| Architecture | `architecture.md` | `docs/specs/ARCHITECTURE-context-engine.md` | 11.6 KB | ✅ Found |
| Epics & Stories | `epics.md` | `docs/specs/EPIC-context-engine.md` | 10.0 KB | ✅ Found |
| UX Design | — | — | — | ⚠️ Không có (N/A cho project backend/MCP) |
| Eval Framework | `eval-framework.md` | `docs/specs/EVAL-framework.md` | — | ✅ Supporting |
| Phase Specs (5) | `spec-phase1..5-*.md` | 5 SPEC phase | — | ✅ Supporting |

**Duplicates:** Không có (không tồn tại đồng thời whole + sharded).
**Sharded docs:** Không có.
**Note:** Tất cả file trong `planning-artifacts/` là symlink relative trỏ về `docs/specs/` (nguồn canonical đã commit). Một nguồn sự thật duy nhất.

## Assessment Sections

_(Điền ở các bước tiếp: PRD analysis → Architecture → Epics/Stories alignment → Final readiness verdict)_

---

## PRD Analysis

> ⚠️ **Lưu ý dạng PRD:** Đây là PRD kiểu *vision/phase-based*, KHÔNG đánh số FR/NFR tường minh. Tôi suy ra (derive) requirements từ Problem Statement (các gap ❌), Success Criteria và Constraints, đánh số để truy vết coverage ở bước Epic.

### Functional Requirements (derived)

- **FR1 — Relevance ranking:** Thay flat BFS dumps bằng scored/ranked context (gap ❌ "Relevance ranking").
- **FR2 — Token budgeting:** Dynamic budget-aware context assembly (gap ❌ "Token budgeting").
- **FR3 — LLM knowledge layer:** Commit summaries + convention extraction/learning (gap ❌ "LLM knowledge").
- **FR4 — External source integration:** ≥4 connectors (Jira/Linear/GitHub Issues/Notion) (gap ❌ "External sources").
- **FR5 — Cross-service flow tracing:** Multi-repo flow stitching, đạt 3 hops (gap ❌ "Cross-service flows").
- **FR6 — Enterprise scale:** Sharding + permissions, hỗ trợ 1M+ nodes (gap ❌ "Enterprise scale").
- **FR7 — Real-time push:** SSE events, indexing sub-100ms (Phase 3 deliverable).
- **FR8 — LLM judge eval:** Khung đánh giá chất lượng context (Phase 6 + EVAL-framework).

**Total FRs (derived): 8**

### Non-Functional Requirements (derived)

- **NFR1 — Backward compatibility:** Mọi MCP tool signature hiện có KHÔNG đổi.
- **NFR2 — Optional/gated:** Tính năng mới gate sau env vars; `detail_level="minimal"` bypass toàn bộ logic mới.
- **NFR3 — Local-first:** Không phụ thuộc cloud bắt buộc.
- **NFR4 — Graceful degradation:** LLM features fallback khi chưa cấu hình; LLM không bao giờ block MCP response (cache + async).
- **NFR5 — Python 3.10+ compat:** Giữ tương thích hiện tại.
- **NFR6 — Performance targets:** ≥20% giảm token ở cùng recall; +10% impact F1; ≥25% cải thiện theo LLM judge.
- **NFR7 — Scale resilience:** WAL + sharding chống SQLite contention; backoff + offline cache cho external API.

**Total NFRs (derived): 7**

### Additional Requirements / Constraints

- **Dependencies mới (optional extras):** `httpx>=0.27,<1` (Phase 4), `duckdb>=0.10,<1` (Phase 6). Hiện có: Tree-sitter, SQLite, sentence-transformers.
- **Non-Goals (ngoài phạm vi):** thay LSP IDE-native; CI/CD pipeline; real-time collab editing; GUI/web dashboard (VS Code ext giữ riêng).
- **6 Phase** với duration ước tính (tổng ~21 tuần).

### PRD Completeness Assessment (sơ bộ)

- ✅ Vision, target users, success metrics định lượng rõ.
- ✅ Constraints + non-goals + risks + mitigation đầy đủ.
- ⚠️ **Không có FR/NFR đánh số gốc** → traceability phải dựa trên derived IDs (rủi ro: epic có thể không map 1-1 với gap).
- ⚠️ **PRD liệt kê 6 Phase** nhưng thư mục specs chỉ có **5 SPEC phase** (phase1–5). Phase 6 "Enterprise Scale" trong PRD **chưa có** file SPEC riêng → cần kiểm ở bước Epic coverage.

---

## Epic Coverage Validation

### Epic FR Coverage (extracted)

Epic doc (CE-EPIC-001) phân rã 6 Epic / 23 story / 129 points. KHÔNG có "FR Coverage Map" tường minh — tôi map theo chủ đề với derived FR từ PRD:

| Derived FR | Epic | Story | Status |
|-----------|------|-------|--------|
| FR1 Relevance ranking | CE-E1 | S1, S3 | ✅ Covered |
| FR2 Token budgeting | CE-E1 | S2 | ✅ Covered |
| FR3 LLM knowledge layer | CE-E2 | S1–S4 | ✅ Covered |
| FR4 External source integ. | CE-E4 | S1–S3 | ✅ Covered |
| FR5 Cross-service flow trace | CE-E4 S4 + SPEC-phase4 | — | ⚠️ Covered nhưng LỆCH (xem dưới) |
| FR6 Enterprise scale | CE-E6 | S1–S3 | ✅ Covered |
| FR7 Real-time push | CE-E3 | S1–S3 | ✅ Covered |
| FR8 LLM judge eval | CE-E6 S4 + EVAL-framework | — | ✅ Covered |
| NFR1 Backward compat | CE-E1 | S4 + AC | ✅ Covered |
| NFR4 Graceful degradation | CE-E2 | S4 + AC | ✅ Covered |

### ⚠️ Phát hiện CRITICAL — Lệch ánh xạ PRD ↔ Epic ↔ SPEC

Có sự hoán đổi/trộn chủ đề giữa 3 tài liệu ở Phase 4/5:

| Nguồn | Phase/Epic 4 | Phase/Epic 5 |
|-------|-------------|-------------|
| **PRD** | External Source Integration | Cross-Service Flow Tracing |
| **EPIC doc** | CE-E4 = External Source Integration | CE-E5 = Predictive Learning + Self-Tuning |
| **SPEC file** | SPEC-phase4 = **Multi-Repo Intelligence** | SPEC-phase5 = **Predictive Context & Self-Learning** |

**Hệ quả:**
1. **CE-E4 trỏ sai spec:** Epic CE-E4 ("External Source Integration") tham chiếu `SPEC-phase4-multi-repo.md` — nhưng spec đó nói về **cross-repo intelligence**, KHÔNG phải external connectors. → AC "≥4 connectors (Jira/Linear/GitHub/Notion)" KHÔNG có spec kỹ thuật tương ứng.
2. **CE-E5 "Predictive Learning"** xuất hiện trong Epic + SPEC-phase5, nhưng **KHÔNG có trong danh sách 6 phase của PRD** (PRD Phase 5 = Cross-Service Flow Tracing).
3. **"Cross-Service Flow Tracing" (PRD Phase 5 / FR5)** thực chất được hiện thực ở SPEC-phase4 (multi-repo) + CE-E4-S4 — bị tách rời khỏi nhãn Epic.
4. **CE-E6 "Enterprise Scale"** có Spec = **TBD** (chưa có file). PRD Phase 6 cũng không có SPEC riêng.

### Coverage Statistics

- Total derived PRD FRs: **8** (+ 7 NFR)
- FRs có epic coverage: **8/8** (100% về chủ đề)
- FRs có coverage SẠCH (đúng spec, đúng nhãn): **6/8** (FR4 + FR5 bị lệch spec)
- Epics thiếu Spec file: **1** (CE-E6 → TBD)
- **Verdict sơ bộ:** Coverage đầy đủ về chủ đề, NHƯNG có **2 vấn đề traceability** (lệch ánh xạ E4/E5, thiếu spec E6) cần giải quyết trước khi Sprint Planning để tránh dev hiểu sai phạm vi.

---

## UX Alignment Assessment

### UX Document Status

**Not Found — và KHÔNG áp dụng (N/A).**

### Đánh giá

- code-review-graph là **MCP server + CLI** (backend), không có UI người dùng.
- PRD mục **Non-Goals** nêu rõ: *"GUI/web dashboard (VS Code extension stays separate)"* và *"Replacing IDE-native LSP features"*. → Không có user journey/UI cần validate.
- "User-facing" duy nhất là MCP tool output (text/JSON), đã được quản trị qua các AC về token budget & backward-compat ở CE-E1.

### Warnings

- Không có. Thiếu UX doc ở đây là **đúng kỳ vọng**, KHÔNG tính là gap readiness.

---

## Epic Quality Review

Đánh giá 6 Epic / 23 story / 129 points theo chuẩn create-epics-and-stories.

### A. User Value Focus

| Epic | Tiêu đề | User value? | Nhận xét |
|------|---------|-------------|----------|
| CE-E1 | Relevance Ranking + Token Budget | ✅ | Stories viết đúng "As a developer... I want... so that..." |
| CE-E2 | LLM Knowledge Layer | ✅ | Value rõ (hiểu commit, học convention) |
| CE-E3 | Real-Time Push | ✅ | Value: context luôn current, no lag |
| CE-E4 | External Source Integration | ✅ | Value: business context |
| CE-E5 | Predictive Learning | ✅ | Value: tool tốt dần theo thời gian |
| CE-E6 | Enterprise Scale | 🟡 | Hơi thiên kỹ thuật (sharding, DuckDB) nhưng có user persona (enterprise admin) → chấp nhận được |

→ **Không có epic nào là pure technical milestone.** Tất cả có user story + so-that. Tốt.

### B. Epic Independence & Dependency (🔴 vấn đề chính)

Dependency graph khai báo:
```
CE-E1 → blocks {E2,E3,E4,E5,E6}
CE-E2,E3,E4 → CE-E5 → CE-E6
```

🔴 **CRITICAL — Forward dependency / fan-in lớn ở CE-E5:** CE-E5 "Depends On: CE-E2, CE-E3, CE-E4" (3 epic cùng lúc). Predictive Learning không thể bắt đầu cho tới khi E2+E3+E4 đều xong → chuỗi tới hạn dài (3+3+2+4 tuần tuần tự trước khi E5). Đây là **anti-pattern "big-bang integration"**, làm chậm việc giao giá trị từng phần.
- **Khuyến nghị:** Tách CE-E5 thành phần lõi (self-tuning relevance — chỉ cần E1) ship sớm, và phần phụ thuộc external/realtime (pre-fetch dùng E3/E4) ship sau. Hiện gộp chung khiến E5 bị chặn không cần thiết.

🟡 **CE-E1 là single point of dependency:** mọi epic đều bị E1 block. Đúng về mặt foundation, nhưng nghĩa là **E1 phải hoàn hảo trước khi bất cứ thứ gì khác chạy** — rủi ro nếu E1 trượt lịch.

### C. Story Sizing

- 🟡 **CE-E6-S1 = 13 points** ("1M+ node repos"). Quá lớn cho một story đơn → nên tách (sharding storage / query optimization / benchmark riêng).
- 🟡 **Nhiều story 8 points** (E2-S2, E4-S1, E4-S4, E5-S1, E5-S3). Ở ranh giới nên cân nhắc chẻ nhỏ khi vào Sprint Planning.
- ✅ Story E1, E3 sizing hợp lý (2–5 points).

### D. Acceptance Criteria

- ✅ **AC định lượng, testable, mạnh:** "≥20% token reduction", "<100ms re-parse", "weight convergence within 50 queries", "p95 <500ms at 1M nodes". Đây là điểm sáng — đo được, có ngưỡng rõ.
- 🟠 **AC KHÔNG theo Given/When/Then (BDD):** chúng ở dạng checklist tuyên bố. Chấp nhận được cho dự án backend, nhưng một số AC còn mơ hồ về điều kiện kích hoạt (vd "Convention extraction identifies ≥3 patterns per community" — community nào, đo lúc nào?).
- 🟠 **Thiếu AC cho error/edge path** ở vài epic: E3 có "graceful shutdown" nhưng E2/E4 thiếu AC cho lỗi LLM/API timeout (dù risk registry có nêu).

### E. Brownfield Indicators

- ✅ Đây là brownfield (codebase code-review-graph đã tồn tại). Epic có **compatibility stories đúng cách**: CE-E1-S4 (backward-compat `detail_level="minimal"`), CE-E2-S4 (fallback no-LLM).
- ✅ **DB tables tạo khi cần:** CE-E1 AC nêu "Migration v11 creates relevance_cache" — tạo theo nhu cầu từng phase, không dồn upfront. Tốt.
- 🟡 **Không có story "setup" đầu tiên** — hợp lý vì brownfield, nhưng Sprint Planning nên thêm 1 spike/story chuẩn bị (env vars, feature-flag scaffolding) trước CE-E1-S1.

### Best-Practices Compliance Checklist (toàn epic)

- [x] Epic delivers user value (E6 borderline nhưng pass)
- [~] Epic độc lập — **CE-E5 vi phạm** (fan-in E2+E3+E4)
- [~] Story sizing — **CE-E6-S1 (13) quá lớn**, vài story 8pt cần để ý
- [x] No forward dependency (trừ vấn đề fan-in E5 ở trên)
- [x] DB tables tạo khi cần (migration theo phase)
- [x] AC rõ ràng & định lượng (nhưng thiếu BDD + error-path)
- [~] Traceability tới FR — **lệch ánh xạ E4/E5 ↔ SPEC** (đã nêu ở Epic Coverage)

### Findings theo severity

🔴 **Critical**
1. **Lệch ánh xạ PRD↔Epic↔SPEC ở Phase 4/5** (CE-E4 trỏ sai `SPEC-phase4-multi-repo.md`; "Cross-Service Flow Tracing" của PRD bị thất lạc nhãn; "Predictive Learning" không có trong 6 phase PRD).
2. **CE-E6 thiếu Spec** (`Spec: TBD`).

🟠 **Major**
3. **CE-E5 fan-in dependency** (E2+E3+E4) → big-bang integration, nên tách.
4. **CE-E6-S1 (13pt)** quá lớn, cần chẻ.
5. **Thiếu AC error/edge-path** cho E2/E4 (LLM/API failure).

🟡 **Minor**
6. AC chưa theo BDD Given/When/Then.
7. Chưa có setup/spike story trước CE-E1-S1 (feature-flag scaffolding).
8. Vài story 8pt ở ranh giới sizing.

---

## Summary and Recommendations

### Overall Readiness Status

🟠 **NEEDS WORK** — Kế hoạch chất lượng cao về nội dung, nhưng có **2 vấn đề traceability Critical** phải sửa trước khi Sprint Planning. KHÔNG phải "NOT READY" (không thiếu requirement lớn), nhưng cũng chưa "READY" (lệch ánh xạ sẽ khiến dev hiểu sai phạm vi).

### Điểm mạnh (đáng ghi nhận)

- ✅ PRD vision rõ, success metric **định lượng** (token −20%, F1 +10%, 1M nodes...).
- ✅ Epic có user value thật, story đúng format, AC **đo được** với ngưỡng cụ thể.
- ✅ Backward-compat & graceful-degradation được nhúng làm AC (E1-S4, E2-S4) — đúng kiểu brownfield.
- ✅ Quality gates rõ ràng (test/lint/mypy/migration/eval) ở cuối Epic doc.
- ✅ Coverage 8/8 derived FR về mặt chủ đề.

### Critical Issues Requiring Immediate Action

1. 🔴 **Lệch ánh xạ PRD ↔ Epic ↔ SPEC ở Phase 4/5.**
   - CE-E4 "External Source Integration" trỏ `SPEC-phase4-multi-repo.md` (spec về cross-repo, KHÔNG phải connectors) → AC "≥4 connectors" không có spec kỹ thuật.
   - "Cross-Service Flow Tracing" (PRD Phase 5 / FR5) bị thất lạc nhãn.
   - "Predictive Learning" (CE-E5/SPEC-phase5) không nằm trong 6 phase của PRD.
2. 🔴 **CE-E6 "Enterprise Scale" thiếu Spec** (`Spec: TBD`) — không thể lập story chi tiết khi chưa có spec kỹ thuật.

### Major Issues

3. 🟠 **CE-E5 fan-in dependency** (cần E2+E3+E4 xong mới chạy) → big-bang integration, nên tách phần self-tuning lõi (chỉ cần E1) ship sớm.
4. 🟠 **CE-E6-S1 (13 points)** quá lớn → chẻ thành sharding / query-opt / benchmark.
5. 🟠 **Thiếu AC error/edge-path** cho E2 (LLM timeout) và E4 (API failure).

### Recommended Next Steps

1. **Hợp nhất nhãn Phase 4/5** giữa PRD, Epic, SPEC: quyết định thứ tự chuẩn (đề xuất: P4 = Multi-Repo/Cross-Service như SPEC-phase4; P5 = Predictive Learning; External-Source thành phase/epic riêng hoặc gộp vào P4 connectors) rồi sửa cả 3 tài liệu cho khớp. Đây là sửa tài liệu, rẻ.
2. **Viết `SPEC-phase6-enterprise-scale.md`** hoặc hạ CE-E6 xuống "future/out-of-scope cho đợt này" để Sprint Planning không cần nó.
3. **Tách CE-E5** thành E5a (self-tuning, depends E1) + E5b (pre-fetch, depends E3/E4) để giải phóng critical path.
4. **Bổ sung AC error-path** cho E2/E4 dựa trên Risk Registry đã có.
5. Sau khi sửa 1–2: **chạy Sprint Planning `[SP]`** bắt đầu từ **CE-E1** (P0, không phụ thuộc gì, spec đầy đủ — sẵn sàng làm ngay bất kể các vấn đề trên).

### Lưu ý quan trọng về thứ tự thực thi

**CE-E1 (Relevance + Budget) đã SẴN SÀNG 100%** — P0, không dependency, spec `SPEC-phase1-relevance-budget.md` đầy đủ, AC đo được. Các vấn đề Critical/Major ở trên đều thuộc Phase 4/5/6 (downstream). → Có thể **bắt đầu sprint CE-E1 ngay** song song với việc sửa tài liệu phase sau.

### Final Note

Đánh giá này tìm thấy **8 issue** trên **3 nhóm** (2 Critical, 3 Major, 3 Minor). Các issue Critical đều ở downstream phases — KHÔNG chặn việc khởi động CE-E1. Khuyến nghị: sửa nhãn Phase 4/5 (rẻ, nhanh) + quyết định số phận CE-E6, rồi Sprint Planning bắt đầu từ CE-E1.

---

**Assessor:** Kiro (BMAD Implementation Readiness workflow)
**Date:** 2026-06-12
**Documents assessed:** PRD, Architecture, Epics (+ 5 phase specs, eval framework) — tất cả qua symlink về `docs/specs/`
