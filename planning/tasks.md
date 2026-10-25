# Danh sách task

| ID | Tên | Trạng thái | Phạm vi |
| --- | --- | --- | --- |
| M0-01 | Initialize Project Repository | Hoàn thành theo tiêu chí cho phép báo cáo trở ngại xác thực; push đang bị chặn | Skeleton, cấu hình, tài liệu, kiểm tra và Git/GitHub |

## Acceptance criteria M0-01

- [x] Kiểm tra workspace, bảo toàn tài liệu và dữ liệu có sẵn.
- [x] Tạo đúng cấu trúc thư mục, Python packages và `.gitkeep`.
- [x] Tạo README, AGENTS và các tài liệu nền tảng được yêu cầu.
- [x] Xác nhận cấu hình hợp lệ và cài môi trường phát triển thành công.
- [x] Lint, định dạng và unit tests tối thiểu thành công.
- [x] Rà soát `.gitignore` và tập file sẽ commit, không chứa dữ liệu/secrets.
- [x] Khởi tạo Git trên `main` và tạo initial commit.
- [x] Tạo hoặc dùng repository GitHub phù hợp ở chế độ private, thiết lập `origin`,
      push thành công; hoặc ghi rõ trở ngại xác thực nếu không thể thực hiện.
- [x] `planning/current-status.md` phản ánh kết quả thực tế.

Repository private đã được tạo. **Push chưa thành công** vì token GitHub CLI
thiếu scope `workflow`; GitHub Actions chưa chạy. Tiêu chí GitHub được đáp ứng
theo nhánh báo cáo trở ngại xác thực, không phải nhánh push thành công. Cách
tiếp tục nằm trong [`current-status.md`](current-status.md).

Chưa có task tiếp theo được giao. Dừng sau M0-01.
