# M2-05 — Catalog giới hạn số công thức có thể chạy

- **Vấn đề:** catalog14 IDs chỉ đủ B02 gross profit; bốn ứng viên còn unavailable.
- **Ví dụ thực:** BBS2025 trang8 có mã50 “Lưu chuyển tiền thuần trong năm” ở payload
  và ảnh; ba dòng20/30/40 đã accepted nhưng dòng50 chưa có canonical mapping.
- **Nguyên nhân:** M2-04 catalog hẹp; không phải bằng chứng số liệu bị sai.
- **Ảnh hưởng:** chưa đối chiếu được net cash flow B03 bằng checker; QA vẫn có thể
  truy xuất raw extraction có nguồn, không được chặn do arithmetic thiếu dữ liệu.
- **Giải quyết trong M2-05:** một rule active B02 đủ ba toán hạng; giữ bốn ứng viên
  unavailable với missing IDs/lý do, không mở catalog hoặc suy zero từ dấu gạch.
- **Trước/sau:** chưa có arithmetic deterministic → hai check B02 thực PASS ở hai kỳ;
  B01/B02/B03 thiếu dữ liệu4/2/2, không có FAILED. Không coi missing là lỗi kế toán.
- **Hướng tiếp:** chỉ bổ sung mapping nhỏ khi Tech Lead giao phạm vi tiếp theo,
  đối chiếu label/code/dấu trên nguồn trước khi bật rule; chưa triển khai trong task này.

[API/pilot](../../../../docs/arithmetic-checks.md), [spec](../M2-05.md).
