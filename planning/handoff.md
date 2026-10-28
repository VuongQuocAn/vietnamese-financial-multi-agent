# Codex Handoff

## Active Task
M2-04a — Gemini-Assisted Table Recovery & Numeric Linking

## Status
IN_PROGRESS

## Last Verified State
M2-04 DONE; baseline HEAD/origin c26e3bf3f84cd88d429be5275469c64ddc096c7b. Gemini qua Gateway gemini-3.5-flash-lite: 3 calls thành công, 0 retry. 8 nguồn không đổi hash trong pilot.

## Completed Work
Recovery structured và adapter theo link với schema, binding ảnh, geometry review, OCR witness, kỳ/unit và code. Pilot 40 ô: 6 accepted đúng, 0 sai, 12 rejected ngoài catalog, 22 unresolved. OCR và Gemini bbox có lỗi; giữ manual review riêng và provenance. Hai links cũ bị thu hồi và xác minh lại với identity ảnh chính xác. [API/evidence](../docs/table-recovery.md), [issue](tasks/M2/issues/M2-04-numeric-linking.md).

## Remaining Work
Rà diff/staged, commit/push implementation, kiểm tra CI exact SHA Python 3.11/3.12; cập nhật REVIEW và chờ Tech Lead. Không bắt đầu M2-05.

## Modified Files
planning/tasks.md, progress.md, roadmap.md, current-status.md, handoff.md, tasks/M2/M2-04a.md, tasks/M2/issues/M2-04-numeric-linking.md; docs/table-recovery.md; src/accounting/__init__.py, table_recovery.py; tests/unit/test_table_recovery.py. Pilot artifacts ignored.

## Tests
14 focused + 12 regression PASS; Ruff lint/format, planning checker 83 và diff check PASS. Không full suite.

## Blockers
Chưa có CI exact SHA; một reviewer, không xác minh glyphs tự động, 22 links chưa đủ evidence, không accuracy toàn dataset.

## Git Checkpoint
Baseline c26e3bf3f84cd88d429be5275469c64ddc096c7b; implementation hiện tại chưa commit, chưa xác nhận CI.

## Exact Next Action
Commit/push implementation và kiểm tra CI exact SHA, sau đó chuyển REVIEW.
