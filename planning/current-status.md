# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

M2-09 IN_PROGRESS — Full-PDF Real-World Evaluation & Targeted Hardening,
dependency M2-08 DONE. User đã giao implementation, live Gateway và commit/push/CI.

PDF BBS2025 24 trang, không có text layer, hash nguồn giữ nguyên.
Automatic discovery đúng 24/24: B01 5–6, B02 7, B03 8, B09 9–24, other 1–4.
Runtime bỏ pages vẫn xử lý đủ bốn trang chính. Reference trực tiếp PDF: 163 numeric
+7 dash; precision/recall/kỳ/unit/grounding/usability đều 163/163. Notes sample riêng 6/6.
7 dash sai glyph nhưng giữ missing, không suy zero. Chưa notes QA hoặc đa PDF.
25/26 structured queries đúng và grounded như M2-08; không runtime regression.
24 discovery calls +1 extraction mới trang 6 =25 calls/37.382 tokens, recovery 0.
Đề xuất CONDITIONAL GO, còn chờ Tech Lead quyết định Web Demo V1.

[Báo cáo/API](../docs/m2-09-full-pdf-evaluation.md), [spec](tasks/M2/M2-09.md).
Baseline thực tế `d0a82ea` trên main sạch/trùng origin/main khi bắt đầu;
khác SHA ghi trong handoff cũ. 140 targeted tests PASS, đang hoàn tất checks/CI.
Không dùng CI M2-08 cho implementation M2-09; chưa tự DONE hoặc mở demo/M3.

Next action: Hoàn tất checks, commit/push và xác minh CI đúng implementation SHA.
