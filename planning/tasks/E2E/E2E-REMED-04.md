# TASK E2E-REMED-04 — Goal Binding & Document Evidence

## Metadata

- Milestone: E2E
- Status: DONE
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
- [x] Owner chấp nhận đóng phạm vi kỹ thuật với giới hạn live được ghi nhận;
  việc xác nhận core đạt toàn luồng live nằm ngoài phạm vi nghiệm thu này.
- [x] Implementation commit, bàn giao push main/SHA verified; Owner/Tech Lead
  chấp nhận kết quả kỹ thuật và đóng task có giới hạn ngày17/11/2026.

## Required Tests

3controls và compatibility M6 goal/obligations/document/fusion; offline saved
trace/real JSON integration. Retest<=2QA/20calls tổng/10calls mỗi QA/300s request/
retries0. Nếu đạt core:9QA cố định/90calls cap/cùng runtime và corpus.
Không vòng FIX/retest kéo dài. Ruff/planning/diff.

## Risks and Blockers

JSON-only chưa PDF-verified. Continuation/entity/layout/cột mơ hồ giữ gap;
engineering controls không là financial accuracy benchmark.
Tiêu chí core đạt toàn luồng live ban đầu chưa đạt: MH vẫn bị planning/payload/
timeouts chặn. Owner chấp nhận đóng phạm vi kỹ thuật với giới hạn này;
không chuyển kết quả chưa đạt thành PASS hoặc xác nhận readiness Pilot.

## Implementation Evidence

Implementation `bac7362e07a81ca0ab1f3c0812315df72e58a539`;
[report](../../../docs/e2e-remed-04-goal-document.md).47unique PASS/1baseline FAIL,
offline replay/document integration đạt;2QA14calls/103724known tokens/2unknown,
accuracy/coverage50%→50%,7citations,wall559,595s. MH không đạt core live;
không9QA hoặc vòng FIX tiếp. Runtime/source/imported/local/evidence hashes verified.
Nghiệm thu kết quả kỹ thuật theo xác nhận Owner/Tech Lead ngày17/11/2026;
giữ toàn bộ RCA và giới hạn live, chưa readiness Pilot. Bàn giao d659971 đã push
main/remote verified. Phiên đóng chỉ tài liệu/tracking và planning/diff/Git;
không sửa runtime/artifacts hoặc chạy lại tests/Qwen/benchmark/CI.
Next action: chờ Owner/Tech Lead giao nhiệm vụ tiếp theo.

## Handoff Notes

Registry là nguồn trạng thái chính; DONE trong phạm vi kỹ thuật được Owner chấp nhận,
giữ các giới hạn đã ghi nhận và không tự mở nhiệm vụ hoặc benchmark tiếp theo.
