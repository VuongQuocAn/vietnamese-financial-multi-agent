# Danh sách task

| ID | Tên | Trạng thái | Phạm vi |
| --- | --- | --- | --- |
| M0-01 | Initialize Project Repository | Hoàn thành theo tiêu chí cho phép báo cáo trở ngại xác thực; push lúc khởi tạo bị chặn | Skeleton, cấu hình, tài liệu, kiểm tra và Git/GitHub |
| M0-02 | Reorganize Financial Dataset & Commit to GitHub | Chưa hoàn thành; phần local đã kiểm tra và commit, push còn chờ quyền `workflow` | Sắp xếp dataset local, cấu hình đường dẫn, tài liệu và Git |

## M0-01

Đã tạo skeleton, môi trường, tài liệu và initial commit
`9eb4483f4be4029c014a3a9552dfb5a1a91c8fea`. Lint/format và 11 unit tests đạt.
Repository ban đầu được tạo private; push bị chặn vì thiếu scope `workflow`.
M0-01 đáp ứng nhánh acceptance criteria cho phép báo cáo trở ngại xác thực.
Đến M0-02, người dùng đã chuyển repository sang public; agent không đổi visibility.

## Acceptance criteria M0-02

- [x] Kiểm tra workspace, đích không tồn tại, đủ dung lượng và cùng ổ đĩa.
- [x] Di chuyển nguyên trạng hai dataset vào `data/raw/` và `data/processed/`.
- [x] Tạo `data/normalized/`, `data/canonical/`, giữ `data/samples/`.
- [x] Đối chiếu đủ 9.127 file, 2.327.680.425 byte và metadata trước/sau.
- [x] Hash 18 mẫu khớp; đọc 6 JSON và xác minh/giải mã 12 PNG thành công.
- [x] Bổ sung bốn biến đường dẫn và hướng dẫn ánh xạ Colab bên ngoài JSON gốc.
- [x] Cập nhật README, tài liệu dataset và quy tắc AGENTS.
- [x] Xác minh ignore rules, tập staged, lịch sử Git và phạm vi file thay đổi.
- [x] Chạy lint/format, unit tests và kiểm tra cấu hình/tài liệu liên quan.
- [x] Tạo commit đúng message được yêu cầu.
- [ ] Push thành công lên `origin/main` mà không force push.
- [ ] Xác nhận task hoàn thành khi không còn lỗi chưa giải quyết.

Không đánh dấu M0-02 hoàn thành nếu push vẫn bị chặn. Trạng thái thực tế và
hướng xử lý được ghi tại [`current-status.md`](current-status.md).
Chỉ thực hiện M0-02, không tự bắt đầu task khác.
