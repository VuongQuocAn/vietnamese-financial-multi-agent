# TASK E2E-TECH-FIX-01 — Loại bỏ lỗi implementation trước Benchmark

## Metadata

- Milestone: E2E
- Status: IN_PROGRESS
- Priority: P1
- Dependencies: QWEN-THINK-01
- Estimated Complexity: S

## Objective

Sửa tối thiểu lỗi kỹ thuật đã xác nhận qua saved traces gate: tool request,
demand token budget và evidence binding. LLM giữ quyền chọn nghĩa/công cụ;
Python thực thi, quản lý dữ liệu và provenance.

## Inputs

Trace E2E-GATE-09, runtime baseline `3a08371`, corpus pin và 9-QA manifest cũ.
Owner giao task ngày 18/11/2026 dù gate đang REVIEW; cho phép commit/push main.
Worktree riêng bảo toàn local edits checkout gốc.

## Context

Gate là input nghiên cứu đang REVIEW, không tự đổi DONE. Dependency triển khai
QWEN-THINK-01 đã DONE; Owner cho phép bắt đầu task sửa kỹ thuật từ traces gate.

## Outputs

Runtime sửa nhỏ, targeted offline tests và báo cáo tối đa ba live probes một lượt.

## Allowed Changes

Chuẩn hóa cấu trúc tool request không đổi lựa chọn của LLM; cân đối cap demand
với context 24K; sửa binding/mapping nếu xác nhận lỗi code.

## Out of Scope

Refactor M5/M6/M7, agent/framework/guard/fallback mới, nới ACCEPT, EF-EG,
corpus/Gold/model/Colab, regex/hardcode thay suy luận, full CI, gate9/Pilot45.
HTTP 524 ghi riêng; không retry probes hoặc mở FIX theo accuracy.

## Acceptance Criteria

- [ ] Lỗi kỹ thuật đã xử lý hoặc phân loại rõ bằng trace/offline evidence.
- [ ] Tối đa ba live probes, mỗi probe một lượt; báo calls/tokens và giới hạn.
- [ ] Commit/push main, xác minh SHA, giữ local edits và bàn giao REVIEW.

## Implementation Steps

Phân tích saved traces; sửa parser/cap; kiểm offline và freeze SHA; tối đa ba
probes một lượt, báo lỗi còn lại rồi dừng runtime để chuyển Pilot 45.

## Required Tests

Targeted parser/budget/binding controls; smoke M5–Tools–M6/M7 liên quan.
Ruff, planning checker và git diff --check; không full CI.

## Risks and Blockers

HTTP 524 thuộc endpoint; thiếu unit/scale và lựa chọn nguồn/suy luận Qwen vẫn
có thể làm abstain. Không sửa logic để tăng accuracy.

## Implementation Evidence

Chưa commit. 8 targeted offline controls PASS; chưa chạy live.

## Handoff Notes

Next action — hoàn tất offline validation rồi chạy tối đa ba live probes.
