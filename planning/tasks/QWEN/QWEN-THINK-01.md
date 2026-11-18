# TASK QWEN-THINK-01 — Thinking Validation

## Metadata

- Milestone: QWEN
- Status: REVIEW
- Priority: P1
- Dependencies: E2E-REMED-04
- Estimated Complexity: S

## Objective

Đánh giá Qwen3-8B-AWQ Thinking trên pipeline hiện tại; loại lỗi tích hợp đã biết
để quan sát năng lực thực tế, không thay kiến trúc hoặc hạ chuẩn kiểm chứng.

## Context

Owner giao18/11/2026, cho phép commit/push main. Baseline remote `f6059f1`,
worktree riêng giữ checkout gốc và dependencies REMED01–04. Colab đã bật Thinking.

## Inputs

API Thinking hiện tại; saved traces Non-thinking và cùng corpus REMED04 đã pin.
Ba inputs đã có: MH0001, NR0001, SH0006; Gold chỉ hậu kiểm, không vào runtime.

## Outputs

Adapter nhận final channel; sửa payload/timeout/fallback có giới hạn;3controls,
tối đa3QA thật, receipts/hashes/metrics và báo cáo so với saved traces; REVIEW.

## Allowed Changes

Qwen adapter, request budget, semantic batching giữ đủ evidence, Fusion fallback/
prompt, runner/tests và tracking của task.

## Out of Scope

Không sửa notebook/server/vLLM/model/context24K, không API mới/Non-thinking/OCR/
Gemini/Pilot/Full600/fullCI; không đổi EF-EG/M7, không nới M6/Obligations.

## Implementation Steps

1. Kiểm tra baseline/dependencies và RCA REMED04.
2. Sửa tích hợp tối thiểu, targeted controls và compatibility liên quan.
3. Freeze implementation, tối đa3QA/30calls tổng/10calls mỗi QA/300s chung,
   timeout stage180s/output8192 opt-in; không retry/tuning loops.
4. Hậu kiểm Gold/citations, so saved traces, ghi khác biệt và REVIEW, push main.

## Acceptance Criteria

- [x] Không ép Non-thinking; reasoning không thành final output/JSON.
- [x] Payload giữ nguồn/dependency, budget chung và fallback giữ công việc/quan hệ.
- [x] Targeted controls và đúng3QA thật; không vượt giới hạn task.
- [x] Báo accuracy/coverage/latency/tokens/calls/lỗi, nêu giới hạn so sánh.
- [x] Evidence/dataset/local edits nguyên trạng, commit/push main, REVIEW.

## Required Tests

3controls mới, adapter/REMED04/obligations/fusion compatibility; saved trace/real
JSON live integration tối đa3QA. Ruff, planning checker, diff check; không fullCI.

## Risks and Blockers

N=3 là probe, không benchmark accuracy hoặc readiness; JSON-only chưa PDF-verified.
Thinking/output/timeouts và fallback/batching khác baseline nên không A/B tuyệt đối.
Một claim riêng vượt48K vẫn chặn; không cắt evidence để đạt cap.

## Implementation Evidence

Implementation `80ffc468ad3a40c8eca859fb8f19da3f273e4aac`,189runtime Git blobs đã
xác minh.37unique targeted PASS,1legacy FAIL (`operand_bindings`) tái hiện đúng
baseline f6059f1. [Report](../../../docs/qwen-think-01-thinking-validation.md):
3QA/11calls, accuracy/coverage0% (saved33,33%),0citations;79.813known tokens/
1unknown,716,230s.10HTTP200 có inline Thinking;M6 timeout/invalid JSON và retrieval
miss vẫn chặn đáp án.264JSON/115pins/3Pilot/272parent/80local hashes bất biến;
Ruff/planning/diff đạt. Không retest/Non-thinking/Gemini/OCR/fullCI.
REVIEW chờ nghiệm thu; không coi negative probe là readiness hoặc DONE.

## Handoff Notes

Next action: Tech Lead review probe âm tính, regression NR và giới hạn budget/routing trước khi giao việc tiếp theo.
