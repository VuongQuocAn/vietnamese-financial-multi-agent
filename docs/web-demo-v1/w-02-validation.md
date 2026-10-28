# W-02 — Bằng chứng triển khai

Ngày 28/10/2026 (Asia/Bangkok). Scope engineering/UI skeleton; không financial
evaluation. Trạng thái REVIEW, chưa Tech Lead nghiệm thu.

## Git và dependency

- Baseline W-01 DONE: `31ca5704c388b31ac102b19577b030fcb1026628`, fetch trước
  triển khai, working tree sạch. PR #1 OPEN/chưa merge, không CI vì [skip ci].
- Implementation: `22c48a5897350673d6082d6d9868f24df520c1a9`, đã commit/push;
  `git ls-remote` khớp exact SHA trên feat/w-02-web-skeleton.
- [PR #2](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/2)
  OPEN, base docs/w-01-web-demo-design. Đây là stacked development; không merge
  PR #1/#2. Sau dependency merge phải kiểm tra ancestry rồi retarget main để
  tránh lặp commits. Connector tạo PR trả 403; GitHub CLI tạo thành công.
- Sáu Stitch assets, src/core/accounting/document_processing không đổi so với
  baseline. Không stage dữ liệu/secrets/node_modules/.next/ảnh browser.

## Local validation

Môi trường Node 24.14.0, Python 3.12.0; Next.js 16.4.3, React 19.3.1,
Tailwind 4.3.3, TypeScript 5.9.3, FastAPI 0.162.0, Uvicorn 0.54.0.
ESLint 9.39.5 tương thích peer ranges của plugins trong eslint-config-next;
npm báo deprecated (ESLint 10 chưa được các peer plugins này khai hỗ trợ).
Dependencies frontend có lockfile; `npm ci` PASS, audit 0 vulnerabilities tại
thời điểm cài. Các cảnh báo không được coi là errors hoặc bị tắt đi.

| Check | Kết quả |
| --- | --- |
| npm run typecheck (next typegen + tsc --noEmit) | PASS |
| npm run lint | PASS, 0 errors/warnings |
| npm run build | PASS; /, /documents, /evidence, /ai-workspace |
| npm run test:smoke trên production build | 5 PASS |
| API/package/planning targeted unit tests | 16 PASS |
| Full local unit suite bổ sung | 1469 PASS, 2 SKIP, 633.81s |
| python -m ruff check . | PASS |
| python -m ruff format --check src tests scripts | PASS, 130 files |
| python -m ruff format --check . | FAIL baseline, chi tiết bên dưới |
| python scripts/check_planning.py | PASS, 88 tasks |
| git diff --check và staged diff check | PASS |

Hai skip local là filesystem Windows không phân biệt case và không hỗ trợ FIFO.
Một cảnh báo upstream Starlette TestClient khuyến nghị httpx2; tests vẫn PASS
với httpx được FastAPI hỗ trợ. Không cài thêm client mới chỉ để tắt warning.

Smoke gọi thật FastAPI qua Next rewrite `/api/health`, đúng JSON
`{"status":"ok","service":"financial-ai-api"}`, không Gemini key/PDF/database.
Browser kiểm navigation/active link/collapse, upload disabled, empty documents,
Explorer B01–B09/Graph, slider và tabs bằng keyboard, AI Coming Soon không chat.
Fixture bảng chỉ trong tests: kỳ động, mã `01`, zero `0`, dash `—`, missing và
unmapped/quality text giữ nguyên, không parse/scale số tiền hoặc tạo runtime facts.

Screenshots dashboard/Explorer tại 1440×900, 1280×900 và 390×900 đã được tạo;
đã xem trực tiếp dashboard/Explorer desktop và dashboard mobile, đối chiếu hai
PNG Stitch. Sửa mobile preview sau lần xem đầu, chụp/xem lại. Font Be Vietnam Pro
local, navy/light/sidebar/upload/recent/AI preview và PDF trái 45% phù hợp handoff.
Không so khớp pixel; ảnh Stitch có dữ liệu còn skeleton dùng empty states.
Artifacts ở web/test-results/ bị ignore. Không broken resources/page errors
trong smoke chính; các routes được kiểm response 200 và không tràn ngang viewport.

## Global format và CI

Ruff 0.17.2 hiện kiểm Python code fences trong Markdown. `git show` exact
baseline đưa vào formatter tái hiện FAIL ở docs/web-demo-v1/architecture.md:
code example dòng gọi process_financial_pdf cần tách arguments thành từng dòng.
Bốn tài liệu cũ khác chỉ báo newline CRLF trong working copy Windows; blobs Git
của bốn file này PASS. Không sửa tài liệu W-01 đã nghiệm thu ngoài scope hoặc
thay/skip quality gate để che lỗi.

[CI 40701696004](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40701696004)
trên exact implementation SHA được kích hoạt qua PR #2. Python 3.11/3.12 FAIL
ở Check formatting, unit tests/planning sau đó SKIPPED; không gọi đó là CI unit
PASS. Web skeleton SUCCESS gồm typecheck/lint/build và browser/proxy (5 PASS).
Đã kiểm steps và log Python 3.12: đúng một file architecture code fence bị format,
khớp local baseline reproduction. Toàn workflow kết thúc FAILURE do Python gates.
Không sửa required checks hoặc tự chạy lại khi chưa có thay đổi khắc phục.

## Giới hạn và bàn giao

W-02 chỉ HTTP/UI skeleton. Upload, metadata preflight, sessions/worker/storage,
PDF.js, evidence API/source navigation và AI chưa có. Slider resize gọn thay cho
drag splitter; mobile dùng toggle pane. Không có financial quality claims.

Next action: Tech Lead nghiệm thu độc lập W-02 và quyết định xử lý lỗi format baseline.
