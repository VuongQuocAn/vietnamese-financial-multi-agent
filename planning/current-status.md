# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

M2-09 DONE — Full-PDF Real-World Evaluation & Targeted Hardening.
Tech Lead APPROVED Research MVP Lean v3, Evaluation Level 1 ngày 2026-10-28;
nghiệm thu planning-only, dependency M2-08 DONE.

PDF BBS2025 24 trang, không có text layer, hash nguồn giữ nguyên.
Automatic discovery đúng 24/24: B01 5–6, B02 7, B03 8, B09 9–24, other 1–4.
Runtime bỏ pages vẫn xử lý đủ bốn trang chính. Reference trực tiếp PDF: 163 numeric
+7 dash; precision/recall/kỳ/unit/grounding/usability đều 163/163. Notes sample riêng 6/6.
7 dash sai raw glyph nhưng giữ ngữ nghĩa missing, không suy zero.
Reference do một agent đối chiếu trực tiếp PDF, không có reviewer độc lập thứ hai;
chỉ một PDF, chưa đánh giá tổng quát, notes QA hoặc chatbot.
25/26 structured queries đúng và grounded như M2-08; không runtime regression.
24 discovery calls +1 extraction mới trang 6 =25 calls mới/37.382 tokens, recovery 0;
discovery 116,11 giây. Kiến trúc: Gemini-first, tự chọn trang, optional accounting
checks, không ManualReview gate. Tech Lead đồng ý CONDITIONAL GO cho Financial
Document Explorer Web Demo V1 B01/B02/B03; B09 chỉ inventory/viewer.

[Báo cáo/API](../docs/m2-09-full-pdf-evaluation.md), [spec](tasks/M2/M2-09.md).
Baseline thực tế `d0a82ea` trên main sạch/trùng origin/main khi bắt đầu;
khác SHA ghi trong handoff cũ. 140 targeted tests PASS; Ruff/planning/diff PASS.
Implementation `bd5a3c525f4cfe1d3f5204983e86746e748b1c93` đã push;
[CI40661431781](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40661431781)
SUCCESS đúng SHA; mọi bước Python 3.11/3.12 đã xác minh lại trong phiên nghiệm thu.
Baseline nghiệm thu sạch local/origin `c774b1dd7cc81195aee460708a272e3bf328dfc8`.
Phiên này chỉ sửa sáu tài liệu planning, chạy planning checker và git diff --check.
Không sửa implementation/tests/PDF/cache/reference/artifacts; không gọi Gemini,
không chạy lại pytest/CI. Commit nghiệm thu [skip ci]; không gán CI implementation
cho SHA nghiệm thu. Checkpoint REVIEW trong báo cáo giữ làm lịch sử trước approval.

Next action: Chờ Tech Lead giao Web Demo V1; không tự bắt đầu Web Demo V1 hoặc M3.
