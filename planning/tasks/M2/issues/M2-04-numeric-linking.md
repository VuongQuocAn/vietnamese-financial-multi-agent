# M2-04 — Vì sao chưa nối được số liệu

## Hiện tượng
Pilot M2-04 xác nhận đúng 14 trong 20 nhãn nhưng không nối được số: 28 ô thuộc nhãn đã map bị từ chối, 12 ô thuộc 6 nhãn ngoài catalog chưa xét. Nhận diện tên không chứng minh hàng, cột kỳ và ô số tương ứng.

## Ví dụ thực tế
BBS2025 trang ảnh 7, B02: **4. Giá vốn hàng bán**, mã **11**, năm 2025 **417.992.011.559**, năm 2024 **319.074.961.905**, đơn vị **VND**. Trước M2-04a cả hai liên kết bị từ chối. Sau recovery và đối chiếu ảnh thủ công, hai liên kết thô accepted; chúng không phải financial facts đã xác minh.

Ảnh before/after có khung vị trí đọc trực tiếp được lưu local ignored ở `artifacts/item-mapping/M2-04a/before-page-7.png` và `after-page-7.png`. Không đưa crop nguồn vào Git theo quy tắc dữ liệu repository. Các khung chỉ minh họa vùng; không thay nội dung chữ hoặc số.

## Nguyên nhân
- Trang 5: bảng unresolved, layout false; 97 cells layout/geometry unresolved, provenance cell; `raw_layout_not_verified`.
- Trang 7: bảng unresolved dù layout true; 100 cells layout accepted nhưng geometry unresolved, provenance chỉ page.
- Trang 8: bảng unresolved, layout false; 121/123 cells layout accepted, 2 unresolved; geometry unresolved, provenance chỉ page; `table_layout_unresolved`.

Mapper M2-04 yêu cầu bảng accepted cùng layout và từng cell đủ điều kiện, nên cả ba bị chặn. Đây là nguyên nhân quan sát được; không khẳng định các điều kiện khác đều đạt. Trên trang 7 đã thấy bbox OCR của một số dòng lệch so với nội dung ảnh, bbox Gemini cũng lệch; không dùng cả hai làm geometry xác minh. Candidate của Gemini và OCR có 40 chuỗi giá trị trùng expected từ ảnh; OCR có label/code/value cùng hàng ở 28 ô trang 5/7. Trang 8 không có OCR table để kiểm tra đồng hàng; đối chiếu chuỗi chưa chứng minh layout hoặc không có mọi conflict khác.

## Ảnh hưởng
M2-05 trước đây thiếu đầu vào thực được nối có truy nguyên. Web Demo V1 không thể dựa vào các liên kết chưa đủ bằng chứng để hiển thị kiểm tra. Nhóm sáu liên kết mới chỉ là pilot thô; chưa chứng minh toàn bộ M2-05 hay demo end-to-end.

## Kết quả
Gemini `gemini-3.5-flash-lite`: 3 calls thành công, 0 retry. Adapter kiểm tra schema, binding, row/column, hình học vùng được đối chiếu, mapping/code, kỳ/unit và OCR độc lập; mỗi link xét riêng. Một reviewer đọc ảnh; không tự xác minh glyphs hay suy từ một Gemini response sang ground truth. Hai links trong checkpoint trước bị thu hồi vì gắn nhầm identity ảnh render PDF; sau đó kiểm tra lại trên ảnh OCR đã bind và mới accepted cùng bốn links khác.

| Chỉ số | Trước | Sau |
| --- | ---: | ---: |
| Nhãn mapped đúng | 14 | 14, mapper không đổi |
| Numeric links accepted | 0 | 6 |
| Accepted đúng / sai | 0 / 0 | 6 / 0 |
| Rejected | 28 | 12 |
| Unresolved / chưa xét | 12 chưa xét | 22 unresolved |

12 rejected sau là nhãn ngoài catalog, trước đó chưa xét; 22 unresolved thuộc nhãn đã map, không có đủ review/binding. Kết quả là pilot ba trang, một reviewer, không đánh giá accuracy toàn dataset. Hash 2 unified exports, 3 ảnh và 3 OCR JSON giữ nguyên. [API và evidence](../../../../docs/table-recovery.md).
