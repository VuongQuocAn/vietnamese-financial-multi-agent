# TASK PERF-01 — Fast Path Optimization

## Metadata

- Milestone: PERF
- Status: DONE
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
- [x] Focused regression và CI đúng implementation SHA đạt; giữ pending changes.

## Required Tests

Focused changed modules, source-quality/snapshot/cache/ledger controls, planning/diff.

## Risks and Blockers

Mẫu nhỏ offline không đại diện provider latency hoặc M8 financial accuracy.
Nghiệm thu có giới hạn: latency chưa được giải quyết; refresh median35,828s và
mixed QA78,349s trong phép đo này. Không mở PERF-01-Fix hoặc vòng tối ưu thứ ba.

## Implementation Evidence

Implementation `de2d430bb59be9539ede5e772470dba8011483c1` đã push main;
[CI42565568084](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42565568084)
SUCCESS đúng SHA (Python3.12/Web; manual full regression SKIPPED).99focused PASS,
12payloads tương đương,13entries exact;17legacy replay/H08/PDF30 blocked.
Source load giảm75,2%, document refresh giảm23,7%, cache-hit giảm23,2%; refresh toàn
nhóm chậm4,5%, ledger query chậm3,5%. Hai baseline lỗi được loại minh bạch; final
policy digest đúng như after. [Report](../../../docs/perf-01-fast-path-optimization.md).

Tech Lead APPROVED ngày09/11/2026, cho phép DONE với giới hạn trên: hai tối ưu đúng
phạm vi, cải thiện source loading/document QA và giữ các kiểm soát quan trọng;
không bắt buộc đạt chỉ tiêu tốc độ bằng mọi giá. Phiên nghiệm thu chỉ cập nhật
planning và chạy planning/diff checks; không chạy lại CI/tests/QA.

## Handoff Notes

Next action: Chờ Owner/Tech Lead giao nhiệm vụ tiếp theo.
