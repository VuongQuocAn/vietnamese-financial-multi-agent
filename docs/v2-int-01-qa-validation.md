# V2-INT-01 — Hoàn thiện và kiểm chứng QA V2

## Rà lại Gold C07, xác nhận C10 và phân rã latency — 13/11/2026

**REVIEW**, tiếp tục trong V2-INT-01. Owner chấp nhận tiến triển C01; phiên này
không sửa `src/`, không gọi lại C01/C07 và không thêm agent/tầng xử lý. C10 chạy
riêng đúng source `3734eb921e6fb0892a1d10ff6de37323cbded3ff`, 1 lượt, 4 Qwen calls,
23.370 tokens API, 0 unknown/error/retry. C01 giữ kết quả live `25f7316` đã PASS.
Các bảng bên dưới mục này giữ nguyên như lịch sử theo rubric cũ, không phải kết luận
hiện hành về C07.

### C07: sửa lỗi đánh giá, không sửa runtime

Câu “Không suy ra số lãi vay vốn hóa thực tế từ chính sách” là **ràng buộc không
được vi phạm**, không yêu cầu thêm một claim giải thích. Gold cũ đã sai khi đưa
`no_actual_amount_inference` vào mẫu số Claim Recall. Gold v2 giữ bốn nội dung cần
trả lời: LNST, ghi chi phí, điều kiện vốn hóa và ngoại lệ vay riêng; ràng buộc được
kiểm riêng bằng `constraints_met`. Vi phạm vẫn làm Answer Accuracy = 0, kể cả
khi trả đủ bốn nội dung; không cộng điểm chỉ vì viết lời nhắc phạm vi.

Rà toàn bộ hai final answers xác nhận không bịa/suy ra số vốn hóa thực tế. Số tiền
LNST, điều kiện thời gian, tỷ lệ/formula trong chính sách không phải số vốn hóa
thực tế. Bốn nội dung đều có và đúng nguồn PDF7/12. **Cả baseline b113136 và live
25f7316 đều PASS C07** theo rubric sửa đúng: Numeric1/1, Claim P7/7, Recall4/4,
F1=100%, Citation7/7, AnswerAccuracy1. Điểm 88,89%/PARTIAL trước đây là lỗi Gold,
không phải một thiếu sót runtime; quotation dài còn là hạn chế trình bày.

Gold v2 được lưu riêng trước call C10 mới, SHA256
`eee4bbea33955ff1a9b6fd093a17026dba5022cfd1d06c431b48be587bdc02f0`.
Không ghi đè Gold/reviews/metrics cũ. Trên cùng C01/C07 với rubric mới, baseline
ClaimF1=95,65%, AnswerAccuracy1/2; bản25f7316 ClaimF1=100%, AnswerAccuracy2/2;
Numeric8/8 và citation16/16→18/18. C07 không có cải thiện runtime giữa hai bản.

### C10: retrieval đã được xác nhận, tách completeness khỏi groundedness

Supervisor lại khai đúng canonical operands nhưng chọn `sources=[S1,S18]` như lượt
hồi quy. Bản3734eb9 đã resolve và lấy đủ current_assets, short_term_liabilities và
CFO trước khi resolve tên kết quả động. Final phát hành đúng:

- Vốn lưu động ròng −600.656.455.132 VND, current ratio0,56 lần, đúng toán hạng/kỳ.
- CFO314.097.335.438 VND; tài sản ngắn hạn767.374.839.317 VND và nợ ngắn hạn
  1.368.031.294.449 VND; PDF5/6/8 đúng document/snapshot.
- Nhận xét thiếu hụt số dư cuối kỳ bên cạnh CFO dương cả năm và giới hạn không bảo
  đảm thanh toán tương lai. Numeric5/5, EM1, positive-gold Recall6/6.

M6 ACCEPT7/ABSTAIN1; cả7ledger IDs được phát hành. **Không lấy completeness hoặc
M6 ACCEPT làm bằng chứng mọi prose đã grounded.** Candidate
`candidate:149acfd13711ccb2293db2f2` còn thêm “Hệ số thanh toán hiện hành thấp có thể
cho thấy khả năng thanh toán hiện tại hạn chế” và “Lưu chuyển tiền thuần dương là
dấu hiệu tích cực”. Semantic verifier chủ yếu xác nhận các số và cho rằng toàn bộ
limitations phù hợp; chưa giải thích chuẩn/tiêu chí cho hai nhãn định tính này.
Phần giới hạn/tổng hợp có căn cứ cũng được ACCEPT độc lập ở
`candidate:df226a85f0373230dc4858be`.

Adjudication bảo thủ đếm11mệnh đề độc lập, không đếm lại số/nhận xét lặp ở caveats:
9đủgrounding/2nhãn định tính chưa đủ rõ chuẩn. Claim Precision9/11=81,82%, Recall6/6,
**F1=90%**, Citation Accuracy/Completeness9/11, AnswerAccuracy0 → **PARTIAL**, chờ
Tech Lead review hai mệnh đề. Đây không phải bằng chứng số CFO/ratio sai; trang
nguồn đúng chưa tự chứng minh một đánh giá định tính. Từ “thấp” có thể được hiểu là
so với mức đủ bù nợ ngắn hạn, nhưng câu chưa nói rõ cách hiểu đó; báo nguyên văn và
giữ adjudication để reviewer quyết định. Không sửa runtime hoặc chạy thêm live để
ép PASS. Final vẫn lặp số/phép tính và limitations nhiều lần.

So baseline C10: Numeric5/5→5/5, Recall5/6→6/6, F1 90,91%→90%, citations5/5→9/11,
AnswerAccuracy0→0. So lượt hồi quy9eb0951, numeric1/5→5/5. Đã xác nhận retrieval
fix nhưng chưa thể nói toàn bộ chất lượng C10 đã đạt. Không gộp số liệu mới với
C01/C07 cũ thành một lượt ba câu cùng SHA/model-server condition.

### Thời gian ngoài provider: số đo và điểm nóng

Từ trace C01 đã có,182,83s E2E =69,67s provider +**113,15s ngoài provider**.
API trace chiếm118,67s, trong đó49,00s ngoài provider;64,16s còn lại nằm ngoài
API trace (imports/setup/ghi artifacts của runner). Trace cũ không đủ tách64,16s
thành từng phần; không quy toàn bộ113s cho catalog hoặc LLM.

Runner phiên này đo riêng từng phase. C10 trên3734eb9: E2E **241,70s**, provider
**159,67s**, non-provider **82,03s**:

| Phase | Giây | Phạm vi |
| --- | ---: | --- |
| Imports | 52,99 | Trước tạo request/catalog |
| Adapter và request | 1,05 | Config không ghi ra log |
| Dựng BBS catalog | 8,05 | Không được dùng bởi factory BCC |
| Pipeline setup BCC | 0,99 | Catalog BCC/composition hiện có |
| Pipeline run | 177,58 | Gồm159,67s provider và17,91s nội bộ |
| Ghi execution/ledger/answer artifacts | 1,04 | Sau pipeline run |

C10 calls5→4 so baseline, nhưng E2E210,99→241,70s **không cải thiện** trong lượt này.
Khác server/load nên không quy tăng latency cho source. Diagnostic import ở process
riêng sau khi files đã được đọc chỉ mất2,12s; đo cold52,99s chưa được giải thích
dứt điểm, không khẳng định nguyên nhân antivirus/cache hoặc hứa giảm cố định50s.

Một offline C01 saved-response replay,0API, cProfile: dựngBBS19,52s, setup4,92s,
run102,93s. Đây là **số đo có overhead profiler**, không cộng chúng với live hoặc
báo là benchmark latency. Điểm nóng theo cumulative time: deepcopy46,13s;
M6 constructor18,17s; snapshot metric/lineage selection khoảng15,86s;
ledger admission15,20s, ledger find15,02s, atomic JSON dump10,83s. Các số lồng nhau,
không cộng tổng. Catalog init cũng copy records rồi retrieval lại copy, chiếm
15,84/19,52s của setupBBS khi profile. Hướng tối ưu có căn cứ là tái sử dụng snapshot
request-local đã có cho M6 và giảm copy/serialize lặp, giữ nguyên isolation/replay;
phiên này **chưa thay runtime C01** hoặc bỏ kiểm chứng để làm nhanh.

Kiểm tra exact-text replay C01 ban đầu FAIL do bốn fact paragraphs đổi thứ tự;
đối chiếu multiset tất cả paragraphs (gồm citations) khớp hoàn toàn. Không che
assertion fail, không báo byte-identical hoặc API quality rerun. C01 content/citations
đã PASS vẫn giữ nguyên.

Sửa nhỏ chỉ ở runner: cho phép manifest thật chỉ có C10, không giả chạy C01/C07;
ghi phase timings và bỏ dựng BBS catalog cho C10. Test loader xác nhận C10 không gọi
BBS, C01 vẫn dùng loader cũ. Lượt live trên đo trước tối ưu skipBBS:8,05s là chi phí
đã quan sát có thể loại bỏ, **chưa có live sau sửa runner để công bố E2E giảm**.
Không đổi FinancialQAPipeline, source3734eb9, M6 hoặc prompt C01/C07.

### Bàn giao

3targeted runner/scoring tests PASS (gồm constraint compliance không làm giảm Recall),
Ruff/format/planning/diff đạt; không full CI/Gemini/OCR. Artifacts ignored ở
`artifacts/evidence/V2-INT-01/qa-review-followup/`: gold-v2, C07 before/after reviews,
`c10-live/` nguyên requests/provider-events/execution/ledger/answer/phase timings,
C10 adjudication/citation audit và performance-review/profile summaries. Credentials
không vào Git/log. Giữ local edits ngoài task; QA toàn task vẫn REVIEW.

**Next action duy nhất:** Tech Lead review adjudication C10 và số đo hiệu năng trước
khi quyết định phạm vi tối ưu tiếp trong V2-INT-01.

## Phiên tối ưu synthesis và hiệu năng — 13/11/2026

**REVIEW — chưa đạt đầy đủ QA ba câu.** Source bàn giao `3734eb921e6fb0892a1d10ff6de37323cbded3ff`
trên main; live gần nhất dùng `25f73161b829dcc4162b006d4404a11644bf459b`.
Qwen timeout tại call đầu C10, adapter `timeout/not_retryable`, 60,14s;
runner dừng ngay, không retry hoặc gọi thêm API. Bản sửa operands `d5b91a7` đã kiểm
offline nhưng **chưa live**. Các phiên dưới mục này là lịch sử, không phải kết quả
live của source bàn giao mới.

`3734eb9` chỉ sửa định dạng hai đoạn mới trong `specialist_common.py`; logic giữ
nguyên `d5b91a7`, không gọi lại API. Format check cuối phát hiện hai đoạn này chưa
đạt; đã sửa và kiểm lại thành công trước bàn giao.

### So trực tiếp với baseline b113136

Giữ nguyên Gold 8/5/6 atoms, 7/1/5 numeric slots và rubric ở dưới. Gold hiện lưu
CRLF, SHA256 bytes `4f81b77c629a720e699d1494b2e638342bd9315ac13caa4243395a048ed7e40c`;
chuẩn hóa LF khớp SHA `665ce0e…` đã công bố. Toàn bộ atoms khớp baseline reviews.
Chấm final answer, không cộng số chỉ có trong ACCEPT/ledger. Interruption là N/A.

| Câu | Gold QA trước → sau | Numeric Accuracy trước → sau | Claim F1 trước → sau | Answer Accuracy trước → sau | Citation Accuracy trước → sau |
| --- | --- | --- | --- | --- | --- |
| C01 | PARTIAL → **PASS** | 7/7 → 7/7 | 93,33% → **100%** | 0 → **1** | 9/9 → 11/11 |
| C07 | PARTIAL → PARTIAL | 1/1 → 1/1 | 88,89% → 88,89% | 0 → 0 | 7/7 → 7/7 |
| C10 | PARTIAL → INTERRUPTED | 5/5 → N/A | 90,91% → N/A | 0 → N/A | 5/5 → N/A |

Trên **cùng hai câu evaluable C01/C07**: Numeric 8/8 giữ nguyên, numeric EM 2/2;
micro Claim F1 91,67% → **96,00%**, Precision 100%, Recall 11/13 → 12/13;
Answer Accuracy 0/2 → **1/2**; citation accuracy/completeness 16/16 → **18/18**.
Không so 96% của hai câu với 91,43% baseline ba câu như cùng mẫu; không báo bản cuối
đạt 13/13 hoặc Answer Accuracy 2/3. Reviewer vẫn là người triển khai, không đánh giá mù.

| Câu | Calls baseline → live gần nhất | E2E gồm setup baseline → live gần nhất |
| --- | ---: | ---: |
| C01 | 5 → **2** | 242,24s → **182,83s** (−24,53%) |
| C07 | 4 → **3** | 133,17s → **132,86s** (gần như không đổi) |
| C10 | 5 → 1 attempt lỗi | 210,99s → 66,89s tới interruption, **không so tốc độ** |

C01 hai calls là Supervisor và M6 semantic; các specialists dùng số/metric và
candidate quan sát có căn cứ. Tổng provider latency C01 162,14s → 69,67s;
E2E vẫn còn chi phí nạp catalog, replay/admission và nguồn. Một lượt trên hai câu
không đủ kết luận hiệu năng tổng quát; C07 chưa chứng minh giảm latency.

### Nguyên nhân và sửa kỹ thuật

- Aggregation lấy evidence theo inventory, trong khi owner và `analysis_premises`
  theo thứ tự IDs do specialist khai báo. Sai thứ tự gây false owner/item/period
  mismatch. Giữ thứ tự khai báo cho reasoning, không đổi nguồn hay giá trị.
- Supervisor chọn operands dù target là metric đã có, khiến LLM dựng lại công thức.
  Resolve target chính xác rồi đưa handle metric vào retrieval, dùng Calculator và
  numeric renderer hiện có. Chuẩn hóa yêu cầu thuần tính số khỏi cờ interpretation
  sai của model; yêu cầu nhận xét riêng vẫn giữ. Narrative references tới requirement
  IDs được mở rộng thành canonical operands đã resolve, không tự tạo chỉ tiêu.
- Calculator trước kiểm một reporting context cho toàn graph, làm hai nhánh độc lập
  doanh thu theo năm và tỷ số số dư cuối năm bị bác cùng nhau. V2 chỉ truyền operands
  thực sự dùng và kiểm context theo dependency của từng phép toán. Replay thật chấp
  nhận hai nhánh độc lập; control phép toán trộn stock/flow vẫn bị bác. Default cũ giữ.
- Qwen tiếp tục thêm “ổn định”, nhận định cao/thấp và số/phần trăm không có proof dù
  prompt cấm. Hai dạng yêu cầu có đủ nguồn — nhận xét sức khỏe tài chính và thanh khoản —
  dùng candidate quan sát từ dấu/quan hệ của facts, kỳ đo và giới hạn kết luận. Không
  có ngưỡng đánh giá hay dự báo. Candidate đi qua generator, M6 semantic và ledger
  hiện có; thiếu/khác kỳ/ambiguous sources hoặc mục tiêu ngoài phạm vi thì trả về
  generator cũ. Đây là xử lý có giới hạn, chưa chứng minh tổng quát hóa.
- M7 hiển thị phép tính đơn bước bằng câu tiếng Việt và bỏ phần công thức/operands
  lặp của approved metric; source facts và citations vẫn giữ. Không phát hành prose
  tự do chưa được M6 kiểm. Không thêm agent, đổi Gateway/EF-EG hoặc bật V2 mặc định.

**C01:** đủ doanh thu hai kỳ, tăng 26,71%, nợ/tài sản 59,06%, CFO dương; nhận xét
liên kết ba khía cạnh và nói rõ không dùng riêng một chỉ tiêu để kết luận toàn bộ
sức khỏe tài chính/xu hướng dài hạn. M6 ACCEPT 8, ABSTAIN 2; 8 ledger/released IDs,
coverage complete. Nhận xét mới qua M6 semantic, không nới gate để phát hành prose sai.

**C07 còn thiếu:** LNST và chính sách/ngoại lệ đúng, PDF7/12; scope note giữ yêu cầu
không suy số vốn hóa. Nhánh document hiện chỉ có exact-source claim/proof, không sinh
và kiểm chứng riêng giải thích “chính sách không xác định số vốn hóa thực tế”. Do đó
quotation vẫn dài, scope acknowledgement không được chấm thành gold atom còn thiếu.
Pipeline completed_with_caveats không đồng nghĩa QA PASS. Không thêm đường phát hành
paraphrase không được M6 kiểm để làm đẹp điểm.

### Giữ cả hồi quy và phần chưa xác nhận

Lượt đầu `9eb0951`: đủ ba final, **11 calls/38.489 tokens/0 provider errors**;
C01/C07/C10 lần lượt 198,13/101,44/152,32s, đều QA PARTIAL. Numeric **9/13**,
micro Claim F1 **77,42%**, citation 15/15, Answer Accuracy 0/3. C10 chỉ phát hành CFO
(1/5 numeric slots), không giữ được mức 5/5 của baseline; không che hồi quy này.
Supervisor khai đúng canonical nợ ngắn hạn trong requirement nhưng chọn sai source
handle, đồng thời đặt tên kết quả bằng chuỗi biểu thức chưa có trong catalog. Retrieval
không lấy operand đã khai; các phép tính không được tạo, fact tài sản ACCEPT cũng
không có binding để phát hành. Không phải M6 bác một phép tính đúng đủ nguồn.

Sửa tại `d5b91a7`: resolve/truy xuất canonical operands trước khi resolve tên kết quả
dynamic, giữ period/ambiguity guards; chuẩn hóa unit alias `lần` → `ratio`. Không suy
phép toán/tên chỉ tiêu từ giá trị. Control dynamic target chưa đăng ký, unit/period/
source/semantic requirement binding đạt. **Chưa có final C10 sau sửa**, vì lượt
`25f7316` dừng tại Supervisor timeout trước retrieval. Không chạy lượt thứ ba.

Lượt gần nhất: 6 attempts, 5 success + 1 timeout; **12.475 known tokens + 1 unknown**,
0 retry. Toàn phiên: **17 attempts/50.964 known tokens + 1 unknown**. Không sửa logic
hoặc gọi API sau khi quan sát timeout; chỉ hoàn tất chấm điểm, định dạng, tài liệu và bàn giao.

### Bằng chứng và nghiệm thu

41 targeted V2/M6/M7 PASS trên staged source `9eb0951`; sau sửa observation/branch
replay: 19 V2/M6 PASS trên staged source. Với `d5b91a7`: 16 V2 PASS working tree,
3 controls liên quan PASS staged (dynamic operand/semantic binding, numeric reuse,
readable arithmetic/observation guards). Real saved independent-branch arithmetic
ACCEPT và cross-stock/flow control không ACCEPT, 0 model calls. Runner lịch sử
`replay_v2_integration.py` dừng ở assertion cố định 3 tasks; không tính run đó là PASS.
Ruff/format, planning checker và diff checks được kiểm trước bàn giao; không full CI.

Artifacts ignored: `artifacts/evidence/V2-INT-01/qa-performance/`: `live/` và
`final-live/` giữ nguyên final answers, requests, raw responses, ledger và elapsed;
`*-Cxx-review.json`, `*-Cxx-metrics.json`, `*-summary.json`, `citation-audit.json` giữ
adjudication tái tính bằng `scripts/qa_metrics.py`; `offline-proof.json` giữ replay.
Citation audit đối chiếu document/snapshot/PDF page và released IDs, không nâng
page-level/uncertain thành cell-level. Credentials/dataset không stage hoặc commit.

**Next action duy nhất:** Tech Lead review thay đổi/metrics và giới hạn còn lại,
quyết định lượt xác nhận source `d5b91a7` khi Qwen sẵn sàng; dừng REVIEW.

## Phiên tiếp tục QA thực tế — 13/11/2026

**REVIEW**. Implementation đã kiểm chứng `b113136f876b7fa2c1411c8295e0a09cdb97220c`;
trực tiếp `main`, giữ V2 opt-in,
EF-EG, Calculator và M6. Các mục từ “Cải thiện QA thực tế” bên dưới là lịch sử,
không phải kết quả của source mới.

### Kết quả cuối trên cùng source

Qwen live hoàn tất C01/C07/C10 trên đúng SHA trên, **14 calls / 50.688 tokens API /
0 unknown / 0 retry / 0 provider errors**. Không sửa runtime sau lượt cuối.
Runner có final answers, ledger, raw provider events và exit 0 cho cả bộ ba.

| Câu | Gold QA | Numeric Accuracy / EM | Claim Precision / Recall / F1 | Citation Accuracy / Completeness | Answer Accuracy |
| --- | --- | --- | --- | --- | --- |
| C01 | PARTIAL | 7/7 / 1 | 9/9=100% / 7/8=87,50% / **93,33%** | 9/9 / 9/9 | 0 |
| C07 | PARTIAL | 1/1 / 1 | 7/7=100% / 4/5=80% / **88,89%** | 7/7 / 7/7 | 0 |
| C10 | PARTIAL | 5/5 / 1 | 5/5=100% / 5/6=83,33% / **90,91%** | 5/5 / 5/5 | 0 |

So với bộ B `9526fa0`, cùng Gold/rubric chấm lại: **Numeric Accuracy 5/13 → 13/13**,
numeric EM 1/3 → 3/3; **micro Claim Recall 8/19 → 16/19**, micro F1 **59,26% → 91,43%**.
Micro Precision giữ 100% (11/11 → 21/21); citation accuracy trên các mệnh đề đã phát
hành giữ 100%, C10 từ không có citation thành 5/5. **Answer Accuracy vẫn 0/3**.
C01 chỉ phục hồi mức F1 tốt nhất lịch sử 93,33% ở `474cc21`, chưa vượt mức đó.
Đây là 3 case đã biết, một lượt/source, không chứng minh tổng quát hóa hoặc lợi ích
Multi-Agent so với single-agent; không gọi toàn hệ thống đạt chất lượng tài chính.

| Câu | Calls | Tokens API | E2E runner, gồm setup catalog |
| --- | ---: | ---: | ---: |
| C01 | 5 | 21.053 | 242,24s |
| C07 | 4 | 7.733 | 133,17s |
| C10 | 5 | 21.902 | 210,99s |

Latency còn cao, chưa chứng minh cải thiện tốc độ. Toàn phiên tiếp tục này có
3 lượt đủ bộ: **41 calls / 137.347 tokens**, 0 unknown/retry/provider errors;
thêm một lần khởi động local lỗi cấu hình, 0 API. Không che lượt hồi quy ở bảng dưới.

- **C01:** final đủ doanh thu hai kỳ, tăng 26,71%, nợ/tài sản 0,59 lần và CFO dương.
  Gold tỷ trọng nợ 59,0584…% tương đương ratio 0,590584… được làm tròn 0,59;
  không bắt câu dài khớp nguyên văn. Còn thiếu tổng hợp. Model vẫn viết CFO “ổn định”
  từ một kỳ và đổi ratio proof thành %, đồng thời mixed annual/as-of reasoning còn
  lỗi owner/context (`dynamic_reporting_context_mismatch`, `reasoning_owner_mismatch`).
  Các candidate đó bị chặn; không giải quyết false narrative bằng cách nới M6.
- **C07:** final đúng LNST 7.249.557.946 VND và policy/ngoại lệ PDF12, giữ scope note.
  Không bịa số vốn hóa. Chưa có giải thích riêng “chính sách không xác định số vốn
  hóa thực tế”, quotation dài chưa thành diễn giải gọn đã kiểm chứng. Pipeline
  completed_with_caveats không được đổi thành QA PASS.
- **C10:** final có đúng vốn lưu động ròng **−600.656.455.132 VND**, current ratio
  **0,56 lần**, CFO **314.097.335.438 VND** và hai toán hạng; numeric bindings được M6
  xác nhận, hết rơi ACCEPT ở M7. Chưa có tổng hợp/giới hạn thanh khoản. Model viết
  “vốn lưu động ròng giảm… thanh khoản không cải thiện” khi không có kỳ gốc; nhận định
  đó không được phát hành. Mixed-period reasoning vẫn báo context/period-relation
  mismatch trước semantic pass; chưa chứng minh xử lý mọi nhận xét liên nhánh đúng.

Đã đối chiếu **21/21 claim citations** trong final với Gold document/snapshot/PDF
pages và released IDs: C01 PDF5/6/7/8, C07 PDF7/12, C10 PDF5/6/8. Đây là page-level,
không nâng `source_reference_uncertain` hoặc locator unresolved thành cell-level.
Source caveats vẫn hiển thị. Hai kết quả trung gian về doanh thu C01 đúng nhưng thừa;
gaps còn dài/lặp và cách trình bày vẫn thiên về biểu thức, chưa đạt độ tự nhiên mục tiêu.

Artifacts cuối: `qa-followup/verified-live/{manifest,results,provider-events}.json`,
`execution/Cxx.json`, `Cxx-answer.txt`; adjudication `final-Cxx-review.json`,
`final-Cxx-metrics.json`, `qa-summary.json`, `final-citation-audit.json` ở thư mục cha.
Có thể tính lại bằng `python scripts/qa_metrics.py <final-Cxx-review.json>`.
Gold/credentials/raw data không vào Git. Local edits ngoài task được giữ; phần sửa
riêng `specialist_common.py` chỉ stage callback của V2, không gom local prompt edits.

**Next action duy nhất:** Tech Lead nghiệm thu metrics/final answers và các giới hạn
tổng hợp, semantic binding, trình bày, latency trên source `b113136`; dừng REVIEW.

### Cách chấm được chuẩn hóa

Gold độc lập giữ nguyên 8/5/6 atomic requirements của C01/C07/C10, từ PDF đã đọc
trong E2E-GEN-01; không dùng M6 ACCEPT làm oracle. Rubric/Gold được đóng băng trước
provider call mới tại `qa-followup/gold.json`, SHA256
`665ce0ea0c78daa39b50cb798dd49a1ae9347906916a65fff34feb05203dd07c`.

Theo nguyên tắc câu trả lời số và scale trong
[metric chính thức TAT-QA](https://github.com/NExTplusplus/TAT-QA/blob/master/tatqa_metric.py),
phiên này chấm **các slot số** và mệnh đề tương đương về nghĩa. Đây là rubric nội bộ
cho 3 câu thực tế, không phải chạy benchmark TAT-QA/FinQA hoặc công bố điểm benchmark.
Không dùng EM nguyên văn cho đoạn trả lời dài; không dùng token-overlap F1 để thay
độ đúng của mệnh đề tài chính.

- Numeric Accuracy: slot tài chính đúng/slot số bắt buộc (C01=7, C07=1, C10=5).
  Numeric EM: toàn bộ slot số đúng, không có mệnh đề số sai được phát hành.
  Reviewer kiểm item/kỳ/scope; `Decimal` kiểm quy đổi VND/scale, percent↔ratio và
  làm tròn HALF_UP đúng độ chính xác hiển thị. Không có tolerance phần trăm tùy ý.
- Claim Precision: unique propositions đúng/unique propositions phát hành.
  Claim Recall: gold atoms thể hiện đúng/tổng gold atoms; F1 là harmonic mean.
  Gộp mệnh đề lặp; policy quotation có nhiều mệnh đề phải tách để chấm.
- Citation Accuracy: mệnh đề có citation hỗ trợ đúng toàn mệnh đề/tổng mệnh đề
  có citation. Citation Completeness: mệnh đề có nguồn đúng/tổng mệnh đề cần nguồn.
  Kiểm đúng tài liệu, snapshot và PDF page, gồm cả toán hạng của phép tính.
  Thiếu câu trả lời/citations không được coi là 100%; interruption không có final là N/A.
- Answer Accuracy vẫn là tiêu chí toàn câu nghiêm ngặt, gồm giới hạn/tổng hợp và
  citations; không đồng nhất với numeric EM hay trạng thái pipeline.

`scripts/qa_metrics.py` tính điểm từ adjudication có exact quote trong final answer,
Gold slot IDs, giá trị/đơn vị và nhận xét nguồn. Đây là chấm thủ công có kiểm tra số
và tái tính được; không tự động hiểu ngữ nghĩa hoặc tự chứng minh citation đúng.
Reviewer cũng là người triển khai, chưa có đánh giá mù độc lập. Ghi chú phạm vi do
user yêu cầu không là claim tài chính và không tự đáp ứng gold atom nhận xét/giới hạn.

### Nguyên nhân đã sửa và phạm vi kiểm chứng

- Rút gọn prompt V2 theo nhiệm vụ số liệu và tổng hợp; công bố root response schema,
  giữ schema analyses riêng. Tác vụ nhận xét chỉ yêu cầu một analysis liên nhánh.
- Qwen có thể đặt object `AnalysisProposal` đúng schema vào `claims`; trước đây nó
  bị loại như numeric proposal, làm mất cả phép tính đúng. V2 chuyển nguyên object
  đúng schema sang `analyses`, giữ raw response/trace, vẫn chạy grounding/Calculator/M6.
  Không sửa sai số, toán tử, kỳ hoặc IDs do model sinh; V1 không bật bước này.
- Mệnh lệnh thuần “Không suy ra/suy diễn/kết luận…” giữ như phạm vi trả lời, không
  thành một financial retrieval mới. M7 nhắc nguyên văn, không cấp claim/citation/
  coverage tài chính. C07 hết lỗi kỹ thuật do cố truy xuất phần bị cấm suy diễn.
- Notes do model viết trong proposal khai `claim_type=derived_fact` giữ ở raw trace, không kèm
  proof số học đã render: M6 kiểm số học không xác minh mệnh đề prose về thiếu dữ liệu.
  Caveats từ nguồn/tools vẫn giữ, limitations của reasoned conclusions vẫn qua M6.
- C10 có current ratio chưa được inventory đặt tên. Resolve canonical operands
  trước khi resolve tên kết quả; dynamic goal không mất chỉ vì thiếu catalog name.
  Source ambiguity, period/unit/operand guards giữ nguyên; binding vẫn cần M6 semantic
  support. Payload M6 dùng định nghĩa trong text/kỳ/unit/phép toán, không nhầm source
  anchor `current_assets` với tên kết quả “vốn lưu động ròng”. Whole-response goal giữ
  cả required operand indicators, gồm nợ ngắn hạn, thay vì chỉ union nguồn đại diện.
- Runner bỏ fingerprint ràng buộc endpoint cũ, archive `src` và helper scripts từ
  một SHA; chạy cả ba case trong một process, lưu JSON nguyên tử và elapsed/calls
  trong `finally`. Có fail-stop cho provider error, không retry/token pre-count.
  Tự giới hạn 8 calls/câu, 24 calls/lượt, 300s/request; ghi tokens do provider báo.

Khởi động đầu trên `53ca2a4` lỗi local do runner đặt 360s vượt contract 300s:
0 API calls, không phải Qwen FAIL. Sửa tại `1f458a8`, validate request trước chuẩn bị
catalog. Không xác định được nguyên nhân process lịch sử biến mất; phiên mới chỉ
chứng minh runner đã hoàn tất được bộ ba, không chứng minh chống được hard kill.

39 targeted tests trên isolated source trước normalization đạt; lần archive đầu
thiếu `configs` nên fixture lỗi, bổ sung đúng input rồi mới có 39 PASS. Sau normalization:
15 V2/M6 targeted PASS trên isolated staged source, bao gồm wrong value/unit/period/
source/operand controls; 3 tests runner/scoring đạt sau sửa deadline. Ruff/format đạt.
Source cuối: 16 V2/M6 targeted PASS trên isolated staged tree, thêm test dynamic goal
không có catalog name không được phát hành khi thiếu M6 semantic goal binding.
Planning checker đạt: 143 tasks trên working tree và 139 trên staged tree dùng checker
committed; chênh lệch là local edits ngoài task được giữ nguyên. Diff checks đạt;
local edits không liên quan giữ nguyên byte, phần local cũ trong shared module cũng
giữ nguyên sau khi trừ đúng callback mới. Không có supplied API key trong task diff.
Không chạy full CI/OCR/Gemini hoặc benchmark diện rộng.

Replay nguyên responses C01 của lượt `1f458a8` trên source normalization khôi phục
26,71%, 0,59 lần và CFO cùng facts nguồn; không sửa raw output. Một semantic request
mới không có saved response được để thiếu/INVESTIGATE, 0 API mới; không lấy replay
này làm bằng chứng synthesis đã đúng hoặc thay cho live.

### Giữ cả lượt hồi quy, không chọn riêng kết quả đẹp

Baseline so sánh là bộ cuối có đủ final answers trước phiên này: `9526fa0` (B).
Source `5f71772` cũ không có final nên không dùng làm baseline accuracy. Lượt đầu mới
`1f458a8` hoàn tất cả ba, 13 calls/38.461 tokens/0 unknown/0 retry/0 provider errors;
E2E case gồm setup catalog: C01 214,06s, C07 108,01s, C10 174,81s.

| Source/câu | Numeric Accuracy | Numeric EM | Claim P/R/F1 | Citation Accuracy | Answer Accuracy |
| --- | --- | --- | --- | --- | --- |
| B / C01 | 4/7 | 0 | 100% / 50% / 66,67% | 4/4 | 0 |
| B / C07 | 1/1 | 1 | 100% / 80% / 88,89% | 7/7 | 0 |
| B / C10 | 0/5 | 0 | 0% / 0% / 0% | N/A | 0 |
| 1f458a8 / C01 | 1/7 | 0 | 100% / 12,50% / 22,22% | 1/1 | 0 |
| 1f458a8 / C07 | 1/1 | 1 | 100% / 80% / 88,89% | 7/7 | 0 |
| 1f458a8 / C10 | 1/5 | 0 | 100% / 16,67% / 28,57% | 1/1 | 0 |
| 4ca965c / C01 | 7/7 | 1 | 81,82% / 87,50% / 84,56% | 9/9; completeness 9/11 | 0 |
| 4ca965c / C07 | 1/1 | 1 | 100% / 80% / 88,89% | 7/7 | 0 |
| 4ca965c / C10 | 1/5 | 0 | 100% / 16,67% / 28,57% | 1/1 | 0 |

Lượt trung gian `4ca965c` khôi phục số C01 nhưng còn 2 mệnh đề data-availability trong
notes chưa được kiểm chứng, đếm một lần dù xuất hiện lặp. Không bỏ chúng khỏi mẫu số
Precision hoặc gọi citation accuracy 9/9 là toàn câu grounded. Đó là lý do tách model
notes khỏi pure numeric proofs. C10 có 5 numeric ACCEPT nhưng chỉ CFO được render:
working-capital semantic verdict thiếu supported IDs, current-ratio goal mất target;
không cộng những ACCEPT không xuất hiện trong final vào Recall.

Lượt đầu cho thấy rút gọn prompt đơn thuần chưa đủ: Qwen tiếp tục sai envelope,
thêm số sai 26,4% hoặc diễn giải “phục hồi mạnh”, “sinh tiền tốt” thiếu chuẩn.
Final C01/C10 chỉ còn CFO; không gọi đây là tiến bộ QA. C07 pipeline completed
nhưng chấm PARTIAL: quote chính sách còn dài, scope note chưa giải thích giới hạn
xác định số vốn hóa. Kết quả/source/Gold/review/raw responses được giữ riêng ở
`artifacts/evidence/V2-INT-01/qa-followup/`, ignored; không commit credentials/dataset.

## Cải thiện QA thực tế — kết quả và giới hạn bàn giao

**REVIEW**, 13/11/2026. Source cuối: `5f717726f0e16010f1ce7a3335f249fa7ca369a3`,
trực tiếp main; `integration_v2` opt-in. **Chưa đạt QA đầy đủ và chưa có xác nhận
end-to-end hoàn tất trên SHA cuối.** Không lấy tests PASS/M6 ACCEPT làm chất lượng QA.

### Code đã sửa trong V2 hiện tại

- M5 giữ original question và `answer_goal` riêng cho số liệu, phân tích, tổng hợp,
  giới hạn. Nếu plan chỉ có số, giữ thêm nghĩa vụ gốc và giao task phụ thuộc cho một
  specialist hiện có. Shared proofs được rút gọn trong prompt; không thêm agent.
- `integration_plan` chuẩn hóa shorthand calculation/analysis/synthesis/limitation
  về schema hiện có; dependency task IDs không dùng làm sources. Alias chỉ tiêu rõ
  trong câu hỏi được bổ sung khi đúng một nguồn/năm xác định được; không đoán source.
  Không biến năm model tự thêm thành yêu cầu bắt buộc khi câu hỏi không yêu cầu so sánh.
- `resolve_requirements/run` lấy operand periods từ metric inventory, giữ cột so sánh
  dù Qwen bỏ reasoning_periods. Proof canonical có thể đáp ứng numeric goal ở task khác;
  ownership của nhận xét và M6 semantic coverage vẫn được giữ.
- M6 tiếp tục canonical replay/value/unit/period/type/snapshot/source/citation checks.
  Nhận xét độc lập nhiều kỳ không bị bắt buộc có phép tính khi không tự tính số mới;
  arithmetic vẫn replay riêng. Named dynamic goals phải có semantic goal support;
  intermediate outputs đã replay được xét đúng unit. Ví dụ JSON M6 V2 giữ rõ field
  `supported_requirement_ids`, không còn mâu thuẫn với hướng dẫn bổ sung phía sau.
- API phân biệt ngày suy từ câu hỏi và period caller pin tường minh: V2 không áp ngày
  suy ra cho toàn bộ annual/as-of claims. Explicit period pin vẫn được kiểm tra.
- M7 gộp nguyên dòng text/proof trùng theo source scope, nhóm theo verified bindings,
  giữ claim IDs/citations. Chỉ phát hành bound claims và fact operands của chúng;
  không phát hành cả inventory chỉ vì từng fact ACCEPT. Không tạo prose tài chính
  mới hoặc dùng M7 để kiểm chứng tài chính lần hai.

Các đoạn chính: `lite_orchestrator.integration_plan/preserve_answer_goal/
preserve_explicit_facts/retain_requested_periods/run/_specialist`,
`integration_workspace.matches_requirement/export`, `validators._reasoning`,
`lite_runtime.verify/_semantic`, `financial_qa_pipeline.execute`,
`qa_lite._group_verified_segments/compose_lite`. Contracts sidecar ghi tại
[data-contracts](data-contracts.md). Không sửa OCR, EF-EG, Financial Tools hoặc default V1.

### QA live đã thực sự chạy

Mỗi lượt dùng Gateway Qwen thật, cùng model/endpoint/key; không retry, không token
pre-count/cap. Giữ6calls/câu,18calls/bộ3câu,300s/câu. PARTIAL/FAIL tiếp tục câu kế;
chỉ dừng provider/hạ tầng. Không dùng saved responses thay kết quả live.

| Lượt / source | C01 | C07 | C10 | Calls / tokens API |
| --- | --- | --- | --- | --- |
| A / d0f0e7c | PARTIAL | PARTIAL | FAIL, internal_error | 12 / 36.927 |
| B / 9526fa0 | PARTIAL | PARTIAL | FAIL, verification_blocked | 16 / 57.305 |
| C / 5f71772 | INTERRUPTED, chưa final | NOT_RUN sau điểm dừng | NOT_RUN sau điểm dừng | 5 / 20.703 |

Tổng phiên **33calls,114.935tokens API báo,0usage unknown,0retry,0provider errors
quan sát được**. Hai lượt đủ bộ được giữ nguyên, không chỉ chọn lượt đẹp. Lượt C
không kết thúc: sau5provider responses thành công không còn process runner và chưa
có `execution/C01.json`/final answer. State cuối còn IN_PROGRESS; khi resume đã kiểm
không có process và ghi STOPPED/INTERRUPTED, giữ bản state trước đó. **Nguyên nhân
process biến mất chưa xác định; không gọi đây là API timeout.** Dừng theo điều kiện
hạ tầng, không chạy lại C01 hoặc gọi tiếp C07/C10 trên SHA cuối.

### Metrics theo final answer, không theo ledger

Rubric đóng băng trước live: C01 có8gold atoms, C07 có5, C10 có6. Answer Accuracy
là binary đủ toàn câu (số, ý, nhận xét/giới hạn, citations, không suy diễn).
Precision=unique claims phát hành đúng/unique claims phát hành; Recall=gold atoms
được đáp ứng/tổng atoms; F1=harmonic mean. Không đếm lặp, bibliography/caveats kỹ thuật.
Empty technical answer của một QA đã chạy chấm0; transport/process interruption
không có final chấmN/A. Ratio/percent tương đương với làm tròn đúng precision được phép.

| Source / câu | Answer Accuracy | Claim Precision | Claim Recall | Claim F1 |
| --- | --- | --- | --- | --- |
| A / C01 | 0/1 | 5/5=100% | 5/8=62,50% | 76,92% |
| A / C07 | 0/1 | 22/22=100% | 4/5=80% | 88,89% |
| A / C10 | 0/1 | 0 (empty) | 0/6=0% | 0% |
| B / C01 | 0/1 | 4/4=100% | 4/8=50% | 66,67% |
| B / C07 | 0/1 | 7/7=100% | 4/5=80% | 88,89% |
| B / C10 | 0/1 | 0 (empty) | 0/6=0% | 0% |
| C / C01,C07,C10 | N/A | N/A | N/A | N/A |

**Không có bằng chứng live chất lượng tăng so với baseline C01 F1=93,33%.**
Lượt B còn hồi quy phát hành do binding ownership/semantic contract; đã sửa code
ở6d3f834/5f71772 nhưng lượt C bị ngắt trước final. Replay không sửa raw responses
trên code mới khôi phục growth26,71% và hai revenue facts; đây là **offline evidence**,
không thay thế QA live của bản cuối. C07 Precision cao không đồng nghĩa gọn/đủ ý:
lượt A có14facts ngoài mục tiêu (grounded nhưng thừa), lượt B đã bỏ chúng và bỏ năm2024
không được hỏi. Claim counts C07 tách6policy propositions,1LNST2025; lượt A thêm
LNST2024 và14balance facts. Không dùng số M6 ACCEPT làm tử số Precision.

### Nguyên nhân QA còn thiếu, có trace đối chiếu

- **C01 A:** supervisor phát shorthand schema sai; model bỏ operand periods; backend
  thiếu revenue2024 dù inventory có. Các model analyses sau đó khẳng định thiếu dữ liệu
  hoặc dùng số/đơn vị sai, bị chặn. Không có tổng hợp hợp lệ.
- **C01 B:** đã truy xuất đủ revenue2025/2024, debt/assets/CFO. Task tổng hợp vẫn trả
  các analyses riêng: ghi growth26,6% thay26,71%; đổi ratio thành59,06%; nhận xét CFO
  “ổn định” không đủ evidence. Chúng không thành nhận xét tổng hợp có M6 support.
  Growth proof26,71% đúng được sinh tại task tổng hợp nhưng ownership cũ không bind
  sang R002, nên M7 scope filtering loại cả growth/revenue operands. Đã sửa export
  cho numeric cross-task; không tự cho các nhận xét sai ACCEPT.
- **C07:** đúng LNST2025=7.249.557.946VND và literal policy đầy đủ điều kiện/ngoại lệ.
  Fusion Qwen tách “Không suy ra số lãi vay vốn hóa thực tế…” thành một financial
  subrequest unsupported thay vì giữ như ràng buộc nội dung. Lượt B không còn phát
  hành inventory balance ngoài mục tiêu, nhưng vẫn chưa có claim giới hạn được bind;
  final báo thiếu phần này. Mixed negative constraints chưa được xử lý trọn vẹn.
  Policy còn là quotation dài, chưa có diễn giải ngắn đã M6 xác minh.
- **C10 A:** kind calculation/synthesis/limitation làm toàn plan fail schema. B đã
  chuẩn hóa, lấy assets767.374.839.317VND, liabilities1.368.031.294.449VND và đúng CFO
  314.097.335.438VND; có proof working capital−600.656.455.132VND/current ratio0,56lần.
  Final B vẫn không phát hành: Qwen M6 bỏ supported_requirement_ids; period từ ngày
  trong câu hỏi còn làm CFO annual ABSTAIN. Intermediate-unit/ownership cũng cản goal
  đầu trong proof nhiều outputs. Đã sửa các boundary này ở code cuối; chưa live xác
  nhận bản cuối do process bị ngắt. Không suy rằng solvency future đã được chứng minh.

### Agents/tools và citations quan sát ở lượt B

| Câu | Provider stages thực gọi | Tools thực gọi |
| --- | --- | --- |
| C01 | Supervisor1; liquidity2 (gồm follow-up); profitability1; cash-flow1 | get_financial_fact5; get_evidence_sources5 |
| C07 | fusion-planner1; Supervisor2; profitability1; M6 Lite1; document-planner1 | get_financial_fact15; get_evidence_sources20; search_document_evidence4; get_graph_context1 |
| C10 | Supervisor1; liquidity2; cash-flow1; M6 Lite1 | get_financial_fact4; get_evidence_sources4 |

M7 V2 deterministic, không có Qwen M7 call. C01 B phát hành nợ/tài sản/CFO với PDF6/5/8
đúng, nhưng mất doanh thu/growth PDF7 ở output; không tính retrieval page như released
citation. C07 B chỉ còn PDF7 cho LNST và PDF12 cho policy, đúng document/snapshot và
binding. C10 B không có released claims/citations, nên citation quality N/A, không báo
PASS chỉ vì tools lấy được trang. Tất cả provenance vẫn page-level, chưa cell-level.

Artifacts riêng ignored `artifacts/evidence/V2-INT-01/qa-quality/`: từng lượt giữ
provider events, execution/ledger, nguyên văn `Cxx-answer.txt`, Gold và review JSON;
lượt C giữ5raw responses và trạng thái interruption. Không overwrite các evidence cũ.
37targeted PASS trên source stage9526fa0,1shared-owner test sau đó; **15targeted PASS
trên source bàn giao5f71772** (V2 integration/M6 Lite và embedded-proof/citation control).
Không full tests/CI/OCR/Gemini/benchmark. Planning/diff/Ruff đạt.

**Next action:** Tech Lead/Owner review các kết quả QA và interruption trước khi quyết
định việc xác nhận live tiếp; dừng REVIEW, không tự mở task/milestone hoặc vòng chạy mới.

## QA live thật sau sửa runner — C01 PARTIAL, dừng trước C07

**REVIEW**, 13/11/2026. Theo chỉ đạo mới, `scripts/validate_v2_live.py` bỏ hoàn toàn
pre-count/token reservation và giới hạn tổng token cứng; chỉ cộng usage API nếu có,
ghi số calls usage unknown riêng. Vẫn6calls/câu,12calls tổng,300s/câu, không retry.
Source được archive trực tiếp từ implementation **`474cc218498512748aaaa96ab463c070b27f9228`**;
không sửa M5/M6/M7, không dùng local runtime ngoài commit. Giữ nguyên fingerprint
model/endpoint/key của cấu hình Owner đã cấp. Credentials qua stdin, không ghi traces.

**C01 đã chạy Qwen thật một lượt:5calls thành công,26.599tokens API báo,0unknown,
0retry,130,06s pipeline.** Các stages: supervisor, liquidity, profitability, cash-flow,
M6; không gọi Qwen M7 vì V2 trình bày deterministic. Không dùng saved provider responses
để thay kết quả. Chỉ lấy lại nguyên question/context và Gold references đã đóng băng.

Pipeline trả `completed_with_caveats`,10ACCEPT/10ledger entries/10released IDs,
coverage3/3numeric requirements satisfied, không errors/gaps. **Đánh giá độc lập câu
trả lời cuối là PARTIAL**: có đủ số và citations, thiếu nhận xét tổng hợp ba nhánh
có giới hạn. Đã dừng theo điều kiện6 của Owner; **C07 NOT_RUN**, không tự gọi tiếp,
sửa runtime hoặc chạy lại C01. Không gán pipeline status/M6ACCEPT thành QA accuracy.

### Gold và metrics theo câu

Rubric đóng băng trước call đầu trong `live-qa-gold-rubric.json`. Answer Accuracy
là exact full-answer accuracy:1 chỉ khi đủ nội dung, nhận xét/giới hạn, số và citations
đúng, không suy diễn; còn lại0. Đây là chấm một câu, không phải accuracy thống kê
trên dataset. Precision = claims tài chính/chính sách phát hành đúng và grounded /
tổng claims phát hành; Recall = gold atomic claims được thể hiện / tổng gold atoms;
F1 là harmonic mean. Gộp claims lặp, không đếm caveats kỹ thuật/bibliography.

| Câu | QA verdict | Answer Accuracy | Claim Precision | Claim Recall | Claim F1 |
| --- | --- | --- | --- | --- | --- |
| C01 | PARTIAL | 0/1 =0% | 9/9 =100% | 7/8 =87,50% | 93,33% |
| C07 | NOT_RUN do fail-stop C01 | N/A | N/A | N/A | N/A |

C01 gồm7gold atoms về số liệu/phép tính và1atom nhận xét tổng hợp có giới hạn.
Cả7atoms số đạt: doanh thu2025/2024=450.474.531.227/355.507.372.286VND,
tăng26,71%; nợ157.146.559.558VND/tài sản266.086.680.765VND tại2025-12-31;
CFO dương14.319.681.754VND. Gold tỷ trọng nợ59,05840875%≈59,06%; proof live
0,5905840875… đúng, output0,59lần là làm tròn2chữ số ở đơn vị ratio, được chấp nhận
theo rubric đơn vị/độ chính xác hiển thị đã đóng băng; không giả output đã in59,06%.

Hai claims đúng ngoài7atoms số: tỷ trọng nợ mô tả mức phụ thuộc vào nợ (không gán
ngưỡng cao/thấp), và CFO dương thể hiện tiền tạo ra từ hoạt động kinh doanh **trong
năm2025** (không suy khả năng tương lai hay sức khỏe toàn diện). Vì vậy9unique emitted
claims được đánh giá đúng,0unsupported; duplicate formula/value chỉ tính một lần.
Đây là chấm theo Gold/nguồn và phạm vi nội dung, không lấy10M6ACCEPT làm tử số.

Citations khớp cùng document/snapshot: [1]PDF7 cho doanh thu/tăng trưởng, [2]PDF8
cho CFO, [3]PDF6 cho nợ, [4]PDF5 cho tài sản; ratio dẫn [3][4]. Chỉ có page-level
provenance, không tuyên bố cell-level. Hai trong ba required-point groups đầy đủ;
groupCFO/tổng hợp mới có CFO, chưa có tổng hợp giới hạn. Caveat nguồn chung không
thay thế nhận xét tài chính được hỏi. Chưa đủ cơ sở chấm C07, không điền0 hay suy PASS.

### Nguyên văn câu trả lời cuối C01

> (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. [1]
>
> Lưu chuyển tiền thuần từ hoạt động kinh doanh kỳ 2025 là 14.319.681.754 VND. [2]
>
> Tỷ trọng nợ trong tài sản cuối năm 2025 được tính bằng tỷ lệ giữa tổng nợ phải trả và tổng tài sản. Tỷ lệ này cho thấy mức độ phụ thuộc vào nợ của doanh nghiệp.
> Tổng nợ phải trả (kỳ 2025-12-31) / Tổng tài sản (kỳ 2025-12-31): 0,59 lần (tỷ số đối chiếu). [3][4]
>
> Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. [3]
>
> Dòng tiền thuần từ hoạt động kinh doanh năm 2025 là 14.319.681.754 VND, cho thấy khả năng sinh tiền từ hoạt động kinh doanh chính của doanh nghiệp trong năm 2025. [2]
>
> Tổng nợ phải trả (kỳ 2025-12-31) / Tổng tài sản (kỳ 2025-12-31): 0,59 lần (tỷ số đối chiếu). [3][4]
>
> Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. [4]
>
> Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. [1]
>
> Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [2] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [3] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [4] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### Nguyên nhân chính xác và điểm dừng

1. Raw supervisor live chỉ tạo3requirements tính nợ/tài sản, tăng trưởng doanh thu
   và CFO; không tạo synthesis/limitation requirement hoặc dependent synthesis task.
   `lite_orchestrator._specialist` nhận assigned requirements và đặt user_question
   bằng task.objective; ba responses chỉ có phân tích riêng, không có candidate tổng hợp.
2. M6 đã ACCEPT các nhánh số/nhận xét riêng có căn cứ. M7 dùng đúng bindings3mục
   nên coverage.complete=True; inventory của plan thiếu mục tiêu Gold tổng hợp.
   V2 M7 không tự sinh nhận xét tài chính mới, nên final vẫn thiếu mục tiêu này.
   Đây là thiếu goal/candidate tổng hợp, không phải mất ledger release hay lỗi kỳ.
3. Phép tăng trưởng26,71% đã còn một lần. Ratio0,59lần vẫn lặp: một segment gồm prose
   +proof và một segment proof riêng. Dedup trong `qa_lite.compose_lite` khóa theo
   **toàn segment text+scope**, nên không gộp proof nằm bên trong hai segment khác nhau.
   Đây là giới hạn presentation quan sát được; không sửa tiếp trong lượt QA này.

Artifacts ignored `artifacts/evidence/V2-INT-01/live-qa-474cc21/` giữ provider requests/
raw responses, `execution/C01.json`, `C01-answer.txt` nguyên byte UTF-8, Gold references,
`C01-review.json`, `C07-review.json`, manifest và STOPPED results. Không sửa evidence cũ.
Đã kiểm Ruff/compile runner, planning và diff; không chạy lại unit/full tests, CI,
benchmark, OCR hoặc Gemini. Runtime giữ nguyên `474cc21`, `integration_v2` vẫn opt-in.

**Next action:** Tech Lead/Owner review C01 live PARTIAL và quyết định bước tiếp theo;
không tự mở FIX, chạy lại C01 hoặc gọi C07 sau điểm dừng.

## Lượt xác nhận được Owner cấp phép — dừng trước API

**REVIEW — chưa có kết quả Qwen mới**, 13/11/2026. Owner cấp đúng một lượt
C01/C07, tối đa6calls/câu,12calls/60.000tokens tổng; C10 hoãn. Giữ model,
endpoint/key và generation/timeout hiện có; không retry, lỗi hoặc PARTIAL/FAIL thì dừng.
Source chạy được đóng băng từ main `811112a08c9f0d9cad9f37f5123c0c30aa4ecad3`,
implementation `474cc218498512748aaaa96ab463c070b27f9228`; không dùng local runtime ngoài commit.

**Lượt này chưa gửi request tới Qwen:0API calls,0tokens; C07 chưa chạy.**
Runner bổ sung bước đếm input tokens bằng cached Qwen tokenizer qua subprocess local
để reserve ngân sách trước mỗi call. Subprocess này vượt timeout45giây trước khi
gateway gọi provider. Pipeline bắt Exception và ghi `m5:TimeoutExpired`, trả
`provider_unavailable`,0released claims; elapsed case51,76giây. Đây là lỗi runner
kiểm thử trước API, **không phải API timeout và không phải verdict FAIL chất lượng Qwen**.
Không có provider response, M6 decision hoặc câu trả lời tài chính mới để đánh giá.

Đã dừng ngay khi thấy kết quả lỗi; không chạy C07, không sửa runner/runtime để rerun.
Ngân sách API chưa sử dụng. Không chạy lại offline tests, OCR, benchmark hoặc CI.
Artifacts riêng ignored: `artifacts/evidence/V2-INT-01/live-confirmation-20261113/`;
`results.json`, `execution/C01.json`, manifest và `provider-events.json=[]` giữ bằng chứng.
Credentials chỉ truyền trong bộ nhớ/stdin, không ghi file/traces. Planning/diff checks đạt.

**Next action:** Owner/Tech Lead review lỗi runner trước API và quyết định bước tiếp theo;
không kết luận các sửa đổi đã được live Qwen xác nhận.

## Bổ sung sửa source, claim-local period và coverage — 13/11/2026

**REVIEW**, implementation `474cc218498512748aaaa96ab463c070b27f9228`, base `68c22ee` trên main;
`integration_v2` vẫn opt-in. Owner giao sửa tiếp đúng V2-INT-01, không mở task/nhánh,
không gọi Qwen. Các phần phía dưới giữ bằng chứng lịch sử của lượt live trước sửa.

### Nguyên nhân và code sửa

- `lite_orchestrator.resolve_source/resolve_requirements/run`: source lookup cũ chỉ
  nhận S handles; requirements lại dùng chính handles như canonical target. Python
  nay resolve handle/canonical item trong inventory đã ghim company/document/snapshot/
  reporting scope, chọn đúng kỳ từ assigned requirements và operand periods. Không
  dùng requirement ID làm source ID; unknown, period mismatch và ambiguous có reason
  riêng, không chọn một record tùy ý. Metric inventory cần operands cùng pinned scope.
  Role không cấm đọc nguồn hợp lệ của domain khác. Giữ requirement IDs/text và refs.
- `integration_workspace._matches_metric_expression/matches_requirement/export`:
  normalize targets/indicators trước binding; đối chiếu cấu trúc biểu thức với
  definition và ordered canonical operands/kỳ trong inventory, cùng requested unit.
  Vì vậy percentage_change hợp lệ có thể đáp ứng revenue_yoy, nhưng quotient của chỉ
  tiêu khác, đảo operands hoặc sai kỳ/đơn vị không đáp ứng. Không thêm formula/policy.
  Scalar retrieval bị model gắn nhầm kind=metric/interpretation được chuẩn hóa tại M5;
  yêu cầu diễn giải rõ ràng vẫn cần semantic support.
- `validators._requested_periods/_context/_reasoning`: V2 dùng kỳ của claim và sources,
  thay comparison periods của toàn câu. Vẫn kiểm canonical period/type, exact request
  pins, company/document/snapshot/scope, values/units, operands và citations. Legacy
  giữ cách kiểm cũ. `lite_runtime.verify` giữ binding của derived proof đã ACCEPT mà
  không đòi thêm semantic verdict; diễn giải vẫn đi cùng semantic batch hiện có.
- `qa_lite.compose_lite`: chỉ với V2 sidecar, gộp segments có cùng nội dung và scope;
  hợp nhất claim IDs/citations, giữ các findings khác nhau. M7 chỉ chiếu binding từ
  verified claims thực sự phát hành, không diễn giải lại requirement hay kiểm tài chính.

### Raw replay trước/sau

Runner `scripts/replay_v2_raw.py` dùng **nguyên response** trong
`qa-completion/live/provider-events.json` cho C01/C07, chạy lại pipeline thật bằng
SavedGateway chỉ đọc file, không tạo provider adapter. Không sửa Qwen output, thêm
verdict còn thiếu hoặc thay response bằng fixture. Trước là execution đã lưu cùng
lượt live; sau là replay trên source đã stage riêng, tách khỏi local runtime ngoài task.

| Case | Trước | Sau offline |
| --- | --- | --- |
| C01 | 7 ACCEPT / 6 ABSTAIN / 1 INVESTIGATE, 6 unique releases; 3 requirements unverified; 26,71% lặp 3 lần | 11 ACCEPT / 1 ABSTAIN / 2 INVESTIGATE, 9 unique releases; 3 numeric requirements satisfied; 26,71% đúng 1 lần |
| C07 | 0 financial facts retrieved; 1 document ACCEPT/release PDF12 | LNST2025 và2024 được resolve/truy xuất đúng; 2 financial facts ACCEPT từ numeric fallback V2 sẵn có, cộng đúng document ACCEPT cũ; citations PDF7/12 |

C07 không giả Qwen sinh numeric claims mới: hai responses specialist gốc vẫn claims=[],
khai thiếu dữ liệu và analyses hỏng schema. Chỉ numeric source fallback **đã có từ trước**
mới tạo candidates qua M6 sau khi retrieval được sửa; absence prose không được phát hành.
Requirement2024 do model thêm vẫn còn, chưa sửa planning ngoài ba nguyên nhân được giao.

| C01 candidate (suffix) | Trước → sau | Ý nghĩa |
| --- | --- | --- |
| `eb85321eafb8cfc367d7fb9a` | ABSTAIN → ACCEPT | Nợ phải trả tại2025-12-31 |
| `37663657fb14968dbe7421b2` | ABSTAIN → ACCEPT | Tổng tài sản tại2025-12-31 |
| `f3d5f7da6c87b5bccc13935f`, `01912929fd8e191bf2d18c29` | ABSTAIN → ACCEPT | Hai candidates cùng phép nợ/tài sản; một ledger identity/paragraph |
| `af00458bddec0650bff909df` | ABSTAIN → INVESTIGATE | Hết lỗi kỳ; response M6 cũ không có verdict cho claim này, không tự bổ sung |
| `2285c67b1361fd374c95e34f` | ABSTAIN → ABSTAIN | Prose59,06% dùng proof ratio; vẫn unbound number/unit |

| Binding | Trước | Sau |
| --- | --- | --- |
| C01 R001 | S34, indicators S11/S9; không binding | debt_to_assets, total_liabilities/total_assets; verified derived ratio đã render |
| C01 R002 | S35, indicators S15/S16; không binding | revenue_yoy, net_revenue với đúng2025/2024; verified percentage_change đã render |
| C01 R003 | S25, kind metric; không binding | b03.operating_cash_flow, kind fact, kỳ2025/VND; verified CFO fact đã render |
| C07 R1:R001/R002 | canonical target có nhưng sources canonical bị loại; không binding | sources resolve đúng2025/2024; hai verified LNST facts đã render |
| C07 R2/R2:R1 | document ACCEPT đã phát hành | Giữ nguyên verified ID và citation PDF12 |

C01 vẫn `partial_verified_coverage`: thiếu semantic verdict gốc cho claim nợ mới qua
deterministic gates được ghi technical error; CFO inference vẫn INVESTIGATE. Cả ba
numeric rows satisfied không đồng nghĩa đã có nhận xét tổng hợp đầy đủ. C07 replay
`completed_with_caveats` không chứng minh Qwen sẽ tự dùng nguồn mới hoặc giữ negative
constraint trong một lượt mới. Chưa xác nhận synthesis/constraint hoặc live quality.

### Kiểm chứng và giới hạn bàn giao

- Source stage riêng: **46 targeted PASS, 1 deselected** qua V2 integration, M5/M6 Lite,
  M7 Lite và comparative-period controls. Ba tests mới kiểm source variants/pins/role,
  công thức/ordered operands/units/kỳ/goal và claim-local negative controls. Đây là
  counterfactual fixtures kiểm logic, tách biệt raw replay nêu trên.
- Test deselected `test_m7_restores_omitted_accepted_comparison_without_new_verification`
  đã FAIL cả với `qa_lite.py` trước task: restored_calculation_claims rỗng khi test mong
  một ID. Giữ nguyên test, không sửa lỗi ngoài scope; không báo toàn suite xanh.
- Saved C04: ba absence claims không ACCEPT khi retrieval chưa đủ. Saved C10: hai
  proofs đúng và current-assets fact ACCEPT, phép trừ sai không ACCEPT. Không live C10.
- Controls sai giá trị, nguồn, company/document/snapshot, kỳ/type, unit, thiếu citation,
  tên chỉ tiêu và đảo operands vẫn bị chặn; ambiguous source giữ unresolved.
- Raw provider/execution inputs giữ nguyên; artifacts mới riêng tại
  `artifacts/evidence/V2-INT-01/source-period-coverage/staged-raw/`. Không OCR/Gemini,
  benchmark, full CI hoặc dataset/hash audit diện rộng. Không ghi/lưu API key.
- Ruff lint/format, planning checker và diff check đạt. Source ngoài task giữ local;
  không gom dataset, notebooks hoặc credential/config vào commit. Các SHA verified IDs
  mới phụ thuộc history/input digest; report JSON giữ toàn bộ bindings để đối chiếu.

**Next action:** Tech Lead/Owner review bằng chứng offline và quyết định có cấp phép
một lượt live xác nhận; chưa gọi Qwen và không tự nghiệm thu DONE.

## Lịch sử QA trước lần sửa này

**REVIEW — chờ Tech Lead nghiệm thu**, 13/11/2026 (Asia/Bangkok).
Implementation: `2783e7dd71b1a53db91c1a363d757fff67630622`, baseline main
`8b669be77f209a8cc0a6fb56ab36fa906a940092`. Tiếp tục V2-INT-01 theo Owner,
không tạo nhánh/task FIX mới; `integration_v2` vẫn opt-in.

**Kết quả QA thật: C01 PARTIAL, C07 PARTIAL, C10 INTERRUPTED do API timeout.**
11provider attempts,10success; **35.653tokens đã biết +1call usage unknown**,
0retry. Đã dừng ngay tại timeout, không gọi tiếp và không sửa runtime sau live.
C07 không còn mất document ACCEPT ở root, nhưng yêu cầu financial+document đầy đủ
chưa đạt vì financial retrieval không được thực hiện. Không báo GO/QA PASS.

## Thay đổi đúng phạm vi

`src/api/fusion_pipeline.py::compose_fusion_v2` nối **exact child released IDs**
với current verified ledger theo company/document/financial snapshot hoặc document
composition pins. Bỏ lookup lại target từ câu hỏi ở bước tổng V2; parent và child
requirement IDs được namespace để tránh va chạm. Claim hợp lệ tiếp tục phát hành
khi requirement khác thiếu; coverage vẫn giữ các phần chưa đáp ứng.

`src/outputs/qa_lite.py` tái dùng rendering/citation projection cho cả financial
và document ACCEPT. Chỉ hiển thị content/proofs đã admit, không sinh số hoặc nhận
định mới. Không đổi M6, Ledger, policy, OCR, EF-EG hoặc Financial Tools; không thêm
verifier/firewall. Legacy fusion giữ path cũ, V2 dùng M7 Lite đã có.

`src/agents/qa_planning.py::plan_fusion` làm rõ phân loại policy/điều kiện/ngoại lệ
vào document lane và gom cùng chủ đề, thay vì tạo nhiều financial subrequests cho
chính sách. Không hardcode case, số liệu hoặc nguồn của C01/C07/C10.

## Offline trước live

- Saved-data replay C01 giữ3task/assignments và7shared evidence identities;
  fixture requirement IDs được gắn nhãn counterfactual, không giả Qwen đã sinh chúng.
- C04 ba absence claims không ACCEPT; C10 hai proofs đúng và current-assets fact
  ACCEPT, phép trừ model sai không ACCEPT. Kiểm giá trị/đơn vị/kỳ/nguồn giữ nguyên.
- C07 replay nguyên document history trước đây: ID ACCEPT được khôi phục ở root,
  citation PDF12. Ghép deterministic financial counterfactual cho thấy cả financial
  và document citations PDF7/12; không phải lời hứa model sẽ chọn đúng nguồn.
- Control mixed mới giữ child releases dù parent target khác; ID không tồn tại
  trong current ledger không được phát hành; phần đúng được giữ khi có lỗi/thiếu.
- 22historic ledger entries serialize/replay nguyên vẹn;607non-runtime protected
  files unchanged; source JSON E2E không ghi đè. Kết quả mới ở
  `artifacts/evidence/V2-INT-01/qa-completion/`, không commit dataset/credentials.
- Run đầu:6PASS/1FAIL do fixture dùng model_copy với model dict chưa deserialize;
  đã sửa fixture, control mixed1PASS. Nhóm targeted cuối27PASS; Ruff lint/format,
  planning checker143tasks working tree và diff check đạt. Không full CI/M8.

Đây là engineering/boundary evidence, không thay thế độ đúng và độ đầy đủ QA thật.
Runtime được đóng băng trước live; không sửa hoặc gọi thêm lượt live sau FAIL/PARTIAL.

## Một lượt live được Owner cấp phép

Thứ tự C01→C07→C10; mỗi câu một lượt, max6calls/câu và18tổng; giữ model/endpoint/
key đã cấp, không retry hoặc provider fallback. Dùng lại token cap180.000tổng và
timeout300giây/câu của ngân sách trước, không nới giới hạn. Fail-stop trước call
tiếp theo khi provider/network lỗi. Manifest giữ exact runtime hashes và câu hỏi.

Working tree còn local edits từ trước, không gom chúng vào implementation commit;
không gán live quality cho riêng SHA nếu bỏ các runtime local đó. File hash của
lượt chạy nằm trong `implementation-receipt.json` và `live/manifest.json`.

### Tổng kết lượt chạy

Trạng thái runner: **STOPPED**; **11 calls / 35.653 known tokens +1unknown usage**,
không retry. Không tính failed timeout call là0tokens. Không có lượt live thứ hai.
Dừng: `provider_error_fail_stop`; không tiếp tục case còn lại.

### C01 — Kết quả thực tế

**Câu hỏi nguyên văn:**

> Lập nhận xét ngắn về BBS năm 2025 gồm ba phần: tăng trưởng doanh thu thuần so với 2024, tỷ trọng nợ trong tài sản cuối năm và dòng tiền kinh doanh. Nêu số liệu cho từng phần, không dùng một chỉ tiêu để kết luận toàn bộ sức khỏe tài chính.

**Câu trả lời thực tế nguyên văn** (giữ cả lặp/gaps/caveats):

> (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. [1]
>
> (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. [1]
>
> (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. [1]
>
> Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1]
>
> Lưu chuyển tiền thuần từ hoạt động kinh doanh kỳ 2025 là 14.319.681.754 VND. [2]
>
> Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa đáp ứng: Tính tỷ lệ nợ trên tổng tài sản (debt_to_assets) cho năm 2025-12-31.; Tính tỷ lệ tăng trưởng doanh thu thuần (revenue_yoy) giữa năm 2025 và 2024.; Tính dòng tiền thuần từ hoạt động kinh doanh (operating_cash_flow) cho năm 2025.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [2] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Status `partial_verified_coverage`; 5calls; 26,802tokens; 156.45giây.

**Chuẩn/điểm cần kiểm chứng:** Doanh thu2025=450.474.531.227VND,2024=355.507.372.286VND, tăng26,71%; nợ157.146.559.558/tài sản266.086.680.765=59,06%; CFO dương14.319.681.754VND, kết luận giới hạn theo ba nhánh.

**Agents/stages thực gọi qua Gateway:** `m5-lite-supervisor`×1; `m5-lite-liquidity_and_leverage`×1; `m5-lite-profitability`×1; `m5-lite-cash_flow_and_earnings_quality`×1; `m6-lite`×1.

**Tools:** `get_financial_fact`×5; `get_evidence_sources`×5.

**M6 decisions thực tế** (không dùng ACCEPT làm gold):

| Candidate | Mệnh đề candidate | Decision / reasons | Admission |
| --- | --- | --- | --- |
| `candidate:af00458bddec0650bff909df` | Tỷ trọng nợ trong tài sản cuối năm 2025 được tính bằng tỷ lệ giữa tổng nợ phải trả và tổng tài sản. Tỷ lệ này cho thấy mức độ phụ thuộc vào nợ của doanh nghiệp. | ABSTAIN: context_mismatch; reasoning_comparison_period_mismatch | NOT_EXECUTED |
| `candidate:f3d5f7da6c87b5bccc13935f` | Tổng nợ phải trả (kỳ 2025-12-31) / Tổng tài sản (kỳ 2025-12-31): 0,59 lần (tỷ số đối chiếu). | ABSTAIN: context_mismatch; reasoning_comparison_period_mismatch | NOT_EXECUTED |
| `candidate:eb85321eafb8cfc367d7fb9a` | Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. | ABSTAIN: context_mismatch | NOT_EXECUTED |
| `candidate:37663657fb14968dbe7421b2` | Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. | ABSTAIN: context_mismatch | NOT_EXECUTED |
| `candidate:7cd7d4647464ad6a9c1bee57` | Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. | ACCEPT: deterministic_source_and_calculation_verified | stored |
| `candidate:bc13cb26bebe9761e9131a5a` | Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. | ACCEPT: deterministic_source_and_calculation_verified | stored |
| `candidate:5c1da1bf605b709a5b775754` | Lưu chuyển tiền thuần từ hoạt động kinh doanh kỳ 2025 là 14.319.681.754 VND. | ACCEPT: deterministic_source_and_calculation_verified | stored |
| `candidate:1387910614fc94c0f9407928` | Tỷ lệ tăng trưởng doanh thu thuần giữa năm 2025 và 2024 được tính bằng tỷ lệ phần trăm tăng trưởng (percentage change) giữa doanh thu thuần năm 2025 và doanh thu thuần năm 2024. | ACCEPT: semantic_supported; Statement is directly supported by the provided facts and calculations. The percentage change between 2025 and 2024 revenue is correctly calculated as 26.71% using the given values and the percentage change operation. | stored |
| `candidate:ae178f65bf2253d61c7d2975` | (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. | ACCEPT: deterministic_source_and_calculation_verified | stored |
| `candidate:cca283e3c1db09f8173fa768` | Lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2025 là 14.319.681.754 VND, cho thấy khả năng sinh tiền từ hoạt động kinh doanh chính của doanh nghiệp trong năm. | INVESTIGATE: semantic_insufficient; The statement provides a fact about operating cash flow but includes an interpretation ('cho thấy khả năng sinh tiền từ hoạt động kinh doanh chính') that is not directly supported by the evidence. The evidence only confirms the cash flow value, not its implications. | NOT_EXECUTED |
| `candidate:1b928f009f247bae84c795b4` | So sánh với doanh thu thuần năm 2024 (355.507.372.286 VND), doanh thu thuần năm 2025 (450.474.531.227 VND) tăng 26,71%, cho thấy sự tăng trưởng mạnh trong hoạt động kinh doanh. | ACCEPT: semantic_supported; The statement is supported by the provided facts and calculations. The percentage change between 2025 and 2024 revenue is correctly calculated as 26.71% using the given values and the percentage change operation. | stored |
| `candidate:71fdd25046cda7e49811bc2d` | (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. | ACCEPT: deterministic_source_and_calculation_verified | idempotent |
| `candidate:2285c67b1361fd374c95e34f` | Tỷ lệ nợ trên tổng tài sản năm 2025 là 59,06%, cho thấy doanh nghiệp có mức độ phụ thuộc vào nợ tương đối cao. | ABSTAIN: context_mismatch; lite_unbound_number; lite_unbound_unit; reasoning_comparison_period_mismatch | NOT_EXECUTED |
| `candidate:01912929fd8e191bf2d18c29` | Tổng nợ phải trả (kỳ 2025-12-31) / Tổng tài sản (kỳ 2025-12-31): 0,59 lần (tỷ số đối chiếu). | ABSTAIN: context_mismatch; reasoning_comparison_period_mismatch | NOT_EXECUTED |

**M6 → Ledger → M7:** {'ABSTAIN': 6, 'ACCEPT': 7, 'INVESTIGATE': 1}; 6unique admitted IDs; 6ledger entries; 6root released IDs. Ledger-not-released: `[]`. Released-outside-ledger: `[]`.

| Verified ID | Root M7 | Citation PDF pages |
| --- | --- | --- |
| `verified:078f675351614d34ce0b552b33acd5e44979ba1e693a9038393d4cdea2b38f4c` | released | [7] |
| `verified:1e5f1509597a20a3c3205eca8e5314169436507dc703967c3d6db5141c8b6ce4` | released | [8] |
| `verified:44dad4d1cfe1aad22664ab34ffd099de4fe6dcf7f6ed6036f18d4d189acf34e7` | released | [7] |
| `verified:861c26deb972969c4d0a137cf1f25dffafbdb30dc92b74a7bc1541418a36c202` | released | [7] |
| `verified:c4dc144c35934096a1c51bc78089cde3ab457e9cea26e92a90024cbe52621d51` | released | [7] |
| `verified:d52ea7a531658b7649ee3156b1ddb81a5efa1093176e87ef5a43e0c2b7f95660` | released | [7] |

**Coverage thực tế:**
- `R001`: Tính tỷ lệ nợ trên tổng tài sản (debt_to_assets) cho năm 2025-12-31.; unverified; verified IDs=[].
- `R002`: Tính tỷ lệ tăng trưởng doanh thu thuần (revenue_yoy) giữa năm 2025 và 2024.; unverified; verified IDs=[].
- `R003`: Tính dòng tiền thuần từ hoạt động kinh doanh (operating_cash_flow) cho năm 2025.; unverified; verified IDs=[].

Nguồn evidence: local `qa-completion/live/execution/C01.json` và `provider-events.json`. Root errors: `[]`.

### C07 — Kết quả thực tế

**Câu hỏi nguyên văn:**

> Nêu LNST BBS năm 2025 rồi đối chiếu chính sách chi phí đi vay trong thuyết minh: khoản nào ghi chi phí, khoản nào có thể vốn hóa? Không suy ra số lãi vay vốn hóa thực tế từ chính sách.

**Câu trả lời thực tế nguyên văn** (giữ cả lặp/gaps/caveats):

> Tài liệu ghi «4.12. Chi phí đi vay Chi phí đi vay bao gồm lãi tiền vay và các chi phí khác liên quan trực tiếp đến các khoản vay. Chi phí đi vay được ghi nhận vào chi phí sản xuất, kinh doanh trong năm khi phát sinh, ngoại trừ chi phí đi vay liên quan trực tiếp đến việc đầu tư, xây dựng hoặc sản xuất tài sản dở dang cần có một thời gian đủ dài (trên 12 tháng), để có thể đưa vào sử dụng theo mục đích định trước hoặc bán, được tính vào giá trị của tài sản đó (được vốn hóa) khi có đủ các điều kiện quy định của Chuẩn mực kế toán Việt Nam số 16 - Chi phí đi vay. Đối với khoản vay riêng phục vụ việc xây dựng tài sản cố định, lãi vay được vốn hóa kể cả khi thời gian xây dựng từ 12 tháng trở xuống. Đối với các khoản vốn vay chung, trong đó có sử dụng cho mục đích đầu tư xây dựng hoặc sản xuất tài sản dở dang thì số chi phí đi vay được vốn hóa được xác định theo tỷ lệ vốn hóa đối với chi phí lũy kế bình quân gia quyền phát sinh cho việc đầu tư xây dựng hoặc sản xuất tài sản đó. Tỷ lệ vốn hóa được tính theo tỷ lệ lãi suất bình quân gia quyền của các khoản vay chưa trả trong năm, ngoại trừ các khoản vay riêng biệt phục vụ cho mục đích hình thành một tài sản cụ thể.» [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa đáp ứng: Tìm LNST của BBS năm 2025; Tìm LNST của BBS năm 2024; Nêu LNST BBS năm 2025
>
> Nguồn tham chiếu
>
> [1] BBS 2025 — Trang PDF 12. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Status `partial_verified_coverage`; 5calls; 8,851tokens; 107.40giây.

**Chuẩn/điểm cần kiểm chứng:** LNST BBS2025=7.249.557.946VND (PDF7); chính sách chi phí đi vay PDF12: thường ghi chi phí khi phát sinh, vốn hóa tài sản dở dang đủ điều kiện VAS16 và ngoại lệ vay riêng xây dựng TSCĐ kể cả<=12tháng. Không suy số vốn hóa thực tế từ chính sách.

**Agents/stages thực gọi qua Gateway:** `fusion-planner`×1; `m5-lite-supervisor`×1; `m5-lite-profitability`×2; `document-planner`×1.

**Tools:** `search_document_evidence`×4; `get_evidence_sources`×5; `get_graph_context`×1.

**M6 decisions thực tế** (không dùng ACCEPT làm gold):

| Candidate | Mệnh đề candidate | Decision / reasons | Admission |
| --- | --- | --- | --- |
| `document:702135aa78af81180a240c294ec279189b982483cb0adbef2ff583282946c032` | Tài liệu ghi «4.12. Chi phí đi vay Chi phí đi vay bao gồm lãi tiền vay và các chi phí khác liên quan trực tiếp đến các khoản vay. Chi phí đi vay được ghi nhận vào chi phí sản xuất, kinh doanh trong năm khi phát sinh, ngoại trừ chi phí đi vay liên quan trực tiếp đến việc đầu tư, xây dựng hoặc sản xuất tài sản dở dang cần có một thời gian đủ dài (trên 12 tháng), để có thể đưa vào sử dụng theo mục đích định trước hoặc bán, được tính vào giá trị của tài sản đó (được vốn hóa) khi có đủ các điều kiện quy định của Chuẩn mực kế toán Việt Nam số 16 - Chi phí đi vay. Đối với khoản vay riêng phục vụ việc xây dựng tài sản cố định, lãi vay được vốn hóa kể cả khi thời gian xây dựng từ 12 tháng trở xuống. Đối với các khoản vốn vay chung, trong đó có sử dụng cho mục đích đầu tư xây dựng hoặc sản xuất tài sản dở dang thì số chi phí đi vay được vốn hóa được xác định theo tỷ lệ vốn hóa đối với chi phí lũy kế bình quân gia quyền phát sinh cho việc đầu tư xây dựng hoặc sản xuất tài sản đó. Tỷ lệ vốn hóa được tính theo tỷ lệ lãi suất bình quân gia quyền của các khoản vay chưa trả trong năm, ngoại trừ các khoản vay riêng biệt phục vụ cho mục đích hình thành một tài sản cụ thể.» | ACCEPT: exact_source_support | stored |

**M6 → Ledger → M7:** {'ACCEPT': 1}; 1unique admitted IDs; 1ledger entries; 1root released IDs. Ledger-not-released: `[]`. Released-outside-ledger: `[]`.

| Verified ID | Root M7 | Citation PDF pages |
| --- | --- | --- |
| `verified:51a072f22f60714682823b1c9c84a755a7c31beb8eefb28c68cafb28795fb9b0` | released | [12] |

**Child → root:**
- `R1`/financial: verification_blocked, child IDs=[]; mất ở root=[].
- `R2`/document: completed_with_caveats, child IDs=['verified:51a072f22f60714682823b1c9c84a755a7c31beb8eefb28c68cafb28795fb9b0']; mất ở root=[].

**Coverage thực tế:**
- `R1:R001`: Tìm LNST của BBS năm 2025; unverified; verified IDs=[].
- `R1:R002`: Tìm LNST của BBS năm 2024; unverified; verified IDs=[].
- `R1`: Nêu LNST BBS năm 2025; unverified; verified IDs=[].
- `R2:R1`: chi phí đi vay; satisfied; verified IDs=['verified:51a072f22f60714682823b1c9c84a755a7c31beb8eefb28c68cafb28795fb9b0'].
- `R2`: đối chiếu chính sách chi phí đi vay trong thuyết minh: khoản nào ghi chi phí, khoản nào có thể vốn hóa; satisfied; verified IDs=['verified:51a072f22f60714682823b1c9c84a755a7c31beb8eefb28c68cafb28795fb9b0'].

Nguồn evidence: local `qa-completion/live/execution/C07.json` và `provider-events.json`. Root errors: `[]`.

### C10 — Kết quả thực tế

**Câu hỏi nguyên văn:**

> Tại 31/12/2025, BCC có vốn lưu động ròng (tài sản ngắn hạn trừ nợ ngắn hạn) bao nhiêu và hệ số thanh toán hiện hành mấy lần? Đặt hai kết quả bên cạnh CFO dương năm 2025 và nêu giới hạn khi đánh giá thanh khoản.

**Chưa có final answer**: INTERRUPTED. Không tự suy ra câu trả lời hoặc verdict khi chưa chạy tới bước đó.

**Chuẩn/điểm cần kiểm chứng:** Vốn lưu động ròng767.374.839.317−1.368.031.294.449=−600.656.455.132VND; current ratio0,560933688…≈0,56lần; CFO dương314.097.335.438VND; dữ liệu này không chứng minh chắc chắn khả năng thanh toán tương lai.

Provider event cuối: `m5-lite-supervisor`, status=`error`, category/code=`timeout`,
retryability=`not_retryable`, origin=`adapter`; request timeout60giây. Một call
đã thử, input/output/total usage đều unknown; không có response content để quote,
không có tool call/M6 decision/ledger entry/M7 answer. Runner không lưu elapsed
E2E của case bị BaseException interrupt, nên **không có thời gian C10 chính xác
để báo**;60giây là cấu hình timeout, không phải số đo E2E. Không dùng đây làm
FAIL chất lượng financial verification; C10 hiện chỉ có bằng chứng offline.

## Đối chiếu từng phần và nguyên nhân còn lại

| Case | Đã đạt nội dung thật | Còn thiếu / nguyên nhân cụ thể |
| --- | --- | --- |
| C01 — PARTIAL | Doanh thu hai kỳ, phép tăng26,71%, CFO14.319.681.754VND và citations PDF7/8; đủ3roles được gọi, shared evidence được dùng | Thiếu nợ/tài sản59,06% và kết luận tổng hợp có giới hạn. `LitePlan.requirements` dùng `target_id=S34/S35/S25`, `required_indicators` cũng là S handles thay canonical IDs; CFO còn khai kind=metric. `IntegrationWorkspace.export` không match được nên toàn bộ candidate_requirements rỗng; M7 báo thiếu cả phần đã có số. Đây là model contract error được schema string hiện tại cho qua; không phải thiếu corpus. |
| C01 — phần nợ | M5 có nợ157.146.559.558VND/tài sản266.086.680.765VND, phép ratio0,59 và một prose59,06% | M6 `_context/_reasoning` dùng `comparison_periods(batch.question)` toàn câu={2024,2025}; các nguồn as-of2025-12-31 không nằm trong tập fiscal-year đó nên context_mismatch/reasoning_comparison_period_mismatch. Một analysis59,06% còn dùng ratio proof nên lite_unbound_unit/number. Đây là lỗi scope còn tồn tại tại boundary kiểm chứng cùng lỗi đại lượng do model, không được quy cho M7 làm rơi ACCEPT. |
| C01 — coverage/presentation | 7native ACCEPT hợp thành6unique ledger entries,1idempotent;6/6đến M7, không ledger entry bị mất | Accepted findings/proofs trùng mục tiêu khiến phép26,71% xuất hiện3lần. Coverage chưa canonical-bind nên báo thiếu phần đúng. M6 giữ CFO fact nhưng INVESTIGATE inference về khả năng sinh tiền. Không có cơ sở gọi whole answer đầy đủ. |
| C07 — PARTIAL | Chính sách ghi chi phí/vốn hóa và ngoại lệ được phát hành nguyên văn, citation PDF12. Child document ACCEPT có đúng cùng ID ở root | Thiếu LNST7.249.557.946VND, vì supervisor financial đặt `sources=['b02.profit_after_tax']` thay source handles S…; retrieval không chạy, `unknown_or_foreign_source` trong task bundle, specialists abstain/invalid_analysis_schema. Model còn thêm requirement2024 không được hỏi. Không có numeric claim tới M6; không phải M6 bác LNST đúng hoặc tài liệu thiếu LNST. |
| C07 — constraint | Không bịa số vốn hóa thực tế, không tạo nhận định tài chính mới ở M7 | Fusion plan không giữ negative constraint thành requirement riêng; final không giải thích rõ giới hạn “không suy số vốn hóa thực tế”. Câu trả lời chỉ có document evidence, chưa đồng thời có financial evidence. |
| C10 — INTERRUPTED | Typed verifier đã có offline replay đúng3candidate, chặn model subtraction sai | API timeout tại supervisor trước retrieval; không quan sát được end-to-end C10 mới. Tokens và thời gian E2E case này không có đủ telemetry, không tự điền0. |

Code/trace evidence: `src/agents/integration_workspace.py::matches_requirement/export`,
`src/agents/lite_orchestrator.py::integration_plan/run`,
`src/verification/validators.py::_context/_reasoning`,
`src/verification/lite_runtime.py::LiteFinancialValidator._analysis`;
`live/execution/C01.json#/response/trace/financial_execution/integration_context`,
`C07.json#/response/trace/fusion_bundle/lane_results`, `live/provider-events.json`.
Không sửa các nguyên nhân quan sát sau live, không thử prompt/model/case khác.

**Phân biệt sửa và giới hạn:** lỗi child document ACCEPT mất ở root đã được sửa
và xác nhận cả saved replay lẫn live C07 (1/1child release được giữ). Binding
target/source-handle do model, M6 global comparison-period scope, negative
constraint và lặp presentation vẫn còn. Financial+document completeness và live
C10 chưa được chứng minh. Không thay quality verdict bằng số unit tests PASS.

## Bàn giao

Trạng thái REVIEW; không tự nghiệm thu DONE, không mở vòng FIX hoặc tự triển khai
task tiếp theo. Next action duy nhất: Tech Lead review kết quả QA thật và phạm vi
đã kiểm chứng trước quyết định nghiệm thu.
