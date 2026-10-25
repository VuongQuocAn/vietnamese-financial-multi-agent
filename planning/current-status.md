# Trạng thái hiện tại

Ngày cập nhật: **2026-10-25** (Asia/Bangkok).

Task được giao: **M0-03 — Repository Housekeeping & Planning Synchronization**.
M0-01 và M0-02 đã hoàn thành. M0-03 đang đồng bộ tài liệu; chưa bắt đầu M1-01
hoặc bất kỳ task phát triển nghiệp vụ nào.

## Git và GitHub đã xác minh

- Repository [VuongQuocAn/vietnamese-financial-multi-agent](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent)
  là **public**, nhánh làm việc và nhánh mặc định là `main`; giữ nguyên `origin`.
- Khi bắt đầu M0-03, working tree sạch. Sau `git fetch origin`, local `HEAD` và
  `origin/main` cùng là `279e65a38c44feca385b305e32e34be2c30510db`, ahead/behind 0/0.
- Commit M0-02 đã có trên `origin/main`; lịch sử gồm initial commit M0-01
  `9eb4483f4be4029c014a3a9552dfb5a1a91c8fea`. Không còn blocker xác thực đang mở.
- CI đã xác minh cho commit M0-02:
  [run 40207830248](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40207830248),
  trạng thái `completed`, kết luận `success`.

## Trạng thái các mốc

| Task | Trạng thái | Kết quả |
| --- | --- | --- |
| M0-01 | Hoàn thành | Skeleton, cấu hình phát triển, tài liệu, Git và CI; lịch sử đã có trên GitHub |
| M0-02 | Hoàn thành | Di chuyển dataset, cấu hình đường dẫn và tài liệu; commit `279e65a` đã push, CI đạt |
| M0-03 | Đang thực hiện | Đồng bộ planning và quy tắc lâu dài; chờ commit/push bản cập nhật và xác minh CI |
| M1-01 đến M1-04 | Dự kiến, chưa bắt đầu | Phạm vi đề xuất tại `planning/roadmap.md`; chưa có triển khai |

## Kiểm thử local và CI

| Môi trường / phạm vi | Kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Local M0-03, Windows / Python 3.12.0 | Ruff 0.17.2: lint và format | Đạt |
| Local M0-03, pytest 9.1.1 | `python -m pytest tests/unit` | 11 passed |
| Local M0-03 | Đọc TOML và YAML của CI, đối chiếu Python matrix và quyền workflow | Hợp lệ |
| GitHub Actions, commit `279e65a` | Ubuntu / Python 3.11 và 3.12: cài package, lint, format, unit tests | Cả hai jobs và các bước kiểm tra đều `success` |

Kết quả local không thay thế CI. Run nêu trên kiểm tra commit M0-02; chưa phải
bằng chứng CI của bản cập nhật M0-03 chưa push. Các unit tests hiện kiểm tra
đóng gói/import, không đánh giá chất lượng OCR, số liệu hoặc phân tích tài chính.

## Dữ liệu và phạm vi bảo toàn

| Vị trí local | Số file | Dung lượng (byte) |
| --- | ---: | ---: |
| `data/raw/Financial_Report/` | 500 | 1.490.251.896 |
| `data/processed/Financial_Report_OCR/` | 8.627 | 837.428.529 |
| Tổng | 9.127 | 2.327.680.425 |

Đây là số liệu metadata đọc lại ở M0-03. Dataset gồm ba mã, năm kỳ 2021–2025;
`normalized/` và `canonical/` chưa có dữ liệu. M0-03 chỉ sửa tài liệu, không xử lý
hoặc sửa raw/OCR. Đối chiếu trước/sau M0-03 cho thấy đường dẫn, kích thước,
thời gian sửa và định danh của đủ 9.127 file không đổi. Kết quả lấy mẫu M0-02 nằm trong
[`docs/dataset.md`](../docs/dataset.md).

`.gitignore` đã kiểm tra trên đủ 9.127 file dữ liệu, `.env`, cache và tài liệu
tham chiếu riêng tư. Git không theo dõi các mục này; trong `data/` chỉ có
`samples/.gitkeep`. Không cần đổi ignore rules. `.env.example`, source và CI
vẫn được theo dõi bình thường.

## Những thành phần chưa triển khai

Các package trong `src/` vẫn chỉ có docstring. Chưa có bộ nạp cấu hình trung tâm,
DataPathResolver, OCR adapter/pipeline, chuẩn hóa kế toán, Canonical Evidence
Layer, EF-EG, Shared Executable Tools, LLM Gateway, Agent, verification, ledger
hoặc chức năng QA/report/API. Dữ liệu OCR có sẵn không chứng minh pipeline đã
được triển khai trong repository này.

Contracts chi tiết, schema kế toán, công nghệ lưu trữ, model, benchmark và phạm
vi tuân thủ quy định vẫn là `TBD` theo [`decisions.md`](decisions.md).

## Việc còn lại của M0-03

Tập thay đổi chỉ gồm AGENTS và ba tài liệu planning; dữ liệu và các file source,
cấu hình khác giữ nguyên. Còn commit đúng message được yêu cầu, push bình thường
lên `origin/main` và kiểm tra CI cho commit mới. M1-01 đến M1-04
chỉ là kế hoạch dự kiến; dừng sau M0-03.
