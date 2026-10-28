# Web Demo V1 — API contracts đề xuất

W-01 REVIEW, `web_demo_v1`; chưa có endpoints chạy thật.
[Kiến trúc/lifecycle](architecture.md), [UI mapping](ui-handoff.md).
Tất cả JSON ví dụ dưới đây là **synthetic minh họa contract**, không là dữ liệu
tài chính, output Gemini hoặc kết quả chạy web thật. UUID dùng dạng chuẩn;
hash trong ví dụ là placeholder 64 ký tự, không gán cho PDF pilot.

## Quy tắc chung và endpoints

Prefix `/api`; same-origin local. JSON UTF-8, UTC ISO8601 timestamps,
Decimal hữu hạn là string (cả scale/delta/tolerance), không NaN/Infinity/float.
ID document/job UUIDv4 do server tạo; pdf_page bắt đầu 1, table/row/column
index trong payload bắt đầu 0. Metadata revision và attempt_id bind mọi result.
Frontend không coi symbol legacy là ticker. Response không chứa local paths,
credentials, image base64 hoặc raw provider errors. Lỗi client trả message an toàn.

| Method/path | Input | Response | Điều kiện/lỗi |
| --- | --- | --- | --- |
| POST `/documents` | multipart `file` duy nhất, không ticker/year/pages | 201 Document, job preflight được queue nếu còn slot; Location detail | 413 quá size/pages, 415 không PDF, 422 malformed/encrypted; khi queue đầy vẫn uploaded, job=null |
| GET `/documents?offset=0&limit=20` | offset>=0, limit 1..100 | 200 `{items: DocumentSummary[], offset, limit, total}` | Sort created_at desc rồi ID để ổn định |
| GET `/documents/{id}` | UUID | 200 Document (metadata, job hiện tại, result pointer) | 404 không tồn tại |
| PATCH `/documents/{id}/metadata` | JSON metadata_revision, confirmed, values | 200 Document, revision tăng, ready hoặc needs_metadata | 409 revision stale/job active; 422 field sai |
| POST `/documents/{id}/process` | JSON `{operation: "preflight" hoặc "extract", metadata_revision: int}`; Idempotency-Key UUID | 202 `{document_id, job}` + Location status | extract cần ready/terminal có confirmed metadata; 409 chưa ready/job khác active; 429 queue đầy + Retry-After |
| GET `/documents/{id}/status` | không | 200 `{document_id, metadata_revision, job}` | job=null nếu chưa queue; polling phase/counters |
| GET `/documents/{id}/inventory?attempt_id={uuid}` | attempt_id bắt buộc | 200 `{document_id, attempt_id, metadata_revision, pages: PageSummary[]}` | 409 chưa publish trang; 404 attempt không thuộc document |
| GET `/documents/{id}/evidence?attempt_id={uuid}&statement=B01&offset=0&limit=200` | statement B01/B02/B03 hoặc bỏ để lấy tất cả; limit 1..500 | 200 EvidencePage gồm items, invalid_pages, annotations, pagination | 409 chưa có snapshot; 422 B09 (dùng inventory) |
| GET `/documents/{id}/file` | Range header tùy chọn | 200 application/pdf hoặc 206 byte range; Accept-Ranges: bytes | 416 range không hợp lệ; inline filename được sanitize |

DocumentSummary: id, filename, created_at, state, metadata_revision,
company_name/stock_ticker/reporting_year (confirmed values hoặc null),
latest_result (attempt_id/revision hoặc null). Document thêm content_id,
page_count, metadata, job, limits (max_upload_bytes/max_pages), latest_result.
`content_id` có prefix sha256; document id không đổi khi sửa metadata.
Metadata object giữ `suggestions`, `values`, `confirmed`, `edits` và `preflight`.
Suggestions của AI không bị PATCH ghi đè; edits chứa field/previous/value và
origin=user, không cần suy giá trị user nhập là bằng chứng PDF.

PATCH values là object đầy đủ có company_name, stock_ticker, reporting_year,
reporting_period {value,type} hoặc null, reporting_scope separate/consolidated/null.
company_name string không rỗng và year integer 1..9999 cần cho confirmed=true;
ticker nullable không bắt buộc. confirmed=false cho lưu nháp (tên/năm có thể null),
không xử lý extraction. Từ chối unknown fields; field thiếu dùng 422, không tự
default zero/năm hiện tại. Mỗi PATCH tăng revision, invalidates current result
pointer; kết quả cũ vẫn đọc qua attempt_id nhưng UI gắn “Metadata phiên cũ”.

Idempotency key scope document+operation+revision, lưu trong attempt metadata.
Lặp cùng key/body trả job cũ (202 còn active, 200 đã terminal), khác body trả 409.
Key mới cho retry terminal; không tự retry Gemini từ polling. Khi active có key
khác trả 409. preflight chỉ chạy khi idle; kết quả mới không ghi đè confirmed
values, muốn thay phải PATCH. uploaded/needs_metadata có thể retry preflight;
extract không yêu cầu người dùng chọn trang. Không API cancel ở V1.

## Metadata và nguồn dẫn preflight

Mỗi field suggestion: `{status, candidates, issues}`; status là resolved,
uncertain hoặc unresolved. Candidate gồm `value`, `raw_text` giữ nguyên,
`sources: [{pdf_page, content_id}]`. reporting_period.value/type theo semantics
FinancialContext (as_of, fiscal_year, fiscal_year_end, date_range, quarter,
year_to_month); không dùng năm nhãn document thay cho period từng cell.
Uncertain giữ nhiều candidates; unresolved có candidates=[] nếu không quan sát
được; không confidence %. Preflight là schema mới W-03, không giả là output
PagePrediction hoặc ExtractedPage đã có. preflight object gồm analyzed_pages,
stop_reason (sufficient_evidence/pages_exhausted/budget_limit/provider_error),
issues, schema_revision/prompt_revision. Candidate nguồn phải thuộc PDF hiện tại.

Upload thành công (201, preflight đã queue):

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "filename": "bao-cao.pdf",
  "content_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "page_count": 12,
  "created_at": "2026-10-28T08:00:00Z",
  "state": "queued",
  "metadata_revision": 0,
  "metadata": {"suggestions": {}, "values": {"company_name": null, "stock_ticker": null, "reporting_year": null, "reporting_period": null, "reporting_scope": null}, "confirmed": false, "edits": [], "preflight": null},
  "job": {"id": "22222222-2222-4222-8222-222222222222", "operation": "preflight", "state": "queued", "phase": "preflight", "metadata_revision": 0, "progress": {"discovery": null, "extraction": null}, "page_errors": [], "error": null, "updated_at": "2026-10-28T08:00:00Z", "revision": 1},
  "latest_result": null,
  "limits": {"max_upload_bytes": 52428800, "max_pages": 200}
}
```

Metadata preflight: fragment `metadata` trên Document sau job về needs_metadata;
`values` vẫn null cho đến PATCH xác nhận. Không có ticker thì vẫn tiếp tục được.

```json
{
  "suggestions": {
    "company_name": {"status": "resolved", "candidates": [{"value": "Công ty Minh Họa", "raw_text": "CÔNG TY MINH HỌA", "sources": [{"pdf_page": 3, "content_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]}], "issues": []},
    "stock_ticker": {"status": "unresolved", "candidates": [], "issues": ["not_observed"]},
    "reporting_year": {"status": "resolved", "candidates": [{"value": 2025, "raw_text": "Năm 2025", "sources": [{"pdf_page": 3, "content_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]}], "issues": []},
    "reporting_period": {"status": "resolved", "candidates": [{"value": {"value": "2025", "type": "fiscal_year"}, "raw_text": "Năm 2025", "sources": [{"pdf_page": 3, "content_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]}], "issues": []},
    "reporting_scope": {"status": "unresolved", "candidates": [], "issues": ["not_observed"]}
  },
  "preflight": {"analyzed_pages": [1, 2, 3, 4], "stop_reason": "sufficient_evidence", "issues": [], "schema_revision": "metadata_v1", "prompt_revision": "v1"}
}
```

Metadata không xác định: fragment Document; suggestions áp dụng đầy đủ năm fields
theo cùng cấu trúc (ví dụ rút gọn hai field cần xác nhận). Không tự fallback năm
hiện tại hoặc filename, vẫn có thể PATCH bằng người dùng.

```json
{
  "state": "needs_metadata",
  "metadata": {
    "suggestions": {
      "company_name": {"status": "unresolved", "candidates": [], "issues": ["unreadable"]},
      "reporting_year": {"status": "unresolved", "candidates": [], "issues": ["insufficient_evidence"]}
    },
    "preflight": {"analyzed_pages": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "stop_reason": "pages_exhausted", "issues": ["manual_metadata_needed"], "schema_revision": "metadata_v1", "prompt_revision": "v1"}
  }
}
```

Xác nhận/chỉnh sửa (request PATCH):

```json
{
  "metadata_revision": 0,
  "confirmed": true,
  "values": {"company_name": "Công ty Minh Họa", "stock_ticker": null, "reporting_year": 2025, "reporting_period": {"value": "2025", "type": "fiscal_year"}, "reporting_scope": null}
}
```

## Processing và partial semantics

State dùng lifecycle kiến trúc. Job có id, operation, state, phase,
metadata_revision, progress, page_errors, error, updated_at, revision.
Progress.discovery `{completed_pages,total_pages}` đếm records đã persist kể cả
uncertain; extraction `{completed_pages,selected_pages,valid_pages,invalid_pages}`
đếm sau record/exception persist. Chưa biết count thì null, không dùng 0 giả.
page_errors [{pdf_page,phase,code,retryable}], không bao gồm stack trace.
Không tính phần trăm từ tokens/cells và không suy ETA. Status là job hiện tại,
evidence đọc theo attempt_id cố định; UI không ghép dữ liệu từ hai attempts.

Ví dụ processing progress (GET status):

```json
{
  "document_id": "11111111-1111-4111-8111-111111111111",
  "metadata_revision": 1,
  "job": {"id": "33333333-3333-4333-8333-333333333333", "operation": "extract", "state": "processing", "phase": "discovery", "metadata_revision": 1, "progress": {"discovery": {"completed_pages": 5, "total_pages": 12}, "extraction": null}, "page_errors": [], "error": null, "updated_at": "2026-10-28T08:02:00Z", "revision": 6}
}
```

Sau đây là ba **Job objects** terminal (bọc trong `job` của status như trên).
completed không đồng nghĩa financial_fact_verified hoặc đủ B01/B02/B03 trong
mọi loại báo cáo; chỉ completeness kỹ thuật theo policy architecture.

```json
{
  "id": "33333333-3333-4333-8333-333333333333",
  "operation": "extract", "state": "completed", "phase": "finalizing", "metadata_revision": 1,
  "progress": {"discovery": {"completed_pages": 12, "total_pages": 12}, "extraction": {"completed_pages": 4, "selected_pages": 4, "valid_pages": 4, "invalid_pages": 0}},
  "page_errors": [], "error": null, "updated_at": "2026-10-28T08:05:00Z", "revision": 18
}
```

```json
{
  "id": "33333333-3333-4333-8333-333333333333",
  "operation": "extract", "state": "partial", "phase": "finalizing", "metadata_revision": 1,
  "progress": {"discovery": {"completed_pages": 12, "total_pages": 12}, "extraction": {"completed_pages": 4, "selected_pages": 4, "valid_pages": 3, "invalid_pages": 1}},
  "page_errors": [{"pdf_page": 6, "phase": "extraction", "code": "invalid_extraction_response", "retryable": true}],
  "error": null, "updated_at": "2026-10-28T08:05:00Z", "revision": 18
}
```

```json
{
  "id": "33333333-3333-4333-8333-333333333333",
  "operation": "extract", "state": "failed", "phase": "extraction", "metadata_revision": 1,
  "progress": {"discovery": {"completed_pages": 12, "total_pages": 12}, "extraction": {"completed_pages": 4, "selected_pages": 4, "valid_pages": 0, "invalid_pages": 4}},
  "page_errors": [{"pdf_page": 5, "phase": "extraction", "code": "provider_unavailable", "retryable": true}, {"pdf_page": 6, "phase": "extraction", "code": "provider_unavailable", "retryable": true}, {"pdf_page": 7, "phase": "extraction", "code": "provider_unavailable", "retryable": true}, {"pdf_page": 8, "phase": "extraction", "code": "provider_unavailable", "retryable": true}],
  "error": {"code": "no_usable_evidence", "message": "Chưa trích xuất được số liệu có thể sử dụng.", "retryable": true},
  "updated_at": "2026-10-28T08:05:00Z", "revision": 18
}
```

Failed vẫn giữ inventory nếu discovery đã chạy; khác partial khi có một phần
evidence số usable hoặc inventory-only không có selected statements (notes-only).
Interrupted có phase/counters cuối, error=application_interrupted, không ngụ ý
retry sẽ miễn phí. Terminal job không đổi lại thành processing; retry tạo job mới.

## Inventory, financial evidence và provenance

PageSummary projection từ discovery: pdf_page (=record.page), statement_type,
classification statement/notes/other/uncertain, description, has_financial_table,
has_notes_text, uncertainty, selected, reason, method text_layer/gemini.
Thêm extraction_status not_selected/pending/valid/invalid/error từ attempt.
Không expose response payload trong inventory. Trang B09 chỉ link PDF từ đây.
Ví dụ PageSummary (fragment):

```json
{"pdf_page": 9, "statement_type": "B09", "classification": "notes", "description": "Thuyết minh", "has_financial_table": true, "has_notes_text": true, "uncertainty": null, "selected": false, "reason": "notes_inventory", "method": "gemini", "extraction_status": "not_selected"}
```

EvidencePage: document_id, attempt_id, metadata_revision, snapshot_revision,
items, invalid_pages [{pdf_page,issues}], annotations {arithmetic,relationships},
offset, limit, total. Sắp items theo pdf_page/table/row/column/evidence_id;
pagination không loại raw/unmapped/conflicted. Annotations rỗng khi chưa chạy,
không suy PASS. Partial snapshot đang chạy có thể đọc sau từng trang; đổi
snapshot_revision thì UI tải lại từ offset=0 để tránh trộn pagination snapshots.

Item projection từ AssessableEvidence + EvidenceAssessment:
evidence_id (opaque string trong attempt), source_item_code/canonical_item_id,
raw_label/raw_header, value (FinancialValue giữ nguyên), context
(FinancialContext giữ nguyên), extraction_issues, quality {decision,issues,caveats},
sources (projection FinancialSourceReference), binding {table,row,column} từ
validated AutomatedLink, financial_fact_verified=false. Binding null nếu không
có linkage rõ, không tự suy hierarchy từ label. Source pointer luôn trỏ payload
structured extraction được giữ server-side, không trỏ PDF byte hoặc raw OCR ID.
Giữ nguyên provenance backend trong private snapshot; API projection chỉ bỏ
legacy symbol/year/image internals, thêm content_id/pdf_page kiểm binding.
Sources gồm content_id, pdf_page, source_pointer, provenance_level và bbox=null
khi không có tọa độ trusted. Không fabricating bbox từ table row/column.

Financial evidence kèm nguồn (một item synthetic zero, không phải pilot BBS):

```json
{
  "document_id": "11111111-1111-4111-8111-111111111111",
  "attempt_id": "33333333-3333-4333-8333-333333333333",
  "metadata_revision": 1, "snapshot_revision": 18,
  "items": [{
    "evidence_id": "opaque-observation-1", "source_item_code": "01", "canonical_item_id": null,
    "raw_label": "Chỉ tiêu minh họa", "raw_header": "Năm 2025",
    "value": {"raw_value": "0", "normalized_value": "0", "unit": "VND", "status": "resolved", "issues": []},
    "context": {"period": "2025", "period_type": "fiscal_year", "currency": "VND", "scale": "1", "reporting_scope": null, "statement_type": "B02", "raw_item_label": "Chỉ tiêu minh họa", "mapped_item_code": null},
    "extraction_issues": [],
    "quality": {"decision": "usable_with_caveat", "issues": [{"code": "missing_canonical_mapping", "detail": "Raw item identity retained"}], "caveats": ["missing_canonical_mapping"]},
    "sources": [{"content_id": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "pdf_page": 7, "source_pointer": "/tables/0/cells/2", "provenance_level": "page", "bbox": null}],
    "binding": {"table": 0, "row": 1, "column": 2}, "financial_fact_verified": false
  }],
  "invalid_pages": [], "annotations": {"arithmetic": [], "relationships": []},
  "offset": 0, "limit": 200, "total": 1
}
```

Ví dụ chỉ giữ một source để ngắn; runtime DTO phải trả **mọi** provenance ref
(context, header, label, code, value), không cắt theo ví dụ. Chọn cell chuyển
đúng pdf_page; nhiều nguồn cho phép chọn từng nguồn. Artifact payload ngoài HTTP
chưa có download endpoint V1; operator có thể inspect private snapshot khi cần.

| Tình huống | Representation và UI |
| --- | --- |
| Numeric zero | raw_value="0", normalized_value="0"; không kiểm truthiness |
| Thiếu numeric | raw_value="" hoặc chuỗi nguồn thiếu, normalized_value=null, quality thường insufficient; không thay zero |
| Dash | raw_value giữ đúng glyph (ví dụ "—", "_." nếu backend đã chép thế), normalized_value=null; UI không sửa raw hoặc gán zero |
| Unresolved | value.status=unresolved/uncertain **nếu backend trả thế**, normalized có thể null; xem cả issues/quality; raw fallback hiện có có thể value.status=resolved dù numeric null |
| Conflicted | quality.decision=conflicted; giữ tất cả evidence/candidates, không đổi value.status thành literal mới |
| Usable | quality.decision=usable (đánh giá theo direct_qa), không verified |
| Usable with caveat | quality.decision=usable_with_caveat; hiển thị caveats/unmapped, không ẩn dữ liệu |
| Invalid extraction response | invalid_pages/page_errors có invalid_extraction_response, không tạo financial item hoặc numeric giả từ raw invalid payload |

Dash/missing là cách trình bày dựa trên raw, không thêm parser số thứ hai hoặc
thay enums backend. UI không suy usable chỉ từ value.status=resolved; authoritative
decision là EvidenceAssessment, giữ nguyên numeric khi decision insufficient.
Annotations giữ rule_id/status/reason/inputs/provenance và Decimal strings theo
models ArithmeticCheck/RelationshipCheck, không gọi financial verification.

## Errors và đồng bộ

Error envelope cho HTTP lỗi:

```json
{"error": {"code": "metadata_revision_conflict", "message": "Thông tin tài liệu đã thay đổi. Hãy tải lại.", "retryable": false}, "request_id": "44444444-4444-4444-8444-444444444444"}
```

400 invalid request, 404 unknown ID, 409 state/revision/attempt conflict,
413 limits, 415 type, 422 invalid metadata/PDF, 429 queue capacity,
503 service chưa cấu hình hoặc storage unavailable. Không leak exception input.
Quota/provider failures sau queue là job errors qua status, không đổi mọi HTTP
poll thành 500. Nếu retry_at có từ guard, trả timestamp đó; nếu không có, null.
Known usage/cost chỉ ở private artifacts; unknown không thành 0 hoặc percentage.
Không lấy quality aggregate thay session state, không bỏ trang tốt khi một trang lỗi.
