# TASK M7-ANSWER-01 — Grounded Natural Answer Generation

## Metadata

- Milestone: M7
- Status: DONE
- Priority: P1
- Dependencies: M7-LITE-02, M6-PY-01
- Estimated Complexity: S

## Objective

Sinh câu trả lời tiếng Việt mạch lạc, có citations từ verified claims và goal
bindings M6/Ledger, phản ánh đúng coverage đầy đủ hoặc partial.

## Context

Owner giao17/11/2026, cho phép commit/push main. Baseline remote `fcd0675`;
worktree riêng giữ nguyên local edits có trước. Tái sử dụng M7 Lite.

## Inputs

Câu hỏi gốc, saved M5/M6/Ledger thật trên JSON/EF-EG; Qwen qua Gateway hiện có.
Credentials chỉ trong environment, không vào trace hoặc Git.

## Outputs

M7 natural segments có claim IDs; backend gắn citations và missing goals;
targeted controls, live trace riêng, implementation SHA và REVIEW handoff.

## Allowed Changes

M7 Lite, targeted tests, runner replay M7 và planning/report tối thiểu.

## Out of Scope

Không đổi M5/M6/Ledger, ACCEPT hoặc goal binding; không thêm agent/pipeline;
không OCR/Gemini/PDF/fullCI, không triển khai E2E-ARCH-02.

## Implementation Steps

1. Cung cấp câu hỏi/claims/coverage/bindings/citations qua Gateway.
2. Phát hành prose có claim IDs, giữ kiểm tra số và citation projection hiện có.
3. Dùng saved Ledger cho2–3câu hỏi, tối đa3Qwen calls, không retry tối ưu văn.
4. Kiểm targeted/planning/diff, commit/push main và bàn giao REVIEW.

## Acceptance Criteria

- [x] Qwen tạo câu trả lời tiếng Việt tự nhiên trên câu hỏi thật.
- [x] Có ca full và partial, không thay coverage/bindings/ACCEPT.
- [x] Giữ exact source bindings, không thêm số liệu hoặc kết luận ngoài Ledger trong mẫu đã audit.
- [x] Tối đa3Qwen calls, targeted checks đạt; implementation SHA/live trace được ghi.

## Required Tests

Ba controls tổng hợp/citations, partial/unbound và số liệu/citation sai;
M7 compatibility và live M7-only replay trên saved Ledger thật.

## Risks and Blockers

Kiểm số không chứng minh ngữ nghĩa của paraphrase. Audit thủ công mẫu live;
không thêm verifier M7 hoặc suy accuracy tổng quát. Giữ caveats JSON-only/page-level.

## Implementation Evidence

Owner xác nhận **M7-ANSWER-01 DONE ngày17/11/2026**. Nghiệm thu implementation
và evidence tại bàn giao `0d6daf1`, đã push main và xác minh remote SHA; giữ nguyên
các giới hạn dưới đây. Phiên đóng chỉ cập nhật tài liệu/tracking và kiểm
planning/diff/Git, không sửa runtime hoặc chạy lại tests/API.

Implementation `5414b699e63758270d80cc36390ecc6eb7149134`;
[report](../../../docs/m7-answer-01-live-validation.md).3actual Qwen calls/24442tokens,
0retry/unknown.2full/1partial;30references/6exact bindings, coverage nguyên M6.
Ca partial có unsupported number đã chặn; final giữ các câu hợp lệ bằng cùng
numeric guard. Exact saved-response replay3ca/0API calls; không fresh final Qwen.
28targeted PASS;185runtime/24JSON hashes bất biến, Ruff/planning/diff đạt.
Giữ giới hạn semantic paraphrase, JSON-only và G2/G3 chưa verified; không fullCI/PDF.

## Handoff Notes

Next action: chờ Owner/Tech Lead giao nhiệm vụ tiếp theo.
