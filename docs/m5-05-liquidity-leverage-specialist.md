# M5-05 — Liquidity and Leverage Specialist

Ngày02/11/2026; trạng thái REVIEW, chờ Tech Lead nghiệm thu. Baseline main/origin
`348528fc6e39356b9ac2706307e9ade7db5f12fc`. Implementation
`ebea73076975acdd331f22ce6122d0c0aa48625d` đã push trực tiếp main, remote khớp.
Không triển khai M5-06 hoặc M6.

## P1 correction — explicit reporting scope

Tech Lead phát hiện “giữ riêng bằng chứng” bị hiểu thành báo cáo riêng; M4
`understand()` còn có thể trả false ambiguity khi câu hỏi có cả “hợp nhất” và
“giữ riêng”. Fix dùng trực tiếp `_explicit_constraints()` của M5-02 cho scope và
scope ambiguity; M4 chỉ cung cấp period/formula parsing, không dùng scope gate.
Không sửa parser hoặc accepted financial semantics M4, không đổi M5-04/common.
Ba regression cases kiểm tra giữ riêng evidence, báo cáo riêng và báo cáo hợp nhất
kèm giữ riêng evidence; explicit scope chưa confirmed vẫn bị chặn, matching
confirmed scope qua được, yêu cầu thực sự cả hai scopes vẫn abstain.
43 targeted tests PASS (M5-05/M5-04 và Planner scope regression). Câu BBS2025
“Giải thích Debt-to-Assets BBS năm2025, giữ riêng bằng chứng nợ phải trả và tổng tài
sản” chạy Planner → Supervisor → Specialist: scope=None, completed,2 candidates
59,06%, exact accepted citations/calculation/lineage. Replay ba real M5-04 cases
R01/R05/R08 khớp outputs trước sửa, bỏ random IDs/correlation/timing.
Evidence mới: `artifacts/evidence/M5-05-scope-fix`;10 input/code/Web hashes unchanged.
Gateway dùng4 saved-response replays; **0 actual Gemini calls,0 OCR**, không fresh
benchmark hoặc chạy lại live6. Fix `3f7e1ce46a51db0648243d1c8776a661e693133f`
đã push main, remote khớp; [CI41469949667](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41469949667)
completed/SUCCESS đúng fix SHA: Python3.12/Web smoke SUCCESS, full regression
SKIPPED. Checkpoint sau chỉ docs/planning [skip ci], không gán CI fix cho SHA
checkpoint. CI41466737325 bên dưới thuộc implementation gốc. Status giữ REVIEW.

## Kiến trúc và audit M5-04

`LiquidityLeverageSpecialist` nhận `SupervisorResult`, chọn B01 evidence, gửi một
digest qua SharedLLMGateway rồi ràng buộc proposals thành candidate claims.
Gemini chọn chỉ tiêu/nhận định và viết diễn giải tiếng Việt; backend kiểm tra
identity, kỳ, nguồn, số liệu và accepted calculation trước khi tạo candidate.

Audit M5-04 xác nhận contracts, kiểm tra facts/citations/metric lineage, selection
và Gateway processing có thể dùng chung. Các phần này được chuyển sang
`src/agents/specialist_common.py` dưới dạng models và functions, không tạo base
agent, registry, reflection loop hoặc framework. Profitability giữ domain labels,
proposal schema, prompt, grammar và public API riêng. `ProfitabilityEvidence` và
`ProfitabilityCandidate` vẫn import được dưới tên cũ; default result version/role
của Profitability giữ nguyên. Common result bổ sung role/version cho specialist mới.

M5-05 giữ allowlist bốn canonical items đã xác nhận có dữ liệu thật:
`b01.total_assets`, `b01.total_liabilities`, `b01.total_equity`,
`b01.short_term_receivables`. B01 giữ nguyên kỳ `as_of` dạng ngày ISO, không chuyển
thành fiscal-year B02. Chỉ nhận `debt_to_assets` đã computed/approved từ Supervisor;
không chia lại operands, sửa M4 semantics hoặc tạo approval mới.

## Public API và bàn giao M6

```python
from vietnamese_financial_multi_agent.agents import LiquidityLeverageSpecialist

specialist = LiquidityLeverageSpecialist(gateway=gateway, model=model_identity)
result = specialist.analyze(question=question, supervisor_result=supervisor_result)
```

Default model là `gemini-3.5-flash-lite`; `ModelIdentity` vẫn cấu hình được.
Public exports gồm `SpecialistResult`, `SpecialistCandidate`, `SpecialistEvidence`,
`SpecialistTrace`. Result có role `liquidity_and_leverage`, question/upstream status,
evidence digest, candidates, missing evidence, risks/caveats, raw Gemini payload,
Gateway model/usage/cost/provenance và selection/grounding trace.

Candidate giữ document/snapshot/company/period, fact references, exact metric ID,
supporting evidence IDs, exact citations và nguyên `FinancialCalculationResponse`:
formula/version/digest/approval, operands, source reviews, closure và full lineage.
`status="candidate"`, `financial_fact_verified=False`; specialist không kiểm chứng
hoặc phê duyệt claim. M6 có thể deserialize typed result mà không mất provenance.

## Ngữ nghĩa và các gates

Facts/metric values được backend render chính xác; conflicting model text bị loại,
không tự sửa số Gemini. Interpretation phải là câu số học đầy đủ trong hai họ
diễn đạt quan hệ “100 đồng tổng tài sản ↔ accepted đồng nợ phải trả”. Cho phép
placeholder hoặc literal khớp giá trị; không cho thêm nguyên nhân, đánh giá cao/thấp,
an toàn, phá sản hoặc khả năng thanh toán. Tổng nợ phải trả không đồng nghĩa nợ vay
có lãi; Debt-to-Assets không chứng minh mất khả năng thanh toán.

Giữ fact quality/source review/citation binding, formula digest/approval và đủ hai
operands/lineage; kiểm thêm B01/as_of, roles liabilities/assets, cùng kỳ/unit/scale,
selected snapshot, explicit date và reporting scope. Conflicting variants không được
chọn tùy tiện. Partial chỉ giữ nhánh độc lập hợp lệ; blocked/failed không gọi Gemini
và không tạo financial claims. D03-B10, ambiguous snapshot và explicit scope chưa
confirmed tiếp tục chặn. Scope chưa xác nhận nhưng không được yêu cầu explicit vẫn
giữ caveats theo accepted M4 policy.

Current/Quick/Cash Ratio, Debt-to-Equity, Interest Coverage và Working Capital
không được tự tính. Unsupported request trả missing capability; mixed request vẫn
có thể giữ facts độc lập thực sự được hỏi. Mọi citations do backend lấy từ nguồn,
không tin citation Gemini tự sinh.

## Ba candidate BBS thật từ live

| Candidate content | Nguồn |
| --- | --- |
| Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. | BBS2025, PDF trang5, live L07/E001 |
| Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. | BBS2025, PDF trang6, live L07/E003 |
| Cứ 100 đồng tổng tài sản tại thời điểm báo cáo tương ứng khoảng 59,06 đồng nợ phải trả. | BBS2025, PDF trang5–6, live L01/E003 |

L07 còn tạo vốn chủ sở hữu108.940.121.207 VND tại2025-12-31, trang6.
L01 đồng thời tạo metric candidate59,06%, giữ metric ID
`derived_metric:366cf1c0be5e6cf89b71e4edc0e7b6fb1285ad4914b14e39f25938a2f7e9f730`,
snapshot `D-01/normalized-v2`, formula version `M4/formula-execution-v1`, digest
`396bcc315e2c625b650a46917d2e1e1ec2006b4cb4b68e8712387e8cd918838b`.
Full citations/selectors/lineage nằm trong local result artifacts, không nâng
page-level/uncertain provenance thành cell-level hoặc verified facts.

## Real BBS evaluation

Manifest: `evaluation/m5-05-scenarios.json`; evaluator:
`scripts/evaluate_m5_05_liquidity.py`. Reference độc lập từ persisted canonical facts
và accepted `M4-03-final/executions.json`, không từ Gemini hoặc specialist output.
Mỗi target được kiểm tra có đúng một persisted fact/accepted calculation trước khi
chạy. Original canonical2022 (`D-01/normalized-v2`) và recovery2022 được chọn bằng
snapshot ID tường minh, không gộp hai snapshots.

| Scenarios | Nội dung | Kết quả final |
| --- | --- | --- |
| L01–L03 | Debt-to-Assets2025/2023/2024 | 59,06% / 64,19% / 62,98%, đúng accepted M4 |
| L04–L06 | Assets2025, liabilities2023, equity2024 | Facts/citations đúng |
| L07 | Assets/liabilities/equity2025 | Ba candidates độc lập |
| L08 | Approved Debt-to-Assets recovery2022 | 68,26%, đúng snapshot/trace |
| L09 | Ý nghĩa100 đồng tài sản2025 | Supported interpretation |
| L10 | Partial, thiếu liabilities | Hai facts assets/equity, không ratio |
| L11 | Citation liabilities sai | Giữ assets, loại liabilities |
| L12 | Current Ratio/Quick Ratio | Abstained, unsupported capability |
| L13–L15 | D03-B10, explicit consolidated scope, snapshot ambiguity | Abstained |
| L16–L17 | Assets2021, short-term receivables2025 | Facts/citations đúng |
| L18 | Approved Debt-to-Assets original canonical2022 | 68,26%, selected snapshot đúng |
| L19 | Formula approval bị vô hiệu | Không metric claim |
| L20 | Liabilities có conflicting variant | Giữ assets, không chọn một liabilities |
| L21 | Thiếu assets | Không Debt-to-Assets claim |

L10/L11/L19/L20/L21 là **synthetic injected failure controls trên bản copy của real
BBS evidence**, không phải lỗi quan sát được trong persisted dataset. L13–L15 tái
dùng negative Supervisor traces đã lưu. Offline dùng mock Gemini trên real inputs;
không được coi đây là live model accuracy hoặc kiểm chứng toàn bộ PDF scan.

Final offline: **21/21 scenarios**,22/22 target claims;12 generated/3 partial/6
abstained. Grounding/numeric/citations22/22; full formula/operand/lineage10/10;
supported interpretations4/4; unsupported claims0/22; appropriate abstention6/6.

## Gemini initial và failures

Prompt `liquidity_leverage_v1`, temperature0, một call/analysis, không retry/reflection.
Sáu câu initial gồm L01/L02 approved ratios + interpretations, L07 multi-fact,
L04 fact/source explanation, L10 partial và L12 unsupported. **6/6 đúng**,10 candidate
claims; grounding/numeric/citations10/10, formula/operand/lineage4/4, supported
interpretations2/2, coverage10/10, unsupported claims0/10, appropriate abstention1/1.
Không targeted live retest; tổng **6 actual calls,9.879 tokens** (8.999 input/880 output).
Gateway latency median1,608 giây/max1,991 giây; analysis median1,856 giây/max2,298 giây.
Provider trả model/usage; monetary cost vẫn unknown, không suy giá.

Initial execution bị gián đoạn bởi lỗi scorer sau L01, dù raw Gemini result đã có
hai candidates đúng. Fix regex độc lập rồi chấm lại saved L01, không gọi lại Gemini;
sau đó chạy nốt năm câu initial. Aggregation dùng sáu actual outputs, không tính
saved replay như một call mới hoặc fresh benchmark. Runtime/common/prompt hashes
giống nhau giữa hai phần initial. Không có model interpretation failure trong sáu câu.

Các lỗi evaluator trước đó được giữ riêng: mock prose tiếng Việt lỗi encoding;
trace `S16_assets2021` thực tế chứa equity2021 nên đổi sang Supervisor query đúng;
token “original” lọc `original_extraction` trong khi selected canonical snapshot có
origin khác nên dùng câu hỏi chỉ định snapshot và context ID; thiếu dấu đóng regex
ở independent interpretation scorer. Sửa evaluator/manifest, không đổi accepted
M4/Planner semantics hoặc dựng số liệu. Initial offline có17 scored cases trước khi
dừng L18; không trình bày lần đó là21/21. Final dùng inputs đã lưu và tạo những
upstream cases còn thiếu/không đúng target.

Một lỗi ghi report cuối xảy ra sau khi21 scenarios và bounded regression đã PASS:
helper M5-04 đã ghi `regression-summary.json`, wrapper định ghi thêm fields vào cùng
file nên append-only writer từ chối. Fix ghi `compatibility-summary.json` riêng;
hai focused evaluator regressions kiểm tra scorer và không ghi đè evidence đều PASS.
Summary được materialize từ21 score files đã có, không chạy lại pipeline/live;
`completion.json` ghi rõ bước này. `input-origins.json` sửa bookkeeping mode cho
các upstream fallback được tạo mới; raw financial results/scores giữ nguyên.

## Validation và artifacts

217 targeted/bounded unit tests và2 evaluator regressions PASS, gồm18 focused
specialist mới và21 M5-04 focused; warning
hiện có ở negative invalid-Decimal calculator control. M5-04 real before/after:
13/13 exact outputs sau khi bỏ random IDs/correlation/timing; mọi financial content,
citations, calculations, caveats, raw mock proposals, statuses và trace giữ nguyên.
Không gọi lại M5-04 Gemini. Bounded M4/M5 regression kiểm accepted18 calculations,
29 retrieval queries,36 evidence pairs, QA36, M5-01 15 cases và D-06/D-07; giữ19
M5-03 traces và M5-02 accepted baseline, không tuyên bố là executions mới.

Local evidence dưới `artifacts/evidence/` (ignored):

- `M5-04-M5-05-before`, `M5-04-M5-05-after`: compatibility13 cases.
- `M5-05-offline-initial`: raw failure run và persisted upstream inputs.
- `M5-05-offline-final`: scorer interruption, giữ raw L01 output.
- `M5-05-offline-complete`: final21 cases, references và bounded regression.
- `M5-05-live-initial`: actual L01 request/response trước scorer fix.
- `M5-05-live-initial-L01-rescored`: saved replay, zero API calls.
- `M5-05-live-initial-part2`: năm actual initial calls còn lại.
- `M5-05-review-evidence`: aggregate six-call scores/usage, input hashes và issue notes.

3.818 protected hashes trước/sau unchanged, gồm PDFs, canonical facts, accepted
artifacts và Web local. Không OCR/extraction, sửa raw/processed hoặc leak key.
Ruff lint/format, planning checker và diff check PASS.
[CI41466737325](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41466737325)
completed/SUCCESS đúng implementation SHA; Python3.12/Web smoke SUCCESS, full unit
regression SKIPPED. Checkpoint sau chỉ docs/planning [skip ci], không gán CI này
cho SHA checkpoint. Next action: Tech Lead review M5-05; không tự DONE/M5-06.
