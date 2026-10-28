# W-03 — Upload PDF và metadata auto-first

Chạy Python 3.11+ với `pip install -e ".[dev]"`; frontend giữ dependencies W-02.
Từ root repository, PowerShell (ứng dụng không tự load .env):

```powershell
$env:GEMINI_API_KEY_FILE = 'src/api/api_key/api_gemini.txt'
.\.venv\Scripts\python.exe -m uvicorn vietnamese_financial_multi_agent.api.main:app --host 127.0.0.1 --port 8000
```

Terminal khác: `cd web`, `npm.cmd run dev`, mở <http://127.0.0.1:3000>.
Upload PDF từ Dashboard/Documents → hệ thống tự phân tích → ready khi tên công ty
và năm rõ ràng, không mâu thuẫn và có nguồn trang. Không cần ticker hoặc nhấn xác
nhận. Thông tin chi tiết hiển thị nguồn/raw text/candidates và nguồn gốc quyết
định; nút Chỉnh sửa thông tin là tùy chọn. Nếu thiếu căn cứ, UI ưu tiên Thử nhận
diện lại, người dùng có thể bổ sung. Ready chưa có nghĩa đã trích xuất tài chính.

## Key file và Free Tier

Chỉ cần đường dẫn key file; mỗi dòng một key. Dòng khác định dạng bị bỏ qua,
key trùng được gộp. Không project ID/name, fingerprint, policy JSON hoặc scope
thủ công. Có thể dùng GEMINI_API_KEY cho một key. Key luôn server-only, không
NEXT_PUBLIC, Git, logs hoặc snapshots. Restart để nạp lại danh sách keys.

Dùng key khả dụng hiện tại cho tới khi 429: cooldown ít nhất 60 giây (hoặc
retry-after lớn hơn), thử key kế tiếp. Authentication/authorization: tạm loại
key trong phiên. Mỗi request thử tối đa min(3, số key), không tự lặp vô hạn;
timeout/server error không tự gửi request thứ hai sang key khác. Hết keys hoặc
đạt cap: dừng rõ ràng, giữ PDF và cho retry thủ công.

Một pool chia sẻ **một cap ứng dụng**, default 15 attempts/phút, 500/ngày,
250000 reserved tokens/phút. Đây là cap bảo thủ theo reference user cung cấp,
không cam kết quota hiện hành của Google. Không nhân quota theo số keys; không
suy chúng thuộc project khác nhau. Mỗi rotated attempt cũng tính vào cap.
WEB_GEMINI_RPM/RPD/TPM/MAX_ATTEMPTS/COOLDOWN_SECONDS là tùy chọn cho operator.
Provider quota thực có thể thấp hơn; luôn tôn trọng 429/cooldown.

Dùng lại SharedLLMGateway, GeminiAdapter và CachedLLMService. Composition pool
có admission interface dùng GuardResult/QuotaLimits/Reservation của core. Không
dựng ProjectPolicy mapping_confirmed giả cho các Google project chưa biết:
QuotaBudgetGuard của M1–M2 vẫn giữ nguyên cho flows có project binding đã xác
nhận. Cache scope `web-local-free-pool` chỉ là namespace local single-user.
Metadata adapter gộp các user parts thành một lượt; không thay adapter/core M1–M2.

Key states/index/recent attempts/cooldown/error category ở bộ nhớ. Chỉ counters
chung được atomic persist trong `free-tier-usage.json` trước mỗi attempt, bảo
toàn qua restart, không key values. Usage unknown giữ reservation bảo thủ, không
coi unknown=0. Counter local không thấy usage từ ứng dụng khác; provider vẫn là
nguồn quota thực. Không xóa counter/đổi root để reset cap khi đã dùng.

Người dùng xác nhận các key Free Tier trong yêu cầu refinement. Theo
[Google pricing](https://ai.google.dev/gemini-api/docs/pricing), model hiện hành
gemini-3.5-flash-lite có Free Tier. Ứng dụng giữ nguyên model, không tự đổi model,
tier hoặc bật billing; GEMINI_MODEL khác default bị từ chối ở composition này.
Key file/SDK usage không chứng minh trạng thái billing của từng project; billing
vẫn phụ thuộc cấu hình tài khoản đã được người dùng xác nhận. Cost unknown được
giữ nguyên trong evidence, không tuyên bố API báo chi phí bằng 0.

## Auto-accept và provenance

metadata.accepted là điều kiện sẵn sàng; acceptance_origin=auto hoặc user.
metadata.confirmed chỉ biểu thị người dùng xác nhận, auto không giả confirmed.
Hai trường bắt buộc: company_name không rỗng, reporting_year integer 1..9999,
mỗi field resolved có một giá trị nhất quán, raw text và nguồn PDF phù hợp.
Ticker/period/scope unresolved được để null. Không suy từ filename/năm hiện tại.

Default batch 4 trang đầu, mở rộng tuần tự trong page/request caps khi core
metadata chưa đủ. Response invalid có thể tiếp tục batch sau. Candidate uncertain
cùng giá trị được làm rõ bởi nguồn resolved sau; nhiều giá trị mâu thuẫn vẫn giữ,
không tự chọn thắng. Dừng ngay khi core đủ căn cứ, không đợi ticker.

Schema phục vụ metadata_v2 được làm phẳng; Pydantic vẫn kiểm tra strict types,
candidate limits và provenance tại runtime. Auto-accept tăng metadata_revision,
lưu acceptance_history với attempt ID; user PATCH giữ API body cũ, tăng revision,
ghi edits origin=user, accepted=confirmed và origin=user. Không ghi đè gợi ý AI
hoặc user values khi retry. Re-preflight metadata origin=auto bỏ accepted cũ
trong lúc phân tích, chỉ chấp nhận lại khi đủ căn cứ mới. Job giữ input revision;
accepted_metadata_revision ghi revision mới được auto-accept.

needs_metadata hiển thị Cần bổ sung thông tin. Provider/quota/config/runtime lỗi
khi chưa có accepted metadata → failed. Restart active → interrupted; không tự
gọi lại. Snapshots W-03 cũ confirmed=true được đọc thành accepted/user, không
thay dữ liệu nguồn hoặc chạy migration dataset.

## Storage, limits và W-04

Giữ PDF-only/header/PDFium/encryption, default 50 MiB/200 trang và upload bytes
bound. UUID paths, containment, không symlink/junction, atomic snapshots, Range,
Origin allowlist và no-store. Một API process/worker, không thêm auth/framework.
Queue capacity 4 gồm running; đầy vẫn lưu PDF uploaded, cho retry sau.

WEB_STORAGE_ROOT default artifacts/web-demo-v1; WEB_MAX_UPLOAD_BYTES/MAX_PAGES,
WEB_PREFLIGHT_BATCH_SIZE/MAX_PAGES/REQUEST_LIMIT/DPI là tùy chọn như trước.
Counter snapshots/PDF/model telemetry đều ignored, không frontend/public/Git.
Next.js proxy cần cùng WEB_MAX_UPLOAD_BYTES nếu đổi; rebuild production frontend.

Runtime symbol luôn document:<UUID>, độc lập ticker. Metadata document không
ghi đè FinancialContext trong M1–M2. W-04 mới discovery/extraction; W-05 mới PDF.js
viewer. W-03 chỉ mở PDF/tab trang nguồn, không đưa financial evidence giả lên UI.

## Kiểm thử và live smoke

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_web_documents.py tests/unit/test_metadata_key_pool.py tests/unit/test_api.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe scripts/check_planning.py
git diff --check
```

Tại web: typecheck/lint/build và test:smoke khi backend/frontend production chạy.
Browser test phải dùng storage riêng và bỏ GEMINI_API_KEY_FILE/GEMINI_API_KEY
để không vô tình gọi live. CI giữ full Python 3.11/3.12, không thay quality gates.
Desktop ưu tiên 1440/1366; mobile chỉ kiểm không vỡ layout, không pixel-perfect.

Smoke live opt-in: `python scripts/smoke_web_metadata.py --live` sau khi đặt key
file. Tạo PDF raster synthetic 2 trang, không text layer/financial values/private
data; tối đa 3 provider attempts, xác minh tên/năm/scope/trang, tự ready và edit.
Có --attempt-cap 1 để chặn retry trong chẩn đoán. Không chạy benchmark M2-09.
[Evidence](w-03-validation.md) phân biệt lỗi ban đầu và successful live smoke.
