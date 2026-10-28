# Codex Handoff

## Active Task
M2-05 — Deterministic Arithmetic Checks

## Status
REVIEW

## Last Verified State
M2-05 REVIEW — chờ Tech Lead nghiệm thu. M2-04b giữ DONE, M2-06 TODO.
Checker Decimal riêng với extraction; một rule active B02 gross_profit và bốn ứng viên unavailable.
Pilot PDF-bound cache BBS2025 trang5/7/8: B01 P/F/I/N=0/0/4/0,
B02=2/0/2/0, B03=0/0/2/0; hai check thực, difference0/tolerance0, không gọi Gemini.
28 accepted extraction giữ nguyên; financial_fact_verified=false, scope null không bị suy đoán.

## Completed Work
API evaluate_arithmetic_rules/evaluate_automated_records, registry, exact Decimal,
grouping cùng trang/kỳ/loại kỳ/scope, unit/scale/conflict/missing và lineage snapshots.
Replay PDF-bound cache, đọc ảnh nguồn5/7/8, đối chiếu hai đẳng thức B02.
Tài liệu API/pilot/issue/spec và planning đồng bộ; không sửa M2-04b hoặc catalog.

## Remaining Work
Commit/push, CI Python3.11/3.12 đúng implementation SHA và Tech Lead nghiệm thu.

## Modified Files
src/accounting/arithmetic.py, src/accounting/__init__.py,
scripts/run_arithmetic_pilot.py, tests/unit/test_arithmetic.py,
docs/arithmetic-checks.md, planning/tasks/M2/M2-05.md,
planning/tasks/M2/issues/M2-05-arithmetic-checks.md,
planning/tasks.md, planning/progress.md, planning/current-status.md, planning/handoff.md.

## Tests
28 focused PASS; 84 targeted tổng cộng với automated extraction/item mapping/contracts.
Ruff changed files, planning checker84 tasks và git diff --check PASS local.
Pilot local thật không phải synthetic; CI tests synthetic, không gọi Gemini.

## Blockers
Không có blocker triển khai. Bốn rule unavailable vì thiếu catalog/nguồn;
scope null chỉ tính cùng trang, chưa hỗ trợ multi-page arithmetic hoặc financial verification.

## Git Checkpoint
Baseline sạch local/origin `99f2a91e3d2642268cc6bb0cd769de94cb6d5e37`.
Implementation hiện ở working tree, chưa commit/push/CI; không gán CI cũ cho code mới.
Artifact local ignored: artifacts/arithmetic/M2-05/final/arithmetic.json;
SHA256 6784479f9a03a0c16802fe18a0a33adea0e8665917c28706ec4639e8e8c82ce9.

## Exact Next Action
Commit/push và xác minh CI đúng implementation SHA trước bàn giao Tech Lead.
