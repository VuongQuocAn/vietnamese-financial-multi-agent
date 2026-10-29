# Demo Web V1 — 5–7 phút

Chuẩn bị PDF scan BBS_2025 thực (24 trang), dependencies theo
[local development](local-development.md). Không đưa PDF/key/storage vào Git.

1. **0:00–0:45 — Khởi động:** chạy `.\dev.ps1`, mở
   <http://127.0.0.1:3000>. Nếu dùng storage nghiệm thu riêng, đặt
   `$env:WEB_STORAGE_ROOT` tới bản sao storage đã chuẩn bị trước khi khởi động.
2. **0:45–1:45 — Tài liệu và metadata:** với demo live, upload PDF qua nút
   “Tải lên và nhận diện”; đây là thao tác gọi Gemini. Xem tên doanh nghiệp,
   năm và nguồn metadata; không cần ticker/project ID. Nếu thiếu hoặc không chắc
   chắn, dùng “Chỉnh sửa thông tin”. Auto-accepted chỉ là chấp nhận metadata
   theo nguồn, chưa xác minh số liệu tài chính.
3. **1:45–2:30 — Phân tích:** live bấm “Phân tích báo cáo” đúng một lần và xem
   số trang nhận diện/xử lý thực. Có thể mất nhiều phút, vượt thời lượng demo.
   Nếu quota hết, dừng live và nói rõ trạng thái partial/failed; không bấm retry
   liên tục. Với demo persisted, mở tài liệu đã xử lý từ danh sách, bỏ qua upload
   và nút phân tích; nói rõ đang đọc kết quả lưu từ lần chạy trước, không gọi Gemini.
4. **2:30–4:30 — Bảng và nguồn:** bấm “Xem PDF”, chọn B02, xem hai kỳ theo
   backend. Chọn một ô: URL đổi `?page=7`, PDF tới trang 7. Source Details giữ
   raw/normalized, kỳ, unit/scale, source pointer, quality và “Chưa xác minh”.
   Thử B01 trang 5–6, B03 trang 8; giữ cả unmapped/insufficient và ô thiếu.
   Không tự coi dash/missing là zero hoặc tự quy đổi đơn vị.
5. **4:30–5:15 — Giới hạn:** chọn B09, thấy inventory trang 9–24 và thông báo
   chưa trích xuất thuyết minh. Extracted evidence là dữ liệu có nguồn;
   quality đánh giá khả năng sử dụng với caveats; cả hai chưa phải verified
   financial facts. Completed là trạng thái xử lý kỹ thuật, không phải accuracy.
6. **5:15–6:30 — Persistence:** Ctrl+C, chạy lại cùng storage, mở lại danh sách,
   metadata, bảng và một ô nguồn. Chỉ đọc lại, không bấm nhận diện/phân tích.
   Khi đổi metadata sau extraction, kết quả cũ phải có cảnh báo stale. Explorer
   dùng “Tải lại dữ liệu” thủ công nếu vừa hoàn tất xử lý ở màn hình khác.

Nếu viewer lỗi/IDM can thiệp: dùng “Thử tải PDF lại” hoặc “Mở PDF gốc”; kiểm tra
tiện ích trong trình duyệt người dùng. Chromium smoke không chứng minh IDM đã hết lỗi.
Nếu chưa có snapshot, vẫn xem PDF được; không mô tả là đã có bảng hoàn chỉnh.

Kiểm tra đọc lại PDF thực tùy chọn (provider phải bị vô hiệu trên storage bản sao):

```powershell
Set-Location web
$env:WEB_BASE_URL = 'http://127.0.0.1:3000'
$env:W07_REAL_DOCUMENT_ID = '<UUID tài liệu đã xử lý>'
npm.cmd run test:smoke -- tests/acceptance.spec.ts
```

Test bỏ qua nếu không cấu hình UUID; không có dữ liệu giả thay cho bằng chứng PDF
thực. Kết quả thực nghiệm và hạn chế nghiệm thu ghi trong [W-07](../../planning/tasks/W/W-07.md).
