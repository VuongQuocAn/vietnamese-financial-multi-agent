# M5-08 — Agent and Tool Orchestration

Status: REVIEW; chờ Tech Lead nghiệm thu. Claims là candidates,
`financial_fact_verified=False`; M6 mới quyết định verification.

Implementation [1868928](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/18689287aaecc1257762564a9693948b4b273b96) đã push trực tiếp main;
[CI41562965030](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41562965030)
completed/SUCCESS đúng implementation SHA: Python3.12 và Web smoke SUCCESS,
full regression thủ công SKIPPED. Checkpoint sau chỉ docs/planning [skip ci],
không gán CI cho checkpoint SHA.

## Public API và ranh giới

```python
from vietnamese_financial_multi_agent.agents import FinancialMultiAgentOrchestrator

orchestrator = FinancialMultiAgentOrchestrator(
    planner=planner,
    supervisor=supervisor,
    router=router,
    specialists={
        "profitability": profitability,
        "liquidity_and_leverage": liquidity,
        "cash_flow_and_earnings_quality": cash_flow,
    },
)
result = orchestrator.run(question=question, context=planner_context)
```

Caller hydrate catalog, cấu hình SharedLLMGateway/model và cung cấp PlannerContext.
Không UI dependency, không conversation sharing; từng agent có prompt/Gateway call riêng.
Supervisor dùng shared M4 tools một lượt; không extraction/OCR hoặc calculation mới
ở aggregator. Python tuần tự, không LangGraph, retry/reflection hoặc synthesis LLM.

## Stages và stop conditions

Planning một lần; planned mới gọi Supervisor. clarification_required/unsupported/
blocked dừng; failed có structured error. Supervisor blocked/failed dừng trước Router;
partial vẫn được route. Router một lần, giữ toàn quyền chọn roles và yêu cầu.
Chỉ routes execution_eligible trong selected_roles được thực thi, theo thứ tự routes,
mỗi role tối đa một lần, tối đa ba roles. Projection failure chặn đúng nhánh trước LLM.
Specialist failure giữ error/trace và không retry; branches khác tiếp tục.

Trace gồm planning, supervisor, routing, context_projection, specialist_execution,
candidate_aggregation, finalization; stages chưa chạy có skipped/reason. Chỉ lưu
outcomes, timings và provenance; không chain-of-thought. Giữ nguyên global/branch
gates của Supervisor/Router, D03-B10, snapshot/scope, formula/quality/lineage/units.

SpecialistExecution ghi covered/missing_requirement_ids theo Router targets;
raw SpecialistResult/status được giữ nguyên. LLM missing_information là annotations,
giữ verbatim trên SpecialistResult và global caveats, không tự thành required evidence.
Full target coverage với annotations về công việc ngoài yêu cầu có thể completed;
grounding exclusions vẫn partial. Khi có missing coverage/routing partial/failed branch/conflicts,
pipeline là partial. Không có candidates: failed nếu lỗi kỹ thuật, abstained nếu
Specialists không có claim hợp lệ; không tự tạo fake claims hoặc fake plan.

## Evidence projection và root cause

`build_specialist_context` trả typed EvidenceProjection chứa bản sao SupervisorResult.
Seed từ covered_requirement_ids và missing requirements liên quan; lấy dependency
closure và citations/lineage descendants, không lấy analysis bundle của cả pipeline.
Giữ assigned facts qua exact references và assigned metric qua metric identity/formula;
metric giữ nguyên calculation, approval/version/digest, operands, canonical facts,
source reviews, quality, citations và lineage. Thiếu operand/citation gây projection
failure. Không sửa SupervisorResult gốc.

Giữ original question, explicit constraints, company/document/snapshot/period,
currency/unit/scale, caveats và risk liên quan. Chỉ thu hẹp query targets/selectors
theo Router. Plan DAG được deserialize/revalidate. Full step/tool responses giữ ở
OrchestrationResult một lần; projection giữ source_step_ids để tra ngược, tránh đưa
global prepare_bundle response vào Specialist. Snapshot metric inventories và source
review bindings cũng được giới hạn theo closure.

Root cause ở shared selector M5-04/05/06: trước M5-08 mọi fact trong bundle đều
được xem là candidate evidence. Metric operands bắt buộc có mặt để validate metric,
nhưng không mặc nhiên là factual workloads. Thêm optional
`ExecutionEvidenceBundle.claim_fact_references`: None giữ legacy behavior; projection
đặt danh sách exact assigned facts, kể cả danh sách rỗng cho metric-only. Common
selector vẫn kiểm tra metric bằng toàn bộ operands nhưng chỉ đưa assigned facts
vào digest sinh claim. Không đổi financial values hoặc formulas.

Live initial còn phát hiện Router coi explicit operand retrieval operations là
independent workloads ngay cả khi typed intent là calculated_metric/evidence_explanation.
Sửa `_targets` để metric-only intent không tạo factual workloads; multi_step_analysis
vẫn giữ facts độc lập. Planner/Supervisor execution không bị viết lại. Regression test
giữ mixed fact+metric và kiểm explicit operand operations. 42 accepted routing decisions
phải khớp khi replay sau fix.

Giữ full original question trong mỗi call từng khiến Gemini báo thiếu dữ liệu thuộc
role khác hoặc so sánh/phân tích sâu không được giao. `with_assignment` chỉ áp dụng
cho projected calls, thêm assigned facts/formulas và phạm vi trách nhiệm vào prompt;
standalone legacy prompt giữ nguyên. Orchestrator dùng actual assigned coverage để
phân biệt thiếu evidence thực sự với model annotations; không xóa annotations/trace.

Orchestrator kiểm tra supporting evidence của Specialist thuộc assignment; malformed
result chặn nhánh và không để aggregation làm mất branches khác. Requested factual/
metric coverage được kiểm tra riêng với supported interpretations; thiếu coverage
không được báo completed.

## Aggregation và provenance

AggregatedCandidate giữ original content/kind/context, fact/metric references,
citations, calculation, caveats, resolved supporting evidence và origins gồm role,
execution_id, original candidate_id/content. Local E001 IDs chỉ có nghĩa trong từng
SpecialistResult; origins giữ mapping riêng. Không dùng random candidate IDs để dedup.

Dedup deterministic theo exact rendered proposition, semantic target/context và
provenance; giữ mọi origin/caveat. Khác period/snapshot/evidence identity không gộp.
Nếu cùng company/target/period nhưng giá trị hoặc context khác: giữ hai candidates,
gắn CandidateConflict/candidate_ids, không chọn winner hoặc nâng verified. Đây là
conflict flag cơ học, chưa phải M6 financial adjudication. Supported interpretations
khác nội dung là propositions riêng; không cố semantic NLP dedup.

## Evidence, evaluation và giới hạn

Traces offline đại diện ở `artifacts/evidence/M5-08-offline-v3/`:

| Trace | Kết quả và activation |
| --- | --- |
| result-E02.json | Gross Margin2025: chỉ Profitability; 7,21%, trang7; hai supporting operands, không operand claims |
| result-E10.json | Revenue + Liabilities + CFO2025: ba roles, mỗi role nhận đúng một target |
| result-E11.json | CFO + Profit Before Tax2025: chỉ Cash Flow, hai factual candidates, nguồn B03/B02 riêng |
| result-E13.json | Synthetic missing CFO: Profitability + Liquidity tiếp tục, partial và missing CFO |
| result-E23.json | Synthetic Liquidity transport failure: Profitability/Cash Flow giữ hai candidates, không retry |

Ví dụ E10: doanh thu thuần2025=450.474.531.227VND (trang7), tổng nợ phải
trả31/12/2025=157.146.559.558VND (trang6), CFO2025=14.319.681.754VND (trang8).
Cùng filing/snapshot BBS2025; citations giữ source keys, anchor IDs và original
provenance level. Debt-to-Assets E09=59,06%, citations trang5–6; giữ formula
approval/digest, liabilities/assets operands và complete lineage. Đây là
persisted-source candidates, chưa độc lập xác minh financial facts.

Offline initial có 34/35 cases đạt; E31 lỗi mock proposal (evidence_needs khai metric/
lineage trong khi chỉ có facts). Harness ban đầu còn có strict Decimal deserialization,
append-only writer dùng nhầm cho mutable ledger, và PowerShell encoding; giữ các
directories initial/v2/v3, không sửa artifacts cũ. Sửa encoding và chạy riêng E31/E32/
E36; E31 lộ reference kỳ vọng partial không phù hợp preflight: chỉ tiêu net_cash_flow2025
không có canonical fact nên Planner phải blocked/no_matching_fact trước Supervisor.
Giữ blocker đó, sửa reference theo contract; case partial dùng controlled missing CFO
sau Supervisor, không tự bypass Planner để tạo partial.

Eight representative reruns sau runtime fixes: `M5-08-offline-final`, 8/8; bao gồm
single/multi/partial/failure, natural missing fact và Debt-to-Assets2025. Final offline
coverage hợp nhất 36 cases từ v3, corrected-UTF8 supplement và final reruns; không gọi
lại toàn bộ cases đã PASS. Source map/metrics lưu ở `M5-08-review`.

| Offline metric | Evidence hợp nhất |
| --- | ---: |
| E2E expected scenario behavior / routing / activation | 36/36 mỗi mục |
| Evidence isolation | 37/37 projected executions |
| Actual Specialist invocations / extra activations | 37 / 0 |
| Assigned target coverage | 25/25 cases có factual/metric targets |
| Source grounding và citations | 38/38 candidates không bị synthetic corruption |
| Formula/operand/lineage integrity | 6/6 metric projections |
| Partial recovery / failure isolation | 6/6 / 2/2 cases |
| Dedup và conflict controls | 2/2; một giá trị cố ý sai được giữ và gắn conflict, không winner |
| Appropriate abstention / projection rejection | 9/9 / 2/2 cases |
| Actual Gemini calls offline | 0 |

Synthetic conflicting candidate không nằm trong38/38 numeric-grounding denominator;
đó là giá trị cố ý tăng1, được giữ cho M6 với conflict flag. Scorer initial đánh giá
expected conflict behavior cho case này, không coi injected value là financial gold.
Offline combined latency median11,36s/max26,61s là các executions từ nhiều phase;
không phải fresh36-case performance benchmark. Manifest37 entries gồm36 offline và
một live-only controlled partial case.

| Live phase | Scenario result | Actual calls | Actual tokens |
| --- | ---: | ---: | ---: |
| Fresh full-pipeline initial: E02/E10/E11/E37 | 1/4 | 11 | 29.472 |
| Targeted partial-live: E02/E10, saved Planner response | 2/2 | 4 | 6.411 |
| Tổng actual | Không gộp thành fresh 4/4 | 15 | 35.883 |

Initial routing/activation/grounding/citations đều4/4, target coverage3/4. E02 có
operand claims ngoài metric-only workload; E10/E11 partial do annotations ngoài
assignment. Cả bốn initial runs thực sự đi từ question qua Gemini Planner, Supervisor,
Router và Specialists đến candidates. E37 là fresh run với synthetic missing CFO,
không phải observed natural source failure. Targeted dùng Gemini cho một Profitability
và ba Specialists, replay Planner qua Gateway và rematerialize/execute plan; **partial-live**,
không fresh benchmark. Raw initial requests/responses/results còn nguyên. Provider-reported
model là `gemini-3.5-flash-lite`; không retry, không OCR, không chạy benchmark Gemini cũ.

Saved-response replay sau fixes: E11 completed, E37 partial, 2/2 PASS, zero actual
calls ở `M5-08-live-saved-replay`; đây là replay, không fresh Gemini results.

Live initial latency median17,48s/max26,61s; targeted median19,25s/max22,40s. Median
stage initial/targeted: Planner6,713/4,181s (targeted replay); Supervisor7,300/12,072s;
Router0,049/0,082s; projection0,203/0,253s; Specialists1,922/2,651s;
aggregation0,006/0,011s. Đây là local wall time, không performance ablation; không tính
catalog hydration/constructor. Gemini cost chưa provider-priced; không suy giá tiền từ tokens.
Manifest `evaluation/m5-08-scenarios.json` quy định expected roles/status/targets
trước execution. Dùng BBS2021–2025/recovery2022 persisted, accepted M4 calculations,
reconstructed citations từ canonical sources, không lấy Gemini làm financial gold.
Mock Gateway chỉ kiểm orchestration/grounding; saved response replay kiểm compatibility;
injected negative controls được gắn nhãn riêng. Không suy thành financial accuracy
toàn PDF hoặc Specialist/Gemini quality mới khi chỉ dùng mock.

Offline command:

```powershell
python scripts/evaluate_m5_08_orchestration.py --output artifacts/evidence/M5-08-offline-new
```

Live dùng `--allow-live`, Gemini3.5 Flash Lite qua SharedLLMGateway, credential resolver
local hiện có; tối đa12 initial+4 targeted actual calls toàn các M5-08 run directories.
Attempt và ledger ghi trước transport, không retry; targeted không công bố là fresh
benchmark. Requests/responses, projection/routing/results/candidates, tokens/model
identity và stage/total latency được lưu local ignored. Token tổng là phần provider
thực sự báo; unknown usage được đếm riêng, không gán zero cost.

339 bounded M4/M5 tests PASS trước live fixes;85 focused tests PASS sau fixes, gồm14
orchestration controls và Router regression. Bounded real regression giữ18 approved
metrics/29 queries/QA36/15 M5-01 cases/19 Supervisor traces; M5-02 offline18/18 và
prior Gemini evidence giữ nguyên, không rerun benchmark. Sau shared fixes,9 accepted
Specialist outputs replay exact và42/42 accepted routing decisions exact;
5.030 protected hashes unchanged (gồm Web local). Ruff424/planning101/diff PASS; exact-SHA CI SUCCESS như trên. Artifacts/traces/dataset/key không stage/commit.

Bounded regression gồm accepted M4/M5 inputs và representative saved-output replay;
không chạy lại Gemini benchmark cũ. Source-review unverified/unknown scope/page-level
provenance còn là caveats, grounded candidate không đồng nghĩa financial fact verified.

Next action: Tech Lead review M5-08; không bắt đầu M6.
