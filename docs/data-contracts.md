# Data contracts

M0-01 chỉ ghi nhận các khái niệm giao tiếp đã được mô tả trong task và báo cáo
giữa kỳ, Chương 4–5. Chưa có contract máy đọc được, JSON Schema, Pydantic model,
schema kế toán hoặc migration nào được phê duyệt trong repository này.

| Điểm bàn giao | Nội dung đã xác định ở mức khái niệm | Chi tiết còn thiếu |
| --- | --- | --- |
| PDF → xử lý tài liệu | Tài liệu gốc và metadata nguồn | Định danh, kiểu file hỗ trợ, manifest: `TBD` |
| Xử lý tài liệu → chuẩn hóa | Văn bản, bảng, vị trí nguồn và trạng thái chất lượng | Schema trích xuất, tọa độ và mã chất lượng: `TBD` |
| Chuẩn hóa → Canonical Evidence Layer | Structured Financial Facts, Text/Table Evidence, Source Provenance | Kiểu dữ liệu, trường bắt buộc, đơn vị chuẩn, mã chỉ tiêu: `TBD` |
| Canonical Evidence Layer → EF-EG | Bằng chứng và liên kết phục vụ truy nguyên, tính toán | Schema nút/cạnh, định danh và lưu trữ: `TBD` |
| Công cụ → tác nhân/kiểm chứng | Kết quả truy xuất hoặc phép tính kèm bằng chứng nguồn | Chữ ký công cụ, lỗi, serialization: `TBD` |
| Tác nhân → kiểm chứng | Candidate Claims và bằng chứng liên quan | Claim schema, tham chiếu bằng chứng: `TBD` |
| Kiểm chứng → ledger | Nhận định được chấp nhận, bằng chứng và lịch sử kiểm chứng | Schema ledger, versioning và lưu trữ: `TBD` |
| Ledger → đầu ra | Verified Claims và trích dẫn nguồn | Định dạng QA/report và citation contract: `TBD` |

## Các ràng buộc đã xác định

- Dữ liệu tài chính phải giữ source provenance xuyên suốt pipeline; cần truy
  nguyên được đến tài liệu và vị trí nguồn phù hợp (trang, bảng, ô hoặc đoạn).
- Phép tính phải truy được tới công thức và dữ liệu đầu vào để kiểm tra lại.
- Candidate claims chưa được coi là verified claims.
- Output chỉ sử dụng nhận định đã được xác minh trong ledger.
- Không tự bổ sung dữ liệu thiếu, schema hoặc quy tắc kế toán chưa được xác định.

Chương 5.3 nêu các khái niệm `SourceFact`, `TextEvidence`, `DerivedMetric`,
`Claim`, `EvidenceAnchor`, `VerificationRecord`. Đây chưa phải tên class hoặc
database tables được duyệt. Quy tắc null, độ chính xác số, làm tròn, versioning,
trạng thái lỗi và backward compatibility đều là `TBD`.

Contract cụ thể phải được làm rõ và cập nhật cùng tài liệu liên quan trước khi
triển khai module sử dụng; không suy ra schema từ tên biến trong `.env.example`.
