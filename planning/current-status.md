# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

W-01 REVIEW — Web Demo V1 Architecture, API Contracts & UI Design.
Được người dùng giao bắt đầu và commit/push, phụ thuộc M2-09 DONE.
[Spec](tasks/W/W-01.md), [architecture](../docs/web-demo-v1/architecture.md),
[API](../docs/web-demo-v1/api-contracts.md), [UI](../docs/web-demo-v1/ui-handoff.md).

Baseline đã fetch `5c8a80e4ceedb735dcbad12e267620b0b8046adb`, main trùng origin/main;
chỉ docs/UI untracked. Nhánh docs/w-01-web-demo-design.
Đã đọc backend thực tế, cả hai bộ Stitch HTML/MD/PNG; giữ nguyên sáu assets.
Đề xuất Next.js + FastAPI, local PDF/JSON, bounded worker/polling;
PDF-only Vision metadata preflight mới, tái sử dụng discovery/extraction M1–M2.
API giữ Decimal string, raw/unmapped/context và page provenance; B09 inventory,
AI Workspace/Evidence Graph Coming Soon. Cache/quota in-memory và extraction
không callback được nêu rõ; checkpoint chưa tự nối financial runtime.

Local planning 87 tasks PASS, checker regressions 3 PASS, Ruff PASS;
diff phần W-01 tự viết PASS; staged toàn bộ báo bốn trailing spaces có sẵn
trong Stitch DESIGN.md (giữ nguyên assets theo yêu cầu).
11 JSON examples parse PASS. Publication/remote SHA/CI ở [handoff](handoff.md).
Không sửa M1–M2/dataset/PDF/cache/reference; không Gemini live/evaluation/web tests.
M2-09 DONE theo Tech Lead 2026-10-28 trên một PDF, chưa suy chất lượng tổng quát.
W-01 chờ Tech Lead review, không tự DONE hoặc bắt đầu W-02/M3.

Next action: Tech Lead nghiệm thu độc lập W-01.
