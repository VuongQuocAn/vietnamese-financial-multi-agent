# Codex Handoff

## Active Task

M1-12 — Table Structure Reconstruction.

## Status

REVIEW

## Last Verified State

Baseline `0dd9bd1e7ee8aa9c8e458e49182e7d01624b2c46` = origin/main sau fetch,
working tree sạch trước triển khai. M1-11/M1-11b DONE. User giao M1-12 và cho
commit/push; không được tự DONE/M1-13. Implementation SHA/CI chờ publication.

## Completed Work

Deterministic reconstruction/DU v1; logical grid, exact source anchors,
reviewed SpanEvidence, placeholder semantics, collisions/gaps/geometry gate.
14 focused +205 regression =219 passed. Bounded frozen validation 4 pages,
8 tables/310 cells: 1 resolved/7 unresolved; 8 snapshots và manifest bất biến.
0 API requests/tokens. Usage/evidence/spec/registry/dashboard đồng bộ REVIEW.

## Remaining Work

Publication CI exact implementation SHA và Tech Lead review. Không implementation
khác hoặc task M1-13. Chưa ground truth merges; không claim accuracy.

## Modified Files

src/document_processing/table_reconstruction.py; tests/unit/test_table_reconstruction.py;
scripts/validate_table_reconstruction.py; docs/table-reconstruction.md;
docs/reviews/M1-12-evidence.md; planning/{tasks,progress,current-status,handoff}.md;
planning/tasks/M1/M1-12.md. Không thay raw/contracts/classification/credentials.

## Tests

219 targeted passed; Ruff lint/format đạt; planning/diff cuối trước commit.
Real report private ignored artifacts/table-reconstruction/M1-12/validation.json:
5 gaps, 32 out-of-bounds, 2265 pairwise geometry conflicts, 47 observed empty cells.
DU quality chỉ empty_text47; source/anchor/status issues0. Không full local suite.
Final core rerun cùng 4 pages sau duplicate-placeholder regression: report khớp.

## Blockers

Chờ Tech Lead acceptance. Chưa ground truth/real merge annotations; geometry strict,
trailing extent cần shape annotation, raw extras semantics TBD, run identity caller-bound.
Gemini-assisted và checkpoint orchestration deferred; không provider client giả.

## Git Checkpoint

Baseline stable `0dd9bd1e7ee8aa9c8e458e49182e7d01624b2c46`.
Code local đã chạy targeted và real validation; implementation SHA/CI ghi sau push.
[Evidence](../docs/reviews/M1-12-evidence.md), [spec](tasks/M1/M1-12.md).

## Exact Next Action

Tech Lead review M1-12 sau publication CI; không DONE/M1-13.
