# Codex Handoff

## Active Task

M1-03e — Verified Local Mapping & Real Crop Recovery Pilot.

## Status

DONE

## Last Verified State

M1-03d DONE theo Tech Lead APPROVED engineering/synthetic/zero-output;
acceptance `1e7fe344c4991b99127448a5180bdcb4470c9a60`, remote khớp,
CI 40340730395 success đúng SHA/mọi steps Python 3.11/3.12. M1-03 giữ DONE.

## Completed Work

A: 2/2 exact local mappings verified, rejected/ambiguous 0; 1.178 positive controls
trên 14 nhóm mã/năm mỗi prefix, 4 negative controls, 193 verified page bindings.
B: audit đúng 193/193 trang, references 1.557, existing 985, missing 572,
unique/contextual missing 572/572, unmapped/unsafe/ambiguous 0. Baseline khớp;
eligible table.crop 199, unsupported views 288, non-table review 85.
C: dry-run 12/12; recovered 12, conflicts/failures 0, reopen/pixels/hash/provenance
12/12 đạt. Rerun 12 already_recovered; output bytes/metadata giữ nguyên, cap 12.
193 JSON + 193 raw images hash/metadata trước/sau khớp. Không ghi raw/processed.
Private bindings tái lập/idempotent, không tạo run_identity; artifacts bị ignore.

## Remaining Work

Tech Lead review [sanitized GitHub evidence](../docs/reviews/M1-03e-evidence.md).
Không mở M1-04a/b hoặc mở rộng recovery. Không còn implementation work trong scope.

## Modified Files

src/document_processing/{local_crop_mapping.py,crop_evidence.py,crop_audit.py};
scripts/{verify_local_crop_pilot.py,export_crop_evidence.py};
tests/unit/{test_local_crop_mapping.py,test_crop_evidence.py};
docs/{crop-recovery.md,dataset.md,reviews/M1-03e-evidence.md}; planning/{tasks.md,progress.md,current-status.md,handoff.md,decisions.md,
tasks/M1/M1-03e.md}. Full artifacts local artifacts/crop-recovery/M1-03e/;
12 PNG + sidecars local data/recovered_crops/. Không tạo contact sheet.

## Tests

Windows Python 3.12: 614 passed/13 skipped; mapping 26 tests, publication 13 tests.
Ruff lint/format 71 files, planning 74 tasks/pip check đạt. Windows skips:
11 symlink privilege, case-insensitive filesystem, FIFO unsupported. Native junction
đạt. CI Linux Python 3.11/3.12: 617 passed/10 skipped mỗi job, mọi steps success.
Tests không đánh giá OCR/tài chính.

## Blockers

Không có blocker cho bounded local pilot. Original Drive byte/run identity và
preprocessing equivalence chưa xác minh. TOCTOU, aliases/hardlinks/concurrent
writers còn giới hạn; trusted local filesystem/single writer. Không đưa private
source paths/hashes, ảnh hoặc OCR content lên GitHub.

## Git Checkpoint

Stable acceptance `1e7fe344c4991b99127448a5180bdcb4470c9a60`;
[CI 40340730395](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40340730395)
success đúng SHA. Stable implementation M1-03e
`6c2b8c7738631b578c97b9b0d930b51ff69c6162`, push/remote khớp;
[CI 40342491992](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40342491992)
success đúng SHA/mọi steps Python 3.11/3.12, 617 passed/10 skipped mỗi job.
Evidence/REVIEW publication đi sau implementation; kiểm tra CI publication theo
HEAD riêng, không suy từ CI trên. Không commit artifacts/data/paths thật.

## Exact Next Action

Chờ Tech Lead review M1-03e qua GitHub.

Tech Lead APPROVED M1-03e ng?y 2026-10-26 theo task M1-03f: mapping,
193-page audit, 12 real crops/pixels/hash/rerun v? source integrity ???c nghi?m thu.
Original preprocessing equivalence v?n unverified; M1-03 gi? DONE.
Publication checkpoint b0168a0c37f5a0c29b53693833d8c300e338ff74.
