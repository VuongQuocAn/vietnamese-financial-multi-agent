# Khảo sát dữ liệu OCR và provenance — M1-01

Khảo sát local ngày **2026-10-26** (Asia/Bangkok), toàn bộ JSON trang hiện có.
Đây là kết quả quan sát cấu trúc, không phải contract được duyệt, ground truth
hoặc đánh giá độ chính xác tài chính. Không gọi API, tải model hay chạy OCR mới.

## 1. Tổng quan dataset

Ba mã BBS/BCC/BED, thư mục năm 2021–2025, 15 nhóm báo cáo local. Giữ nguyên
`data/raw/Financial_Report/` và `data/processed/Financial_Report_OCR/` theo
[quy tắc dữ liệu](dataset.md). Tổng **9.127 file, 2.327.680.425 byte**, khớp
baseline M0-02. Raw: 500 PNG / 1.490.251.896 byte; processed: 8.627 file /
837.428.529 byte. Số file dữ liệu khác số trang: 500 JSON trang có 500 danh tính
mã/năm/page riêng biệt, khớp 500 tham chiếu ảnh raw tồn tại; không suy ra số
trang của corpus nghiên cứu lớn hơn hay tính đầy đủ của từng báo cáo.

## 2. Thống kê inventory

| Loại | Số file |
| --- | ---: |
| PNG raw | 500 |
| JSON OCR trang | 500 |
| JSON phụ trợ | 33 |
| JSONL phụ trợ | 15 |
| PNG trong `ocr_crops` | 8.063 |
| Log / extension `.log` | 16 |
| Tổng | 9.127 |

Extension toàn dataset: `.json` 533, `.jsonl` 15, `.png` 8.563, `.log` 16.
Không có extension khác ở lần khảo sát này. Có 3 JSON phụ trợ ở cấp root,
không gán mã/năm (`unknown/unknown`), 4.409 byte. Mỗi nhóm mã/năm có thêm
2 JSON phụ trợ và 1 JSONL. Đã parse tất cả JSON/JSONL; không gặp JSON hỏng,
dòng JSONL hỏng hoặc file JSON không đọc được. Không kiểm tra giải mã toàn PNG.

| Mã/năm | Trang JSON = PNG raw | Crop PNG | Tổng file | Byte | Bảng |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBS/2021 | 28 | 418 | 478 | 188.005.924 | 30 |
| BBS/2022 | 26 | 257 | 313 | 158.571.374 | 30 |
| BBS/2023 | 29 | 472 | 534 | 161.207.349 | 36 |
| BBS/2024 | 26 | 413 | 469 | 142.601.286 | 25 |
| BBS/2025 | 24 | 416 | 468 | 153.938.655 | 25 |
| BCC/2021 | 40 | 375 | 459 | 204.404.089 | 44 |
| BCC/2022 | 38 | 251 | 331 | 61.605.500 | 36 |
| BCC/2023 | 44 | 1.934 | 2.027 | 215.071.861 | 38 |
| BCC/2024 | 41 | 1.001 | 1.087 | 202.109.255 | 38 |
| BCC/2025 | 2 | 85 | 93 | 11.416.853 | 0 |
| BED/2021 | 40 | 738 | 822 | 213.070.631 | 50 |
| BED/2022 | 41 | 273 | 359 | 91.356.408 | 43 |
| BED/2023 | 40 | 564 | 648 | 181.681.324 | 43 |
| BED/2024 | 40 | 566 | 650 | 163.959.831 | 44 |
| BED/2025 | 41 | 300 | 386 | 178.675.676 | 52 |

Các số file/byte trong bảng gồm raw và processed, chưa gồm 3 JSON root.
Tổng trang theo mã: BBS 133, BCC 165, BED 202. **BCC/2025 chỉ có 2 trang**
và không có table element: cần xác nhận phạm vi đầu vào trước xây Golden Dataset,
không tự kết luận báo cáo gốc thiếu hay lỗi OCR.

## 3. Cấu trúc JSON quan sát được

500/500 JSON trang là object với đúng ba top-level keys: `page` (dict),
`elements` (list), `provenance` (dict). Không có trường thiếu ở cấp này.
Trường có mặt trong mọi object quan sát được không tự trở thành bắt buộc trong
contract tương lai. Artifact schema đếm occurrence, số object cha, missing,
kiểu dữ liệu và null cho từng đường dẫn lồng nhau; array rỗng không tạo object
con giả. 85 đường dẫn field/item trong schema tổng, bao gồm các nhánh element.

`page` có `symbol`, `year`, `image` là str; `page`, `width`, `height`, `dpi`
là int, mỗi trường có mặt 500/500. `year` là chuỗi; không ép kiểu JSON gốc.
Không gặp metadata mã/năm lệch vị trí thư mục hoặc số trang không phải int.
Schema `provenance` ổn định về tên/kiểu trường trên 500 trang. Riêng
`signature_fallback_detector` có mặt nhưng null ở 500/500 trang, khác với thiếu key.

Heterogeneity chủ yếu do `elements` là tập hợp nhiều loại object. Trường `text`
có ở text element; `cells` chỉ ở table; `checked` chỉ ở checkbox. Không áp dụng
union keys như một danh sách required chung. Trong từng loại element hiện có,
các top-level keys quan sát được đều có mặt trên mọi instance, chưa thấy key
hiếm hoặc key bị thiếu riêng lẻ. `signature.confidence` có float và null.

## 4. Element taxonomy

Tổng **15.784 elements**; số trang trong các dòng có thể chồng lấp.

| Type | Elements | Trang chứa | Keys ngoài `id`, `type`, `bbox` |
| --- | ---: | ---: | --- |
| `text` | 14.211 | 499 | `text` |
| `table` | 534 | 298 | `name`, `crop`, `cells` |
| `checkbox` | 38 | 4 | `checked`, `choice`, `confidence`, `crop`, `group_id`, `label`, `label_text_ids` |
| `signature` | 224 | 102 | `role`, `signer_name`, `kind`, `confidence`, `crop`, `ink_view_crop`, `black_view_crop`, `red_view_crop`, `blue_view_crop` |
| `seal` | 148 | 146 | `seal_name`, `crop`, `black_view_crop`, `red_view_crop`, `blue_view_crop` |
| `seal_signature_region` | 213 | 111 | `seal_bbox`, `signature_bbox`, `signature_id`, `source`, `crop`, `black_view_crop`, `red_view_crop`, `blue_view_crop` |
| `red_mark` | 416 | 301 | `crop` |

Không phát hiện loại khác trong lần chạy; script không dùng whitelist để loại
bỏ type mới. `bbox` là list[int] bốn tọa độ; có mặt không có nghĩa hình học hợp lệ.
`seal_bbox` và `signature_bbox` là list[int]; `label_text_ids` là list (không
suy ra kiểu item nếu array rỗng). Các trường mô tả/crop/id là str; checkbox
`checked` là bool. Checkbox confidence: 38 float, không null; signature:
216 float, 8 null. Không có confidence trực tiếp ở text/table/cell/line hoặc
ba loại còn lại; không gán confidence mặc định và không diễn giải là accuracy.

## 5. Cấu trúc bảng và cells

**534 bảng / 298 trang, 21.461 cells, 21.419 line objects**. Số cells/bảng
min/median/max: **3 / 25 / 185**. Artifact lưu histogram cells/bảng, các row/col
và số cells từng row/col cho mỗi bảng. Số row phân biệt/bảng từ 1 đến 42;
số col phân biệt từ 1 đến 12. Phân bố số col:

| Số col phân biệt | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 12 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Số bảng | 5 | 17 | 268 | 42 | 116 | 37 | 33 | 8 | 5 | 2 | 1 |

Mỗi cell có `id` str, `bbox` list[int], `row` int, `col` int, `text` str,
`line_count` int, `lines` list, đủ 21.461/21.461. Mỗi line có `id`, `type`,
`text`, `cell_id` là str và `bbox` list[int], đủ 21.419/21.419. Không quan sát
`rowspan`/`colspan` hoặc representation header phân cấp riêng; không suy ra
không tồn tại header nhiều cấp trên ảnh. BCC/2022/9 và BBS/2023/6 có header
nhiều dòng khi kiểm tra trực quan.

Có **64 cells vượt lần xuất hiện đầu của cặp row/col**, ở 6 bảng trên 6 trang.
Đây là duplicate positions, không phải 64 bảng trùng. Không có row/col sai kiểu
hoặc âm theo kiểm tra script. Có 263 cell bbox không hợp lệ trên 17 trang;
keys vẫn tồn tại đầy đủ. Quy tắc hình học hiện dùng: bốn số hữu hạn và
`x1 < x2`, `y1 < y2`, chưa kiểm tra containment hoặc vượt kích thước trang.
Có 866 cell text rỗng trên 86 trang; có thể là ô trống có chủ đích hoặc thiếu OCR.

Không có bảng thiếu cells hoặc cells rỗng. Có **199 tham chiếu `table.crop`**
không có file tại suffix tương ứng (xem provenance). **365 bảng** có lưới row/col
không phủ kín hình chữ nhật min–max; đây là ứng viên sparse/merged/incomplete,
không phải kết luận mất ô. Không sửa hoặc suy ra cell/giá trị thiếu.

## 6. Provenance và tham chiếu đường dẫn

Giá trị khai báo trong 500/500 JSON:

| Trường | Giá trị khai báo |
| --- | --- |
| `architecture` | `multi_resolution_conditional_fast_first` |
| `layout_engine` | PaddleOCR PP-Structure filtered to table/image/seal |
| `text_detector` | PaddleOCR detector on low-resolution page view |
| `text_recognizer` | VietOCR batched in RAM |

Đây là metadata tự khai báo của OCR cũ, không phải xác minh đã chạy đúng engine,
phiên bản/model/hash hoặc chất lượng đầu ra. `detection_view` chứa width/height
int, scale_x_to_original/scale_y_to_original float. `checkbox_detection` chứa
native/magnified proposals/accepted int, threshold/proposal_threshold/seconds
float. Các detector/policy/threshold/count của signature, checkbox, seal,
`page_seconds` float và `notes` list[str] cũng có mặt 500/500. Các engine chính
không có biến thể giá trị; schema provenance không có trường thiếu theo trang.
Thông tin phiên bản tái lập OCR, nguồn báo cáo chính thức và quyền sử dụng còn TBD.

| Phân loại tham chiếu | Số lần |
| --- | ---: |
| Colab/Drive, suffix ảnh raw tồn tại local | 500 |
| Colab/Drive, suffix crop tồn tại local | 2.980 |
| Colab/Drive, suffix crop không tồn tại local | 572 |
| Tham chiếu local trực tiếp đã tồn tại | 0 |
| Giá trị đường dẫn thiếu | 0 |
| Mơ hồ hoặc không ánh xạ được ngoài nhóm suffix thiếu | 0 |

Đường dẫn nguồn có dạng Drive shortcut/Colab, không thể dùng trực tiếp như
đường dẫn local. Script chỉ đối chiếu marker root `Financial_Report` hoặc
`Financial_Report_OCR`, **toàn bộ suffix gồm mã/năm/cấu trúc con**, từ chối
`..`, marker không rõ, mã/năm sai; không tìm file theo basename. Trạng thái
`colab_suffix_exists` chỉ cho biết file đích ứng viên tồn tại; **chưa xác minh
danh tính gốc Drive/run nguồn** và chưa phải resolver production được duyệt.
Giữ nguyên đường dẫn gốc trong JSON; không công bố Drive IDs hoặc đường dẫn cá nhân.

572 lần thiếu nằm trên **193 trang**, gồm table.crop 199; seal có 52 ở mỗi
trường crop/black/red/blue (208); signature có 33 ở mỗi trường
crop/ink/black/red/blue (165). Đây là số lần tham chiếu, không phải số ảnh duy
nhất. Không coi 8.063 PNG crops là 8.063 trang hoặc tự tính ảnh thừa bằng phép
trừ: còn ảnh debug, ảnh cell và nhiều tham chiếu có thể dùng chung file.

## 7. Cảnh báo chất lượng dữ liệu

| Cảnh báo | Lần | Trang |
| --- | ---: | ---: |
| Cell bbox thiếu/sai hình học | 263 | 17 |
| Cell text rỗng | 866 | 86 |
| Crop suffix thiếu file | 572 | 193 |
| Row/col lặp vượt lần đầu | 64 | 6 |
| Element bbox thiếu/sai hình học | 49 | 19 |
| Không có text trong elements/cells/lines | 1 | 1 |

Không có key bbox thiếu trong corpus hiện tại: các cảnh báo bbox ở đây là
hình học không hợp lệ theo quy tắc nêu trên. BCC/2024/2 là trang gần trống,
có đồ họa/trang trí khi xem ảnh; `no_text_content` không tự chứng minh lỗi OCR.
Các số cảnh báo không đo CER/WER, accuracy bảng, sai số kế toán hoặc chất lượng
Gemini. Không có reference labels để đánh giá các chỉ số này.

## 8. Ứng viên trang bảng ngầm

**19 trang** không có table element nhưng có >=15 text bbox hợp lệ, tỷ lệ
text chứa chữ số >=0,25, >=3 nhóm hàng có >=3 phần tử, >=2 nhóm cột có >=4 phần
tử. Tọa độ gom bằng `round(position / 20)` pixel; script lưu thêm tín hiệu kỳ
nhưng không dùng làm điều kiện bắt buộc. Text numeric ratio dựa trên text lồng
nhau, tọa độ dựa trên text cấp trang; heuristic phụ thuộc DPI và có thể bỏ sót.

| Mã | Năm | Page trong JSON/file |
| --- | --- | --- |
| BBS | 2021 | 25, 28 |
| BBS | 2024 | 23 |
| BBS | 2025 | 8 |
| BCC | 2021 | 9 |
| BCC | 2022 | 7, 8, 21, 35 |
| BCC | 2023 | 37, 40 |
| BCC | 2024 | 35 |
| BED | 2022 | 31, 38 |
| BED | 2023 | 38 |
| BED | 2024 | 32, 38, 39 |
| BED | 2025 | 38 |

BBS/2021/28 có bố cục nhiều cột số không kẻ khung khi xem ảnh; được ưu tiên
pilot để kiểm tra. Chưa kiểm tra trực quan 18 ứng viên còn lại. Danh sách không
phải ground truth và M1-01 không reconstruction bảng.

## 9. Phương pháp chọn trang đại diện

Script chọn một trang mỗi mã/năm trước, tối ưu số đặc trưng mới, rồi thêm chín
trang theo đặc trưng và cân bằng số trang mỗi mã. Tie-break theo đường dẫn
tương đối có thứ tự, không random. Đặc trưng gồm tên biểu mẫu duy nhất được
regex nhận ra, object types, >=40 text elements, >=100 cells/trang, bảng ngầm,
từng mã cảnh báo. Trang nhắc nhiều biểu mẫu không nhận điểm phủ biểu mẫu.
Mọi `form_candidates` tự động mang `form_status: unverified` vì regex có thể
khớp tham chiếu trong phần kiểm toán/thuyết minh thay vì tiêu đề chính.

Pilot chọn trong 24 trang, cân bằng theo mã trước, rồi tối ưu đặc trưng chưa
phủ: trọng số 3 cho form/object/bảng ngầm, 1 cho các đặc trưng còn lại, tie-break
theo source. Manifest lưu đặc trưng, cảnh báo, số bảng/cells, lý do chọn và tọa
độ thống kê để tái lập. Tổng **24 trang, 8 mỗi mã, phủ 15/15 nhóm mã/năm**.

| Mã/năm | Các page được chọn | Lý do chính |
| --- | --- | --- |
| BBS/2021 | 9, 28 | B03 ứng viên, B09/bảng ngầm, text và chữ ký/con dấu |
| BBS/2022 | 7 | B02 ứng viên, bảng phức tạp, cell rỗng |
| BBS/2023 | 6 | B01 tiếp theo, bảng nhiều cells |
| BBS/2024 | 9, 10 | B02/B03 ứng viên, cell rỗng |
| BBS/2025 | 7, 8 | B02 ứng viên/crop thiếu và B03 ứng viên/bảng ngầm |
| BCC/2021 | 9, 31 | B01 ứng viên/bảng ngầm, B09 ứng viên/bbox bất thường |
| BCC/2022 | 9 | B02, duplicate row/col và cell bbox |
| BCC/2023 | 1, 13 | Checkbox/nhiều text; B02 ứng viên/crop thiếu |
| BCC/2024 | 2, 10 | No-text cần kiểm tra; B01 ứng viên/crop thiếu |
| BCC/2025 | 1 | Phủ báo cáo chỉ có hai trang; chữ ký/con dấu |
| BED/2021 | 12 | B03, bảng nhiều cells, crop thiếu |
| BED/2022 | 10 | B03, so sánh năm khác và crop thiếu |
| BED/2023 | 9, 10, 39 | B01/B02/B09 ứng viên, cell rỗng/crop thiếu |
| BED/2024 | 10 | B02 ứng viên/crop thiếu |
| BED/2025 | 11, 40 | B03/B09 ứng viên, cell rỗng/crop thiếu |

Số page là `page.page`/tên file, **không phải số trang in trong báo cáo**.
Không copy nội dung tài chính vào manifest chọn mẫu hoặc tài liệu public.

| Pilot | Lý do chọn và xác nhận trực quan |
| --- | --- |
| BBS/2021/28 | Tiêu đề B09, bảng ngầm, nhiều text, chữ ký/con dấu |
| BCC/2022/9 | Tiêu đề B02, header nhiều dòng, cảnh báo duplicate row/col |
| BED/2021/12 | Tiêu đề B03, bảng kẻ khung/phân cấp, cell rỗng/crop thiếu |
| BBS/2023/6 | Tiêu đề B01 tiếp theo, header nhiều dòng, bảng nhiều cells |
| BCC/2023/1 | Công bố thông tin với checkbox và nhiều text; không xác nhận B01–B09 |
| BED/2022/10 | Tiêu đề B03, bảng kẻ khung, đối chiếu crop thiếu giữa năm |

Đã xem **8 ảnh raw local**: sáu pilot trên, BBS/2024/6 (kiểm toán có nhắc cả
bốn biểu mẫu) và BCC/2024/2 (trang trí/no-text). Ghi chú riêng trong
`sampling_review.json` local, không phải golden annotations. Các trang khác
và nhãn tự động vẫn unverified; chưa tạo nhãn cell, giá trị hay kế toán.

## 10. Chuẩn bị Golden Dataset

Giữ page identity và nguồn JSON/ảnh tách khỏi phân loại biểu mẫu và nhãn con
người. Mỗi candidate cần xác nhận loại trang, header, ownership text/cell,
provenance cùng tình trạng thiếu crop trước annotation. Pilot đề xuất ở trên
phục vụ thiết kế quy trình, chưa là tập train/test hoặc nhãn đã nghiệm thu.

Quy trình Gemini-assisted sau này cần task/contract/Gateway/ngân sách riêng,
lưu model/prompt/version, structured output, chi phí và review của con người.
Không dùng OCR tự khai báo hoặc heuristic làm nhãn chuẩn; không lấy kết quả
Gemini làm nguồn thay thế báo cáo gốc. Các trang cùng báo cáo/công ty/kỳ cần
xem xét leakage khi xây tập đánh giá; policy split còn TBD.

## 11. Tái lập và giới hạn

Chạy từ root repository, Python 3.11+ standard library:

```powershell
python scripts/inventory_ocr_dataset.py --dataset-root data --output-dir artifacts/dataset-inventory --summary
```

Có thể dùng biến `DATASET_ROOT` thay mặc định; CLI có ưu tiên cao hơn. Dataset
không tồn tại sẽ báo lỗi, không tạo dữ liệu thay thế. Output không được nằm
trong raw/processed hay chứa dataset root; artifact symlink/hardlink bị từ chối.
Thống kê metadata full raw/processed trước/sau (path tương đối, size, mtime_ns,
inode) khớp nhau; SHA-256 **của bản metadata**, không phải nội dung toàn dataset:
`c92a8dd93accb74c936118b40eafc481febf8ec85559094c6c0d98b6217a16bb`.
Metadata chỉ là bằng chứng bảo toàn quan sát được, không thay thế content hash.

Artifacts local bị Git ignore: `inventory_summary.json`,
`element_schema_summary.json`, `page_manifest.jsonl`, `representative_pages.json`,
`pilot_candidates.json`, `inventory_warnings.jsonl`; `sampling_review.json` ghi
8 ảnh đã xem và không bị script ghi đè. Một lần inventory toàn bộ; sau khi
điều chỉnh chọn mẫu để tránh nhiều form mentions, chỉ dùng lại manifest đã có,
không chạy lại inventory toàn bộ. Script cuối tái tạo cùng 24/6 từ dữ liệu này.

Giới hạn: không hash toàn dataset, không giải mã 8.063 crops, không kiểm tra
tọa độ line/containment hoặc tính toán kế toán; không biết đầy đủ báo cáo gốc,
OCR run implementation, quyền phân phối hay độ đúng của 19 ứng viên bảng ngầm.
JSON phụ trợ/JSONL chỉ được kiểm tra khả năng parse, chưa khảo sát schema chính
thức của log. Metadata path mapping không xác minh nội dung hoặc nguồn Drive.

## 12. Task tiếp theo và câu hỏi chưa chốt

Bàn giao kết quả cho M1-02a (Raw OCR Contracts), M1-02b (Document Understanding
Contracts), M1-02c (Path Mapping Contract) trong [registry](../planning/tasks.md).
Không tự bắt đầu những task này. Cần chốt nullable confidence, row/col trùng,
bbox suy biến, ownership cell/line, cách biểu diễn header nhiều cấp, cảnh báo
crop thiếu và tiêu chí xác minh nguồn. Cần xác nhận root/run nguồn và phạm vi
BCC/2025; không tự sửa OCR, phục hồi crop hoặc suy ra schema kế toán.
