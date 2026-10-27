# Extraction Structure Validators — M1-04a

Runtime composition thuộc `document_processing`; giữ nguyên `raw_ocr_v1`,
`document_understanding_v1`, `path_mapping_v1` và ba schema artifacts.
Không tạo Canonical Evidence/accounting schema, không OCR/LLM/API hoặc recovery execution.

## APIs và luồng dữ liệu

Import từ `vietnamese_financial_multi_agent.document_processing.extraction_validation`:

- `validate_extraction_payload(payload, *, source_context, understanding=None,
  raw_binding_verified=False)`: pure in-memory. Parse toàn trang Raw OCR, quality
  riêng; parse/quality Understanding độc lập dù Raw OCR structural invalid.
  `raw_page` chỉ truyền vào validator Understanding khi caller xác nhận binding.
- `validate_extraction(request, config, mappings, *, expected_identity=None,
  image_bindings=None, run_identity=None, recovery_entries=None, bbox_ledger=None,
  ledger_plan_id=None, understanding=None, raw_binding_verified=False,
  expected_image_hash=None)`: một trang, read-only I/O. `request` là
  `PathMappingRequest` đã validate; `config` là `DataConfig`; `mappings` là list
  approved `PathRootMapping`. Identity là tuple `(symbol, year, page)`;
  image bindings là dict từ exact original image reference sang tuple này.
- `ExtractionReport.export()`: dict có thể JSON serialize. Các dataclasses frozen
  `ExtractionReport`, `ExtractionIssue`, `CropAvailability` chỉ là runtime models.

Luồng: loader → Raw/Understanding validators → resolver/read_image → fresh
crop audit → selected output verification → structured report. Không ghi file trong
các APIs. Caller có thể lưu reports ở `artifacts/extraction-validation/` bị ignore,
ngoài mọi source datasets. Không log payload hoặc exception details của filesystem.

Ví dụ caller đã có inputs được phê duyệt:

```python
from vietnamese_financial_multi_agent.document_processing.extraction_validation import (
    validate_extraction,
)

report = validate_extraction(
    request,
    config,
    mappings,
    expected_identity=expected_identity,
    image_bindings=approved_image_bindings,
    recovery_entries=local_index,
    bbox_ledger=local_ledger,
    ledger_plan_id=approved_plan_id,
)
```

`raw_binding_verified=True` là attestation của caller rằng Understanding source_ref/run
thực sự trỏ đúng Raw OCR này, không suy từ tuple metadata hay từ các image bindings.
Thiếu attestation vẫn chạy standalone Understanding quality và báo
`raw_binding_not_verified`. Không tự cấp identity toàn cục từ symbol/year/page/image.

## Phân loại và provenance của issues

`category`: structural (không parse được theo contract), quality (parse được),
artifact (runtime/references/nguồn). Structural failure không trả trang hợp lệ một phần;
image/crop availability và ledger có statuses riêng, không dùng một boolean “valid all”.

`origin` phân biệt validator đã có (`raw_ocr_v1`, `document_understanding_v1`,
`path_mapping_v1`), issue do caller lưu trong Understanding (`understanding_reported`),
`human_review`, và checks runtime (`page_image`, `recovery_index`, `crop_audit`,
`source_binding`, `original_crop`, `ocr_loader`). Root và nested Understanding issues
được giữ, không echo free-form messages. Code được giữ khi đúng dạng machine code;
giá trị không an toàn chuyển `unrecognized_issue_code`, giữ opaque record token.

Report giữ source/artifact SHA-256 tokens và source field paths; không chứa raw OCR
text, original paths, local absolute paths hoặc raw element IDs. Index của element/
cell/line trong path xác định đối tượng nguồn. Unknown field names có thể nhạy cảm
được thay `[field]`, giữ path token để không gộp hai vị trí khác nhau. Tokens/IDs vẫn
chỉ dành local, không công bố per-file tokens/hashes trong public evidence.

Issue mặc định `requires_review`; thiếu bằng chứng dùng `not_verified`.
Dedup theo toàn record (category/origin/source/path/artifact/status), thứ tự deterministic;
không xóa issue khác nguồn chỉ vì cùng code. Không sửa bbox/text/row/col/IDs/provenance.

## JSON–ảnh và source binding

Dùng `read_image`/bounded `_read_bytes`/resolver đã được nghiệm thu: PNG, tối đa
64 MiB và 40 triệu pixels, mode RGB/RGBA/L/LA/1/P. Missing/unsafe/unmapped/ambiguous,
corrupt/unsupported image giữ lỗi riêng; PNG extension không chứng minh content.
So width/height OCR với ảnh thực và bounds của element/cell/line/seal/signature bboxes.
Invalid bbox geometry vẫn là quality của Raw OCR, không đổi thành structural error.
Không scale/clip/correct hoặc dùng image similarity chứng minh JSON–ảnh cùng nội dung.

`image_status=checked` chỉ xác nhận kiểm tra ảnh/dimensions đã chạy thành công;
bbox issues vẫn xuất riêng. `source_binding_status=caller_bound` chỉ là binding do
caller khai báo và metadata khớp, không xác thực nội dung/run trên Drive.
Thiếu run identity dùng `caller_bound_run_unverified`; thiếu binding/expected identity
dùng `not_verified`. Nếu caller có hash ảnh độc lập, `expected_image_hash` phát hiện
nguồn khác snapshot. Loader metadata revalidation, fresh audit/JSON comparison và
final image reread phát hiện source change trong phạm vi lần gọi.

## Crop availability và recovery trust boundary

- `existing_original`: exact reference resolve an toàn và bounded PNG decode thành công.
- `reconstructed_available`: original missing; alternative qua mọi checks bên dưới.
- `missing_unrecovered`: không có original usable hoặc alternative đã verify.
  `mapping_status` và issues vẫn giữ lý do missing/unmapped/unsafe/ambiguous/corrupt;
  tên tổng hợp này không chứng nhận original thật sự missing khi resolver chưa xác minh.

Không fallback reconstruction khi confirmed original target hỏng/unsafe; không tìm
file khác hoặc basename. Original references không bị thay. `original_equivalence`
luôn `unverified`, kể cả exact pixels khớp source bbox.

`extraction_artifacts.RecoveryEntry` là strict projection runtime của index M1-03f,
không phải versioned Path Mapping Contract. Parse tất cả entry trong bộ nhớ, reject
malformed/unknown fields, duplicate recovery ID hoặc ambiguous source+original-reference.
Index lỗi làm alternatives fail closed; original checks và human issue reporting vẫn chạy.

Đối với từng crop của trang được yêu cầu: fresh `audit_page` tạo canonical record;
`recovery_id(record)` phải khớp ID trong index, bao gồm run/source/element index/field/
original path/mapping/hash context. Đối chiếu exact page/element/field/bbox/source image,
source hash và audit issues; duplicate element IDs làm binding ambiguous. Cần caller
identity/image binding; thiếu chúng không xác nhận alternative.

Chỉ approved `data/recovered_crops/`, tên đúng `<recovery_id>.png`/`.json`; dùng
`validate_output_root` và `_read_output` hiện hữu, reject link/reparse/unsafe parents.
So sidecar đủ năm fields với index/source, output SHA-256, dimensions/mode và source
bbox pixels qua `_validate_png`. Header PNG được giới hạn trước decode vì index là
untrusted input. Không gọi recover_crop/inspect_outputs, không re-encode PNG, không
scan/re-hash 199 outputs mỗi lần gọi; chỉ các alternatives trên trang được yêu cầu.
Không cache kết quả qua nhiều snapshots. Final image change thu hồi availability đã verify.

## Human-reviewed bbox ledger và evidence input

`read_local_evidence(path, config, jsonl=False)` đọc file caller chỉ định trong
`project_root/artifacts/`, bounded 8 MiB, reject links/unsafe parents, paths ngoài root,
overlap source datasets, duplicate JSON keys/nonfinite constants. Không tự discover files,
không đọc `.env` hoặc tự tải nguồn khác. Mất file/unsafe read ném lỗi có code an toàn;
caller báo input failure và có thể truyền `bbox_ledger=None` để chạy phần độc lập.

Ledger đối chiếu `ledger_plan_id` độc lập caller cung cấp, count, sheet uniqueness,
recovery IDs, PNG hashes, page/element/bbox với index, attribution/evidence fields,
status requires_review/follow-up M1-04a và cờ bbox_modified/complete_table đều false.
`ledger_status=consistent` chỉ xác nhận recorded linkage với index; việc kiểm tra
artifact bytes vẫn riêng theo từng trang. Không xác thực reviewer bằng chữ ký số.
Thiếu ledger: `not_verified` và `bbox_ledger_not_verified`, không dựng ledger giả.
Ledger lỗi: báo `bbox_ledger_inconsistent`, vẫn chuyển tiếp các nhãn bbox đã ghi dưới
ledger context/status `not_verified`, không bịa page binding hoặc tự đóng issue.

M1-03f thực tế có 5 issues sheets 02/03/08/11/12. API cho phép ledger synthetic nhỏ
để tests; smoke thật kiểm tra đúng năm issues từ ledger thật, không public hóa danh tính.
Pixel-exact crop không chứng minh bảng đầy đủ. Không có thuật toán tự phát hiện completeness.

## Giới hạn và kiểm thử

Trusted local filesystem như loader/recovery hiện có: checks/open không atomic,
Windows thiếu O_NOFOLLOW, TOCTOU qua parent/root, hardlinks/mount/case/Unicode aliases
và writers bên ngoài vẫn chưa chống đầy đủ. Caller phải kiểm soát roots và snapshot;
report không phải security sandbox hoặc proof nguyên bản OCR/Drive run.

Synthetic tests kiểm tra structural/quality, JSON–ảnh, no mutation/determinism,
missing/ambiguous/unsafe references, index/source binding, sidecar/hash/pixel integrity,
bounded recovered decode và human issue preservation/failure isolation. Symlink tests
skip rõ lý do khi Windows không đủ quyền; CI Linux kiểm tra ở nền tảng có hỗ trợ.
Bounded real smoke và sanitized evidence tại [M1-04a evidence](reviews/M1-04a-evidence.md).
Không ngoại suy OCR accuracy, precision/recall, completeness accuracy, dataset quality
hoặc financial correctness. M1-04b chưa triển khai.
