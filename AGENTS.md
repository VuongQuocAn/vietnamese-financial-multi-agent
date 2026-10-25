# Quy tắc làm việc của Codex

Các quy tắc áp dụng lâu dài cho toàn bộ repository. Tài liệu viết bằng tiếng
Việt; identifiers, tên file và tên code dùng tiếng Anh. Phạm vi và giới hạn
riêng của từng task nằm trong yêu cầu task và `planning/tasks.md`.

1. Luôn đọc task, `planning/current-status.md` và tài liệu liên quan trước khi
   triển khai; đặc biệt là `docs/architecture.md`, `docs/module-boundaries.md`
   và `docs/data-contracts.md` khi thay đổi luồng hoặc giao tiếp giữa module.
2. Tuân thủ pipeline Offline → Online → Output và ranh giới module đã ghi nhận.
   Ưu tiên modular monolith, giữ cấu trúc đơn giản.
3. Không tự thay đổi kiến trúc hoặc contracts đã được duyệt. Ghi `TBD` cho thông
   tin chưa xác định; không tự tạo schema hay quy tắc kế toán chi tiết.
4. Chỉ thực hiện task được giao và dừng khi hoàn tất. Roadmap là kế hoạch;
   không tự bắt đầu task tiếp theo hoặc coi đề xuất là quyết định đã được duyệt.
5. Không sửa các module không liên quan. Kiểm tra workspace, nhánh, working tree
   và thay đổi đang có trước khi chỉnh sửa; bảo toàn công việc của người dùng.
6. Không tạo dữ liệu tài chính giả và sử dụng như dữ liệu thật. Không trình bày
   smoke test như kết quả đánh giá chất lượng phân tích tài chính.
7. Luôn lưu source provenance cho dữ liệu tài chính, đủ để truy nguyên đến tài
   liệu và vị trí nguồn. Không đưa dữ liệu từ Google Drive vào Git repository.
8. Không hardcode API keys hoặc secrets; dùng cấu hình môi trường. `.env.example`
   chỉ chứa tên biến và giá trị mẫu không bí mật. Không ghi secrets vào log.
9. Chạy kiểm thử phù hợp trước khi báo cáo hoàn thành. Các kiểm tra cơ bản là
   `python -m ruff check .`, `python -m ruff format --check .` và
   `python -m pytest tests/unit` bằng môi trường đã cài `.[dev]`. Chỉ thêm kiểm
   thử tích hợp/đánh giá khi phù hợp với thay đổi; không tự gọi dịch vụ có phí.
10. Cập nhật `planning/current-status.md` và `planning/tasks.md` sau mỗi task.
    Ghi bằng chứng thực tế, phân biệt local với CI và gắn kết quả CI với commit;
    bỏ thông tin blocker đã giải quyết khỏi trạng thái hiện tại.
11. Không đánh dấu task hoàn thành khi chưa đáp ứng acceptance criteria. Phân
    biệt implementation, kiểm thử, commit, push và CI; không tuyên bố bước chưa
    kiểm tra hoặc coi package skeleton là chức năng đã triển khai.
12. Chỉ commit, push, merge, tạo/xóa repository hoặc đổi visibility khi task hay
    người dùng đã yêu cầu. Kiểm tra remote và lịch sử trước khi push; không force
    push, ghi đè lịch sử hoặc tạo trùng repository phù hợp.
13. Bảo toàn dữ liệu gốc trong `data/raw/` và kết quả OCR hiện có trong
    `data/processed/`, gồm JSON, JSONL, PNG và log. Di chuyển dữ liệu phải giữ
    cấu trúc/nội dung, không ghi đè đích; đối chiếu metadata và mẫu trước/sau.
    Kết quả xử lý mới phải ở vị trí riêng được task xác định.
14. Không commit dataset lớn, OCR JSON, ảnh báo cáo, PDF, dữ liệu normalized hoặc
    canonical. Kiểm tra `.gitignore`, `git ls-files` và danh sách staged trước
    commit. Nếu dữ liệu đã được theo dõi, chỉ bỏ khỏi index và giữ bản local;
    nếu từng vào lịch sử Git, báo cáo, không tự rewrite history hay force push.
15. Rà soát file chuẩn bị commit để loại secrets, tài liệu riêng tư, thông tin
    nhạy cảm và đường dẫn tuyệt đối chứa thông tin cá nhân. Cấu hình dataset
    dùng đường dẫn tương đối hoặc biến môi trường; giữ nguyên đường dẫn Colab
    trong JSON gốc và ánh xạ môi trường bên ngoài dữ liệu đó.

Sử dụng Python 3.11+. Không cài thư viện AI lớn khi chưa cần; không tạo
implementation giả cho Agent, OCR hoặc EF-EG. Tích hợp LLM phải qua Gateway
chung theo kiến trúc, hỗ trợ đổi model, structured outputs và quản lý chi phí;
chỉ triển khai khi thuộc phạm vi task được giao.
