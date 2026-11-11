# TASK M5-LITE-01 — Simplified Multi-Agent Orchestration

## Metadata

- Milestone: M5
- Status: DONE
- Priority: P1
- Dependencies: M5-08
- Estimated Complexity: M
- Related Modules: agents, api, M4 tools; existing M6 input adapter

## Objective

Nhánh M5 Lite đơn giản: Supervisor → Specialist(s) → candidate findings → M6.
Owner giao ngày11/11/2026; baseline main `a7da263`. Giữ mặc định legacy và local edits.

## Context

Task Owner cung cấp trong phiên triển khai; M7 Lite đã đóng. Đọc current-status,
contracts M5/M6 và boundaries/architecture/data-contracts có liên quan.

## Inputs

Artifacts BBS có thật đã lưu, Financial Tools/EF-EG và Gateway hiện có.
Company/document/snapshot/scope từ context tin cậy; không lấy identity do LLM đoán.
Tối đa4 live Gemini calls,20.000known tokens; usageunknown không là0. Không retry429/503.

## Outputs

- Flag `m5_lite=False`, chạy cùng `m7_lite=True`.
- Supervisor plan ngắn, dispatch độc lập, findings giữ citations/proofs và chuyển M6.
- Nhóm targeted tests và runner offline/live/replay có giới hạn.
- Một [báo cáo](../../../docs/m5-lite-01-simplified-orchestration.md), traces local ignored.

## Allowed Changes

Module M5 Lite mới; integration tối thiểu financial QA/request; tests/runner;
registry/dashboard/current-status, checker ID và thêm test Lite vào CI trọng tâm.

## Out of Scope

Không sửa nghiệp vụ M6/M7/M1–M4, thêm agent role, OCR, dataset hoặc live benchmark.
Không PlannerProposal/DAG/coverage gates, Adaptive Judge, revision/replan trong nhánh Lite.
Candidate không được ACCEPT hoặc ghi Ledger/M7 trước M6. Không task FIX tiếp theo.

## Implementation Steps

1. Kiểm tra baseline/local và đọc có mục tiêu.
2. Tái sử dụng tools, evidence selection/calculation/candidate contracts và native adapter.
3. Targeted offline + real BBS smoke; một lượt live tối đa4calls; replay không network khi cần.
4. Một implementation commit/push main nếu checks đạt; xác minh CI exactSHA, dừng REVIEW.

## Acceptance Criteria

- [x] Supervisor lập một plan ngắn và chọn Specialist thực có; không gọi tất cả mặc định.
- [x] Nhiều Specialist dùng tools thật; giữ source references/calculation proofs.
- [x] Hỗ trợ partial, lỗi độc lập, JSON fallback; không revision loop.
- [x] Candidate findings chuyển native M6 input, không bypass verification/admission.
- [x] Legacy default giữ nguyên; flag tương thích M7 Lite.
- [x] Có offline tests, BBS smoke và live evidence trong4calls; phân biệt original/replay.
- [x] Owner/Tech Lead nghiệm thu ngày11/11/2026, giữ giới hạn live/M6 đã báo; CI không thay chất lượng tài chính.

## Required Tests

4 Lite controls;15 legacy orchestration/pipeline controls. Real BBS A/B offline,
một native M6/Ledger/M7 smoke; live4calls và replay responses đã lưu.
Ruff, planning checker, diff checks và exact staged-tree validation.

## Risks and Blockers

Live B Profitability HTTP503; không retry. Original A numeric shorthand bị reject;
final parser giữ đúng backend candidate khi replay, chưa live lại sau sửa.
Không tuyên bố E2E live hoặc mọi nhận định được M6 chấp nhận.

## Implementation Evidence

Implementation SHA: `9a6aaac9a60a4dc2b000bd4f0e86bce875cf3295`, đã push main đúng một commit.
[CI42942089012](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42942089012)
SUCCESS exactSHA: Python3.12/Web smoke. SHA/CI receipt cập nhật local sau commit.
Local BBS original/live/replay và checks ghi tại report; Owner/Tech Lead APPROVED ngày11/11/2026.
Phiên chuyển DONE chỉ cập nhật planning; không chạy lại Gemini/tests/CI, không tạo task FIX.

## Handoff Notes

Next action: chờ Owner giao nhiệm vụ mới.
