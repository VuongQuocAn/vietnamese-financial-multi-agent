# Canonical và Provenance Contracts — M3-01

Public API: `vietnamese_financial_multi_agent.evidence`. Chỉ biểu diễn metadata;
không ingest/persist facts, chạy graph, tính metric hay xác minh claim.

| Contract/API | Ý nghĩa |
| --- | --- |
| `SourceFact` / `CanonicalFinancialFact` | Cùng một model; canonical item nullable, giữ raw ngoài catalog |
| `ObservationIdentity` | Tuple logic document_id + snapshot_id + local_id, có thể hash; thiếu một thành phần thì helper trả None |
| `SemanticFactKey` | Company + canonical item + statement/period/type/scope/currency/scale + unit; không chứa raw label/code |
| `EvidenceAnchor` | document/snapshot binding và `FinancialSourceReference` nullable; `source_key()` scope selector theo document/snapshot/page |
| `TaskQualityContext` | Giữ task type, bốn decisions M2, issues/caveats và evidence IDs; không propagation |
| `assess_fact_consistency(fact)` | consistent/unresolved/inconsistent cùng code/path; không mở PDF hoặc sửa inputs |
| `OperationCompatibilitySpec` | Hai operand requirements theo role/item/semantic role/statement, quan hệ kỳ và tài liệu tường minh |
| `FinancialOperand` / `assess_compatibility(spec, operands)` | compatible/incompatible/undetermined, reason codes, roles và observation references |

`FinancialValue`, `FinancialContext`, `FinancialSourceReference`, `SourceAnchor`,
`RawPageIdentity`, `QualityIssue` và task decisions tái sử dụng M1/M2 nguyên semantics.
Không có parser số, period/unit resolver, item mapping hoặc source selector mới.
`value` giữ raw string, Decimal chính xác và status/issues; `context` giữ kỳ,
scope, currency/scale, statement, raw label/code. B09 vẫn được nhận như M2;
statement chưa xác định là null. `source_item_code` giữ mã nguồn riêng mapping.
`resolution_issues` giữ thiếu/mơ hồ; `quality_context` giữ annotations có nguồn.

## Identity và provenance

Caller cung cấp document_id ổn định trong corpus và snapshot_id phân biệt từng
extraction attempt/snapshot trong document. Không dùng symbol/year/item làm ID,
không suy run từ filename/hash/source_ref. local_observation_id chỉ unique trong
document/snapshot; caller M3-02 chịu trách nhiệm phát hiện local ID trùng khi ingest.
Missing IDs vẫn lưu được, `observation_identity()` trả None. Không tự điền từ anchors.

Reporting period thuộc fact, độc lập document identity và `RawPageIdentity.year`.
Ví dụ chỉ tiêu 2024 trong BBS_2024 và cột so sánh BBS_2025 có thể cùng semantic key,
nhưng khác document/observation/source keys. Phải giữ hai observations, kể cả giá trị
bằng nhau. Khác attempt cũng giữ riêng. Semantic key **không phải deduplication key**;
không gộp hoặc tự kết luận conflict/restatement giữa hai nguồn. Khác kỳ/scope không
cùng semantic key. Thiếu company/mapping/statement/period/type/scope/currency/unit/scale
thì `semantic_key()` trả None; không loại raw observation. Key là model so sánh
metadata, không phải hash toàn cục hoặc chứng nhận context đã được xác minh.

EvidenceAnchor wrap reference M2, không copy hoặc sửa raw payload. Nguồn thiếu
binding/reference hoặc anchor uncertain/unresolved được thể hiện bằng assessment
unresolved; binding document/snapshot khác fact trả inconsistent. Page số không hợp
lệ/thiếu ảnh hoặc level vượt anchor IDs trả inconsistent. Cell-level cần table_id
và cell_id nguồn; element-level cần element/table/line ID. Có IDs chỉ đủ kiểm tra
metadata, validator không phát hiện ID giả nếu chưa đối chiếu nguồn. Không sinh ID/bbox.

Page provenance được giữ nguyên ngay cả khi source_pointer trỏ tới ô trong JSON.
Pointer payload và row/column không chứng minh cell grounding. `source_key()` scope
cả pointer/IDs/observed bbox theo document/snapshot/page, không có global cell ID;
source_ref/image giữ nguyên locator M1, không tự resolve. proposed_bbox không là
observed source identity. Thiếu binding/reference trả source key None.
Hash nguồn, consistent assessment và compatible semantics đều không chứng nhận
financial accuracy. `financial_fact_verified` chỉ nhận false.

## Semantic compatibility

Spec do caller chọn theo operation/policy được duyệt, với `rule_reference` truy
nguyên; field này không tự xác minh approval. Chưa có catalog rule thực thi M4.
Validator chỉ xét metadata của hai operands, không đọc/tính raw hoặc normalized values.

| Scenario trong task | Khai báo | Kết quả |
| --- | --- | --- |
| Gross margin | Roles revenue/gross_profit với IDs b02.net_revenue/b02.gross_profit, statement B02; period_relation=same | Compatible khi metadata đầy đủ, cùng kỳ/type/scope/company/currency/unit/scale |
| YoY revenue | Hai roles prior/current đều revenue; ordered_pair với cặp fiscal_year 2024→2025 đã xác nhận | Compatible; hai kỳ khác nhau là yêu cầu, không phải mismatch |
| Sai role/item/statement theo spec | Metadata đã biết trái requirement | Incompatible |
| Khác scope/company/currency hoặc period_type | Hai metadata đã biết khác nhau | Incompatible |
| Thiếu period/scope/company/document, observation identity hoặc context có resolution issues | Không đủ căn cứ | Undetermined |
| Khác unit/scale hoặc scale không dương | Chưa có conversion đã duyệt | Undetermined; không nhân/chia giá trị |

Quan hệ tài liệu `same` chặn khác document; `any` cho phép cross-document khi
company/context phù hợp. Không yêu cầu extraction snapshot của hai operands giống
nhau; snapshot thuộc observation identity. Không đánh đồng document khác với kỳ khác.
PeriodPair khai báo kỳ trái/phải và period_type, không parse năm/kỳ mới. Không có
cặp kỳ được xác nhận thì undetermined; không suy annual/quarter từ chuỗi tùy ý.
Missing operand giữ role và reason; duplicate/unknown role bị incompatible.
Known mismatch ưu tiên incompatible khi đồng thời có missing metadata; mọi reasons
đều giữ lại. Compatible không có nghĩa input values đã chính xác hoặc đủ điều kiện
thực thi phép chia (ví dụ denominator zero thuộc M4).

Compatibility tái sử dụng các source issues từ `assess_fact_consistency()` cho từng
operand: provenance inconsistent trả incompatible, unresolved trả undetermined.
Giữ nguyên issue code và operand role; thiếu provenance không loại raw/unmapped fact
khỏi model hoặc truy xuất. Consistency/compatibility vẫn không xác minh số liệu tài chính.

## TBD và giới hạn

M3-02 quyết định cấp/kiểm tra uniqueness IDs, ingest/persistence và reconciliation
các observations có cùng semantics. Không mặc định merge cross-document/restatement.
M3-03 đối chiếu nguồn chi tiết, M3-04 mở graph với các IDs/references này;
M3-05/06 xử lý metric/lineage/quality propagation. M4 phê duyệt catalog operations,
period comparability ngoài các pairs tường minh, unit/scale conversions, multi-operand
formulas và execution preconditions. Claim/VerificationRecord thuộc M5/M6.
Không thêm graph nodes/edges, agents, Gateway calls, schemas của M1/M2 hoặc runtime demo.
Focused fixtures chỉ chứng minh engineering invariants, không đánh giá PDF BBS thực tế.
