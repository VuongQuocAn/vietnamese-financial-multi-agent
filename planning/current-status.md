# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

W-03 REVIEW — final refinement auto-first metadata và key rotation.
Tên/năm có nguồn rõ tự ready, ticker tùy chọn; accepted/auto khác confirmed/user.
UI Hệ thống đề xuất, form tùy chọn, retry khi thiếu. Chỉ key file, bỏ manual
project/policy/fingerprint/scope; một cap ứng dụng chung cho keys, counters durable.
Core/M1–M2/Stitch/CI giữ nguyên; không W-04/M3/merge.

Nhánh feat/w-03-pdf-upload-metadata, baseline refinement f617e68.
PR #1/#2 OPEN, #3 draft OPEN base W-02. Bảo toàn next-env local ngoài stage.
[Spec](tasks/W/W-03.md), [usage](../docs/web-demo-v1/w-03-usage.md),
[evidence](../docs/web-demo-v1/w-03-validation.md).

Live synthetic scan 2 trang PASS: model gemini-3.5-flash-lite, nguồn trang2,
tên/năm2025/scope separate, không ticker vẫn ready/auto; user edit/revision PASS.
Tổng 3 attempts: 2 HTTP400 ban đầu + 1 success (2805 tokens), không thêm live calls.
Không đánh giá accuracy dataset thật. 8 browser documents PASS; Python focused
44 cases, lint/format/TypeScript/ESLint/build/planning/diff kiểm trước publication.
CI baseline b494788 SUCCESS là lịch sử, không gán cho refinement chưa push.

Next action: Commit/push refinement và xác minh CI.
