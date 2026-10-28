# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

M2-05 REVIEW — chờ Tech Lead nghiệm thu. M2-04b giữ DONE, M2-06 TODO.
Checker Decimal riêng với extraction; một rule active B02 gross_profit và bốn ứng viên unavailable.
Pilot PDF-bound cache BBS2025 trang5/7/8: B01 P/F/I/N=0/0/4/0,
B02=2/0/2/0, B03=0/0/2/0; hai check thực, difference0/tolerance0, không gọi Gemini.
28 accepted extraction giữ nguyên; financial_fact_verified=false, scope null không bị suy đoán.

- Baseline local/origin sạch `99f2a91e3d2642268cc6bb0cd769de94cb6d5e37`; người dùng giao cả commit/push/CI.
- [API/pilot](../docs/arithmetic-checks.md), [spec](tasks/M2/M2-05.md),
  [issue](tasks/M2/issues/M2-05-arithmetic-checks.md).
- 28 focused/84 targeted PASS; Ruff/planning/diff PASS local.
- Implementation `4472916ed19320d13b0a4d0f830d0a7a836fec90` đã push;
  [CI40649070030](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40649070030)
  completed/SUCCESS đúng SHA, từng bước Python3.11/3.12 đã xác minh.
- Mặc định exact Decimal, không đổi unit/scale; nhóm cùng page/period/type/scope.
- Arithmetic failure/thiếu dữ liệu kiểm tra không chặn dùng extraction cho QA;
  chưa verified financial facts.
- Checkpoint evidence sau CI chỉ docs/planning; không gán CI implementation cho SHA docs.
- Next action: Chờ Tech Lead review M2-05.
