# Dữ liệu và nguồn gốc

Hệ thống hướng đến xử lý báo cáo tài chính với khả năng truy nguyên về tài liệu,
trang, bảng, ô hoặc đoạn nguồn. M0-02 chỉ tổ chức lại dữ liệu local đã có; không
chạy lại OCR, gọi Gemini hoặc thay đổi nội dung dữ liệu.

## Cấu trúc local

```text
data/
├── raw/
│   └── Financial_Report/
│       ├── BBS/{2021,2022,2023,2024,2025}/
│       ├── BCC/{2021,2022,2023,2024,2025}/
│       └── BED/{2021,2022,2023,2024,2025}/
├── processed/
│   └── Financial_Report_OCR/
│       ├── BBS/{2021,2022,2023,2024,2025}/
│       ├── BCC/{2021,2022,2023,2024,2025}/
│       └── BED/{2021,2022,2023,2024,2025}/
├── normalized/
├── canonical/
└── samples/
    └── .gitkeep
```

Ký hiệu `{2021,...,2025}` biểu diễn năm thư mục năm riêng biệt. Mọi cấu trúc con
bên dưới được giữ nguyên. Hai thư mục dữ liệu không còn ở thư mục gốc repository.

| Vị trí | Vai trò và trạng thái |
| --- | --- |
| `raw/Financial_Report/` | Dữ liệu đầu vào có sẵn, hiện gồm 500 ảnh PNG; không sửa nội dung |
| `processed/Financial_Report_OCR/` | Kết quả OCR có sẵn gồm JSON, JSONL, PNG và log; không sửa nội dung |
| `normalized/` | Dành cho kết quả chuẩn hóa kế toán khi có task riêng; hiện rỗng |
| `canonical/` | Dành cho Canonical Evidence Layer khi có task riêng; hiện rỗng |
| `samples/` | Chỉ theo dõi `.gitkeep`; chưa có mẫu dữ liệu được duyệt để commit |

## Kết quả di chuyển M0-02

Di chuyển trong cùng ổ đĩa bằng thao tác đổi vị trí thư mục, không ghi đè đích.
Metadata toàn bộ file và thư mục đã được đối chiếu, bao gồm đường dẫn tương đối,
kích thước, thời gian sửa và định danh file/thư mục.

| Dataset | File trước | File sau | Byte trước | Byte sau |
| --- | ---: | ---: | ---: | ---: |
| `Financial_Report` | 500 | 500 | 1.490.251.896 | 1.490.251.896 |
| `Financial_Report_OCR` | 8.627 | 8.627 | 837.428.529 | 837.428.529 |
| Tổng | 9.127 | 9.127 | 2.327.680.425 | 2.327.680.425 |

Tổng khoảng 2,328 GB theo hệ thập phân. Hash SHA-256 của 18 file lấy mẫu trước/sau
khớp nhau; mẫu gồm 6 JSON, 6 PNG raw và 6 PNG processed, trải trên ba mã ở năm đầu
và năm cuối. Sáu JSON đọc được; 12 PNG xác minh cấu trúc và giải mã thành công.
Chỉ hash khoảng 16,6 MB mẫu, không hash toàn bộ dataset. Đây là kiểm tra bảo toàn
di chuyển và khả năng đọc mẫu, chưa phải đánh giá độ chính xác OCR hoặc kế toán.

Corpus trong báo cáo giữa kỳ Chương 8.1 lớn hơn dữ liệu local: tài liệu ghi nhận
1.005 báo cáo logic, 1.006 PDF, 202 mã trong 2021–2025, khoảng 11,8 GB. Các con số
đó là thông tin từ báo cáo, không phải kết quả kiểm kê M0-02. Không coi thư mục
local hiện có là toàn bộ corpus nghiên cứu hoặc khẳng định có PDF trong raw.

## Cấu hình đường dẫn

| Biến môi trường | Giá trị mẫu tương đối với gốc repository |
| --- | --- |
| `FINANCIAL_REPORT_DIR` | `data/raw/Financial_Report` |
| `FINANCIAL_OCR_DIR` | `data/processed/Financial_Report_OCR` |
| `NORMALIZED_DATA_DIR` | `data/normalized` |
| `CANONICAL_DATA_DIR` | `data/canonical` |

`.env.example` chỉ khai báo cấu hình dự kiến. Chưa có bộ nạp cấu hình trung tâm
hoặc DataPathResolver; không thêm implementation trong M0-02. Các biến cũ như
`RAW_DATA_DIR`, `PROCESSED_DATA_DIR` vẫn chỉ thư mục cha tương ứng.
`EVIDENCE_DATA_DIR` là cấu hình dự kiến từ M0-01, chưa có logic sử dụng hoặc
contract lưu trữ; không tự đồng nhất nó với dữ liệu canonical.

## Ánh xạ đường dẫn Colab sang local

Một số JSON OCR giữ đường dẫn tuyệt đối bắt đầu bằng `/content/drive/...`.
Đây là tham chiếu tại môi trường tạo dữ liệu, không bảo đảm dùng trực tiếp được
ở máy local. Không tìm/thay thế hoặc ghi lại JSON gốc.

Khi đối chiếu thủ công hoặc thiết kế resolver ở task sau:

1. Xác định thư mục gốc nguồn từ provenance hoặc cấu hình của lần chạy OCR;
   không đoán gốc dựa trên tên file.
2. Nếu đã xác nhận nguồn thuộc `Financial_Report`, lấy phần đường dẫn tương đối
   bên dưới gốc đó và nối với `FINANCIAL_REPORT_DIR`. Tương tự, tham chiếu đã
   xác nhận thuộc `Financial_Report_OCR` dùng `FINANCIAL_OCR_DIR`.
3. Diễn giải đường dẫn Colab theo dấu `/`; từ chối phần đuôi tuyệt đối hoặc có
   `..` thoát khỏi thư mục dữ liệu đã xác định.
4. Đối chiếu mã, năm và toàn bộ cấu trúc con; kiểm tra file local tồn tại.
   Không dùng riêng basename vì có thể trùng tên giữa các trang, mã hoặc năm.
5. Giữ ánh xạ bên ngoài JSON gốc. Nếu gốc nguồn chưa xác định hoặc không có file
   tương ứng, ghi nhận chưa ánh xạ được; không sửa hoặc tạo dữ liệu để lấp chỗ thiếu.

Các bước trên là hướng dẫn, chưa có resolver được triển khai hoặc xác nhận mọi
tham chiếu Colab đều ánh xạ thành công.

## Quy tắc Git và bảo toàn

- Repository hiện là public; dataset local không được phân phối qua Git.
- Bỏ qua toàn bộ `data/raw/`, `data/processed/`, `data/normalized/`,
  `data/canonical/`. Trong `data/`, chỉ `samples/.gitkeep` được theo dõi.
- Các thư mục bị bỏ qua, kể cả thư mục rỗng, không xuất hiện khi clone; tạo local
  khi cần và cung cấp dữ liệu riêng, không ghi đè dữ liệu đã có.
- Không đưa dữ liệu từ Google Drive, PDF, ảnh, OCR JSON/JSONL, database hoặc
  artifacts lớn vào Git. Không tạo dữ liệu tài chính giả rồi dùng như dữ liệu thật.
- Không chỉnh sửa raw hoặc kết quả OCR gốc; kết quả xử lý mới ở vị trí riêng
  được task xác định và phải duy trì source provenance.
- `.gitignore` không tự bỏ file đã được Git theo dõi. Nếu gặp trường hợp đó,
  chỉ bỏ khỏi index, giữ local; nếu dữ liệu/secrets từng vào lịch sử Git, báo cáo
  và không tự rewrite history hoặc force push.
- Manifest kiểm tra di chuyển chỉ lưu local trong thư mục bị Git bỏ qua;
  tài liệu chỉ ghi số liệu tổng hợp, không sao chép nội dung báo cáo tài chính.

## Nội dung TBD

Corpus chính thức, quyền sử dụng/phân phối, manifest nguồn, schema provenance,
chất lượng dữ liệu, các tập chia và contract chuẩn hóa/canonical vẫn là `TBD`.
