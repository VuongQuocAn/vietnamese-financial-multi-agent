# Danh sách task

| ID | Tên | Trạng thái |
| --- | --- | --- |
| M0-01 | Initialize Project Repository | Hoàn thành |
| M0-02 | Reorganize Financial Dataset & Commit to GitHub | Hoàn thành |
| M0-03 | Repository Housekeeping & Planning Synchronization | Đang thực hiện |
| M1-01 | Dataset Inventory & Provenance Review | Dự kiến, chưa bắt đầu |
| M1-02 | Data Contracts & Path Mapping Design | Dự kiến, chưa bắt đầu |
| M1-03 | Configuration & Read-Only OCR Adapter | Dự kiến, chưa bắt đầu |
| M1-04 | Extraction Quality Validation & Pilot | Dự kiến, chưa bắt đầu |

Chi tiết đề xuất M1 và phụ thuộc nằm tại [`roadmap.md`](roadmap.md).
Không có task M1 nào được tự động giao hoặc bắt đầu từ danh sách này.

## M0-01 — Kết quả và phạm vi lịch sử

- Đã tạo cấu trúc Python 3.11+, cấu hình môi trường, tài liệu, quy tắc làm việc,
  lint/format, smoke tests và CI.
- Initial commit: `9eb4483f4be4029c014a3a9552dfb5a1a91c8fea`; đã nằm trong lịch sử
  `origin/main`. Kết quả local đạt; CI trên nền tảng M0 đã được xác minh ở M0-02.
- Phạm vi riêng của task: chỉ skeleton, không triển khai OCR, Gemini/Gateway,
  EF-EG, Agent hoặc chức năng nghiệp vụ. Đây là giới hạn của task khởi tạo,
  không phải lệnh cấm triển khai các thành phần này trong task được giao sau đó.
- Task đã cho phép `git init`, initial commit, tạo repository private và push
  `main`. Quyền khởi tạo này không áp dụng mặc định cho task khác. Người dùng
  đã đổi repository sang public trước M0-02; không cần tạo lại repository.

## M0-02 — Acceptance criteria đã xác minh

- [x] Di chuyển nguyên trạng hai dataset trong cùng ổ đĩa, không ghi đè đích.
- [x] Tạo `data/normalized/`, `data/canonical/`, giữ `data/samples/`.
- [x] Đối chiếu đủ 9.127 file, 2.327.680.425 byte và metadata trước/sau.
- [x] Hash 18 mẫu khớp; đọc 6 JSON và xác minh/giải mã 12 PNG thành công.
- [x] Bổ sung bốn biến đường dẫn và tài liệu ánh xạ Colab bên ngoài JSON gốc.
- [x] Cập nhật README, tài liệu dataset, AGENTS và planning.
- [x] Kiểm tra ignore rules, tập commit, lịch sử Git và phạm vi thay đổi.
- [x] Lint/format và 11 unit tests local đạt.
- [x] Commit đúng message: `279e65a38c44feca385b305e32e34be2c30510db`.
- [x] Commit đã có trên `origin/main`; xác minh lại trong M0-03.
- [x] [CI run 40207830248](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40207830248)
  thành công trên Python 3.11 và 3.12; không còn lỗi mở của M0-02.

Phạm vi riêng của M0-02: chỉ sắp xếp dữ liệu local, cấu hình đường dẫn, tài liệu
và commit/push. Không OCR lại, gọi Gemini, viết nghiệp vụ hoặc triển khai
DataPathResolver trong task này. Giới hạn đó được lưu ở đây; các quy tắc bảo toàn
dữ liệu và bảo mật lâu dài tiếp tục nằm trong [`AGENTS.md`](../AGENTS.md).

## M0-03 — Acceptance criteria

- [x] Đối chiếu nhánh, working tree, local/remote commit và CI của M0-02.
- [x] Đồng bộ M0-01/M0-02 theo GitHub; bỏ blocker đã giải quyết khỏi trạng thái hiện tại.
- [x] Tách giới hạn task cũ khỏi AGENTS, giữ nguyên các nguyên tắc kiến trúc.
- [x] Bổ sung kế hoạch M1-01 đến M1-04 với trạng thái dự kiến, chưa bắt đầu.
- [x] Rà soát `.gitignore`, Git index và kiểm tra cấu hình TOML/YAML.
- [x] Lint, format và 11 unit tests local đạt.
- [x] Xác minh cuối cùng dữ liệu, phạm vi thay đổi và các file chuẩn bị commit.
- [ ] Commit `chore(project): sync repository status and development roadmap`.
- [ ] Push bình thường lên `origin/main` và đối chiếu kết quả GitHub/CI.

M0-03 chỉ housekeeping và đồng bộ tài liệu, không gọi Gemini, xử lý OCR hoặc
viết code nghiệp vụ. Dừng sau khi hoàn tất M0-03.
