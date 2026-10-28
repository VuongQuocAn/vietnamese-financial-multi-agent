# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok).

M2-08 IN_PROGRESS — implementation/audit/pilot hoàn tất local, đang chờ CI.
Runtime primary: PDF → Gemini structured/cache bound → raw evidence → task-aware query.
26 structured queries: 23/26 → 25/26 answered (88,46% → 96,15%); correct 23→25,
incorrect/unsupported 0; partial 1→0; abstained 2→1; grounding 23/23→25/25.
Gain từ targeted recovery mã300 trang6, không từ nới quality gate trên ba trang cũ.
136→138 slots,121→123 numeric usable,28 canonical,93→95 ngoài catalog;
28 accepted extraction không đổi. Một Gemini call/2.037 tokens; không đo monetary cost/live latency.
18 focused +134 regression =152 targeted PASS; Ruff local PASS.
PDF/cache/reference hash trước/sau khớp; không commit artifacts/dataset/secrets.
Giới hạn: một PDF, intent khai báo trước; không là free-form chatbot accuracy.
[Audit/API/benchmark](../docs/m1-m2-end-to-end-audit.md), [spec](tasks/M2/M2-08.md).

Baseline ổn định `2c9c63dbcfd8fd86cf5eb0b81090fc49f8bf5469`.
Next action: Commit/push implementation M2-08 và xác minh CI đúng SHA.
