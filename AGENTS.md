# Quy tắc làm việc của Codex

Áp dụng toàn repository. Tài liệu tiếng Việt; identifiers/tên code bằng tiếng Anh.
Python 3.11+, ưu tiên Modular Monolith. Đây là dự án nghiên cứu học thuật AI,
báo cáo tài chính và Multi-Agent, local single-user prototype.

## Research-First, Minimal Engineering, Low Codex Quota

Thứ tự ưu tiên:

1. Chất lượng thuật toán, Gemini Vision, extraction và Multi-Agent.
2. Grounding, provenance và độ chính xác dữ liệu tài chính.
3. Đánh giá thực nghiệm trên PDF scan thực tế.
4. Khả năng chạy và demo hệ thống.
5. Code cleanliness, testing và documentation ở mức vừa đủ.

Không mặc định tiêu chuẩn enterprise/production khi task không yêu cầu. Quy trình
này áp dụng cho công việc mới từ W-04; giữ nguyên evidence M0–M2/W-01–W-03.

## Phạm vi, trạng thái và Git

1. Trước triển khai đọc task, `planning/current-status.md` và spec liên quan.
   Khi resume: AGENTS → current-status → handoff nếu cần → active task spec;
   kiểm tra Git/commit/checkpoint rồi chỉ đọc module/tài liệu cần thiết.
2. `planning/tasks.md` là nguồn trạng thái chính. Task ID bất biến; không đánh số
   lại/tái sử dụng; giữ lịch sử khi tách task bằng ID mới/hậu tố chưa dùng.
3. Chỉ dùng TODO, READY, IN_PROGRESS, BLOCKED, REVIEW, DONE. READY cần dependencies
   DONE và spec/inputs/criteria đủ, không tự cấp phép bắt đầu. Tối đa một active
   implementation task chính; không tự chuyển task hoặc mở rộng scope.
4. Mỗi task có output/acceptance criteria cụ thể; ưu tiên XS/S, chia M/L khi phù
   hợp. Không gộp nhiều module lớn hoặc refactor ngoài yêu cầu. Vấn đề ngoài scope
   không chặn chức năng chính: ghi chú/đề xuất, không tự triển khai.
5. Tuân thủ Offline → Online → Output và contracts/module boundaries được duyệt.
   Đọc architecture/module-boundaries/data-contracts khi đổi giao tiếp; không tự
   đổi pipeline, thêm agent hoặc suy đoán schema/quy tắc kế toán. Ghi TBD.
6. Bảo toàn thay đổi local. Kiểm tra Git trước sửa, chỉ stage file thuộc task.
   Chỉ commit/push/merge/tạo/xóa repo/đổi visibility khi được yêu cầu; không force
   push, ghi đè lịch sử hoặc tạo trùng repository.
7. Chức năng đúng + bằng chứng phù hợp + targeted validation đủ điều kiện REVIEW.
   Tech Lead review trước DONE; cần criteria/tests liên quan đạt và SHA/bằng chứng
   đã xác minh. BLOCKED ghi lý do/next action; REVIEW ghi phần chờ nghiệm thu.
   Khi Git và tài liệu mâu thuẫn, xác minh thực tế rồi cập nhật.

## Bảo vệ thiết yếu cho dữ liệu và local demo

- Giữ source provenance cho dữ liệu tài chính; không dùng dữ liệu giả như thật.
- Raw OCR JSON, JSONL, ảnh và log trong `data/raw/`, `data/processed/` là read-only.
  Nếu được giao di chuyển: không ghi đè đích, đối chiếu metadata/mẫu trước/sau.
  Kết quả mới ở vị trí riêng được giao; giữ JSON Colab, ánh xạ bên ngoài.
- Không hardcode/commit/leak secrets, API keys, `.env` thực tế, tài liệu riêng tư,
  dataset/Drive/OCR/PDF/ảnh/normalized/canonical hoặc đường dẫn cá nhân. Kiểm tra
  ignore/index/staged; chỉ bỏ khỏi index khi cần, giữ local. Báo dữ liệu/secrets
  trong lịch sử, không tự rewrite Git. Không ghi secrets vào log.
- Cấu hình bằng biến môi trường/đường dẫn tương đối; `.env.example` chỉ có mẫu
  không bí mật. Không cho truy cập file ngoài storage được cấu hình.
- Giới hạn upload PDF và số request để tránh lỗi/tốn tài nguyên; không tự chuyển
  API trả phí hoặc retry vô hạn. Mọi LLM qua Gateway chung, hỗ trợ đổi model,
  structured outputs và chi phí; không tạo implementation giả.
- Không tự thêm authentication/RBAC, enterprise frameworks, distributed controls,
  audit lớn, hàng chục security edge-case tests, bảo vệ trùng chức năng hoặc
  hardening public production khi task không yêu cầu. Giữ validations hiện có;
  không mở rộng task để xử lý rủi ro giả định ngoài phạm vi local demo.

## Kiểm thử và CI tối thiểu

- Mặc định 1–3 targeted tests cho logic chính nếu cần; một integration smoke cho
  luồng thực tế liên quan khi đổi chức năng. Docs-only không cần smoke.
- Lint/format file đã sửa nếu áp dụng; build frontend khi thay đổi ảnh hưởng build.
  Khi sửa planning, chạy `python scripts/check_planning.py`; dùng `.[dev]` khi cần.
  Chạy `git diff --check` trước bàn giao.
- Không bắt full unit/browser/regression suite mỗi task. Full regression chỉ khi
  thay đổi module chung có rủi ro lan rộng, chuẩn bị nghiệm thu milestone quan trọng
  hoặc Tech Lead yêu cầu cụ thể.
- Không viết hàng chục tests cho tình huống cực hiếm; không xóa tests hiện có để
  giảm số lượng. Chỉ giảm tests mới và tần suất chạy.
- CI mặc định Python 3.12, Ruff lint/format, planning checker và unit tests trọng
  tâm; frontend typecheck/build và browser smoke giới hạn khi có thay đổi liên quan.
  Không bắt matrix 3.11/3.12 cho mọi PR; full regression có thể chạy thủ công.
  Không tắt toàn bộ CI hoặc gọi smoke PASS là chất lượng tài chính.

## Engineering tests và research evaluation

Engineering smoke chỉ trả lời pipeline có chạy không. Research evaluation phải
đánh giá nhận diện PDF scan thực tế, độ đúng số liệu trích xuất, provenance đúng
trang/ô nguồn, QA grounded và lợi ích thực tế của Multi-Agent. Ưu tiên tài nguyên
cho đánh giá này trong task/ngân sách được giao. Không báo synthetic test PASS như
bằng chứng hệ thống đạt chất lượng tài chính.

## Quota và tài liệu tối thiểu

- Chỉ đọc code/tài liệu cần thiết; không đọc lại hàng loạt tài liệu không đổi.
  Ưu tiên sửa nhỏ, trực tiếp; tái sử dụng contracts, tránh abstraction/validation
  trùng lặp, framework/tooling hoặc thư viện AI lớn chưa cần.
- Không chạy lại lệnh PASS nếu không có lý do mới; không polling/chờ CI nhiều vòng.
  Một run thành công đúng implementation SHA đủ bằng chứng engineering trong phạm
  vi đó. Phân biệt kết quả local, CI và benchmark.
- Không benchmark, Gemini live calls hoặc xử lý dataset lớn ngoài task/ngân sách.
- Mỗi task chỉ cần status, implementation SHA đã xác minh (hoặc chưa commit),
  thay đổi chính, tests thực sự đã chạy và đúng một next action. Giữ registry là
  nguồn chính; handoff ngắn nếu cần resume. Dashboard chỉ cập nhật khi số đếm/trạng
  thái thay đổi; current-status/spec chỉ cập nhật thông tin cần cho công việc đó.
  Không bắt buộc lặp nội dung ở mọi tài liệu hoặc viết validation report dài.
- Không tạo nhiều vòng review/checkpoint hình thức; không gọi code không chạy được
  là checkpoint ổn định. Báo cáo ngắn, kết thúc khi đạt criteria REVIEW; không tự
  nghiệm thu DONE hoặc bắt đầu task khác.

## Frontend

Desktop-first 1366–1920px; mobile responsive tối thiểu. Không yêu cầu pixel-perfect,
ảnh nhiều breakpoint hoặc visual regression trừ khi task có mục tiêu UI cụ thể.
