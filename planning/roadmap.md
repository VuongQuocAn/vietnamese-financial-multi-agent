# Lộ trình phát triển

## Nền tảng M0

| Mốc | Kết quả | Trạng thái |
| --- | --- | --- |
| M0-01 | Skeleton modular monolith, cấu hình phát triển, tài liệu, Git và CI | Hoàn thành |
| M0-02 | Dataset local trong `data/`, cấu hình đường dẫn, bảo toàn và loại dữ liệu khỏi Git | Hoàn thành; commit đã trên GitHub, CI đạt |
| M0-03 | Đồng bộ trạng thái, quy tắc lâu dài và kế hoạch phát triển | Hoàn thành; commit/push và CI đã xác minh |

Bằng chứng commit/CI và acceptance criteria nằm trong
[`current-status.md`](current-status.md) và [`tasks.md`](tasks.md).

## M1 — Các task dự kiến, chưa bắt đầu

Bốn task dưới đây là đề xuất lập kế hoạch trong M0-03 để chuẩn bị đầu vào cho
Offline Pipeline. Chưa được coi là yêu cầu triển khai hoặc contracts đã duyệt.
Phạm vi cuối cùng, người phụ trách, lịch thực hiện và acceptance criteria chính
thức cần được xác định trong yêu cầu giao từng task; hiện là `TBD`.

### M1-01 — Dataset Inventory & Provenance Review

- Mục tiêu: xác định dataset local thực có và khả năng truy nguyên nguồn trước
  khi thiết kế adapter hoặc schema.
- Phạm vi dự kiến: kiểm kê metadata theo mã/năm, loại file và liên kết nguồn
  có sẵn; khảo sát một tập mẫu JSON/ảnh phù hợp, ghi rõ dữ liệu thiếu hoặc mơ hồ.
- Đầu ra dự kiến: manifest local nằm ngoài Git, tài liệu tổng hợp corpus và
  khoảng trống provenance; không sao chép nội dung tài chính vào tài liệu public.
- Tiêu chí đề xuất: manifest đối chiếu được số file/dung lượng; phân biệt dữ
  liệu quan sát được với thông tin chưa xác minh; raw/OCR không đổi.
- Phụ thuộc: nền tảng M0 đã hoàn tất. Trạng thái: **Dự kiến, chưa bắt đầu**.

### M1-02 — Data Contracts & Path Mapping Design

- Mục tiêu: làm rõ giao tiếp với dữ liệu OCR và cách giữ provenance trên local.
- Phạm vi dự kiến: dự thảo contract đầu vào OCR, tham chiếu nguồn, quy tắc
  ánh xạ đường dẫn Colab và lỗi thiếu/mơ hồ; đối chiếu ranh giới module hiện có.
- Đầu ra dự kiến: cập nhật thiết kế contracts và các trường hợp cần kiểm chứng;
  ghi `TBD` cho thông tin chưa xác định, chưa tự tạo schema kế toán chi tiết.
- Tiêu chí đề xuất: mỗi khái niệm nguồn có cơ sở từ M1-01; quy tắc ánh xạ giữ
  nguyên JSON gốc, xử lý đường dẫn không tồn tại/trùng tên và không thoát gốc.
  Contract phải được duyệt trước khi task sau triển khai dựa vào nó.
- Phụ thuộc: M1-01. Trạng thái: **Dự kiến, chưa bắt đầu**.

### M1-03 — Configuration & Read-Only OCR Adapter

- Mục tiêu: cung cấp cấu hình dùng chung và đọc kết quả OCR có sẵn theo contract
  đã được duyệt, không xử lý OCR lại.
- Phạm vi dự kiến: cấu hình đường dẫn trong `core`, ánh xạ nguồn và adapter đọc
  trong `document_processing`; vị trí interfaces cụ thể theo thiết kế M1-02.
- Đầu ra dự kiến: bộ nạp cấu hình, adapter và xử lý lỗi với provenance được giữ
  nguyên; không hardcode đường dẫn Windows/Colab hoặc thêm lời gọi LLM.
- Tiêu chí đề xuất: kiểm thử đường dẫn tương đối/cấu hình môi trường, JSON lỗi,
  file thiếu, tên trùng và nguồn nằm ngoài gốc; đọc dữ liệu không ghi lại raw/OCR.
- Phụ thuộc: M1-02 và contracts đã được duyệt. Trạng thái: **Dự kiến, chưa bắt đầu**.

### M1-04 — Extraction Quality Validation & Pilot

- Mục tiêu: kiểm tra khả năng sử dụng dữ liệu trích xuất trước chuẩn hóa kế toán.
- Phạm vi dự kiến: validation cấu trúc, liên kết JSON–ảnh và vị trí nguồn theo
  contract; chạy pilot trên tập con được xác định khi giao task.
- Đầu ra dự kiến: báo cáo chất lượng/issue có provenance, kết quả pilot local
  ở vị trí bị Git bỏ qua; không sửa dữ liệu gốc để làm hết lỗi.
- Tiêu chí đề xuất: phát hiện trường hợp thiếu file hoặc cấu trúc không hợp lệ
  theo contract; báo cáo phân biệt lỗi dữ liệu và giới hạn kiểm tra; kiểm thử
  tương ứng đạt. Bộ mẫu, ngưỡng đạt và quy tắc chi tiết hiện là `TBD`.
- Phụ thuộc: M1-03. Trạng thái: **Dự kiến, chưa bắt đầu**.

## Định hướng sau M1

Thứ tự phụ thuộc theo kiến trúc và Chương 8.4 của báo cáo giữa kỳ:

1. Hoàn thiện đầu vào tài liệu và chuẩn hóa kế toán, duy trì source provenance.
2. Xây dựng Canonical Evidence Layer và EF-EG.
3. Phát triển Shared Executable Tool Space và hỏi đáp cơ bản.
4. Tích hợp Planner, Supervisor và các tác nhân chuyên môn.
5. Kiểm chứng claim, Verified Claim Ledger và tạo báo cáo có dẫn nguồn.
6. Tích hợp, benchmark và ablation trên QA/report.

Đây là định hướng, không phải chức năng đã triển khai. Không thay đổi pipeline,
module boundaries hoặc contracts được duyệt. LLM Gateway dùng chung cần task
riêng trước khi thêm Gemini hoặc nhà cung cấp khác; mọi tích hợp phải giữ cơ chế
đổi model, structured outputs và quản lý chi phí. Không bắt đầu công việc M1
hoặc các hướng tiếp theo trong M0-03.
