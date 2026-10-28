# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

M2-08 DONE — Tech Lead APPROVED trong phạm vi Research MVP Lean v3 ngày 2026-10-28;
nghiệm thu planning-only.
26 structured queries: trước 23/26, sau 25/26 answered; sau tối ưu 25 đúng, 0 sai,
0 partial, 1 abstained, 25/25 grounded (0 unsupported).
Sau recovery: 123 numeric usable, gồm 95 ngoài catalog; 28 accepted extractions không đổi.
Gemini recovery: một target B01 mã 300 trang PDF 6, một call, 2.037 tokens,
hai giá trị được phục hồi. Gain do bổ sung trang 6, không do nới quality gate.
Kiến trúc: Gemini structured financial extraction là primary path;
OCR/unified, manual recovery và accounting checks là optional theo tác vụ.
Giới hạn: một PDF BBS2025, structured query intent khai báo trước;
chưa đánh giá chatbot ngôn ngữ tự nhiên.
Phiên nghiệm thu giữ nguyên code/tests/PDF/cache/artifacts; chỉ planning checker
và git diff --check đều PASS. Không chạy lại Gemini, pytest hoặc CI.
[Audit/API/benchmark](../docs/m1-m2-end-to-end-audit.md), [spec](tasks/M2/M2-08.md).

Implementation `12fd518526ae395566380313fe10d7a25bf58724` đã push; [CI40657097537](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40657097537) SUCCESS đúng SHA;
đã xác minh lại mọi bước Python 3.11/3.12.
Evidence implementation trước nghiệm thu: 18 focused +134 regression =152 targeted PASS.
Commit nghiệm thu chỉ planning, dùng [skip ci]; không gán CI implementation cho SHA nghiệm thu.

Baseline nghiệm thu sạch local/origin `52fd721bec5283dd37dbb558c7fff17be33fe323`.
Next action: Chờ Tech Lead giao Web Demo V1; chưa tự bắt đầu Web Demo hoặc M3.
