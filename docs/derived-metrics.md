# Derived Metric Records — M3-05

API qua `vietnamese_financial_multi_agent.evidence`: `FormulaDefinition`,
`MetricRequest`, `MetricOperand`, `DerivedMetric`, `build_metric()`,
`DerivedMetricNode`; mở rộng `build_graph()`/`validate_graph()` bằng keyword
`metrics=()`. Không đổi M1/M2 hoặc facts M3-02, không thêm executor.

`FormulaDefinition` giữ reference/version/name/expression, expected operand roles
và `OperationCompatibilitySpec` M3-01. `policy_status=reference_example` phân biệt
công thức minh họa với executable accounting policy chưa được phê duyệt. Expression
là mô tả dùng tên roles, không parse/eval. Ba examples cố định trong
`scripts/validate_m3_metrics.py`: gross profit / revenue; liabilities / assets;
(current revenue − prior revenue) / prior revenue. Output là ratio, chưa nhân 100,
zero denominator/rounding/precision policy phải được chốt tại M4 trước execution.
Không dùng expression để tự quyết định accounting semantics.

`MetricRequest` bắt buộc document/snapshot identity và period cho từng role.
`build_metric(definition, request, facts)` chỉ lấy candidates khớp canonical item,
statement, period và document/snapshot; không dùng raw label hoặc tự gán semantic
role. Giữ mọi candidate khi có nhiều observations, kể cả values bằng nhau hoặc
duplicate input identity. Không preferred attempt, merge hoặc cross-attempt binding.
Một candidate thiếu local identity giữ `unresolved_identity`, không bind/cạnh giả.
V1 chỉ tham chiếu SourceFact; nested DerivedMetric chưa được hỗ trợ.

Metric ID hash toàn definition, request, role và candidate/binding identities/counts,
không hash giá trị để deduplicate. Hai attempts tạo metric instances riêng. Record
giữ ObservationIdentity, canonical item, company, semantic role, FinancialContext,
unit và SourceFact node ID cho mỗi role bind. Không copy FinancialValue hoặc toàn
fact; provenance resolve qua SourceFact → `from_source` → EvidenceAnchor.

Ba chiều được giữ độc lập:

| Chiều | Fields / semantics |
| --- | --- |
| Structural | `binding_status`: fully_bound/partially_bound/missing_operands/ambiguous_candidates; `structural_readiness`: complete/incomplete/ambiguous. Complete chỉ nói roles/references đã bind |
| Semantic | `compatibility`: nguyên kết quả `assess_compatibility()` M3-01, giữ exact codes/roles/outcomes. Không engine thứ hai. Partial binding trả missing_operand theo engine hiện có; không khẳng định các field còn lại đã đạt |
| Evidence | `evidence_usability` theo từng bound role: nguyên M2 quality_context, resolution codes, source levels/statuses/provenance reasons, missing-value và display status. Không aggregate/propagate quality hoặc tạo quality decision mới |

Display probe yêu cầu normalized/raw value, nguồn, đúng một persisted direct_qa
usable/usable_with_caveat và không có known inconsistent provenance. Insufficient/
conflicted hoặc thiếu value luôn blocked; thiếu annotation giữ undetermined.
`display_with_caveat` chỉ là extracted display có giới hạn nguồn, không approval
cho calculation. `preparation_blockers` giữ cả policy, binding, compatibility và
evidence blockers; không thay ba chiều bằng một boolean. Task-specific analytical
quality policy vẫn cần phê duyệt, không tái dùng direct_qa làm computation approval.

Graph bổ sung DerivedMetricNode tham chiếu metric_id, cạnh `used_in` theo hướng
SourceFact → DerivedMetric, bắt buộc `operand_role`. ID cạnh hash source/target/role;
hai roles dùng cùng source vẫn phân biệt. Existing edge IDs giữ nguyên; field
operand_role optional/null trên cạnh cũ, payload cũ vẫn parse. Builder chỉ tạo cạnh
khi bound observation có trong catalog, không tạo SourceFact thay thế. Validator
resolve metric/fact catalogs, tái dựng binding/readiness để phát hiện stale/tampered
records, kiểm tra edge domain/role/duplicates/missing edges/identity/document/snapshot.
Metric incomplete có thể có node structural valid; kiểm tra readiness ở record.
Metric grounding đọc sources của bound facts, không nâng source status/level.

`DerivedMetric` JSON strict: role/count/status/reference coherence và deterministic
identity được kiểm tra khi parse. `result=None`; statuses not_computed/unavailable/
invalid_inputs. **Computed bị từ chối hoàn toàn ở M3-05**, kể cả LLM number kèm
execution reference tự khai. Acceptance deterministic result/lineage thuộc M3-06/M4.
Không confidence hoặc quality propagation.

Persistence dùng `core.persistence.atomic_json` với list metric JSON trong output
ignored mới, rồi `TypeAdapter(list[DerivedMetric]).validate_json()` để restart.
Không repository/database mới. Caller cung cấp storage root; không dùng ID làm path.
Xem [real-artifact report](m3-05-real-readiness.md) cho giới hạn dữ liệu thật.
