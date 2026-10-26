# Data contracts

M1-02a triển khai Raw OCR Contract `raw_ocr_v1` trong `document_processing`.
Các giao tiếp nghiệp vụ khác vẫn ở mức khái niệm theo báo cáo giữa kỳ, Chương 4–5;
không suy ra schema kế toán, Document Understanding hay Canonical Evidence từ OCR.

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

Document Understanding Contract (M1-02b) sẽ biểu diễn kết quả hiểu tài liệu có
liên kết raw riêng. Canonical Financial Evidence thuộc lớp evidence sau chuẩn hóa
kế toán; cả hai chưa triển khai ở M1-02a. Path Mapping Contract (M1-02c), nguồn
Drive/run, missing crops, ownership nâng cao và ground truth vẫn ngoài phạm vi.

## Các giao tiếp nghiệp vụ chưa triển khai

| Điểm bàn giao | Nội dung đã xác định ở mức khái niệm | Chi tiết còn thiếu |
| --- | --- | --- |
| PDF → xử lý tài liệu | Tài liệu gốc và metadata nguồn | Định danh, kiểu file hỗ trợ, manifest: `TBD` |
| Xử lý tài liệu → chuẩn hóa | Văn bản, bảng, vị trí nguồn và trạng thái chất lượng | Schema trích xuất, tọa độ và mã chất lượng: `TBD` |
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
