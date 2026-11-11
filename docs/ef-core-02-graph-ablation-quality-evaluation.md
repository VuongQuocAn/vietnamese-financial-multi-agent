# EF-CORE-02 — Controlled EF-EG Ablation & Quality Evaluation

Ngày 11/11/2026 (Asia/Bangkok). Development evaluation trên BBS 2025, **không phải M8**. Status: **REVIEW**, chờ Tech Lead nghiệm thu.
Runtime cố định tại `f5bbac6b6d5befd0b3021654b48218feeab54942`.

## 1. Executive Summary

**REVIEW — development evaluation hoàn tất, còn technical attrition.**
60 primary +20 bounded replacements trên15 câu/BBS scan thật, Gemini thật,
M5/M6/M7 giữ nguyên accepted baseline. Có23 clean pairs;52/60 slots có execution
clean, không đủ hai clean repetitions cho mọi câu.

Trong cùng23 pairs, ON đạt14/23 câu đúng có caveat so với11/23 OFF; completeness
84/111 so với82/111. Hai improvement về correctness/grounding đến từ bỏ caveat sai
về trang nguồn ở B2; một improvement ở F1 xảy ra khi không gọi graph. Không phát
hiện sai phép tính trong final paired answers được đọc, không có financial fact
mới do graph bổ sung. ON tăng mean tokens60,22% và latency61,23%.

Graph có contribution hẹp về provenance/context projection (B2/D2) và có trace
relation use→ACCEPT→release, nhưng chưa chứng minh quan hệ graph tự thân cải thiện
financial accuracy hoặc multihop completeness. G3 mất percentage analysis/wording;
G5 có retrieval nhưng mất relation coverage tại projection/goal/diễn giải. M6
ACCEPT một số caveat nguồn không đúng. Không cần kiến trúc/agent/database mới;
ưu tiên sửa cách khai thác thông tin, rồi kiểm chứng hypothesis rộng hơn ở M8.

## 2. Research Questions và hypotheses

- RQ1: Graph bổ sung truy xuất/liên kết gì ngoài Financial/Evidence Tools?
- RQ2: Graph cải thiện correctness, completeness, grounding hoặc citations không?
- RQ3: G3/G5 mất thông tin ở tầng nào?
- RQ4: M6 có ACCEPT nội dung thiếu semantic grounding không?
- RQ5: Tokens, calls, setup/traversal và end-to-end latency tăng bao nhiêu?

Giả thuyết phát triển: graph có thể giúp lineage và phân biệt nguồn/ngữ cảnh,
nhưng không nhất thiết bổ sung financial facts hoặc tăng answer accuracy.
Hai cấu hình có thể tương đương hoặc ON kém hơn; không chọn câu hỏi theo edge có sẵn.

## 3. Experimental Setup

Runner `scripts/evaluate_ef_ablation.py` tách toàn bộ `src` bằng `git archive` của
accepted SHA; không overlay các runtime local edits. Cùng BBS PDF, financial
snapshot, approved EF-01 composition, model và generation parameters của runtime
gốc. Không thay M5/M6/M7, schema, Calculator, graph, OCR hoặc extraction.

Mỗi câu sinh **một Supervisor plan thật**, lưu trước lượt ON rồi dùng nguyên vẹn
cho bốn executions. Plan gồm objective, source handles, Specialist và `use_graph`.
Request chỉ thay `m5_graph`; không ép Supervisor bật graph. Lượt một OFF→ON, lượt
hai ON→OFF để giảm một phần ảnh hưởng thứ tự. Plan hash được đối chiếu từng cặp.
Không tái sử dụng Specialist/M6/M7 outputs. Mỗi execution có ledger riêng,
`force_refresh=true`; request giữ ceiling 32 calls/300 giây như EF-CORE-01.

Planning có chi phí chung, tách khỏi tokens/calls/provider attempts và latency
đối chiếu. End-to-end so sánh bằng wall time trừ planning call thực sự phát sinh;
không trừ graph setup hoặc tool execution. Trace giữ cả wall time gốc và normalized
comparison time. Graph setup và `get_graph_context` traversal được đo riêng bằng
wrapper quan sát, giữ nguyên input/output và implementation.

Gemini qua Shared Gateway, QA key rotation/pool hiện có; không tạo provider khác.
Provider failure có output fallback vẫn được đánh dấu technical-affected, tách khỏi
quality denominator. Không quy technical failure thành analytical failure.
Resume bỏ qua execution đã lưu; dừng khi ba executions liên tiếp bị chặn hoàn toàn,
không coi một HTTP503 xen giữa các lời gọi thành công là provider outage toàn bộ.
Không retry vô hạn. Raw traces giữ lỗi, usage chưa biết và kết quả âm tính.

Sau primary runs, cho phép tối đa **một replacement** cho mỗi slot bị lỗi kỹ thuật,
lưu `retry1` riêng và dùng lại cùng plan. Không thay thế một câu trả lời clean chỉ
vì PARTIAL/INCORRECT. Mỗi slot vẫn tối đa một execution clean trong thống kê chất
lượng; giữ mọi original failure và tính mọi attempt vào chi phí/failure rate.
So sánh chính chỉ lấy cặp OFF/ON đều clean của cùng câu/repetition, tránh mẫu số
khác thành phần câu hỏi. Báo cáo riêng primary và replacement, không giấu attrition.

Pilot A1/B1/C1/D1, một cặp/câu, kiểm tra controls/oracle/trace trước main experiment.
Pilot được giữ nguyên trong tập chính; không chạy lại lượt đã hoàn tất.

## 4. Dataset/Question Categories

15 câu, phân bố đúng 2/3/3/3/2/2 theo task. Câu hỏi đầy đủ và content requirements
đóng băng trước khi gọi Gemini trong `freeze.json`. Không dùng lại toàn bộ G1–G6.

| Nhóm | Cases | Nội dung |
| --- | --- | --- |
| A. Direct Financial Facts | A1–A2 | Doanh thu, tổng tài sản, đơn vị/trang nguồn |
| B. Metric Lineage | B1–B3 | Revenue growth, gross margin, debt/assets; công thức/toán hạng/kỳ/nguồn |
| C. Multi-hop | C1–C3 | Revenue/gross profit, hai gross margins, tài sản/nợ đầu-cuối kỳ |
| D. Document Evidence/Context | D1–D3 | Bốn loại relation; bảng/anchor; giới hạn giải thích nguyên liệu |
| E. Unsupported Relations | E1–E2 | Revenue growth không chứng minh quản lý chi phí; thiếu customer data |
| F. Period/Conversation | F1–F2 | Kỳ so sánh và câu hỏi tiếp nối về mất khả năng thanh toán |

C1 và D1 là regression intents G3/G5, với tiêu chí rõ hơn câu cũ. F2 dùng hội thoại
đầu vào chuẩn hóa giống nhau cho cả bốn lượt: câu trước hỏi debt/assets và câu trả
lời dựa trên oracle 59,06%; không giả đây là output fresh của turn trước. Test này
đo xử lý cùng input conversation, không đo độ bền toàn session nhiều lượt.

## 5. Oracle Construction

Oracle lấy từ canonical source records có thật, trước các outputs ON/OFF. Tính lại
bằng `Decimal`; không dùng Gemini answer làm đáp án. Đã render và Codex đọc trực
tiếp PDF trang 5/6/7: company VICEM Bao bì Bút Sơn, VND, row labels, cột kỳ và tám
giá trị dưới đây khớp. PDF page 5/6/7 tương ứng số trang in 4/5/6.

| Chỉ tiêu | Kỳ gốc | Kỳ mục tiêu | Nguồn PDF |
| --- | ---: | ---: | --- |
| Doanh thu thuần | 355.507.372.286 | 450.474.531.227 | 7, năm 2024/2025 |
| Lợi nhuận gộp | 36.432.410.381 | 32.482.519.668 | 7, năm 2024/2025 |
| Tổng tài sản | 291.306.659.104 | 266.086.680.765 | 5, 01/01/2025 và 31/12/2025 |
| Nợ phải trả | 183.476.510.255 | 157.146.559.558 | 6, 01/01/2025 và 31/12/2025 |

Revenue: +94.967.158.941 VND/+26,71%; gross profit: −3.949.890.713 VND/−10,84%.
Gross margin 2024/2025: 10,25%/7,21%, chênh lệch −3,04 điểm phần trăm.
Assets: −25.219.978.339 VND/−8,66%; debt: −26.329.950.697 VND/−14,35%.
Debt/assets cuối kỳ: 59,06%. Không đổi kỳ 01/01/2025 thành FY2024 trong source record.
Reporting scope còn unresolved theo nguồn; không tự gán consolidated/standalone.

Tách ba lớp evidence:

1. Facts/calculations và binding PDF đã đối chiếu độc lập; chỉ xác minh những dòng
   được dùng, không chứng nhận accuracy toàn PDF hoặc từng glyph của tất cả OCR.
2. Graph oracle lấy các đường SourceFact của tám facts qua approved composition,
   giữ nguyên typed edges/citations. `from_source` là provenance; `associated_with`
   là exact extraction association; `used_in` là operand role; contextual relation
   chỉ cùng ngữ cảnh. Không relation nào tự chứng minh nhân quả hoặc semantic support.
3. Codex đọc final answers và claims/M6/selection traces để chấm semantic content.
   Nhận định không xác minh chắc được ghi UNCERTAIN, không ép đúng.

E1 tự nêu thêm giá vốn: source PDF7/canonical đã lưu có319.074.961.905 và
417.992.011.559 VND; supplementary independent Decimal xác minh tăng31,00%.
Đây là post-hoc kiểm tra phát biểu phụ, không sửa frozen questions/requirements
hoặc lấy ON answer làm oracle.

Full source identities/selectors/hashes ở oracle/graph/source-review JSON ignored.
Page binding đã xác minh; tọa độ ô/anchor chính xác chưa được kiểm chứng độc lập.
Không suy từ việc chưa tìm thấy customer/raw-material evidence trong selected
context thành khẳng định toàn PDF không có thông tin ấy.

Completeness là số content requirements thực sự đáp ứng/tổng requirements có thể
đáp ứng. Toàn bộ phép tính C1–C3 đều source-answerable; thiếu output không loại chúng
khỏi mẫu số. D/E/F có yêu cầu nêu giới hạn hợp lệ thay cho bịa dữ liệu/nhân quả.

## 6. Paired Graph OFF/ON Results

Có **60 primary executions +20 replacements**, chấm đủ 80 outputs. Primary có
20/60 lượt technical-affected (OFF12/30, ON8/30); replacement còn8/20 affected.
Có52 execution clean, tương ứng52/60 slots; **23/30 cặp** đủ clean hai cấu hình.
Bảy cặp chưa đủ điều kiện: A1 cả hai repetitions, A2-r2, B3-r1, C1-r2, C2-r1,
D2-r1. Vì vậy chưa có hai clean OFF và hai clean ON cho mọi câu; không gọi tập này
là repeated benchmark sạch hoặc evidence đủ mạnh để chứng minh EF-EG vượt trội.

Bảng chính chỉ dùng **cùng 23 câu/repetition ở hai cấu hình**, không so mẫu khác
thành phần. Technical failures nằm ngoài quality denominator và vẫn trong cost.

| Nhóm | Graph OFF | Graph ON | Chênh lệch | Kết luận |
| --- | --- | --- | --- | --- |
| Answer correctness (CWC hoặc CORRECT) | 11/23 (47.83%) | 14/23 (60.87%) | +13.04 điểm % | Hai B2 cải thiện caveat; F1 cải thiện khi không gọi graph. |
| Completeness | 82/111 (73.87%) | 84/111 (75.68%) | +1.80 điểm % | Hai content units thêm ở C1/F1; không phải cải thiện đồng đều. |
| Grounding: không có assertion sai/thiếu căn cứ đã xác định | 21/23 (91.30%) | 23/23 (100.00%) | +8.70 điểm % | Khác biệt là caveat về trang nguồn ở B2. |
| Citation accuracy: document/snapshot/page | 30/30 | 30/30 | 0 | Không đồng nghĩa mọi narrative trên trang được entail. |
| Unsupported assertion (answer-level) | 2/23 | 0/23 | -2 answers | Source-page absence; không phải causal claim sai. |
| Unjustified refusal | 0/23 | 0/23 | 0 | Exception được tách kỹ thuật, không gọi là analytical refusal. |
| Tokens: mean/lượt | 7229.22 | 11583.00 | +4353.78 (+60.22%) | Planning chung đã loại khỏi so sánh. |
| Latency: mean giây/lượt | 34.52 | 55.66 | +21.14 (+61.23%) | Planning chung đã loại khỏi so sánh. |

Toàn bộ46 final answers thuộc clean pairs được Codex đọc đối chiếu số liệu/phép
biến đổi với oracle: không phát hiện arithmetic discrepancy trong nội dung đã nêu.
Các phép tính bị bỏ sót vẫn trừ completeness. Across80 attempts,62 retained tool
metric occurrences (OFF30/ON32) được tính lại độc lập,62/62 khớp;198 occurrences
thuộc tám oracle facts exact value/context/source và89 citation bindings không mismatch.
Đây là đúng trên phần được kiểm tra, không là accuracy toàn báo cáo.

CWC = đúng có caveat nguồn; P = PARTIAL; TF = TECHNICAL_FAILURE.
Mũi tên là primary→replacement, không xóa kết quả gốc.

| Case | OFF r1 | ON r1 | OFF r2 | ON r2 |
| --- | --- | --- | --- | --- |
| A1 | TF→TF | TF→TF | TF→TF | P |
| A2 | TF→CWC | CWC | TF→TF | CWC |
| B1 | CWC | CWC | CWC | CWC |
| B2 | P | CWC | P | CWC |
| B3 | TF→TF | CWC | CWC | CWC |
| C1 | P | P | TF→TF | CWC |
| C2 | P | TF→TF | TF→P | TF→P |
| C3 | TF→P | TF→P | P | P |
| D1 | TF→P | P | P | P |
| D2 | TF→TF | P | P | P |
| D3 | TF→CWC | TF→CWC | CWC | TF→CWC |
| E1 | CWC | CWC | CWC | TF→CWC |
| E2 | CWC | CWC | CWC | CWC |
| F1 | P | CWC | P | TF→P |
| F2 | TF→CWC | CWC | P | P |

C1-r1 ON thêm biến động tuyệt đối doanh thu nhưng vẫn thiếu delta/% gross profit;
C1-r2 ON đầy đủ, còn OFF có lỗi ở cả primary/replacement nên không tính paired win.
C2 cả hai còn thiếu gross margin2024 và chênh lệch điểm phần trăm. D1 cả hai
chưa phân biệt đủ relations. C3-r2 OFF nêu59,06%, ON chỉ mô tả tỷ lệ chung: ON
kém cụ thể ở chi tiết này dù content-unit rubric C3 chấm cùng3/9; không che giấu
bằng kết quả tie. D2-r2 ON nêu được tên bảng B02, nhưng chưa đủ distinction yêu cầu.
F1-r1 ON giải thích cột so sánh tốt hơn **mà không gọi graph**: đây là model variance,
không là GRAPH_ADDED_VALUE. F2-r2 cả hai bỏ phần suy luận thanh toán.

Full answers nguyên văn, oracle, shared plan, tools/relations, claims/M6/M7,
assessment/root cause và per-run usage/timings ở `question-appendix.md` ignored.

## 7. Graph Contribution Analysis

Trong38 ON attempts,30 có relations được truy xuất;16 có Specialist khai báo dùng,
11 có claim dùng graph được M6 ACCEPT và M7 chọn. Counts gồm cả technical-affected
attempts có partial outputs; không coi chúng là clean answer wins. A1/E2/F1 có
`use_graph=false` trong shared plan, vì vậy ON flag không tạo treatment ở ba case.
Tất cả30 paired slots có cùng real plan hash, cùng Financial Tool fact identities
và cùng model/generation parameters ở các stage chung; OFF không gọi graph.
Graph không mở rộng tập financial facts được Financial Tools cấp cho candidate.

B2 cải thiện grounding lặp lại hai lần: OFF nói thiếu page trong khi vẫn citePDF7;
ON có page trong compact context và không nói sai đó. D2-r2 có hai graph-related
analysis ACCEPT/selected và nêu đúng bảng báo cáo kết quả kinh doanh. Đây là
**GRAPH_ADDED_VALUE hẹp của integration về source/context visibility**. Chưa tách
được lợi ích riêng của edges khỏi metadata projection. B1/B3 vẫn cùng đầy đủ về
operands/formula/citations khi OFF; không có lineage-completeness win ổn định.
C1 có một paired content improvement, nhưng không đủ repetitions clean để quy
nguyên nhân cho graph; F1 improvement chắc chắn không đến từ graph vì0 graph calls.


Phân biệt `GRAPH_NOT_NEEDED`, `GRAPH_RETRIEVED`, `GRAPH_USED`,
`GRAPH_SUPPORTED_ACCEPT`, `GRAPH_ADDED_VALUE`. Tool returns, prompt supplied,
Specialist khai báo dùng relation, M6 ACCEPT và M7 chọn là các bước khác nhau.
Trace tự động chỉ nhận explicit graph handles trong reasoning goal; Codex đọc cả
candidate statement để tìm use không khai báo handles. Added value chỉ ghi khi
paired answer cải thiện một content requirement/grounding/citation thực tế.
Không dùng ACCEPT hoặc tăng tokens làm bằng chứng added value.

Hai nguyên nhân baseline cần được kiểm chứng riêng trước mở rộng: source
projection/semantic metadata bị thiếu và invalid `derived_fact` làm mất cả batch.
Không thêm edges/agent/database để che lỗi ở cách dùng thông tin.

Cần phân biệt lợi ích của **quan hệ graph** với lợi ích của **projection nguồn**:
baseline OFF đưa numeric choices/evidence scalar vào Specialist, không đưa số trang
trong danh sách scalar đó. ON có thể đưa trang/citations từ graph projection vào
prompt, dù Evidence Tools ở OFF đã truy xuất được cùng trang. Vì vậy giảm caveat
sai về trang nguồn là lợi ích thực tế của cách tích hợp hiện tại, nhưng chưa chứng
minh chỉ graph mới cung cấp được thông tin đó. Không gọi đây là financial fact mới.

## 8. G3/G5 Root Cause Analysis

### G3 lịch sử

Đối chiếu `EF-CORE-01/live-final`, cùng real Supervisor plan: profitability được
yêu cầu phân tích hai chỉ tiêu, hai kỳ, growth và nguồn. Financial Tools đã lấy đủ
bốn facts; graph ON trả `used_in`/`from_source`, prompt projection còn hai edges
mỗi loại. Không có bằng chứng retrieval làm mất hai số gross profit.

Specialist ON tạo `subtract` đúng −3.949.890.713 VND nhưng statement chỉ nói gross
profit “thay đổi”; không nêu hướng/mức giảm và không tạo percentage-change gross
profit. Do vậy completeness mất ngay tại Specialist analysis/candidate wording,
trước M6. M6 ACCEPT candidate mơ hồ; trong lượt ON, M7 giữ wording chung và không
đưa mức chênh lệch đã có trong reasoning ra prose. Không có claim đủ “giảm 10,84%” đã ACCEPT
rồi bị M7 bỏ trong lượt ON đó. OFF có diễn giải giảm và phần trăm trong answer.

Graph làm prompt lớn hơn, nhưng chưa có attention ablation hoặc can thiệp để chứng
minh phân tán attention là nguyên nhân. Đây là model output/coverage finding dưới
graph context, không phải kết luận graph traversal trả sai số.

### G5 lịch sử

`EF-CORE-01/live-context` trả đủ bốn loại: from_source, associated_with, used_in,
same_extraction_context. Projection 14.000 ký tự chỉ giữ một used_in và hai
same_extraction_context; from_source/associated_with không đến compact context
trong lượt này. Đây là **có trong retrieval nhưng bị giới hạn projection**, không
phải thiếu edge trong graph.

Specialist nhắc G1/G2/G3 và cảnh báo cấu trúc/ngữ cảnh không chứng minh nhân quả,
nhưng không phân biệt semantics bốn loại. Objective của Supervisor cũng chỉ yêu
cầu chung truy vết nguồn/ngữ cảnh, không giữ rõ mọi phân biệt trong câu hỏi.
M6 ACCEPT mô tả chung, M7 phát hành mô tả chung. Có cả mất yêu cầu ở planning và
thiếu diễn giải ở Specialist; không có bằng chứng cần thêm edge hoặc database.

### C3 — giới hạn xử lý kỳ so sánh chung cho hai cấu hình

Request được bind `period=2025-01-01` khi hỏi cuối năm so đầu năm. M5 đã lấy đủ
closing/opening facts, nhưng direct closing facts và debt/assets cuối năm bị M6
ABSTAIN `context_mismatch`. Các analysis across-period có thể ACCEPT nếu dùng
phép tính/hỗ trợ đúng, nên một số narrative vẫn nêu được closing metric hoặc delta.
Đây là context/verification-policy interaction, không phải graph thiếu dữ liệu.
Ở lượt hai cả OFF/ON vẫn thiếu các mức thay đổi được yêu cầu. Không quy sự thiếu
đầy đủ này cho traversal hoặc sửa period policy trong ablation.

## 9. M6 Semantic Grounding Findings

Claim G3 lịch sử được M6 ACCEPT:

> Loi nhuan gop thay doi giua nam 2024 va nam 2025 dua tren gia tri thuc te tu nguyen lieu.

Source/calculation đi kèm chỉ có gross-profit facts và phép trừ hai kỳ; không có
evidence giá/sử dụng nguyên liệu làm căn cứ cho cụm “từ nguyên liệu”. M6 reason
chỉ giải thích phép trừ đúng, gloss over cụm đó và chấp nhận do limitation nói chỉ
phân tích số học. Nếu hiểu “nguyên liệu” theo nghĩa vật liệu thì thiếu căn cứ;
intended meaning của wording không dấu là **UNCERTAIN**. Không nâng ambiguity thành
kết luận đã chứng minh quan hệ nhân quả sai, nhưng wording này không đủ semantic
grounding và không đạt nội dung phân tích cần có.

Theo code baseline, M6 semantic payload gồm statement, facts/calculations scalar,
scope, assumptions/limitations; không gửi typed graph edges/text source excerpts.
Deterministic checks xác minh numeric/provenance; semantic batch được giao kiểm
tra toàn statement và mỗi mệnh đề. Lượt trên semantic model chỉ đối chiếu số học;
SUPPORTED ánh xạ ACCEPT, không có independent per-clause proof. Vì vậy ACCEPT
không chứng nhận tất cả semantic implications, đặc biệt graph relation semantics.

Các lượt mới đã tái hiện caveat nói không có số trang trong khi citation vẫn có
PDF7. Đã đối chiếu riêng A1-r2 ON, B2-r1 OFF và B2-r2 OFF: claim/caveat tương ứng
M6 ACCEPT rồi M7 phát hành, nhưng page binding của chính record/citation là7.
Hai B2 nằm trong main paired comparison, A1 bị loại do counterpart technical.
 Specialist numeric projection không chứa page; M6 scalar payload cũng không
chứa page. M6 có thể đánh giá limitation theo input bị rút gọn, dù source binding
đã có ở tầng khác. Đây là thiếu metadata khi kiểm chứng source-availability và
wording mâu thuẫn, không phải phép tính sai. Khắc phục nhỏ được đề xuất là đưa
page/provenance scalar đã xác minh vào các payload hiện hữu; không thêm verifier.

Giữ nguyên M5/M6/M7. Các câu negative D3/E1/E2 không tái hiện một khẳng định nhân
quả tài chính sai rõ ràng đáp ứng điều kiện P1 safety correction. Source-page
contradiction là finding semantic/provenance cần sửa; chưa đổi verifier để tăng
điểm. Dataset còn có limitation availability: `derived_fact` với `operations=[]`
đi tới `render_dynamic(None)`, làm mất cả numeric candidates. Offline replay từ
response thật tái hiện đúng AttributeError; đây là pipeline failure (safe failure),
không là numerical error hoặc chứng cứ Graph OFF suy luận sai. Bounded replacements
còn gặp lỗi này ở cả OFF/ON. Đề xuất guard loại analysis không có computation và giữ
valid numeric candidates; không triển khai runtime correction ngoài đối chứng.

## 10. Cost/Latency/Token Analysis

23 clean pairs; mỗi ô là **mean / median / sample standard deviation**. Setup và
traversal là thành phần của M5, không cộng lặp vào end-to-end. Graph timings là
cumulative/request, gồm số0 khi Supervisor không yêu cầu graph.

| Chỉ số | Graph OFF | Graph ON |
| --- | ---: | ---: |
| Input tokens | 6064.83 / 5624.00 / 2751.06 | 10396.43 / 10819.00 / 3782.26 |
| Output tokens | 1164.39 / 1032.00 / 568.61 | 1186.57 / 1125.00 / 495.77 |
| Total tokens | 7229.22 / 6653.00 / 3307.50 | 11583.00 / 12013.00 / 4217.45 |
| Gateway invocations | 2.78 / 3.00 / 0.42 | 2.87 / 3.00 / 0.34 |
| Provider attempts | 2.78 / 3.00 / 0.42 | 2.87 / 3.00 / 0.34 |
| End-to-end không planning (s) | 34.52 / 35.96 / 10.22 | 55.66 / 60.17 / 21.97 |
| Graph setup/request (s) | 0.00 / 0.00 / 0.00 | 15.91 / 20.85 / 9.33 |
| Graph traversal tổng/request (s) | 0.00 / 0.00 / 0.00 | 5.23 / 5.76 / 3.09 |
| M5 stage (s) | 4.53 / 4.51 / 0.88 | 26.06 / 34.10 / 12.79 |
| M6 stage (s) | 9.66 / 10.33 / 3.69 | 9.14 / 9.72 / 3.97 |
| M7 stage (s) | 2.68 / 2.52 / 0.68 | 2.65 / 2.40 / 0.91 |

ON thêm trung bình 4353.78 tokens/lượt
(+60.22%) và
21.14s
(+61.23%). Phần lớn latency
chênh nằm ở graph setup/traversal, không phải thêm nhiều LLM calls.
Không suy luận statistical significance hoặc causal overhead chính xác từ mean;
provider/time-of-day/local cache/CPU và technical attrition vẫn có ảnh hưởng.

Mọi80 attempts cộng planning: **230 Gateway invocations,679.767 known tokens**;
18 logical calls có usage unknown. Planning chung15 calls/29.351 known tokens,
được tách khỏi bảng. Comparison executions: OFF102 calls/234.322 known tokens,
ON113 calls/416.094 known tokens; failed attempts vẫn giữ trong tổng này.
Provider attempts quan sát được cho comparison: OFF103/ON115 (218 tổng):
196 success,18 HTTP503,3 HTTP429 và1 structured-output-invalid. Các429 được rotation
hiện có xử lý; planning provider-attempt count riêng không được persist đầy đủ,
ghi **unknown**, không gán logical call count thành số attempts thực tế.
Usage của failed rotation attempts cũng chưa biết;679.767 là known subtotal,
không phải tổng billing usage đầy đủ. Provider money cost: **unknown**.

## 11. Limitations and Threats to Validity

Một công ty/một filing, 15 câu development; hai repetitions không đủ kiểm định
thống kê mạnh. Câu hỏi không blind/holdout; C1/D1 cố ý regression. Cùng một plan/câu
cô lập execution context nhưng không đo end-to-end planner variance. Order đảo
giảm một phần confounding, không loại provider load/key rotation/warmup effects.

Codex là implementation engineer và assessor, không independent human gold panel;
“độc lập” ở đây là chấm từ source/oracle, không lấy M6 hay ON answer làm truth.
Semantic scoring có judgment; lưu satisfied requirements và reasons theo từng lượt
để reviewer kiểm tra. Completeness không đo văn phong dài/ngắn. Citation binding
đúng không đồng nghĩa mọi statement trên cùng trang được entail; kiểm tra semantic
grounding riêng. Technical exclusion và bounded replacements có selection bias:52 slots clean,
nhưng23 clean pairs vẫn loại hoàn toàn A1 và một số repetitions khác. Primary
coverage60/60 không có nghĩa financial success60/60; kết luận trên phần clean
không thay thế báo cáo failure rate toàn bộ. Ưu tiên cặp clean khi so contribution.
F2 chỉ có một antecedent/tỷ lệ phù hợp, không có control đổi antecedent, nên không
chứng minh M5 đã hiểu hội thoại đầy đủ. Các caveat "thiếu dữ liệu" có scope mơ hồ
ở C3/D1 được ghi UNCERTAIN, không khẳng định toàn PDF không có thông tin ấy.

Graph v1 chủ yếu structural/contextual, source quality/scope còn giới hạn; không
tuyên bố mọi graph/text/table relation là financial evidence đã kiểm toán.

## 12. Recommendations for EF-EG and M5

Ưu tiên dùng graph cho truy vết toán hạng và khi cần phân biệt provenance/context;
giữ lựa chọn không gọi graph cho direct facts. Trước mở rộng graph, giữ các yêu cầu
người dùng trong objective, phân bổ compact context theo loại relation cần giải
thích, và làm rõ operand role so với association/context. Đây là khuyến nghị,
không thay runtime trong evaluation này hoặc tự mở FIX task.

## 13. Implications for M8

Giả thuyết có thể kiểm chứng: trên câu hỏi cần nhiều operand/source paths đã được
gán nhãn độc lập, graph context có relation coverage cân bằng cải thiện lineage
completeness so với Financial/Evidence Tools, trong khi direct-fact accuracy không
tăng và token overhead dương. M8 cần nhiều công ty/filings, blind source-grounded
gold, repeated shared-plan và end-to-end planning experiments riêng, kèm budgets.
Không dùng tập development này làm kết quả M8 hoặc kết luận EF-EG vượt trội.

Để tách ảnh hưởng relations khỏi metadata bị thiếu ở OFF, M8 nên có thêm arm
Financial/Evidence Tools với cùng page/provenance scalar như graph projection,
nhưng không có edges. Nếu lợi ích biến mất ở arm này, kết luận phù hợp là cải
thiện source projection; nếu còn, mới điều tra contribution riêng của quan hệ.

## 14. Implementation/CI Evidence

Implementation [`43c55aa3ac7b3f9cb6dc9c6b35fcbb6a61d117e1`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/43c55aa3ac7b3f9cb6dc9c6b35fcbb6a61d117e1) đã push main.
[CI42976641605](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42976641605) completed/**SUCCESS** đúng SHA: **213 Python tests PASS**,
lint/format/planning PASS; Web smoke và full regression SKIPPED đúng phạm vi.
Không gán CI này cho documentation checkpoint sau implementation.

Local staged tree:3 targeted evaluator tests PASS, Ruff check/format toàn tree,
planning checker và diff check PASS. 169 runtime Python files đúng frozen baseline;
10.670 protected files và19 unrelated pre-existing files giữ hash. PDF digest khớp
cả tám canonical document identities. Không OCR/extraction, source writes, model
khác, benchmark M8 hoặc runtime changes. Engineering CI không chứng minh financial
accuracy; research conclusions chỉ dựa trên nguồn/outputs được kiểm tra ở trên.

Registry/spec ghi tối thiểu EF-CORE-01 DONE theo xác nhận nghiệm thu của Owner trong
task EF-CORE-02 để dependency nhất quán. Các pending local approvals/code khác
không đưa vào implementation commit. Giữ nguyên mọi local edits ngoài scope.

Artifacts ignored tại `artifacts/evidence/EF-CORE-02/`: task Owner, freeze,
questions/question-oracles, source oracle/graph oracle/PDF review, shared plans,
80 run JSONs và ledgers riêng, full provider requests/responses, raw citations,
80 independent assessments, paired summary,80-answer question appendix,
supplemental COGS verification, integrity/final audit và implementation/CI receipt.
Long identities/hashes nằm trong JSON; không dùng M6 verdict làm ground truth.

Next action: Tech Lead review EF-CORE-02 cùng limitations về attrition và source projection.
