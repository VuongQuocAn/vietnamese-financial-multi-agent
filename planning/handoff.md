# Codex Handoff

## Active Task

M1-02b — Document Understanding Contracts.

## Status

REVIEW

## Last Verified State

2026-10-26: local Python 3.12 đạt 170 unit tests (79 mới), Ruff lint/format,
pip check và planning validator 72 task. Chưa push/CI M1-02b.

## Completed Work

A: strict models, page identity, classification, anchors, statuses (17 tests).
B: structured text/table/cell, hai origins, multi-anchor, optional spans (27 tests).
C: structural errors có paths/payload snapshot, standalone quality và explicit raw
reference validation; schema export/sync; docs/decisions/planning (79 tests mới).
Giữ nguyên Raw OCR implementation/schema/tests, không đọc/sửa raw/processed.

## Remaining Work

Commit/push, kiểm tra CI đúng SHA; Tech Lead review schema/status/identity policy.
Không triển khai task khác.

## Modified Files

src/document_processing/contracts/{document_understanding.py,
document_understanding_validation.py,__init__.py};
tests/unit/test_document_understanding.py; schemas/document_understanding_v1.schema.json;
scripts/export_document_understanding_schema.py; docs/data-contracts.md;
planning/{tasks.md,progress.md,current-status.md,handoff.md,decisions.md,tasks/M1/M1-02b.md}.

## Tests

A 17/B 27/C 79 tests mới passed; full suite 170 passed.
Ruff lint/format 42 files, pip check, planning validator 72 task đạt local.
CI chưa chạy cho thay đổi mới. Synthetic tests không đánh giá chất lượng tài chính.

## Blockers

Không có blocker implementation. Chờ Tech Lead review.
Strict/extra forbid cho output sở hữu; export exclude_unset giữ missing/null.
Bbox observed/proposed riêng, pixel ảnh gốc; image-only anchors uncertain/unresolved.
source_ref do caller cung cấp, caller binding Raw OCR run; global identity, taxonomy,
migration và header relationships TBD. Không suy diễn tính duy nhất của symbol/year/page.

## Git Checkpoint

Baseline ổn định `0c8533e6027652129ce5edb01ec1a4ebc7722f6f`; M1-02b chưa commit.
main/origin baseline đã fetch khớp, initial working tree sạch.

## Exact Next Action

Commit/push checkpoint M1-02b và xác minh CI.
