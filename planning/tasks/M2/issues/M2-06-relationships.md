# M2-06 — Giới hạn nguồn, kỳ và catalog

## Vấn đề và ví dụ BBS2025

Đối chiếu tiền cuối kỳ2025 đã chạy được bằng canonical B01/110 và B03/70 trang5/8.
Các quan hệ còn lại thiếu dữ liệu hoặc căn cứ, không phải bằng chứng sai báo cáo.
Ảnh/caches giữ local ignored, không đưa dataset hoặc ảnh vào Git.

## Nguyên nhân

- B01 trang5 có số dư 01/01/2025, B03 trang8 có cột Năm2024. Không tự coi hai thời
  điểm này bằng nhau; evidence ngày cuối kỳ B03 ghi rõ2025, không ghi riêng ngày2024.
- Tổng nguồn vốn và lợi nhuận chưa phân phối không có trong pilot trang5/7/8;
  chưa khảo sát trang khác vì đã có check liên báo cáo thực đáp ứng task.
- Lợi nhuận giữ lại còn phụ thuộc cổ tức, phân phối, điều chỉnh; thiếu đủ thành phần
  thì không có đẳng thức trực tiếp được phép chạy.
- B03 trang8 có **raw mã50 lưu chuyển thuần và60 tiền đầu năm** nhưng catalog14 IDs
  chưa map. Adapter accepted-links chưa sử dụng hai dòng này. Đây là hạn chế mapping
  dù nguồn thực có số. Đồng thời ảnh không có dòng ảnh hưởng tỷ giá: thiếu evidence
  không phải zero, nên chỉ mở source mapping cũng chưa đủ bật công thức D.

## Ảnh hưởng và hướng giải quyết

QA vẫn dùng extraction và raw payload có nguồn. Chỉ kết luận về quan hệ tương ứng
bị giới hạn; không hạ accepted extraction hoặc suy vi phạm kế toán/pháp luật.
API trực tiếp cho phép mã/nhãn chính xác đã xác nhận, không bắt mở catalog toàn diện.
Không mở rộng source mappings mã50/60 khi FX/applicability vẫn thiếu; candidate D
giữ unavailable với lý do rõ. Nếu mở rộng sau review, xác nhận đủ rule/basis trước.
Không coi hạn chế này là blocker engineering M2-06 vì đã có check C thực.

## Kết quả trước/sau

Trước M2-06: chỉ có arithmetic cùng trang, không có đối chiếu B01/B03.
Sau M2-06: một check liên trang5/8 consistent ngày31/12/2025, difference0,
28 accepted extraction giữ nguyên;9 insufficient có missing inputs/issues riêng.
Giới hạn scope vẫn ghi `scope_unconfirmed`; không tạo verified facts.
