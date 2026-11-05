# M7-02 — Report Outline Planner

Owner giao05/11/2026; baseline main/origin
`445733426514cc0d8c3ce535c8b8fa931e93702f` đã fetch/xác minh. M6 và M7-01 DONE.
Status **REVIEW**; implementation chưa commit, exact-SHA CI chờ push.

## Architecture và API

ReportOutlineRequest → scope/policy guard → VerifiedClaimLedger.find_claims →
typed classification/conflict checks → protected sections/slots → optional
SharedLLMGateway permutation → deterministic validator → GroundedReportOutline.
Không import calculator, canonical retrieval hoặc M5 execution vào planner.
Không sửa M6 persistence/policy hoặc QA behavior.

```python
from vietnamese_financial_multi_agent.outputs import ReportOutlinePlanner, ReportOutlineRequest

outline = ReportOutlinePlanner(ledger, gateway=shared_gateway).plan(
    ReportOutlineRequest(
        report_type="general_financial_analysis",
        company_id=company_id,
        document_id=document_id,
        snapshot_id=snapshot_id,
        period="2025",
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
Ngôn ngữ vi; model mặc định lấy DEFAULT_GEMINI_MODEL hiện hành.

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
context, citations, caveats, limitations và neutral suggested_role. Sections có
purpose cố định, order/status/missing_information. Overview liên kết sections thay
vì lặp financial slots. M7-03 đọc trực tiếp IR, có thể đối chiếu lại ledger IDs;
không được tính metrics hoặc sinh facts mới. Full proof histories không nằm trong IR.

## Selection, scope và caveats

Caller phải cung cấp đủ bốn identities; không chọn snapshot/period đầu tiên.
Filters AND theo exact period. `2025` và `2025-12-31` không tự ghép; vì vậy general
annual outline có thể partial dù ledger có B01 ở thời điểm cuối năm. Đây là giới
hạn MVP một period; không làm comparability approval mới. Accepted revenue_yoy có
operands hai kỳ trong cùng nguồn vẫn được dùng như một claim đã ACCEPT; planner
không dựng thêm so sánh. Cross-document/multi-year request giữ D03-B10 blocked.

Reuse `_assertion_signature`, `_segments`, claim_scope và citation/caveat projection
của M7-01, không tái dùng QA intent matcher. Group cùng typed target/kind trong
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

Proposal chỉ có ordered section IDs và slot IDs của từng section. Giữ scope đầu,
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

## Oracle, protocol và kết quả

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
| Synthetic engineering | 49 controls:47/48 initial; corrected fixture1/1 +scope guard1/1 PASS |
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

## Fresh Gemini: PARTIAL

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

## Mẫu outline thực tế BBS2025

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

## Root causes, fixes và limitations

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
gồm local web/next-env.d.ts; `M7-02-integrity-final/summary.json`. Ruff toàn repo,
format477files,planning/diff PASS. Oracle SHA256
`ef281feef9705ac086431ec2d1092bf805ac73b19445c304fb0948064e944cf5`.
Exact-SHA CI chờ implementation push; chưa gán local PASS cho CI.

Next action: Tech Lead review M7-02. Không tự bắt đầu M7-03.
