# Typed EF-EG v1 — M3-04

Public API qua `vietnamese_financial_multi_agent.evidence`; implementation ở
`src/evidence/graph.py`. Graph chứa references, không copy financial values, raw text
hoặc table structure. Caller giữ canonical/document repositories để resolve records.

| Contract/API | Ý nghĩa |
| --- | --- |
| `SourceFactNode.reference` | ObservationIdentity của CanonicalFinancialFact, không gộp semantic keys |
| `TextEvidenceNode.reference`, `TableEvidenceNode.reference` | EvidenceIdentity M3-03, kind phải khớp |
| `EvidenceAnchorNode.anchor` | EvidenceAnchor M3-01 nguyên metadata; ID namespace/hash của source_key có thật |
| `GraphEdge` | edge_id + relation + source/target node IDs |
| `EvidenceGraph` | Typed union nodes, edges, input_issues với occurrence locators |
| `build_graph(facts, evidence=())` | Builder deterministic, chỉ exact source candidates; không mutate inputs |
| `validate_graph(graph, facts, evidence=())` | Resolve và kiểm tra tất cả nodes/edges, trả GraphValidation |
| `GraphAssessment.status/reasons` | Chỉ structural validity và reasons: valid/invalid/unresolved |
| `GraphAssessment.grounding` / `SourceGrounding` | Observed levels, source statuses và missing/unsupported/uncertain reasons riêng |
| `GraphValidation.evidence_context` / `EvidenceQualityContext` | Map theo record node_id, giữ nguyên TaskQualityContext M2, resolution_issues và table structural_issues |
| `GraphValidation` | Assessments, context và orphan IDs, financial_fact_verified=false |

```python
graph = build_graph(facts, document_evidence)
assessment = validate_graph(graph, facts, document_evidence)
# Có thể lưu graph.model_dump(mode="json") bằng core.persistence.atomic_json.
# Khi đọc dùng EvidenceGraph.model_validate_json(...), rồi validate lại với records.
```

## Relationships và identity

`from_source`: SourceFact/TextEvidence/TableEvidence → EvidenceAnchor. Bao gồm
table member_sources thực có; cùng anchor identity được dùng chung. Validator yêu cầu
source binding document/snapshot và toàn bộ anchor metadata bằng reference thật của
record. Page/image, provenance level và raw IDs được kiểm tra; selectors không được
nâng page-level thành cell-level. Cùng source_key nhưng khác status/level/metadata là
collision invalid, không âm thầm lấy bản resolved thay cho uncertain.

`associated_with`: SourceFact → TextEvidence/TableEvidence. Builder index candidates
theo source_key, rồi gọi lại `associate_fact()`; validator gọi lại helper này trên
records thật, kiểm tra document/snapshot/request binding. Cùng trang hoặc fuzzy text
không đủ. Association có thể chỉ là context chung trong payload, không chứng minh
semantic support hoặc whole-table accuracy. Không có relations claim/verification.

Node IDs hash identity đầy đủ cùng namespace; edge IDs hash relation/source/target.
Thiếu identity không tạo indexed node hoặc anchor ID giả. `input_issues.reference`
trỏ `records/{index}` trong thứ tự facts rồi evidence do caller cung cấp; caller phải
giữ payloads/quarantine gốc để audit. Indexed record thiếu source vẫn giữ node unresolved.
Duplicate records/collisions báo occurrence và không overwrite; validator còn kiểm tra
catalog duplicates, node/edge identities, domain, dangling refs và bindings.

## Validation semantics và giới hạn

Sau review correction, `status/reasons` chỉ phản ánh **structural validity**:
`invalid` là known violation; `unresolved` là thiếu identity/source/reference hoặc
chưa có exact association; `valid` là types/identity/refs/bindings/selectors đủ và
đúng theo contracts. Known violation ưu tiên invalid. Chỉ structural reasons được
truyền từ endpoints tới edge. Uncertain source hoặc ambiguous period/context không
tự đổi structural status. Missing source hoặc unsupported provenance vẫn chặn valid.

`grounding` giữ riêng observed levels, upstream source statuses và các reasons
missing/unsupported/uncertain. Edge giữ hợp các metadata grounding từ endpoints,
không tính confidence hoặc quality decision mới. `evidence_context[node_id]` giữ
M2 quality decisions/issues/caveats và resolution/structural issues nguyên semantics;
edge resolve context qua source/target node IDs. Không có aggregate quality status.
Structural valid không chứng minh source resolved, semantic support hoặc financial
fact verified. `financial_fact_verified` vẫn false.

Schema từ chối unknown node/edge types; metadata
provenance không hợp lệ bị phát hiện khi validate. Unreferenced anchor không có trong
record catalog giữ unresolved. Orphans là nodes không có incident edge với đủ hai
endpoints; báo riêng, không tự loại bỏ khỏi partial graph.

Đây là representation in-memory/JSON; không graph database, query/traversal engine,
pipeline hook, metric calculation hoặc quality aggregation. `used_in` sẽ cần
SourceFact → DerivedMetric contract tại M3-05; v1 chưa nhận relation này vì chưa có
DerivedMetric record/type. Thêm node model vào discriminated union và domain check
khi được giao task tương lai; không placeholder/plugin system. Operational semantics
về sau dùng `assess_compatibility()` M3-01, không duplicate accounting rules.

Validator không đọc PDF hoặc chứng minh selector/cell glyph tồn tại ở nguồn độc lập.
Runner real-artifact đối chiếu selectors với persisted payload riêng. Kết quả và
limitations ở [real-artifact report](m3-04-real-graph-validation.md).

Runner có hai probes deterministic: persisted direct retrieval với caveat (không
yêu cầu cell grounding), và gross-margin operand readiness dùng nguyên
`assess_compatibility()`. Không endpoint/chatbot/M4 tool và không thực thi phép tính.
