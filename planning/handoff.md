# Codex Handoff

## Active Task

M3-07 — Evidence Retrieval Interface

## Status

DONE

## Last Verified State

Tech Lead APPROVED M3-07 ngày 30/10/2026; Owner cho phép chuyển DONE,
planning trực tiếp main. Accepted implementation e8f293d giữ nguyên.
102 focused/regression PASS; real run-2 356/356 exact,18/18 queries,172 hashes unchanged.

## Completed Work

Unified retrieval/contracts/citations, inventory missing coverage, negative controls,
real queries và deterministic question flow. [API/report](../docs/evidence-retrieval.md).

## Remaining Work

Không còn việc M3-07; M4-01 chưa được giao triển khai.

## Modified Files

Phiên nghiệm thu chỉ sửa planning registry/spec/status/dashboard/handoff.
Giữ local web/next-env.d.ts ngoài stage, không đưa artifacts/data vào Git.

## Tests

102 focused/regression PASS; real run-2 356 exact/18 queries PASS; restart exact.
9 complete-with-caveat/3 partial-quality-blocked/2 canonical-unavailable questions.
Ruff lint/format toàn repository, planning/diff PASS.
CI41056561499 completed/SUCCESS đúng e8f293de4445f91860ff8820f123502da649d2e6;
Python 3.12 và Web smoke đều SUCCESS. Không suy CI từ checkpoint docs/planning.
Phiên chuyển DONE chỉ planning checker/diff check; không chạy lại tests,
real evaluation/Gemini/OCR/extraction hoặc mở rộng test suite/refactor.

## Blockers

Không blocker implementation. Chưa PDF financial verification/multi-year canonical
coverage; liabilities mapping thiếu, M2 blocked và compatibility undetermined giữ nguyên.
Zero Gemini/OCR/extraction/raw changes.

## Git Checkpoint

Implementation `e8f293de4445f91860ff8820f123502da649d2e6` đã push main,
origin/main khớp; baseline d0bf722. Main-first, không branch/PR/worktree.
Checkpoint trước nghiệm thu `650582ff5335a5a107b873c6e2b5a76705882596` trên main.
Local web/next-env.d.ts giữ nguyên SHA-256 trước/sau và ngoài commit.

## Exact Next Action

Chờ giao nhiệm vụ mới; không bắt đầu M4-01.
