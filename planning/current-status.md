# Trạng thái hiện tại

Ngày cập nhật: **2026-10-25** (Asia/Bangkok).

Task đang thực hiện: **M0-01 — Initialize Project Repository**.

## Đã thực hiện

- Kiểm tra workspace: chưa có Git repository; có sẵn dữ liệu và báo cáo giữa kỳ.
- Đọc kiến trúc và các phần liên quan trong báo cáo; tạo tài liệu nền tảng bằng
  tiếng Việt, đánh dấu các quyết định chưa chốt là `TBD`.
- Tạo skeleton Python, cấu hình đóng gói, Ruff, pytest và CI.
- Thêm quy tắc loại dữ liệu gốc, OCR, báo cáo tham chiếu và secrets khỏi Git.
- Xác nhận Git 2.53.0, Python 3.12.0; GitHub CLI 2.103.2 nằm ngoài PATH tại
  `C:\Program Files\GitHub CLI\gh.exe`, đã đăng nhập tài khoản `VuongQuocAn`.

## Kết quả kiểm tra local

Môi trường Windows, Python 3.12.0, Ruff 0.17.2, pytest 9.1.1.

| Kiểm tra | Kết quả |
| --- | --- |
| Cài editable `pip install -e ".[dev]"` trong `.venv` | Thành công |
| Đọc `pyproject.toml`, xác minh thư mục/package | Hợp lệ; đủ 20 thư mục yêu cầu, 10 package chỉ có docstring |
| `python -m ruff check .` | Đạt |
| `python -m ruff format --check .` | Đạt |
| `python -m pytest tests/unit` | 11 passed |
| `python -m pip check` | Không có dependency lỗi |
| Build wheel, cài vào thư mục kiểm tra riêng | Đạt; import đủ 10 package, wheel chỉ chứa code package và metadata |
| `git diff --cached --check` và rà soát tập commit | Đạt; 34 file văn bản/chỗ giữ thư mục, không có dữ liệu gốc hoặc secrets được phát hiện |
| Liên kết Markdown và bảo toàn báo cáo gốc | Liên kết nội bộ hợp lệ; SHA-256 báo cáo không đổi |

## Git và GitHub

Đã khởi tạo Git trên `main`. Chưa tạo initial commit hoặc push tại bản ghi này.
Repository đúng tên chưa tồn tại; sẽ tạo private theo M0-01. Repository cũ
`Mutil_Agent_Financial_Report` đang public và có code C1–C5 nên được giữ nguyên.
CI GitHub Actions chưa chạy.

## Giới hạn

Mới có skeleton; chưa triển khai nghiệp vụ, OCR, Gateway, EF-EG, Agent hoặc API.
Chưa kiểm định dataset hoặc chạy benchmark. Chưa chốt schema/contracts chi tiết,
backend lưu trữ, model và phạm vi tuân thủ quy định; xem `planning/decisions.md`.
