# QWEN-E2E-06 — Development rerun sau AGENT-EFFICIENCY-01

**REVIEW**, 20/11/2026. Main `3b99d2a00598b73ce254a08a3f698d2313218162` + runtime local gồm
AGENT-EFFICIENCY-01; không commit/push runtime. Chạy một lần đúng SH-0018,
MH-0017, NR-0018 bằng runner và telemetry QWEN-E2E-05 hiện có; cap12 calls/
600s mỗi QA,36 tổng. Một QA lỗi không hủy các QA độc lập còn lại.

Freeze runtime, source/import, input manifests và cấu hình trước inference;
endpoint/model phải xác nhận context20.480. T4x2/TP2/VRAM0,55 theo Owner.
Không sửa code/prompt/config hoặc retry QA trong lúc chạy; stdout vào log,
không đọc/phân tích từng call khi chạy. Không tạo script phụ hoặc report từng call.
Gold đã biết: đây là development rerun, không blind evaluation; chỉ đối chiếu
Gold sau khi cả3 outputs freeze. Không dùng Gold điều chỉnh runtime.

Sau batch: một bảng trước/sau với QWEN-E2E-05 provider rerun (34 calls:
3 Coordinator/29 Specialist/2 M6; E2E1.568,036s;0 Correct/1 Partial/1 Abstain/
1 Technical Failure). Kiểm tra plan có dư thừa, Calculator→analysis claim,
MH semantic trong budget, SH đúng nghĩa vụ, M6 riêng và Ledger/M7;
phân biệt giảm calls do tối ưu với dừng sớm/thất bại. Giữ các confound cấu hình
server và observer trong diễn giải latency, không tự mở FIX/thêm QA.

Raw riêng: `artifacts/evidence/QWEN-E2E-06/`; không ghi đè batch05.

## Kết quả trước/sau

**Calls/latency giảm; accuracy grounded chưa tăng.** Kết quả batch06:
**0 Correct /1 Partial /1 Incorrect /1 Abstain /0 Technical Failure**.
SH có số khớp Gold nhưng citation/chỉ tiêu là Giá gốc, không phải Giá trị hợp lý;
không tính Correct chỉ vì hai ô cùng750.000.000 VND. Coverage cao hơn bao gồm
cả câu Incorrect, không đồng nghĩa chất lượng tài chính cao hơn.

| Chỉ số | Batch05 provider rerun | Batch06 | Thay đổi |
| --- | ---: | ---: | --- |
| Tổng Qwen calls | 34 | 30 | −4 (−11,76%) |
| Coordinator | 3 | 3 | không đổi |
| Specialists | 29 | 21 | −8 (−27,59%) |
| M6 | 2 | 6 | +4 |
| Input tokens | 159.829 | 102.542 | −57.287 |
| Output tokens | 5.730 | 4.460 | −1.270 |
| Tổng tokens | 165.559 | 107.002 | −58.557 |
| Tổng HTTP API | 1.181,049s | 816,313s | −364,736s |
| Tổng E2E | 1.568,036s | 1.084,562s | −483,474s (−30,83%) |
| Accuracy | 0% | 0% | không đổi |
| Coverage | 33,33% | 66,67% | +33,33 điểm % |
| Technical Failure | 33,33% | 0% | −33,33 điểm % |
| Correct / Partial / Incorrect / Abstain / TF | 0 /1 /0 /1 /1 | 0 /1 /1 /1 /0 | SH phát hành sai nghĩa chỉ tiêu; MH hết lỗi budget |

| QA | Batch05 → Batch06 | Calls C/S/M6 trước → sau | E2E trước → sau | Input/output tokens batch06 |
| --- | --- | --- | --- | --- |
| SH-0018 | Abstain → Incorrect (grounding) | 1/9/0 → 1/7/1 | 602,287 →337,419s | 31.998 /1.156 |
| MH-0017 | Technical Failure → Abstain | 1/10/1 → 1/7/4 | 545,217 →395,959s | 39.789 /1.807 |
| NR-0018 | Partial → Partial | 1/10/1 → 1/7/1 | 420,532 →351,184s | 30.755 /1.497 |

30/30 HTTP200, usage đầy đủ; không API/transport/parse/schema failure quan sát
được. Không gọi Gemini/OCR, không retry QA. Adapter820,068s; pipeline962,353s;
load122,209s; Tools35,878s. API gồm queue/network/tunnel/inference, không phải
pure GPU time. E2E không gồm toàn bộ preflight/hash/khởi tạo; không cộng các stage
lồng nhau hoặc Tools vào API như các phần độc lập.

## Các câu hỏi nghiệm thu

**Specialist có giảm thật không?** Có:29→21 calls thật qua transport, không tính
4 attempts bị Gateway chặn trước HTTP (SH3,NR1). Tuy nhiên cả3 QA đều dùng hết
8 M5 calls=1 Coordinator+7 Specialists. SH dùng7 calls ở T1; MH3+3+1 ở T1/T2/T3;
NR4+3 ở T1/T2. Chưa chứng minh loop tự chốt sớm khi đủ evidence hoặc giảm được
lượt thừa độc lập với cap. Sự giảm này có phần trực tiếp từ reserve budget và
việc không chạy tiếp tasks. Không gọi đây là tối ưu hiệu quả trọn vẹn.

**Coordinator còn dư thừa?** Có. SH tăng từ3 lên**4 tasks**: thu thập BCTC công ty
được đầu tư, phân tích ROE/ROA/EBITDA, thanh khoản/cấu trúc vốn và dòng tiền.
Đây vẫn là bài định giá doanh nghiệp thay vì đọc một giá trị khoản đầu tư.
T1 dùng hết7 Specialist slots; T2/T3/T4 bị reserve chặn. MH vẫn3 tasks; NR vẫn3
tasks tách đọc2025/đọc2024/tính tỷ lệ, dù một Specialist có thể làm cùng nhiệm vụ.
Không có bằng chứng prompt Coordinator mới đã đạt mục tiêu phân rã tối thiểu.

**SH đúng nghĩa vụ bằng chứng?** Không. Final phát hành:
“Công ty CP DVXB Giáo dục Hà Nội (*) kỳ2021-12-31 là750.000.000 VND.”
Citation giá trị là JSON trang19 `/blocks/6/table/rows/0/1`, header
`31/12/2021 - Giá gốc`; Gold hỏi cột2 `31/12/2021 - Giá trị hợp lý`.
Cả hai cùng750.000.000 nên số-match che sai lệch chỉ tiêu. Trong M6 request,
E1 đã có header Giá gốc; retrieved table cũng có đủ hai cột, nhưng Verifier nói
E1 hỗ trợ giá trị hợp lý, SUPPORTED và goal G1 satisfied. Ledger lưu1, M7 phát
hành1 claim/5 citations. Đây là lỗi chọn/diễn giải nguồn và semantic false accept
quan sát được; không phải thiếu header ở M6 request hoặc lỗi API. Chấm
**Incorrect theo nghĩa tài chính/grounding**; nếu chỉ tính exact number thì SH
khớp Gold, nhưng đó không phải grounded Correct. Tech Lead cần xem cả hai ô.

**NR Calculator→analysis có hoạt động?** Chưa đạt. Hai Calculator executions đều
cho ratio1,085655322555942…; task T1/T2 giữ `calculations` đầy đủ qua retrieval,
và final prompts vẫn có history. Tuy nhiên cả hai final chỉ chọn scalar facts,
`analyses` rỗng/không có và ghi thiếu thông tin tỷ lệ. Task T3 tính tỷ lệ không
được gọi vì hết phần M5. M6 chỉ kiểm2 operands; Ledger/M7 phát hành
36.662.394.003 VND năm2024 và39.802.723.187 VND năm2025,10 citations, vẫn báo
chưa đáp ứng goal tỷ lệ. **Partial** chỉ là credit cho inputs đúng; không có
ratio analysis candidate để M6 duyệt và không có đáp án1,09 lần được phát hành.
Không còn mất Calculator history như trước, nhưng model chưa sử dụng để tạo
analysis; budget/task decomposition cũng chặn task tính riêng. Python không tự
bịa claim hoặc tính thêm ở M7 để cứu đáp án.

**MH semantic có đủ budget?** Có. 8 M5 calls để lại đúng4 calls M6 document;
4/4 semantic requests hoàn tất HTTP200,4 ABSTAIN/`semantic_unsupported`, không
technical error hoặc budget block. T1 và T2 chọn lại hai D handles của nội dung
không chứng minh quan hệ/giao dịch được hỏi; tạo4 document candidates. M6 bác
hết nên final là abstention,0 admissions/claims/citations. Dự trữ đã giải quyết
starvation trong case này, nhưng retrieval/reasoning chưa hoàn thành câu hỏi;
4 calls còn dùng cho proposals lặp nội dung theo tasks, không phải4 bằng chứng mới.

## M6 và vận hành đo riêng

| QA | Path | Tổng M6 trước → sau | Validators sau | Semantic wrapper sau | M6 calls/API sau |
| --- | --- | --- | ---: | ---: | --- |
| SH | Lite | 49,023 →24,775s | 5,533s | 19,230s | 1 /19,080s |
| MH | Document | 16,986 →63,885s | không timer riêng | không timer riêng | 4 /62,958s |
| NR | Lite | 29,416 →29,806s | 13,093s | 16,693s | 1 /16,470s |

MH numeric `m6` mặc định NOT_EXECUTED không nghĩa M6 không chạy: timer đúng là
`m6_document`. M6 tổng tăng95,425→118,466s trong khi E2E giảm. M6 không chỉ
tốn API; validators/source checks và observer nằm trong timer tổng. Không có
ablation tách riêng policy M6, nên không quy causal effect cho một thay đổi.

Tools: SH2 document searches+2 fact retrievals (18,146s); MH2 document searches
(17,101s); NR2 fact retrievals+2 Calculator (0,631s). Cache reuses/attempts và
từng kết quả tính giữ trong raw trace. Sandbox preflight unavailable, không có
execution; không coi batch này là bằng chứng Python worker hoạt động.
Ledger mới3 claims (SH1,NR2); M7 giữ đủ3, tổng15 citation pointers resolve đúng
JSON. Pointer resolve được không chứng minh đúng chỉ tiêu: lỗi cột SH nêu trên.
Đây là JSON-grounded checks, **không xác minh PDF độc lập**.

## Freeze, validation và giới hạn

Chỉ khởi chạy một lần runner `run_vifinbench_pilot.run` qua harness/observer
batch05 hiện có. Override trong bộ nhớ chỉ output directory và endpoint assertion;
không tạo/sửa script, runtime hoặc prompt. Stdout ghi `runner.log`; không mở
log/call trong lúc chạy. Theo chỉ đạo kiểm tra mới của Owner, đã đọc artifacts
khi tiến trình vừa hoàn tất đủ3 outputs; sau đó freeze outputs rồi mở lại Gold.
Config chứa key chỉ ở file local được ignore; chỉ hash config và lưu cấu hình
không bí mật trong baseline. Giữ observer giống baseline, không thêm telemetry layer.

183 runtime hashes, source/import1.780 JSON,3 benchmark input files, schema,
tokenizer assets, runner/harness và config hashes giữ nguyên trước/sau. Outputs
freeze kiểm lại PASS; secret scan PASS. Tokenizer khớp server30/30;24 responses
có JSON schema validate PASS,6 M6 JSON-mode outputs được runtime parse.
Input lớn nhất5.805 dưới17.096; không phải thử sát20K. Runtime task này
**0 files,+0/−0**, không thêm branch/config flag; không mở FIX hoặc thêm QA.

Raw artifacts: `baseline.json`, `receipt.json`, `questions-only.json`, preflight,
`runner.log`, `provider/`, `http/`, `results/`, `ledgers/`, `timings.json`,
`outputs-freeze.json`, `gold-selected.json`, `evaluation.json`, `validation.json`.
Per-call tokens/API và summary nằm trong evaluation JSON, không tạo báo cáo từng call.
Planning checker vẫn lỗi `CHAT-01/Status` có sẵn; diff check PASS. Không chạy lại
unit suite vì không sửa runtime. Chỉ một báo cáo Markdown tổng hợp này.

Cùng inputs/cap/model name nhưng khác endpoint/server và VRAM0,7→0,55;
load159,345→122,209s cũng góp vào E2E. Mẫu3 development cases/1 run không chứng
minh tổng quát hóa, causal speedup hay benchmark readiness. Accuracy grounded
không tăng; coverage tăng nhờ SH được release dù sai nghĩa nguồn, MH chuyển từ
technical failure sang abstention. Kết quả có tiến bộ budget nhưng còn lỗi
planning, proposal và semantic verification; giữ REVIEW, không tự FIX.

Next action: Tech Lead đánh giá tradeoff giảm Specialist calls với lỗi planning/grounding và NR chưa có ratio claim.
