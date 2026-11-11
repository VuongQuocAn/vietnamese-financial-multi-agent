# TASK CORE-PERIOD-01 — Fix Comparative Period Verification in Financial QA

## Metadata

- Milestone: CORE
- Status: REVIEW
- Priority: P1
- Dependencies: EF-CORE-03
- Estimated Complexity: S

## Objective

Kiểm chứng và phát hành phép so sánh nhiều kỳ hợp lệ, giữ chặn trộn kỳ sai.

## Context

Owner giao ngày 11/11/2026; baseline 1fb2e39 trên main. EF-CORE-03 được nghiệm thu
có điều kiện; Q5/C3 còn giới hạn kỳ. Giữ evidence cũ.

## Inputs

Spec Owner đầy đủ lưu ignored artifacts/evidence/CORE-PERIOD-01/owner-task.md;
traces Q5-C/Q5-C-exact/C3-C, CORE-FLOW-01 Q5 và canonical BBS đã chuẩn bị.

## Outputs

Báo cáo docs/core-period-01-comparative-period-verification.md; raw evidence
trong artifacts/evidence/CORE-PERIOD-01/ (ignored).

## Allowed Changes

Request binding, M6 period validation, targeted tests, planning/checker/CI;
M7 chỉ nếu mất claim ACCEPT trực tiếp cản mục tiêu. Commit/push main và xác minh CI.

## Out of Scope

Không OCR/extraction, thay canonical/raw/processed, Graph, agent mới, period engine,
M8, Llama/Qwen, benchmark diện rộng hoặc local edits ngoài task.

## Implementation Steps

Truy vết request/claim/operand periods; sửa tối thiểu; offline controls/replay;
chạy một fresh lượt L1–L5 qua Gateway hiện có; đối chiếu oracle; commit/push/CI.

## Acceptance Criteria

- [ ] Root cause và trước/sau đúng trace thật.
- [ ] Comparative hợp lệ ACCEPT; exact date và identity/provenance guards giữ nguyên.
- [ ] Sai hướng/mẫu số/nguồn/kỳ bị chặn; metrics và candidate isolation không regression.
- [ ] Fresh Gemini/raw M7 cho L1–L5, phân biệt verification và answer completeness.
- [ ] Targeted checks và CI đúng implementation SHA PASS; chờ Tech Lead nghiệm thu.

## Required Tests

T1–T8 theo spec Owner; targeted tests trước live. L1 Q5, L2 explicit comparative,
L3 C3, L4 exact fact 31/12/2025, L5 B02 cross-year. Không full benchmark.

## Risks and Blockers

Provider errors và generic M5 coverage phải báo riêng; không retry để làm đẹp kết quả.

## Implementation Evidence

Status: **REVIEW**; chưa commit. Request binding + M6 endpoint guards, M7 phục hồi calculation display đã ACCEPT. 82 staged targeted trước M7 +33 final M7 PASS (12 overlap);20 real controls PASS;6 fresh E2E/25 attempts/111680 known tokens/1 unknown. L2 final fresh đủ −8,66%/−14,35%/59,06%;Q5/C3 final M7 offline replay đủ số, runtime vẫn partial;46fact/593citation checks0 mismatch. [Report](../../../docs/core-period-01-comparative-period-verification.md). Next action: Tech Lead review CORE-PERIOD-01 sau CI đúng SHA.

## Handoff Notes

Next action: Tech Lead review CORE-PERIOD-01 sau CI đúng SHA. Chưa tự DONE.
