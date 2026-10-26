# Codex Handoff

## Active Task

M1-01 — Dataset Inventory & Provenance Review

## Status

IN_PROGRESS

## Last Verified State

2026-10-26: đọc hướng dẫn/spec/dataset/contracts; main sạch tại `dbe3192`, fetch origin khớp 0/0. M0-04 DONE.

## Completed Work

Checkpoint A: script CLI/tests độc lập đạt. Checkpoint B: inventory 9.127 file, 500 JSON trang, 534 bảng, 21.461 cells; metadata nguồn khớp trước/sau. Discovery report đã tạo. Checkpoint C: 24 representative (8/mã, phủ 15 báo cáo), 6 pilot; đã xem 8 ảnh raw, ghi chú local.

## Remaining Work

Checkpoint C: kiểm tra staged, commit/push và xác minh CI; chưa đánh dấu DONE.

## Modified Files

`scripts/inventory_ocr_dataset.py`, `tests/unit/test_inventory_ocr_dataset.py`,
`docs/ocr-data-discovery.md`, spec M1-01 và planning tasks/progress/current-status/handoff.
Artifacts chi tiết ở `artifacts/dataset-inventory/` (Git ignore), không stage.

## Tests

Ruff lint/format đạt; 34 unit tests passed (23 inventory + 11 smoke); planning
check 72 task đạt. Dùng .venv Python 3.12 với dev dependencies. Inventory thực tế
một lần; sampling tinh chỉnh từ manifest đã có, chưa có CI M1-01.

## Blockers

Không có.

## Git Checkpoint

Baseline `dbe3192` (M0-04), chưa có commit M1-01. Không thay đổi dữ liệu.

## Exact Next Action

Kiểm tra staged chỉ gồm file task rồi commit/push và xác minh CI (checkpoint C).
