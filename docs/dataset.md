# Dữ liệu và nguồn gốc

Đầu vào của hệ thống là báo cáo tài chính PDF; dữ liệu sau xử lý phải duy trì
khả năng truy nguyên về tài liệu, trang, bảng, ô hoặc đoạn nguồn.

## Dữ liệu hiện có

Workspace tại thời điểm M0-01 có `Financial_Report/`, `Financial_Report_OCR/`
và tài liệu tham chiếu `docs/report_midterm.docx`. Các mục này đã có trước task,
được giữ nguyên tại máy và loại khỏi Git. Chưa xác minh chất lượng, tính đầy đủ
hoặc provenance của từng file trong các thư mục này.

Báo cáo giữa kỳ Chương 8.1 ghi nhận 1.005 báo cáo logic, 1.006 tệp PDF, 202 mã
chứng khoán trong giai đoạn 2021–2025, khoảng 11,8 GB. Đây là số liệu được báo cáo
trong tài liệu, không phải kết quả kiểm kê hay xác nhận toàn bộ dataset ở M0-01.
Không coi những file đang có trong workspace là toàn bộ corpus nghiên cứu.

## Quy tắc lưu trữ

- Không đưa dữ liệu từ Google Drive vào Git repository.
- Không commit PDF, tập OCR, dataset lớn, database, model checkpoint hoặc artifacts.
- `data/samples/` hiện chỉ theo dõi `.gitkeep`; chưa có mẫu được duyệt để đưa vào Git.
- Dữ liệu gốc, dữ liệu xử lý và bằng chứng có thể ở ngoài repository; các biến
  `RAW_DATA_DIR`, `PROCESSED_DATA_DIR`, `EVIDENCE_DATA_DIR` chỉ là cấu hình dự kiến.
- Không tạo dữ liệu tài chính giả rồi mô tả như dữ liệu thật.
- Khi xử lý dữ liệu ở task sau, phải lưu nguồn và vị trí trích xuất; không làm
  mất liên kết nguồn khi chuẩn hóa hoặc tính toán.

## Nội dung TBD

Danh sách corpus chính thức, quyền sử dụng/phân phối, nguồn tải từng tài liệu,
manifest, checksum, schema provenance, quy trình kiểm tra chất lượng và danh sách
chia tập là `TBD`. M0-01 không tải thêm, chuyển đổi hoặc nhập dữ liệu vào hệ thống.
