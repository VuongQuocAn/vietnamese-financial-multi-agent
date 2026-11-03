# M5-07 — Adaptive Routing Rules

Status: REVIEW; CI SUCCESS, chờ Tech Lead nghiệm thu. Baseline main/origin
`86a8cc5a0c9b76dead6eba9891be54ab79f8ba83`, Owner giao03/11/2026.
Phạm vi: quyết định routing, chưa thực thi Specialists/M5-08 hoặc verification/M6.

## Kiến trúc và public API

```python
from vietnamese_financial_multi_agent.agents import AdaptiveSpecialistRouter

decision = AdaptiveSpecialistRouter().route(
    question=question,
    planner_result=planner_result,
    supervisor_result=supervisor_result,
)
```

API thuần Python, có thể bọc thành graph node sau này. Không cần Gateway/catalog,
không gọi retrieval/calculator hoặc Specialist. Inputs read-only; output Pydantic
`RoutingDecision` round-trip JSON, version `adaptive_specialist_router_v1`.
Thiếu Planner/plan/Supervisor trả `incomplete`; Planner cần clarification được giữ
`clarification_required`; upstream blocked/failed không được bypass.

Các bước: kiểm question/plan bindings → xác định factual/metric requests → domain
match → dependency/risk/evidence gates → tìm tập Specialist nhỏ nhất → phân công
references một lần. Output giữ plan IDs/status, selected/skipped routes, covered/
uncovered requirements, citations, caveats, risk signals, stop reasons và trace.
Không chứa Gemini conversation/raw proposal hoặc financial values. Mọi kết quả
giữ `financial_fact_verified=False`.

## Policy ba Specialist

| Vai trò | Facts / approved metrics | Chọn khi |
| --- | --- | --- |
| Profitability | B02 revenue, cost of sales, gross profit, profit before/after tax; gross_margin, revenue_yoy | Có yêu cầu sinh lời/fact B02 phù hợp và evidence eligible |
| Liquidity & Leverage | B01 total assets/liabilities/equity, short-term receivables; debt_to_assets | Có yêu cầu trong đúng allowlist M5-05; không suy mọi B01 item đều được hỗ trợ |
| Cash Flow & Earnings Quality | B03 operating/investing/financing/net cash flow, opening/closing cash; B02 profit before/after tax | Có yêu cầu B03/B02 phù hợp và evidence eligible; registry không bảo đảm fact tồn tại |

Roles lấy từ `SPECIALIST_BOUNDARIES`; IDs lấy trực tiếp từ allowlists implemented
Specialists. Không thêm registry tài chính độc lập hoặc confidence score.
Exhaustive set cover chỉ xét ba vai trò, ưu tiên ít Specialist nhất. Tie-break
cố định theo domain, không theo thứ tự facts. Không chọn cả ba mặc định.

Profit đơn lẻ → Profitability. CFO + profit → Cash Flow bao phủ cả hai, mỗi fact
giữ citations riêng. CFO + yêu cầu phân tích khả năng sinh lời tường minh → có thể
chọn Cash Flow + Profitability. Khi revenue đã buộc chọn Profitability, profit được
phân công theo ưu tiên Cash Flow nếu cũng có CFO; mỗi requirement chỉ giao một lần.

Planner đưa operands vào `query.required_indicators`; Router dùng explicit fact
operations để phân biệt requests độc lập với inputs tính metric. Không biến yêu
cầu Debt-to-Assets thành workload Profitability hoặc các factual claims tự thêm.

## Evidence và risk gates

Reuse `specialist_common.select_evidence`, `_fact_error`, `_metric_error` qua helper
chung, cùng `_debt_semantics_error` của M5-05. Kiểm thêm requirement references,
resolved dependencies, document/snapshot/company, statement/period/unit và scope
constraints. Reporting scope dùng `_explicit_constraints` M5-02; từ “riêng” trong
“giữ nguồn riêng” không tự đồng nghĩa báo cáo riêng.

| Loại gate | Hành vi |
| --- | --- |
| Global | Planner/Supervisor không eligible, D03-B10/cross-document, required snapshot ambiguity, explicit global scope ambiguity: không route |
| Branch | Risk gắn requirement/step được truyền theo dependencies và citations/lineage của nhánh; các yêu cầu độc lập tiếp tục |
| Metric | Approval/lineage chặn metric tương ứng; không chặn factual request độc lập dù fact cũng là operand |
| Optional | Thiếu optional evidence ghi uncovered; không tự biến thành required/global blocker |
| Unsupported | Không tính công thức mới; ghi capability unsupported, vẫn cho facts độc lập nếu Planner giữ được yêu cầu đó |
| Caveat | Giữ usable_with_caveat, page provenance, source-review unverified, scope chưa explicit và upstream limitations |

`routed` cần bao phủ mọi required request; có nhánh chính thiếu/unsupported hoặc
upstream partial thì `partial`. `blocked`/`unsupported` không có selected roles.
Routing eligibility chưa phải grounding cuối cùng hoặc financial verification;
Specialists và M6 vẫn chịu trách nhiệm gates của mình.

## Reference scenarios và phương pháp

[Manifest](../evaluation/m5-07-scenarios.json): 42 cases, expected roles/status/reasons
định nghĩa trước run; 5 Profitability, 5 Liquidity, 5 Cash Flow, 6 multi/overlap,
21 negative/caveat controls. Có BBS2021–2025, original/recovery2022, saved M5-02
PlannerResults và M5-03 execution traces; reuse coverage/accepted artifacts M5-04–06.
Không lấy Router output làm reference.

Các cases không có saved trace dùng deterministic M5-02 materializer/M5-03 trên
persisted BBS thật. M03 fact+metric dùng proposal operations tường minh từ manifest:
alias baseline M5-02 bỏ factual operations khi có formula; không sửa Planner trong
task này. Đây là deterministic reference proposal, không phải Gemini accuracy.
Negative injections chỉ sửa bản sao inputs; origin/mode và mutations được ghi rõ.
N19 kiểm Planner giữ unsupported capability cùng independent fact; không công bố
alias baseline đã hiểu đúng mọi mixed unsupported question.

Evaluator chặn Gateway/Supervisor dispatch/Specialist analyze trong mỗi lần route,
đo latency riêng Router, kiểm input immutability và JSON round-trip; đảo thứ tự
facts/calculations/citations rồi so toàn bộ decision. Compatibility dùng saved
responses trong process, không Gemini API. Engineering/routing PASS không chứng
minh financial accuracy trên toàn PDF.

```powershell
.venv\Scripts\python.exe scripts/evaluate_m5_07_routing.py --output artifacts/evidence/M5-07-new --regressions
```

Output bắt buộc là thư mục M5-07 mới, không ghi đè artifacts cũ. Có thể dùng
`--reuse-inputs artifacts/evidence/M5-07-previous` để giữ inputs deterministic đã
lưu khi chỉ sửa policy/evaluator; reference proposal cần materialize lại nếu đổi.

## Routing decisions BBS

Final evidence: `artifacts/evidence/M5-07-final-v2/`, gồm frozen manifest, inputs,
42 typed decisions, rows, implementation hashes và before/after protected hashes.
Inputs positive là persisted hoặc deterministic trên accepted BBS; N01–N04,
N09–N10, N13–N16, N19–N21 là injected controls trên bản sao, không real source errors.

| Case | Yêu cầu / dữ liệu | Quyết định thực tế | Căn cứ |
| --- | --- | --- | --- |
| A01 | Gross Margin BBS2025, saved P05/S03 | Profitability, routed | Approved metric, exact references/citations/lineage |
| A02 | Revenue BBS2024, saved P02/S02 | Profitability, routed | Fact đúng period/document/snapshot |
| B01 | Total Assets BBS2025, saved P01/S01 | Liquidity, routed | B01 as_of date và citations đủ |
| B05 | Debt-to-Assets BBS2022 recovery | Liquidity, routed | Explicit recovery, approved formula và operands |
| C01 | CFO BBS2023, saved P03/S17 | Cash Flow, routed | Fact B03 fiscal_year có nguồn |
| M03 | Debt-to-Assets + CFO BBS2025 | Liquidity + Cash Flow, routed | Metric và factual workload độc lập |
| M04 | Revenue + liabilities + CFO BBS2025 | Cả ba, routed | Ba domain cần thiết, không evidence thừa trong assignment |
| M05 | CFO + profit BBS2025, saved P11/S07 | Chỉ Cash Flow, routed | Một role bao phủ cả hai, sources riêng |
| M06 | CFO + yêu cầu phân tích khả năng sinh lời BBS2025 | Profitability + Cash Flow, routed | Intent sinh lời tường minh tạo workload riêng |
| N01 | M04 nhưng CFO thiếu evidence, injected | Profitability + Liquidity, partial | missing_evidence chỉ gắn nhánh CFO |
| N05 | Current Ratio + CFO/Net Income | Không chọn, unsupported | Planner không có approved capability/plan |
| N07 | Assets BBS2022 chưa chọn snapshot | Không chọn, clarification_required | Không tự chọn original/recovery |
| N21 | A01 nhưng policy execution_approved=False, injected | Không chọn, blocked | Approval payload gate, không chỉ dựa risk label |

| Metric routing riêng | Final result |
| --- | --- |
| Routing accuracy (roles + status + reasons + caveats) | 42/42 = 100% |
| Specialist selection precision / recall | 46/46 / 46/46 = 100% / 100% |
| Multi-specialist coverage | 12/12 = 100% |
| Incorrect / unnecessary activation | 0 / 0 |
| Appropriate abstention/blocking | 10/10 = 100% |
| Partial routing correctness | 9/9 = 100% |
| Risk gate correctness trên negative group | 20/20 = 100% |
| Determinism, đảo bundle order | 42/42 = 100% |
| Routing latency, local single run | median2,085ms; max11,327ms |
| Gemini / Router tool / Specialist executions trong routing | 0 / 0 / 0 |

Đây là correctness trên scenario reference có chủ đích, chưa estimate khả năng
khái quát trên mọi câu hỏi hoặc corpus mới. Không dùng accuracy Specialists thay
cho routing accuracy. Latency đo riêng route, không gồm hydration/Planner/Supervisor.

## Root causes và targeted fixes

1. Shared year filter coi B01 ISO date khác năm: Router chọn evidence không lọc
   prose rồi kiểm typed selector/period cho từng requirement.
2. Query chứa metric operands không đồng nghĩa yêu cầu factual độc lập: dùng
   explicit operations; metric-only routes không có assigned factual workload.
3. Support dependency không được đi xuyên metric để chặn fact độc lập: giới hạn
   traversal citations/lineage, thêm regression fact+metric cùng operand.
4. Mixed deterministic reference proposal phải có prepare_bundle theo M5-02;
   đã bổ sung trước run đầy đủ. Initial run dừng sớm, không tính là41-case result.
5. Run đầy đủ đầu `M5-07-final`:36/41 khi chấm cả reasons, nhưng roles/status41/41.
   Ba reference reason strings không khớp nguồn Planner hiện tại: D03-B10 và
   explicit scope đã bị preflight chặn trước Supervisor, company reason là
   `company_required` (query_planner.py/contracts.py). Hai missing-B03 cases đã
   có RiskSignal `missing_evidence`, nhưng scorer chỉ đọc stop/trace prose.
   Sửa reference strings theo contract và thêm risk codes vào scorer; giữ nguyên
   mọi expected role/status. Giữ raw run và summary, không gán lại thành PASS.
6. Thêm N21 kiểm approval thật trong metric payload; Router kiểm approved policy,
   digest và approval reference cho mọi metric, vẫn reuse grounding helpers.
   Source-review unverified được giữ tường minh trong caveats.

## Compatibility, protected evidence và bàn giao

250 bounded tests PASS ở vòng implementation;4 final Router focused tests PASS
sau các sửa policy cuối. Ruff toàn repository417 files/planning101/diff PASS.
CI thêm Router tests vào focused offline list; không yêu cầu full regression.

Bounded real evidence tại `artifacts/evidence/M5-07-final/`:18/18 metrics accepted
exact và independent arithmetic;29 retrieval queries,36 cross-document undetermined
pairs/D03-B10,5 D07 scope views/D06 exact,QA36,15 M5-01 contract cases,19 M5-03 traces.
M5-02 offline18/18 và historical live/replay giữ nguyên, không rerun Gemini.
M5-04 offline13/13/live2/6+targeted4/4;M5-05 offline21/21/live6/6;
M5-06 offline28/28/live5/6+targeted2/2 là history, không benchmark mới.

Chín saved-response compatibility assertions khớp accepted outputs:
Profitability R01/R05/R08;Liquidity L01/L07/L10;Cash Flow C01/C09/C11.
Lưu ý helper M5-06 cũ ghi `exact=false` cho sáu cases khi không có before-directory;
nhánh đó vẫn assert equality với accepted saved result; đây là metadata chế độ so
sánh, không phải mismatch. Ba cash-flow assertions ghi exact=true tường minh.
Không sửa helper/accepted artifacts trong task này.

4.725 protected hashes before=after ở cả hai run, gồm PDFs/OCR/canonical/approved
financial evidence, mọi artifacts trước M5-07 và Web local. Final routing run không
chạy lại compatibility đã PASS vì Router/contracts mới không sửa modules cũ.
Implementation hashes Router/contracts/evaluator/manifest khớp final42 run.
Không đổi shared financial contracts hoặc formulas; claims chưa verified.
Implementation `c40947687e1e9e62a21a7179a11ed2ef13447dcc` đã push main,origin/main khớp.
[CI41556677681](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41556677681)
completed/SUCCESS đúng SHA; Python3.12/Web smoke SUCCESS,full regression SKIPPED.
Metadata jobs/steps tại `artifacts/evidence/M5-07-handoff/ci-exact-sha.json`. Proof local tại
`artifacts/evidence/M5-07-handoff/implementation-sha.json` xác nhận final routing
hashes khớp implementation. Checkpoint tiếp theo chỉ docs/planning [skip ci].
Next action: Tech Lead review M5-07; không tự DONE hoặc bắt đầu M5-08.
