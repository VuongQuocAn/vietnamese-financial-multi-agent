# TASK M5-COORD-03 — Verification-Driven Feedback

## Metadata

- Milestone: M5
- Status: REVIEW
- Priority: P1
- Dependencies: M6-OBL-01
- Estimated Complexity: S

## Objective

Feedback M6 kích hoạt tối đa một lượt sửa task lỗi và các task phụ thuộc;
tái sử dụng nhánh độc lập, đưa candidates sửa qua M6 → Ledger → M7.

## Context

Owner giao ngày17/11/2026, cho phép commit/push main. Baseline remote7cb4a03;
worktree riêng bảo toàn local edits. M6-OBL-01 và M5-COORD-02 DONE.

## Inputs

Structured feedback M6, Adaptive Coordinator/Workspace/Gateway hiện có;
JSON/EF-EG BBS2025 và ADC2021 đã import.

## Outputs

Routing theo task/goal/evidence/action, repair frontier theo DAG, revision2,
reuse M6 histories không đổi, trace trước/sau và báo cáo live giới hạn.

## Allowed Changes

M5 coordinator/workspace, API composition tối thiểu, runner/targeted controls
và planning/report liên quan.

## Out of Scope

Python Agent, sửa M7, kiến trúc mới, OCR/PDF/Gemini, corpus mutation,
full CI/benchmark hoặc task khác.

## Implementation Steps

1. Chọn task nhận feedback và descendant; không gọi lại Supervisor.
2. Revision mới giữ lineage/provenance; M6 quyết định ACCEPT và bindings.
3. Ba controls, ba câu Qwen mới; commit/push main, bàn giao REVIEW.

## Acceptance Criteria

- [x] Phân biệt source/selection/join/formula/goal binding qua feedback hiện có.
- [x] Chỉ thực thi frontier bị ảnh hưởng, giữ nhánh độc lập và M6 history hợp lệ.
- [x] Tối đa một repair/request; không đổi proposal hoặc hết budget thì dừng partial.
- [x] Candidates sửa qua M6/Ledger/M7, không tự cấp ACCEPT hoặc goal support.
- [ ] Targeted controls, live traces, SHA đã xác minh, commit/push main và REVIEW.

## Required Tests

Ba targeted controls routing/reuse/E2E/no-progress/budget; compatibility liên quan.
Ba câu mới và một controlled replay saved M5 để kiểm tra root-cause frontier;
tối đa28actual calls toàn task,16calls/fresh request,8calls/replay. Không lặp
fresh câu hỏi hoặc retry transport; Ruff/planning/diff. Không full CI.

## Risks and Blockers

M6 có thể false-negative; evidence thiếu giữ partial. JSON-only provenance,
không phải PDF-verified hoặc accuracy benchmark. Token usage unknown thì không
mở repair tùy chọn; dùng call/deadline budget chung hiện có.

## Implementation Evidence

Chưa commit; [report](../../../docs/m5-coord-03-live-validation.md).
31targeted PASS trên final runtime.3câu mới+1controlled scalar-fault replay,
20actual calls/178629known tokens/1unknown. Final replay chỉT4 được repair,
3histories reuse; M6 từ3ACCEPT/2ABSTAIN thành4ACCEPT→Ledger v2→M7 partial/18citations.
180runtime hashes khớp receipt controlled replay;57source JSON bất biến.
Natural run trước sửa frontier kéo4tasks và rollback; không gọi positive tự nhiên.
Giữ G3 thiếu, M6 semantic binding G2 false-positive và một smoke deterministic
cũ thiếu binding cũng fail baseline. Không sửa M6 verdict/M7 hoặc chạy full CI.

## Handoff Notes

Next action: Tech Lead review selective-repair evidence và các giới hạn M6/G3 trước nghiệm thu.
