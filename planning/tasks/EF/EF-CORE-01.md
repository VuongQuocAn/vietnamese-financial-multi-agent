# TASK EF-CORE-01 — Integrate EF-EG into the Multi-Agent Financial QA Pipeline

## Metadata

- Milestone: EF
- Status: IN_PROGRESS
- Priority: P1
- Dependencies: CORE-FLOW-01, EF-01
- Estimated Complexity: M

## Objective

Tích hợp EF-EG vào M5 Lite, chứng minh đóng góp bằng Gemini live trên BBS thật.

## Context

Owner giao ngày 11/11/2026; baseline `0f6165546d2db7a130fbcca666d0e2abf95b7649`.
Tái sử dụng graph hiện có, không thêm Graph Agent hoặc đổi trách nhiệm M5/M6/M7.

## Inputs

Catalog đã pin, approved EF-01 compositions, BBS 2025 persisted và task Owner đính kèm.

## Outputs

Graph-aware M5, targeted tests, runner và báo cáo
`docs/ef-core-01-graph-aware-multi-agent-integration.md`; raw traces ignored.

## Allowed Changes

Graph facade/catalog mode, Lite orchestration/bundle, QA wiring/flag, tests,
evaluation và planning liên quan.

## Out of Scope

Không đổi M6/M7 nếu không có lỗi tương thích; không OCR/extraction, causal edges,
graph database, M8 hoặc EF-CORE-02. Giữ local edits ngoài task.

## Implementation Steps

Kiểm tra integration; ánh xạ identity; bounded traversal; compact Specialist context;
M6/M7 gốc; offline → Gemini live G1–G6 → controlled ON/OFF 2–3 câu.

## Acceptance Criteria

- [x] Graph retrieval, starting identity, citations/quality đúng trên PDF thật.
- [x] Specialist sử dụng graph, M6 kiểm chứng, M7 phát hành ACCEPT.
- [x] Negative controls và controlled Graph ON/OFF.
- [ ] Tests/Ruff/planning/CI đúng SHA, report trung thực; REVIEW không tự DONE.

## Required Tests

Ba targeted controls, M5/composition compatibility; BBS offline và Gemini live G1–G6.

## Risks and Blockers

Graph có thể không bổ sung thông tin; contextual relation không chứng minh semantic
support. Không giả replay thành live hoặc accuracy tài chính toàn hệ thống.

## Implementation Evidence

Chưa commit; [báo cáo](../../../docs/ef-core-01-graph-aware-multi-agent-integration.md).
49 targeted PASS; G2/G4 graph→analysis ACCEPT→M7; G3/G5 PARTIAL.
83 live logical calls/269220 known tokens/3 unknown HTTP503; 1366 protected unchanged;
33 fact/324 citation/13 metric occurrences audit PASS. Chờ CI đúng implementation SHA.

## Handoff Notes

Next action: commit/push implementation và kiểm tra CI đúng SHA theo Owner.
