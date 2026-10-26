# Codex Handoff

## Active Task

M1-02a — Raw OCR Contracts.

## Status

REVIEW

## Last Verified State

2026-10-26: checkpoint C local đạt 91 unit tests (57 contracts); Ruff lint/format,
pip check và planning validator 72 task đạt. Baseline đã fetch khớp origin/main.

## Completed Work

Checkpoint A: Pydantic v2 strict/extra allow, 7 element types, nested table/cell/line,
metadata/provenance, export_source. Cài editable .[dev] thành công, 24 tests đạt.
Checkpoint B: structural errors có source paths và bản sao payload, quality issues
riêng, unknown type không bị loại bỏ, round-trip tests; 57 tests đạt.
Không gọi API/OCR mới hoặc inventory lại dataset.
Checkpoint C: schema version raw_ocr_v1 sinh từ code, test đồng bộ, docs đã cập nhật.
Ba JSON mẫu BCC/2022/9, BCC/2023/1, BBS/2021/28 phủ 7 types round-trip khớp.
Metadata raw/processed SHA khớp M1-01:
`c92a8dd93accb74c936118b40eafc481febf8ec85559094c6c0d98b6217a16bb`.
Đây là metadata hash, không phải content hash hoặc đánh giá chất lượng tài chính.

## Remaining Work

Chờ commit/push và xác minh CI. Dừng sau M1-02a.

## Modified Files

pyproject.toml; src/document_processing/contracts/; tests/unit/test_raw_ocr_contracts.py;
schemas/raw_ocr_v1.schema.json; scripts/export_raw_ocr_schema.py; docs/data-contracts.md;
planning/tasks/M1/M1-02a.md; planning/tasks.md, progress.md, current-status.md, handoff.md.

## Tests

Checkpoint A 24 và B 57 contract tests passed; full suite 91 tests passed.
Ruff lint/format toàn repository, pip check và planning validator 72 task đạt.

## Blockers

Không có. label_text_ids item schema, non-null fallback detector và OCR run
version còn TBD. Không đánh đồng quality warnings với lỗi tài chính.

## Git Checkpoint

Baseline ổn định: `ddeef06691fe619f6cde8f3ac09d83c9595b0386`.
Checkpoint C chạy được ở working tree, chưa commit; CI chưa chạy cho thay đổi mới.

## Exact Next Action

Commit/push M1-02a và xác minh CI.
