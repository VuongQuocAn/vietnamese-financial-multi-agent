# Codex Handoff

## Active Task
M1-14 — Document Understanding Evaluation

## Status
REVIEW

## Last Verified State
Baseline acceptance `7ed1b808239d5a1240f79a167d6c06ac8b677da8`, main sạch trước triển khai.
User cho phép một implementation commit/push; không tự DONE/M2.

## Completed Work
Evaluator offline hash-pinned inputs/JSON selectors, 4 ảnh đối chiếu trực tiếp,
46 snippets/cells,18 số,36 partial positions/3 bảng; benchmark/results private ignored.
Common26: A/B24/26,C26/26; số6/6 cả ba. Available A/B44/46,số18/18.
Same8 A/B structure1/8→2/8; C schema2/2 nhưng tables0/4 accepted.
Report đề xuất Hybrid có kiểm soát; tách schema/structure/content/provenance.
Không gọi API, không sửa source/raw/images/outputs hoặc task DONE.

## Remaining Work
CI exact implementation SHA kiểm sau một push và ghi trong final response;
Tech Lead review nhãn, metrics và đề xuất. Không publication commit cập nhật SHA.

## Modified Files
src/document_processing/evaluation.py; tests/unit/test_document_evaluation.py;
planning/tasks.md; planning/tasks/M1/M1-14.md; planning/handoff.md;
planning/current-status.md; planning/progress.md; docs/reviews/M1-14-evaluation.md.

## Tests
8 focused passed; Ruff changed files, planning checker, diff check.
Không full local regression, không API/benchmark lớn. Existing CI full units3.11/3.12.

## Blockers
Không blocker offline. Nhãn Codex visual review chưa human second review;
B09-only/selection bias, C2/4 pages, thiếu full grid/merge/bbox truth,
không comparable latency/cost; historical crop timeout usage unknown.

## Git Checkpoint
Stable baseline `7ed1b808239d5a1240f79a167d6c06ac8b677da8`.
Implementation một commit/push, SHA/CI trong final response sau push;
không tự tham chiếu SHA chưa tồn tại. Private benchmark SHA:
`771ecdb67671419b01b9b08468e5f12f81c34b468bccda8a357464fba16158c2`.

## Exact Next Action
Tech Lead review nhãn, metrics và đề xuất Hybrid; giữ M1-14 REVIEW, không M2.
