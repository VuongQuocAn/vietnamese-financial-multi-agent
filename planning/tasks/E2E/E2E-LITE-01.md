# TASK E2E-LITE-01 — Real-Data End-to-End Validation of Multi-Agent Lite

## Metadata

- Milestone: E2E
- Status: REVIEW
- Priority: P1
- Dependencies: M5-LITE-01, M6-LITE-01, M7-LITE-02
- Estimated Complexity: S

## Objective

Kiểm chứng tích hợp M5 Lite → M6 Lite → Ledger → M7 Lite bằng dữ liệu BBS thật.

## Context

Owner giao 11/11/2026; baseline e72f867. Giữ local edits; import runtime từ Git archive riêng.

## Inputs

Catalog BBS2025 và cột so sánh2024 đã duyệt; tám câu hỏi cố định trong runner, Q8 hai lượt.

## Outputs

[Report](../../../docs/e2e-lite-01-real-data-validation.md); runner scripts/evaluate_e2e_lite.py;
artifacts ignored artifacts/evidence/E2E-LITE-01/: oracle, freeze, results, Ledger, receipts.

## Allowed Changes

Runner/tests, một vòng sửa tích hợp nhỏ nếu cần, CI web path filter, planning/report.
Owner cho phép tối đa một implementation commit/push main khi checks đạt.

## Out of Scope

Không OCR/rebuild/re-extraction, kiến trúc mới, M8, Web local, full regression hoặc task FIX.

## Implementation Steps

1. Freeze câu hỏi/oracle và runtime.
2. Một lượt offline8cases/9turns, persist/reload Ledger.
3. Chẩn đoán và tối đa một vòng sửa tích hợp, targeted offline nếu sửa.
4. Live Q3/Q6, tối đa8calls tổng/25000known tokens, không retry.
5. Báo cáo nội dung, tests và REVIEW.

## Acceptance Criteria

- Có trace tích hợp ba flags true, phân biệt fresh/cached/replay.
- Có câu trả lời nguyên văn, source IDs, đánh giá/root cause từng câu.
- Có Ledger fresh/reload và receipts live/usage unknown.
- Bảo toàn nguồn/local edits; CI Agent-only không chạy Web; dừng REVIEW.

## Required Tests

Targeted runner/integration tests, Ruff, planning checker, git diff --check; không full suite.

## Risks and Blockers

Chất lượng reasoning đánh giá từ câu trả lời và provenance, không từ smoke PASS.

## Implementation Evidence

- Implementation SHA: chưa commit; runtime e72f867d05f25d14f1c46cb5ee1ae6480a6b7146.
- Main Changes: runner tách runtime/local edits, CI filter.
- Test Results: offline8cases/9turns; live6calls/6203known tokens/2unknown503;47numeric/148citation variants không mismatch;12+19targeted PASS.
- Review Notes: NOT READY; một sửa M7 selection; replay14/15findings. Chờ Tech Lead, không tự nghiệm thu DONE.

## Handoff Notes

Next action: Tech Lead review evidence và quyết định remediation P1.
