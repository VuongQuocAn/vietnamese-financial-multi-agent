# Quy tắc làm việc của Codex

Các quy tắc áp dụng cho toàn bộ repository. Tài liệu viết bằng tiếng Việt;
identifiers, tên file và tên code dùng tiếng Anh.

1. Luôn đọc task, `planning/current-status.md` và tài liệu liên quan trước khi
   triển khai; đặc biệt là `docs/architecture.md`, `docs/module-boundaries.md`
   và `docs/data-contracts.md` khi thay đổi luồng hoặc giao tiếp giữa module.
2. Tuân thủ pipeline Offline → Online → Output và ranh giới module đã ghi nhận.
   Ưu tiên modular monolith, giữ cấu trúc đơn giản.
3. Không tự thay đổi kiến trúc hoặc contracts đã được duyệt. Ghi `TBD` cho thông
   tin chưa xác định; không tự tạo schema hay quy tắc kế toán chi tiết.
4. Không tự chuyển sang nhiệm vụ mới. Dừng sau task được giao; M0-01 không bao gồm
   OCR, Gemini, EF-EG, Agent hoặc chức năng nghiệp vụ.
5. Không sửa các module không liên quan. Kiểm tra workspace trước khi tạo file;
   bảo toàn dữ liệu và các thay đổi đang có của người dùng.
6. Không tạo dữ liệu tài chính giả và sử dụng như dữ liệu thật. Không trình bày
   smoke test như kết quả đánh giá chất lượng phân tích tài chính.
7. Luôn lưu source provenance cho dữ liệu tài chính, đủ để truy nguyên đến tài
   liệu và vị trí nguồn. Không đưa dữ liệu từ Google Drive vào Git repository.
8. Không hardcode API keys hoặc secrets; dùng cấu hình môi trường. `.env.example`
   chỉ chứa tên biến và giá trị mẫu không bí mật. Không ghi secrets vào log.
9. Thực hiện kiểm thử phù hợp trước khi báo cáo hoàn thành. Với skeleton, chạy
   `python -m ruff check .`, `python -m ruff format --check .` và
   `python -m pytest tests/unit` bằng môi trường đã cài `.[dev]`.
10. Cập nhật `planning/current-status.md` và `planning/tasks.md` sau mỗi task,
    ghi rõ kiểm thử, giới hạn và trở ngại còn tồn tại.
11. Không đánh dấu task hoàn thành khi chưa đáp ứng acceptance criteria. Phân
    biệt trạng thái local, commit, push và CI; không tuyên bố bước chưa kiểm tra.
12. Không tự push, merge hoặc xóa repository sau nhiệm vụ khởi tạo nếu chưa được
    yêu cầu. M0-01 cho phép initial commit, tạo GitHub repository private và push
    `main`; không force push, ghi đè lịch sử hoặc tạo trùng repository phù hợp.
13. Không chỉnh sửa dữ liệu gốc trong `data/raw/` hoặc kết quả OCR hiện có trong
    `data/processed/`: giữ nguyên JSON, JSONL, PNG và log. Di chuyển dữ liệu phải
    bảo toàn cấu trúc và nội dung, không ghi đè đích; đối chiếu số file, dung lượng
    và lấy mẫu trước/sau. Kết quả xử lý mới phải ở vị trí riêng được task xác định.
14. Không commit dataset lớn, OCR JSON, ảnh báo cáo, PDF, dữ liệu normalized hoặc
    canonical. Kiểm tra `.gitignore`, `git ls-files` và danh sách staged trước
    commit. Nếu dữ liệu đã được theo dõi, chỉ bỏ khỏi index và giữ bản local;
    nếu từng vào lịch sử Git, báo cáo, không tự rewrite history hay force push.
15. Với repository public, rà soát file chuẩn bị commit để loại secrets, thông
    tin nhạy cảm và đường dẫn tuyệt đối chứa thông tin cá nhân. Cấu hình dataset
    dùng đường dẫn tương đối hoặc biến môi trường; giữ nguyên đường dẫn Colab
    trong JSON gốc và chỉ mô tả ánh xạ môi trường bên ngoài dữ liệu đó.

Sử dụng Python 3.11+. Không cài thư viện AI lớn khi chưa cần, không tạo implementation
giả cho Agent, OCR hoặc EF-EG. Mọi LLM sẽ tích hợp qua Gateway dùng chung khi có task
riêng; không thêm lời gọi trực tiếp tới nhà cung cấp trong task khởi tạo.
