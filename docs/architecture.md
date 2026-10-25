# Kiến trúc hệ thống

## Cơ sở và phạm vi

Nguồn: yêu cầu M0-01 và báo cáo giữa kỳ cục bộ `docs/report_midterm.docx`,
Chương 4–6. Tài liệu gốc không được đưa vào Git. Kiến trúc dưới đây là định hướng
thiết kế; code trong M0-01 chỉ là skeleton Python theo modular monolith.

## Offline Pipeline

Financial PDF → Document Processing & Accounting Normalization → Canonical
Evidence Layer → Executable Financial Evidence Graph (EF-EG).

Xử lý tài liệu tạo văn bản, bảng và vị trí nguồn. Chuẩn hóa kế toán giữ nguyên
khả năng truy nguyên khi chuẩn hóa chỉ tiêu, đơn vị, kỳ và phạm vi báo cáo.
Canonical Evidence Layer tổ chức facts, text/table evidence và provenance;
EF-EG liên kết bằng chứng với phép tính và nhận định.

## Online Processing

Shared Executable Tool Space → Evidence/Risk-Aware Planner & Supervisor →
Specialist Agents → Claim-Level Verification → Verified Claim Ledger.

Planner và Supervisor lựa chọn công cụ, tác nhân theo nhu cầu bằng chứng và
tín hiệu rủi ro. Công cụ và tác nhân sử dụng chung cơ sở bằng chứng. Nhận định
đề xuất phải được kiểm chứng về số liệu, phép tính, nguồn và lập luận.

Theo Chương 4.5 và 5.6, kiểm chứng có thể dẫn đến `ACCEPT`, `REVISE`,
`INVESTIGATE` hoặc `ABSTAIN`. Việc sửa hoặc tìm thêm bằng chứng quay về luồng
phân tích có giới hạn; chỉ nhận định được chấp nhận mới vào ledger. Ngưỡng rủi ro,
quy tắc kích hoạt, giới hạn vận hành và schema trạng thái dùng trong code là `TBD`.

## Output

- Interactive Financial Question Answering: câu trả lời tiếng Việt có dẫn nguồn.
- Grounded Financial Report Generation: báo cáo phân tích có dẫn nguồn.

Hai đầu ra dùng chung Verified Claim Ledger. Theo cơ chế Information Firewall
trong Chương 5.7, bộ tạo đầu ra chỉ tổng hợp nhận định đã xác minh, không tự bổ
sung số liệu, tính toán hoặc truy xuất bằng chứng mới. Thiếu bằng chứng phải
được thể hiện rõ, có thể không đưa ra kết luận.

## Hạ tầng và các lựa chọn chưa chốt

Python 3.11+, modular monolith; ranh giới cụ thể ở
[module-boundaries.md](module-boundaries.md). LLM Gateway dùng chung dự kiến
thuộc hạ tầng `core`, hỗ trợ Gemini và các LLM khác, đổi model, structured
outputs và quản lý chi phí. Không triển khai Gateway trong M0-01.

Framework API, thư viện OCR, engine lưu trữ/đồ thị, SDK LLM, model, schema chi
tiết và cơ chế triển khai là `TBD`. Các công nghệ được nêu như phương án trong
báo cáo giữa kỳ không được coi là dependency đã được chốt trong repository.
