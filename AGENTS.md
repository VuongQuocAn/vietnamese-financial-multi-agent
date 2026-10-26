# Quy tắc làm việc của Codex

Áp dụng lâu dài cho toàn repository. Tài liệu tiếng Việt; identifiers/tên code
bằng tiếng Anh. Python 3.11+, ưu tiên Modular Monolith.

1. Trước triển khai, đọc task, `planning/current-status.md` và spec liên quan.
   Khi resume: đọc AGENTS → current-status → handoff → active task spec, kiểm tra
   `git status`/commit/checkpoint rồi chỉ đọc module/tài liệu cần thiết.
2. `planning/tasks.md` là nguồn trạng thái task chính. Task ID bất biến, không
   đánh số lại hoặc tái sử dụng; giữ lịch sử khi tách task bằng ID mới/hậu tố.
3. Chỉ dùng TODO, READY, IN_PROGRESS, BLOCKED, REVIEW, DONE. READY cần dependencies
   DONE và spec/inputs/criteria đầy đủ, không tự cấp phép bắt đầu. Tối đa một
   active implementation task chính; không tự chuyển task hoặc mở rộng scope.
4. Mỗi task có output và acceptance criteria cụ thể. Ưu tiên XS/S, chia M/L khi
   phù hợp; không gộp nhiều module lớn hoặc refactor ngoài yêu cầu. Đề xuất công
   việc ngoài phạm vi thành task mới, không tự triển khai.
5. Tuân thủ Offline → Online → Output, module boundaries và contracts được duyệt.
   Đọc architecture/module-boundaries/data-contracts khi thay đổi giao tiếp;
   không tự đổi pipeline, thêm agent hoặc suy đoán schema/quy tắc kế toán. Ghi TBD.
6. Bảo toàn thay đổi của người dùng. Kiểm tra nhánh/working tree trước sửa, chỉ
   stage file thuộc task. Chỉ commit/push/merge/tạo/xóa repo/đổi visibility khi
   được yêu cầu; không force push, ghi đè lịch sử hoặc tạo trùng repository.
7. Dữ liệu tài chính luôn giữ source provenance. Không tạo dữ liệu giả rồi dùng
   như dữ liệu thật; không trình bày smoke tests như đánh giá chất lượng tài chính.
8. Raw OCR JSON, JSONL, ảnh và log trong `data/raw/`, `data/processed/` là read-only.
   Nếu task yêu cầu di chuyển: không ghi đè đích, đối chiếu metadata/mẫu trước/sau.
   Kết quả mới ở vị trí riêng được giao; giữ nguyên JSON Colab, ánh xạ bên ngoài.
9. Không commit dataset, dữ liệu Google Drive, OCR/PDF/ảnh, normalized/canonical,
   secrets, API keys, `.env` thực tế, tài liệu riêng tư hoặc đường dẫn cá nhân.
   Kiểm tra ignore/index/staged; chỉ bỏ khỏi index khi cần, giữ local. Báo cáo
   dữ liệu/secrets trong lịch sử, không tự rewrite Git.
10. Cấu hình dùng biến môi trường/đường dẫn tương đối; không hardcode secrets hoặc
    ghi vào log. `.env.example` chỉ chứa giá trị mẫu không bí mật.
11. Không tự gọi API, xử lý dataset lớn hoặc chạy benchmark ngoài task/ngân sách.
    Không cài thư viện AI lớn khi chưa cần hoặc tạo implementation giả.
    Mọi LLM đi qua Gateway chung, hỗ trợ đổi model, structured outputs và chi phí.
12. Kiểm thử theo thay đổi; kiểm tra cơ bản gồm Ruff lint/format, unit tests và
    `python scripts/check_planning.py` trong môi trường `.[dev]`. Không chạy lại
    công việc đã xác minh nếu không có lý do; phân biệt local, CI và benchmark.
13. DONE cần tất cả acceptance criteria/tests đạt và commit/bằng chứng đã kiểm
    tra. BLOCKED ghi lý do/next action; REVIEW ghi phần chờ nghiệm thu. Khi Git
    và tài liệu mâu thuẫn, xác minh thực tế rồi cập nhật tài liệu.
14. Cập nhật registry, dashboard, current-status, spec và handoff ở checkpoint
    quan trọng và trước kết thúc phiên. Ghi completed/remaining work, modified
    files, tests, SHA ổn định và đúng một next action; không đợi quota hết.
    Không gọi code không chạy được là checkpoint ổn định; không tự sang task mới.
