# TASK E2E-STABILIZE-01 — Ổn định Pipeline để chạy Benchmark

## Metadata

- Milestone: E2E
- Status: IN_PROGRESS
- Priority: P1
- Dependencies: QWEN-THINK-01
- Estimated Complexity: S

## Objective

Kết thúc lỗi kỹ thuật đã biết khiến pipeline không trả lời dù có dữ liệu/suy luận
hợp lệ; kết thúc chuỗi REMED, bàn giao Tech Lead quyết định Pilot45.

## Context

Owner giao18/11/2026, cho phép commit/push main. Baseline remote `bdf2fd7`;
worktree riêng bảo toàn checkout gốc/local edits. Đọc RCA/traces REMED01–04 và THINK.

## Inputs

9QA cố định từ manifest baseline-nine E2E-VAL-01; corpus đã pin THINK/REMED04,
Qwen Thinking hiện tại qua Gateway; Gold chỉ hậu kiểm, không vào runtime.

## Outputs

Sửa M5/routing/M6/payload tối thiểu,3controls và compatibility liên quan;
đúng9QA một lần trên cùng runtime/corpus; traces/receipts và report ngắn, REVIEW.

## Allowed Changes

M5 planner/coordinator, document retrieval/source projection hiện có, M6 xử lý
verdict/budget, runner/tests và tracking/report task.

## Out of Scope

Không thêm agent/framework/kiến trúc, sửa Colab/server/model/context24K/raw/EF-EG/
Gold/M7/Obligations hoặc nới ACCEPT; không OCR/Gemini/fullCI/36Pilot/Full600.

## Implementation Steps

1. Replay saved traces; sửa lỗi tổng quát, không hardcode QA/company/answer.
2. Targeted controls, freeze runtime; một run9QA, cap90calls/10mỗi QA/retries0.
3. Nếu live lộ lỗi payload đơn giản: giữ lượt dở, sửa một lần rồi final9QA;
   tổng cap90calls gồm cả lượt dở. Hậu kiểm accuracy/coverage/latency/tokens/traces;
   commit/push main và REVIEW. Không vòng FIX vô hạn sau live.

## Acceptance Criteria

- [ ] Mục tiêu/dependencies/phân công không mất qua planning/fallback.
- [ ] Routing tới dữ liệu hiện hữu, giữ provenance và M6 kiểm lại nguồn.
- [ ] JSON/verdict thiếu/timeout không xóa proof đã verified; không tự ACCEPT.
- [ ] Đúng9QA/runtime/corpus, agent/tool traces và metrics; không ngưỡng accuracy.
- [ ] Báo lỗi phức tạp còn lại; implementation SHA/commit/push verified, REVIEW.

## Required Tests

3controls mới; Thinking/REMED04/obligations/document/coordinator compatibility,
saved traces/real-JSON replay và9QA integration. Ruff/planning/diff; không fullCI.

## Risks and Blockers

Thinking có thể thiếu verdict/binding hoặc reasoning chưa đủ; abstain hợp lệ được
chấp nhận. Timeout chung client600s/câu, stage180s, output8192 như THINK; không đổi
model/context/server; output base8192 được clamp theo ước lượng chars/2 và reserve1024.
Missing-verdict repair tối đa1, không retry timeout. Một lượt dở15attempts được giữ
riêng vì HTTP400/payload. Lượt sau29attempts lộ lỗi model chép sai hash claim
lặp lại; thêm exact wire handles C1/C2, không nới identity matching. Tổng44attempts
trước final, còn46calls tối đa trong cap90; giữ các lượt dở, không sửa sau final9QA.

## Implementation Evidence

Chưa commit; đang targeted validation. Evidence local riêng E2E-STABILIZE-01.

## Handoff Notes

Next action: hoàn tất targeted validation và chạy9QA đã cố định.
