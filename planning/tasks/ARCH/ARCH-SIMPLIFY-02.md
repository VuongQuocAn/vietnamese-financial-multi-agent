# TASK ARCH-SIMPLIFY-02 — Contract tối giản cho Coordinator

## Metadata

- Milestone: ARCH
- Status: REVIEW
- Priority: P1
- Dependencies: ARCH-02
- Estimated Complexity: S

## Objective

Qwen lập danh sách goals và DAG tasks. Specialists chọn nguồn và công cụ theo
nhiệm vụ. Python thực thi và lưu provenance để M6 kiểm chứng và M7 tổng hợp.

## Context

Baseline `c4e0450` ghi ba lượt dừng ở bước lập kế hoạch của ARCH-SIMPLIFY-01.
Triển khai trên worktree riêng từ `origin/main`.

## Inputs

Ba câu Single-hop, Multi-hop và Mixed từ manifest đã chốt trong ARCH-SIMPLIFY-01,
corpus pin E2E-REMED-04 và Qwen đang phục vụ.

## Outputs

Contract M5, kiểm thử trọng tâm và [báo cáo live](../../../docs/arch-simplify-02-live.md). Trace và receipts lưu local
trong `artifacts/evidence/ARCH-SIMPLIFY-02/live-three/`.

## Allowed Changes

Wire Coordinator, lựa chọn và thực thi công cụ của Specialist trong M5, cùng
kiểm thử liên quan.

## Out of Scope

Model, Colab, context 24K, corpus, Gold, viết lại EF-EG/Financial Tools/M6/M7 và
full CI hoặc Pilot 9/45/600.

## Implementation Steps

Dùng goals dạng text và tasks dạng role, objective, goal indexes và dependencies.
Cho Specialist chọn Financial Tools, BM25, EF-EG hoặc Calculator qua workspace.
Chốt SHA trước ba lượt live.

## Acceptance Criteria

- [x] Kiểm tra goal có task và giữ nhánh DAG độc lập khi nhánh khác lỗi.
- [x] Offline smoke thực thi Specialist, Financial Tools, BM25, EF-EG, Calculator
  và đường nối M6/M7.
- [x] Bàn giao trace và kết quả của ba QA thật, mỗi câu một lượt.
- [ ] Xác nhận thực thi EF-EG trong QA live.

## Required Tests

20 targeted tests PASS và Ruff lint/format PASS. Ba QA live trên corpus đã pin.

## Risks and Blockers

Single-hop đi hết M5–M7. Hai lượt còn lại timeout. Mixed cũng chọn sai phạm
vi chỉ tiêu. EF-EG đã chạy offline, còn chờ bằng chứng live.

## Implementation Evidence

Implementation `25df8ebb184fc118373da68cfe0ef0808830d3f2`.

## Handoff Notes

Next action — Tech Lead quyết định chuyển sang `E2E-GATE-09`.
