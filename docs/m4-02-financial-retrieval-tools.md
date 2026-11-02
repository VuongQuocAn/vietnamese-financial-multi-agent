# M4-02 — Typed Financial Retrieval Tools

Ngày02/11/2026 (Asia/Bangkok). Status **REVIEW**. Baseline main
`075222afcf4992dd80fbd600c4979b7d66f3f78e`; chờ Tech Lead independent review.

## Public API v1

Import từ `vietnamese_financial_multi_agent.tools`. Caller hydrate
`SnapshotCatalog` từ persisted descriptors/facts/evidence/metrics/graph/reviews và
production approvals trước khi tạo `FinancialRetrievalTools(catalog, coverage=...)`.
Không I/O, rebuild metrics, LLM/NLP, financial calculations hoặc storage engine mới.
Catalog được copy riêng; response deep-copy, sửa object trả về không sửa lần gọi sau.

| Method | Request | Selection |
| --- | --- | --- |
| `get_financial_fact` | `GetFinancialFactRequest(document_id, snapshot_id, local_observation_id)` | Exact ObservationIdentity, không fallback |
| `find_financial_facts` | `FindFinancialFactsRequest` kế thừa EvidenceQuery | AND: document/snapshot/company/canonical item/statement/period/period type/scope/source page |
| `get_financial_metric` | `GetFinancialMetricRequest(metric_id, document_id=None, snapshot_id=None)` | Exact persisted metric ID; hai optional fields là AND guards |
| `list_financial_metrics` | `ListFinancialMetricsRequest(document_id, snapshot_id=None, formula_id=None)` | Chỉ persisted records; formula_id đối chiếu `definition.name` |

Mỗi request có literal `tool` discriminator tương ứng method. Financial filters
không dùng raw label, filename hoặc fuzzy search. Không tự chọn candidate đầu tiên.
Không rebuild hoặc chọn lại operands cho metric. Exact metric ID đã ràng buộc
snapshot trong persisted record nên không cần caller lặp document/snapshot.

Ví dụ (IDs do caller lấy từ persisted inventory, không dùng filename thay ID):

```python
from vietnamese_financial_multi_agent.tools import (
    FinancialRetrievalTools,
    GetFinancialFactRequest,
    GetFinancialMetricRequest,
)

tools = FinancialRetrievalTools(catalog, coverage=coverage)
fact_response = tools.get_financial_fact(
    GetFinancialFactRequest(
        document_id=document_id,
        snapshot_id=snapshot_id,
        local_observation_id=observation_id,
    )
)
metric_response = tools.get_financial_metric(GetFinancialMetricRequest(metric_id=metric_id))
wire = metric_response.model_dump_json()
```

## Response và status

`FinancialToolResponse.version = financial_retrieval_tools_v1`, JSON-serializable,
strict Pydantic/extra-forbid. `request` là discriminated union của bốn request;
`matches` là discriminated union `FinancialFactMatch`/`FinancialMetricMatch` theo
`kind`. Kèm `snapshot_candidates`, `reporting_scopes`, `reasons`, `caveats`,
`inventory_references` và literal `financial_fact_verified=False`.
Invalid request bị Pydantic ValidationError; thiếu dữ liệu là status/reasons.

| Status | Ý nghĩa |
| --- | --- |
| `found` | Tìm được record; không chứng minh số liệu tài chính đúng hoặc usable |
| `not_found` | Không có identity/filter/kỳ tương ứng; scope confirmed khác request không là match |
| `ambiguous` | Nhiều fact candidates hoặc document có nhiều snapshots chưa chọn; giữ candidates |
| `unavailable` | Known inventory gap, unresolved requested scope hoặc snapshot selection blocked |
| `conflicted` | M3 known conflict, conflicting source review/scope hoặc duplicate metric identity |

`list_financial_metrics` trả `found` khi có nhiều metrics khác ID (đây là list,
không phải yêu cầu một observation); duplicate ID giữ `conflicted`.
Metric record vẫn có thể `found` khi closure blocked: caller phải kiểm
`match.closure.calculation_eligible`, không suy eligibility từ found hoặc SourceReview.

`FinancialFactMatch` tái sử dụng RetrievalMatch, thu hẹp `record` thành
CanonicalFinancialFact, thêm SourceReviewLookup và ReportingScopeResolution.
Raw/normalized value ở `record.value`; currency/scale/period/statement/scope gốc ở
`record.context`; quality/resolution annotations ở record; original citations và
evidence references giữ nguyên M3. Display blocked/undetermined giữ nguyên, không
nâng insufficient/conflicted thành usable. SourceReview là overlay riêng; không
đổi page-level/uncertain citations thành cell-verified.

Decimal value/scale giữ precision và exponent, JSON dưới dạng string; null vẫn
null. Không đổi đơn vị hoặc nhân/chia scale. Round-trip bằng
`FinancialToolResponse.model_validate_json(wire)`; JSON schema qua
`FinancialToolResponse.model_json_schema()`.

## Snapshot và reporting scope

Dùng SnapshotCatalog selection, không latest hoặc parent fallback. Find/list
không chỉ snapshot trong document nhiều snapshots trả ambiguous cùng descriptors,
chưa trả facts. Find toàn catalog cũng yêu cầu selection không mơ hồ ở từng document;
caller thu hẹp document/snapshot để tiếp tục. Snapshot-only filter chỉ xét documents
thực sự có snapshot đó. Parent chain chỉ là lineage, không nguồn facts/reviews.

Scope filter dùng exact-bound ReportingScopeResolution của selected snapshot.
Confirmed khớp mới truy facts qua các AND filters còn lại; confirmed khác trả
not_found/reporting_scope_mismatch; unknown/ambiguous trả
unavailable/reporting_scope_unresolved, conflicting review trả conflicted.
Không sửa `CanonicalFinancialFact.context.reporting_scope`. Không scope filter
vẫn cho đọc record unknown scope với caveats và đầy đủ review reasons.

D-07 original2024 `separate/confirmed`; original2021/2022/2023/2025 insufficient.
Review2024 không áp sang năm khác, D-04 recovery hoặc D-06 projection. Không suy
scope từ ticker/accounting basis hoặc tự cấp cross-document approval.

## Metric contract cho M4-03

`FinancialMetricMatch.record` giữ DerivedMetric/formula ID/version/expression và
bindings gốc. `selected_snapshot` là exact descriptor. `operands` chứa mỗi
MetricOperand (role, exact ObservationIdentity, source_fact_node_id), RetrievalResult
với original fact/value/context/unit/quality/citations và SourceReviewLookup.
`accounting_bases` giữ exact selected snapshot reviews; `reviewed_lineage` chứa
MetricLineage, operand reviews và parent chain; `citations` lấy nguyên M3 lineage.

`closure` tái sử dụng MetricSnapshotClosure từ production SnapshotCatalog gates;
không đánh giá lại bằng một bộ flags riêng trong tools. `closure.readiness` giữ
global compatibility, approved execution compatibility, formula policy/approval,
eligibility/execution blockers. `closure.status`, issues và calculation_eligible
vẫn có khi graph/lineage/reviews/operands thiếu. Không có approval không được tự
mở execution. Caller kiểm eligibility rồi mới gọi executor thuộc M4-03.

`record.result_status=not_computed`, `record.result=None` cho accepted18 metrics.
Eligible không đồng nghĩa computed hoặc financial_fact_verified. Task này không
thực thi formula, không tạo numeric result và không sửa M4-01 approvals.

## Validation và giới hạn

Targeted controls trên hai independent synthetic documents: exact/semantic,
multiple candidates/conflicts/mapping gaps/missing period, no latest/parent,
wrong scope/identity isolation, Decimal/null/unit/scale, insufficient quality,
source-backed scope và unknown scope, metric operands/approvals/lineage,
JSON/restart/returned-object isolation và deterministic ordering.

Local **145 focused PASS** trên tools/retrieval/execution/closure/scope; Ruff toàn
repo **355 files**, planning100 và diff check PASS. CI focused list thêm tools tests.

Offline evaluator: `python scripts/evaluate_m4_02_retrieval.py --output artifacts/evidence/M4-02-final`.
Kết quả local tại `artifacts/evidence/M4-02-final/summary.json` (ignored):

| Kiểm tra | Kết quả |
| --- | --- |
| Exact baseline/recovery facts, original citations/quality/source reviews và JSON | 1.177/1.177 |
| Exact D-06 corrected facts, selected snapshot riêng | 910/910 |
| Semantic/scope/negative BBS cases | 40/40 |
| Metric lookup, closure/lineage/operands/reviews/citations và formula-filtered listing | 18/18 |
| Eligibility Gross Margin / Debt-to-Assets / Revenue YoY | Mỗi formula 5 baseline + 1 recovery; tổng 15+3 |
| Computed metrics | 0 |
| Accepted M3 retrieval queries | 29/29 exact |
| Cross-document pairs | 36/36 undetermined |
| D-07 scope views | 5/5 exact; original2024 separate, bốn năm insufficient |
| D-06 QA09/QA15 và source validations | Giữ nguyên; 100 checks:65 consistent/35 insufficient |
| JSON/restart/returned-object isolation | PASS |
| Protected input hashes | 2.626/2.626 unchanged |
| Gateway/OCR/extraction calls | 0 |

1.177 baseline/recovery facts gồm 1.002 display_with_caveat và 175 blocked; tools
giữ nguyên M3 display statuses. 40 cases gồm 25 item queries (B01 assets/liabilities,
B02 revenue/gross profit,B03 OCF trên năm filings),10 scope filters, mapping gap,
multiple periods/snapshots, recovery scope không kế thừa và insufficient quality.
Baseline2022 B03 vẫn blocked khi thiếu quality; found không làm record usable.

Không phát hiện lỗi retrieval/runtime M3 nên không sửa src/evidence. Phát hiện
evaluator D-06 cũ trong `evaluate_m4_01_eligibility.d06_regression` so JSON cứng:
D-07 thêm `ContextEvidence.scope_selection=None`, gây 58 differences chỉ do default
field được serialize. Sửa bằng hydrate accepted `RelationshipCheck` theo current
typed schema rồi so toàn bộ checks; không bỏ field/caveat hoặc sửa accepted artifacts.
QA09/QA15,giá trị/status/nguồn giữ nguyên. ID query liabilities dùng canonical ID
đã duyệt `b01.total_liabilities`.

Lượt final đã hoàn thành facts/metrics/cases/29 queries/36 pairs trước khi sửa
adapter regression. Tiếp tục tail bằng cùng lệnh thêm `--resume` sau khi xác nhận
protected hashes khớp và tools runtime không đổi; D-06,910 corrected facts,restart18
metrics và final hashes đều PASS. Fresh run yêu cầu output directory mới;
`--resume` chỉ dùng cho interrupted evaluation cùng runtime và inputs, không dùng
kết quả cũ sau khi thay tools. Accepted artifacts read-only, không re-extraction.

Implementation [`3ac01c02ef1ba6d713bf67706ade436da3ebb97f`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/3ac01c02ef1ba6d713bf67706ade436da3ebb97f)
đã push trực tiếp main. [CI41373589020](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41373589020)
completed/SUCCESS đúng SHA; Python3.12 và Web smoke SUCCESS. Full unit regression
skipped theo focused policy. Checkpoint sau chỉ docs/planning `[skip ci]`,không gán
CI implementation cho SHA checkpoint. web/next-env.d.ts giữ nguyên ngoài commit.

Đây là retrieval/identity/provenance regression trên persisted BBS, chưa independent
gold hoặc full-PDF financial accuracy. Chưa executor, QA baseline hoặc Multi-Agent.
Không có P0/P1 mới trong phạm vi M4-02; giữ B10 scope/cross-document limitation.
Next action: Tech Lead independent review M4-02; chưa bắt đầu M4-03.
