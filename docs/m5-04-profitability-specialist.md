# M5-04 — Profitability Specialist

Status: REVIEW; baseline main `07a577f947f5956405524fbf9ce06d35a75f4a6d`.
Ngày thực hiện02/11/2026 (Asia/Bangkok). Chờ Tech Lead nghiệm thu; CI đang chờ push.

## Kiến trúc và API

`SupervisorResult → profitability digest → SharedLLMGateway/Gemini → backend
grounding → SpecialistResult`. Một module, không framework hoặc agent mới khác.
Tái sử dụng `SPECIALIST_BOUNDARIES`, M4 typed facts/calculations/citations, RiskSignal,
Gateway và credential resolver M4-05a. Model mặc định `gemini-3.5-flash-lite`;
constructor nhận ModelIdentity để đổi model. Một call mỗi analysis, không retry.

```python
from vietnamese_financial_multi_agent.agents import ProfitabilitySpecialist

specialist = ProfitabilitySpecialist(gateway=gateway)
result = specialist.analyze(question=question, supervisor_result=supervisor_result)
```

`SpecialistResult` giữ upstream status, candidate/evidence IDs, missing evidence,
risks/limitations, raw JSON proposal, trace chọn/lọc, model/provenance/usage/cost/
latency/errors. Reuse typed PlannerLLMMetadata vì cùng Gateway metadata contract.
`ProfitabilityCandidate` là contract M5 tạm, không thay CandidateClaim M6-01:
kind/content, company/document/snapshot/period, observation references và metric IDs,
citations, full FinancialCalculationResponse, caveats/missing information/status.
Full calculation giữ formula/version/digest/approval, exact operands và reviewed
lineage để M6 chuyển đổi không mất provenance. Không lưu chain-of-thought.
Mọi candidate/result có `financial_fact_verified=False`; không verified/accepted.

## Gemini và backend

Gemini chọn evidence phù hợp câu hỏi, tạo nhiều propositions và viết diễn giải
tiếng Việt. Digest tối đa24 evidence, chỉ gồm profitability facts/approved metrics,
nhãn/số/kỳ/unit/scale, operands/formula và caveats; không toàn catalog/PDF hoặc
toàn bộ source-review payload. Citations không nhận từ Gemini.

Backend đối chiếu từng fact với identity/quality/source review/citations gốc;
conflicting variants cùng context bị loại toàn bộ. Metric cần computed result,
closed eligible closure, complete lineage, formula digest/approval/version đúng,
exact operand observations/values/context/source-node bindings cùng filing và
matching period roles. Kiểm tra result với scaled result có trong trace M4;
không tự tính metric mới. Citation anchor ID tái dùng graph_id/source_key chính
thức; document/snapshot/page/provenance/source phải đúng bundle và fact sources.
Không suy eligibility toàn bundle từ upstream completed.

Facts và metric descriptions có thể để statement=null để backend render exact
Decimal tiếng Việt. Supported interpretations phải do Gemini viết và khớp ngữ pháp
ý nghĩa số học giới hạn: lợi nhuận gộp trên100 đồng doanh thu, hoặc biến động doanh
thu hai kỳ cùng filing. Chấp nhận placeholders hoặc literal numbers/periods khớp
chính xác accepted evidence; sau đó render số bằng evidence, không sửa số sai.
Ngoài ngữ pháp này bị loại, kể cả câu có số đúng nhưng tự thêm nguyên nhân hoặc
đánh giá cao/thấp/tốt/xấu/ngành. Đây là generation constraint trước M6, không là
claim verification độc lập. Giới hạn này có thể làm giảm coverage với paraphrase
khác; chưa hỗ trợ diễn giải tài chính mở hoặc quan hệ nhân quả.

Partial chỉ giữ nhánh đủ nguồn; missing/conflict nhánh khác được báo riêng.
Blocked/failed upstream không gọi Gateway, không financial claims. ROE/ROA/NPM/
Operating Margin chưa approved được ghi unsupported capability; không tính thay.
Question period ngoài evidence bị loại. D03-B10 giữ blocked. Optional missing
không chặn nhánh độc lập. Source limitations/scope unresolved và caveats M4 được
giữ nguyên, kể cả caveat lịch sử `formula_policy_not_approved` trong payload;
actual execution approval vẫn lấy từ trace M4 đã được chấp thuận, không sửa artifact.

## Đánh giá và reference độc lập

Manifest: `evaluation/m5-04-scenarios.json`,13 scenarios BBS2021–2025, original và
recovery2022. Typed input tái dùng `M5-03-verified/execution-*.json`; chỉ R07/R13
thực thi thêm Supervisor deterministic cho after-tax fact, không extraction mới.
Reference lấy persisted canonical facts và accepted18 M4 calculations; kiểm số
trong content, full trace/operands, context và exact citations từ canonical sources.
Gemini output không là ground truth. Coverage đo các targets trong manifest,
không tăng khi model nhắc thêm operands đã có nguồn.

```powershell
.venv\Scripts\python.exe scripts/evaluate_m5_04_profitability.py --output artifacts/evidence/M5-04-new
.venv\Scripts\python.exe scripts/evaluate_m5_04_profitability.py --output artifacts/evidence/M5-04-new-live --allow-live
```

Live mặc định chỉ6 case trong manifest; có thể chọn `--cases`, tối đa6 mỗi run.
`--replay-from` là offline replay riêng, không live accuracy. `--regressions`
chạy bounded M4/QA/M5-01, không chạy lại Gemini Planner/Supervisor benchmark.
Output folder mới bắt buộc, không ghi đè. Mỗi case lưu request/raw Gateway response,
candidate sau filtering, exclusions, token usage/latency và origin hash. Provider
error dừng phần còn lại; started attempt được ghi trước call. Artifacts ignored,
không commit raw/normalized data, source reviews hoặc key local.

## Initial failures và root causes

- Initial live6:2/6 đủ coverage;12/12 final candidates grounded/numeric/citation
  đúng,0 unsupported final claims; coverage7/11. R01/R03 viết literal numbers đúng
  nhưng backend ban đầu chỉ chấp nhận placeholders; R02 còn ghép hai động từ,
  bị loại đúng; R10 bỏ sót giá vốn độc lập khi nhánh doanh thu conflicted.
- Fix: grammar chấp nhận literal đúng exact evidence và canonical rendering;
  giữ full-match để loại số sai/diễn giải vượt nguồn; prompt có ví dụ câu hoàn chỉnh,
  một động từ và coverage các nhánh có evidence. Bổ sung focused regression cho
  correct/wrong literal, uppercase placeholder và exact citation anchor.
- Initial offline R08: harness chọn Gross Margin trong khi saved recovery trace
  là Revenue YoY. Sửa manifest/question theo metric thực có trong trace;
  targeted recovery retest1/1. Không sửa upstream hoặc accepted calculations.
- Initial failures/raw outputs giữ nguyên trong `M5-04-live-initial`,
  `M5-04-offline-initial`, `M5-04-offline-final`. Retest4 live có budget tối đa4
  calls cho R01/R02/R03/R10; không fresh rerun toàn6.

## Kết quả cuối và bàn giao

| Scenario | Target | Final offline với mock trên BBS thật |
| --- | --- | --- |
| R01 | Gross Margin2025 | generated,2 candidates |
| R02 | Gross Margin2023 | generated,2 |
| R03 | Revenue YoY2025 | generated,2 |
| R04 | Doanh thu + lợi nhuận gộp2024 | generated,2 |
| R05 | Doanh thu + giá vốn + lợi nhuận gộp2024 | generated,3 |
| R06 | Lợi nhuận trước thuế2025 | generated,1 |
| R07 | Lợi nhuận sau thuế2025 | generated,1 |
| R08 | Revenue YoY recovery2022 | generated,2;−14,32% |
| R09 | Partial/missing doanh thu | partial,2 nhánh độc lập |
| R10 | Partial/conflicted doanh thu | partial,2 nhánh độc lập |
| R11 | Cross-document2024/2025 | abstained,0;D03-B10 |
| R12 | ROE/Net Profit Margin | abstained,0;unsupported |
| R13 | Lợi nhuận sau thuế2021 | generated,1 |

Offline final `M5-04-offline-v2`:13/13,20 candidates,9 generated/2 partial/2 abstained.
Đây là real-data backend evaluation với mocked interpretation, không Gemini accuracy.

| Metric | Final offline13 | Initial live6 | Targeted live4 sau fix |
| --- | ---: | ---: | ---: |
| Scenarios đủ coverage và grounded | 13/13 | 2/6 | 4/4 |
| Candidate grounding | 20/20 | 12/12 | 13/13 |
| Numeric accuracy, gồm số trong câu | 20/20 | 12/12 | 13/13 |
| Citation correctness | 20/20 | 12/12 | 13/13 |
| Formula/operand correctness | 8/8 | 3/3 | 6/6 |
| Unsupported final claims | 0/20 | 0/12 | 0/13 |
| Appropriate abstention | 2/2 | 1/1 | N/A |
| Target claim coverage | 20/20 | 7/11 | 8/8 |
| Live API calls | 0 | 6 | 4 |
| Input/output/total tokens | N/A | 8.856/1.089/9.945 | 7.040/916/7.956 |
| Median/max latency mỗi analysis | 473/573ms | 2.153/2.579ms | 2.181/2.852ms |

Tổng10 live calls/17.901 tokens, không rotation/retry, không fresh6/6.
Targeted4/4 không thay initial2/6; không công bố là fresh accuracy6/6. Targeted run
chỉ R01/R02/R03/R10, có3 supported interpretations thật được giữ sau backend filter.
Không chạy replay để thay thế live. Final specialist source SHA256
`ce0aadd1edbd2522896cbfb7191e44adae718aabe0b0385ad959fc22061f5b2d`
khớp cả final offline-v2 và live-targeted-v2 implementation manifests.

### Ví dụ candidates từ Gemini live và BBS thật

Các observation dưới đây scope bởi document BBS2025
`sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`,
snapshot `D-01/normalized-v2`, company `vn-business-registration:0600312071`.
Observation local ID là document ID nối `/page/7/link/<n>`.

| Candidate | Fact/metric references | Citations gốc |
| --- | --- | --- |
| “Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.” | b02.net_revenue,link4 | PDF trang7,`/tables/0/cells/10`,11,13 và source header/context |
| “Biên lợi nhuận gộp kỳ 2025 đạt 7,21%.” | gross_margin;gross_profit link8=32.482.519.668 và revenue link4=450.474.531.227 | PDF trang7,cells20/21/23 và10/11/13, full lineage |
| “Trong kỳ 2025, với mỗi 100 đồng doanh thu thuần tạo ra 7,21 đồng lợi nhuận gộp.” | Cùng approved gross_margin và hai operands trên | Cùng exact Supervisor citations,không citations Gemini |

Metric ID:
`derived_metric:ccffa7fe4cda4d77bd4d96fdb3e57501394d372e0fe482e153d1603fb3c9617c`;
formula/version `gross_margin`/`M4/formula-execution-v1`, expression
`gross_profit / revenue`, Decimal34/output multiplier100/final quantum0,01.
Approval digest `f9fb82dfdd9330056e6eafb7fd1518de45ef8899d6d5727038ead52ecb4dc4f7`.
Provenance vẫn page-level/uncertain với source selectors, chưa cell-level verified.
Đây đều là candidates, không financial facts đã được M6 xác minh.

Multi-fact liveR05 còn tạo đủ doanh thu355.507.372.286,giá vốn319.074.961.905 và
lợi nhuận gộp36.432.410.381 VND ở filing2024,PDF trang9,links4/6/8. References
giữ document/snapshot riêng; Revenue YoY dùng cả hai kỳ trong chính filing2025.

### Negative controls, regressions và protected inputs

21 focused tests final PASS: hallucinated number/period/evidence ID/citation/schema,
causal/industry judgment, mismatched source/anchor/quality/duplicate/lineage/
operand/formula/result, partial/caveats, blocked zero-call, structured multi-fact,
unsupported formula/wrong question period, correct literal và uppercase placeholders.
199 bounded tests PASS trước focused fixes; các fixes chỉ trong specialist,
không đổi common modules. Một warning cũ từ intentional invalid-decimal control.

Bounded real regressions ở `M5-04-offline-final/regression-summary.json`:
18/18 accepted M4 calculations exact/independent arithmetic,29 queries,36 pairs
vẫn undetermined,QA36 exact,M5-01 15 exact,D-06/D-07 exact. M5-03 giữ19 traces
13completed/3partial/3blocked; tái sử dụng, không tính là19 executions mới.
M5-02 offline18/18,fresh4/6,raw5/6,replay6/6 giữ nguyên, không chạy lại Planner live.
3.379 protected hashes before=after ở final offline và targeted live,bao gồm PDFs,
canonical/source reviews/snapshots/previous artifacts và local Web file. Không
OCR/extraction/financial value/formula approval changes; không full regression.
Ruff files đã sửa/planning/diff PASS. Key và raw artifacts ignored,không tracked.

Implementation chưa commit; CI được kiểm sau push, không suy từ local PASS.

Next action: Tech Lead review M5-04; không tự DONE hoặc bắt đầu M5-05.
