# Text and Table Evidence — M3-03

Public API qua `vietnamese_financial_multi_agent.evidence`:

| Contract/API | Ý nghĩa |
| --- | --- |
| `TextEvidence` | raw_text nullable, structural_role nullable, identity, sources, metadata và resolution_issues |
| `TableEvidence` | structure nullable dùng nguyên UnderstoodTable/UnifiedTable/ExtractionTable, original_table_id nullable, sources/member_sources, structural_issues |
| `EvidenceIdentity` | document_id + snapshot_id + kind + local_id; không phải page/table index toàn cục |
| `evidence_from_understanding(result, *, document_id, snapshot_id)` | DU v1: giữ raw Vietnamese text, reading order/issues trong metadata, anchors và cell structures |
| `evidence_from_unified_page(page, *, document_id, snapshot_id)` | M1-16: giữ source_component, candidate structure và issues; text chỉ lấy từ source_component.text |
| `evidence_from_persisted_result(result)` | W-04 records: context text và bảng từ response.output.payload; không replay M1/M2 |
| `associate_fact(fact, evidence)` | FactEvidenceAssociation có matching_sources hoặc None; không mutate fact/evidence |
| `DocumentEvidenceRepository(root, *, lock=None)` | JSON atomic snapshot riêng document-evidence.json; không đổi canonical-facts.json |

## Identity, nguồn và uncertainty

Caller chịu trách nhiệm binding document/snapshot thật, giống M3-02. Local IDs
DU/unified scope bởi page + loại + source ID/pointer; W-04 scope bởi record index,
page và pointer của payload. Đây là locator xác định trong snapshot đã kết thúc,
không phải raw OCR ID mới. Không dùng content hash/random ID để che thiếu identity.
Thứ tự records phải giữ nguyên trong snapshot; không sửa snapshot đã materialize.
Blank binding/source local ID → None + resolution issue, lưu quarantine.

`EvidenceAnchor`/`FinancialSourceReference`/`SourceAnchor`/`RawPageIdentity` giữ
nguồn. Provenance nằm trên từng reference, không có global level giả cho cả bảng.
`sources` trỏ bảng/đoạn; `member_sources` trỏ cells/headers có sẵn. Selector tới cell
trong JSON vẫn có provenance page khi M1/M2 chỉ cung cấp cấp trang. Không tạo
bbox/token positions/cell IDs từ row/column; unified bbox candidate ở metadata,
không chuyển thành observed_bbox. DU raw IDs/anchors có sẵn giữ nguyên cấp nguồn.

Raw text giữ nguyên Unicode, dấu câu, whitespace/thứ tự. Không đọc response.raw_text
vì đó là JSON envelope của LLM. Không dựng quote từ page pointer hoặc financial
label; thiếu exact raw text giữ None + missing_exact_text. Unified candidate text
còn trong metadata; không thay thế raw_text bằng paraphrase. Structural role chỉ
copy role biết từ contract nguồn (context), còn lại nullable. Tables không tự thêm
cells/headers, không ép thành fact hoặc verified value. Source status, limitations,
partial structures và unknown/unmapped observations vẫn được giữ.

Association cần đủ fact/evidence identities, cùng document/snapshot, tất cả source
bindings không mâu thuẫn, request_id khớp nếu có ở một trong hai phía và exact
source key có selector/anchor ID. Không liên kết từ page-only co-location; không
fuzzy matching hoặc đoán row/header thuộc fact. Table member selector chỉ chứng minh
association với payload; không nâng cell grounding hoặc xác nhận cả bảng đúng.
Matching context text có thể là association ngữ cảnh, không phải chứng minh claim.
Không persist graph edges hoặc thay financial_fact_verified=false của M3-02.

## Persistence và cách dùng

`put(evidence)` trả stored/idempotent/quarantined. Cùng identity khác JSON payload
ném EvidenceConflict với existing/incoming; không overwrite. `get(EvidenceIdentity)`,
`list_by_document(document_id, snapshot_id=None)` và `list_quarantine()` đọc lại đĩa,
giữ đầy đủ anchors/structure sau restart. Kind phân biệt text/table local ID trùng.
Quarantine giữ unresolved payload; payload giống hoàn toàn không thêm bản sao,
không chứng minh hai occurrences thiếu identity là cùng nguồn. Invalid version/schema,
duplicate identity trong file bị từ chối. Reuse core.persistence.atomic_json.
Storage root do caller cấu hình trong vị trí ignored; không chọn raw/processed.
Local single-writer; share lock giữa instances cùng process, không multi-process.

```python
from pathlib import Path

from vietnamese_financial_multi_agent.evidence import (
    DocumentEvidenceRepository,
    evidence_from_persisted_result,
)

# result là snapshot W-04 đã đọc bởi composition layer, không chạy extraction.
repo = DocumentEvidenceRepository(Path("artifacts/evidence/M3-03"))
for evidence in evidence_from_persisted_result(result):
    repo.put(evidence)
```

## Coverage thực có và giới hạn

Preflight đọc cấu trúc snapshot BBS_2025 persisted W-07: 4 records trang 5–8,
178 quality observations. Có context và headers/cells của structured financial
extraction trong records, không có complete OCR/unified document. Adapter không
tạo text từ quality projection hoặc items viewer. Không có records thì trả [];
record thiếu source payload ném ValueError, không fabricate hoặc silently skip.
Hai file PDF BBS_2024/2025 trong raw không chứng minh persisted extraction của cả hai.
Không đọc/xử lý BBS_2024; coverage text/table của BBS_2024 chưa xác minh.

Checkpoint ban đầu chỉ kiểm tra DU/unified synthetic và W-07 smoke. Validation bổ sung
đã inventory raw OCR/M1-15 và kiểm tra toàn bộ hai M1-16 exports cùng hai W-07 attempts:
99/99 records chuyển đổi/round-trip nguyên vẹn, 7 missing document binding giữ quarantine.
Đã đối chiếu trực tiếp PDF cho mẫu B01/B02/B03 và B09 có source thật, phát hiện
ambiguous columns/glyph/segmentation failures; không đồng nghĩa full-PDF accuracy.
Phạm vi, mẫu số riêng từng metric và limitations tại
[real-artifact validation](m3-03-real-evidence-validation.md),
SHA/checkpoint tại [spec](../planning/tasks/M3/M3-03.md).
Không OCR/Gemini/page discovery/reconstruction/normalization/quality reassessment.
Graph, metrics, lineage và unified retrieval thuộc M3-04–07, chưa triển khai.
