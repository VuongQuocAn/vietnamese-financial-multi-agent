# TASK E2E-STABILIZE-01 — Ổn định Pipeline để chạy Benchmark

## Metadata

- Milestone: E2E
- Status: REVIEW
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

- [x] Có control giữ mục tiêu/dependencies/roles qua fallback; còn giới hạn semantic planning đã báo.
- [ ] Routing tới dữ liệu hiện hữu, giữ provenance và M6 kiểm lại nguồn.
- [x] JSON/verdict thiếu/timeout có controls giữ proof; unknown handles không tự ACCEPT.
- [ ] 9QA/runtime/corpus chưa hoàn tất; Owner yêu cầu dừng, không chạy bù.
- [x] Báo giới hạn và implementation SHA; bàn giao REVIEW, push/remote verify tại bàn giao.

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

Implementation `7b06babef9cad02c8ad894c3c0adb7f1babd5221`;
[report](../../../docs/e2e-stabilize-01-benchmark-readiness.md).15targeted PASS cuối;
41PASS/2baseline FAIL trước. Owner yêu cầu dừng18/11/2026: không QA/API/FIX thêm.
Tổng59attempts/56responses/325648known tokens/6unknown;3calls ngắt chưa response.
15QA attempts hoàn tất/7IDs; code cuối4/9 (2correct1partial1abstain), không score9QA.
190runtime/264JSON/115pins/3Pilot/80local và parent/prior hashes verified;
63citation/pointer occurrences resolve. Giữ mọi artifacts/lượt dở; không sửa M7/
Obligations/raw/server/model/context. Chưa xác nhận readiness Pilot45; không ngưỡng accuracy.
Chỉ audit offline/Ruff/planning/diff sau stop, không chạy lại tests/model/fullCI.

## Handoff Notes

Owner stop thay yêu cầu chạy đủ9 bằng bàn giao thực tế; giữ phần chưa nghiệm thu.
Không tự DONE, không mở vòng FIX/REMED mới.
Next action: Tech Lead review bàn giao và quyết định Pilot45, không tiếp tục REMED theo từng QA.
