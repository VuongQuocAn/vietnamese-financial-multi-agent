# M6-04 — Financial Logic Critic

Status: **REVIEW**, chờ Tech Lead nghiệm thu. Owner giao04/11/2026, baseline main/origin
`94bf6988b87096260c7569c4054252ecff1398c6`; M6-01–03 DONE.
Implementation `4a09238d4d1bfe15b88e3090425e4319f947ab75` đã push trực tiếp main,
origin/main khớp; evaluation đã hoàn tất trong ngân sách.
[CI41751757736](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41751757736)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS;full regression SKIPPED.

## API và boundaries

`FinancialLogicCritic(gateway=None, model=None, max_semantic_calls=6).assess(batch,
validation, evidence)` trả `FinancialLogicCriticResult`. Không filesystem/PDF,
retrieval, calculator replay, SDK trực tiếp, retry/debate hay orchestration mới.
Chỉ sử dụng existing M6-02 checks và M6-03 source projections/support findings.
Typed JSON round-trip, không sửa inputs/catalog; không decisions hoặc ledger.

Mỗi `LogicFinding` giữ candidate/assertion ID, exact span, references/evidence IDs,
relevant validation checks và support findings, required/missing premises,
caveats và deterministic/Gemini provenance. Status consistent/inconsistent/
insufficient_context/not_applicable là reasoning annotation, không verification.
Không có claim-level verdict làm mất assertion đúng/sai trong cùng candidate.

## Stage A — deterministic

- Exact numeric restatements thuộc M6-02: logic `not_applicable`, không nhận là
  financial conclusion đúng. Numeric FAIL/UNDETERMINED không trở thành proven premise.
- Approved revenue_yoy: direction dùng dấu `trace.numerator` M4 đã được check,
  không thêm công thức. Tránh kết luận ổn định từ displayed0,00% đã làm tròn,
  hoặc đảo chiều khi denominator âm. Chỉ xác nhận câu bound đúng financial item.
- Financial sign với ngữ pháp hữu hạn và M5 cash-flow sign template: âm/dương
  chỉ mô tả giá trị; sign không tự chứng minh performance hoặc trend.
- CFO không phải lợi nhuận; doanh thu/lợi nhuận accrual không đồng nghĩa cash flow.
  Phát hiện sai implication không khẳng định doanh nghiệp thực tế lãi/lỗ ngược lại.
- Margin dương không chứng minh cải thiện; causal attribution thiếu evidence,
  solvency/leverage/earnings quality và investing-outflow overreach giữ thiếu premise.
  Không đặt industry/risk thresholds hoặc kết luận rằng missing cause chắc chắn sai.
- Split sentences và conjunction của các propositions tài chính hữu hạn; so sánh
  từng assertion với premises. Hai propositions cùng subject/context đối nghịch giữ
  contradiction; khi independent numeric direction đã chứng minh một phía thì giữ
  phía đó consistent và phía sai inconsistent.
- Context/scope mismatch và D03-B10 giữ insufficient_context, kể cả numeric span.
  Không suy scope từ2024 sang năm khác; original/recovery2022 không tự chọn/gộp.
  Approved same-filing YoY được dùng khi existing operands/context/lineage cho phép.

Ngữ pháp bounded, không phải general Vietnamese financial NLP. Negation,
hypothetical/quoted/khả năng có điều kiện chuyển sang semantic assessment nếu đủ
premises; không ép missing context thành inconsistent.

## Identity và upstream support

Bind toàn bộ VerificationInput bằng `verification_input_digest`, bind exact
ValidationResult (checks/status/conflicts) bằng `validation_result_digest`.
M6-03 outputs mới thêm hai optional digest fields; không sửa accepted artifacts cũ.
Legacy callers phải truyền `validated_batch`, `evidence_batch`, `evidence_validation`
là original paired inputs. Đây là caller attestation, không chữ ký xác thực artifacts.
Thiếu pairing hoặc stale/mismatched source/input/candidate/content/references/
conflicts/relevant findings trả structured consistency error, không gọi Gemini.

Numeric PASS chỉ chứng minh numeric premise tương ứng khi context/source/quality/
calculation checks đủ và có fully supported source assertion. Unsupported/partial
assertions không được dùng như proven premises; phần supported riêng vẫn dùng được.
Lỗi semantic M6-03 không xóa phần numeric đã supported; retrieval/identity failures
vẫn chặn. Conflict IDs, source-review/page-level/scope và global upstream missing/
stop/risk limitations được giữ. Một claim hỏng không làm mất claim còn lại.

## Stage B — bounded Gemini

Default `gemini-3.5-flash-lite` qua SharedLLMGateway; đổi model qua constructor.
Chỉ gọi cho semantic assertions Stage A chưa giải quyết, tối đa một call/candidate,
0–6 calls/instance gồm failure. Evaluator reserve disk slots toàn task, tối đa6
actual attempts kể cả interruptions/retests; không retry tự động.

Prompt chỉ có claim/assertions, verified-by-check numeric premises, support
findings, exact evidence projections/references và context/known limitations.
Không conversation history hoặc toàn PDF. Output Pydantic JSON extra=forbid chỉ có
IDs và finite reason/premise/limitation codes: không có fields để sinh facts,
values, formulas, scope overrides, decisions hoặc ledger entries.

Local validation kiểm candidate/assertion set, allowed evidence/premise IDs,
status/reason/missing consistency và minimum premises theo assertion. Confirmed
semantic result cần numeric check PASS và fully supported numeric source assertion;
required premises phải available. Unknown inference không thể đổi thành numeric-only
để vượt missing financial context. Chưa có typed causal/liquidity/earnings-quality
premises đầy đủ trong accepted inputs: giữ thiếu bằng chứng, không đoán.
Stage B không tự cấp comparison premise từ một revenue_yoy để chứng minh cải thiện
profitability/liquidity; approved same-filing direction do Stage A xử lý.
LLM không nhận deterministic findings vào editable assertion set.
Malformed/failed response giữ structured error và insufficient_context;
metadata model/provenance/usage/cost/latency được giữ riêng.

## Evaluation và oracle

Oracle tại `evaluation/m6-04-scenarios.json` đặt trước execution, dựa canonical
facts, approved M4 calculations và accepted gates; không gán labels theo output.
Saved source replays dùng exact M6-03 input/check/support triplets, không rerun
M6-02/03. Chỉ scenarios mới chạy upstream checks một lần cho input đã đổi.

```powershell
python scripts/evaluate_m6_04_financial_logic.py --output artifacts/evidence/M6-04-offline-new
python scripts/evaluate_m6_04_financial_logic.py --live --offline-evidence artifacts/evidence/M6-04-offline-final-v2 --output artifacts/evidence/M6-04-live-new
```

30 persisted-source renderings +21 saved M5/M6 batches (gồm empty/partial/conflict
controls) và20 controlled reasoning scenarios. BBS2021–2025/recovery2022 có nguồn
thật; renderings/mock generation/saved Gemini replay/synthetic interpretations tách
riêng, không giả nhận scenario là natural Gemini-generated claim.
Hai saved sign interpretations được đánh giá deterministic, còn numeric facts/metrics
không tự tạo financial reasoning để làm đẹp coverage.

Canonical CFO hiện có đều không âm. Control negative CFO→loss là counterfactual
sign injection trên CFO2025 dương, không phải BBS negative CFO thực tế. Investing
outflow control dùng canonical investing_cash_flow2025 âm thực sự. Negative YoY
dùng approved recovery2022 metric; margin/debt dùng saved2025 results7,21%/59,06%.

Initial run giữ nguyên tại `M6-04-offline-initial`: phát hiện tên metric “Tăng trưởng
doanh thu” bị đọc như conclusion “doanh thu tăng”; sửa logic numeric-only, không
đổi financial labels để khớp output. Hai context controls ban đầu oracle ghi một
finding thay vì hai spans; sửa cardinality thành cả numeric/conclusion insufficient,
giữ nguyên reasoning rationale/status. Saved oracle ban đầu còn trong initial run.
Lượt `M6-04-offline-final` đạt71/71; final-v2 kiểm thêm conjunction splitting và
M4 trace direction. Không sửa accepted M5/M6 hoặc canonical artifacts.

Final offline `artifacts/evidence/M6-04-offline-final-v2/summary.json`:71/71 cases,
98 assertion findings. Theo status: consistent6, inconsistent5,
insufficient_context15, not_applicable72. Trong đó93 deterministic và5 Gemini-mock
assessments, zero actual Gemini calls; không coi mock agreement là model accuracy.
30 persisted-source cases,13 saved BBS mock-generated M5 batches,6 saved synthetic
controls,1 saved Gemini-response replay,1 replay kèm synthetic control và20 new
reasoning controls (19 interpretations +1 counterfactual). Năm saved batches rỗng
giữ nguyên zero claims, không đưa vào số findings. Hai sign paraphrases đã lưu
(một M5 mock, một saved Gemini replay) có kết quả consistent; các assertions đã lưu
còn lại phần lớn chỉ là numeric assertions.

20/20 controls bao phủ positive margin→improvement, CFO→loss, debt→insolvency,
wrong/correct YoY direction, missing causal evidence, scope mismatch,
original/recovery mixing, numeric PASS overreach, mixed conjunction,
stale validation/evidence, numeric FAIL no-override, correct/wrong CFO sign,
investing outflow và4 semantic scenarios. Wrong implication/sign/direction bị phát
hiện; missing context không bị đổi thành financial falsity.

## Bounded live và root causes

Initial4 actual calls trên4 synthetic interpretations grounded canonical BBS,
không phải4 natural M5-generated claims: causal attribution, net inflow, net outflow,
missing comparison. Initial2/4 đạt oracle: sign-inflow consistent, comparison
insufficient. Causal call trả HTTP503/provider_unavailable, unknown usage;
sign-outflow trả premise_ids=[sign_context] ngoài allowed ID set và bị local reject,
giữ structured error/insufficient_context thay vì âm thầm chấp nhận premise mới.

Initial recorded tokens117.695 cho3 successful provider responses; usage của503
unknown, không coi missing usage là0 hoặc công bố total billing chính xác.
Root cause request projection chứa full repeated citation metadata ở các check:
causal/margin user payload124.685 ký tự. Đã rút thành numeric premise/check status,
source content và compact exact citation IDs; payload cùng case còn22.053 ký tự.
Prompt làm rõ premise IDs khác premise categories và sign restatement khác causal
attribution. Không sửa oracle hoặc nới local validator để nhận malformed response.

Post-prompt validation:28 logic tests PASS và4/4 semantic mock cases PASS tại
`M6-04-offline-post-prompt`, zero actual calls. Targeted retest chỉ causal và
sign-outflow, tối đa2 remaining attempts; không chạy fresh4/4 hoặc mở rộng ngân sách.
Targeted1/2 đạt oracle: sign-outflow inconsistent với exact numeric/support premise
IDs; causal vẫn HTTP503, không có valid Gemini assessment. Tổng6/6 authorized
actual calls đã dùng, gồm2provider failures và1locally rejected malformed output.
Không gọi thêm hoặc đổi provider/model trả phí. Accepted live semantic coverage là
3/4 unique scenarios sau targeted fix, không fresh4/4 và không coi error fallback
insufficient_context ở causal là correct semantic prediction. Current compact prompt
chỉ fresh live retest trên causal/sign-outflow, chưa fresh rerun inflow/comparison.

| Phase / scenario | Semantic outcome | Recorded tokens | Latency ms |
| --- | --- | ---: | ---: |
| Initial causal | HTTP503, chưa đánh giá | unknown | 3719,5 |
| Initial sign-inflow | consistent, đúng oracle | 24.665 | 10723,7 |
| Initial sign-outflow | malformed premise ID, bị reject | 24.662 | 4770,2 |
| Initial comparison | insufficient_context, đúng oracle | 68.368 | 6835,2 |
| Targeted causal | HTTP503, chưa đánh giá | unknown | 4656,8 |
| Targeted sign-outflow | inconsistent, đúng oracle | 5.147 | 19713,1 |

Recorded total122.842tokens cho4provider-success responses, gồm malformed response;
hai503 usage unknown nên tổng billing actual N/A. Requested model cả6 là
gemini-3.5-flash-lite, provider-reported model của4responses thành công cùng tên;
effective_model=null theo Gateway, cost unknown. Exact requests/responses/errors,
token/model/latency trace ở ignored `M6-04-live` và `M6-04-live-targeted`;
`M6-04-call-budget` giữ6 reserved attempts; `M6-04-live-review/summary.json` tổng hợp
coverage/tokens và bind hashes tới6 raw responses. Final targeted protected14.033 hashes
unchanged. Causal live coverage là phần còn thiếu do provider, ghi rõ để Tech Lead
review; không phải lý do tự vượt budget hoặc sửa oracle.

Một root cause offline khác: premise gate ban đầu chặn cả numeric premise fully
supported khi M6-03 semantic gateway unavailable. Đã tách semantic limitation khỏi
retrieval/identity failure: chỉ dùng phần numeric supported, không nâng unsupported
hoặc undetermined. Initial unit failures còn gồm fixture assumptions về frozen
ObservationIdentity/dataclass catalog, đã sửa fixture usage theo actual contracts.

## Engineering và bảo toàn inputs

155 focused/compatibility PASS gồm logic critic, M6-02/03, candidate contracts,
M4 calculator và M5 orchestrator. Sau direction/conjunction/global-caveat/prompt
changes:28 final logic PASS; một targeted test sau đó xác nhận malformed call vẫn
tiêu quota và không làm mất independent candidates. Một warning có sẵn từ test
M4 cố tình đưa invalid Decimal, không có runtime financial failure.
Final review phát hiện `b03.*` quá rộng cho semantic sign premise: cash balances
không phải net cash flow. Đã giới hạn vào operating/investing/financing/net_cash_flow;
29 final logic tests PASS, gồm balance-versus-flow control. Fix chỉ thu hẹp premise
availability; các BBS/live scenarios vẫn dùng đúng CFO nên không rerun dataset/Gemini.
Initial implementationf8d1770, final fix4a09238; chỉ dùng CI của final fix SHA.
Ruff lint/format, planning101 và diff check PASS; không full OCR/M1–M5 benchmark.
Protected hashes trước/sau mọi evaluation khớp; initial preflight13.077 files,
final-v2 kiểm13.674, post-prompt14.005; bao gồm raw/processed/accepted evidence/Web.
Implementation `4a09238d4d1bfe15b88e3090425e4319f947ab75` đã push main;
exact-SHA CI41751757736 completed/SUCCESS, đã kiểm run metadata và từng job/step:
Python3.12 focused tests/lint/format/planning, Web typecheck/lint/build/browser smoke
SUCCESS;full unit regression SKIPPED đúng workflow. Raw CI metadata ở ignored
`artifacts/evidence/M6-04-ci-final.json`. Checkpoint tiếp theo chỉ docs/planning
[skip ci], không gán CI implementation cho SHA checkpoint. Original preflight13.077 protected hashes đã đối
chiếu lại sau toàn bộ implementation/evaluation:unchanged. Staged scope/key-pattern
check PASS, không stage dataset/evaluation artifacts/secrets hoặc Web local.

## Giới hạn và nghiệm thu

Đây là source-bound reasoning evaluation, chưa independent human PDF gold hoặc
full verification accuracy. Nhiều persisted assertions chỉ là số liệu; positive
semantic coverage còn bounded sign paraphrase. Causal/industry/solvency conclusions
chưa có typed sufficient premises để xác nhận. Judge/ledger thuộc M6-05/M6-06,
claims vẫn pending/decision=null/financial_fact_verified=false.

Next action: Tech Lead review M6-04.
