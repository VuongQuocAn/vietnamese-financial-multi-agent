# QWEN-E2E-05 — 3 QA và phân rã latency trên server 20K

**Cập nhật provider rerun được Owner cấp phép:** 34/34 HTTP200; **1 Partial /
1 Abstain /1 Technical Failure**. NR chưa phát hành tỷ lệ được hỏi; MH cạn call
budget ở M6, không phải lỗi HTTP endpoint. M6 đã đo riêng ở cả3 QA; xem
[provider rerun](#provider-rerun--t4x2-tp2-vram07). Runtime giữ nguyên, REVIEW.

## Lượt đầu — giữ nguyên kết quả

**REVIEW**, 20/11/2026. Main `ae215e737ae2d625c4288f4a0957281ece1f33c9`
+ local edits; chưa commit/push. Đã chạy đúng 1 Single-hop, 1 Multi-hop,
1 Numerical: **0 Correct / 0 Partial / 0 Incorrect / 0 Abstain / 3 Technical Failure**.
Accuracy/Coverage **0%**, Technical Failure **100%**. Không sửa runtime/FIX/retry QA.
**M6 chưa được gọi: chưa đo được latency thực thi hoặc tác động của policy M6 mới.**

Chọn trước inference: SH-0018 (medium, ADC_2021), MH-0017 (easy, ADC_2021),
NR-0018 (easy, CAG_2025). Chọn câu đầu chưa có trong manifests còn lưu, chỉ dùng
input/question; không khẳng định blind holdout hoặc chưa từng gặp trong lịch sử.
Gold chỉ mở sau freeze toàn bộ outputs. Rubric: Correct/Partial/Incorrect/Abstain/
Technical Failure; Accuracy=Correct/3, Coverage=(Correct+Partial+Incorrect)/3.

Runtime hiện tại gồm AGENT-PROTOCOL-01 và M6-PRINCIPLE-01; freeze SHA256 toàn bộ
`src/**/*.py`, runner, benchmark inputs và source/import JSON trước chạy.
Server `/models` phải xác nhận model `qwen3-8b-awq-t4`, context 20.480;
input budget 17.096, output cap 2.500. T4/utilization 0,8 theo Owner.
Cap 12 model calls/600s mỗi QA, 36 calls tổng; không gọi Gemini/OCR.

Dùng runner/pipeline/Gateway hiện có. Harness riêng ghi HTTP request/response
không headers, thời gian HTTP đến đọc hết body, adapter latency, usage từng call;
observer `sys.setprofile` chỉ ghi nhận được 3 lượt `FinancialLiteOrchestrator.run`
trong batch này; per-Agent model calls lấy từ Gateway request IDs, Tools/stages lấy
từ trace hiện có. Không thay quyết định hoặc thêm runtime path. Các thời gian lồng
nhau không cộng thành tổng; overhead observer nằm trong E2E, không được đo riêng.
Không so tốc độ E2E này trực tiếp với batch không bật observer.

## Kết quả và latency

| QA | Chấm | Calls | Known input/output | API | Adapter | Tools | Load | Pipeline | E2E |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SH-0018 | Technical Failure | 5 | 3.061 / 810 | 138,283s | 139,539s | 1,077s | 38,005s | 162,885s | 200,890s |
| MH-0017 | Technical Failure | 1 | unknown / unknown | 0,468s | 0,497s | không gọi | 35,757s | 18,437s | 54,195s |
| NR-0018 | Technical Failure | 1 | unknown / unknown | 1,624s | 1,656s | không gọi | 45,650s | 25,362s | 71,011s |

Tổng **7 calls**, HTTP **200×2 / 500×3 / 502×2**; **3.871 known tokens**
(3.061 input +810 output). **5 calls thiếu usage**, không quy tokens lỗi thành 0.
Tổng E2E **326,096s**; pipeline **206,684s**; HTTP API **140,375s**;
adapter **141,691s**. Load119,412s; trong pipeline còn khoảng63,916s ngoài
adapter/Tools (snapshot/context/planning/serialization và overhead observer),
không tự quy phần này cho GPU. `request_snapshot` lần lượt13,446/12,491/17,585s.
Tổng wall batch còn có preflight/hash/khởi tạo ngoài cửa sổ E2E từng QA.

| Call | QA | Agent/stage | Input | Output | API s | Adapter s | HTTP |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | SH | Coordinator plan | 534 | 243 | 59,064 | 59,872 | 200 |
| 2 | SH | Specialist T1 profitability, tool selection | 2.527 | 567 | 76,557 | 76,642 | 200 |
| 3 | SH | Specialist T1 profitability, tiếp tục sau Tools | unknown | unknown | 1,509 | 1,642 | 500 |
| 4 | SH | Specialist T2 profitability | unknown | unknown | 0,366 | 0,474 | 500 |
| 5 | SH | Specialist T3 profitability | unknown | unknown | 0,787 | 0,910 | 500 |
| 6 | MH | Coordinator plan | unknown | unknown | 0,468 | 0,497 | 502 |
| 7 | NR | Coordinator plan | unknown | unknown | 1,624 | 1,656 | 502 |

API đo bằng HTTP request hook đến khi đọc hết response body, gồm network/tunnel/
queue/inference; không có server telemetry để tách các phần này. Adapter còn gồm
tokenizer, tạo payload và parse; không dùng adapter time làm pure inference time.

## Vận hành, M6, Ledger và M7

**SH:** Coordinator lập 3 tasks profitability có dependencies T1→T2→T3.
T1 chọn16 `get_financial_fact`:13 completed,3 `conflicted/known_conflict`
(các cột đầu năm tại trang19). Không cache reuse; tổng Tools1,077s, từng Tool
có thời gian trong `latency.json`. Không Calculator/document search/graph/Sandbox.
Call3 trả HTTP500: “EngineCore encountered an issue”; calls4–5 cùng lỗi.
Đó là provider failure; không có stack trace server để xác định CUDA/OOM/kernel.
Runtime vẫn gọi T2/T3 theo kế hoạch dù T1 thất bại; ghi nhận hành vi, không sửa.

Lỗi model reasoning thứ cấp: câu hỏi cần đọc giá trị hợp lý khoản đầu tư đang
được nắm giữ, nhưng Coordinator chuyển thành tính giá trị doanh nghiệp từ lợi
nhuận ròng và giá trị sổ sách. T1 còn lấy giao dịch bán hàng. Không thể kết luận
đây là nguyên nhân duy nhất của kết quả vì provider đã chết trước final/candidate.
Ba Tool conflicts là trạng thái evidence hiện có, chưa điều tra nguyên nhân nhập
liệu/mapping trong task này; không suy rằng toàn corpus thiếu bằng chứng.

**MH/NR:** Coordinator trả HTTP502; chưa có kế hoạch/Tools/candidates. Không có
evidence để đánh giá chất lượng reasoning của hai QA này hoặc kết luận corpus thiếu.

**Giao thức:**2 responses HTTP200 đều JSON-schema valid; tokenizer khớp usage2/2.
Không parse/schema failure được quan sát; các response lỗi HTTP không thể đánh
giá giao thức Agent. Request lớn nhất7.734 input tokens, dưới budget17.096;
không HTTP400 hoặc context guard rejection. Không phải test sát20K.

**M6 riêng từng QA:** `m6` và `m6_validators` đều `NOT_EXECUTED`; không có
`m6_semantic`, **0 semantic calls**,0 candidates/ACCEPT. Các số0 trong raw stage
là sentinel của bước chưa chạy, **không phải latency M6 được đo bằng0 giây**.
Không thể đánh giá thêm calls/latency do M6-PRINCIPLE-01 từ batch này.

**Ledger:** lookup lần lượt0,000933/0,001071/0,001159s; admission/reload không chạy,
không có verified claims mới. **M7 composer** chạy đường provider-error với
0 claims/0 citations:0,000166/0,000144/0,000120s; **0 model calls** ở M7.
Không coi error rendering là bằng chứng M7 tổng hợp claims thành công.
Sandbox preflight `python_unavailable/worker_preflight_failed`, không có execution.

## Vì sao 4–12 model calls/QA?

Một QA không tương đương một model call: Coordinator lập DAG; mỗi Specialist có
nhiều lượt chọn Tools rồi đọc kết quả và final; M6 gọi semantic riêng khi có
candidates đủ điều kiện. Tools và Ledger/M7 deterministic không tự là Qwen calls.
Batch05 thực tế **5/1/1 calls**, không ép kết quả vào khoảng4–12: SH có1 plan+
2 lượt T1+1 T2+1 T3; MH/NR dừng sau1 plan do provider failure. Không HTTP retry
trong adapter và không retry QA; các calls4–5 là tasks khác của runtime đã freeze.

Đối chiếu trace cũ **QWEN-E2E-04, không chạy lại hoặc chấm lại**: SH/MH mỗi câu
4 calls=1 plan+3 T1; NR12 calls=1 plan+4 T1+4 T2+2 T3+1 M6.
Vì vậy phần lớn12 calls cũ là vòng Specialist–Tool, M6 chiếm1 call; không dùng
số liệu cũ để suy latency/policy M6 mới, không so accuracy giữa hai tập khác nhau.

## Gold, validation và bàn giao

Freeze outputs **13:23:10**, freeze measurements13:23:28 trước mở Gold
**13:23:28** ngày20/11/2026 Asia/Bangkok; timestamps UTC đầy đủ trong manifests
phân biệt chính xác thứ tự dưới1 giây. Gold: SH750.000.000 VND; MH Nhà Xuất bản
Giáo dục tại Hà Nội; NR1,09 lần. Cả3 phát hành cùng thông báo `PROVIDER_ERROR`,
không đáp án tài chính: chấm **Technical Failure**, không Abstain/Incorrect.
Không PDF verification; nguyên văn question/Gold/answer ở `answers-and-gold.md`.

SHA256 **183 runtime files +1.780 source/import JSON files +3 benchmark inputs**
giữ nguyên; runner hash giữ nguyên, outputs/measurements freeze kiểm lại PASS.
Raw scan không chứa API key, headers không được serialize; artifacts/config
được ignore, không stage/commit. Không full CI hoặc test runtime lại.
Planning checker vẫn FAIL `CHAT-01/Status` có sẵn; không sửa task khác.
`git diff --check` PASS. Offline latency summarizer lượt đầu lỗi khi response
`output=null`; chỉ sửa analysis script sau batch, không sửa raw/runtime hay rerun.

Runtime **0 files, +0/−0**, không nhánh/cờ/abstraction runtime mới.
Chỉ3 docs/planning files thuộc bàn giao này;7 scripts local trong thư mục evidence
để chuẩn bị/chạy/freeze/chấm/đo/validate, tái dùng5 scripts batch04.
Artifacts: `artifacts/evidence/QWEN-E2E-05/`: manifests, `provider/`, `http/`,
`results/`, `timings.json`, `latency.json`, `latency.md`, `model-calls.csv`,
`evaluation.json`, `results.csv`, `validation.json`. Bộ này chỉ3 development QA;
provider failures chặn đánh giá chất lượng tài chính và latency M6 thực thi.

Next action: Tech Lead review batch và quyết định xử lý server trước khi cấp phép lượt đo M6 mới.

## Provider rerun — T4x2, TP2, VRAM0,7

**REVIEW**, 20/11/2026. Owner cấp phép chạy lại đúng3 QA qua endpoint mới;
`/models` xác nhận `qwen3-8b-awq-t4`, max_model_len20.480. T4x2/tensor-parallel2/
VRAM0,7 theo Owner, không có GPU telemetry độc lập. Runtime183 files và runner
hash khớp lượt đầu trước/sau rerun, source/import1.780 JSON cùng3 benchmark inputs
không đổi. Không sửa runtime/prompt/cap:12 calls/600s mỗi QA,36 tổng.
Raw lưu riêng `artifacts/evidence/QWEN-E2E-05/provider-rerun/`; giữ nguyên lượt đầu.
Gold đã biết từ lượt đầu; rerun không phải blind holdout. Outputs freeze
**14:05:52**, mở lại Gold **14:06:03** Asia/Bangkok; không gửi Gold vào runtime.

| QA | Điểm | Calls | Input / output tokens | API s | Tools s | E2E s |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| SH-0018 | Abstain | 10 | 57.249 /2.425 | 478,088 | 2,760 | 602,287 |
| MH-0017 | Technical Failure | 12 | 63.247 /1.682 | 373,280 | 33,645 | 545,217 |
| NR-0018 | Partial | 12 | 39.333 /1.623 | 329,681 | 0,607 | 420,532 |

**0 Correct /1 Partial /0 Incorrect /1 Abstain /1 Technical Failure**;
Accuracy0%, Coverage33,33%, Technical Failure33,33%. **34 HTTP200**, không
400/5xx/timeout/transport failure, đầy đủ usage34/34: **165.559 tokens**
(159.829 input +5.730 output). Không suy T4x2 nhanh hơn T4 từ các E2E này.

Tổng E2E **1.568,036s** (26phút8,036giây), gồm load159,345s và pipeline1.408,691s.
HTTP API1.181,049s; adapter1.187,035s; Tools37,012s (nằm trong M5).
Per-call tokens/API/adapter/status đầy đủ34 dòng ở
[latency.md](qwen-e2e-05-latency.md),
`model-calls.csv` và `latency.json`; per-Agent totals cũng trong `latency.json`.
API gồm network/tunnel/queue/inference, không phải pure GPU time. Giữ observer
như lượt đầu; E2E/validators bao gồm overhead chưa đo riêng.

SH E2E602,287s **không đồng nghĩa timeout API600s**: load42,628s trước pipeline;
pipeline559,659s và vẫn chạy deterministic M6 sau model. Cap600s được runtime
áp cho cửa sổ Gateway, không phải hard kill toàn E2E. Offline freezer bỏ assertion
wall≤600 vốn không đúng với định nghĩa này; không sửa runtime hoặc tăng timeout.

### M6 đo riêng, không gộp vào API tổng

| QA | M6 path | Tổng M6 s | Validators s | Semantic wrapper s | Qwen calls / API s |
| --- | --- | ---: | ---: | ---: | --- |
| SH | Lite | 49,023 | 48,908 | không gọi | 0 /không gọi |
| MH | Document | 16,986 | không có counter riêng | không có counter riêng | 1 /16,753 |
| NR | Lite | 29,416 | 13,068 | 16,328 | 1 /16,105 |

SH numeric M6 bác4 candidates `selection_source_mismatch`, không có semantic
candidates nên không Qwen. MH `m6` mặc định trong trace là NOT_EXECUTED vì không
chạy numeric Lite; **`m6_document` có chạy**16,986s. Một document candidate được
gửi semantic (1.648 input/153 output tokens), UNSUPPORTED→ABSTAIN; candidate thứ
hai đã qua source checks nhưng semantic bị Gateway chặn trước HTTP do đủ12 calls,
INVESTIGATE/`semantic_provider_failure`. Không cộng một HTTP call không tồn tại.
Stage `m6_document` bao gồm cả lần bị chặn; không có timer validators riêng để
tách thêm. NR semantic1 call (2.240 input/143 output) đánh giá2 fact candidates;
ACCEPT2, không có ratio candidate được M6 duyệt.

Không kết luận policy M6 mới làm tăng bao nhiêu calls/latency: rerun dùng cùng
runtime đã freeze, không có matched ablation policy cũ/mới. Số đo chỉ mô tả
2 semantic HTTP calls thực sự và một semantic attempt bị chặn bởi call cap.

### Calls, lỗi và đáp án phát hành

**SH10 calls**=1 Coordinator+3 T1+3 T2+3 T3. Coordinator vẫn chuyển bài đọc giá trị
khoản đầu tư thành định giá doanh nghiệp. Tools18 fact executions/51 attempts,
3 conflicted như lượt đầu; candidates có `json_fact_unbound_or_ineligible`12 lần
trong trace các tasks. M6 source-selection replay bác4 proposals; không giải thích
mã mismatch thành một root cause đã chứng minh hoặc quy hết cho model. Không
điều tra/sửa tiếp consistency nguồn trong task này. Final là abstention,0 citations.

**MH12 calls**=1 Coordinator+4 T1+3 T2+3 T3+1 M6 document. Tools4 document-search
executions/7 attempts; candidates vẫn gồm nội dung giới thiệu doanh nghiệp thay
vì liên kết quan hệ bên liên quan với bảng bán hàng. M6 bác candidate đầu; candidate
sau không được semantic vì call cap. Final `PROVIDER_ERROR`,0 claims/citations;
chấm Technical Failure do giới hạn thực thi. Nhãn `provider_unavailable`/semantic
failure không phân biệt budget với provider trong output hiện tại; raw HTTP200 và
`request_provider_budget_exhausted` cho thấy **không có lỗi API mới được quan sát**.
Đây là vấn đề vận hành budget/reporting và model retrieval/reasoning thứ cấp;
không tự nới cap hoặc mở FIX.

**NR12 calls**=1 Coordinator+4 T1+4 T2+2 T3+1 M6 Lite. Tools2 fact retrievals+
2 Calculator executions/9 attempts. Calculator thực sự cho ratio
**1,085655322555942…** và percentage108,565532…; pipeline không đưa ratio thành
verified claim. Có2 candidate protocol rejections `kind_or_meaning_mismatch`.
M6 chỉ ACCEPT2 facts:2025 **39.802.723.187 VND**,2024 **36.662.394.003 VND**.
Ledger lưu2; M7 giữ2 claims/10 citations, báo còn thiếu goal tỷ lệ, không tự suy
thêm1,09. **Partial** là partial credit cho operands đúng; đáp án numerical chính
**chưa hoàn thành**, không gọi là Correct vì Calculator đã tính đúng ở bên trong.
10/10 citation pointers resolve đúng JSON nguồn; không PDF verification.

Toàn rerun3 Coordinator+29 Specialist+2 M6=34 calls; Tools deterministic không
tăng Qwen count. Nhiều calls do DAG và các lượt Tool→Agent→final; MH còn thêm
semantic theo từng document candidate. M7 có0 Qwen calls. NR admission0,101s,
Ledger reload0,696s, composer0,005203s; SH/MH composer0,000189/0,000243s,
không claims được release. Sandbox vẫn unavailable và không được gọi.

### Validation và trạng thái

Tokenizer khớp server34/34; max input9.925, output cap2.500;32 schema outputs
validate PASS,2 M6 outputs JSON mode có verdicts được runtime parse. Không test
sát20K. Freeze manifests/source/runtime/runner và secret scan PASS; config local
và artifacts được ignore, không stage/commit/push. Runtime **0 files,+0/−0**,
không nhánh/cờ mới; chỉ harness/config endpoint và3 docs/planning files của task.
Planning checker vẫn lỗi CHAT-01/Status có sẵn; diff check PASS.

Next action: Tech Lead nghiệm thu rerun và các giới hạn budget/goal chưa hoàn thành.
