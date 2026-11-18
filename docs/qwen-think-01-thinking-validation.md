# QWEN-THINK-01 — Thinking Validation

Ngày18/11/2026 (Asia/Bangkok). **REVIEW**. Baseline remote `f6059f1`;
implementation [`80ffc46`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/80ffc468ad3a40c8eca859fb8f19da3f273e4aac), worktree riêng bảo toàn80local edits và dependencies
REMED01–04. Không sửa notebook/server/vLLM/model/context24K/EF-EG/M7 hoặc chuẩn M6.

## Thay đổi và kiểm tra

Adapter bỏ `enable_thinking=False`, chỉ nhận final `content` hoặc phần sau
`</think>`, không đưa `reasoning_content` vào JSON/claims. Thiếu final bị chặn;
hết output budget khi đang reasoning là partial, không báo success. Usage provider
được giữ, gồm cả completion budget đã tiêu hao cho reasoning.

M6 chia batch theo claim khi tổng vượt48K; mỗi claim giữ nguyên nguồn, task closure,
digest và một verdict, không truncate evidence hoặc nới ACCEPT/Obligations. Claim
riêng vẫn quá cap tiếp tục bị chặn. Shared Gateway giới hạn tổng calls/deadline.
Fusion prompt yêu cầu nested document_requirement/dependencies; fallback gom
financial work có cùng nguyên span và giữ phụ thuộc đại từ chỉ khoản mục đã chọn.

Profile client opt-in `QWEN_THINKING_BUDGET=true`: output budget tối thiểu8192,
timeout stage tối đa180s nhưng clamp theo deadline chung300s/câu. Không gửi
chat_template override và không đổi model/context. Profile mặc định tắt.

Local **37unique targeted PASS/1legacy FAIL**, từ hai nhóm:

- Adapter/Thinking/REMED04/obligations/fusion:29PASS.
- M6 Lite/goal binding/Qwen generalization/Thinking:11PASS/1FAIL, gồm3Thinking
  tests trùng nhóm đầu. Failure `test_semantic_request_binds_operations_to_source_ids_without_new_calls`
  thiếu `operand_bindings` tái hiện y hệt baseline `f6059f1`; không sửa ngoài scope.

Ruff lint/format, planning162tasks, py_compile runner và diff checks đạt. Không
fullsuite/fullCI/OCR/Gemini; engineering PASS không là chứng nhận financial accuracy.

## Live và đối chiếu

Freeze trước live; đúng3saved inputs MH0001/NR0001/SH0006, tối đa30calls tổng,
10mỗi câu, retries0. Dùng nguyên corpus REMED04 đã pin; Gold chỉ hậu kiểm. Lưu
receipts/provider/results/ledgers mới tại `artifacts/evidence/QWEN-THINK-01/live-final/`.
`wire-summary.json` chỉ giữ số ký tự reasoning/tag và finish/usage metadata,
không lưu credentials hay nội dung reasoning như đáp án.

**0CORRECT/0PARTIAL/0INCORRECT/3NO_ANSWER**; accuracy và answer coverage đều0/3.
Coverage tính trên QA có released verified answer, không tính scalar ACCEPT nội bộ.
Không có released citations nên citation accuracy/provenance accuracy là N/A.

| QA | Saved Non-thinking → Thinking | Calls trước→sau | Known tokens trước→sau | Wall s trước→sau | Citations trước→sau |
| --- | --- | --- | --- | --- | --- |
| MH0001 | NO_ANSWER → NO_ANSWER |9→5|57.502→31.549|360,383→323,181|0→0|
| NR0001 | CORRECT → NO_ANSWER |5→4|46.222→37.382|199,212→263,387|7→0|
| SH0006 | NO_ANSWER → NO_ANSWER |2→2|10.123→10.882|82,176→129,662|0→0|

Saved3QA: accuracy/coverage33,33% → **0%**,16→**11API calls**,
113.847known tokens/2unknown → **79.813known tokens/1unknown**;
wall641,771→**716,230s** (trung bình238,743s/câu). Input72.495/output7.318known
tokens; completion count gồm cả inline reasoning, provider không tách reasoning
tokens. Tổng latency transport565,953s; đây gồm provider/queue/network, không là
inference-only latency. Call timeout có chi phí/tokens thực tế chưa biết.

10HTTP200 responses đều có inline `<think>`/`</think>`;9được adapter map success,
1final JSON malformed;1network timeout,0partial. Đây là bằng chứng Thinking đã
chạy, không chỉ suy từ tên model `qwen3-8b-awq-t4`. Không vượt3QA/30calls, không
retry/retest/tuning vòng sau; tổng chỉ11calls. Không có M7 live generation call
hoặc released answer để đánh giá chất lượng diễn đạt.

MH0001: FusionPlanner trả typed document_requirement và dependency đúng cấu trúc,
không dùng fallback;4response đầu thành công. Tuy nhiên Coordinator chỉ lập hai
goal/scalar, chưa có verified comparison để chọn chủ thể thuyết minh.2scalar ACCEPT
không có verified goal support; M6 semantic còn19,8s trong deadline rồi timeout.
Kết thúc verification_blocked/0citations,5calls/323,181s. Shared deadline giới hạn
network budget, không là hard wall cap cho tool/post-processing.

NR0001: proposal/Calculator đúng công thức và10,56%, nhưng final M6 JSON thừa
một dấu `}`, chỉ trả1/3verdicts, supported_requirement_ids rỗng. Payload23.389ký tự,
không vượt cap; không salvage JSON hoặc gọi lại.2scalar ACCEPT/1INVESTIGATE,
0goal binding/0citations;4calls/263,387s, provider_unavailable ở final status.
Đây là lỗi structured output thực tế, không được tính thành câu trả lời đúng từ
con số đúng trong trace nội bộ. Không có bằng chứng live cho nhánh chia batch;
nhánh này mới được xác minh qua targeted controls giữ closure/digest/admission.

SH0006: một goal đúng lookup nhưng input_handles rỗng, đi financial Coordinator/
Specialist thay vì tới source row cần hỏi. Retrieved D1/D2 chỉ tên công ty, D3 là
quyền sử dụng đất;0candidate, M6 không chạy. Gold chỉ hậu kiểm; đọc trực tiếp
JSON BED2025 trang15 `/blocks/18/table/rows/1/1` xác nhận “02–07 năm” có trong
nguồn. Model đã đề xuất nhận định thiếu dữ liệu từ retrieval miss; hệ thống chặn
và không phát hành.2calls/129,662s,0citations, không phải lỗi API hoặc JSON.

Thinking sinh final JSON dùng được ở phần lớn calls và Calculator có kết quả đúng,
nhưng **chưa chứng minh cải thiện QA end-to-end hoặc phối hợp Multi-Agent** trên
probe này. Lỗi còn lại: mất goal comparison, deadline chung chưa đủ cho MH, M6
JSON/verdict coverage và retrieval/routing của câu document. Không kết luận
Thinking kém hơn nói chung từ3câu hoặc coi correct intermediate calculation là
financial QA accuracy. Không mở thêm vòng sửa/benchmark trong task này.

## Integrity và bàn giao

`comparison.json`/`reviews.json` và `validation.json` ở local task evidence;
receipts, safe wire metadata,11provider events và3results giữ riêng. Hậu kiểm
xác minh189runtime Git blobs khớp implementation;264JSON nguồn,115imported pins,
3Pilot hashes,272parent evidence files và80local files không đổi. M7/EF-EG/
Obligations/notebooks không đổi.0released claims/citations nên không có pointer
audit dương tính để tuyên bố grounding PASS. Source cell/Decimal hậu kiểm chỉ
xác nhận dữ liệu cần hỏi hiện hữu và phép tính10,56%, không thay M6.

Python worker preflight vẫn `python_unavailable`;3QA này không dùng Python Agent,
không xác nhận capability worker hoặc mở server/API khác. Không có credentials/
dataset/private traces trong tập commit; chỉ runtime/tests/runner/report/tracking.
Implementation và handoff được commit/push `main`, remote SHA kiểm tra ở bàn giao;
không suy CI từ local tests hoặc tự nghiệm thu DONE.

## Giới hạn so sánh

MH/NR đối chiếu REMED04, SH đối chiếu REMED02; baseline không cùng runtime.
Thinking hiện tại cộng adapter/batching/fallback fixes và client output/time budget
khác Non-thinking cũ. SH baseline cũ hơn cả canonical/document fixes REMED03–04.
MH/NR dùng đúng snapshots REMED04; BED_2025 của SH byte-identical với imported
snapshot đã dùng ở baseline. Không phát hiện data migration trong3inputs này;
khác biệt chính là runtime, proposal/goals và client generation/time budget.
Goal/task decomposition và số calls có thể khác; không gọi đây là A/B tuyệt đối.
Không chạy lại Non-thinking; không so tốc độ thuần model từ wall pipeline.
Ba câu được chọn để probe regression/capability, không là Pilot/Full600 score.
Nguồn JSON từ PDF scan đã có, chưa independent PDF verification; không suy chất
lượng OCR hoặc accuracy toàn corpus từ kết quả này.

Next action: Tech Lead review probe âm tính, regression NR và giới hạn budget/routing trước khi giao việc tiếp theo.
