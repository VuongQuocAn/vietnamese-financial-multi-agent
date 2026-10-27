# Codex Handoff

## Active Task

M1-04a — Extraction Structure Validators.

## Status

REVIEW

## Last Verified State

2026-10-27: baseline 895087deeb06801ff4c67f198f8b1392a7da59de sạch,
local/origin/main khớp sau fetch. CI 40430400703 success exact SHA,
Python 3.11/3.12 mọi steps đạt. M1-03/M1-03f DONE, M1-04/M1-04b TODO.
User giao M1-04a và cho phép commit/push, dừng REVIEW; không tự DONE.
Implementation 32a3d23362f494fe8a39fa8ed9b3983841e4f287 đã push main,
local/origin/main khớp, working tree sạch trước cập nhật checkpoint REVIEW.
CI 40432840930 success exact SHA; mọi steps Python 3.11/3.12 đã kiểm tra,
719 passed/11 skipped mỗi job. Full local checks/smoke đạt.

## Completed Work

Checkpoints A–G: audit/spec; runtime reports; Raw/Understanding/Path composition;
JSON–ảnh dimensions/all bbox bounds; crop availability; strict recovery projection,
fresh canonical binding/sidecar/hash/pixels và bounded recovered header checks;
human-ledger preservation. Không sửa ba contracts hoặc recovery engine.
Real smoke 5 pages/50 refs: 43 original, 7 reconstructed, 5 bbox issues giữ requires_review;
hai lượt deterministic, integrity đạt. API docs/sanitized evidence/statistics đã có.

## Remaining Work

Chờ Tech Lead acceptance M1-04a. Checkpoint này chỉ cập nhật evidence/planning sang
REVIEW sau CI implementation success; push/check exact SHA checkpoint cuối trong
báo cáo kết thúc, không thêm self-reference commit. Không M1-04b/DONE.

## Modified Files

src/document_processing/extraction_validation.py, extraction_artifacts.py;
tests/unit/test_extraction_validation.py; docs/extraction-validation.md;
docs/reviews/M1-04a-evidence.md, M1-04a-statistics.json;
planning/tasks/M1/M1-04a.md, tasks.md, current-status.md, progress.md, handoff.md.
Private smoke reports/script ở artifacts/extraction-validation/M1-04a bị ignore.

## Tests

Full local 728 passed/2 skipped, targeted 61 passed. Skips: case-insensitive FS/FIFO
Windows; symlink tests chạy đạt ở lượt cuối. Ruff check/format --check 85 files,
planning 75 tasks, pip check và diff --check đạt. Python 3.12.0/Pillow 12.3.0.
Selected JSON/images/output/evidence hashes+metadata bất biến; metadata của toàn
199 PNG + 199 sidecars bất biến. Không re-hash toàn 193 sources hoặc 199 outputs.
Không dùng synthetic/smoke làm bằng chứng OCR accuracy/completeness/tài chính.

## Blockers

Không có blocker engineering. REVIEW chờ Tech Lead acceptance.
5 human bbox issues chưa sửa; original equivalence/OCR/Drive run identity unverified.
Trusted FS/TOCTOU/hardlinks/aliases/concurrent writers còn giới hạn policy cũ.

## Git Checkpoint

Baseline ổn định 895087deeb06801ff4c67f198f8b1392a7da59de,
[CI 40430400703](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40430400703)
success. Stable implementation 32a3d23362f494fe8a39fa8ed9b3983841e4f287,
[CI 40432840930](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40432840930)
success Python 3.11/3.12. Checkpoint REVIEW chỉ docs/planning; SHA/CI mới xác minh
sau push trong báo cáo cuối. Resume đối chiếu git status/HEAD/spec, không reset.
Chỉ stage allowlist; private artifacts/datasets/secrets giữ ngoài index.

## Exact Next Action

Tech Lead review/accept M1-04a; không tự DONE hoặc bắt đầu M1-04b.
