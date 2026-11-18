# Handoff

## Active Task
E2E-TECH-FIX-01 — Loại bỏ lỗi implementation trước Benchmark

## Status
REVIEW

## Last Verified State
Implementation `6b181024135bc252abe1f07e45a419e48a01f6e1`; ba probes trên `a8db198`.
[Báo cáo](../docs/e2e-tech-fix-01-live.md). Baseline `3a08371`, worktree riêng.

## Completed Work
Chuẩn hóa use_graph sai tầng, cap demand 2.500/context24K, mapping UnderstoodCell.col.
Phân loại NR-0006 thiếu unit/scale trong facts pin; giữ corpus/M6/Gold/model/Colab.
Ba probes một lượt: 18 calls/82.749 tokens/13 citations, toàn HTTP200.
MH-0006 partial và SH-0001 qua M6/M7. SH-0013 lỗi mapping đã sửa offline.

## Remaining Work
Chờ Tech Lead review. Mapping cuối chưa fresh live; không lặp probe.

## Modified Files
Demand parser, table source projection, 3 targeted controls, contracts/planning/report.

## Tests
8 targeted trước live, 6 sau mapping PASS. Saved-search replay hết AttributeError;
không thêm API. Ruff lint/format, planning/diff PASS. Không full CI/gate9/Pilot45.
190 runtime blobs, 264 JSON/115 corpus/3 Pilot và local edits giữ nguyên.

## Blockers
Không còn blocker code đơn giản đã xác nhận chưa sửa trong phạm vi kiểm.
Giữ thiếu metadata, lựa chọn nguồn/kind/query/evidence IDs của Qwen và HTTP524 endpoint.

## Git Checkpoint
Implementation SHA trên đã commit; commit tài liệu cuối chỉ chốt REVIEW.
Publish main từ worktree riêng; không chạm branch/index/local edits checkout gốc.

## Exact Next Action
Tech Lead review runtime freeze để chuyển Pilot45 theo Gold/rubric ViFinBench;
không tiếp tục FIX nhằm tăng accuracy.
