# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

M2-05 DONE — Tech Lead APPROVED Research MVP Lean v3 ngày 2026-10-28;
nghiệm thu planning-only. M2-04b giữ DONE, M2-06 TODO.
Checker Decimal riêng với extraction; một rule active B02 gross_profit và bốn ứng viên unavailable.
Pilot PDF-bound cache BBS2025 trang5/7/8: B01 P/F/I/N=0/0/4/0,
B02=2/0/2/0, B03=0/0/2/0; hai check thực, difference0/tolerance0, không gọi Gemini.
Tổng 2 PASS B02 cho lợi nhuận gộp2025/2024, 0 FAILED, 8 INSUFFICIENT;
chưa có kiểm tra arithmetic thực B01/B03, không phải verified financial facts.
28 accepted extraction giữ nguyên; financial_fact_verified=false, scope null không bị suy đoán.

- Baseline nghiệm thu sạch local/origin `82aedb66480cc62cedfbfd38d2cce2502b9ff27e`.
- [API/pilot](../docs/arithmetic-checks.md), [spec](tasks/M2/M2-05.md),
  [issue](tasks/M2/issues/M2-05-arithmetic-checks.md).
- Evidence implementation trước nghiệm thu:28 focused/84 targeted PASS, Ruff/planning/diff PASS.
- Implementation `4472916ed19320d13b0a4d0f830d0a7a836fec90` đã push;
  [CI40649070030](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40649070030)
  completed/SUCCESS đúng SHA, từng bước Python3.11/3.12 đã xác minh lại từ run hiện có.
- Mặc định exact Decimal, không đổi unit/scale; nhóm cùng page/period/type/scope.
- Arithmetic failure/thiếu dữ liệu kiểm tra không chặn dùng extraction cho QA;
  chưa verified financial facts.
- Phiên nghiệm thu chỉ năm file planning; planning checker/diff check;
  giữ nguyên code/tests/schema/PDF/output nguồn, không chạy lại Gemini/pytest/CI.
  Không gán CI implementation cho SHA nghiệm thu planning-only.
- Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2-06.
