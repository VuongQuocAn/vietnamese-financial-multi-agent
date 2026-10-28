# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok).

M2-08 REVIEW — chờ Tech Lead nghiệm thu, không tự DONE hoặc bắt đầu Web Demo/M3.
Runtime primary: PDF → Gemini structured/cache bound → raw evidence → task-aware query.
26 structured queries:23/26 →25/26 answered (88,46% →96,15%); correct23→25,
incorrect/unsupported0; partial1→0; abstained2→1; grounding23/23→25/25.
Gain từ targeted recovery mã300 trang6, không từ nới quality gate trên ba trang cũ.
136→138 slots,121→123 numeric usable,28 canonical,93→95 ngoài catalog;
28 accepted extraction không đổi. Một Gemini call/2.037 tokens; monetary cost/live latency chưa đo.
18 focused +134 regression =152 targeted PASS; Ruff/planning/diff local PASS.
PDF/cache/reference hash trước/sau khớp; không commit artifacts/dataset/secrets.
Giới hạn: một PDF, intent khai báo trước; không là free-form chatbot accuracy.
[Audit/API/benchmark](../docs/m1-m2-end-to-end-audit.md), [spec](tasks/M2/M2-08.md).

Implementation ổn định `12fd518526ae395566380313fe10d7a25bf58724` đã push; [CI40657097537](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40657097537) SUCCESS đúng SHA, mọi steps Python3.11/3.12 đã xác minh.
Checkpoint kết thúc chỉ docs/planning dùng [skip ci]; không gán CI implementation cho SHA tài liệu.

Next action: Chờ Tech Lead review M2-08.
