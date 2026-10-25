# Trạng thái hiện tại

Ngày cập nhật: **2026-10-25** (Asia/Bangkok).

Task: **M0-02 — Reorganize Financial Dataset & Commit to GitHub**.

Trạng thái: **Chưa hoàn thành. Phần local đã di chuyển, kiểm tra và commit;
push còn chờ quyền `workflow`, CI trên GitHub chưa chạy.**

## Dữ liệu local

| Nguồn cũ → vị trí mới | File trước/sau | Byte trước/sau |
| --- | ---: | ---: |
| `Financial_Report/` → `data/raw/Financial_Report/` | 500 / 500 | 1.490.251.896 / 1.490.251.896 |
| `Financial_Report_OCR/` → `data/processed/Financial_Report_OCR/` | 8.627 / 8.627 | 837.428.529 / 837.428.529 |
| Tổng | 9.127 / 9.127 | 2.327.680.425 / 2.327.680.425 |

- Di chuyển trong cùng ổ đĩa; đích chưa tồn tại, không ghi đè hoặc chỉnh sửa file.
- Cấu trúc con, kích thước, thời gian sửa và định danh toàn bộ file/thư mục khớp.
- SHA-256 của 18 mẫu khớp; chỉ hash 16.580.761 byte mẫu thay vì toàn bộ dataset.
- Đọc thành công 6 JSON; xác minh cấu trúc và giải mã thành công 12 PNG.
- Mẫu bao phủ ba mã BBS, BCC, BED ở năm đầu/cuối. Dataset có năm kỳ 2021–2025.
- `data/normalized/`, `data/canonical/` đã tạo và đang rỗng; `data/samples/` giữ
  nguyên. Các thư mục dữ liệu đều bị Git bỏ qua, chỉ theo dõi `samples/.gitkeep`.
- Manifest metadata và hash mẫu lưu local trong `.venv/`, không được commit.

## Cấu hình và tài liệu

Bổ sung `FINANCIAL_REPORT_DIR`, `FINANCIAL_OCR_DIR`, `NORMALIZED_DATA_DIR`,
`CANONICAL_DATA_DIR` bằng đường dẫn tương đối trong `.env.example`.
Skeleton chưa có bộ nạp cấu hình trung tâm; không thêm implementation.
README và `docs/dataset.md` mô tả bố cục mới, giới hạn kiểm tra mẫu và cách ánh
xạ đường dẫn `/content/drive/...` mà không sửa JSON gốc. AGENTS bổ sung quy tắc
bảo toàn raw/OCR và không commit dataset lớn hoặc thông tin nhạy cảm.

## Kiểm tra Git và quyền truy cập

- Working tree sạch trước task, 34 file được theo dõi; chưa có dataset trong index.
- `.gitignore` đã kiểm tra với đủ 9.127 file dữ liệu và các đường dẫn đại diện
  cho normalized/canonical, secrets và cache. `.env.example`, code và
  `data/samples/.gitkeep` vẫn được phép theo dõi.
- Chỉ bảy file cấu hình/tài liệu của task thay đổi và được stage; không có dữ
  liệu lớn, secrets hoặc đường dẫn cá nhân được phát hiện trong các file này.
  Source, unit tests, `pyproject.toml`, CI và các file ngoài phạm vi giữ nguyên.
- Rà soát 30 blob trong hai commit lịch sử local: không thấy dataset, `.env`
  thực tế, blob lớn, mẫu secrets phổ biến hoặc đường dẫn tuyệt đối cá nhân.
  Đây là kiểm tra theo đường dẫn/kích thước và mẫu nhận diện, không phải bảo đảm
  phát hiện mọi loại secret. Không sửa lịch sử Git.
- Đã xác nhận repository
  [VuongQuocAn/vietnamese-financial-multi-agent](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent)
  là **public** theo thay đổi của người dùng; remote `origin` giữ nguyên.
- Repository remote đang rỗng. Nhánh local `main` phù hợp cho lần push đầu tiên.
- Token GitHub CLI hiện có các scope `gist`, `read:org`, `repo`, chưa có
  `workflow`; đây là nguyên nhân push M0-01 bị từ chối. Push chứa file CI vẫn
  cần bổ sung quyền này. Chưa chạy CI trên GitHub.

## Kiểm thử project

Môi trường local: Python 3.12.0, Ruff 0.17.2, pytest 9.1.1.

| Kiểm tra M0-02 | Kết quả |
| --- | --- |
| `python -m ruff check .` | Đạt |
| `python -m ruff format --check .` | Đạt |
| `python -m pytest tests/unit` | 11 passed |
| Bốn biến dataset | Đúng đường dẫn tương đối, thư mục đích tồn tại |
| `.env.example` | Giá trị API key, model và database để trống |
| Liên kết Markdown và anchor | Hợp lệ |
| Metadata và mẫu JSON/PNG | Đạt, chi tiết ở phần dữ liệu local |
| Tập file commit và phạm vi thay đổi | Chỉ bảy file được yêu cầu; các file còn lại khớp bản trước task |

## Commit và push

Message commit M0-02:

```text
chore(data): organize financial datasets and update path configuration
```

Bảy file trong commit: `.gitignore`, `.env.example`, `AGENTS.md`, `README.md`,
`docs/dataset.md`, `planning/tasks.md`, `planning/current-status.md`.
Không có dataset được thêm vào index nên không cần `git rm --cached`.

Push lên `origin/main` chưa hoàn tất. Repository public remote đang rỗng nên lần
push đầu tiên bao gồm cả lịch sử M0-01 có `.github/workflows/ci.yml`; vì vậy dù
M0-02 chỉ sửa tài liệu/cấu hình, token vẫn cần scope `workflow`. Việc đổi
repository sang public không bổ sung scope này cho token.

Để tiếp tục, người dùng cần bổ sung quyền qua luồng đăng nhập GitHub chính thức,
rồi push bình thường tại thư mục repository:

```powershell
& (Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe') auth refresh --hostname github.com --scopes workflow
git push -u origin main
```

Nếu `gh` đã có trong PATH, dùng `gh auth refresh --hostname github.com --scopes workflow`.
Remote và visibility được giữ nguyên; không viết lại lịch sử Git hoặc force
push. Cần cập nhật trạng thái task sau khi push thành công và kiểm tra CI.

## Giới hạn và việc còn lại

Chưa đánh dấu task hoàn thành vì push chưa thành công. Không chạy lại OCR,
gọi Gemini, triển khai nghiệp vụ hoặc tạo resolver.
Chưa đánh giá độ chính xác dữ liệu tài chính, OCR hoặc toàn bộ tham chiếu Colab.
Chỉ tiếp tục trong phạm vi M0-02.
