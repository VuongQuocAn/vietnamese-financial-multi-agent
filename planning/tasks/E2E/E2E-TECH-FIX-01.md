# TASK E2E-TECH-FIX-01 — Loại bỏ lỗi implementation trước Benchmark

## Metadata

- Milestone: E2E
- Status: REVIEW
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
[Báo cáo và giới hạn](../../../docs/e2e-tech-fix-01-live.md).

## Allowed Changes

Chuẩn hóa cấu trúc tool request không đổi lựa chọn của LLM; cân đối cap demand
với context 24K; sửa binding/mapping nếu xác nhận lỗi code.

## Out of Scope

Refactor M5/M6/M7, agent/framework/guard/fallback mới, nới ACCEPT, EF-EG,
corpus/Gold/model/Colab, regex/hardcode thay suy luận, full CI, gate9/Pilot45.
HTTP 524 ghi riêng; không retry probes hoặc mở FIX theo accuracy.

## Acceptance Criteria

- [x] Lỗi kỹ thuật đã xử lý hoặc phân loại rõ bằng trace/offline evidence.
- [x] Đúng ba live probes, mỗi probe một lượt; báo calls/tokens và giới hạn.
- [x] Commit/push main, xác minh SHA, giữ local edits và bàn giao REVIEW.

## Implementation Steps

Phân tích saved traces; sửa parser/cap; kiểm offline và freeze SHA; tối đa ba
probes một lượt, báo lỗi còn lại rồi dừng runtime để chuyển Pilot 45.

## Required Tests

Targeted parser/budget/binding controls; smoke M5–Tools–M6/M7 liên quan.
Ruff, planning checker và git diff --check; không full CI.

## Risks and Blockers

HTTP 524 thuộc endpoint; lượt mới 0/18. Facts NR-0006 thiếu unit/scale trong
corpus pin. Qwen còn chọn nguồn/kind/query hoặc evidence IDs sai; không sửa
logic để tăng accuracy. Mapping ô bảng cuối chỉ offline verified, chưa fresh live.

## Implementation Evidence

Implementation cuối `6b181024135bc252abe1f07e45a419e48a01f6e1`; ba probes trên
`a8db198acd43212edf9f98c0e297ee5dd9fa73bf`. Sửa cấu trúc use_graph, cap demand
2.500/context24K và mapping UnderstoodCell.col. 8 targeted PASS trước live,
6 targeted PASS sau mapping và exact saved-search replay không AttributeError.
18 calls/82.749 tokens, 18 HTTP200, 0 thiếu usage; MH-0006 partial/7 citations,
SH-0001 M6/M7/6 citations; SH-0013 live internal_error được sửa mapping offline,
còn model không tạo claim. 190 runtime blobs và pins/local edits đã xác minh.
Không lặp probe, không full CI/gate9/Pilot45 hoặc thay corpus/Gold/model/Colab.

## Handoff Notes

Next action — Tech Lead review runtime đã freeze để chuyển Pilot 45, chấm theo
Gold/rubric ViFinBench; không tiếp tục FIX nhằm tăng accuracy.
