# Unified Evidence Retrieval v1 — M3-07

Public API qua `vietnamese_financial_multi_agent.evidence`; module
`src/evidence/retrieval.py`. Facade read-only trên snapshot catalogs; không thêm
repository, storage engine, pipeline hook, HTTP/UI hoặc M4 executor.

`EvidenceRetrieval(facts=(), evidence=(), metrics=(), *, graph=None, coverage=())`
copy inputs, không I/O. `from_repositories(fact_repositories,
evidence_repositories, document_ids, **kwargs)` dùng public `list_by_document()`
của repositories M3-02/03; caller truyền document IDs thật và storage đã cấu hình.
Quarantine không vào indexed retrieval. Muốn thấy snapshot mới, caller tạo facade
mới; facade không tự refresh hoặc chọn latest. Metrics dùng persisted catalog M3-05,
lineage gọi M3-06 trên graph được caller truyền; thiếu graph không tự dựng thay thế.

| API | Input bắt buộc | Kết quả |
| --- | --- | --- |
| `get_fact(identity)` | ObservationIdentity đầy đủ document/snapshot/local | CanonicalFinancialFact nguyên value/context/quality |
| `find_facts(query)` | EvidenceQuery, có thể rỗng | Mọi candidates; không chọn một observation tùy ý |
| `get_evidence(identity)` | EvidenceIdentity có kind text/table | Persisted text/table record nguyên payload |
| `find_evidence(query)` | EvidenceQuery | Text/table theo document/snapshot/page/kind; financial filters trả unavailable |
| `get_metric(metric_id)` | Exact persisted metric ID | DerivedMetric; không numeric execution |
| `get_lineage(metric_id)` | Exact metric ID | MetricLineage, operands/candidates/blockers/anchors |
| `get_anchor(anchor_id)` | Graph anchor ID từ citation | EvidenceAnchor; dangling/identity mismatch tường minh |
| `get_sources(reference)` | RetrievalReference typed | Original record hoặc lineage và citations; không source trả unavailable |

EvidenceQuery có các filters optional kết hợp AND: document_id, snapshot_id,
company_id, canonical_item_id, statement_type, period, period_type, reporting_scope,
source_page, evidence_type. None nghĩa là không lọc, không xác nhận context thiếu.
Exact lookup cần identity đầy đủ; semantic query rộng trả ambiguous nếu nhiều
observations, kể cả hai periods caller muốn so sánh. Caller có thể trình bày từng
candidate riêng hoặc query từng kỳ; không tính chênh lệch/tỷ lệ. Không suy company,
scope hay kỳ từ filename, không merge same-value observations xuyên tài liệu.

RetrievalResult JSON giữ exact Decimal strings, stable ordering, identities,
record payload và citations. `found` nghĩa là một record phù hợp, không xác minh
tài chính. `not_found` là không có match trong catalog đã cung cấp; không kết luận
extraction chưa chạy. `ambiguous` giữ tất cả candidates. `conflicted` dành cho
known M2 conflicted hoặc cùng identity khác payload; khác tài liệu/giá trị tự nó
không chứng minh conflict. `unavailable` dành cho thiếu inputs đã biết, broken
lineage hoặc inventory-backed missing coverage. Lineage partial vẫn found kèm
partial_lineage; missing toàn bộ used_in edges được facade nhận diện broken.

Reason codes chính: `no_matching_fact`, `missing_period`, `ambiguous_candidates`,
`known_conflict`, `canonical_extraction_missing`, `canonical_mapping_missing`,
`missing_derived_metric`, `graph_unavailable`, `broken_lineage`,
`missing_evidence_anchor`, `dangling_evidence_anchor`, `source_unavailable`.
`CanonicalCoverage` bắt buộc inventory_reference và explicit document identity;
snapshot optional chỉ dùng khi inventory áp dụng toàn document. Không có inventory
thì missing item vẫn no_matching_fact. Caller chịu trách nhiệm inventory đúng scope
và còn hiệu lực; facade không kiểm kê filesystem hoặc diễn giải raw code thành mapping.

M2 annotations/issues/caveats giữ nguyên trong `match.record.quality_context`.
`display_status` riêng theo direct-display criteria M3-05: có số và source page,
đúng một direct_qa decision usable/usable_with_caveat, không provenance inconsistency
thì display_with_caveat; insufficient/conflicted chặn display, thiếu annotations
giữ undetermined. Retrieval không loại bỏ blocked facts hoặc cấp phép calculation.
Compatibility vẫn nằm riêng ở metric/lineage; financial_fact_verified luôn false.

EvidenceCitation giữ document/snapshot, PDF page, provenance_level, anchor_id và
EvidenceAnchor nguyên nguồn (source_ref/image/pointer/real element/table/cell IDs).
Page/uncertain giữ nguyên; không bbox giả hoặc nâng cell-level. Citations của fact
đọc source references gốc, không đòi graph phải available; get_anchor kiểm tra
graph/catalog reference riêng. `evidence_references` là exact `associate_fact()`
references; association không chứng minh semantic support. Không tạo fact từ text/table.

## Real-artifact evaluation

Runner cố định 18 structured queries trước execution, dùng hai W-07 attempts,
hai canonical repositories M3-04/final, hai document repositories M3-03 và sáu
persisted metrics M3-05. Expected/actual filters, identities, statuses, original
values, units, quality, anchors, limitations và pass/fail từng query nằm trong
ignored `artifacts/evidence/M3-07/run-2/report.json`; không commit financial artifacts.

| Queries | Mục đích | Actual / expected |
| --- | --- | --- |
| Q01–04 | Assets, net revenue, gross profit, cash cuối kỳ trên fresh attempt | 4 found / 4 PASS |
| Q05–06 | Revenue hai annual periods, assets hai instant dates | 2 ambiguous, đủ 2 candidates/query / PASS |
| Q07 | Net revenue không scope attempt/document | ambiguous, 2 candidates / PASS |
| Q08 | Storage revenue M2 insufficient | found, display blocked / PASS |
| Q09 | Source-backed revenue lookup | found và citations / PASS |
| Q10–11 | Text/table exact persisted lookup | 2 found / PASS |
| Q12–13 | Gross-margin metric và lineage | 2 found, lineage complete, compatibility undetermined / PASS |
| Q14 | Liabilities thiếu canonical mapping | unavailable/canonical_mapping_missing / PASS |
| Q15 | Original filing 2022 thiếu canonical extraction | unavailable/canonical_extraction_missing / PASS |
| Q16 | Nonexistent observation identity | not_found/no_matching_fact / PASS |
| Q17 | Revenue period chưa có | not_found/missing_period / PASS |
| Q18 | Uncertain page provenance | found, giữ page/uncertain / PASS |

356/356 exact lookups found, 0 ambiguous/missing; 292 display_with_caveat/64 blocked.
356/356 có page citations trên trang 5–8; 56 text/table records và 6 metrics.
18/18 query expectations PASS: 11 found, 3 ambiguous, 2 unavailable, 2 not_found.
Original M2 quality preserved; JSON round-trip và repository restart exact,
document/snapshot identities không bị merge. Real data không có known conflicted
case trong scope này; conflict được kiểm tra bằng synthetic negative controls.

Mô phỏng 14 financial questions không LLM: sáu câu/snapshot (bốn direct numbers,
hai period comparisons) và hai missing-coverage questions. **9 complete_with_caveat,
3 partial_quality_blocked, 2 canonical_unavailable**. Partial nghĩa là lấy được
record và source nhưng quality chặn answer data đầy đủ, không phải số đã usable.
Không so sánh bằng phép tính, không chatbot hoặc external PDF accuracy evaluation.

Inventory M3-06 được dùng có nguồn/hash cho 2021–2024: OCR có nhưng chưa canonical
facts. Identity `pdf-sha256:<hash>` chỉ định danh PDF inventory chưa extraction,
không company ID hay runtime document ID giả. Kỳ 2024 có trong comparative filing
2025 vẫn giữ document 2025; không thay thành original filing 2024.
Tên PDF 2021 local hiện là BBS_2021.pdf, inventory cũ là BB2_2021.pdf; hash khớp,
runner ghi source_aliases riêng, không rename/move nguồn hoặc sửa evidence M3-06.
172 input hashes unchanged; zero Gemini/OCR/extraction calls và raw changes.

```powershell
.venv/Scripts/python.exe scripts/validate_m3_retrieval.py --output artifacts/evidence/M3-07/new-run
.venv/Scripts/python.exe -m pytest tests/unit/test_evidence_retrieval.py tests/unit/test_canonical_facts.py tests/unit/test_document_evidence.py tests/unit/test_evidence_graph.py tests/unit/test_derived_metrics.py tests/unit/test_metric_lineage.py tests/unit/test_evidence_contracts.py -q
```

Output phải là directory mới. Không full regression/browser tests hoặc live calls.
Đây là retrieval consistency và deterministic evidence usability trên persisted
extractions, chưa xác minh financial accuracy ngoài PDF, coverage toàn báo cáo
hoặc nhiều original filings. Tech Lead nghiệm thu độc lập trước DONE.

14 focused M3-07 test cases bao phủ negative controls: wrong document/snapshot/
period/item, ambiguous same-value cross-document/snapshots và không latest,
missing SourceFact/anchor/used_in, dangling anchor, uncertain provenance,
M2 insufficient/conflicted, missing metric/broken lineage, text/table identity
mismatch và structural validity không financial verification. Nhóm targeted
M3-02–06/contracts kèm M3-07 tổng 102 PASS; Ruff toàn repository/planning/diff PASS.
Implementation `e8f293de4445f91860ff8820f123502da649d2e6` đã push main;
[CI41056561499](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41056561499)
completed/SUCCESS đúng SHA, Python 3.12 và Web smoke đều SUCCESS.
