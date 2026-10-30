# Codex Handoff

## Active Task

D-01 — BBS Multi-Year Canonical Coverage & Analytical Readiness

## Status

REVIEW

## Last Verified State

Real evaluation hoàn tất: 981 observations/165 mapped, exact retrieval/restart/context
preservation PASS; source hashes union 173 unchanged. Baseline main 24eedb1.

## Completed Work

109 discovery pages mới; 16 primary + 4 B09 fallback extraction pages, reuse 2025.
Source-backed company binding, liabilities/equity mapping, versioned normalized-v2.
29 queries: 22 available/1 blocked/4 ambiguous/1 mapping gap/1 source limit.
48 numeric cells/48 label occurrences khớp controlled original PDF visual read.
36 cross-year pairs numeric equal, scope thiếu nên undetermined.
15 metrics complete/undetermined; matched six từ 4 lên 6 complete. Không executor.
Chi tiết tại docs/d01-multi-year-readiness.md và planning/tasks/D/D-01.md.

## Remaining Work

Tech Lead nghiệm thu phạm vi D-01 và limitations; không tự DONE.

## Modified Files

Hai scripts D-01, mapping, focused tests, docs và planning/checker hỗ trợ ID D.

## Tests

119 targeted/core PASS; Ruff toàn repo/planning/diff PASS.
129 Gemini attempts, 260593 known tokens, 4 provider errors; zero calls ở evaluation.
Offline evaluation resume sau WinError 5 và sửa lời gọi graph validation.

## Blockers

Scope thiếu/source anchors uncertain; Q07 OCF 2022 table_position_conflict giữ blocked.
Chưa full-PDF/independent human gold accuracy hoặc approved formula execution.

## Git Checkpoint

Implementation `0f2ca6124cd4a4c994f38c32557d3f9b88f42e7c` đã push main, origin/main khớp.
CI41064083725 completed/SUCCESS đúng SHA, Python 3.12/Web smoke SUCCESS.
Giữ web/next-env.d.ts byte-for-byte ngoài stage.
Artifacts/data/secrets ignored; không suy CI từ documentation checkpoint sau này.

## Exact Next Action

Tech Lead review D-01; không bắt đầu M4-01.
