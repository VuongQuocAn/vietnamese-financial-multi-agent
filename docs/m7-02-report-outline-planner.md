# M7-02 — Report Outline Planner

Owner giao05/11/2026; baseline main/origin
`445733426514cc0d8c3ce535c8b8fa931e93702f` đã fetch/xác minh. M6 và M7-01 DONE.
Status **DONE**, Tech Lead APPROVED ngày05/11/2026,chấp nhận implementation
`eff170d406228181435b8d8b88a1c775db772b3a`. Targeted fix P1/P2 theo review05/11/2026;
baseline fix HEAD/origin `35ea6588dcda8dcaa4d7d97b3011e075939658c6` đã xác minh.
Runtime fix `f5c9971c112ebcd38017e9bdf987b0156d87af30` đã push;
[CI41957365549](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41957365549)
SUCCESS:784 focused tests,Python3.12 và Web smoke PASS. Final implementation
`eff170d406228181435b8d8b88a1c775db772b3a` đã push main;
[CI41958482836](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41958482836)
completed/SUCCESS đúng SHA,785 focused tests PASS, gồm51 cases trong planner test
module (50planner +1oracle-pin). Web smoke SKIPPED ở lượt verifier cuối; đã xác
minh src/Web/workflow không đổi từ runtimef5c9971 có Web smoke SUCCESS. Full unit
regression manual SKIPPED. Checkpoint sau chỉ docs/planning [skip ci].
Bằng chứng lần đầu được giữ để đối chiếu:
implementation `b5898cd29b81d9f67c96b778ccf81fcd8800e8b3` (core4c6a612 +scope guard).
[CI41954306492](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41954306492)
completed/SUCCESS đúng implementation SHA: Python3.12 và Web smoke SUCCESS,
full regression manual SKIPPED.783 focused tests PASS, gồm toàn bộ49 planner cases.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI cho checkpoint SHA.

## Architecture và API

ReportOutlineRequest → scope/policy guard → VerifiedClaimLedger.find_claims →
typed classification/conflict checks → protected sections/slots → optional
SharedLLMGateway permutation → deterministic validator → GroundedReportOutline.
Không import calculator, canonical retrieval hoặc M5 execution vào planner.
Không sửa M6 persistence/policy hoặc QA behavior.

```python
from vietnamese_financial_multi_agent.outputs import (
    ReportOutlinePlanner,
    ReportOutlineRequest,
    ReportPeriodContext,
)

outline = ReportOutlinePlanner(ledger, gateway=shared_gateway).plan(
    ReportOutlineRequest(
        report_type="general_financial_analysis",
        company_id=company_id,
        document_id=document_id,
        snapshot_id=snapshot_id,
        period="2025",
        period_context=ReportPeriodContext(period_end="2025-12-31"),
        allow_gateway=False,
    )
)
payload = outline.model_dump(mode="json")
```

`report_type`: general_financial_analysis, profitability, liquidity_and_leverage,
cash_flow_and_earnings_quality, focused_analysis. Caller chọn `requested_sections`
khi muốn thu hẹp/thay danh sách mặc định; focused_analysis cần danh sách cụ thể.
`title` là nhãn yêu cầu, không được render thành nhận định/objective. Tiêu đề output
luôn lấy từ catalog trung tính. Guard chặn một số yêu cầu ngoài policy phổ biến;
không có natural-language intent parser tổng quát. Fields có cấu trúc là nguồn
quyết định phạm vi và chủ đề; yêu cầu scope trong title cần binding rõ ràng.
Ngôn ngữ vi; model mặc định lấy DEFAULT_GEMINI_MODEL hiện hành. Ngày cuối kỳ trong
ví dụ là caller binding được khai báo rõ; planner không tự suy ngày31/12 từ năm.

## Taxonomy và IR cho M7-03

| section_type | Nội dung được phép |
| --- | --- |
| scope | Exact company/document/snapshot/period; requested và confirmed scope riêng |
| overview | Index `linked_section_ids` tới các mục có support; có thể giữ slot khi chỉ yêu cầu tổng quan |
| profitability | B02 catalog facts, gross_margin/revenue_yoy đã ACCEPT |
| financial_position | B01 catalog facts, debt_to_assets đã ACCEPT |
| cash_flow | B03 catalog facts và accepted interpretations tương ứng |
| verified_unclassified | Claim chưa có ánh xạ chủ đề an toàn |
| limitations | Toàn bộ caveats/limitations và phần chưa đủ evidence |

Metric phân loại từ formula_id trước, không từ operands. Debt-to-Assets không cấp
quyền kết luận khả năng thanh toán. Mixed/unknown category giữ unclassified.
ClaimKind fact/approved_metric/supported_interpretation giữ nguyên; vai trò trình
bày chỉ key_fact/approved_metric/verified_interpretation. Không tạo financial prose.

ReportClaimSlot giữ stable hash ID, mọi verified IDs, accepted content nguyên văn,
context, citations, caveats, limitations và neutral suggested_role. `period_role`
là exact_period hoặc closing_balance; native claim_context.period giữ nguyên.
Scope giữ period_context và included_periods để Writer không phải đoán kỳ nguồn.
Sections có
purpose cố định, order/status/missing_information. Overview liên kết sections thay
vì lặp financial slots. M7-03 đọc trực tiếp IR, có thể đối chiếu lại ledger IDs;
không được tính metrics hoặc sinh facts mới. Full proof histories không nằm trong IR.

## Selection, scope và caveats

Caller phải cung cấp đủ bốn identities; không chọn snapshot/period đầu tiên.
Request không có period_context giữ exact-period behavior và oracle cũ. Request
annual có ReportPeriodContext(fiscal_year, period_end) truy xuất hai exact periods
trong cùng company/document/snapshot. Chỉ B01 tại đúng period_end được bổ sung:
facts theo canonical item catalog B01/as_of; Debt-to-Assets theo typed trace operands
B01/as_of đúng ngày và source identities. B02/B03 tại ngày đó không được đổi thành
closing balance. Binding khác năm hoặc request as_of có annual context yêu cầu làm
rõ. Không tự chọn filing/snapshot hoặc ghép chuỗi nhiều năm; D03-B10 giữ nguyên.
Native periods, citations và caveats không bị đổi sang năm báo cáo. Accepted revenue_yoy có
operands hai kỳ trong cùng nguồn vẫn được dùng như một claim đã ACCEPT; planner
không dựng thêm so sánh. Cross-document/multi-year request giữ D03-B10 blocked.

Reuse `_assertion_signature`, `_segments`, claim_scope và citation/caveat projection
của M7-01, không tái dùng QA intent matcher. Group cùng typed target/kind/native period trong
nguồn đã bind; khác assertion signatures bị loại toàn nhóm, giữ lý do/conflict IDs.
Cùng semantics nhưng khác wording giữ slot riêng nguyên văn. Cùng content/context
thì union mọi IDs/citations/caveats/limitations, không chọn bản ít caveats hơn.

Scope chỉ confirmed khi accepted embedded resolution resolved/confirmed đúng nguồn.
Fact-only thiếu resolution vẫn unknown; yêu cầu consolidated/separate chưa xác nhận
sẽ clarification hoặc partial khi còn support khác. Scope top-level chỉ confirmed
khi mọi selected slot đồng nhất; scope riêng vẫn có trong từng slot. Nếu selected
targets có cả separate và consolidated đã confirmed, yêu cầu clarification trước
khi lập outline; không ghép hai phạm vi vào cùng một báo cáo.
Caveats từ decision/claim/supporting evidence/citation limitations và unknown-scope
note; limitations từ decision blockers/missing information. Giữ cả caveat codes lịch
sử khó đọc, không diễn giải chúng thành kết luận mới.

`ready` là đủ support cho các section được chọn ở mức cấu trúc. `partial` có mục
thiếu hoặc ambiguity/scope exclusions; `abstained` không có support; clarification
cần binding/giải quyết ambiguity; unsupported vượt policy. Không đồng nghĩa đủ dữ
liệu để kết luận mọi vấn đề trong tên nhóm tài chính. `omitted_sections` liệt kê
categories không có mục phân tích supported trong kết quả, kể cả placeholder
insufficient_evidence của requested category; Writer phải giữ placeholder là thiếu
bằng chứng. Thiếu claim trong ledger
không chứng minh PDF không có dữ liệu.

## Gemini, fallback và local validation

Proposal chỉ có section_index và slot_order là các chỉ số nguyên từ0 trong chính
section đó. Mapping ngược từ index sang protected section/slot deterministic;
opaque IDs chỉ giữ trong IR, không bắt model sao chép. Dynamic schema dùng const
cho từng section được chọn và enum cho chính inventory slots của section; không
gửi enum toàn catalog. Prompt có example hợp lệ theo schema. Giữ scope đầu,
limitations cuối. Title/purpose/content/context/citation/caveat không cho model sửa.
Một call/request, temperature0, output1600tokens, timeout45s, prompt≤24000bytes;
không full history, retry/key rotation hoặc chuyển API. Gateway metadata giữ model,
usage/cost/provenance/error đúng nguồn.

Validator dựng lại toàn bộ deterministic outline từ request và retrieved entries;
so mọi protected field và coverage/status, chỉ cho hoán vị sections/slots. Kiểm tra
verified ACCEPT/identity/context/citation boundary trước selection. Proposal sai
IDs, missing/duplicate/moved slots, extra prose/fields, invalid JSON hoặc provider
failure → fallback deterministic với nguyên metadata. Bản deterministic fail gate
không trả financial slots. Đây là local gate M7-02; chưa phải M7-05 Firewall.

## Oracle, protocol và kết quả trước targeted fix

`evaluation/m7-02-scenarios.json` chốt trước lần chạy planner: pin ledger SHA256,
58 accepted claim projections bằng content/citation digests, context, required
caveats/limitations; mỗi case có expected status/sections/IDs/omissions và forbidden
operations. Nhãn lấy từ original M6 ACCEPT và reviewed source item/formula mapping,
không từ planner output. Hai scenario configs M6-06/M7-01 dùng để audit protocol.

36 unique BBS cases: sáu contexts (2021–2025 + recovery2022), mỗi context general,
profitability, cash flow, leverage, missing-section và multi-section. Có6 general,
30 focused,13 partial và1 abstained (original2022 thiếu accepted CFO). General2025
có equivalent IDs khác caveats; 2024/2025 giữ supported interpretations. Thêm13
negative controls và15 Gateway controls; conflict injection là detached adversarial
source-selector mutation, không phải fact mới hoặc dữ liệu BBS thật.

Real repository hydrate/replay một lần mỗi session, sau đó read-only saved view dùng
public AND-query của repository. Không sửa M6 để tăng tốc. Tool sentinels giám sát
calculator/canonical retrieval/orchestrator; zero calls. Artifacts mới, không overwrite:

```powershell
.venv/Scripts/python.exe scripts/evaluate_m7_02_outline.py --mode all --output artifacts/evidence/M7-02-new
.venv/Scripts/python.exe scripts/evaluate_m7_02_outline.py --mode integrity --output artifacts/evidence/M7-02-integrity-new
```

Source/live session: local ignored `artifacts/evidence/M7-02-evaluation-final-v2/`.
Summary riêng `offline/summary.json`, `live/summary.json`, `preflight.json`.
Final offline sau scope guard: `artifacts/evidence/M7-02-scope-guard-final/`.

| Bằng chứng | Kết quả |
| --- | --- |
| Synthetic engineering | Local47/48 initial +corrected fixture1/1 +scope guard1/1; CI toàn bộ49 PASS trong783 focused tests |
| M4/M5/M6/QA compatibility | 327/327 PASS |
| Saved BBS oracle | 36/36 PASS;22 ready/13 partial/1 abstained |
| Negative/adversarial | 13/13 +15/15 PASS;14/14 deterministic fallback |
| Tổng fixed oracle | 64/64 status/coverage/omission/selection agreement |
| Section và claim precision/recall | 1.0/1.0 trên cases có support |
| Citation binding / required caveat retention | 100% /100% theo saved oracle |
| Unsupported claims/objectives, unverified leakage | 0/0/0 |
| Snapshot/scope violations, unauthorized calculations | 0/0 |
| Cold proof read | 35,426s cho58 entries (28 facts/28 metrics/2 interpretations); session fresh trước đó34,412s |
| Warm BBS deterministic planning | 1,989–23,542ms; all offline tối đa49,687ms |

Đây là saved-source oracle agreement và engineering; chưa independent financial
accuracy, full-PDF audit hoặc bằng chứng lợi ích Multi-Agent end-to-end.

## Fresh Gemini trước targeted fix: PARTIAL

Task budget đã dùng3/3, provider-reported `gemini-3.5-flash-lite`;0 provider errors.
Cả3 response JSON thành công nhưng structured proposal không hợp lệ. Model thêm
các enum catalog sections không nằm trong selected list; có opaque slot IDs bị
chép sai. Gate từ chối tất cả, fallback giữ đúng selection/citations/caveats và status.
Không retry để lấy kết quả đẹp, không tính fallback là fresh proposal success.

| Case | Input/output/total tokens | Proposal | Final outline | Latency |
| --- | --- | --- | --- | --- |
| general2025 | 1461/765/2226 | rejected → fallback | partial, oracle PASS | 3,540s |
| profit2025 | 1000/479/1479 | rejected → fallback | ready, oracle PASS | 2,565s |
| missing2025 | 637/313/950 | rejected → fallback | partial, oracle PASS | 2,028s |

Tổng4655 provider-reported tokens. Fresh organization acceptance0/3, fallback3/3.
Fresh chạy trước guard mixed confirmed scopes cuối cùng; guard giữ nguyên prompt
và ba requests thực tế không có mixed confirmed scopes. Không đổi prompt hoặc gọi
thêm sau fresh; không còn ngân sách call.

## Mẫu outline BBS2025 trước targeted fix

Nguồn document `sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`,
snapshot `D-01/normalized-v2`, period `2025`, reporting_scope unknown. Response đầy
đủ tại `offline/response-general-2025.json`:22 verified IDs,9 slots,58 unique caveats.

1. Thông tin và phạm vi: exact source bindings ở trên.
2. Tổng quan: linked_section_ids profitability/cash_flow; không summary prose.
3. Khả năng sinh lời:6 slots, accepted metrics/facts; ví dụ bindings dưới đây.
4. Tình hình tài chính và cơ cấu nợ: insufficient_evidence cho exact period2025.
5. Dòng tiền và chất lượng lợi nhuận:3 slots, gồm1 supported_interpretation.
6. Hạn chế: unknown scope, page-level provenance và mọi upstream caveat; missing
   `verified_claims:financial_position`. Status partial.

Ví dụ ba bindings nguyên nguồn trong outline (không chép financial values):

| Section/kind | Một selected verified ID trong slot | Citation |
| --- | --- | --- |
| profitability/approved_metric | verified:0c32cfcfc9f3b1c5e7de1966e2478f5a7f6bacb8b8bf6833ed40e70f109a267d | BBS2025 PDF page7, same document/snapshot |
| profitability/fact | verified:320b6eb2f9fced32bdec01f75fee42656ff0be015b7cb96dc0f72a612736f822 | BBS2025 PDF page7, same document/snapshot |
| cash_flow/supported_interpretation | verified:0095bde4055f1f3d0f750468a2e8b6d40c564b85cca602bf1ff15d0904bfcc86 | BBS2025 PDF page8, same document/snapshot |

Mỗi row là ví dụ một ID, slot tương đương giữ mọi IDs/caveats trong JSON. Source
citations đầy đủ còn anchor/source pointer/provenance; không nâng page-level thành
cell-level. M7-03 chỉ dùng accepted_content nguyên văn hoặc xử lý theo policy riêng.

## Root causes, fixes và limitations trước targeted fix

Fixture conflict đầu đổi numeric value nhưng chưa đồng bộ proof nên M6 reject đúng;
đã chuyển control sang detached source-selector injection và giữ admission nguyên.
Evaluation initial dừng ở selector field sai observation_id; sửa thành frozen
ObservationIdentity.model_copy(local_id), giữ partial artifacts; không đổi oracle.
Final audit bổ sung guard cross-target mixed confirmed scopes và targeted test;
hủy CI trung gian41953766131 để dành quota cho SHA cuối. Final replay64/64 giữ
nguyên frozen oracle. Lỗi fresh tổ chức đã được gate chặn/fallback;
chưa chứng minh model có thể tổ chức outline hợp lệ trên ba cases này.

Không phát hiện remaining P0/P1 trong bounded checks. P2: fresh structural acceptance
0/3, prompt/opaque IDs cần nghiên cứu tiếp; title parsing hữu hạn, exact single-period
scope bảo thủ, full proof cold read tốn tài nguyên, caveat codes kế thừa khó đọc.
Không M7-03/04/05, Web/API/export, independent PDF audit hoặc thay accepted artifacts.

Protected:14831 hashes mới +400 supplemental normalized/canonical/crop inputs đã
đối chiếu khớp accepted M7-01 baseline. Final integrity15231/15231 unchanged,
gồm local web/next-env.d.ts; `M7-02-integrity-scope-final/summary.json`. Ruff toàn repo,
format477files,planning/diff PASS. Oracle SHA256
`ef281feef9705ac086431ec2d1092bf805ac73b19445c304fb0948064e944cf5`.
Exact-SHA CI đã xác minh SUCCESS như trên; không chạy lại real evaluation/live
hoặc tests sau khi chỉ cập nhật checkpoint tài liệu.

## Kết quả targeted fix P1/P2

Giữ nguyên oracle cũ SHA256 ef281feef9705ac086431ec2d1092bf805ac73b19445c304fb0948064e944cf5
và toàn bộ artifacts cũ. Oracle mới `evaluation/m7-02-review-fix-scenarios.json`
pin lại original ledger/projections; labels chốt trước planner run từ accepted IDs,
typed B01/as_of trace và explicit caller period_end. Không sửa nhãn oracle cũ.
New oracle SHA256 `ec25110b8fc13eef86ac507c35cd98e53fd0f8c0f2dedac25193d8b938d5d11d`.

```powershell
.venv/Scripts/python.exe scripts/evaluate_m7_02_outline.py --review-fix --mode all --output artifacts/evidence/M7-02-review-fix-new
.venv/Scripts/python.exe scripts/evaluate_m7_02_outline.py --review-fix --mode integrity --output artifacts/evidence/M7-02-review-fix-integrity-new
```

Session `artifacts/evidence/M7-02-review-fix-evaluation/` hydrate proof một lần,
rồi replay legacy64 và new44 qua read-only view/public query. New44 gồm25 source-bound
BBS scenarios (có6 ngày cuối kỳ không có support),4 negative và15 index/proposal
controls. Kết quả64/64 cũ và44/44 mới PASS. Section/claim precision/recall1.0,
citations/caveats retained100%, mọi safety violations0. Cold65,338s, warm new BBS
2,598–47,534ms trong session chạy cùng compatibility tests; không kết luận tốc độ.

P1 sample `offline/response-annual-general-2025.json`: request period2025,
period_context fiscal_year/end2025-12-31; scope.included_periods=[2025,2025-12-31].
Outline **ready**,27 verified IDs/11slots/66caveats. Financial_position có2slots,
5IDs native2025-12-31, period_role=closing_balance:3fact IDs nợ phải trả (PDFpage6)
và2metric IDs Debt-to-Assets (PDFpages5/6). Ví dụ hai ID mới:
`verified:03854e8b6c52466e3a0a6ced4095851d03984b1d10903c66bd6a27ab4ad55b97`,
`verified:657e77e01c3034d428c99ca30fed734b75c50d2fa87e7c13bfd94c738b553569`.
Không đổi native periods thành2025 hoặc lấy B01 từ recovery/snapshot khác. Các
ngày cuối kỳ không khớp vẫn abstain; scope unknown và limitations giữ nguyên.

P2 thêm tối đa3 fresh calls theo quyền cấp lại của Owner trong phiên review,
budget riêng M7-02-review-fix-call-budget; budget/evidence3calls cũ giữ nguyên.

| Fresh case | Provider result | Proposal / final outline | Tokens đã báo |
| --- | --- | --- | --- |
| annual-general-2022 | HTTP503 | fallback / partial đúng oracle | unknown |
| annual-general-2025 | HTTP503 | fallback / ready đúng oracle | unknown |
| annual-profit-2025 | gemini-3.5-flash-lite | accepted / ready đúng oracle | 850input +64output =914 |

Fresh structural acceptance **1/1 response thành công**,1/3 attempted calls;
2/2 provider-error fallbacks đúng. LIVE PARTIAL do2 HTTP503; không có invalid
proposal ở response thành công, không retry/key rotation/thêm calls.914 là known
provider-reported tokens, hai calls lỗi không có usage. Chưa có fresh proposal
evidence cho general/partial; deterministic/adversarial cases đã PASS riêng.

50 planner tests local PASS, gồm typed annual/as_of mapping/read-only/native-period
tamper và finite-index-schema assertions trong Gateway controls.327 focused
compatibility regression PASS; Ruff/format477files PASS.15496 protected hashes unchanged (gồm oracle cũ,
accepted artifacts và Web local) tại M7-02-review-fix-integrity/summary.json.
Audit cuối phát hiện Git chuyển CRLF/LF của oracle JSON; pin cũ vẫn giữ nguyên.
Verifier chấp nhận duy nhất khác biệt line endings khi đối chiếu SHA, mọi byte khác
vẫn phải khớp. SHA oracle trên là byte hashes của local frozen artifacts trước
Git line-ending normalization. Targeted test1/1 PASS với LF checkout và mutation label bị reject;
không sửa label hoặc oracle file.51 cases trong planner test module (50planner +1pin).
Không chạy lại BBS/live sau thay đổi verifier vì runtime/request/proposals không đổi.

Fix xử lý root causes P1/P2, không phát hiện P0; còn giới hạn caller phải bind
period_end rõ ràng, conservative scope unknown và provider availability. Chưa
independent financial accuracy. Implementation SHA/CI mới đã xác minh như trên;
không gán CI implementation cho checkpoint docs tiếp theo.

Phiên nghiệm thu chỉ đồng bộ tài liệu/planning và chạy planning/diff checks;
không sửa runtime hoặc chạy lại tests/BBS/Gemini;giữ nguyên evidence và các giới hạn đã báo.
Next action: chờ nhiệm vụ mới từ Owner/Tech Lead. Không tự bắt đầu M7-03.
