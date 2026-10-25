# Trạng thái hiện tại

Ngày cập nhật: **2026-10-25** (Asia/Bangkok).

Task: **M0-01 — Initialize Project Repository**.

Trạng thái: **Hoàn thành phần khởi tạo và tiêu chí cho phép báo cáo trở ngại
xác thực. Push đang bị chặn; CI trên GitHub chưa chạy.**

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
| Phân tích cấu trúc YAML của CI | Hợp lệ; đúng triggers, quyền đọc, matrix Python và các lệnh kiểm tra; chưa chạy trên GitHub |
| `git diff --cached --check` và rà soát tập commit | Đạt; 34 file văn bản/chỗ giữ thư mục, không có dữ liệu gốc hoặc secrets được phát hiện |
| Liên kết Markdown và bảo toàn báo cáo gốc | Liên kết nội bộ hợp lệ; SHA-256 báo cáo không đổi |

## Git và GitHub

- Nhánh local: `main`.
- Initial commit: `9eb4483f4be4029c014a3a9552dfb5a1a91c8fea`.
- Đã tạo và xác nhận repository **private**:
  [VuongQuocAn/vietnamese-financial-multi-agent](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent).
- `origin`: `https://github.com/VuongQuocAn/vietnamese-financial-multi-agent.git`.
- Repository cũ `Mutil_Agent_Financial_Report` public, có code C1–C5 được giữ nguyên.
- GitHub từ chối push vì token OAuth của GitHub CLI thiếu scope `workflow` để
  tạo/cập nhật `.github/workflows/ci.yml`. Repository GitHub vẫn rỗng; chưa có
  nhánh remote hoặc CI run. Không bỏ file CI để vượt qua giới hạn quyền.
- Kiểm tra SSH chưa kết nối được vì máy chưa có host key GitHub được tin cậy;
  không tắt xác minh host key hoặc tự thay đổi quyền xác thực.
- Git local đã cấu hình credential helper dùng GitHub CLI hiện có, chỉ trong
  `.git/config` của repository; không lưu token vào file được theo dõi.

## Bước cần người dùng thực hiện để hoàn tất push

Trong PowerShell tại thư mục repository, cấp thêm scope `workflow` qua luồng
đăng nhập chính thức, sau đó push (không cần tạo lại repository):

```powershell
& 'C:\Program Files\GitHub CLI\gh.exe' auth refresh --hostname github.com --scopes workflow
git push -u origin main
```

Sau khi push thành công, kiểm tra workflow bằng:

```powershell
& 'C:\Program Files\GitHub CLI\gh.exe' run list --repo VuongQuocAn/vietnamese-financial-multi-agent
```

CI đã cấu hình lint/format và unit tests trên Python 3.11/3.12, nhưng hiện chỉ
có kết quả chạy local Python 3.12.0. Cần cập nhật trạng thái GitHub/CI sau khi
có kết quả thực tế. Không có task nghiệp vụ tiếp theo được tự triển khai.

## Giới hạn

Mới có skeleton; chưa triển khai nghiệp vụ, OCR, Gateway, EF-EG, Agent hoặc API.
Chưa kiểm định dataset hoặc chạy benchmark. Chưa chốt schema/contracts chi tiết,
backend lưu trữ, model và phạm vi tuân thủ quy định; xem `planning/decisions.md`.
