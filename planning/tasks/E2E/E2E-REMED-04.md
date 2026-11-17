# TASK E2E-REMED-04 — Goal Binding & Document Evidence

## Metadata

- Milestone: E2E
- Status: REVIEW
- Priority: P1
- Dependencies: E2E-REMED-03
- Estimated Complexity: S

## Objective

Sửa liên kết goal/verified claims và tạo candidate có provenance cho bảng
thuyết minh; phân biệt truth ACCEPT với goal support, giữ chốt chặn M6.

## Context

Owner giao17/11/2026, cho phép commit/push main. Baseline52237cf remote;
worktree riêng bảo toàn local edits. MH0001 có3ACCEPT/goal0of4.

## Inputs

Saved traces REMED-03, JSON/projection EF-EG hiện có,9questions-only đã pin
từ E2E-VAL-01. Gold chỉ hậu kiểm, không vào runtime.

## Outputs

Sửa tổng quát,3controls,offline saved replay/real JSON integration,
tối đa2QA Qwen rồi9QA cố định nếu core fix đạt; report/SHA/traces/REVIEW.

## Allowed Changes

Goal resolution/binding, existing Specialist/document candidate contracts và M6
source replay, integration handoff, targeted validation/tracking.

## Out of Scope

Không hardcode Gold/QA/đáp án, nới ACCEPT/Obligations, thêm Agent/đổi kiến trúc,
sửa M7/raw JSON/EF-EG/verified data, OCR/Gemini/fullCI/36Pilot/Full600.

## Implementation Steps

1. RCA traces, alias ambiguity và table route.
2. Sửa goal alternatives và source-bound document candidate/replay.
3. Offline controls/integration; freeze trước live.
4. Retest<=2QA; core còn lỗi thì dừng RCA, nếu đạt chạy9QA cố định.
5. Report accuracy/coverage/citations/latency/calls/limits; commit/push main.

## Acceptance Criteria

- [x] Offline goal replay ghi nhận comparison, không cấp coverage cho scalar.
- [x] Candidate bảng qua M6 replay nguồn/miền/kỳ; Specialist Gateway control đạt.
- [x] Không phát hành từ raw context hoặc kết luận thiếu căn cứ.
- [x] Offline/live bằng chứng và runtime/corpus pin; dừng RCA khi core live chưa đạt.
- [ ] Xác nhận core đạt toàn luồng live: MH vẫn bị planning/payload/timeouts chặn.
- [x] Implementation commit, bàn giao push main/SHA verified; REVIEW chờ Tech Lead.

## Required Tests

3controls và compatibility M6 goal/obligations/document/fusion; offline saved
trace/real JSON integration. Retest<=2QA/20calls tổng/10calls mỗi QA/300s request/
retries0. Nếu đạt core:9QA cố định/90calls cap/cùng runtime và corpus.
Không vòng FIX/retest kéo dài. Ruff/planning/diff.

## Risks and Blockers

JSON-only chưa PDF-verified. Continuation/entity/layout/cột mơ hồ giữ gap;
engineering controls không là financial accuracy benchmark.

## Implementation Evidence

Implementation `bac7362e07a81ca0ab1f3c0812315df72e58a539`;
[report](../../../docs/e2e-remed-04-goal-document.md).47unique PASS/1baseline FAIL,
offline replay/document integration đạt;2QA14calls/103724known tokens/2unknown,
accuracy/coverage50%→50%,7citations,wall559,595s. MH không đạt core live;
không9QA hoặc vòng FIX tiếp. Runtime/source/imported/local/evidence hashes verified.
Next action: Tech Lead review bản sửa và RCA planning/semantic payload/binding analysis.

## Handoff Notes

Registry là nguồn trạng thái chính; chưa nghiệm thu DONE.
