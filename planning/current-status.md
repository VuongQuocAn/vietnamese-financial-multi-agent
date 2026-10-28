# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

W-03 REVIEW — PDF Upload & Gemini Vision Metadata Preflight.
[Spec](tasks/W/W-03.md), [usage](../docs/web-demo-v1/w-03-usage.md).
Đã triển khai upload PDF thật, local storage/atomic snapshots, metadata-only
bounded worker, Gemini qua Gateway/quota/cache, metadata review/confirm và ready.
Không nối financial extraction W-04, không thay M1–M2 hoặc bắt đầu M3.

Baseline W-02 HEAD 78a50c6 sau fetch; W-01/W-02 DONE. Nhánh
feat/w-03-pdf-upload-metadata stacked trên feat/w-02-web-skeleton.
PR #1/#2 OPEN, chưa merge. Giữ thay đổi có sẵn web/next-env.d.ts ngoài commit.

Local: 36 focused unit/integration PASS; 139 Gateway/quota/cache regression PASS.
TypeScript/lint/build và 11 browser/proxy tests PASS, gồm PDF >10 MiB và mobile.
Live Gemini NOT RUN: chưa có scope ngân sách/project policy W-03 được xác nhận;
key có sẵn không tự chứng minh quota. Không dùng policy pilot cũ để reset guard.
CI và SHA publication cập nhật trong evidence/handoff sau push; chưa tuyên bố CI PASS.

Next action: Tech Lead nghiệm thu độc lập W-03.
