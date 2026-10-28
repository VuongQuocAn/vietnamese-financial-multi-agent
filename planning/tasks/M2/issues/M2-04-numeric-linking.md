# M2-04 — Vì sao chưa nối được số liệu

## M2-04b — Automated Extraction

M2-04a cần ManualReview để có bản đọc vùng ảnh độc lập và OCR witness; vì vậy chỉ
6 links B02 accepted, B01/B03 vẫn thiếu bằng chứng theo policy manual. Runtime mới
dùng Gemini làm nguồn trích xuất chính, kiểm tra cấu trúc/ngữ nghĩa nhẹ và gắn trạng
thái `accepted_extraction`; giữ nguyên ý nghĩa và implementation manual path.

Ví dụ từ PDF thật BBS2025 trang7: “4. Giá vốn hàng bán”, mã11, header “Năm 2025”,
raw `417.992.011.559` → Decimal `417992011559`, VND/scale1. PDF/rendered-image hashes,
page, Gateway model/request ID và payload selectors được giữ. Không ManualReview
input, không OCR witness bắt buộc, financial_fact_verified=false. B01 mã110 tại
31/12/2025 `3.711.595.064` và B03 mã30 năm2025 `(7.672.311.772)` cũng accepted.

| Tập đánh giá | Manual-reviewed M2-04a | Automated M2-04b |
| --- | --- | --- |
| Baseline40 — B01 | 0 accepted | 10 đúng / 0 sai / 4 unresolved |
| Baseline40 — B02 | 6 accepted đúng | 10 đúng / 0 sai / 4 unresolved |
| Baseline40 — B03 | 0 accepted | 8 đúng / 0 sai / 4 unresolved |
| Baseline40 — tổng | 6 đúng,0 sai,12 rejected,22 unresolved | 28 đúng,0 sai,12 unresolved |
| Toàn output ba trang mới | Không cùng tập, không so trực tiếp | 28 đúng,0 sai,108 unresolved,0 uncertain |

Đối chiếu thủ công **sau** pipeline trên ba ảnh render PDF, một reviewer; đánh giá
toàn bộ28 accepted, không dùng expected40 làm runtime input. Mapping14 đúng/0 sai,
Decimal28; chưa đo accuracy toàn PDF. B03 “Lưu chuyển tiền thuần trong năm”, mã50,
`1.208.501.810`, unresolved do ngoài catalog. Lượt đầu Gemini sai table row-count
ở B01/B02; validator chặn, làm rõ prompt và recovery hai trang. Không sửa payload
hoặc nới bounds để tăng acceptance. 5 calls gồm2 recovery,0 transport retry;
B03 tốt giữ cache, không gọi lại. Header mô tả không phải numeric slot.

Ảnh thực local ignored `artifacts/item-mapping/M2-04b/live/page-5.png`,
`page-7.png`, `page-8.png`; không commit nguồn. Kết quả PDF entrypoint replay và
post-run evaluation trong `artifacts/item-mapping/M2-04b/pdf-replay.json`.
[API và evidence chi tiết](../../../../docs/automated-financial-extraction.md).
Chỉ chạy trang5/7/8 trong24 trang. M2-04b REVIEW; [CI40646568615](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40646568615)
PASS đúng implementation SHA `912916ed1318628750e160e28338a211e5fc2819`,
Python3.11/3.12. Chờ Tech Lead review.

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

## Nghiệm thu M2-04a
Tech Lead APPROVED ngày 2026-10-28 trong phạm vi Research MVP; task DONE. Pilot 40 slots: 6 accepted đúng, 0 sai, 12 rejected, 22 unresolved. 6 liên kết chỉ thuộc B02 trang 7, có manual image review; chưa có automatic glyph verification, chưa xác minh numeric linking thực tế cho B01/B03, chưa phải verified financial facts. [Implementation](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/4d6221cf222d3bf6faa1380da11cbbe92ffcd5bd); [CI40644142273](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40644142273) SUCCESS exact SHA Python 3.11/3.12. Nghiệm thu chỉ planning, không chạy lại pytest, Gemini hoặc CI.
