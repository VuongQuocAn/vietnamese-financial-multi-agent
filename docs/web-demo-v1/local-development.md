# Chạy Web Demo V1 trên Windows

W-03 bổ sung upload PDF/storage/preflight/review trên skeleton Next.js + FastAPI.
Không cần Docker/database; upload và manual confirmation chạy không cần key.
Cấu hình Gemini server-side, limits, retry/restart và luồng scan PDF tại
[W-03 usage](w-03-usage.md). Financial extraction M1–M2 chưa nối vào HTTP layer.
Thiết kế theo [UI handoff](ui-handoff.md), [kiến trúc](architecture.md).

Yêu cầu Python 3.11+ và Node.js 24 LTS (package web yêu cầu Node >=24).
Các lệnh PowerShell dưới đây bắt đầu từ thư mục repository. Dùng `npm.cmd`
để tránh phụ thuộc execution policy của script npm.ps1.

## Cài đặt

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Set-Location web
npm.cmd ci
Copy-Item .env.example .env.local
Set-Location ..
```

Nếu chỉ có Python 3.11, thay `py -3.12` bằng `py -3.11`. Tái sử dụng `.venv`
đã có; không cần tạo lại. Nếu `.env.local` đã tồn tại, giữ cấu hình hiện có.
`web/.env.example` chỉ chứa `BACKEND_URL=http://127.0.0.1:8000`, server-only;
không có secret/NEXT_PUBLIC key. Khi đổi URL cần restart Next.js; production
rewrite được xác định khi build nên cần build lại nếu thay đổi backend URL.

## Khởi động

Terminal 1 tại repository:

```powershell
.\.venv\Scripts\python.exe -m uvicorn vietnamese_financial_multi_agent.api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 tại repository:

```powershell
Set-Location web
npm.cmd run dev
```

Mở <http://127.0.0.1:3000>. Có thể chuyển bốn trang, thu/mở sidebar ở desktop,
đổi tabs B01/B02/B03/B09/Graph, chỉnh độ rộng PDF bằng slider/keyboard và chuyển
khung xem trên mobile. Upload PDF thật từ Dashboard/Documents, danh sách từ API,
review metadata tại `/documents/[id]`. Evidence còn rỗng; AI Coming Soon.
Font Be Vietnam Pro tiếng Việt được đóng gói local; không fetch Google Fonts.

Kiểm tra backend và proxy từ terminal khác:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:3000/api/health
```

Cả hai trả `status=ok`, `service=financial-ai-api`. Proxy cùng origin nên không
cần CORS. Nếu backend chưa chạy, UI vẫn mở được; proxy health sẽ không thành công.
Không có trạng thái kết nối giả trong dashboard.

Nhấn `Ctrl+C` ở từng terminal để dừng hai dịch vụ. Nếu port bận, dừng instance
cũ của chính bạn; không tự kill tiến trình không rõ nguồn. Backend đổi port thì
cập nhật BACKEND_URL; frontend scripts mặc định cố định 3000 và bind 127.0.0.1.

## Kiểm thử

Tại repository:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest tests/unit/test_api.py tests/unit/test_package.py tests/unit/test_check_planning.py
.\.venv\Scripts\python.exe scripts/check_planning.py
git diff --check
```

Tại `web/`:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npx.cmd playwright install chromium
```

Để smoke trên production build: dừng dev server, giữ backend chạy, chạy
`npm.cmd run start` ở terminal 2, rồi `npm.cmd run test:smoke` tại `web/` ở
terminal 3. Tests kiểm tra routes, navigation, tabs/resize keyboard, empty states,
font, không runtime errors/broken resources, layout 1440/1280/390 và proxy health.
Fixture bảng tổng hợp chỉ ở tests, giữ raw zero/dash/missing; không phải đánh giá
chất lượng tài chính. Screenshots/trace ở `web/test-results/` bị Git ignore.

CI giữ Python 3.11/3.12 full unit suite và thêm web typecheck/lint/build/browser/
proxy. Không dùng kết quả local thay cho CI hoặc Tech Lead nghiệm thu.
