# M1-13b — Structured OCR Quality Improvement

28/10/2026; REVIEW, chờ Tech Lead. Baseline acceptance `97d8d71`; không M1-14.
Usage: `python scripts/run_ocr_correction_pilot.py --structured-quality --live --key-index 0`.
Bỏ --live: hai verified images + baseline replay API0, không tạo lại baseline bằng API.
Input roots theo `.env.example`. Artifacts riêng ignored `artifacts/ocr-correction/M1-13b/`.

Component validator nhận source envelope bắt buộc, so exact page/hash/dimensions với
verified image, kiểm tra bytes/decode; mismatch → rejected toàn bộ, không giữ components.
Text và cell text được xét độc lập với layout/geometry. accepted nghĩa là cấu trúc
hợp lệ, KHÔNG là xác nhận nội dung đúng ảnh hoặc sự thật tài chính. Unknown/inferred
text giữ unresolved; text sai kiểu bị rejected. Sai table/container/cell không xóa
components khác. Cell overflow/duplicate positions làm layout unresolved; giữ nguyên
số, declared dimensions và positions, không infer dimensions, rescale hoặc đảo axes.
Mọi bbox model vẫn unresolved vì chưa independently verified; bounds_valid chỉ kiểm
tra kiểu/giới hạn pixel, không chứng minh đúng vị trí. Top-level status xét content/layout;
geometry có trạng thái riêng. Full-page mới cả hai vẫn unresolved, nhưng giữ components.

Schema v2 cho null text không chắc chắn; prompt ưu tiên text/digits → membership bảng
→ indices → bbox tùy chọn; yêu cầu đếm cả label columns/header rows. Gateway/cache/
quota không sửa. Local schema-invalid JSON hoàn chỉnh có thể salvage từng component;
provider error, truncated/invalid JSON không salvage. V1 API/validator giữ compatibility.

| Chỉ số cấu trúc | BCC baseline replay | BED baseline replay | BCC OCR mới | BED OCR mới |
| --- | ---: | ---: | ---: | ---: |
| Text elements accepted | 20 | 25 | 38 | 17 |
| Tables accepted / returned | 0/1 | 2/3 | 0/1 | 0/3 |
| Cell text accepted | 12 | 20 | 12 | 29 |
| Cell layout accepted | 9 | 16 | 9 | 22 |
| Geometry accepted / unresolved | 0/32 | 0/45 | 0/50 | 0/46 |
| Bbox bounds_valid (chưa verified) | 32 | 45 | 50 | 46 |

M1-13a all-or-nothing từng loại toàn bộ hai trang: retained text/tables/cells =0/0/0.
**Validation-only** trên đúng responses persisted: giữ45 texts,2 tables,32 cell texts
(25 cell layouts), không cải thiện nội dung đọc. Hai bảng baseline accepted chỉ có
headers, chưa có data cells. **OCR mới**:55 texts,0 tables,41 cell texts (31 layouts);
text segmentation khác (BCC tách nhiều dòng), không coi tăng số elements là accuracy.
BED mới thêm data cells cho hai bảng trước chỉ có headers; các label cells làm lộ
column-count mismatch. Không che giấu valid tables giảm2→0, không tự sửa dimensions.

Đối chiếu ảnh BCC: baseline structured header đã đúng `BỈM SƠN`, OCR mới vẫn đúng;
baseline có từ thừa `đê` ở `vấn đề đê môi trường`, OCR mới đọc `vấn đề môi trường`,
không còn từ thừa. Đây là một cải thiện đọc quan sát được, không accuracy toàn trang.
Không chạy lại vision correction M1-13a (kết quả lịch sử correction0 giữ nguyên).

Đối chiếu trực quan10 số BED (sáu ô lương của ba người, hai doanh thu thuê và hai khoản
thuê tối thiểu): **10/10** giá trị được xem khớp ảnh trong cells mới. Baseline6 nằm
trong cells và4 trong text rời, đều đã đọc đúng; cải thiện membership, không chứng
minh tăng digit accuracy trên mẫu này. Giá trị/đối chiếu chi tiết chỉ trong private
manual-comparison.json. Không auto-confirm/apply số; chưa ground truth toàn dataset.

Crop BED table_001 lấy trực tiếp original PNG, source bbox **[345,547,2297,874]**,
1952×327 pixels, không resize. Đã xem original và crop để kiểm tra trọn bảng lương;
envelope giữ parent image SHA-256, crop hash, element ID và coordinates. Model bbox
chỉ có crop-local space; không tự ánh xạ sang trang. BCC raw bbox chỉ cắt một phần
bảng, skip crop, không recovery. **Request crop BED timeout**, không output để so sánh
crop/full-page, không retry hoặc đổi key.

Live đúng **3 attempts:2 successful full-pages +1 crop timeout**. Usage provider-reported
của hai successes: **2999 input +7060 output =10059 tokens**; crop usage unknown1.
**Tổng usage thực tế cả pilot chưa xác định**, không coi10059 là tổng đầy đủ.
BCC1499/3774/5273, BED1500/3286/4786 (input/output/total). Source raw/images, baseline
responses và frozen manifest đối chiếu trước/sau bất biến. SDK boundary có PNG bytes
và hash cho cả3 attempts. Quota15 RPM/250000 TPM/500 RPD owner-attested, không total
input cap, retry/rotation; money NOT_CONFIGURED, không claim billing0/remaining quota.

Local:8 focused mới +9 image integration cũ passed; Ruff files thay đổi, planning và
diff check đạt. Không hàng trăm regressions, không API/cache probes. Một implementation
commit/push, CI exact SHA kiểm tra conclusion sau push; kết quả/SHA trong bàn giao cuối,
không publication commit. Private responses/crop/manifest/usage/manual comparison giữ riêng.

Next action: Tech Lead review implementation và limitations pilot; không tự DONE/M1-14.
