# TASK ARCH-SIMPLIFY-01 — Đơn giản hóa điều phối Multi-Agent

## Metadata

- Milestone: ARCH
- Status: REVIEW
- Priority: P1
- Dependencies: ARCH-02
- Estimated Complexity: S

## Objective

Qwen lập goals, tasks, Specialist, dependencies và công cụ trên Coordinator V2.

## Context

Worktree riêng trên baseline `c1b6450` bảo toàn các chỉnh sửa local ngoài phạm vi.

## Inputs

Qwen đang phục vụ, manifest câu hỏi Pilot, corpus pin của E2E-REMED-04.

## Outputs

M5 dùng một plan và workspace hiện có. [Báo cáo](../../../docs/arch-simplify-01-live.md)
ghi metrics và nguyên nhân các gap từ trace của ba QA.

## Allowed Changes

Coordinator, task execution, đường nối claim M6/M7 và kiểm thử trọng tâm.

## Out of Scope

Colab, model, context 24K, corpus, Gold, viết lại M6/M7, OCR, Gemini và full CI.

## Implementation Steps

Giữ nhánh hợp lệ khi plan có lỗi. Dùng task DAG cho Financial Tools, BM25 và
EF-EG, rồi nối các claims có nguồn đến M6. Chốt implementation trước ba lượt live.

## Acceptance Criteria

- [x] Giữ phần hợp lệ khi một goal, task hoặc dependency có lỗi cấu trúc.
- [x] Một plan điều phối Financial Tools, BM25, EF-EG và chia sẻ kết quả qua workspace.
- [x] Kiểm thử trọng tâm cho multi-goal, dependency, nguồn chia sẻ và mixed.
- [x] Bàn giao trace và kết quả của ba QA thật cho Tech Lead.

## Required Tests

37 targeted tests PASS và ba QA Pilot, mỗi câu một lượt. Gold dùng hậu kiểm.

## Risks and Blockers

Ba lượt dừng ở planning do thiếu task hoặc goal source sai. Phối hợp end-to-end
đã kiểm offline, bằng chứng live chưa xác nhận.

## Implementation Evidence

Implementation `5cb38bd4853c7bbbe054a79ea18c54ba2b2d1408`. Xem bảng metrics
và nguyên nhân theo từng trace trong báo cáo.

## Handoff Notes

Next action — Tech Lead review để quyết định chuyển sang `E2E-GATE-09`.
