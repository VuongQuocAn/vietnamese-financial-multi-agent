# W-03 — Evidence và bàn giao REVIEW

Ngày 28/10/2026 (Asia/Bangkok), Research MVP Lean v3. Chỉ engineering/synthetic
validation; chưa đánh giá độ chính xác metadata/financial trên dataset thật.

## A. Git

Baseline W-02 sau fetch: `78a50c6285a37063463b30ec2e6c991ce23bf0b5`.
Nhánh `feat/w-03-pdf-upload-metadata`, stacked base `feat/w-02-web-skeleton`.
W-01/W-02 DONE. PR #1 OPEN base main, PR #2 OPEN base W-01; không tự merge.
Implementation/publication SHA, remote và CI ghi sau khi xác minh publication;
không gán CI W-02 cho W-03 hoặc ghi SHA tương lai. Thay đổi local có sẵn
web/next-env.d.ts khôi phục sau build, không stage.

## B. PDF upload

POST/GET documents, GET detail/file/status, PATCH metadata và POST process đã có.
PDF-only, magic/PDFium/encryption/size/page validation; default 50 MiB/200 pages.
Actual body bytes có bound kể cả chunked; UUID directories, SHA-256 identity,
filename chỉ display, atomic JSON cùng attempts/job. HTTP Range/416/no-store.
Origin allowlist, symlink/junction/containment và OS single writer lock.
Frontend chọn tệp/drag-drop, tên/dung lượng, XHR bytes progress, lỗi, navigate
detail; Dashboard/Documents đọc list thật. Kiểm tra proxy bằng PDF synthetic >11 MiB.

## C. Gemini metadata

Schema metadata_v1 riêng gồm năm fields, strict candidates/raw text/page và
resolved/uncertain/unresolved. Backend gắn content_id, reject nguồn không thuộc
batch; giữ candidates mâu thuẫn. Không suy ticker từ filename/năm hiện tại.
PDFium render độc lập trước khi biết năm, default 150 DPI, batch đầu 4 trang,
mở rộng các batch đến đủ nhất quán hoặc cap/budget; analyzed_pages/stop_reason.

Tái sử dụng GeminiAdapter + SharedLLMGateway + QuotaBudgetGuard +
CachedLLMService + LocalSchemaRegistry, model từ policy server. Mỗi ảnh một
user message theo Gateway v1, cùng request có nhiều ảnh. Schema thật đi qua
response_json_schema của adapter trong SDK stub test; runtime kiểm provenance.
Semantic-invalid response invalidate cache, không cache vĩnh viễn lỗi.

## D. Metadata review

Gợi ý AI riêng với nháp/confirmed values và audit edits origin=user. UI có
candidates/raw text/trang nguồn/status, form chỉnh/sửa. Ready chỉ khi confirmed
với company_name không rỗng và year integer 1..9999, ticker nullable. PATCH tăng
revision, stale revision hoặc job active trả 409. Namespace document:<UUID>,
runtime year chỉ sau confirm; không ghi đè FinancialContext của evidence M1–M2.

## E. Preflight jobs

Một worker, capacity mặc định 4 gồm running; queue đầy upload giữ PDF uploaded.
uploaded → queued → processing → needs_metadata → ready; lỗi runtime failed,
restart queued/processing interrupted. Polling detail mỗi 2 giây lúc active,
backoff lỗi; status endpoint riêng sẵn có. Không %/ETA giả. Retry thủ công, durable
Idempotency-Key/attempts trong snapshot; không job trùng hoặc auto call qua polling.
Giữ user-confirmed values và history khi retry. Chờ request hiện tại khi shutdown.

Guard/cache in-memory; consumed scope marker chống reset accounting qua restart.
Pending pages được persist trước call; known usage/unknown cost giữ theo batches.
Scope mới phải được operator budget bảo thủ tính prior/unknown usage; không tự
cho rằng marker/snapshot là durable quota guard. Chưa durable per-page replay.

## F. Validation

PASS local:

- 36 focused unit/integration: `tests/unit/test_web_documents.py tests/unit/test_api.py`.
  PDF raster-only từ Pillow, PDFium chứng minh không text layer. Flow upload →
  Vision suggestions (fake responses qua Gateway/guard/cache) → user edit → ready.
  Type/magic/corrupt/size/page, encryption gate (stub security revision), hash/UUID,
  traversal/symlink, validation/revision, candidates/provenance, state/concurrency/
  idempotency/restart, timeout/provider/quota, request/page caps và single writer.
  Adapter SDK shape test dùng GeminiAdapter thật + SDK stub, không gọi network.
- 139 regression Gateway/GeminiAdapter/quota/cache PASS; core không sửa.
- Ruff check toàn tree PASS; format check toàn tree PASS.
- TypeScript, ESLint, production build PASS.
- 11 Playwright Chromium tests PASS: chọn/drop, errors, upload/list/confirm/retry
  thật qua Next.js proxy/FastAPI, PDF >10 MiB, AI fixture/polling/revision conflict,
  desktop/mobile, shell/evidence/health. Synthetic API fixtures chỉ ở test.
- Screenshots metadata 1440/390 và shell 1440/1280/390 đã xem/kiểm overflow;
  screenshots/trace/runtime PDF đều local ignored, không commit.

Planning checker/diff/staged review trước commit; kết quả publication bổ sung sau.
Không chạy full local unit suite lặp lại; CI giữ Python 3.11/3.12 full unit suite.
Không thay/tắt CI. Có warning Starlette TestClient/httpx deprecation, không test failure.

Live Gemini smoke: **NOT RUN**. Key file do người dùng chỉ định đã được ignore,
nhưng chưa có project-policy/budget/exclusive accounting scope W-03 mới được
xác nhận. Policy local tìm được thuộc pilot cũ, không tự tái cấp fresh budget.
Không gửi live requests; actual model/pages/usage/metadata live: N/A, calls=0.
Configured model mặc định hiện hành gemini-3.5-flash-lite không phải live evidence.

## G. Local demo

[Usage/config chi tiết](w-03-usage.md), [local development](local-development.md).

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn vietnamese_financial_multi_agent.api.main:app --host 127.0.0.1 --port 8000
```

Terminal khác tại web: `npm.cmd ci`, `npm.cmd run dev`; mở 127.0.0.1:3000,
upload PDF scan → review gợi ý (hoặc điền tay khi Gemini chưa cấu hình) → confirm.
Live cần WEB_GEMINI_CONFIG và GEMINI_API_KEY_FILE với binding/budget đã xác minh;
[example an toàn](../../configs/web-metadata.example.json) mặc định confirmations=false.

## H. Risks / W-04

Một local process/worker, không public/multiuser auth. Quota/cache không durable,
scope marker cần operator recovery; retry phân tích lại từ đầu, cache-only durable
replay chưa có. Corrupt snapshot fail closed, cần operator khôi phục. PDFium page
render capped, malformed runtime có thể failed dù file mở được lúc upload.
Provenance là page-level, không bbox hoặc tự chứng minh raw_text đúng pixels.
Live recognition chưa được đánh giá. W-04 mới discovery/extraction/session
orchestration, W-05 mới PDF.js viewer; không financial evidence giả hoặc mở
Evidence Explorer như đã extraction. Không M3 và không đổi pipeline M1–M2.

## I. Final status

**W-03 — REVIEW**. Chờ Tech Lead nghiệm thu độc lập trước DONE.
Next action: Tech Lead nghiệm thu độc lập W-03.
