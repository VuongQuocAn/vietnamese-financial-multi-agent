# TASK PERF-01 — Fast Path Optimization

## Metadata

- Milestone: PERF
- Status: IN_PROGRESS
- Priority: P1
- Dependencies: GEN-02, GEN-02-Fix-A, GEN-02-Fix-B
- Estimated Complexity: S

## Objective

Giảm latency QA bằng tối đa hai tối ưu được profiling xác nhận; giữ nguyên semantics.

## Context

Owner giao ngày09/11/2026, baseline `8478c98`. GEN-02/Fix-B DONE có giới hạn;
H08 chưa activation, PDF30 quarantine. Giữ pending GEN-01a/Web.

## Inputs

Sáu câu persisted GEN-02: D01/D05/D17/D22/D18/D23; approved sources và ledger
QA-01b sao chép riêng. Yêu cầu đầy đủ trong attachment Owner; không sửa frozen inputs.

## Outputs

`docs/perf-01-fast-path-optimization.md`; local `artifacts/evidence/PERF-01/`:
baseline, bottleneck-analysis, after, comparison, traces và focused safety results.

## Allowed Changes

Profiling, tối đa hai bottlenecks, focused tests, planning/report; commit/push main
và xác minh một CI đúng implementation SHA theo yêu cầu Owner.

## Out of Scope

Gemini live/OCR, full40 QA, H08 activation, Web, M8, infrastructure/cache service;
không đổi financial logic, source-quality/M6/Ledger/Firewall policy.

## Implementation Steps

Baseline → chọn bottleneck → tối đa hai vòng sửa/test → final paired measurement
→ report/implementation commit/push/CI → REVIEW.

## Acceptance Criteria

- [x] Baseline và after cùng sáu QA, nguồn, seed ledger, policy và modes.
- [x] Tối đa hai bottlenecks có số liệu; báo cả chậm hơn/limitations.
- [x] Semantics, identities, verification/citations/Firewall không hồi quy.
- [x] H08/PDF30, cache invalidation, mismatch và17legacy replay đạt.
- [ ] Focused regression và CI đúng implementation SHA đạt; giữ pending changes.

## Required Tests

Focused changed modules, source-quality/snapshot/cache/ledger controls, planning/diff.

## Risks and Blockers

Mẫu nhỏ offline không đại diện provider latency hoặc M8 financial accuracy.

## Implementation Evidence

Chưa commit;99focused PASS,12payloads tương đương,13entries exact;17legacy replay;
source loading median giảm72,3%, force-refresh median chậm14,3%, cache-hit median
giảm2,8%. Không đạt mục tiêu tổng thể. [Report](../../../docs/perf-01-fast-path-optimization.md).

## Handoff Notes

Next action: xác minh CI đúng implementation SHA rồi chuyển REVIEW cho Tech Lead.
