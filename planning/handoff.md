# Codex Handoff

## Active Task

M1-03c — Read-Only OCR Data Loader.

## Status

IN_PROGRESS

## Last Verified State

Acceptance M1-03b `10eb4e92c64fd241a2b740f7e38584abe1455032` push/remote khớp,
CI 40310998984 success đúng SHA/từng step Python 3.11/3.12 đã kiểm tra.
Local baseline 442 passed/11 skipped; Ruff 54 files, planning 72 tasks, pip check đạt.

## Completed Work

A/B: public loader + typed result/error, resolver integration/revalidation,
bounded read-only read, decode/parse/quality, anchor identity, provenance.
75 passed/1 skipped synthetic loader cases, native junction swap đạt.
C: đúng 3 mẫu manifest BCC/2022/9, BBS/2023/6, BCC/2023/1 parse thành công,
content hashes và size/mtime/inode trước/sau khớp. Không scan corpus.
Docs API/errors/security/provenance/quality/integration hoàn tất.

## Remaining Work

Commit/push/remote/CI đúng SHA, chuyển REVIEW và chờ Tech Lead nghiệm thu.

## Modified Files

src/document_processing/{ocr_loader.py,__init__.py}; tests/unit/test_ocr_loader.py;
planning/{tasks.md,progress.md,current-status.md,handoff.md,tasks/M1/M1-03c.md}.
docs/{ocr-loader.md,data-contracts.md,dataset.md}; planning/decisions.md.
artifacts/ocr-loader/{verify_samples.py,sample-results.json} local bị Git ignore.

## Tests

Loader 75 passed/1 skipped Windows Python 3.12; symlink thiếu privilege.
Full 517 passed/12 skipped; Ruff lint/format 58 files, planning 72 tasks, pip check đạt.
Integration manual đúng 3 mẫu, không có anchor image trong manifest nên chỉ đối
chiếu symbol/year/page; không xác minh run identity. Chi tiết docs/ocr-loader.md.
Synthetic tests không phải benchmark OCR/tài chính.

## Technical Decisions

Runtime wrapper không version/schema mới; UTF-8/BOM, reject duplicate keys;
32 MiB default hữu hạn chưa đo phù hợp toàn corpus. Reuse resolver trước/sau
read; fstat/lstat fingerprint; O_NOFOLLOW/O_NONBLOCK nếu có. Windows ctime không
so chéo lstat/fstat do semantics khác nhau, POSIX thêm ctime.

## Blockers

Không blocker. TOCTOU/aliases/hardlinks còn giới hạn; source/run identity do caller.

## Git Checkpoint

Stable acceptance `10eb4e92c64fd241a2b740f7e38584abe1455032`, remote/CI success.
Loader A/B/C đã kiểm thử local, đang ở working tree; chưa claim CI implementation.

## Exact Next Action

Xác minh publication M1-03c đúng SHA.
