# Canonical Financial Facts — M3-02

Public API: `vietnamese_financial_multi_agent.evidence`.
Luồng hiện tại: PDF → M1 discovery/structured extraction → M2 normalization,
approved mapping và task quality → Web Demo `attempts/<attempt_id>/result.json`
(`quality.items[].evidence` giữ đầy đủ M2) → explicit M3 adapter → repository.
`items` của HTTP/viewer là projection rút gọn, không dùng để tái dựng source anchors.
Không replay `records`, không chạy lại parser/resolver/extraction hoặc quality gate.

## Adapter và tích hợp tường minh

`fact_from_m2(evidence: AssessableEvidence, *, document_id, snapshot_id,
company_id=None, quality_context=())` trả `CanonicalFinancialFact` M3-01.
Giữ evidence_id M2 làm local_observation_id trong document/attempt; caller cung cấp
document/snapshot thật. Không lấy company từ symbol hoặc kỳ từ filename/page.year.
Canonical item chỉ copy mapping có sẵn, không map bằng raw label/code mới.
Giữ FinancialValue/status/issues, FinancialContext, raw code, source references,
provenance level, extraction issues và quality annotations đã được caller cung cấp.
Không có annotations thì giữ list rỗng, không tạo decision mới.

`facts_from_persisted_result(result, *, company_id=None)` đọc JSON snapshot W-04
và validate `QualityAssessment` qua JSON để giữ Decimal strings. Copy item decision,
issues/caveats cùng task_type; **không** thay item decision bằng aggregate task decision.
Aggregate quality/checks vẫn ở result M2 gốc; không thực hiện propagation M3-06.
Không có quality projection nhưng có records/items thì báo ValueError để caller
chuyển đổi tường minh, tránh bỏ dữ liệu hoặc fabricate quality.
Chỉ materialize snapshot đã kết thúc; snapshot đang cập nhật có thể tạo conflict
quality/payload cho cùng identity, cần caller xử lý tường minh.

Ví dụ trong composition/backend code (không endpoint hoặc tự chạy pipeline):

```python
from vietnamese_financial_multi_agent.api.extraction_sessions import read_result
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFactRepository,
    facts_from_persisted_result,
)

result = read_result(store, document_id, attempt_id)
repo = CanonicalFactRepository(store.root / "canonical", lock=store.lock)
for fact in facts_from_persisted_result(result):
    outcome = repo.put(fact)
```

Contract M3-01 chỉ bổ sung backward-compatible `raw_header=None` và
`source_metadata={}` để không mất header/request/render metadata M2; không đổi
semantics của identity, mapping, quality hoặc M1/M2. Source metadata chỉ là payload
gốc, không phải chứng nhận nguồn. Không có representation financial fact song song.

## Storage và identity policy

`CanonicalFactRepository(root, *, lock=None)` dùng `canonical-facts.json` trong
storage root được caller cấu hình, không dùng identifiers làm đường dẫn.
Reuse atomic JSON/fsync/replace của Web Demo qua `core.persistence.atomic_json`;
giữ import cũ tại `api.document_store` cho consumers hiện tại. Helper nằm ở core
để evidence không phụ thuộc ngược HTTP/API. Không engine, cache hoặc index file mới.
Một writer/instance mỗi root; các instances trong cùng process cần share lock;
không hỗ trợ concurrent multi-process writers. Không tự chọn data/raw/processed.
Chọn root trong storage ignored, ví dụ `artifacts/web-demo-v1/canonical`.

| API | Kết quả |
| --- | --- |
| `put(fact)` | `stored`, `idempotent`, hoặc `quarantined` |
| `get(ObservationIdentity)` | Fact hoặc None |
| `list_by_document(document_id, snapshot_id=None)` | Observations indexed của document, tùy chọn snapshot |
| `query_by_semantic_key(SemanticFactKey)` | Tất cả observations có cùng semantic metadata, không merge |
| `list_quarantine()` | Payloads thiếu identity, ngoài indexed retrieval |

Observation identity là tuple document/snapshot/local ID. Same identity + cùng
JSON payload là idempotent; khác payload ném `ObservationConflict` có `existing`
và `incoming`, không overwrite. Caller giữ/xử lý incoming, không swallow exception.
Decimal khác trailing zeros cũng là payload khác; không qua float.
Different documents/attempts cùng semantic key giữ riêng tất cả sources/values,
kể cả conflicting values; M3-02 không kết luận restatement/conflict liên nguồn.

Missing/blank identifier → None + reason ở adapter; `put` lưu nguyên fact trong
quarantine, không tạo random/global ID. Payload quarantine giống hoàn toàn là
idempotent, payload khác vẫn giữ riêng. Quarantine không chứng minh hai occurrence
giống payload là cùng observation. Caller cần nguồn thật để bind lại rồi put
record đủ identity; bản quarantine cũ giữ để không mất evidence.
Không có quality gate loại unmapped/conflicted/missing value observations.

Snapshot giữ Decimal strings, provenance page/element/cell và nullable context;
read lại từ đĩa cho mỗi query/put nên restart không phụ thuộc memory index.
File sai version/schema/duplicate identity bị từ chối tường minh, không tự sửa
hoặc bỏ dữ liệu. Truy vấn scan toàn file, đủ local prototype; chưa tối ưu dataset lớn.
`financial_fact_verified=false` luôn giữ, metadata consistency không là financial
verification. Các quyết định company/context reconciliation vẫn cần evidence thật.

## Validation và giới hạn

Focused synthetic invariants tại `tests/unit/test_canonical_facts.py` kiểm tra
adapter, raw/unmapped/missing context, bốn item decisions, Decimal, cross-document,
re-extraction, duplicate/conflict, quarantine và restart. Kết quả thực chạy và SHA
tại [task evidence](../planning/tasks/M3/M3-02.md).
Smoke dữ liệu persisted chỉ chứng minh chuyển đổi/lưu/đọc lại; không phải PDF accuracy.
Không graph/text-table evidence/metrics/quality propagation hoặc Gemini calls.
