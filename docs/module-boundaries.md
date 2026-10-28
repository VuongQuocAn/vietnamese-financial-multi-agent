# Ranh giới module

Đây là phân chia trách nhiệm cho skeleton M0-01, dựa trên pipeline được yêu cầu
và Chương 4–6 của báo cáo giữa kỳ. Chưa có interfaces hay schema triển khai.

| Module | Trách nhiệm dự kiến | Giới hạn |
| --- | --- | --- |
| `core` | Hạ tầng cấu hình và tích hợp dùng chung; vị trí dự kiến của LLM Gateway | Không sở hữu logic kế toán hay điều phối nghiệp vụ |
| `document_processing` | Đọc tài liệu, trích xuất nội dung và vị trí nguồn | Không đưa ra nhận định tài chính |
| `accounting` | Chuẩn hóa chỉ tiêu, giá trị, đơn vị, kỳ và phạm vi báo cáo, giữ provenance | Chưa tự định nghĩa bảng ánh xạ hoặc quy tắc kế toán |
| `evidence` | Canonical Evidence Layer, provenance và EF-EG | Không điều phối tác nhân hay sinh báo cáo |
| `tools` | Shared Executable Tool Space: truy xuất, tính toán, kiểm tra dữ liệu | Không thay thế Planner/Supervisor hoặc phê duyệt claim |
| `agents` | Planner, Supervisor, xử lý nhu cầu bằng chứng và tác nhân chuyên môn | Dùng công cụ chung; kết quả phân tích vẫn là candidate claims |
| `verification` | Claim-Level Verification và quản lý Verified Claim Ledger | Chỉ nhận định đủ căn cứ mới được chấp nhận |
| `outputs` | Hỏi đáp và tạo báo cáo từ ledger | Không tạo thêm dữ kiện hoặc truy xuất, tính toán mới |
| `api` | Biên giao tiếp với bên sử dụng ứng dụng | Không chứa logic nghiệp vụ; framework và endpoints là `TBD` |

Luồng bàn giao chính: `document_processing` → `accounting` → `evidence` →
`tools` → `agents` → `verification` → `outputs`. Đây là luồng dữ liệu và trách
nhiệm; tác nhân gọi lại công cụ, kiểm chứng có thể yêu cầu điều tra bổ sung.
Không coi sơ đồ này là một chuỗi import cứng hay tự tạo phụ thuộc vòng.

Các module dùng LLM phải đi qua Gateway chung khi được triển khai. Chi tiết
interfaces, hướng phụ thuộc ở mức code và cơ chế kết nối qua `api` là `TBD`,
cần được xác định trong task liên quan trước khi viết logic.

W-03: `api` là HTTP/composition/local storage/job adapters; nhận diện metadata
và PDF raster riêng thuộc `document_processing.metadata_preflight`. Dùng lại
core Gateway/Gemini/quota/cache/schema, không import ngược từ core/accounting.
Không gọi financial runtime/extraction trong W-03. Chi tiết tại
[Web API](web-demo-v1/api-contracts.md) và [usage](web-demo-v1/w-03-usage.md).

`tests/unit/` kiểm tra độc lập; `tests/integration/` dành cho giao tiếp module;
`tests/evaluation/` dành cho kiểm tra đánh giá. `evaluation/` giữ cấu hình và
tài liệu thực nghiệm đã duyệt, không chứa dữ liệu gốc hoặc artifacts lớn.
`configs/`, `scripts/`, `prompts/` chỉ có `.gitkeep` cho tới khi có nhu cầu thực tế.
