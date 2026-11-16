# VFB-E2E-04 — Root Cause Analysis & Targeted Fix

Ngày16/11/2026, Asia/Bangkok. **DONE — Owner chấp thuận**. Implementation
[`2a683faf02318809f6a40bf7cc9a3511fcb63c17`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/2a683faf02318809f6a40bf7cc9a3511fcb63c17)
đã commit local và xác minh; chưa push. Baseline live `f769a12e8f5cf62759018454e167ee9335153988`
cùng local edits có trước.
Đã phân tích15trace E2E03, sửa có giới hạn và chạy **5câu/8Qwen calls**.
Trên đúng5câu này: **0CORRECT/0PARTIAL/1INCORRECT/4NO_ANSWER →
2CORRECT/1PARTIAL/0INCORRECT/2NO_ANSWER**. Graph **0→5calls found**.
Đây chưa phải kết quả mới của toàn15hoặc600câu; không chạy thêm để nâng điểm.

## RCA15câu và sự có mặt của evidence

Đối chiếu saved Supervisor requests/responses, M5 source inventory/tool calls,
M6 outcomes/bindings và M7 coverage. Offline hậu kiểm29Gold evidence anchors
trên15câu: **0missing page/table,0unmatched row label**. Text-only anchor của
SH0071 có trang/văn bản nguồn; kiểm này không phải independent PDF adjudication.
Không có cơ sở nói nguồn JSON thiếu dữ liệu chỉ vì pipeline abstain.
Gold chỉ dùng ở RCA/hậu kiểm; answering dùng questions-only và nguồn import.

| ID | Điểm lỗi xác định từ trace/code | Evidence gốc và trạng thái khắc phục |
| --- | --- | --- |
| SH0016 | Import/mapping: nhãn LNST viết tắt TNDN chưa map; Supervisor chuyển sang PBT; M6 ACCEPT PBT nhưng không bind; M7 giữ lại. | Hàng LNST p11 có số. Sửa alias nguồn và cách hỏi, projection riêng; live CORRECT. |
| SH0080 | Qwen Supervisor: `answer_goal` nằm sai trong task, extra_forbidden; invalid task/plan trước tools/M6. | PBT p9 có trong nguồn/inventory. Prompt/schema example rõ ownership trường; live CORRECT. |
| SH0069 | M5 inventory/truy xuất: chỉ lấy tổng phải thu p7, không lấy ô đối tác Hà Tây trong B09 p20. | Ô chi tiết có trong nguồn. Chưa triển khai truy xuất B09; không live lại. |
| SH0071 | Routing/time parser: “tháng thứ13” trong hợp đồng bị hiểu là kỳ báo cáo không hỗ trợ. | Văn bản p31 có. Chưa sửa phân biệt kỳ hạn hợp đồng/kỳ báo cáo; còn document composition gate sau đó. |
| SH0173 | M5 context thiếu company authority cho C69; chưa có claim để M6/M7 xử lý. | Bảng p41 có. Giữ BLOCKED về authority, không suy company từ ticker. |
| MH0018 | Supervisor nhầm chi phí bán hàng với COGS, thiếu task cover toàn câu; M5 không đọc p27; M6 fact ACCEPT bị dùng như goal support. | B02 p11 và thuyết minh p27 có. Sửa prompt/binding guard; live không còn phát hành COGS sai, nhưng NO_ANSWER. |
| MH0035 | Supervisor `kind/aspect` ngoài enum; requirement bị loại, task/dependency invalid. Specialist còn lại không có evidence. | B02 p9/B03 p10 có; prompt chung đã sửa, chưa live lại câu này. |
| MH0046 | M5 context chỉ nhận scope `confirmed`, từ chối `json_bound` mà catalog đã resolve. | Quan hệ/giao dịch Âu Lạc p46–47 có. Sửa cùng policy ở context/claim selection; actual-catalog context probe đạt, chưa QA live. |
| MH0068 | M5 không nối bảng nợ xấu p15 với tổng phải thu theo khách hàng p14; inventory thiếu chi tiết bị hiểu thành thiếu corpus. | Hai bảng có. M6 INVESTIGATE absence claim là đúng; B09 join chưa sửa, không live lại. |
| MH0078 | Router accent-fold “bằng tiền” thành “bảng tiền”, tạo document requirement rồi đòi composition. | Rollforward p24/p26 và mô tả p16 có. Sửa routing; probe đúng financial lane. Chưa kiểm lại chất lượng trả lời. |
| NR0016 | Số học/nguồn đúng; requirement operand bị gắn interpretation làm M7 vừa trả số vừa báo thiếu. | Hai ô p11 có. Sửa nhận diện scalar goal rõ ràng; offline control đạt, không live lại câu đã đúng. |
| NR0018 | Supervisor sai enum `aspect`, thêm `task_ids`, dependency dùng requirement IDs. | Giá vốn hai kỳ p10 có. Prompt contract rõ hơn; chưa live lại câu này. |
| NR0077 | Vốn chủ chưa map; Supervisor sinh indicator giả/dependency R IDs, task lặp LNST. Sau mapping còn lộ source handle sai kỳ, phép tính bỏ mean và Calculator cấm stock/flow. | LNST p9/vốn chủ p8 có; mapping đã sửa, live retrieve đủ3facts, trả PARTIAL; không nới M6 để lấy điểm. |
| NR0103 | Trước: “bằng tiền” bị route sai. Sau: Supervisor chọn sai source/kỳ, Specialist sai operator/handles; canonical nợ ngắn hạn còn thiếu period. | Raw p9 có nợ, nhưng canonical period=null/quality insufficient; cash cuối kỳ eligible. Routing đã qua, vẫn NO_ANSWER. |
| NR0178 | Context từ chối `json_bound` scope hợp nhất, chưa vào Calculator. | B02 p9 có4operands. Scope policy sửa, actual-catalog context probe đạt; chưa QA live. |

M5/M6 không khai thác được nguồn khác với thiếu canonical authority/capability:

- **Nguồn có nhưng chưa được khai thác:** aliases LNST/vốn chủ, B09 đối tác/
  expense detail, source handles/kỳ chọn sai, false routing và scope gate sai.
- **Input đủ authority chưa có:** company binding C69; period của nợ ngắn hạn
  AME2023. Không dùng tên thư mục để tự điền company/kỳ hoặc đổi quality thành usable.
- **Khả năng chưa hỗ trợ:** `FinancialCalculator.calculate_dynamic` kiểm
  `(period_type, reporting_scope, currency)` và chủ đích chặn trộn stock/flow.
  ROE kết hợp LNST fiscal_year với vốn chủ as_of cần policy phù hợp trước khi
  công nhận phép tính. Cùng lúc, actual Qwen proof còn sai vì bỏ bình quân.
- **Chưa chứng minh thiếu raw evidence:**0/15qua kiểm locator; hash/pointer/row
  có không tự xác minh OCR, ý nghĩa hoặc độ đúng tài chính từ PDF.

## Thay đổi code

1. **Supervisor/graph — `agents/lite_orchestrator.py`:** sửa lỗi V2 ghi đè
   instruction. Giữ hướng dẫn chọn nguồn, vai trò và graph; bỏ mâu thuẫn lịch
   thực thi V1; thêm ví dụ đúng requirement/task, enum/aspect/dependency ownership.
   Schema Pydantic và parser vẫn nghiêm; không sửa response hỏng thành hợp lệ.
   Provider vẫn `json_object`, schema nằm trong prompt, chưa constrained decoding.
   Trên5live plans mới không còn structural plan error, nhưng semantic/source
   choices vẫn sai ở các ca phức tạp; không gọi đây là giải quyết triệt để Qwen.
2. **Graph theo nhu cầu:** task dynamic calculation, nhiều indicators/periods
   hoặc dependency yêu cầu source/operand traversal, dùng tools hiện có. Không
   bật graph cho scalar lookup đơn giản. Raw Qwen plan vẫn có thể use_graph=false;
   policy backend bổ sung truy vết. Tool requests/responses thể hiện execution thật,
   graph structural/contextual không cấp verdict hoặc tự chọn đúng hàng B09.
3. **Mapping — `accounting/item_mapping.py`:** thêm exact aliases từ nhãn nguồn
   `Lợi nhuận sau thuế TNDN`, `D. VỐN CHỦ SỞ HỮU`. Giữ code60/400, statement,
   period/unit/quality gates; không thêm chỉ tiêu hay giá trị tài chính hardcode.
   Alias cách hỏi “lãi sau thuế” ở `question_understanding` tái dùng item đã có.
4. **Routing/context:** giữ dấu cho phân biệt “bảng tiền”/“bằng tiền” trong
   `document_qa_contracts`. Context và claim selection nhận scope `json_bound`
   từ catalog, giữ đúng scope/identity và caveat chưa PDF review; không tự set scope.
5. **Coverage/binding:** lookup fact có alias rõ, một target, không có phép tính/
   so sánh được giữ như scalar. M6 vẫn kiểm source/value; fact được model gán goal
   mà text không khớp alias/nhãn cần semantic support cho binding trong batch hiện có.
   Thiếu verdict không được fallback thành goal support. M6 giữ user question để
   phát hiện local requirement do Supervisor viết sai ý; M7 vẫn chỉ đọc ledger.
   Control offline xác nhận fact ACCEPT không tự bind mục tiêu không liên quan.

Không thêm agent, storage, framework, OCR hoặc mới quy tắc kế toán. Không thay
contracts ledger/provenance. Với MH0018 live, actual numeric candidate đã không
được đề xuất bind vào goal, nên chưa cô lập được tác động riêng của guard M6 mới;
không nhận giảm false release là bằng chứng causal của riêng thay đổi đó.

## Projection và kiểm offline

Reproject đúng **ADC_2021/AMC_2025,68JSON**, suffix `vfb-e2e-04-v1` vào
`artifacts/evidence/VFB-E2E-04/projection-v1/`; corpus41full-final và E2E03 giữ nguyên.
ADC eligible28→32, AMC40→42; graph/fidelity/restart và32+42Financial Tools
lookups đạt,0API. Không lọc/rewrite dữ liệu theo Gold. Ba filing còn lại dùng
bundle IMPORT03 cũ, không reimport toàn41.

**28targeted/compatibility tests PASS** trên code cuối:3controls mới cùng
M5 Lite/V2 integration/M6 Lite. Test mới kiểm prompt/graph dispatch, alias và
negative source-code gate, cash routing, JSON scope acceptance/rejection,
source-valid fact không tự bind câu hỏi khác và scalar interpretation.
Hai lỗi setup của test mới được sửa trước live; không xóa test hoặc nới assertion.
4actual context/routing probes không API đạt: ALT2023/BCC2022 không còn scope
gate sai; MH0078/NR0103 không còn bị “bảng tiền” kéo sang document lane.
Các probe không được gọi là QA PASS.

## Kiểm thử Qwen trước/sau

Một pass5câu, không Gold answering, không retest lặp. SH0080 chạy trước xác
nhận endpoint/prompt rồi4câu còn lại; tối đa6calls/câu,30toàn task, thực dùng8.
Adapter/Gateway/FinancialQAPipeline thật; model `qwen3-8b-awq-t4`, non-thinking,
M5/M6/M7 Lite V2; ledger riêng, Graph/Financial Tools giữ nguyên đường thực thi.

| ID | Trước → sau | Calls trước→sau | E2E(s) trước→sau | Graph sau | Citations sau |
| --- | --- | ---: | ---: | ---: | ---: |
| SH0016 | NO_ANSWER → CORRECT | 2→1 | 47,763→12,123 | 0 | 5 |
| SH0080 | NO_ANSWER → CORRECT | 1→1 | 13,132→11,543 | 0 | 6 |
| MH0018 | INCORRECT → NO_ANSWER | 3→2 | 75,873→45,683 | 2found | 0 |
| NR0077 | NO_ANSWER → PARTIAL | 5→2 | 113,561→87,503 | 3found | 14 |
| NR0103 | NO_ANSWER → NO_ANSWER | 0→2 | 0,003→65,804 | 0, thiếu starting node | 0 |

SH0016/SH0080 đúng tuyệt đối Gold về số/kỳ/VND; citations đúng ô nguồn p11/p9.
NR0077 trả đúng LNST và vốn chủ cuối kỳ nhưng thiếu ROE/vốn đầu kỳ nên PARTIAL.
Qwen dùng vốn cuối kỳ thay bình quân; M6 ABSTAIN proof theo context guard, không
phát hành số ROE sai. Cả3facts đều được Tools lấy, nhưng requirement đầu kỳ còn
trỏ handle cuối kỳ; không sửa handle theo Gold trong answering.

MH0018 không còn câu COGS sai nghĩa trong output, nhưng vẫn thiếu retrieval B09
để xác định nhóm và khoản chi tiết. NR0103 đã qua route nhưng planning/grounding
chưa chạy được phép tính, đồng thời nợ ngắn hạn thiếu period authority; không
quy kết đây là arithmetic error của một phép Calculator đã được thực thi.

**8/8provider responses success,0retry/usage unknown/provider error**,37.934input+
3.449output=**41.383tokens**; tiền chi phí unknown.5Supervisor+3liquidity
Specialist calls; scalar cases dùng generation xác định từ actual tools. M6/M7
thực thi khi có claims, không có provider call riêng ở hai stage đó trong5ca này.
**Không ca nào phối hợp hơn1specialist domain**; graph calls tăng chưa chứng minh
Multi-Agent/EF-EG làm câu trả lời đúng hơn.

So đúng5câu: calls11→8, tokens37.775→41.383, answering250,332→222,656s;
loadcatalog sau19,009s ghi riêng. NR0103 trước dừng ngay, sau có thực thi;
prompt/graph context tăng token. Không suy kết quả này thành latency/cost gain
thuần do code hoặc estimate accuracy15/600; chưa có paired ablation.

25citation references phát hành trên3câu có answer:25/25hash/pointers resolve,
labels hợp lệ và bind released claims. NR0077 có p8/p9 operands và các nguồn
context/unit/company p7/p10/p12/p1; các trang context không thay ô đáp án.
Không tính hai câu không answer thành citation success. Mọi nguồn vẫn JSON-only,
`pdf_page=null`, `financial_fact_verified=false`, có chú thích chưa xác minh PDF.

## Bàn giao, giới hạn và bước tiếp

Đã xử lý lỗi prompt bị ghi đè, kích hoạt graph cho composite task, hai mapping
gaps, cash phrase routing và JSON scope gate; thêm guard goal binding không tự
cấp coverage. Hai câu Single-hop chuyển đúng, Multi-hop ngừng phát hành sai,
ROE khai thác được thêm facts nhưng chưa trả metric. Các lỗi B09/join, company,
period resolution, Qwen chọn source/operation/kỳ và stock/flow policy còn tồn tại.
Chưa sẵn sàng mở600; không đổi kết quả1/15 của E2E03 thành số mới khi10câu chưa rerun.

Artifacts ignored `artifacts/evidence/VFB-E2E-04/`:
`baseline.json` và `baseline-code/` giữ checkpoint local trước sửa;
`root-cause-15.json` có trace/stage/29anchors và phân loại gaps;
`projection-v1/`, `context-probes.json` là offline evidence;
`live-v1/results/`, `provider/`, `ledgers/` giữ actual traces/usage;
`answers-and-gold.md`, `evaluation.json`, `judgments.json`, `before-after.json`
giữ nguyên văn/cách chấm và so sánh5câu. Runner
[run_vfb_targeted_qwen.py](../scripts/run_vfb_targeted_qwen.py) tái dùng runner
E2E03, chỉ lấy manifest questions-only, override đúng2bundle mới và giữ budget.
Evaluator chỉ đọc Gold sau đủ5results; không LLM judge.72artifacts E2E03 không đổi;
1.488source JSON hashes/benchmark/pilot hashes và runtime receipt sau freeze đạt.
Ruff/planning/diff là kiểm kỹ thuật; không fullsuite/CI hoặc API thêm.

**Next action:** chờ Owner/Tech Lead giao task tiếp theo; không tự mở benchmark rộng.

## Chấp thuận và đóng task — 16/11/2026

Owner chấp thuận kết quả VFB-E2E-04 và cho đóng DONE sau khi commit.
Commit giữ7runtime files sửa trong task và6dependency files cho JSON
handoff/citation, target matching từ local implementation trước đó, đúng nội dung
đã dùng khi live;3runners và JSON citation regression là dependencies cần tái lập.
Không đổi trạng thái task trước, không gom legacy prompt/PDF discovery/frontend
hoặc planning ngoài E2E04. Phần tracking được stage riêng theo task.
Phiên đóng không gọi API, OCR hoặc benchmark; giữ nguyên kết quả live và28tests.
Đã commit implementation `2a683faf02318809f6a40bf7cc9a3511fcb63c17`, xác minh
13runtime files trong commit khớp live receipt (chuẩn hóa newline Git).
Trước commit, bản stage tách biệt khỏi working tree đạt29tests (28controls/
compatibility +1JSON citation regression), Ruff lint/format và planning checker.
Registry committed chỉ stage phần E2E04,145tasks; local registry vẫn giữ158tasks
cùng các thay đổi task khác chưa commit. Tracking đóng task ghi SHA implementation
đã tồn tại; không thay đổi code hoặc chạy lại API/tests sau commit.
