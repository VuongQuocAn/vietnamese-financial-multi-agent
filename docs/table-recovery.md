# Table recovery — M2-04a

`recover_table_structure(service, image, credential_ref=..., model=...)` tái sử dụng structured OCR qua Gateway; trả candidate, không xác nhận bảng hay fact. `link_reviewed_candidate(page, image, recovery, review)` kiểm tra riêng một liên kết và trả `LinkDecision`. Không sửa UnifiedPage hay OCR. `image` phải được caller bind bằng `load_verified_image` và mapping/identity đã được duyệt, hoặc bằng chứng tương đương; identity tự khai không chứng minh binding. Chỉ nhánh `existing_ocr` có witness OCR độc lập mới có thể accepted; native Gemini không thể làm witness cho chính Gemini.

`ManualReview` là bản đọc ảnh độc lập, có reviewer, SHA256, text, row/column và bbox gốc cho title, unit, label, code, header, value. Reviewer phải thực sự đối chiếu ảnh; API không tự xác minh danh tính reviewer hoặc đọc chữ từ pixels. Review phải lưu riêng khỏi response Gemini. Adapter kiểm tra binding identity/hash, kích thước PNG, schema payload Gemini, source, vị trí duy nhất, đối chiếu text và row/column, hình học các vùng, catalog/code, kỳ/unit, và witness text/row OCR độc lập. Bbox do Gemini hay OCR dự đoán không được nâng thành geometry đã kiểm chứng. OCR chỉ corroborate, chưa chứng minh độc lập nội dung ảnh. Thiếu hoặc mâu thuẫn → unresolved; một bảng unresolved không tự được accepted toàn bộ.

Link accepted là raw structural link, mang vùng ảnh đã review và các selector OCR gốc; `normalized_value=null`, `financial_fact_verified=false`. Region ảnh được giữ ở provenance page kèm bbox, không tạo OCR cell ID. OCR cell references giữ selector và ID, bbox không verified. Manual review vẫn là một thành phần bắt buộc của pilot; chưa có cơ chế tự động độc lập xác minh glyphs. Không dùng output Gemini làm review.

## Pilot

Ba ảnh BBS2025/5,7,8: Gemini `gemini-3.5-flash-lite`, 3 calls, 0 retry. Expected 40 ô đọc từ ảnh trong artifacts local; candidate label/code/period/value khớp 40/40 chuỗi. OCR gốc có 40/40 chuỗi giá trị; đồng hàng label/code/value 28/28 trên trang 5/7, trang 8 không có OCR table nên 12 ô chưa kiểm tra đồng hàng. Các so sánh này không tự accept.

Sau kiểm tra, 6 links của ba dòng B02 trang 7 (doanh thu thuần, giá vốn, lợi nhuận gộp; mỗi dòng hai kỳ) accepted và khớp expected; 0 accepted sai; 12 rejected do ngoài catalog; 22 unresolved do chưa có đủ binding/region review. Một reviewer, không second review; không suy accuracy toàn dataset. Có bbox OCR và Gemini bị lệch so với ảnh: giữ nguyên và không sử dụng. Hai unified exports, ba PNG và ba OCR JSON giữ nguyên hash trước/sau pilot.

Artifacts local ignored tại `artifacts/item-mapping/M2-04a/`: expected, candidate, `verify_pilot.py`, output từng link, đối chiếu OCR, cùng ảnh crop trước/sau có khung xác minh. Không commit OCR, ảnh nguồn hoặc output lớn. [Issue](../planning/tasks/M2/issues/M2-04-numeric-linking.md).
