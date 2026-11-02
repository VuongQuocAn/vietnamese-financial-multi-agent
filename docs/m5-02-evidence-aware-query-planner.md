# M5-02 — Evidence-Aware Query Planner

Trạng thái **REVIEW**, chưa nghiệm thu. Baseline `33a1f4e`; implementation chưa
commit tại lúc ghi báo cáo, CI chưa chạy. Không bắt đầu M5-03.

Planner nhận câu hỏi tiếng Việt, gọi Gemini một lần để đề xuất targets, nhu cầu
bằng chứng, M4 operations và dependencies. Backend resolve metadata/catalog rồi
materialize và gọi `validate_plan()`. Kết quả `planned` chỉ cho phép cân nhắc bắt
đầu execution ở task sau; mọi steps vẫn pending, requirements unresolved,
`financial_fact_verified=False`. Planner không chạy calculator hoặc tạo câu trả lời.

## API và phân chia trách nhiệm

`src/agents/query_planner.py` dùng trực tiếp M5-01 contracts, `TOOL_CONTRACTS`,
SnapshotCatalog, approved policies và SharedLLMGateway/Gemini Adapter hiện có.
Không framework/orchestration engine mới; không gọi single-target `understand()`
của M4 trước Gemini. `PlannerContext`, `PlannerProposal`, `PlannerOperation`,
`PlannerResult`, metadata và trace là typed models, JSON round-trip.

Gemini quyết định nhu cầu phân tích, canonical targets, formula candidates và
operations/dependencies. Prompt chứa item catalog, semantics/operands/guards của
policies, tools, specialist boundaries, snapshot/scope/D03-B10 restrictions.
Model không được xuất financial values, PDF citations hoặc document/snapshot IDs.
JSON mode qua Gateway; Pydantic kiểm proposal local, không gọi đây là provider
schema enforcement. Một call/request, model mặc định `gemini-3.5-flash-lite`,
temperature0, output≤3000 tokens, timeout60s; không retry/reflection/rotation.

Backend sở hữu document/year/period/snapshot resolution, approved metric binding,
operand expansion, formula/compatibility gates, citations bindings và final
validation. Facts độc lập không bị nối thành một chuỗi giả; bundle phụ thuộc các
outputs Gemini yêu cầu tổng hợp. Mỗi metric phải có lineage; mỗi direct fact phải
có sources. Unknown scope giữ nguyên; explicit scope phải qua production gate.
`usable_with_caveat` giữ original caveats. Không tự chọn latest/parent snapshot.

Chỉ ba formulas được tính theo existing policies. Capability khác vẫn có thể được
Gemini nhận diện và ghi `unsupported_capabilities`; không thay ROE bằng gross margin.
Proposal không là evidence hoặc approval. Specialist roles chỉ biểu thị boundary,
không khởi chạy agent. Không đổi accepted financial semantics M4/M5-01.

Backend còn chuẩn hóa route khi câu hỏi tường minh yêu cầu “kiểm tra nguồn/cách
tính” nhưng model ghi `calculated_metric`. Raw/validated proposal vẫn giữ nguyên;
trace ghi normalization và evaluator chấm riêng **raw proposal intent**. Đây là
quy tắc route nhỏ, không tạo targets/DAG thay Gemini.

```python
from vietnamese_financial_multi_agent.agents import EvidenceAwareQueryPlanner, PlannerContext

# catalog/documents/gateway do composition layer cung cấp từ persisted records.
planner = EvidenceAwareQueryPlanner(catalog=catalog, documents=documents, gateway=gateway)
result = planner.plan("Phân tích doanh thu và lợi nhuận gộp BBS năm 2025", context=PlannerContext())
payload = result.model_dump_json(indent=2)
assert result.financial_fact_verified is False
```

CLI local dùng cùng key resolver M4-05a, mặc định không gọi API:

```powershell
.venv/Scripts/python.exe scripts/plan_financial_query.py "Phân tích doanh thu và lợi nhuận gộp BBS 2025"
.venv/Scripts/python.exe scripts/plan_financial_query.py "Biên lợi nhuận gộp BBS 2025" --allow-live
```

Lệnh live demo tạo thêm một paid/quota request; không chạy thêm trong task này.
Default key resolver dùng `src/api/api_key/api_gemini.txt`, không log key.

## Hai EvidencePlan thực tế do Gemini tạo

JSON đầy đủ nằm local trong ignored `artifacts/evidence/M5-02-live-final/`;
không commit dataset, IDs nguồn hoặc financial artifacts. Hai ví dụ dưới giữ
nguyên step IDs, tools và dependencies từ output thật, lược document/snapshot IDs.

F03 — Gross Margin BBS2023: Gemini đề xuất calculation + lineage; backend mở rộng
operands `b02.gross_profit` và `b02.net_revenue`, cùng period2023. Sáu steps:

| Step | Thao tác | Prerequisites |
| --- | --- | --- |
| snapshot | resolve_snapshot | — |
| op_0_operand_0 | find_financial_facts: gross_profit | snapshot |
| op_0_operand_1 | find_financial_facts: net_revenue | snapshot |
| op_0_gate | check_compatibility: gross_margin | hai operands |
| op_0 | calculate_financial_metric: catalog metric_id | op_0_gate |
| op_1 | get_metric_evidence_lineage | op_0 |

`op_1` bind `metric_id` từ `op_0.metric_id`, tạo lineage/citations requirements;
formula và compatibility requirements phụ thuộc hai operands. Preflight
structurally_valid/execution_eligible, chưa thực thi phép tính.

F01 — BBS2024 doanh thu/giá vốn/lợi nhuận gộp: ba pairs fact→sources độc lập
`op_0→op_1`, `op_2→op_3`, `op_4→op_5`. Mỗi fact chỉ phụ thuộc `snapshot`;
sources bind `reference` từ `matches.0.reference` của đúng fact producer.
`op_6` prepare_bundle phụ thuộc cả sáu outputs; requirements gồm ba facts,
ba citations, một analysis_bundle và snapshot. Tám steps; validation valid,
scope không bị tự gán, source caveats giữ nguyên. Đây là multi-step Gemini thật
đạt acceptance trên persisted BBS và chỉ ra đúng M4 tools.

## Reference và cách chấm

Manifest có human-authored questions/targets/status/intent trước khi chạy model.
`reference_for()` không gọi Planner/parser/validate_plan: dùng approved policy
operands, persisted metric period bindings, canonical item catalog và filing
metadata. Kiểm existence/uniqueness facts nhưng không dùng output Planner làm gold.

Evidence precision/recall là micro-average trên signatures: fact(item,period),
formula/compatibility/metric/lineage/citations(formula), direct citations(item,period),
analysis_bundle. Snapshot identity/period được kiểm riêng. Formula operand source
citations bổ sung là optional hợp lệ theo chính policy operands; không bắt buộc
phải gọi sources riêng nếu metric lineage đã có citations. Extra irrelevant target
vẫn bị false positive. Recall chỉ dùng required signatures; precision tính cả
optional hợp lệ. `minimal_tools_exact`/`evidence_exact` giữ để thấy workflow dư.

Tool accuracy yêu cầu đủ mandatory tools, chỉ cho optional sources đúng operands.
Dependency score kiểm producers/consumers và calculation gate; M5-01 kiểm DAG,
bindings và schema. Constraint score kiểm đúng filing/snapshot/item periods.
Structural/dependency/eligibility denominator là số ca reference cần materialize,
gồm cả explicit-scope negative cần blocked plan. Ba offline/two live negatives
không có plan là N/A structural, không loại failures khỏi intent/status/evidence
recall. Không đánh financial answer accuracy vì chưa execution/answer generation.

## Kết quả thực nghiệm

Offline alias mode là engineering/catalog evaluation, không bằng chứng Gemini.
18 câu, đúng quota nhóm4fact/4metric/4multi/2evidence/4negative; B01/B02/B03,
BBS2021–2025 và recovery2022. Initial17/18: thiếu short alias lợi nhuận trước
thuế. Sau sửa, final18/18,14planned/2blocked/1clarification/1unsupported.

| Metric | Offline final | Fresh live gốc | Replay sau sửa backend |
| --- | --- | --- | --- |
| Overall đúng | 18/18 | 4/6 | 6/6 |
| Intent canonical | 18/18 | 5/6 | 6/6 |
| Raw Gemini proposal intent | N/A | 5/6 | 5/6 |
| Evidence precision | 74/74 | 29/29 | 29/29 |
| Evidence recall | 74/74 | 28/28 | 28/28 |
| Tool selection | 18/18 | 6/6 | 6/6 |
| Dependency validity | 15/15 | 4/4 | 4/4 |
| Structural validity | 15/15 | 4/4 | 4/4 |
| Execution eligibility | 14/15 | 3/4 | 4/4 |
| Negative disposition đúng | 4/4 | 2/2 | 2/2 |
| Filing/snapshot/period | 18/18 | 6/6 | 6/6 |

Offline median/max7.800/12.607ms; fresh live median/max9.636/14.326ms.
Đây là milliseconds dùng dấu chấm phân nhóm; tương ứng live9,64/14,33giây.
Replay median/max3.951/6.228ms không có provider latency, không so trực tiếp live.
Scope gate làm một offline plan không eligible là kết quả đúng, không lỗi.

Live dùng local key0, không rotation, đủ **14calls/59.428tokens** provider-reported:
52.710input +6.718output. Monetary cost unknown, không tự suy pricing. Cả14 provider
responses success; một harness failure sau response đã nhận được, không mất tokens.

| Run | Calls | Tokens | Kết quả và lỗi được giữ |
| --- | ---: | ---: | --- |
| Initial L01–L06 | 6 | 25.054 | L01 writer failure; raw L01/L02 sai multi intent, thiếu bundle. Initial strict2/6; rescore semantic4/6, giữ cả scores cũ |
| Targeted L01/L02 | 2 | 8.831 | 2/2, không dùng như final tổng quát |
| Fresh F01–F06 | 6 | 25.543 | 4/6: F02 scope parser; F04 raw intent |
| Replay toàn bộ F01–F06 | 0 | 0 mới | 6/6 canonical; raw model intent vẫn5/6, không phải live retest |

Initial strict reference coi operand sources ngoài minimal workflow là dư; semantic
rescore áp dụng optional alternatives từ approved policy cho **toàn bộ sáu ca**,
không thay targets/status/financial semantics. Raw original/scores/references giữ
nguyên. L01 raw response được recover bằng offline replay; không tính là API call
mới hoặc initial successful end-to-end plan. Initial semantic4/6 vẫn tính L01 fail.

Các root causes và sửa trong phạm vi task:

- P11: Planner alias thiếu cách gọi ngắn profit_before_tax; thêm question alias
  local và regression missing-evidence, không thay M4 canonical mapping.
- Initial harness: hàm `save()` bất biến bị gọi hai lần cùng tên với payload khác;
  tách attempt/gateway filenames. Original full response có trong gateway-responses,
  usage4.300tokens được tính đầy đủ.
- L01/L02: Gemini understanding không phân biệt nhiều targets với direct_fact;
  bổ sung intent semantics trong prompt, materializer guard và regression. Hai
  targeted model calls đã tạo đúng multi-step DAG, final F01/F02 raw cũng đúng.
- F02: backend lexical scope thấy chữ “riêng” trong “giữ riêng bằng chứng”; giới
  hạn scope marker vào ngữ cảnh báo cáo riêng/riêng lẻ. Raw Gemini scope vốn null.
  Replay giữ đúng ba indicators, sources, bundle; unknown reporting scope vẫn null.
- F04: Gemini raw intent calculated_metric cho yêu cầu kiểm tra nguồn/cách tính;
  targets, revenue_yoy2022/2021 recovery và operations vốn đúng. Backend chuẩn hóa
  route evidence rõ ràng, giữ raw proposal/trace; prompt được làm rõ. Chưa live
  retest prompt sau sửa này vì đã hết ngân sách; raw accuracy vẫn5/6.

Không còn known deterministic failure trong mẫu sau replay. Chưa chứng minh prompt
mới loại bỏ raw intent error của Gemini trên câu mới, chưa tổng quát paraphrases,
chưa hỗ trợ per-target periods hoặc nhiều filings execution. Không claim Multi-Agent
cải thiện financial answer accuracy.

## Gates, regression và bằng chứng

2022 không chọn snapshot → clarification, không chọn latest. ROE → unsupported.
Explicit consolidated2025 → blocked do scope source insufficient, không tự separate.
Cross2021/2025 → D03-B10 blocked, kể cả model đổi nhãn hoặc chia bước. Unknown scope
vẫn cho approved same-filing/direct facts với caveats. Không source approval mới.
Supplemental persisted check: YoY trong báo cáo2025 với operands2025/2024 cùng
filing vẫn planned; không nhầm hai operand periods thành hai documents.13 Planner
tests bao phủ gate này và yêu cầu persisted bindings đúng cả hai kỳ.

197 focused/regression tests PASS trước final scope/intent correction;13 Planner
tests PASS sau correction. Existing invalid_decimal negative control có một warning.
Ruff check/format toàn repo389files, planning101tasks và diff check PASS trước commit.
CI focused list bổ sung Planner tests, không đổi existing gates hoặc web smoke.

Bounded real regressions: M4-05 giữ36/36 dispositions,28answers/grounded citations;
M4-03 giữ18/18 accepted execution/trace/independent arithmetic; M4-02 giữ29queries;
36cross-document pairs vẫn undetermined; D-06 QA09/QA15, D-07 năm scope views và
partial-scope exact.139text/24tables/2.973anchors/18lineages giữ nguyên. M5-01 giữ
15cases=10valid/4blocked/1invalid. Không chạy lại accepted M4 live/OCR/extraction.

**2.701 protected SHA-256 hashes unchanged**, gồm baseline manifests và accepted
M5-01 artifacts, original facts/metrics/evidence và Web local. Plan runs không execute
tools;18 metric executions chỉ ở separate bounded regression, không tính là Planner
outputs. Dataset/keys/artifacts ignored; không stage Web local.

Các artifacts local (không track) đủ cả failures:

- `artifacts/evidence/M5-02-offline-initial` và `M5-02-offline-final`.
- `M5-02-live-initial`, `M5-02-live-initial-remaining`, `M5-02-live-targeted`.
- `M5-02-live-final`, `M5-02-replay-final`, `M5-02-audit/live-budget.json`.
- `M5-02-m4-regression` và `M5-02-contract-regression`.

Reproduce vào output directory mới, không overwrite accepted artifacts:

```powershell
.venv/Scripts/python.exe scripts/evaluate_m5_02_planner.py --output artifacts/evidence/M5-02-new-offline
.venv/Scripts/python.exe scripts/evaluate_m5_02_planner.py --replay-from artifacts/evidence/M5-02-live-final --manifest evaluation/m5-02-live-final-questions.json --output artifacts/evidence/M5-02-new-replay
```

Live evaluator cần `--allow-live`; task đã dùng hết14calls, không chạy thêm trong
phiên này. Latency includes catalog preflight; chưa tối ưu caching/performance.

So với M4-05, Planner lập được nhiều canonical targets cùng filing, nhiều loại
báo cáo trong một bundle và evidence DAG; baseline single-target từ chối các câu
đó. Chưa có Supervisor/execution hay bằng chứng answer accuracy tăng.

Next action: Tech Lead review M5-02 và các hạn chế raw Gemini; không tự DONE/M5-03.
