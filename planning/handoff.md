# Codex Handoff

## Active Task
M1-16 — Unified Document Understanding Pipeline

## Status
REVIEW

## Last Verified State
Baseline `e80319975b1eeef79efc68fac5007980cb20a2a7`, main/tree sạch trước sửa.
Implementation local checks/replay đạt; một implementation commit chứa handoff này.

## Completed Work
Entrypoint chung, adapter existing/native/manifest replay, unified_document_v1,
quality router chỉ đề xuất và consumer test. Existing6 text/1 table/97 cells;
native33 text/3 tables/335 cells, trong đó289 cell texts accepted/46 unresolved.
3 native tables unresolved; geometry0 verified, hash nguồn không đổi,0 API mới.

## Remaining Work
CI exact implementation SHA sau push; Tech Lead review trước DONE.

## Modified Files
ocr_loader.py; contracts/unified_document.py; understanding_pipeline.py;
test_understanding_pipeline.py; docs/data-contracts.md; API/evidence M1-16;
registry/dashboard/current-status/spec/handoff. Dữ liệu/artifacts không stage.

## Tests
10 focused +77 loader regression passed; Ruff changed files, planning/diff checks đạt.
Không full local suite; CI hiện có chạy full unit3.11/3.12 sau push.

## Blockers
Không blocker implementation. Native page-level provenance; geometry chưa verified;
raw layout unresolved khi chưa có evidence. Manifest/PNG replay không rehash PDF gốc.
Text evidence không phải accuracy tài chính; recovery chưa có executor.

## Git Checkpoint
Stable baseline `e80319975b1eeef79efc68fac5007980cb20a2a7`.
Implementation SHA: `git log -1 --format=%H -- src/document_processing/understanding_pipeline.py`.
CI exact SHA báo cuối phiên, receipt riêng dưới artifacts/document-understanding/M1-16/;
không publication commit chỉ để ghi CI.

## Exact Next Action
Tech Lead review implementation, CI exact SHA và giới hạn quality.
