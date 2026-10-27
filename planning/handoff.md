# Codex Handoff

## Active Task

M1-04a — Extraction Structure Validators.

## Status

IN_PROGRESS

## Last Verified State

2026-10-27: baseline 895087deeb06801ff4c67f198f8b1392a7da59de sạch,
local/origin/main khớp sau fetch. CI 40430400703 success exact SHA,
Python 3.11/3.12 mọi steps đạt. M1-03/M1-03f DONE, M1-04/M1-04b TODO.
User giao M1-04a và cho phép commit/push, dừng REVIEW; không tự DONE.
Implementation và full local checks đã hoàn tất; chưa commit/push implementation.

## Completed Work

Checkpoints A–G: audit/spec; runtime reports; Raw/Understanding/Path composition;
JSON–ảnh dimensions/all bbox bounds; crop availability; strict recovery projection,
fresh canonical binding/sidecar/hash/pixels và bounded recovered header checks;
human-ledger preservation. Không sửa ba contracts hoặc recovery engine.
Real smoke 5 pages/50 refs: 43 original, 7 reconstructed, 5 bbox issues giữ requires_review;
hai lượt deterministic, integrity đạt. API docs/sanitized evidence/statistics đã có.

## Remaining Work

Allowlist stage/commit/push, kiểm tra CI implementation exact SHA; sau success cập nhật
checkpoint REVIEW chờ Tech Lead, push/check CI checkpoint cuối. Không M1-04b/DONE.

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

Không có blocker engineering. Chờ publication/CI trước REVIEW, rồi Tech Lead acceptance.
5 human bbox issues chưa sửa; original equivalence/OCR/Drive run identity unverified.
Trusted FS/TOCTOU/hardlinks/aliases/concurrent writers còn giới hạn policy cũ.

## Git Checkpoint

Baseline ổn định 895087deeb06801ff4c67f198f8b1392a7da59de,
[CI 40430400703](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40430400703)
success. Implementation hiện ở working tree đã test, chưa commit/push;
resume đối chiếu git status/HEAD/spec, không reset về checkpoint cũ.
Chỉ stage allowlist; private artifacts/datasets/secrets giữ ngoài index.

## Exact Next Action

Commit/push M1-04a, kiểm tra CI implementation exact SHA.
