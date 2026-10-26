# Read-Only OCR Data Loader — M1-03c

```python
from vietnamese_financial_multi_agent.document_processing import load_ocr_page, OCRLoadError

loaded = load_ocr_page(request, config, max_bytes=32 * 1024 * 1024)
page = loaded.page
issues = loaded.quality_issues
mapping = loaded.mapping_result
```

`request: PathMappingRequest`, `config: DataConfig`; chỉ nhận category
`ocr_page_json`. Không nhận arbitrary Path hoặc PathMappingResult cũ. Không batch,
JSONL/log, fallback basename, tìm JSON từ tên PNG, OCR/crop recovery hay API call.
Adapter nằm trong document_processing, core không import loader/contracts.

## Kết quả và lỗi

`LoadedOCRPage` là frozen dataclass runtime nội bộ, không thêm serialized contract
hoặc version. Các Pydantic objects chứa bên trong vẫn mutable theo contract cũ;
caller cần giữ nguyên nếu muốn export nguồn. Fields:

| Field | Ý nghĩa |
| --- | --- |
| page | OCRPage từ parse_raw_ocr, giữ extra fields và missing/null |
| mapping_result | PathMappingResult với original path/source_ref/location/anchor, mapping ID/root key/full suffix |
| quality_issues | Tuple QualityIssue từ validate_quality, không làm mất trang |
| identity_checked | Có anchor và đã đối chiếu symbol/year/page/image với metadata OCR |

`OCRLoadError` giữ `code`, bản sao `reference`, `mapping_result` nếu đã resolution,
`issues` (tuple StructuralIssue). Structural failure giữ issue paths, đồng thời
giữ RawOCRStructuralError/payload qua `__cause__`; không tạo OCRPage một phần.
Thông báo mặc định chỉ có code, không chứa OCR/local paths. Không log exception
payload hoặc OS exception strings. Lỗi lập trình như TypeError/ZeroDivisionError
không bị đổi thành read errors.

| Codes | Nhóm và hành vi |
| --- | --- |
| invalid_max_bytes, unsupported_category | Input sai, dừng trước filesystem resolution |
| path_failure | Resolver chưa resolved hoặc không có confirmed_target; xem mapping_result.status/issues cho missing/unsafe/unmapped/ambiguous |
| source_changed | Revalidation thất bại, logical target thay đổi hoặc metadata file thay đổi; chưa parse |
| unsafe_file | Link/reparse/non-regular tại read-time hoặc O_NOFOLLOW phát hiện link |
| missing_file, permission_denied, io_error | Lỗi thực tế tại open/read/stat; không parse |
| oversized_file, empty_file | Quá giới hạn hoặc rỗng/BOM-only/whitespace-only |
| invalid_utf8 | UTF-8 decode thất bại |
| invalid_json, duplicate_json_key | Syntax/constant/depth/integer-limit error hoặc duplicate keys ở bất kỳ object nào |
| unsupported_json_root | JSON hợp lệ nhưng root không phải object |
| structural_failure | Raw OCR thiếu field/sai type/unknown element; issues trỏ JSON source |
| identity_mismatch | Anchor metadata khác OCR page; issues liệt kê fields, không sửa metadata |

Resolver có thể phát hiện permission/missing trước loader: khi đó code ngoài là
path_failure, chi tiết nằm ở mapping_result. Khi revalidation phát hiện file mất
hoặc link thay vào, code ngoài source_changed với fresh mapping evidence.

## Safe read và giới hạn tài nguyên

1. Resolve mới bằng resolver đã nghiệm thu; yêu cầu resolved/confirmed_target.
2. Bind lại root key bằng cùng DataConfig, nối approved POSIX suffix theo components.
3. Resolve lại ngay trước open, so logical target; reuse toàn bộ root ancestors,
   symlink/reparse, regular-file, extension, access và runtime containment policy.
4. lstat target, từ chối link/reparse/non-regular và size vượt ngưỡng.
5. os.open chỉ O_RDONLY (+O_BINARY trên Windows). Dùng O_NOFOLLOW và O_NONBLOCK
   khi platform có; O_NONBLOCK tránh treo nếu target bị thay bằng FIFO trước open.
6. fstat phải regular/non-reparse; so dev/inode/size/mtime với lstat. POSIX thêm
   ctime; Windows không so ctime giữa lstat/fstat do semantics có thể khác nhau.
7. Đọc unbuffered từng chunk tối đa 64 KiB, tổng tối đa max_bytes + 1 sentinel,
   không dựa riêng vào stat size. Vượt limit dừng, không parse. File tăng/giảm size,
   đổi identity hoặc mtime khi đọc bị từ chối nếu metadata phát hiện được.
8. fstat sau read, resolve lại và lstat đối chiếu trước trả bytes; luôn đóng handle.

Default 32 MiB là giới hạn RAM hữu hạn ban đầu, **chưa đo là phù hợp toàn corpus**.
`max_bytes` phải int dương, không bool, nhỏ hơn sys.maxsize để sentinel an toàn.
Bytes/chunks/decoded string/JSON/models cùng tồn tại nên RAM thực tế lớn hơn giới
hạn file; không streaming JSON parser, không bảo đảm CPU/RAM budget chống mọi
payload đối kháng. Parser depth/JSON integer-limit errors trả invalid_json.

UTF-8 strict, cho phép một BOM đầu file qua utf-8-sig; không fallback encoding.
Reject duplicate keys (kể cả nested), NaN/Infinity constants; không sửa JSON syntax,
coerce year/page/row/col/bbox, thay null/missing, làm tròn hay bỏ malformed elements.

## Provenance và quality

parse_raw_ocr/validate_quality được gọi trực tiếp, contracts đã duyệt giữ nguyên.
Không thêm local paths vào OCRPage hoặc thay source strings Colab/Drive. IDs,
bbox/crops, page/provenance và các giá trị OCR giữ nguyên. Quality warnings như
bbox geometry, duplicate cell position, sparse table, empty text, confidence và
broken references giữ cùng trang structural hợp lệ; không phải financial errors
hoặc OCR accuracy scores.

Khi có anchor, đối chiếu exact symbol/year/page/image ngay cả status anchor chưa
resolved. Không suy ra OCR run từ các fields này. `source_ref` trên reference/anchor
là caller declaration, filesystem không chứng minh run/artifact identity. Không
có anchor thì identity_checked=False; không suy đoán từ filename hoặc scan dataset.

## Security limitations

Checks và open không atomic: **TOCTOU chưa được loại bỏ**. Windows không có
O_NOFOLLOW; parent/root có thể đổi giữa checks/open. Post-read checks phát hiện
nhiều thay đổi nhưng không bảo đảm ngăn mọi đọc ngoài root khi filesystem bị sửa
đối kháng rồi phục hồi trước kiểm tra. Metadata không phải content signature;
same-size writes với metadata phục hồi, hardlinks/aliases/mounts, một số network
filesystems/inode semantics có thể không phát hiện. Caller phải dùng approved,
trusted local roots/mappings; đây không phải secure descriptor framework.
Cloud placeholders/reparse points vẫn bị chặn theo resolver policy.

## Verification có giới hạn

Synthetic unit tests kiểm tra bảy element types, Unicode/nested provenance,
path/read/decode/structural/identity/quality failures, bounds khi file tăng,
shrink/rewrite/replace, read errors, metadata link/reparse và native junction swap.
Windows thiếu quyền symlink được skip có lý do; Linux CI kiểm tra phần có hỗ trợ.

Đã đọc đúng **3** mẫu từ pilot_candidates.json có sẵn (không scan). Mỗi mẫu parse
thành công; symbol/year/page khớp manifest; SHA-256 nội dung và size/mtime/inode
trước/sau khớp. Không có anchor image đầy đủ trong manifest nên loader không tự
xác minh identity qua anchor, không xác minh run. Script/kết quả chi tiết chỉ local
trong artifacts/ocr-loader/ bị Git ignore; không commit OCR fixtures thật.

| Mẫu | Bytes | Elements | Quality issues quan sát được |
| --- | ---: | ---: | --- |
| BCC/2022/9 | 68.682 | 20 | duplicate_cell_position 17, invalid_bbox_geometry 2, sparse_table 1 |
| BBS/2023/6 | 61.947 | 20 | sparse_table 1, unresolved_signature_reference 1 |
| BCC/2023/1 | 24.313 | 62 | unresolved_signature_reference 8 |

Các số chỉ mô tả ba mẫu, không ngoại suy toàn dataset hoặc đánh giá tài chính.
M1-04 sau nghiệm thu có thể dùng page/mapping_result/quality_issues làm đầu vào;
chưa kiểm tra JSON–image alignment, reconstruction, correction hoặc kế toán.
