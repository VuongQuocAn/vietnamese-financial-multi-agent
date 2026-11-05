# QA-Q01 — Quick QA Execution & Root-Cause Diagnosis

Ngày 05/11/2026 (Asia/Bangkok). **REVIEW — chờ Tech Lead**, không phải M8,
benchmark chính thức hoặc nghiệm thu chất lượng tài chính toàn hệ thống.
[Task](../planning/tasks/QA/QA-Q01.md), [QA-only runner](../scripts/run_qa_q01.py).

## A. Executive Summary

Đã chạy **10/10 câu qua M7 Composer → Citation Renderer → Information Firewall**
bằng public APIs và repository thật, không fake transport hoặc warm ledger view.
Đã gọi M5 Orchestrator thật **4/4 câu được chọn, một lần/câu**: ba câu dừng ở
Planner do HTTP 503; Q07 có response Gemini thành công nhưng Planner phân loại
unsupported. **0/4 hoàn tất downstream, 0 Specialist và 0 M4 tool calls fresh**.
Không được diễn giải bốn attempts thành bốn successful multi-agent runs.

Đã đọc trực quan nguồn cho **10/10 case**: chín case có reference số liệu hoặc
premises phân tích độc lập; Q09 chỉ xác minh các operands liên quan, không áp đặt
công thức quick ratio chưa được duyệt. BBS2025 trang PDF 5–8 cung cấp số liệu;
trang 4/9 cung cấp context; BBS2024 trang 9 xác minh năm 2024 độc lập.

| Đánh giá nội dung M7 | Số câu | IDs |
| --- | ---: | --- |
| CORRECT | 2 | Q04, Q05 |
| INCORRECT | 0 | Không phát hiện trong phần đã phát hành |
| PARTIALLY_CORRECT | 4 | Q02, Q03, Q06, Q08 |
| EXPECTED_ABSTENTION_OR_CLARIFICATION | 4 | Q01, Q07, Q09, Q10 |
| INSUFFICIENT_EVIDENCE | 0 | Không dùng nhãn này thay execution failure |
| NOT_EXECUTED | 0 | Riêng M7; M5 downstream 4/4 không chạy |
| NOT_INDEPENDENTLY_VERIFIED | 0 | Không có numeric quick-ratio assertion để chấm |

Đây là completeness/correctness của output so với câu hỏi và phạm vi cho phép,
không phải accuracy 100%. Bốn abstentions không được tính là bốn đáp án số đúng.
M5 Q03/Q06/Q08: financial verdict **NOT_EXECUTED**; Q07: không có financial answer,
**INSUFFICIENT_EVIDENCE** để đánh giá chất lượng phân tích. Chỉ kiểm được refusal.

**Findings: 0 P0, 3 P1, 3 P2.** P1 gồm mất yêu cầu/không nhận diện đủ câu hỏi ở
M7, Planner M5 từ chối Q07 trước routing và availability chặn ba attempts.
Hai P1 sau có giới hạn bằng chứng về nguyên nhân sâu xa; không quy lỗi Router.
P2 gồm ledger coverage, chi phí đọc repository và presentation nhiều lặp/caveat.
Không thấy số liệu sai được phát hành; khả năng trả lời đầy đủ và chứng minh lợi
ích phối hợp agents trên bốn câu fresh vẫn hạn chế.

## B. Architecture & Execution Paths

**M5:** persisted catalog → EvidenceAwareQueryPlanner/Gateway → typed EvidencePlan
→ RiskAwareSupervisor/M4 tools → AdaptiveSpecialistRouter → context projection
→ tối đa ba Specialists/Gateway → aggregate_candidates → unverified candidates.
Runner dùng `setup` của evaluation cũ chỉ để hydrate persisted facts, graph,
scopes, policies và evidence; không dùng reference proposals, expected answers,
mock tools, injection hoặc scorer. Catalog có 1.177 facts, 18 metrics, năm documents.

**M7:** original VietnameseQARequest + exact company/document/snapshot →
VietnameseQAComposer/ledger retrieval → protected segments → CitationRenderer →
InformationFirewall.evaluate_qa → validated_output. `allow_gateway=False`, zero
M7 external calls; model ordering là optional và không giúp mở rộng financial prose.

M7 không gọi M5, không tạo missing claims, không gọi M4 calculator hoặc fresh M6
critics. Ledger cũ gồm 58 entries, 27 thuộc document BBS2025; 19 unique IDs được
chọn trong run, gồm 10 fact entries và 9 metric entries, **không interpretation**.
Repository thật deserialize và validate/replay **saved proof** ở cold load; đây
là kiểm integrity của saved authority, không phải fresh PDF verification/critic run.
M5 candidates lần này không được admit hoặc đưa vào M7.

| Dữ liệu trace | Có sẵn / loại evidence | Giới hạn của run này |
| --- | --- | --- |
| Orchestrator trace, usage, stage_latency_ms, latency_ms | ACTUAL_EXECUTION, đủ bốn results | Sau Planner đều skipped |
| Planner raw_proposal, query, trace, error/provenance | ACTUAL_EXECUTION | Ba responses lỗi không có token usage |
| routing_decision | Null ở bốn fresh results | Không có lựa chọn role thực tế |
| specialist_executions/projections/aggregation | Empty ở fresh results | Không suy Selected/Executed từ hypothesis |
| Supervisor step_results/tool_trace/bound_request/response | Contracts có đủ | Fresh Supervisor không được gọi |
| M6 decision/proof history, calculation operands | SAVED_TRACE + EVIDENCE_LINEAGE | Không chứng minh tools vừa chạy |
| M7 request/plan/segments/IDs/metadata/rendered bindings/firewall checks | ACTUAL_EXECUTION | Không có per-function internal latency ngoài ba public stages |
| Remaining quota, actual billed cost, provider outage cause | NOT_AVAILABLE | Không suy HTTP503 là hết quota; không có HTTP429 |

Mỗi M7 case lưu tách `m7-Qxx-composer.json`, `m7-Qxx-rendered.json`,
`m7-Qxx-firewall.json`, `m7-Qxx-final.txt` dưới `artifacts/evidence/QA-Q01/`.
Final text chỉ lấy `validated_output.rendered_text`, hoặc safe message khi chưa
release. Q07 **CLARIFICATION_REQUIRED**, không lấy unreleased Composer text làm final.

## C. QA Results Overview

Các actual answer dưới đây là excerpt nội dung được phát hành; caveats/references
nguyên văn ở `m7-Qxx-final.txt`. Không thay pipeline output bằng independent reference.

| ID | M7 status / firewall | Actual financial answer hoặc safe message | Assessment / finding |
| --- | --- | --- | --- |
| Q01 | abstained / ALLOW | Chưa có đủ claim đã xác minh cho yêu cầu này trong ledger. | Expected abstention; PDF có 266.086.680.765 VND, ledger thiếu direct fact; F04 |
| Q02 | partial / ALLOW_WITH_CAVEAT | Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. | Partial; thiếu LNST 7.249.557.946 VND; F01/F04 |
| Q03 | partial / ALLOW_WITH_CAVEAT | Biên lợi nhuận gộp kỳ 2025 đạt 7,21%. / … là 7,21%. | Partial; không nêu công thức/operands; F01/F06 |
| Q04 | answered / ALLOW_WITH_CAVEAT | Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%. | Correct; operands/trang 5–6 khớp |
| Q05 | answered / ALLOW_WITH_CAVEAT | Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 14.319.681.754 VND. | Correct; hai câu tương đương, F06 presentation |
| Q06 | partial / ALLOW_WITH_CAVEAT | Biên gộp 7,21% (hai câu); nợ phải trả/tổng tài sản 59,06%. | Partial; không diễn giải đầy đủ; F01 |
| Q07 | clarification_required / CLARIFICATION_REQUIRED | Cần xác định rõ yêu cầu, tài liệu, snapshot, kỳ hoặc phạm vi báo cáo trước khi tiếp tục. | Expected clarification trong M7 bounded API; M5 refused, F02 |
| Q08 | partial / ALLOW_WITH_CAVEAT | Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. | Partial; CFO có ledger nhưng cả mệnh đề bị unsupported; không kết luận earnings quality, F01 |
| Q09 | unsupported / ALLOW | Yêu cầu vượt quá khả năng QA đã được hỗ trợ. | Expected unsupported_formula; không tự tính quick ratio |
| Q10 | unsupported / ALLOW | Yêu cầu vượt quá khả năng QA đã được hỗ trợ. | Expected D03-B10 restriction; không runtime failure |

### Independent reference từ PDF

Số trang là **PDF 1-based**, khác printed page: BBS2025 PDF5/6/7/8 tương ứng
printed4/5/6/7; BBS2024 PDF9 là printed6. Các bảng ghi VND, scale=1.
B01 cột **31/12/2025**; B02/B03 cột **Năm 2025**, không lấy cột 2024/01-01.
Thuyết minh PDF9 xác nhận niên độ 01/01–31/12. Đơn vị báo cáo là Công ty CP
Vicem Bao bì Bút Sơn, mã đăng ký 0600312071. Những trang đã đọc chưa xác lập nhãn
formal riêng/hợp nhất; giữ scope unknown, không tự nâng thành consolidated/separate.

| Case | PDF/trang, bảng/mã chỉ tiêu | Giá trị gốc đọc trực quan | Independent value / status |
| --- | --- | --- | --- |
| Q01 | BBS2025/5, B01/270 Tổng cộng tài sản | 266.086.680.765 | 266086680765 VND; verified |
| Q02 | BBS2025/7, B02/10 doanh thu thuần; /60 LNST | 450.474.531.227; 7.249.557.946 | Hai facts verified |
| Q03 | BBS2025/7, B02/20 lợi nhuận gộp; /10 doanh thu thuần | 32.482.519.668 / 450.474.531.227 | ×100 = 7,210733885337…%; 7,21% |
| Q04 | BBS2025/6 B01/300 nợ phải trả; /5 B01/270 tài sản | 157.146.559.558 / 266.086.680.765 | ×100 = 59,058408750939…%; 59,06% |
| Q05 | BBS2025/8, B03/20 Lưu chuyển tiền thuần từ HĐKD | 14.319.681.754 | Positive CFO; verified |
| Q06 | BBS2025/5–7, các operands Q03/Q04 | Cùng bốn giá trị trên | Hai ratios verified; diễn giải phải có giới hạn |
| Q07 | BBS2025/5–8, Q01–Q05 | LNST dương, CFO dương, debt/assets59,06%, gross margin7,21% | Premises verified; không suy nguyên nhân hoặc ngưỡng tốt/xấu |
| Q08 | BBS2025/7–8, doanh thu/LNST/CFO | 450.474.531.227; 7.249.557.946; 14.319.681.754 | Premises verified; revenue+CFO chưa đủ khẳng định earnings quality tốt |
| Q09 | BBS2025/5 B01/100 tài sản NH, /140 tồn kho; /6 /310 nợ NH | 203.054.141.595; 50.788.605.600; 157.146.559.558 | Operands verified; metric không assert vì formula variants/policy chưa duyệt |
| Q10 | BBS2024/9 B02/20 và /10; BBS2025/7 cùng chỉ tiêu | 36.432.410.381 / 355.507.372.286; operands2025 ở Q03 | 10,248004182510…% → 7,210733885337…%; giảm 3,037270297172… điểm %, làm tròn3,04 |

Q10 kiểm chéo cột 2024 ở BBS2025 trang7: cả hai operands khớp BBS2024 trang9.
Không dùng sự khớp này để bypass D03-B10. Suy luận độc lập chỉ là lợi nhuận gộp
trên mỗi đồng doanh thu giảm, chưa đủ để xác định nguyên nhân.

Đầu vào đọc trực quan lưu `independent-reference-input.json`; phép tính Decimal
precision40 lưu `independent-calculations.json`. Formula trace cũ dùng precision34,
ROUND_HALF_EVEN, ×100, quantum0.01, round cuối; independent reference dùng
ROUND_HALF_UP ở bước display, kết quả giống hệt do không gặp tie. Mọi numerator/
denominator đúng công ty, filing, kỳ và VND/scale1; scope formal vẫn unknown.
Kiểm thêm doanh thu trừ giá vốn417.992.011.559 = lợi nhuận gộp32.482.519.668.

## D. Detailed Case Reports

### Q01

**Original:** Tổng tài sản của BBS năm 2025 là bao nhiêu?

Actual final: “Chưa có đủ claim đã xác minh cho yêu cầu này trong ledger.”
Kèm yêu cầu chưa đáp ứng r1 và cảnh báo thiếu ledger không có nghĩa PDF không có.
Mode ACTUAL_EXECUTION/M7 deterministic, `abstained`, ALLOW, 0 IDs/0 citations.
PDF2025/5 B01/270 đọc được **266.086.680.765 VND tại31/12/2025**. Parser nhận
đúng `b01.total_assets`, reason `no_verified_claim`.

Saved debt/assets claim có asset operand đúng nhưng không có **standalone fact
ACCEPT** cho assets trong ledger. M7 không được chuyển operand thành admitted fact.
Assessment EXPECTED_ABSTENTION_OR_CLARIFICATION; F04/P2 coverage, không lỗi số.
Nguyên văn `m7-Q01-final.txt`; request/composer/rendered/firewall cùng prefix.

### Q02

**Original:** Doanh thu thuần và lợi nhuận sau thuế của BBS năm 2025 là bao nhiêu?

Actual excerpt: “Kỳ 2025 — Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.”
“Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.”
ACTUAL_EXECUTION/M7 deterministic; partial, ALLOW_WITH_CAVEAT; 5 IDs hợp thành
1 segment, 10 reference selectors đều PDF2025/7. PDF xác minh doanh thu đó và
**LNST7.249.557.946 VND**, mã60; không nhầm lợi nhuận trước thuế9.113.447.433.

Clause LNST bị `ambiguous/specify_catalog_target`; catalog/ledger hiện không có
direct net-profit target/claim. Đổi alias đơn thuần chưa giải quyết thiếu admission.
PARTIALLY_CORRECT, F01/P1 understanding và F04/P2 coverage; không báo sai LNST.
Final đầy đủ `m7-Q02-final.txt`, gồm caveats/provenance gốc.

### Q03

**Original:** Biên lợi nhuận gộp của BBS năm 2025 là bao nhiêu? Hãy nêu công thức và các số liệu sử dụng.

Actual: “Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 đạt 7,21%.” và “… là 7,21%.”
Kèm partial/r2 chưa đáp ứng. ACTUAL_EXECUTION/M7; 7 IDs, 2 segments,
13 selectors PDF2025/7, ALLOW_WITH_CAVEAT. PDF operands32.482.519.668 và
450.474.531.227 cho7,21%; saved calculation dùng gross_profit/revenue ×100,
operands/period/rounding đúng. Chỉ có **lineage**, không fresh calculator call.

Không có công thức hoặc operand values trong final. Requirement đầu chứa “công
thức” nhưng chỉ thành metric-value; tách “và” làm “các số liệu sử dụng” thành
unsupported_question. Earliest gap là requirement decomposition, trước selection/
rendering; verified calculation metadata có sẵn nhưng bounded renderer không
render explanation mới. PARTIALLY_CORRECT, F01/P1; hai câu gần trùng F06/P2.

M5 ACTUAL_EXECUTION một attempt, Planner HTTP503/failed1,737s, 0 tools/roles/
candidates. Financial M5 NOT_EXECUTED, F03/P1. Files `m7-Q03-final.txt`,
`m5-Q03-result.json`, `m5-Q03-call01-response.json`.

### Q04

**Original:** Tỷ lệ nợ phải trả trên tổng tài sản của BBS năm 2025 là bao nhiêu?

Actual: “Kỳ 2025-12-31 — Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31
là 59,06%.” ACTUAL_EXECUTION/M7, answered/ALLOW_WITH_CAVEAT; 2 equivalent
metric IDs, 1 segment, 19 selectors PDF5–6. PDF operands157.146.559.558 và
266.086.680.765, cùng31/12/2025, cho59,05840875…%; đúng approved formula.
Tổng nợ phải trả **không đồng nghĩa nợ vay có lãi**; output giữ caveat này.
CORRECT; không phát hiện arithmetic/period/citation fault. Final `m7-Q04-final.txt`.

### Q05

**Original:** Dòng tiền thuần từ hoạt động kinh doanh của BBS năm 2025 là bao nhiêu?

Actual hai đoạn: “Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là
14.319.681.754 VND.” và cùng ý bỏ từ “của”. ACTUAL_EXECUTION/M7,
answered/ALLOW_WITH_CAVEAT; 5 IDs, 2 segments, 11 selectors PDF2025/8.
Đọc đúng B03 dòng20, cột2025, dương; không lấy27.996.254.086 của2024 hoặc
dòng50 lưu chuyển tiền thuần trong năm1.208.501.810. CORRECT về tài chính,
F06/P2 presentation. Final `m7-Q05-final.txt`.

### Q06

**Original:** Biên lợi nhuận gộp và tỷ lệ nợ trên tổng tài sản nói lên điều gì về khả năng sinh lời và mức độ sử dụng nợ của BBS năm 2025?

Actual: ba đoạn cho biên gộp7,21% (hai cách viết) và debt/assets59,06%; partial.
ACTUAL_EXECUTION/M7, ALLOW_WITH_CAVEAT; 9 IDs, 3 segments, 32 selectors
PDF5/6/7. Cả hai ratios khớp Decimal/PDF. Không có grounded interpretation về
khả năng sinh lời/mức sử dụng liabilities; các caveats hạn chế suy luận vẫn giữ.

“nói lên điều gì” không bật interpretation flag, chỉ nhận `nhận định/diễn giải/
phân tích`. Clause cuối “mức độ sử dụng nợ…” thành unsupported. Không chọn
supported_interpretation; cũng không có accepted interpretation tương ứng cho
hai ratios trong filing này để tự ghép. PARTIALLY_CORRECT; F01/P1, F06/P2.
Không đánh giá cao/thấp nếu chưa có ngưỡng/peer evidence.

M5 Planner HTTP503/failed1,046s, không Supervisor/Router/Specialists; M5 financial
NOT_EXECUTED, F03/P1. Files `m7-Q06-final.txt`, `m5-Q06-result.json`, call02.

### Q07

**Original:** Phân tích khả năng sinh lời, tình hình nợ và dòng tiền kinh doanh của BBS năm 2025.

M7 final nguyên văn: “Cần xác định rõ yêu cầu, tài liệu, snapshot, kỳ hoặc phạm
vi báo cáo trước khi tiếp tục.” ACTUAL_EXECUTION, clarification_required /
CLARIFICATION_REQUIRED; 0 IDs/citations. M7 broad-domain target cần làm rõ;
không phát hành Composer body. EXPECTED_ABSTENTION_OR_CLARIFICATION trong
contract M7; PDF5–8 đã xác minh premises độc lập như bảng C, không gọi đây là
một phân tích hoàn chỉnh.

M5 actual3,182s: một Gemini call thành công4.041 tokens, proposal
`intent=unsupported`, required_indicators/operations rỗng; unsupported_capabilities
lại liệt kê chính ba roles hiện hữu. Lý do model nói vượt khả năng “một mục tiêu
đơn lẻ”. Code materialization nhận unsupported và dừng, Router không chạy.
Prompt thực tế yêu cầu nhận diện nhiều mục tiêu và cung cấp cả specialist_boundaries.
Không thể dùng một response để kết luận prompt defect hoặc Router thiếu role.

M5 financial INSUFFICIENT_EVIDENCE; downstream NOT_EXECUTED. F02/P1, observed
stop chain Confirmed; nguyên nhân model misunderstanding/generalization Probable.
Files `m7-Q07-final.txt`, `m5-Q07-result.json`, `m5-Q07-call03-{request,response}.json`.

### Q08

**Original:** Doanh thu thuần và dòng tiền kinh doanh của BBS năm 2025 có cho thấy chất lượng lợi nhuận tốt không? Giải thích dựa trên số liệu.

Actual chỉ doanh thu450.474.531.227 VND và partial/caveats; **không có câu kết
luận earnings quality tốt**. ACTUAL_EXECUTION/M7, ALLOW_WITH_CAVEAT;
5 IDs, 1 segment, 10 selectors PDF2025/7. PDF8 có CFO14.319.681.754 dương;
PDF7 có LNST7.249.557.946, nhưng revenue/CFO đơn thuần chưa chứng minh chất
lượng lợi nhuận tốt hoặc bền vững. Không dùng NP đọc độc lập để tiêm claim vào QA.

Sau tách “và”, cả clause có CFO bị unsupported_inference do “tốt không”; safe
guard chặn verdict đúng mục đích nhưng làm mất factual subrequest. Alias
“dòng tiền kinh doanh” cũng cần kiểm thay vì giả định nhận đúng mọi paraphrase.
CFO đã có direct ACCEPT trong ledger: thiếu CFO ở final không do PDF/OCR thiếu.
PARTIALLY_CORRECT, F01/P1; recommendation giữ refusal cho verdict nhưng cho
phép tách factual premises nếu được duyệt. M5 HTTP503/failed6,006s, financial
NOT_EXECUTED, F03/P1. Files `m7-Q08-final.txt`, `m5-Q08-result.json`, call04.

### Q09

**Original:** Hệ số thanh toán nhanh của BBS năm 2025 là bao nhiêu?

Actual: “Yêu cầu vượt quá khả năng QA đã được hỗ trợ.” Kèm r1 và ledger limit.
ACTUAL_EXECUTION/M7, unsupported_formula/ALLOW; 0 IDs/citations; không gọi
calculator. PDF5/6 có current assets, inventory, current liabilities như bảng C,
nhưng runtime không có approved quick-ratio formula và admission.
EXPECTED_ABSTENTION_OR_CLARIFICATION; không ép phép tính hay tuyên bố PDF
không có operands. Source review chỉ xác minh operands, không chấm quick ratio Correct.
Final `m7-Q09-final.txt`; đây là limitation thiết kế, không finding runtime mới.

### Q10

**Original:** So sánh biên lợi nhuận gộp của BBS năm 2024 và 2025. Mức thay đổi này phản ánh điều gì?

Actual: “Yêu cầu vượt quá khả năng QA đã được hỗ trợ.” Kèm r1/r2 và ledger limit.
ACTUAL_EXECUTION/M7, unsupported/ALLOW; reason
cross_document_comparison_blocked_D03_B10; không claims/citations/calculation mới.
Independent PDF2024/9 và PDF2025/7 cho10,25% →7,21%, giảm3,04 **điểm phần
trăm**, không phải3,04% relative. 2025 comparative column khớp2024 standalone.
EXPECTED_ABSTENTION_OR_CLARIFICATION: giữ policy so sánh nhiều năm hiện tại;
không coi limitation này là runtime failure, không bypass bằng context2025.
Final `m7-Q10-final.txt`; causal interpretation vẫn không được nguồn xác nhận.

## E. Agent Collaboration Analysis

### Fresh actual activation

Mỗi ô fresh evidence là `m5-Qxx-result.json`; call request/response ghi đúng
question nguyên văn. “Selected —” nghĩa stage đó không có routing decision,
không phải Router chọn danh sách rỗng sau khi đánh giá.

| Case | Stage/Agent | Selected | Executed | Status / evidence |
| --- | --- | --- | --- | --- |
| Q03 | Planner | Có | Có | failed; call01 HTTP503 |
| Q03 | Supervisor; Router | — | Không | trace.skipped: gateway_response_failed |
| Q03 | Profitability; Liquidity & Leverage; Cash Flow & Earnings Quality | — | Không | specialist_executions=[] |
| Q03 | Candidate Aggregation | — | Không | trace.skipped, candidates=[] |
| Q06 | Planner | Có | Có | failed; call02 HTTP503 |
| Q06 | Supervisor; Router | — | Không | trace.skipped: gateway_response_failed |
| Q06 | Profitability; Liquidity & Leverage; Cash Flow & Earnings Quality | — | Không | specialist_executions=[] |
| Q06 | Candidate Aggregation | — | Không | trace.skipped, candidates=[] |
| Q07 | Planner | Có | Có | successful provider response → unsupported proposal, call03 |
| Q07 | Supervisor; Router | — | Không | trace.skipped: unsupported_capabilities |
| Q07 | Profitability; Liquidity & Leverage; Cash Flow & Earnings Quality | — | Không | specialist_executions=[] |
| Q07 | Candidate Aggregation | — | Không | trace.skipped, candidates=[] |
| Q08 | Planner | Có | Có | failed; call04 HTTP503 |
| Q08 | Supervisor; Router | — | Không | trace.skipped: gateway_response_failed |
| Q08 | Profitability; Liquidity & Leverage; Cash Flow & Earnings Quality | — | Không | specialist_executions=[] |
| Q08 | Candidate Aggregation | — | Không | trace.skipped, candidates=[] |

### Fresh actual tools

| Cases | Tool | Caller/Input/Result/Latency | Status |
| --- | --- | --- | --- |
| Q03/Q06/Q07/Q08 | find_financial_facts | Not Available: Supervisor chưa chạy | NOT_EXECUTED |
| Q03/Q06/Q07/Q08 | calculate_financial_metric | Not Available | NOT_EXECUTED |
| Q03/Q06/Q07/Q08 | get_evidence_sources | Not Available | NOT_EXECUTED |
| Q03/Q06/Q07/Q08 | get_metric_evidence_lineage | Not Available | NOT_EXECUTED |

Không có fresh requirements DAG/assignments/projection, branch activation,
duplication/conflict hoặc aggregator preservation để đánh giá. Q07 proposal rỗng
là earliest observable stop; không có selected-but-not-executed specialist.
M5 tool requests trong saved M6 calculation history là EVIDENCE_LINEAGE/SAVED_TRACE,
không thêm vào bảng tools actual.

### Saved supplement, không tính fresh coverage

Đọc hai `M5-08-live-targeted/result-E02.json` và `result-E10.json`: saved phase
**partial-live với saved Planner**, không phải fresh QA-Q01 hoặc fresh full-pipeline.
Tóm tắt local `saved-trace-supplement.json`; không replay lại agents hoặc provider.

E02 completed: Profitability nhận riêng gross_margin, hai supporting operands,
13 citations; assigned/covered op_4 khớp, missing rỗng. Aggregator giữ một candidate
và original profitability origin; operands không thành standalone factual workload.
E10 completed: ba specialists thực thi; mỗi projection một fact đúng assignment
(revenue/liabilities/CFO), lần lượt10/10/11 citations. Assigned/covered op_0/op_2/
op_4 khớp, missing rỗng. Aggregator giữ bốn candidates/origins: revenue,
liabilities, CFO và diễn giải dấu CFO; zero conflicts trong saved record.
Không phát hiện claim ngoài assignment trong hai saved projections được đọc;
không suy điều này đúng cho fresh Q07 chưa chạy.

| Saved case | Tool / main input | Saved result | Latency ms |
| --- | --- | --- | ---: |
| E02 | find_financial_facts / gross_profit2025 | found | 2007,20 |
| E02 | find_financial_facts / net_revenue2025 | found | 112,40 |
| E02 | get_evidence_sources / gross_profit source | found | 2067,85 |
| E02 | get_evidence_sources / revenue source | found | 130,57 |
| E02 | calculate_financial_metric / gross_margin | computed | 2286,05 |
| E02 | get_metric_evidence_lineage / same metric | found | 2427,74 |
| E10 | find_financial_facts / revenue2025 | found | 110,89 |
| E10 | get_evidence_sources / revenue | found | 116,46 |
| E10 | find_financial_facts / liabilities2025-12-31 | found | 116,06 |
| E10 | get_evidence_sources / liabilities | found | 123,09 |
| E10 | find_financial_facts / CFO2025 | found | 109,97 |
| E10 | get_evidence_sources / CFO | found | 118,26 |

Caller là saved Supervisor, exact parameters/responses có trong saved tool_trace.
E02 saved Planner có explicit operands và source operations trước metric/lineage;
đây là cấu trúc plan, chưa đủ chứng minh calls dư để tự tối ưu. Collaboration là
typed contracts/context projection, không có evidence agent-to-agent messaging.

### M6/M7 diagnostics

| Case | Selected ACCEPT IDs | Rendered segments / reference selectors | Final firewall |
| --- | ---: | --- | --- |
| Q01 | 0 | 0 / 0 | ALLOW safe abstention |
| Q02 | 5 | 1 / 10, PDF7 | ALLOW_WITH_CAVEAT |
| Q03 | 7 | 2 / 13, PDF7 | ALLOW_WITH_CAVEAT |
| Q04 | 2 | 1 / 19, PDF5–6 | ALLOW_WITH_CAVEAT |
| Q05 | 5 | 2 / 11, PDF8 | ALLOW_WITH_CAVEAT |
| Q06 | 9 | 3 / 32, PDF5–7 | ALLOW_WITH_CAVEAT |
| Q07 | 0 | 0 / 0 | CLARIFICATION_REQUIRED safe message |
| Q08 | 5 | 1 / 10, PDF7 | ALLOW_WITH_CAVEAT |
| Q09 | 0 | 0 / 0 | ALLOW unsupported message |
| Q10 | 0 | 0 / 0 | ALLOW unsupported message |

Mọi selected ID có saved final ACCEPT/verified; full IDs và original/final candidate
bindings ở `selected-claim-proof-audit.json` và per-case JSON. Composer giữ mọi
equivalent IDs; cùng content/context mới merge text, không semantic paraphrase dedup.
Các selectors đều thuộc SHA document2025, D-01/normalized-v2 và đúng trang có
giá trị/operand. Đây là **page-level citation đúng trang**, chưa chứng minh ô/bbox;
renderer không nâng provenance. 32 references không có nghĩa32 nguồn độc lập.

Firewall checks F01–F11: không có fail, F07 not_applicable (không report outline),
F11 warning ở sáu outputs có facts/metrics. F02 request binding, F03 authority,
F08 protected content và F09 citation integrity đều pass. Không có BLOCK case
trong mười câu tự nhiên; đây không phải adversarial acceptance rate. Targeted
percentage-tampering test xác minh fail-closed ở engineering scope riêng.

## F. Root-Cause Findings

### F01 — M7 requirement understanding làm mất explanation/premises (P1)

- Questions: Q02/Q03/Q06/Q08, Q07 supplemental understanding limitation.
- Symptom/expected-vs-actual: Q03 cần formula+operands nhưng chỉ có7,21%; Q06
  cần diễn giải nhưng chỉ ratios; Q08 thiếu CFO dù ledger có CFO; Q02 LNST thành
  generic ambiguous. Expected là giữ nhu cầu đúng và nêu thiếu evidence cụ thể,
  vẫn chặn suy luận chưa được chứng minh.
- First observed faulty stage: `qa_composer.understand_requirements`, trước retrieval.
- Root mechanism **Confirmed**: split “và” không giữ dependency của câu hỏi;
  interpretation keyword hẹp; unsafe guard loại toàn clause có “tốt không”;
  metric requirement không biểu diễn explanation. Diagnostic pure function và
  actual plan/output đều tái hiện, không chỉ một exception.
- Evidence: `requirement-diagnostics.json`, actual Q03/Q06/Q08 plans; saved
  selected metric traces có formula/operands; saved ledger có direct CFO.
- Limit: không có approved LNST target/claim hoặc matching ratio interpretation;
  sửa parser không tự tạo quyền tính/suy luận. Không tìm thấy factual falsehood.
- Generalized fix đề xuất: representation factual premises/explanation/interpretation
  độc lập; dependency-aware clauses; deterministic rendering từ admitted typed
  metadata nếu Tech Lead duyệt. Không special-case mười câu.
- Future regression: conjunction-bound formula/operands; “nói lên điều gì”; factual
  CFO kèm unsupported quality verdict; thiếu interpretation phải partial/abstain.

### F02 — M5 Planner từ chối ba domains trước Router (P1)

- Question: Q07. Expected xử lý broad intent theo supported boundaries hoặc làm
  rõ metric thiếu; actual unsupported với chính tên ba supported roles.
- First observed faulty stage: Gemini PlannerProposal, rồi materialization dừng.
- **Confirmed** stop chain: raw proposal rỗng operations → `_materialize` nhận
  unsupported_capabilities → Orchestrator bỏ toàn downstream. Prompt có quy tắc
  multi_step_analysis và specialist_boundaries; saved E10 chứng minh multi-role
  execution từng tồn tại, không phải ứng dụng chỉ hỗ trợ single-target.
- Root hypothesis **Probable**: model hiểu sai broad-domain capability/unsupported
  policy. Chưa chứng minh prompt nào gây ra hoặc tần suất tái diễn; câu hỏi có
  broad targets nên cần Tech Lead quyết định clarify-vs-analysis policy.
- Evidence: call03 request/response, Q07 result trace, Planner source unsupported
  gate, saved E10 supplement. Không có evidence Router hoặc Specialist sai.
- Fix đề xuất: clarify broad-domain intent, kiểm unsupported proposal against
  declared capabilities; không ép role/metric hoặc bypass policy.
- Regression: controlled proposal liệt kê supported roles trong unsupported list;
  broad three-domain question; truly unsupported metric vẫn phải từ chối.

### F03 — Provider availability làm mất fresh M5 coverage (P1)

- Questions: Q03/Q06/Q08. Expected Planner proposal; actual ba HTTP503 ở ba
  calls khác nhau, 0 Supervisor/tools/Specialists/candidates.
- First observable failure: Gemini transport response trước plan materialization.
- **Confirmed**: adapter ghi origin=provider, provider_unavailable/http_503;
  Gateway/Planner fail closed, giữ error. Không phải evidence của calculation
  bug hoặc quota exhaustion (không HTTP429).
- Deeper root **Unresolved**: service load, model availability hay account backend;
  provider không cung cấp chi tiết trong safe response. Ba responses là bằng
  chứng boundary failure, không đủ khẳng định nguyên nhân vận hành bên ngoài.
- Evidence: call01/call02/call04-response.json và bốn orchestration traces.
- Fix/retest đề xuất: explicit provider-unavailable status; một đợt rerun có
  ngân sách khi provider ổn định. Không đổi model trả phí hoặc retry hàng loạt.
- Regression: structured provider503 stop/usage unknown, không fake fallback,
  downstream zero; integration retest đủ bốn câu sau approved remedy.

### F04 — Saved ledger coverage chưa đủ direct QA (P2, limitation)

- Questions: Q01/Q02; cũng giới hạn interpretive Q06/Q08.
- Expected end-user facts có trong PDF; actual thiếu standalone assets và LNST.
- Earliest limitation: inventory upstream của M7; không có evidence xác định
  stage M1–M6 nào làm thất lạc hai claims, vì ledger là bounded saved evaluation
  inventory, không phải automatic on-demand admission pipeline.
- **Confirmed**: 27 entries của filing2025 chỉ16 direct fact entries về revenue,
  liabilities, CFO, pre-tax profit; assets chỉ metric operand, LNST không target/
  admitted claim. Không kết luận M6 đã reject hay OCR sai khi chưa có histories đó.
- Evidence: independent PDF5/7, `ledger-inventory-saved.json`, Q01/Q02 plans.
- Fix đề xuất: task riêng cho catalog/admission coverage và explicit missing-claim
  handoff, giữ ledger làm authority; không tự promote operand.
- Regression: operand-only assets không thành direct ACCEPT; LNST khác pre-tax;
  absent claim phải abstain/partial dù PDF có số. QA09/Q10 restrictions giữ nguyên.

### F05 — Repository deserialize/hash toàn ledger lặp lại (P2)

- Questions: mọi M7 case, kể cả unsupported/clarification.
- Expected reviewable local latency; actual median46,013s, dù zero LLM/tools;
  Q09/Q10 unsupported vẫn23–25s. Cold ledger61,915s, file139.487.514 bytes.
- First observable cost: production repository `_read` trong mỗi query;
  `_validated_payloads` tránh proof replay lặp, nhưng vẫn parse toàn snapshot,
  compute payload digests và sort tất cả entries trước lọc context.
- Root **Confirmed về repeated work** từ code và stage timings; chưa profile
  để chia phần trăm thời gian parse/hash/GC/I/O, không kết luận bottleneck duy nhất.
- Evidence: public real-repository run, m7-summary stage latency, repository source.
  Không dùng warmed in-memory view trong run để che chi phí này.
- Fix đề xuất: read-only request/session snapshot có invalidation theo file identity
  nếu Tech Lead duyệt, giữ proof validation và exact query semantics.
- Regression: same queries/claims/integrity sau cache, modified file invalidates,
  cold-vs-warm production timing; không lấy old replay-view latency làm runtime SLA.

### F06 — Text lặp và caveats/locators lấn át đáp án (P2)

- Questions: Q02–Q06/Q08. Expected đoạn tài chính ngắn với limitations đọc được;
  actual Q06 final13.344 ký tự, 32 reference selectors và hai câu gross margin
  tương đương; Q05 hai câu CFO tương đương. Q04 final8.344 ký tự cho một ratio.
- First observed behavior: segment grouping theo exact content/context ở M7;
  upstream caveats được hợp và giữ verbatim, renderer hiển thị nhiều selectors.
- Root **Confirmed** về exact-string merge và warning propagation. Một số caveats
  như formula_policy_not_approved hoặc candidate_claims_pending_M6_verification
  là historical annotations trong ACCEPT; không chứng minh final admission failed.
- Evidence: final texts, segment counts, accepted proof audit; không mất caveats.
- Fix đề xuất: tách current admission state/historical warnings cho presentation,
  compact source display và equivalent typed-assertion display nếu được duyệt;
  giữ original IDs/provenance/raw warnings, không tự xóa uncertainty.
- Regression: alternate accepted wordings vẫn giữ mọi IDs/caveats, financial value
  bất biến; prose/source list ngắn hơn nhưng exact bindings còn resolve.

## G. Recommended QA-Fix Backlog

Đây **chỉ là đề xuất**, chưa đăng ký/mở implementation tasks và chưa sửa runtime.

1. **QA-Fix-01 — Grounded requirement coverage:** F01; ưu tiên Q03 formula/operands
   và Q08 factual CFO + safe refusal, rồi Q06 interpretations. Chốt contracts trước.
2. **QA-Fix-02 — Planner broad-domain capability diagnosis:** F02; chốt clarification
   policy, kiểm proposal semantic boundaries; provider503/F03 là blocker retest,
   không lý do đổi paid model hoặc ép Router.
3. **QA-Fix-03 — On-demand admitted fact coverage:** F04; xác định catalog LNST/
   standalone assets và M5→M6→M7 integration scope riêng. Không sửa accepted ledger.
4. **QA-Fix-04 — Production ledger read cost:** F05; đo và giảm deserialize/hash
   lặp trong phạm vi local prototype sau khi bảo toàn integrity semantics.
5. **QA-Fix-05 — Compact provenance-aware presentation:** F06, sau functional coverage.

## H. Regression & Retest Recommendations

- Chạy lại Q03/Q06/Q07/Q08 M5 sau provider recovery và giải pháp được duyệt;
  fresh Planner+Supervisor+Router+actual Specialists, có budgets/traces, không
  replay Planner rồi tính full fresh run. Retest10 M7 sau thay đổi understanding/
  inventory; giữ Q01/Q09/Q10 abstention controls.
- Thêm paraphrases “cách tính và đầu vào”, “nói lên điều gì”, conjunction có phần
  số liệu và inference chung clause; thay chỉ tiêu/công ty/năm, không hardcode BBS.
- Kiểm ambiguous reporting scope, numerator/denominator khác kỳ, citation đúng
  document nhưng sai trang, total liabilities khác interest-bearing debt; no-value
  admission phải giữ abstention, uncertainty không thành conclusion chắc chắn.
- Chỉ thêm targeted automated tests cho generalized mechanisms nêu F01–F06;
  không benchmark framework/UI mới. Modules ảnh hưởng đề xuất: qa_composer/
  firewall_qa_binding và QA contracts; query_planner; catalog/admission boundary;
  ledger_repository; citation rendering/presentation.
- Đo lợi ích Multi-Agent trên số liệu và grounding thực tế sau khi có fresh
  downstream runs; hiện chưa có dữ liệu để tuyên bố cải thiện accuracy/latency.

## I. Execution Metadata

Baseline code SHA **34a3fec1171b23bc9c9c268aded4a2205ae68936**, branch main,
fetch origin main xong và ahead/behind0/0. Accepted firewall implementation
b22d8319ee94c8f400cc7c12face24baacbb2b2e nằm trong baseline. Runtime không đổi.
Report/tooling implementation **6b245b53b4a17d94279717a214428b3638bb52a6** đã
commit/push main, HEAD/origin khớp sau push. Checkpoint sau chỉ docs/planning.
[CI42050329839](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42050329839)
đúng implementation SHA, đang chạy tại lần đọc ban đầu; không gán kết quả CI
của baseline cho QA-Q01.

Environment Windows PowerShell, Python3.12.0 trong `.venv`, pypdfium2 5.14.0,
pydantic2.14.1, google-genai2.33.0, pytest9.1.1. Không cài dependency mới.
Năm source PDFs `data/raw/Financial_Report_pdf/BBS/{2021..2025}/BBS_{year}.pdf`,
lần lượt28/26/29/26/24 pages =133 pages, zero text chars: scans. Chỉ render các
trang cần đọc/context; không OCR/extraction lại. Metadata/hashes/preflight local.

Execution commands:

```powershell
git fetch origin main
.venv/Scripts/python.exe scripts/run_qa_q01.py prepare --output artifacts/evidence/QA-Q01
.venv/Scripts/python.exe scripts/run_qa_q01.py m7 --output artifacts/evidence/QA-Q01
.venv/Scripts/python.exe scripts/run_qa_q01.py m5 --output artifacts/evidence/QA-Q01
.venv/Scripts/python.exe scripts/run_qa_q01.py integrity --output artifacts/evidence/QA-Q01
```

prepare tạo output directory độc quyền; m7/m5 write-exclusive per artifact, không
rerun vào accepted folders. Source render bổ sung và Decimal diagnostics là
QA-only instrumentation, không nằm trong financial business logic.
Context2025 dùng exact company ID, PDF SHA document ID và snapshotD-01/normalized-v2;
existing scenario chỉ cung cấp context binding, **không dùng expected labels hoặc
ledger values làm independent reference**. Không bind request.period2025 vì B01
có native as-of2025-12-31 và B02/B03 là fiscal2025; parser lọc year hiện có.

| Execution | Total latency / model / calls |
| --- | --- |
| M5 Q03 | 1,737s; planning1,737s; one attempted Gemini call; HTTP503; tokens unknown |
| M5 Q06 | 1,046s; planning1,045s; one attempted Gemini call; HTTP503; tokens unknown |
| M5 Q07 | 3,182s; planning3,181s, provider3,151s; unsupported; 3831input+210output=4041tokens |
| M5 Q08 | 6,006s; planning6,005s; one attempted Gemini call; HTTP503; tokens unknown |
| M7 cold ledger | 61,915s, saved-proof integrity validation; not fresh critic execution |
| M7 ten cases | 411,294s stage totals; median46,013s; no Gateway calls |

M7 per-case compose/render/firewall seconds, bao gồm write-capture nhỏ giữa stages:

| Case | Compose | Render | Firewall | Total |
| --- | ---: | ---: | ---: | ---: |
| Q01 | 25,107 | 0,002 | 21,457 | 46,566 |
| Q02 | 21,185 | 0,010 | 24,266 | 45,460 |
| Q03 | 23,473 | 0,016 | 25,939 | 49,428 |
| Q04 | 25,039 | 0,018 | 23,499 | 48,555 |
| Q05 | 25,232 | 0,015 | 27,053 | 52,300 |
| Q06 | 25,955 | 0,039 | 25,979 | 51,973 |
| Q07 | 0,018 | 0,004 | 24,057 | 24,079 |
| Q08 | 21,625 | 0,010 | 22,284 | 43,919 |
| Q09 | 0,010 | 0,003 | 25,457 | 25,471 |
| Q10 | 0,010 | 0,003 | 23,531 | 23,543 |

Actual Gemini calls **4** trên cap16, không retry/rotation/model switch. Requested
gemini-3.5-flash-lite; successful Q07 provider_reported_model giống requested,
effective_model field null; ba error responses chỉ biết requested model. Known
tokens4041; ba calls unknown usage, **không gán unknown=0**. Billed cost và
remaining quota/tier không xác định qua runtime; không xác nhận free quota còn lại
hoặc phát sinh phí bằng suy đoán. Dùng credential/model route đã cấu hình, không
chuyển sang model/API trả phí khác. 0 fresh tools, 0 M7 LLM, 0 OCR/extraction.
Saved supplement không tăng actual-call counter.

Artifacts chính (local ignored, không commit PDF/dataset/traces có dữ liệu nguồn):

- `artifacts/evidence/QA-Q01/preflight.json`, `hashes-before.json`, `integrity.json`.
- `questions.json`, `independent-reference-input.json`, `independent-calculations.json`.
- `m7-summary.json`, `m7-Q01..Q10-{request,composer,rendered,firewall}.json`,
  `m7-Q01..Q10-final.txt`: full exact released answers/clarification message.
- `m5-summary.json`, `m5-inventory.json`, bốn `m5-Qxx-result.json`, bốn request/
  response captures có actual errors/proposal; không secrets.
- `requirement-diagnostics.json`, `ledger-inventory-saved.json`,
  `selected-claim-proof-audit.json`, `independent-output-audit.json`,
  `saved-trace-supplement.json`.
- `source-2025-p{4,5,6,7,8,9}-*.png` / `BBS_2025-p*.png`,
  `source-2024-p9.png`: PDF render, trang9/2025 có bản upright.

Validation local đã chạy: ba selected test functions, **6 parametrized cases PASS**:
orchestrator planner-stop, empty-ledger no M4/M5 fallback, firewall changed-percentage
blocked. Đây là engineering controls, không financial gold. Ruff tooling và
planning/diff checks PASS; planning checker102tasks. QA audit bổ sung đối chiếu
19selected entries và10cases: saved ACCEPT, mọi metric operands/result khớp
independent PDF transcription, citation document/pages đúng, final đúng validated
output. Không full regression/frontend
build vì không sửa runtime/Web. Protected **16.745 files unchanged, added0**:
data/raw/processed/canonical, toàn bộ accepted evidence, src/configs/prompts/
evaluation và local web/next-env.d.ts; integrity run không đụng protected data.

Giới hạn: single run/câu, provider errors khiến không có fresh collaboration evidence;
scan visual sampling ở những trang liên quan, không full-PDF accuracy audit; formal
scope unresolved; không independent annotation của người thứ hai; không performance
benchmark cô lập vì các preflight/QA reads có phần chạy đồng thời. Không khẳng định
Gemini/Multi-Agent accuracy từ synthetic engineering PASS hoặc frozen oracle agreement.

**Next action duy nhất: Tech Lead nghiệm thu QA-Q01 và quyết định nhóm QA-Fix ưu tiên.**
Chưa sửa runtime/financial facts/accepted ledger, chưa triển khai M8 hoặc QA-Fix.
