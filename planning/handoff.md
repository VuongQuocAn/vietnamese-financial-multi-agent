# Codex Handoff

## Active Task

M1-04b — Bounded Extraction Pilot.

## Status

IN_PROGRESS

## Last Verified State

2026-10-27: baseline phiên d782320 sạch/origin khớp. M1-04a đã finalize DONE tại
6bfd43209d47ada1f236f8619ebc876c47c60f28, push/origin khớp;
CI 40435213198 success exact SHA, mọi steps Python 3.11/3.12 verified.

## Completed Work

Checkpoint A: spec/protocol v1 trước real reads; hai nhóm coverage/risk riêng,
reserve năm ledger pages, coverage per stratum, tối đa 5 supplemental risk signals.
TODO → READY → IN_PROGRESS sau dependencies/spec đủ và user giao.
Checkpoint C: frozen manifest 23 pages/398 references tại ignored output directory.
Approved pool 14 strata, thiếu BCC/2025; không scan corpus hoặc mở rộng mappings.
Thin runner + CLI + synthetic tests. Checkpoint F: first/second canonical reports,
digests và manifest binding khớp; 472 input snapshots (390 files/82 absence) unchanged.
Chỉ 28 selected recovered files được hash; không toàn 199 outputs. Coverage
14 pages/331 refs: 261 original/2 reconstructed/68 unrecovered; risk
9 pages/67 refs: 55 original/12 reconstructed/0 unrecovered. 5 human issues vẫn mở.
H draft API/evidence/sanitized statistics đã có; exporter other-page union regression đạt.

## Remaining Work

Diff/privacy review, commit/push/exact-SHA CI, dừng REVIEW.

## Modified Files

planning/tasks/M1/M1-04b.md, tasks.md, current-status.md, progress.md, handoff.md;
src/document_processing/extraction_pilot.py, scripts/run_extraction_pilot.py,
tests/unit/test_extraction_pilot.py, docs/extraction-pilot.md,
docs/reviews/M1-04b-evidence.md và M1-04b-statistics.json. Private outputs ignored.

## Tests

Finalization planning/diff checks đạt; CI 40435213198 success.
M1-04b targeted cuối 40 passed; Ruff lint/format, planning/pip/diff đạt.
Full cuối 768 passed/2 skipped (Windows case-insensitive FS/FIFO); symlink/junction
pilot test chạy đạt. Full trước regression 767 passed/2 skipped.
Real first/second deterministic/read-only, 0 conflicts/failures.

## Blockers

Chưa có. Coverage bị giới hạn approved bindings; thiếu strata phải báo riêng.

## Git Checkpoint

Stable baseline 6bfd43209d47ada1f236f8619ebc876c47c60f28, CI 40435213198 success.
Không đổi source datasets/artifacts; private outputs ignored.

## Exact Next Action

Allowlist commit/push implementation và kiểm tra exact-SHA CI.
