# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

W-02 REVIEW — Frontend/Backend Skeleton & Local Development.
[Spec](tasks/W/W-02.md), [chạy local](../docs/web-demo-v1/local-development.md).
Next.js 16.4.3 / React 19.3.1, bốn routes, app shell, empty states, AI Coming
Soon; FastAPI 0.162.0 health + Next.js proxy. Không key/PDF/database, chưa upload
hoặc nối nghiệp vụ M1–M2. Không bắt đầu W-03/M3.

Dependency W-01 DONE theo Tech Lead APPROVED 28/10/2026. Baseline W-02 đã fetch,
working tree sạch, exact acceptance `31ca5704c388b31ac102b19577b030fcb1026628`.
PR #1 OPEN/chưa merge; không CI runs vì [skip ci], workflow không dispatch.
Stacked branch feat/w-02-web-skeleton; PR base docs/w-01-web-demo-design để
không lặp commits W-01. Không tự merge/force-push hoặc thay required checks.

Local typecheck/ESLint/build PASS, 16 targeted Python tests PASS, Ruff lint và
format Python PASS, planning 88 tasks PASS, browser/proxy smoke 5 PASS.
Đã xem screenshots dashboard/Explorer 1440, laptop 1280 và mobile 390; sửa
mobile AI preview sau quan sát. Giữ light/navy/sidebar và split 45/55 theo Stitch,
dùng font sans tiếng Việt local; không tuyên bố pixel-perfect hoặc financial accuracy.

Ruff 0.17.2 full-tree format FAIL có sẵn ở architecture W-01 (đã tái hiện trên
Git baseline); bốn tài liệu cũ khác báo do CRLF local. Không sửa tài liệu nghiệm
thu ngoài scope để che CI. Full unit suite bổ sung đang chạy; CI/remote cập nhật
trong checkpoint sau publication, chưa tuyên bố SUCCESS.

Next action: Tech Lead nghiệm thu độc lập W-02 và quyết định xử lý lỗi format baseline.
