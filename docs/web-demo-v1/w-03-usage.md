# W-03 — Upload PDF và review metadata

Backend cần `pip install -e ".[dev]"` (thêm python-multipart); frontend giữ
dependencies W-02. Chạy từ root bằng PowerShell; không tự load file `.env`.

```powershell
$env:WEB_STORAGE_ROOT = 'artifacts/web-demo-v1'
.\.venv\Scripts\python.exe -m uvicorn vietnamese_financial_multi_agent.api.main:app --host 127.0.0.1 --port 8000
```

Terminal khác: `cd web`, `npm.cmd run dev`, mở <http://127.0.0.1:3000>.
Dashboard hoặc Documents → chọn/kéo thả một PDF → Tải lên và nhận diện → detail.
Tên/dung lượng hiện trước upload; progress chỉ từ XHR bytes thực, 100% nghĩa đã
gửi xong bytes, chưa có nghĩa Gemini đã xử lý xong. API validate PDF và queue
preflight trước trả 201, không giữ upload request chờ Gemini.

Không cấu hình Gemini: PDF vẫn được giữ, job về needs_metadata và UI nói rõ
Gemini chưa sẵn sàng; không tạo gợi ý giả. Điền tên công ty/năm, để ticker trống
được, rồi xác nhận → ready. Gemini có cấu hình: đợi worker phân tích, đọc từng
candidate/raw text/trang nguồn rồi chỉnh/xác nhận. Gợi ý AI và dữ liệu người dùng
lưu riêng. Ready mới là metadata đã xác nhận, chưa có financial evidence.

## Cấu hình Gemini server-side

Key file local người dùng cung cấp được Git ignore; backend chỉ đọc khi bật config.
Không gửi key qua frontend/NEXT_PUBLIC, không copy key vào policy JSON.

```powershell
Copy-Item configs/web-metadata.example.json artifacts/web-metadata.local.json
$env:WEB_GEMINI_CONFIG = 'artifacts/web-metadata.local.json'
$env:GEMINI_API_KEY_FILE = 'src/api/api_key/api_gemini.txt'
```

Hoặc dùng GEMINI_API_KEY từ process environment và key_index=0. File key chứa
mỗi key trên một dòng, có thể kèm dòng chú thích không khớp định dạng key.
key_index tính từ 0 trong các dòng key hợp lệ, không tự xoay key. Điền SHA-256
của **key đã xác minh thuộc project được chọn** vào credential_sha256 trong
policy local để tránh vô tình bind key khác; không phải hash PDF.

Các giá trị trong example chỉ minh họa, các confirmations mặc định false nên
không thể gọi live. Operator cần xác nhận account/project/credential mapping,
quota thực cho model đó, data export, giá và budget mới. Không tái sử dụng policy
pilot cũ để tự khẳng định scope mới còn nguyên quota. Model lấy nguyên từ policy;
GEMINI_MODEL nếu đặt phải khớp, không tự fallback sang model khác.

ProjectPolicy.budget bắt buộc. request_spending_upper_bound là trần mỗi request
được operator phê duyệt, giữ reservation khi cost unknown. Giá trị 0 chỉ hợp lệ
với tier=free và pricing_confirmed=true đã xác minh giá 0; không suy giá từ key.
Thiếu/sai cấu hình hoặc scope đã dùng → không dựng live service; UI cho điền
metadata thủ công. Không xuất exception/provider content ra HTTP.

Scope marker lưu exclusive trong `accounting-scopes/<hash>.json` trước gọi live;
một scope chỉ khởi tạo guard một lần. Restart không tự nhận lại budget đầy đủ.
Operator kiểm tra batches/usage/cost/pending_pages trong snapshots, trừ phần đã
dùng/unknown và cấu hình scope mới với quota/budget còn lại bảo thủ trước retry.
Không xóa marker để reset accounting. Guard/cache vẫn in-memory, marker không
biến chúng thành durable quota ledger. Khi shutdown chờ request hiện tại (timeout
120 giây), không chạy tiếp queue; restart đánh dấu job queued/processing interrupted.

## Giới hạn và storage

Mặc định PDF 50 MiB/200 trang; env WEB_MAX_UPLOAD_BYTES/WEB_MAX_PAGES.
Next.js proxy dùng WEB_MAX_UPLOAD_BYTES cùng default; nếu đổi phải đặt ở cả hai
process và build lại frontend production. Có multipart overhead 64 KiB. API giới
hạn actual body bytes kể cả chunked, chỉ một file; `%PDF-`, PDFium mở được,
không mã hóa, page count. Filename chỉ display, storage dùng UUID.

Một API process, một worker, OS lock cho writer; không chạy `--workers > 1`.
WEB_PREFLIGHT_CAPACITY=4 gồm cả job đang chạy; đầy queue vẫn giữ PDF uploaded,
job=null. Retry/process trả 429 + Retry-After. Retry chủ động với key mới, polling
không gửi lại Gemini. Exact Idempotency-Key/body replay trả cùng job, key khác
khi active trả 409. Sau terminal có thể preflight lại kể cả ready: không ghi đè
user values/confirmed/revision. Lịch sử gợi ý cũ giữ trong snapshot nội bộ.

WEB_PREFLIGHT_BATCH_SIZE=4 (1..8), DPI=150 (72..200), MAX_PAGES=200,
REQUEST_LIMIT=50 (1..200). Batch đầu là các trang đầu, mở rộng tuần tự đến cap
khi chưa resolved đủ cả năm fields. Ticker thiếu vẫn có thể cần xem hết PDF;
không yêu cầu người dùng nhập ticker. Dừng sufficient_evidence khi cả năm fields
resolved; conflict không tự chọn. Giới hạn render 16 triệu pixels/trang trước
allocation. Admission reserve ảnh theo tile cùng cơ sở M1, prompt bytes và 32768
output/thinking headroom; không phải số token provider báo. Tất cả qua
CachedLLMService → QuotaBudgetGuard → SharedLLMGateway → GeminiAdapter,
LocalSchemaRegistry kiểm tra structured output và runtime kiểm tra nguồn trang.

Storage: `documents/<UUID>/original.pdf`, `document.json` atomic temp/fsync/replace.
Một snapshot chứa metadata, current job, lịch sử attempts/idempotency và pending
intent/usage theo batch. Không chứa key/policy/credential alias. Không persist raw
provider response; chỉ candidates, issues và telemetry đã chọn. Web API ẩn fields
nội bộ bắt đầu `_`, không trả filesystem path. PDF original qua FileResponse có
Range/If-Range/416 và no-store. Root/ancestors/doc/file không được symlink/junction.
Local operator là trusted filesystem owner; chưa chống race từ hostile local OS.

Không tự xóa PDF/cache/snapshots theo TTL. Không lưu vào Git/public/dataset.
Snapshot corrupt làm request/startup fail closed, cần operator khôi phục bản lưu;
không tự bỏ qua corruption và gửi lại Gemini. Chưa có UI recovery/retention.

## Metadata và W-04

PATCH gửi toàn bộ năm fields, metadata_revision hiện tại và confirmed. Tên không
rỗng + năm integer 1..9999 là điều kiện confirm; ticker/period/scope nullable.
Mỗi PATCH tăng revision, ghi edits origin=user, không thay suggestions. Job active
hoặc revision stale trả 409. Nháp trở về needs_metadata, xác nhận về ready.
Runtime symbol luôn `document:<UUID>`, year chỉ được gán sau confirm, không phải
ticker. Metadata này không ghi đè context kỳ/phạm vi của evidence tài chính M1–M2.

POST process hiện **chỉ** operation=preflight; extract trả 422. W-04 mới xử lý
discovery/extraction B01/B02/B03, sessions/evidence. W-05 mới làm PDF.js viewer;
W-03 mở PDF gốc/trang nguồn trong tab browser. Không mở Evidence Explorer như
đã hoàn tất extraction. Không có %/ETA preflight hoặc confidence % tự tạo.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_web_documents.py tests/unit/test_api.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe scripts/check_planning.py
git diff --check
```

Tại web: `npm.cmd run typecheck`, `npm.cmd run lint`, `npm.cmd run build`.
Chạy backend với **storage riêng bị ignore và không WEB_GEMINI_CONFIG** cùng
frontend production `npm.cmd run start`, rồi `npm.cmd run test:smoke`.
Tests tạo PDF raster synthetic ở temporary directory, không có financial facts,
không commit PDF. Browser kiểm tra upload thật/proxy/manual ready/list và fixture
API synthetic riêng để kiểm tra candidates/polling/conflict; backend integration
chạy Vision responses giả qua Gateway/guard/cache. Không phải benchmark tài chính.
