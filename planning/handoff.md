# Codex Handoff

## Active Task

M1-02a — Raw OCR Contracts.

## Status

DONE

## Last Verified State

2026-10-26: checkpoint C local đạt 91 unit tests (57 contracts); Ruff lint/format,
pip check và planning validator 72 task đạt. Baseline đã fetch khớp origin/main.
Checkpoint `08f3289a47f021a97608b7e8d2885bd3656bc9c5` đã push origin/main;
local/remote khớp, working tree sạch sau push checkpoint.
[CI 40274687167](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40274687167)
success Python 3.11/3.12; đã kiểm tra steps install/lint/format/planning/tests.
CI này chỉ chứng minh checkpoint nội dung; bản nghiệm thu ở commit sau.

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

Không còn acceptance criteria mở của M1-02a. Dừng sau M1-02a.
M1-02b/c và task cha M1-02 giữ TODO; không tự chuyển task.

## Modified Files

pyproject.toml; src/document_processing/contracts/; tests/unit/test_raw_ocr_contracts.py;
schemas/raw_ocr_v1.schema.json; scripts/export_raw_ocr_schema.py; docs/data-contracts.md;
planning/tasks/M1/M1-02a.md; planning/tasks.md, progress.md, current-status.md, handoff.md.

## Tests

Checkpoint A 24 và B 57 contract tests passed; full suite 91 tests passed.
Ruff lint/format toàn repository, pip check và planning validator 72 task đạt.
CI checkpoint nội dung success cả Python 3.11 và 3.12.

## Blockers

Không có. label_text_ids item schema, non-null fallback detector và OCR run
version còn TBD. Không đánh đồng quality warnings với lỗi tài chính.

## Git Checkpoint

Checkpoint nội dung ổn định, đã push/CI success:
`08f3289a47f021a97608b7e8d2885bd3656bc9c5`.
Baseline trước M1-02a: `ddeef06691fe619f6cde8f3ac09d83c9595b0386`.
Bản ghi nghiệm thu ở commit sau checkpoint. Khi resume đọc Git/status thực tế,
không reset về checkpoint hoặc lặp lại inventory/công việc đã kiểm chứng.

## Exact Next Action

Chờ người dùng giao task tiếp theo; không bắt đầu M1-02b.
