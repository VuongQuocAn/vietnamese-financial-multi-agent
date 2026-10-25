# Quyết định và điểm cần làm rõ

## Các lựa chọn cho M0-01

| Nội dung | Quyết định | Cơ sở |
| --- | --- | --- |
| Phạm vi | Chỉ skeleton, môi trường và tài liệu | Yêu cầu M0-01 |
| Ngôn ngữ | Python 3.11+ | Yêu cầu M0-01 |
| Kiến trúc | Modular monolith, Offline → Online → Output | Yêu cầu M0-01 và báo cáo Chương 4–6 |
| LLM | Gateway dùng chung; hỗ trợ đổi model, structured outputs và chi phí | Yêu cầu M0-01; chưa triển khai |
| Đầu ra | QA và báo cáo chỉ dùng nhận định trong Verified Claim Ledger | Báo cáo Chương 4.5, 5.7 |
| Đóng gói | setuptools; distribution `vietnamese-financial-multi-agent`, namespace `vietnamese_financial_multi_agent` ánh xạ vào `src/` | Lựa chọn thiết lập M0-01, giữ cây thư mục yêu cầu và tránh import tên chung |
| Kiểm tra | Ruff cho lint/format; pytest cho smoke tests cài đặt/import | Lựa chọn thiết lập tối thiểu M0-01 |
| Dependencies | Không có runtime dependency; dev chỉ có Ruff và pytest | Không cài thư viện AI khi chưa cần |
| CI | Kiểm tra package thường, lint/format và unit tests trên Python 3.11/3.12 | Xác minh mức Python tối thiểu và bản có tại máy |
| Tài liệu | Tiếng Việt; identifiers/tên code bằng tiếng Anh | Quy tắc nhất quán trong M0-01 |
| Git | Nhánh `main`, repository private; dữ liệu hiện có và tài liệu gốc nằm ngoài tập commit | Yêu cầu M0-01 |

Các khoảng phiên bản dev nằm trong `pyproject.toml`; chưa có lockfile. Phiên bản
đã kiểm tra sẽ được ghi trong trạng thái task. Chính sách khóa dependency cho
thực nghiệm tái lập là `TBD` trước khi triển khai benchmark.

Đã kiểm tra GitHub của `VuongQuocAn`: chưa có repository đúng tên
`vietnamese-financial-multi-agent` tại thời điểm khởi tạo. Repository sẵn có
`Mutil_Agent_Financial_Report` là public, đã có triển khai theo kiến trúc C1–C5;
không phù hợp với yêu cầu skeleton private và pipeline mới của M0-01. Giữ nguyên
repository đó, tạo repository private theo đúng tên được yêu cầu.

## Các vấn đề TBD

- Schema dữ liệu, provenance, facts, EF-EG, claim, ledger và versioning contracts.
- Backend lưu trữ, engine đồ thị, framework API, công cụ OCR và thư viện điều phối.
- SDK Gateway, Gemini model, nhà cung cấp bổ sung, hạn mức và cấu hình chi phí.
- Quy tắc kế toán, bảng ánh xạ, dung sai số học và điều kiện kiểm chứng chi tiết.
- Dataset chính thức, quyền sử dụng, manifest, chia tập và quy trình chú giải.
- Ngưỡng đánh giá, ngân sách thực nghiệm và baseline chốt triển khai.
- Phạm vi tuân thủ quy định: tên đề tài trong M0-01 có nội dung này, trong khi
  Chương 1 của báo cáo giữa kỳ nói kiểm tra tuân thủ pháp lý không thuộc phạm vi
  nghiên cứu chính. Giữ tên đề tài theo yêu cầu mới nhất; chưa tự chọn văn bản
  pháp luật, luật kiểm tra hay module tuân thủ cho đến khi phạm vi được làm rõ.

Không dùng danh sách công nghệ được đề xuất trong báo cáo như quyết định đã
được duyệt. Không tự mở rộng phạm vi trong task khởi tạo.
