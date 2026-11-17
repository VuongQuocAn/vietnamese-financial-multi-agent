# TASK E2E-VAL-01 — ViFinBench Pilot

## Metadata

- Milestone: E2E
- Status: REVIEW
- Priority: P1
- Dependencies: E2E-ARCH-02
- Estimated Complexity: S

## Objective

Đánh giá Pilot, bắt đầu9QA phân tầng SH/MH/NU trước quyết định chạy tiếp36.
Xác định nguyên nhân thực tế; không truy cập Full600QA.

## Context

Owner giao17/11/2026; baseline remote main d72f7c0. Worktree riêng bảo toàn
80local files của checkout gốc9a3adba.

## Inputs

Chỉ pilot.jsonl ba nhóm, metadata định danh và JSON/EF-EG đã import.
Mẫu cố định: câu đầu tiên mỗi difficulty easy/medium/hard trong từng nhóm.
Gold chỉ hậu kiểm offline, không đưa vào answering.

## Outputs

Per-QA Gold/output/verdict/citations/latency/calls/RCA, tổng hợp SH/MH/NU,
traces riêng theo lượt, readiness Full và SHA đã xác minh.

## Allowed Changes

Runner/evaluator/tests; sửa tối thiểu lỗi hệ thống lặp lại trong pipeline hiện có,
chỉ retest câu bị ảnh hưởng; tracking/report E2E-VAL-01.

## Out of Scope

Full600QA, OCR/Gemini/PDF, tạo agent/đổi kiến trúc, sửa corpus/Gold, fullCI.

## Implementation Steps

1. Freeze9QA trước Gold, pin runtime/source hashes và trace từng actual call.
2. Chạy M5→Tools/EF-EG/Calculator/Python→M6→Ledger→M7, hậu kiểm và RCA.
3. Sửa nhỏ nếu phù hợp, retest riêng; quyết định mở rộng36hoặc dừng có lý do.
4. Commit/push main, xác minh SHA và bàn giao REVIEW.

## Acceptance Criteria

- [x] Có kết quả9QA live và Gold hậu kiểm với metrics/traces.
- [x] RCA planning/handles/obligations/binding/dữ liệu-kỳ; giữ riêng trước/sau sửa.
- [x] Dừng mở rộng36vì lỗi nghiêm trọng; chưa sẵn sàng Full600.
- [x] SHA/bằng chứng xác minh, targeted validation, commit/push và REVIEW.

## Required Tests

Cap vòng đầu90actual calls,10/câu,300s/câu,60s/provider call, không retry transport.
Giữ một repair theo runtime. Retest tối đa một lượt/câu bị ảnh hưởng, cap riêng
ghi trước chạy.3targeted input/pointer controls, Ruff/planning/diff.

## Risks and Blockers

Dừng mở rộng nếu false-positive nguồn/kỳ/goal, exception lặp lại, hoặc phần lớn
MH/NU không phát hành đáp án đủ. Không bỏ câu khó khỏi denominator.
Engineering smoke không chứng nhận chất lượng tài chính; nguồn JSON-only,
chưa PDF-verified. Không coi coverage planner là Gold completeness.

## Implementation Evidence

Implementation `2d96f1574551e4a38b80b668066be9940497da46`; [report](../../../docs/e2e-val-01-vifinbench-pilot.md).
Baseline9:1correct/8abstain, accuracy/coverage11,11%,22calls/131299tokens/552,627s.
Retest SH0006/0013:0/2,5calls/14125tokens; candidate regression, đã loại và restore
185runtime files khớp baseline d72f7c0. Tổng27calls/145424tokens/0unknown.
264source JSON/3Pilot hashes và80local files bất biến.3new controls/2coordinator
controls PASS;1legacy deterministic FAIL y hệt baseline, không sửa ngoài scope.
Evidence local artifacts/evidence/E2E-VAL-01 gồm per-QA Gold/output/citations,
traces/Ledger/receipts, candidate patch và integrity audit; không commit dataset.
36Pilot còn lại và Full600 chưa chạy. Chờ Tech Lead nghiệm thu, không tự DONE.

## Handoff Notes

Next action: Tech Lead review gate9/45, RCA và thứ tự remediation trước khi cho phép chạy tiếp36Pilot.
