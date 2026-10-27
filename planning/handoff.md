# Codex Handoff

## Active Task

M1-04b — Bounded Extraction Pilot.

## Status

REVIEW

## Last Verified State

2026-10-27: baseline phiên d78232028f619cb6416a89b2bbe5735f4d09d023 sạch/origin khớp.
M1-04a finalization DONE tại 6bfd43209d47ada1f236f8619ebc876c47c60f28,
CI 40435213198 success exact SHA. M1-04b implementation
4a2a4ed4ae09924e073448029e884b030f61bc27 đã push main, fetch/origin/main khớp;
CI 40437144971 success exact SHA, mọi steps Python 3.11/3.12 verified.

## Completed Work

A: protocol/spec trước real reads; C: frozen manifest 23 pages/398 references.
Coverage 14 pages/331 refs: 261 original/2 reconstructed/68 unrecovered;
risk 9 pages/67 refs: 55 original/12 reconstructed/0 unrecovered. Thiếu BCC/2025.
D/E/F: hai real runs bằng canonical reports/digests/membership; 472 selected input
snapshots (390 files/82 absence) unchanged, chỉ 28 selected recovered files hash.
23 Raw valid/image checked, 5 human issues giữ requires_review, run identity unverified.
H: API/evidence/sanitized statistics, tests, staged privacy review, implementation
commit/push/CI đạt. Không sửa contracts/validators/recovery/data/index/ledger.

## Remaining Work

Tech Lead review protocol/code/manifest methodology/local evidence/results/CI.
Checkpoint REVIEW chỉ docs/planning; push/check CI exact SHA mới trong báo cáo cuối,
không thêm commit chỉ để nhúng metadata tự tham chiếu. M1-04 cha TODO, không M1-05.

## Modified Files

Implementation gồm 11 files: planning/tasks/M1/M1-04b.md, tasks.md,
current-status.md, progress.md, handoff.md; src/document_processing/extraction_pilot.py;
scripts/run_extraction_pilot.py; tests/unit/test_extraction_pilot.py;
docs/extraction-pilot.md, docs/reviews/M1-04b-evidence.md, M1-04b-statistics.json.
Checkpoint REVIEW chỉ sáu planning/evidence files.

## Tests

Local final **768 passed/2 skipped**, targeted **40 passed**. Skips: case-insensitive
FS/FIFO Windows; symlink/junction pilot test chạy đạt. Ruff check/format, planning
75 tasks, pip check/diff check đạt. CI 40437144971: **759 passed/11 skipped** mỗi job,
Python 3.11/3.12 mọi steps success; skips native Windows syntax/junction trên Linux.
CI synthetic không thay real pilot. Real first/second deterministic, 0 conflicts/failures.

## Blockers

Không blocker engineering. REVIEW chờ Tech Lead acceptance.
Thiếu coverage BCC/2025; chưa có Understanding/quality thresholds/ground truth;
5 human bbox issues vẫn mở, original equivalence/Drive run identity chưa xác minh.
Không ngoại suy OCR accuracy/financial correctness hoặc readiness toàn corpus.
Trusted FS/TOCTOU/hardlinks/aliases/concurrent writers còn giới hạn cũ.

## Git Checkpoint

Stable implementation 4a2a4ed4ae09924e073448029e884b030f61bc27,
[CI 40437144971](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40437144971)
success exact SHA. Checkpoint REVIEW mới chỉ docs/planning, SHA/CI kiểm tra sau push.
Private artifacts/extraction-validation/M1-04b/: manifest.json, first.json, second.json,
canonical-report.json, verification.json; Git ignored. Chỉ local review nếu cần
đối chiếu full membership/bindings/fingerprints/digests. Không stage dữ liệu thật/secrets.

## Exact Next Action

Tech Lead review/accept M1-04b; không tự DONE/M1-04 hoặc bắt đầu M1-05.
