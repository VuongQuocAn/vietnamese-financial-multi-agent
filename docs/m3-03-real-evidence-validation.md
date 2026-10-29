# M3-03 — Targeted real-artifact validation

## Phạm vi và mẫu chốt trước đối chiếu

Ngày 29/10/2026; baseline runtime `3fca2b4`, không Gemini/OCR/extraction/replay pipeline.
Kiểm tra toàn bộ records trong hai export M1-16 existing/native và hai attempts W-07
storage/fresh-storage. Không chọn evidence theo khả năng PASS. Các copies W-04/05/06,
Web Demo attempts khác, M2 caches/quality và raw OCR được inventory riêng; không cộng
bản sao thành coverage PDF độc lập. Raw artifacts giữ read-only; outputs chi tiết ignored.

Mẫu PDF chốt theo trang/mã chỉ tiêu trước khi đọc nội dung extraction để so sánh:

| Loại | Trang PDF (one-based) | Mẫu |
| --- | ---: | --- |
| B01 | 5 | Mã 110, 130, 270: label/code và hai cột số; hai headers; hai context đầu |
| B01 | 6 | Mã 300, 410, 440: label/code và hai cột số; hai headers; hai context đầu |
| B02 | 7 | Mã 10, 20, 60: label/code và hai cột số; hai headers; hai context đầu |
| B03 | 8 | Mã 20, 50, 70: label/code và hai cột số; hai headers; hai context đầu |
| B09 | 14, 15 | Text region đầu/cuối và table cells đầu/giữa/cuối trong payload OCR M1-15, nếu tồn tại |

Mẫu thiếu hoặc không đọc rõ phải ghi missing/NOT VERIFIED, không thay bằng mẫu thuận lợi.
Đọc PDF trực tiếp qua render cục bộ, không OCR/text extraction. Reference chép từ ảnh
trước khi so với artifact; đây là kiểm tra trực quan bởi Implementation Engineer,
không phải independent human annotation hoặc benchmark. Không dùng JSON pointers
để tự xác nhận đúng trang hoặc đúng glyph. Không gộp metrics thành một accuracy.

## Artifact coverage

Inventory đọc nội dung/keys, không coi discovery description là raw document text:

| Nguồn persisted | Nội dung thực có | Phạm vi xử lý |
| --- | --- | --- |
| Raw OCR BBS/2025, 24 JSON trang | 745 text elements, 25 tables; còn cells/lines/raw IDs/bbox | Inventory toàn bộ; chưa có direct raw-OCR adapter M3-03, không chạy lại M1 |
| M1-15 pdf/page-{5,7,8,14,15}.json | 58 text regions, 10 table structures, gồm B09 trang 14–15 | Source controls cho unified; B09 trực quan, chưa materialize qua adapter vì không có unified export B09 |
| M1-16 existing.json | Trang 5: 6 text + 1 table/97 cells | Convert toàn bộ 7 records; thiếu document binding giữ quarantine |
| M1-16 native.json | Trang 5/7/8: 33 text + 3 tables/335 cells | Convert toàn bộ 36 records |
| W-07 storage và fresh-storage result.json | Mỗi snapshot 4 records B01/B01/B02/B03 trang 5–8, 24 context + 4 tables; 19 headers/417 cells | Convert toàn bộ 28 records mỗi snapshot; hai attempts riêng, cùng PDF |
| W-07 inventory trong hai snapshots | Mỗi snapshot 24 page classifications, gồm 16 B09 | Metadata/inventory, không có raw quotes/B09 tables trong nhánh này |
| Ba document.json của W-07 | Metadata tài liệu/session | Không tạo text/table evidence |
| Năm copies/snapshots Web khác và sáu M2 financial caches | Structured financial payload thật | Inventory-only; không cộng vào mẫu số conversion đã chọn hoặc số trang PDF độc lập |
| M2-07 review quality.json | 136 observations/quality/source projections | Không có complete OCR table/text export, không tái dựng quotes/tables từ projection |

Đây là correction cho preflight trước: đã có unified exports persisted, không chỉ
runtime/synthetic. Không suy toàn bộ dataset thiếu text/table từ W-07 result.json.
Inventory có 49 source files được hash trước/sau, gồm PDF gốc; không sửa source.
Raw OCR đủ 24 trang không có nghĩa đã đánh giá accuracy hay hỗ trợ adapter đủ 24 trang.

## Conversion, identity, persistence và retrieval

Thực chạy `scripts/validate_m3_document_evidence.py` trên toàn bộ scope đã chốt:

```powershell
.venv\Scripts\python.exe scripts/validate_m3_document_evidence.py --output artifacts/evidence/M3-03-real-validation/final
```

Output phải là thư mục mới. Chi tiết/source hashes/conflict probes ở output ignored;
không commit dữ liệu OCR, normalized/canonical payload hoặc ảnh PDF vào repository.

| Metric | Kết quả / mẫu số |
| --- | ---: |
| Source components dự kiến / converted | 99 / 99 (87 text, 12 tables) |
| Conversion failures trong selected scope | 0 / 99 |
| Exact source representation preservation | 99 / 99 |
| Indexed identities unique | 92 / 92 |
| Missing document identity, giữ quarantine | 7 / 99 |
| Indexed get sau restart, exact model JSON | 92 / 92 |
| Quarantine sau restart, exact model JSON | 7 / 7 |
| Document/snapshot list retrieval | 92 / 92 indexed records |
| Same payload put lặp, không mất/nhân bản | 99 / 99; quarantine vẫn trả quarantined |
| Different payload explicit conflict, không overwrite | 6 / 6 probes (text/table của ba indexed groups) |
| Source selector resolution/page metadata/raw-ID consistency | 1403 / 1403 references |
| Source bytes hash giữ nguyên | 49 / 49 files |

Exact preservation ở đây là raw text nguyên văn và toàn bộ typed source structure,
anchors/metadata qua model JSON; không yêu cầu output JSON có cùng indentation với
source. Selector consistency là đối chiếu với source artifact, không phải PDF accuracy.

Native M1 document binding dùng PDF source_ref fingerprint thực. Snapshot identity
được caller khai báo bằng locator của export persisted đã hash; đây là snapshot file,
không giả có extraction attempt ID upstream. Existing OCR chỉ có manifest reference,
không có fingerprint tài liệu gốc: truyền document_id=None, giữ cả 7 records unresolved.
W-07 giữ document_id/attempt_id nguồn. Không ghép exports vào W-07 attempts hoặc gộp
records khác nguồn vì cùng PDF/page/text. 99 records gồm các lần quan sát lặp cùng PDF,
không phải 99 nguồn độc lập. Không sửa runtime/CanonicalFinancialFact hoặc schema M1/M2.

## Source anchor correctness và unresolved provenance

PDF gốc truy cập được, 24 trang, SHA-256
`6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`.
Đã render trực tiếp, đọc ảnh trang 5/6/7/8/14/15; đúng nội dung mẫu trên 6/6 trang.
Số trang contract là PDF one-based; folios in trên giấy lần lượt 4/5/6/7/13/14.

Đối chiếu độc lập với bytes PDF: render bằng pypdfium2 ở 200 DPI, encode PNG bằng
Pillow, so PDF hash + image hash + dimensions với 8 W-07 records và 5 M1-15 records:
13/13 record occurrences khớp trên 6 trang PDF độc lập. Không gọi ingestion/validation
pipeline. Đây là bằng chứng page image binding, không chứng minh bbox/cell glyph đúng.

| Provenance | Kết quả |
| --- | --- |
| Level giữ từ source | 1299 page, 7 element, 97 cell references |
| SourceAnchor.status giữ uncertain | 1403/1403; không tự nâng sau review |
| Page-only thiếu raw anchor IDs | 1299/1403; giữ unresolved, không biến pointers thành cell IDs |
| Unsupported level vượt IDs hiện có | 0/1403 theo metadata checks |
| Cell IDs existing OCR | 97/97 khớp raw artifact IDs; **không** chứng minh geometry trên PDF |
| Exact bbox/token/cell geometry với PDF | **NOT VERIFIED** |
| Existing OCR binding tới PDF theo fingerprint | **UNRESOLVED**; không có PDF hash trong export |

## PDF-grounded evidence sample review

Reference số được chép trực tiếp từ ảnh PDF trước khi xem extraction sample;
labels/context được đọc trực quan trên ảnh gốc. Implementation Engineer (Codex)
thực hiện review này, chưa có independent human annotator/gold set. Không dùng
JSON pointers làm ground truth. Số liệu review chi tiết ở ignored pdf-reference.json,
web-sample-checks.json, manual-review.json và pdf-image-binding-checks.json.

| Metric mẫu B01/B02/B03 | Kết quả / mẫu số |
| --- | ---: |
| Physical sample rows / numeric glyphs độc lập trên PDF | 12 rows / 24 numeric tokens, 4 trang |
| Numeric token occurrences khớp PDF | 72/72: W-07 cũ 24, fresh 24, M1-native 18, M1-existing 6 |
| Numeric column/period association được đối chiếu rõ | 66/72; 6/72 unresolved ở M1-native trang 5 |
| Label và code tương ứng trên PDF | 36/36 row occurrences; bỏ khác biệt whitespace/linewrap khi so label |
| Hai period headers đọc đúng text | 24/24 occurrences; 2 headers M1-native trang 5 unresolved về cột |
| Hai context đầu đúng nội dung nhìn thấy | 24/24 occurrences |

Không diễn giải 72 lần khớp thành 72 reference độc lập: cùng 24 numeric tokens
được kiểm tra qua bốn groups. Label/context matching không phải exact whitespace
OCR accuracy toàn trang. Không suy độ đúng các cells ngoài mẫu từ kết quả này.

B09 có artifact OCR thật, vì vậy đã kiểm tra mẫu cố định trên trang 14/15:

| Metric B09 | Kết quả / mẫu số |
| --- | ---: |
| First/last text region mỗi trang khớp nội dung PDF | 4/4 |
| First/middle/last cell mỗi source table | 21 cells trong 7 source tables/fragments |
| Non-null cells exact glyph match | 14/21 |
| Null text giữ unresolved, không chấm là đọc đúng/sai | 5/21 |
| Exact glyph mismatch | 2/21: OCR `_`, PDF `-` |
| B09 direct adapter/persistence từ raw M1-15 payload | **UNSUPPORTED**, không có unified B09 export |

## Failure cases và giới hạn nghiệm thu

- M1-native trang 5: cả hai date headers có column=3; mỗi row mã 110/130/270 có
  hai numeric tokens khác kỳ cùng column=3. Text số khớp PDF nhưng 6 period bindings
  không đủ căn cứ. Giữ nguyên layout unresolved; không sửa/đoán cột.
- B09 glyph mismatch: page14/tables/2/cells/39 và page15/tables/1/cells/8 có `_`
  thay vì dấu gạch nhìn thấy. Adapter không normalize nguồn để che lỗi.
- B09 trang 15: PDF có 2 bảng nhìn thấy, OCR chia 4 fragments; trang 14 có 3/3 bảng.
  Không tuyên bố segmentation accuracy hoặc sửa lại bảng trong validation.
- Missing IDs/quarantine, raw OCR inputs chưa có direct adapter, candidate geometry
  và null text là limitations thật; conversion success không phủ nhận chúng.
- Chỉ sampled page/text/value grounding nêu trên được đối chiếu. Full-PDF accuracy,
  bbox/cell geometry accuracy và accuracy theo independent human gold: **NOT VERIFIED**.
  Không có benchmark hoặc một chỉ số accuracy tổng hợp; financial_fact_verified vẫn false.
- Mẫu số B01–B03 đã chốt gồm số dương; chưa đánh giá riêng dấu âm/zero/ngoặc ở
  các financial rows khác. Null/glyph/segmentation B09 được báo riêng, không bù vào mẫu số này.

Local real-artifact runner đã hoàn tất: không conversion/persistence/source-representation
failure trong 99 selected records. Đã hash lại PDF/source files không đổi. Zero Gemini,
OCR hoặc extraction calls; chỉ đọc persisted artifacts và render PDF để review.
Runtime SHA vẫn `3fca2b4`; validation bổ sung chỉ script/docs/planning.
CI40830297216 của runtime đã completed/SUCCESS đúng SHA được xác minh; kết quả đó
không thay thế các limitations/source failures nêu trên.
Ruff lint/format script mới, planning checker 93 tasks và diff check PASS. Không
chạy lại synthetic suites đã PASS vì không đổi runtime/contracts/adapters/repository.

Status **REVIEW**. Next action: Tech Lead nghiệm thu M3-03 cùng evidence bổ sung.
