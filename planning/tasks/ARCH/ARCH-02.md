# TASK ARCH-02 — Technical Architecture Specification

## Metadata

- Milestone: ARCH
- Status: DONE
- Priority: P1
- Dependencies: ARCH-01a
- Estimated Complexity: S
- Related Modules: M5, Financial Tools/Python, EF-EG, M6, ledger, M7, Gateway

## Objective

Đặc tả cải tiến E2E để chuẩn bị triển khai trên coordinator V2 hiện có, giữ
pipeline và quyền quyết định ACCEPT của M6.

## Context

Owner giao ngày 17/11/2026 sau ARCH-01a được Tech Lead APPROVED. Task thiết kế,
chưa triển khai M5-COORD-01. Được phép commit/push tài liệu và tracking lên main;
không push các local commits/edits ngoài phạm vi.

## Inputs

[ARCH-01a](../../../docs/arch-01-adaptive-multi-agent-review.md), AGENTS,
current-status, architecture/module-boundaries/data-contracts và code paths liên
quan. Baseline runtime: HEAD `966b73a17dcf1a573f485ccc67f2ffb3be4bee0d` + local
edits có trước. Baseline publish: remote main
`5eea640d7c1955f7a7454c4c9c5d29fede247d57`, khác runtime đã đối chiếu.

## Outputs

[Đặc tả](../../../docs/arch-02-technical-specification.md): E2E, wire/internal
interfaces, Task DAG/workspace/proof/feedback, Python isolation, M6 obligations,
M7 realization và kế hoạch bắt đầu M5-COORD-01; tiêu chí engineering/scan-backed
research. Registry, current-status và dashboard cập nhật tối thiểu.

## Allowed Changes

Tài liệu ARCH-02 và tracking tương ứng. Publish bằng checkout riêng trên remote
main, chỉ stage allowlist; giữ working tree và bốn local commits ngoài task.

## Out of Scope

Không sửa runtime/schema/tests/checker hoặc corpus/artifacts; không gọi Qwen,
Gemini/OCR, benchmark, smoke/pytest/full CI; không tự bắt đầu task tiếp theo hay DONE.

## Implementation Steps

1. Đối chiếu ARCH-01a, status, Git và runtime working tree.
2. Chốt các giao diện/cơ chế nhỏ trên code hiện có, ghi giới hạn và preflight.
3. Viết spec và kế hoạch implementation; cập nhật tracking ARCH-02.
4. Kiểm planning/diff/phạm vi, commit/push docs-only lên main và dừng REVIEW.

## Acceptance Criteria

- [x] Có kiến trúc E2E và ownership, giữ M5 → Tools/EF-EG → M6 → Ledger → M7.
- [x] Có wire nhỏ, Task DAG/results/versioning, evidence/proof và local feedback.
- [x] Chốt Python Linux container, Calculator reuse, traceback/caps và proof replay.
- [x] Có obligations theo loại claim, truth/goal support riêng và M6 authority.
- [x] M7 dùng propositions đã verify; không thêm semantic verification lần hai.
- [x] Có task tiếp theo bắt đầu M5-COORD-01 và tiêu chí test dữ liệu scan thật.
- [x] Owner/Tech Lead chấp thuận ARCH-02 và cho chuyển DONE ngày 17/11/2026; chưa giao implementation.

## Required Tests

Docs-only: `python scripts/check_planning.py`, `git diff --check` tại working
tree và checkout publish; đối chiếu code/schema và local edits ngoài scope.
Không smoke/pytest/API/benchmark hoặc CI thủ công.

## Risks and Blockers

Đã được Owner/Tech Lead chấp thuận thiết kế ngày 17/11/2026. Docker CLI
có mặt, chưa xác minh daemon/image/isolation; runtime local chưa đồng bộ remote.
Caps chưa calibration; chưa có kết quả live/research mới; novelty chưa xác lập.

## Implementation Evidence

- Implementation SHA: [`cb65c927fe2fc719d06fdd82cf904e3323a941cf`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/cb65c927fe2fc719d06fdd82cf904e3323a941cf),
  đã xác minh commit chỉ năm file tài liệu/tracking; baseline tại Inputs.
- Main Changes: chỉ đặc tả ARCH-02 và tracking; proposed follow-up IDs chưa mở task.
- Test Results: planning PASS tại working tree (161 tasks) và cây publish (145
  tasks); diff check PASS. Fingerprint 182 file Python/JSON trong src/schema
  trước/sau khớp `5e9caa109b27e4e2b3155b850d835a27dac693c1a014093184b184be1fd7bf82`;
  đối chiếu 79 files local ngoài scope không đổi. Không chạy model/pytest/benchmark/CI.
- Review Notes: Owner/Tech Lead APPROVED ngày 17/11/2026, cho chuyển DONE.
  Phiên đóng chỉ cập nhật tài liệu/tracking, kiểm planning/diff; không chạy lại
  tests/model/benchmark/CI hoặc triển khai runtime/M5-COORD-01.

## Handoff Notes

Next action duy nhất: chờ Owner/Tech Lead giao M5-COORD-01.
