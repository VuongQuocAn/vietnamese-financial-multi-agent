# M4-04 — Evidence Retrieval Tools

Năm deterministic read-only tools ở `vietnamese_financial_multi_agent.tools` dùng
`SnapshotCatalog`, M3-07 `EvidenceRetrieval` và M4-02 `FinancialRetrievalTools`.
Caller hydrate persisted repositories/graph/reviews trước khi khởi tạo
`EvidenceRetrievalTools(catalog)`. Tools không đọc PDF, gọi LLM hoặc tính metric.

| Method / request | Identity và selection | Output |
| --- | --- | --- |
| `get_evidence_item(GetEvidenceItemRequest)` | document, snapshot, local evidence ID, kind text/table bắt buộc | Original TextEvidence/TableEvidence, exact reference, citations và issues |
| `find_document_evidence(FindDocumentEvidenceRequest)` | document/snapshot bắt buộc; source_page/evidence_type optional | Toàn bộ matches; nhiều records giữ ambiguous theo M3 |
| `get_evidence_anchor(GetEvidenceAnchorRequest)` | exact graph anchor ID; optional document/snapshot guards | Original anchor, pointer/IDs/image/page/provenance/bbox nếu nguồn có |
| `get_evidence_sources(GetEvidenceSourcesRequest)` | typed M3 RetrievalReference; optional guards | Original citations, exact identities, source associations và fact SourceReview |
| `get_metric_evidence_lineage(GetMetricEvidenceLineageRequest)` | exact metric ID; optional guards | M3 MetricLineage và M4-02 FinancialMetricMatch với formula, operands, SourceFact IDs, reviews và completeness |

Requests version `evidence_tools_request_v1`, discriminated union theo `tool`.
Response `EvidenceToolResponse` version `evidence_tools_v1` mở rộng M3
`RetrievalResult`: `request`, `matches`, `reasons`, `inventory_references`,
`snapshot_candidates`, `reporting_scopes`, `source_reviews`, `metric_matches`,
`caveats`, `financial_fact_verified=False`. Citations ở `matches[].citations`;
reviewed lineage ở `metric_matches[].reviewed_lineage`. JSON round-trip giữ nguyên
typed records. Inputs và returned objects được deep-copy, không sửa catalog nguồn.

```python
from vietnamese_financial_multi_agent.tools import (
    EvidenceRetrievalTools,
    GetEvidenceSourcesRequest,
)

evidence_tools = EvidenceRetrievalTools(catalog)
# fact_match là FinancialFactMatch từ M4-02, giữ nguyên typed reference.
sources = evidence_tools.get_evidence_sources(
    GetEvidenceSourcesRequest(reference=fact_match.reference)
)
```

`found` chỉ xác nhận record tồn tại. `ambiguous` giữ toàn bộ candidates;
`conflicted` giữ các payload mâu thuẫn, không lấy candidate đầu tiên.
`not_found` cho identity/filter không khớp. Missing graph, missing/dangling
anchor hoặc broken lineage trả `unavailable` với reason cụ thể. Missing source
giữ `source_unavailable`; partial lineage giữ M3 status và unresolved reasons.

Không latest/parent fallback, không merge recovery và original. Guard sai không
trả records/citations của document khác. Company/financial period và các financial
filters của document evidence trả
`financial_filter_unavailable_for_document_evidence`; không keyword search.

Scope unresolved không chặn evidence gốc. D-07 2024 separate, các năm còn lại
unresolved; caveat được giữ và không phê duyệt cross-document compatibility.
`value_row_verified` là controlled source review trong phạm vi đã kiểm tra.
`associated_with` chỉ là source association; không là verified semantic support.
Page-level/uncertain citations giữ nguyên, không sinh bbox/selector hoặc nâng
provenance. M4-03 computed result là artifact riêng: persisted `DerivedMetric.result`
vẫn None, không dùng graph làm kho computed results.

## Validation

Focused tests và evaluator offline:

```powershell
.venv/Scripts/python -m pytest tests/unit/test_evidence_retrieval_tools.py tests/unit/test_evidence_retrieval.py tests/unit/test_financial_retrieval_tools.py tests/unit/test_financial_calculator.py tests/unit/test_m4_execution.py tests/unit/test_snapshot_closure.py -q
.venv/Scripts/python scripts/evaluate_m4_04_evidence.py --output artifacts/evidence/M4-04
```

Evaluator yêu cầu accepted artifacts local M4-03-final và D-01/D-04/D-06/D-07;
output mới phải chưa tồn tại dưới `artifacts/evidence`, không ghi đè input.
Inventory đọc repositories đã persist, đối chiếu hydrated records và selected graph.
Các trang không có TextEvidence/TableEvidence được ghi riêng; không coi absence
của canonical records là PDF không có nội dung.

203 focused tests PASS, gồm 17 wrapper cases trên hai synthetic documents và
ba M3 source-availability regressions. Một warning từ existing calculator test
cố ý đưa invalid Decimal; tests vẫn PASS. CI focused list thêm suite M4-04.

## M3 runtime correction

Root cause: `EvidenceRetrieval.get_sources()` chỉ kiểm tra danh sách citations
khác rỗng. Citation wrapper vẫn được tạo khi anchor thiếu `reference`, sai
document/snapshot binding hoặc image rỗng, dẫn đến `found` dù không truy xuất
được source. Ba controls tái hiện đều FAIL trước sửa, PASS sau sửa.

Correction tối thiểu kiểm tra source identity/reference, positive PDF page,
image và owner binding trước khi xác nhận source available. Nếu không có
source đủ thông tin, trả `unavailable/source_unavailable` và giữ nguyên original
records/citations. Page-level và uncertain sources có thông tin trang/image
vẫn available kèm limitations; không đòi cell selector hoặc đổi review status.
Không refactor retrieval engine/graph/lineage hoặc thay policies.

Targeted source replay sau correction:

```powershell
.venv/Scripts/python scripts/evaluate_m4_04_evidence.py --source-controls-only --output artifacts/evidence/M4-04-source-check
```

## Real BBS 2021–2025

Artifacts local ignored: `artifacts/evidence/M4-04/` gồm inventory, exact evidence,
page queries, anchors, priority fact sources, metric lineages và regression summary.
Targeted replay sau M3 correction ở `artifacts/evidence/M4-04-source-check/`.

| Evidence type | Available | Retrieved | Blocked/Unavailable |
| --- | ---: | ---: | ---: |
| Text | 139 | 139 | 0 |
| Table | 24 | 24 | 0 |
| Anchor | 2.973 | 2.973 | 0 |
| Metric lineage | 18 | 18 | 0 |

3.154 exact record/lineage cases PASS. Cả 2.973 anchors giữ
`source_reference_uncertain` và `page_level_only`; 163 document evidence records
cũng giữ các caveats này. 24 tables giữ `partial_or_uncertain_cells` và
`structure_not_verified`. Không có nâng provenance hoặc financial verification.

| Filing / selection | Text | Table | Anchor | Trang có text/table records | Trang chưa có records |
| --- | ---: | ---: | ---: | --- | --- |
| 2021 original | 23 | 4 | 508 | 6–9 | 1–5, 10–28 |
| 2022 original | 22 | 4 | 501 | 5–8 | 1–4, 9–26 |
| 2023 original | 24 | 4 | 512 | 5–8 | 1–4, 9–29 |
| 2024 original | 23 | 4 | 482 | 7–10 | 1–6, 11–26 |
| 2025 original | 24 | 4 | 464 | 5–8 | 1–4, 9–24 |
| 2022 recovery | 23 | 4 | 506 | 5–8 | 1–4, 9–26 |

Original selection là `D-01/normalized-v2`, recovery riêng `D-02/recovery-2022-v1`.
Năm PDFs có 133 trang; canonical text/table records bao phủ 20 trang original.
Recovery bao phủ riêng bốn trang của cùng PDF 2022. Trên 159 page selections
(tính recovery riêng), 477 queries gồm all/text/table: 72 có records, 405
`not_found` do thiếu catalog coverage. Đây không phải 405 trang PDF khác nhau.

25 priority fact-source cases (assets/liabilities/revenue/gross profit/operating
cash flow × 5 filings) PASS qua typed references M4-02. Cả 25 có exact source
associations; associated records truy xuất lại được, giữ caveat không xác minh
semantic support. Scope unresolved vẫn trả nguồn gốc. SourceReview được giữ nguyên.

18/18 lineages khớp original accepted M4-03 `executions.json`, bao gồm formula,
operand roles/identities, SourceFact IDs, source reviews, anchors, pages/selectors,
closure và reviewed lineage. Cả 18 calculations chạy lại khớp artifact, đồng thời
khớp independent Decimal arithmetic. Recovery 2022 không lấy citations original.
Ví dụ Gross Margin 2025 giữ kết quả accepted 7.21% trong execution artifact và
nguồn operands B02 PDF trang 7; M4-04 trả lineage, không tính lại kết quả.
JSON/restart exact cho toàn bộ 163 document records và 18 lineages.

Bounded regression giữ 15+3 eligibility, 29 accepted queries, 36 undetermined
cross-document pairs, năm D-07 scope views, M4-02 partial-scope correction và
D-06 QA09/QA15. 2.657 protected input hashes unchanged; zero Gateway/Gemini/OCR/
extraction. Tests/evidence này không chứng minh independent financial accuracy.

Sau M3 correction: 2.087 exact fact-source cases (1.177 original/recovery và
910 D-06 corrected facts), 163 text/table source cases, 29 accepted queries PASS.
Bảy real negative controls PASS: ba `unavailable` (missing anchor, missing graph,
unsupported period), bốn `not_found` (missing evidence/snapshot, sai document,
recovery metric với original guard). Không fallback nguồn gần giống.

## Review checkpoint

Implementation [`304da3a6a95873acd88fc3b49a5fd0268e07653f`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/304da3a6a95873acd88fc3b49a5fd0268e07653f),
format fix [`a36493b60834c32b5629f23dc4bfa0062359db01`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/a36493b60834c32b5629f23dc4bfa0062359db01)
đã push main. [CI41381388861](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41381388861)
completed/SUCCESS đúng fix SHA; Python3.12 lint/format/planning/focused tests SUCCESS;
Web smoke/full regression SKIPPED theo workflow. CI implementation ban đầu dừng ở
format Python code fence trong tài liệu; correction chỉ format, runtime không đổi.
Local Ruff lint/format toàn repo365 files/planning100/diff PASS.
Checkpoint sau chỉ ghi evidence/docs/planning, không gán CI fix cho SHA checkpoint.
Không phát hiện P0/P1 còn mở trong phạm vi đã kiểm tra. Giữ web local byte-for-byte.
Next action: Tech Lead independent review M4-04; chưa bắt đầu M4-05.
