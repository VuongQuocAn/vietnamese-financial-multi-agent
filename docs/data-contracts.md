# Data contracts

M1-02a triển khai `raw_ocr_v1`; M1-02b bổ sung `document_understanding_v1`;
M1-02c bổ sung `path_mapping_v1` trong `document_processing`.
Các giao tiếp nghiệp vụ khác vẫn ở mức khái niệm theo báo cáo giữa kỳ, Chương 4–5;
không suy ra schema kế toán hoặc Canonical Evidence từ OCR.

## Raw OCR Contract — raw_ocr_v1

Nguồn thiết kế: [khảo sát M1-01](ocr-data-discovery.md) và JSON mẫu có mục đích.
Models nằm ở `src/document_processing/contracts/raw_ocr.py`, validation ở
`validation.py`. Import qua namespace
`vietnamese_financial_multi_agent.document_processing.contracts`.
Contract chỉ diễn giải dữ liệu đã OCR; không đọc file, resolve paths, chỉnh OCR,
tái dựng bảng hoặc chuẩn hóa số liệu/kỳ kế toán.

| Model | Nội dung |
| --- | --- |
| `OCRPage` | Root gồm page, elements, provenance, đều bắt buộc |
| `OCRPageMetadata` | symbol/year/image là string; page/width/height/dpi là int |
| `OCRBoundingBox` | List đúng bốn int [x1, y1, x2, y2] theo quan sát nguồn |
| `OCRText` | id/type/bbox/text |
| `OCRTable` | id/type/name/bbox/crop/cells |
| `OCRTableCell` | id/row/col/bbox/text/line_count/lines |
| `OCRTextLine` | id/type=text/bbox/text; cell_id có thể thiếu hoặc null |
| `OCRCheckbox` | checked bool, choice/confidence/crop/group_id/label/label_text_ids |
| `OCRSignature` | role/signer_name/kind, confidence nullable, crop và bốn debug crops |
| `OCRSeal` | seal_name, crop và black/red/blue crops |
| `OCRSealSignatureRegion` | seal_bbox/signature_bbox/signature_id/source và crops |
| `OCRRedMark` | crop và id/type/bbox |
| `OCRProvenance` | Toàn bộ detector/policy/notes/timing và metadata nguồn |
| `OCRDetectionView`, `OCRCheckboxDetection` | Models metadata lồng trong provenance |

`OCRElement` là discriminated union theo `type` cho đúng bảy loại quan sát:
text, table, checkbox, signature, seal, seal_signature_region, red_mark.
Fields riêng từng loại được kiểm tra riêng; không thêm confidence cho loại khác.
Confidence chỉ nullable ở signature, key confidence vẫn bắt buộc. Số dùng union
int/float để giữ biểu diễn số JSON nguồn; không nhận bool hay chuỗi số.
Các fields đã quan sát là bắt buộc, trừ `cell_id` có thể không được cung cấp.

### Structural validation

`parse_raw_ocr(payload)` nhận object JSON đã decode, trả `OCRPage` hoặc ném
`RawOCRStructuralError`. Models dùng strict types và extra=allow ở mọi cấp.
Root/page/provenance sai kiểu, elements không phải list, thiếu fields bắt buộc,
row/col sai kiểu, bbox không đủ bốn int, nested cells/lines sai kiểu đều thất bại.
Không trả trang hợp lệ một phần khi một element lỗi. Non-finite numeric values
ở fields được định kiểu cũng bị từ chối.

Exception chứa `issues` gồm code/path/message và `payload` là bản sao đầy đủ
đầu vào. Path là tuple key/index tương ứng JSON nguồn, ví dụ
`("elements", 0, "cells", 1, "row")`; root lỗi có path rỗng.
Thông báo exception mặc định chỉ chứa số issues, không in nội dung OCR.
`OCRPage.model_validate` và `model_validate_json` cũng dùng được, nhưng trả
`pydantic.ValidationError` với loc có thêm tag của discriminated union.

Unknown element type: từ chối toàn trang có cấu trúc bằng `union_tag_invalid`,
giữ toàn payload trong exception; không bỏ element và không đổi thành loại đã biết.
Thiếu discriminator có lỗi riêng. Type mới cần review/version contract trước sử dụng.

### Quality validation

`validate_quality(page)` chạy riêng sau parse, trả list `QualityIssue` bất biến
gồm code/path/message. Không sửa model và không tác động khả năng parse.

| Code | Điều kiện |
| --- | --- |
| invalid_bbox_geometry | x1 >= x2 hoặc y1 >= y2, kể cả đảo cả hai trục |
| bbox_outside_page | Bất kỳ tọa độ âm hoặc vượt width/height trang |
| invalid_page_dimension | width/height/dpi không dương |
| duplicate_cell_position | Cặp row/col lặp sau lần đầu trong bảng |
| negative_cell_position | row hoặc col âm |
| sparse_table | Positions không phủ hình chữ nhật min/max; không suy ra ô thiếu |
| empty_cell_text | Text cell bằng chuỗi rỗng, có thể có chủ đích |
| line_count_mismatch | line_count khác số lines |
| confidence_out_of_range | Confidence khác null nằm ngoài [0, 1] |
| duplicate_id | ID trùng trong cùng collection elements, cells hoặc lines |
| cell_reference_mismatch | cell_id được cung cấp nhưng khác ID cell chứa line |
| unresolved_signature_reference | signature_id không trỏ đến signature trong trang |
| unresolved_text_reference | String label_text_ids không trỏ đến page text |
| unresolved_reference_type | Item label_text_ids chưa có schema nhận diện |

Kiểm tra bbox trên element, cell, line, seal_bbox và signature_bbox. Không áp đặt
cell phải nằm trong bbox bảng, không suy ra grid đầy đủ, merged cells hay header.
Không kiểm tra crop tồn tại hoặc ánh xạ đường dẫn; nhiệm vụ này thuộc resolver sau.
Các issues là tín hiệu review, không phải nhãn lỗi hay số đo chất lượng tài chính.

### Source preservation và versioning

`page.export_source()` dùng JSON dump với exclude_unset=True, giữ values, extra
fields lồng nhau, null đã cung cấp, thứ tự arrays, dấu câu/Unicode/whitespace,
chuỗi số tiền, year string và đường dẫn Colab. Không thêm defaults bị thiếu hoặc
contract version vào payload; không sắp xếp, clamp, thay row/col hay sửa provenance.
Kết quả tương đương cấu trúc/giá trị JSON, không cam kết byte-for-byte, indent,
thứ tự object keys hoặc cách escape của file gốc. API này không ghi file nguồn.
Caller không nên sửa model rồi gọi export nếu muốn giữ nguyên bản OCR đã parse.

Version thuộc code qua `RAW_OCR_CONTRACT_VERSION`. Một schema duy nhất tại
`schemas/raw_ocr_v1.schema.json`, sinh lại bằng:

```powershell
python scripts/export_raw_ocr_schema.py
```

Unit test so sánh artifact với `raw_ocr_json_schema()`, đồng thời kiểm tra
discriminator, round-trip mọi loại và nested extras. JSON Schema mô tả cấu trúc;
strict Python types và quality rules được kiểm tra bằng Python, không phải schema.

### TBD và ranh giới các lớp sau

`label_text_ids` chỉ thấy arrays rỗng trong M1-01: giữ list JSON values, chưa chốt
item schema; strings có thể được kiểm tra liên kết, loại khác ghi issue riêng.
`signature_fallback_detector` chỉ thấy null: v1 nhận null, giá trị khác trả lỗi
structural giữ payload, cần review khi có bằng chứng mới. Không bịa model version,
OCR run identity hoặc môi trường. Non-integer bbox cần version review theo nguồn
thực tế; nullable confidence hiện chỉ được duyệt cho signature.

Document Understanding Contract (M1-02b) biểu diễn kết quả hiểu tài liệu có
liên kết raw riêng theo phần bên dưới. Canonical Financial Evidence thuộc lớp evidence sau chuẩn hóa
kế toán; cả hai chưa triển khai ở M1-02a. Path Mapping Contract (M1-02c), nguồn
Drive/run, missing crops, ownership nâng cao và ground truth vẫn ngoài phạm vi.

## Document Understanding Contract — document_understanding_v1

Luồng: Raw OCR → Document Understanding → Accounting Normalization.
M1-02b chỉ định nghĩa data models/validation/serialization, không chạy classification,
reconstruction, correction, Gemini hoặc normalization. Không import accounting/evidence/
agents/verification/outputs. Raw OCR v1 và JSON nguồn không thay đổi.

Implementation: `document_understanding.py`, `document_understanding_validation.py`
trong `src/document_processing/contracts/`; public API qua namespace contracts như Raw OCR.

| Model / type | Fields và ý nghĩa |
| --- | --- |
| `DocumentUnderstandingResult` | Bắt buộc contract_version, raw_page, classification, text_regions, tables, issues; page-level |
| `RawPageIdentity` | symbol/year/image string, page int bắt buộc; source_ref string/null tùy chọn |
| `SourceAnchor` | page và status bắt buộc; element_id/table_id/cell_id/line_id, observed_bbox/proposed_bbox tùy chọn nullable |
| `DocumentClassification` | label string/null, status, anchors bắt buộc; confidence int/float/null tùy chọn |
| `UnderstoodTextRegion` | id/text/anchors/status bắt buộc; reading_order int/null và issues list/null tùy chọn |
| `UnderstoodTable` | id/origin/anchors/cells/status bắt buộc; issues list/null tùy chọn |
| `UnderstoodCell` | id/row/col/text/anchors/status bắt buộc; rowspan/colspan int/null và issues list/null tùy chọn |
| `ResolutionStatus` | Literal resolved / uncertain / unresolved |
| `UnderstandingIssue` | code string, path list các string/int, message ngắn; không thêm severity thiếu căn cứ |

Classification label là vocabulary mở, không có taxonomy bắt buộc. `label=null`
biểu diễn chưa biết; string `unknown` hoặc rỗng bị quality validator báo issue,
không được coi là loại báo cáo. Candidate có label cần anchors; không bắt confidence.
Không nhận diện B01/B02/B03/B09 bằng logic tại đây.

### Provenance và quy ước cấu trúc

Identity gồm symbol/year/page/image; không cam kết tổ hợp này duy nhất giữa OCR runs.
`source_ref` là locator hoặc run/artifact identity nguyên văn caller cung cấp khi có;
không tự sinh, resolve, đọc file hay kiểm tra đường dẫn tồn tại. Chưa có source_ref
thì global identity vẫn chưa xác minh; không diễn giải identity thành khóa toàn cục.
Mọi anchor của result phải có cùng identity, kể cả source_ref nếu cung cấp.

`element_id` trỏ tới page.elements. Nếu dùng `table_id`, đó là ID OCRTable ở page.elements;
`element_id` nếu có phải bằng table_id. `cell_id` cần table_id; `line_id` cần table_id
và cell_id, trỏ tới lines của cell. IDs chỉ duy nhất trong collection chứa nó:
text_regions/tables riêng trong result, cells trong mỗi output table; raw elements
trong page, raw cells trong table, raw lines trong cell. Không tìm cell/line toàn trang
hoặc chọn match đầu khi nhiều match. Vị trí row/col không dùng làm identity.

Bbox là list đúng bốn strict int [x1,y1,x2,y2], pixel ảnh trang gốc theo Raw OCR.
`observed_bbox` là bbox nguồn; nếu anchor trỏ OCR element/cell/line thì phải bằng bbox
của đối tượng cụ thể đó khi đối chiếu raw. Vùng ảnh không có OCR ID dùng image trong
page và observed_bbox; status phải uncertain/unresolved. `proposed_bbox` là vùng do
bước xử lý sau đề xuất/tổng hợp, không thay thế observed_bbox hoặc làm identity.
Không chuyển tọa độ, không tự resolve crop path. Một object có nhiều anchors để lưu
đủ các thành phần nguồn; contract không chứng minh danh sách đó đầy đủ so với thuật toán.

`ocr_table` cần ít nhất một table anchor có table_id. `inferred_from_text` có thể chỉ
trỏ nhiều OCRText hoặc vùng ảnh; không cần OCRTable. Row/col theo chỉ số zero-based;
không đòi grid chữ nhật hoặc header, không điền ô thiếu, không coi sparse là lỗi.
Spans chỉ nhận diện khi có bằng chứng: missing hoặc null đều chưa biết, explicit 1
là đã xác định span một ô. Không có header inference hoặc header tree trong v1.
Text, dấu tiếng Việt, whitespace và chuỗi `1.234.567` giữ nguyên, không parse kế toán.

### Resolution và hai cấp validation

- resolved: bước xử lý đã xác định kết quả với các anchors resolved hợp lệ theo
  kiểm tra có sẵn. Không chứng minh đúng kế toán hoặc accuracy thực nghiệm.
- uncertain: có candidate nhưng còn mơ hồ về cấu trúc/diễn giải/nguồn.
- unresolved: chưa đủ cơ sở xác định, vẫn được lưu text/candidate và issues.

`parse_document_understanding(payload)` nhận JSON object đã decode, trả toàn result
hoặc `DocumentUnderstandingStructuralError`. Exception giữ bản sao payload và list
`StructuralIssue` code/path/message; paths tuple theo JSON thật, không log nội dung.
Models Pydantic v2 strict, extra=forbid ở tất cả object mới: output ứng dụng sở hữu
schema nên unknown fields là lỗi hiển thị, không bỏ âm thầm. Khác với raw extra=allow
để bảo toàn format bên ngoài. Required/type/version/literal/nested/bbox shape lỗi
structural; không coercion bool/string thành int, không nhận NaN/Infinity.
`model_validate_json` hỗ trợ parsing JSON, lỗi `ValidationError` có loc; JSON sai
cú pháp có loc rỗng và code json_invalid.

`validate_understanding_quality(result)` chạy độc lập, trả issues mới, không trộn vào
result.issues hoặc sửa output. Caller có thể lưu issues sau review. Quy tắc gồm:

| Code | Kiểm tra |
| --- | --- |
| duplicate_id / empty_id | ID trùng/rỗng trong collection output tương ứng |
| missing_provenance | Object không có anchors, hoặc anchor thiếu OCR reference và vùng ảnh quan sát |
| empty_source_identity / empty_source_reference | Fields identity hoặc source ID được cung cấp nhưng rỗng |
| anchor_page_mismatch | Identity anchor khác result, kể cả source_ref |
| ambiguous_cell_reference / ambiguous_line_reference | Thiếu container IDs cần thiết |
| source_context_mismatch | element_id khác table_id được cung cấp |
| invalid_bbox_geometry | observed/proposed có x1 >= x2 hoặc y1 >= y2 |
| negative_cell_position / invalid_span | row/col âm; spans đã cung cấp <= 0 |
| duplicate_cell_position | Nhiều output cells cùng row/col trong một bảng, chỉ báo rủi ro |
| empty_text / negative_reading_order | Text rỗng/whitespace hoặc thứ tự đọc âm |
| missing_ocr_table_reference | origin ocr_table thiếu table_id trong table anchors |
| invalid_classification_label / confidence_out_of_range | Unknown label dùng string/rỗng hoặc confidence ngoài [0,1] |
| status_conflict | resolved object không có đủ anchors resolved hợp lệ; resolved classification thiếu label; resolved image-only/invalid anchor |

Đối chiếu nguồn chỉ chạy khi gọi tường minh
`validate_understanding_quality(result, raw_page=page)` với `OCRPage` đã parse.
Bổ sung raw_page_mismatch, unresolved_source_reference, ambiguous_source_reference,
reference_type_mismatch và observed_bbox_mismatch. Không tự tìm trang hoặc fallback ID.
Caller chịu trách nhiệm binding source_ref tới đúng raw_page: raw v1 chưa có run ID
để validator tự chứng minh binding này. Khi không truyền raw_page, không được suy ra
raw references tồn tại/duy nhất chỉ vì standalone validator không trả issues.

Không ép raw bất thường thành bảng hoàn hảo. Geometry sai, empty cell, duplicate positions
vẫn parse/export được; raw duplicate IDs chỉ làm liên kết mơ hồ, không loại bỏ dữ liệu.
Quality validation không đánh giá semantics tài chính, bbox containment/image bounds,
span overlap, completeness của anchors hay inference correctness. Không tự hạ status,
clamp confidence, sửa text, vị trí hoặc spans. Status mô tả resolution theo linkage,
không bảo đảm object không có quality issues khác (ví dụ empty text nguồn).

### Serialization, schema và TBD

Version bắt buộc trong output: `document_understanding_v1`; không chèn vào raw.
`export_result()` dùng mode=json/exclude_unset=True, giữ missing khác explicit null,
Unicode, text số và thứ tự arrays. Optional mặc định None trong Python, không có
nghĩa đã quan sát null. Dùng export_result để round-trip payload; model_dump mặc định
của Pydantic có thể materialize defaults. Không cam kết byte-for-byte JSON.

Schema sinh từ code, test đồng bộ với artifact:

```powershell
python scripts/export_document_understanding_schema.py
```

Artifact: `schemas/document_understanding_v1.schema.json`. Schema mô tả cấu trúc;
quality rules và strict Python type behavior được kiểm tra bằng code/tests.
Fixtures hoàn toàn synthetic, không dùng như ground truth tài chính.
Taxonomy được duyệt, global run identity, backward compatibility/migration,
header relationships và đối chiếu đa trang còn TBD cho task được giao sau.

## Path Mapping Contract — path_mapping_v1

Implementation: `path_mapping.py`, `path_mapping_validation.py` trong contracts;
public API qua `vietnamese_financial_multi_agent.document_processing.contracts`.
Không thay đổi hai contracts cũ. Đây là models, lexical rules và quality validation
trong bộ nhớ; chưa có runtime resolver/loader hoặc crop recovery.

### Models và provenance

| Model | Trường và trách nhiệm |
| --- | --- |
| `PathReference` | original_path, category, source_ref và source_location bắt buộc; anchor/crop_view/candidate_page_image tùy chọn nullable |
| `PathRootMapping` | mapping_id, source_root đầy đủ, path_style posix/windows, destination_root_key, category, containment_policy=lexical_then_runtime |
| `PathMappingRequest` | contract_version=path_mapping_v1, reference và mappings bắt buộc |
| `PathTarget` | mapping_id, root_key và relative_suffix; đích logic, chưa phải absolute local path |
| `PathMappingResult` | contract_version, reference, status, candidate_targets, existence_check, containment_check, issues bắt buộc; confirmed_target tùy chọn nullable |
| `PathMappingIssue` | code, path (list key/index), message; không có severity thiếu căn cứ |

Category phân biệt `raw_page_image`, `ocr_page_json`, `ocr_crop`; không đoán category
từ basename/extension. `source_ref` xác định artifact/run do caller cung cấp;
`source_location` là vị trí key/index trong artifact đó, ví dụ `["page","image"]`
hoặc `["elements",0,"crop"]`. Caller giữ binding artifact/run, không coi string này
là bằng chứng danh tính đã xác minh. Manifest cũng dùng context/location riêng,
không bắt mọi reference là crop hoặc có page identity.

`anchor` dùng lại `SourceAnchor` của Document Understanding v1, giữ page identity,
element/table/cell/line context và observed_bbox khi nguồn cung cấp. Không tự suy ra
bbox hay chuyển status của anchor. `crop_view` optional original/ink/black/red/blue
chỉ dùng cho ocr_crop. `candidate_page_image` chỉ giữ reference ảnh trang caller đã
biết, chưa được ánh xạ hoặc xác minh. Không chứng minh liên kết anchor với JSON chỉ
bằng lexical validation; đối chiếu raw anchors vẫn theo contract M1-02b.

`original_path` giữ nguyên Unicode, dấu, khoảng trắng, separators và cả input lỗi.
Không sửa `crop` trong Raw OCR. Chỉ suffix của candidate Windows được biểu diễn
thành components nối `/`; source string gốc không bị normalize. Không tải Drive,
không mở URL và không tự tìm artifact từ source_ref.

### Lifecycle và status semantics

1. Caller lấy path/context từ OCR đã parse hoặc manifest; chọn approved mappings.
2. `parse_path_mapping_request(payload)` kiểm tra cấu trúc, trả model hoặc
   `PathMappingStructuralError` giữ bản sao payload và StructuralIssue code/path/message.
3. `map_path_lexically(request)` chạy validation cấu hình/context và path policy,
   trả result với machine-readable issues. Không sửa request, không I/O.
4. Runtime M1-03b sau này nhận candidate `(root_key, relative_suffix)`, bind
   root_key vào cấu hình đã duyệt của M1-03a, kiểm tra containment thực tế rồi
   existence. Config keys như FINANCIAL_REPORT_DIR/FINANCIAL_OCR_DIR mới là định
   hướng trong [dataset](dataset.md); chưa có config loader hoặc root binding.
5. Output từ runtime cần `parse_path_mapping_result` và
   `validate_path_mapping_result` trước khi downstream tin status. Structural
   parsing không thay thế quality validation. Validator không tự chứng minh lời
   khai runtime, caller phải thực sự kiểm tra theo policy trước khi ghi evidence.

| Status | Ý nghĩa và điều kiện quality |
| --- | --- |
| not_checked | Đúng một candidate, chưa containment/existence, không confirmed_target; helper chỉ sinh trạng thái này khi mapping duy nhất |
| resolved | Một candidate bằng confirmed_target, containment_check=verified và existence_check=exists do runtime khai báo; không xác minh nội dung file hoặc nguồn Drive |
| missing | Một candidate, containment verified và existence missing; không confirmed_target, cần issue missing_target |
| ambiguous | Ít nhất hai candidates từ các mapping IDs khác nhau, không chọn đích, chưa runtime checks |
| unsafe | Vi phạm path/config/context policy hoặc runtime containment; có issue, không confirmed_target |
| unmapped | Không approved root/category phù hợp, không candidates, chưa runtime checks |

`missing` khác `unmapped`: missing đã có candidate hợp lệ và runtime kiểm tra;
unmapped chưa có rule phù hợp. `ambiguous` giữ tất cả logical candidates phục vụ
review, không thử basename hoặc chọn mapping đầu tiên. Helper tuyệt đối không sinh
resolved/missing, vì chưa truy cập filesystem.

### Lexical rules và containment

Source root là toàn bộ root được caller phê duyệt, không phải marker được tìm tự
động. [M1-01 discovery](ocr-data-discovery.md) chỉ quan sát Colab/Drive roots với
marker `Financial_Report`/`Financial_Report_OCR` và full suffix mã/năm/cấu trúc con;
không đủ để khẳng định identity của mọi Drive root/run. Không hardcode shortcut,
Drive ID, prefix Colab cá nhân hoặc pattern filename trong helper.

- Root matching theo anchor và từng component, phân biệt hoa/thường chính xác
  trên mọi host. Financial_Report_OCR_Backup không thuộc Financial_Report_OCR.
- POSIX dùng `/`, Windows dùng `\`; style được khai báo trong mapping. Hỗ trợ
  source POSIX absolute/relative, Windows drive absolute, UNC server/share và
  Windows relative. UNC/drive chỉ hợp lệ khi toàn source khớp approved root;
  không cho chèn chúng vào suffix. Không phụ thuộc hệ điều hành đang chạy tests.
- Từ chối `..` ở bất kỳ component nào, kể cả khi path sau normalize vẫn nằm trong
  root; không xóa `..` để sửa input. Dot segments, repeated/mixed separators,
  suffix rỗng, root-relative Windows và drive-relative Windows bị từ chối.
- Policy portable từ chối control/format/surrogate chars, `%` (không decode), URL,
  home expansion, colon/ADS, ký tự `< > : " | ? *`, Windows device names và segment
  có dấu chấm/khoảng trắng cuối. Khoảng trắng bên trong và Unicode bình thường
  được giữ nguyên; không normalize Unicode/case hoặc trim source strings.
- Chỉ tạo suffix tương đối từ components bên dưới approved root; giữ toàn bộ
  cấu trúc thư mục, không fallback basename, không glob hoặc search filesystem.
- Nhiều rules cùng root/category hoặc roots lồng nhau cùng category đều ambiguous,
  kể cả trỏ cùng đích. Khác category được lọc tường minh. Không tự ưu tiên root dài
  hơn; candidates được sort theo mapping_id để output độc lập iteration order.
- Duplicate mapping IDs, root/key sai và context thiếu làm toàn request unsafe;
  không bỏ rule hỏng rồi chọn rule khác. Root key là logical identifier dạng
  `[A-Za-z][A-Za-z0-9_]*`, không phải absolute path hoặc secret.

Lexical containment chỉ chứng minh suffix theo components của input. Runtime cần
kiểm tra root binding, symlinks/junctions/reparse points, containment thực tế,
quyền truy cập, file type và race conditions theo policy được duyệt. Không coi
lexical validation là bảo vệ đầy đủ trước symlink traversal. Case aliases, Unicode
normalization aliases hoặc filesystem-specific aliases cũng cần runtime policy;
helper fail closed khi root case khác, không tự tìm case-insensitive match.

### Validation, serialization, schema và giới hạn

Models strict/extra forbid, không coercion path/category/index. Structural errors
giữ payload snapshot và field paths; error string chỉ chứa số issues. Empty paths
vẫn parse để giữ nguồn rồi thành quality issue. Output quality validator kiểm tra
suffix/root key, IDs trùng và status/evidence consistency; trả issues mới, không
sửa status hoặc merge vào result.issues. Status cần quality validator đạt trước
khi sử dụng; schema chỉ mô tả cấu trúc, không chứng minh quality hoặc runtime I/O.

Các code chính: empty_path, path_traversal, absolute_path_injection,
unsupported_path_format, invalid_separators, unsafe_segment, unknown_source_root,
ambiguous_root_matching, duplicate_mapping_identifier, mismatched_source_category,
missing_target, empty_relative_suffix, empty_source_context, invalid_source_location,
empty_mapping_id, invalid_root_key, status_conflict. Issue path trỏ input hoặc
output tương ứng. Source path/context luôn còn trong result kể cả unsafe/unmapped.

`export_result()` dùng mode=json/exclude_unset=True, giữ missing/null, Unicode và
source values. Khi dùng model_dump_json để round-trip, truyền exclude_unset=True.
Không cam kết byte-for-byte JSON. Version path_mapping_v1 độc lập hai contracts cũ.
Schema bao gồm request/result dưới anyOf và definitions chung, sinh bằng:

```powershell
python scripts/export_path_mapping_schema.py
```

Artifact `schemas/path_mapping_v1.schema.json` có test sync. Tests synthetic kiểm
tra contracts/security, không kiểm tra file existence, không phải benchmark tài chính.

Theo M1-01 có 2.980 lượt crop references có local suffix tồn tại và 572 lượt thiếu;
không suy ra 572 ảnh duy nhất hoặc khả năng recovery. Missing results giữ source,
candidate, context/anchor/bbox và page image reference nếu caller biết. Không tạo
crop, không suy đoán recovery eligibility, không coi color views tái tạo được chính
xác từ bbox. M1-03d vẫn chỉ là đề xuất, chưa đăng ký task hoặc tạo recovered_crops.

TBD: approved source root/run identities, root-key binding/config policy M1-03a,
runtime containment/file type/access/race policy M1-03b, migration/version compatibility,
filesystem aliases và quy trình/eligibility recovery. Các path formats ngoài policy
bị từ chối rõ ràng, không tự thêm decoder, URL download hoặc Drive API.

## Các giao tiếp nghiệp vụ chưa triển khai

| Điểm bàn giao | Nội dung đã xác định ở mức khái niệm | Chi tiết còn thiếu |
| --- | --- | --- |
| PDF → xử lý tài liệu | Tài liệu gốc và metadata nguồn | Định danh, kiểu file hỗ trợ, manifest: `TBD` |
| Xử lý tài liệu → chuẩn hóa | Document Understanding v1: text/table/cell, anchors và issues | Input kế toán và mapping nghiệp vụ vẫn `TBD` |
| Chuẩn hóa → Canonical Evidence Layer | Structured Financial Facts, Text/Table Evidence, Source Provenance | Kiểu dữ liệu, trường bắt buộc, đơn vị chuẩn, mã chỉ tiêu: `TBD` |
| Canonical Evidence Layer → EF-EG | Bằng chứng và liên kết phục vụ truy nguyên, tính toán | Schema nút/cạnh, định danh và lưu trữ: `TBD` |
| Công cụ → tác nhân/kiểm chứng | Kết quả truy xuất hoặc phép tính kèm bằng chứng nguồn | Chữ ký công cụ, lỗi, serialization: `TBD` |
| Tác nhân → kiểm chứng | Candidate Claims và bằng chứng liên quan | Claim schema, tham chiếu bằng chứng: `TBD` |
| Kiểm chứng → ledger | Nhận định được chấp nhận, bằng chứng và lịch sử kiểm chứng | Schema ledger, versioning và lưu trữ: `TBD` |
| Ledger → đầu ra | Verified Claims và trích dẫn nguồn | Định dạng QA/report và citation contract: `TBD` |

## Các ràng buộc đã xác định

- Dữ liệu tài chính phải giữ source provenance xuyên suốt pipeline; cần truy
  nguyên được đến tài liệu và vị trí nguồn phù hợp (trang, bảng, ô hoặc đoạn).
- Phép tính phải truy được tới công thức và dữ liệu đầu vào để kiểm tra lại.
- Candidate claims chưa được coi là verified claims.
- Output chỉ sử dụng nhận định đã được xác minh trong ledger.
- Không tự bổ sung dữ liệu thiếu, schema hoặc quy tắc kế toán chưa được xác định.

Chương 5.3 nêu các khái niệm `SourceFact`, `TextEvidence`, `DerivedMetric`,
`Claim`, `EvidenceAnchor`, `VerificationRecord`. Đây chưa phải tên class hoặc
database tables được duyệt. Quy tắc null, độ chính xác số, làm tròn, versioning,
trạng thái lỗi và backward compatibility đều là `TBD`.

Contract cụ thể phải được làm rõ và cập nhật cùng tài liệu liên quan trước khi
triển khai module sử dụng; không suy ra schema từ tên biến trong `.env.example`.
