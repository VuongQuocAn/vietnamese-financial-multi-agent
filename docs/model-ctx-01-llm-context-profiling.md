# MODEL-CTX-01 — LLM Context Profiling & Token Budget for Colab T4

## 1. Executive Summary

Ngày đo: 11/11/2026 (Asia/Bangkok). Status: **REVIEW**. Baseline main `f3c571b`,
runtime comparative-period đã có tại `30710fe`; không thay đổi runtime.

20 execution scenarios, **61 captured logical LLM calls**. Qwen3-14B và
Qwen3-8B dùng tokenizer/chat template có cùng hash, đo riêng từng model cho cùng
kết quả trên toàn bộ mẫu. Baseline là **non-thinking**, giữ output cap từng stage.
8K: **17 OVERFLOW**, 2 NEAR_LIMIT;
16K và 32K: toàn bộ 61 calls FIT với margin 10%.
Input lớn nhất: `m7_composer` (CORE-FLOW-Q6-multispecialist),
8,886 tokens.
Context_required lớn nhất 12,982; cửa sổ tối thiểu phủ mẫu với 10% margin
là 14,425 tokens, nên chọn mốc thử **16.384**.

Tokenizer Llama chính thức bị `GatedRepoError`: toàn bộ counts/overflow là
**unavailable/UNKNOWN**, không dùng tokenizer thay thế. VRAM Llama vẫn ước tính
được từ architecture Meta công khai. Đề xuất thử **Qwen3-8B 4-bit / 16K /
concurrency=1 / non-thinking** đầu tiên. Chưa load model hoặc chứng minh inference T4.

## 2. Pipeline LLM Call Inventory

| Mode / stage | Provider-facing nội dung | Output cap / recovery |
| --- | --- | --- |
| M5 Lite Supervisor (`agents/lite_orchestrator.py`) | system JSON instruction/context/source inventory; user question; không full financial values mặc định | 900; một plan; failure dẫn fallback theo runtime |
| M5 Lite Specialists (`agents/specialist_common.py`) | system JSON objective/question/schema/numeric choices/evidence/calculation/graph; user question lặp | 2.500; một generate, lỗi giữ deterministic candidates/caveats |
| M5 legacy QueryPlanner (`agents/query_planner.py`) | system planner prompt/catalog/schema; user question; recovery có assistant raw JSON + user feedback | 6.000; bounded recovery và một JSON repair; mỗi lượt là context riêng |
| Document/fusion planner (`agents/qa_planning.py`) | một user JSON payload và full Pydantic schema/response_contract | 3.000; gateway structured_call; chưa có sample native trong bộ này |
| M6 Lite (`verification/lite_runtime.py`) | system semantic instructions; user JSON array claims/facts/calculations/source bindings | 2.500; một batch, tối đa 32 claims và 16.000 characters user payload; lỗi giữ uncertainty |
| M6 legacy evidence/logic critics và adaptive judge | evidence_critic/financial_logic_critic dùng system+user JSON; judge user JSON, schemas theo request/registry | 1.800/1.800/2.500; evidence binding có một corrective call; vòng lặp bị giới hạn; chưa sampled |
| M7 Lite (`outputs/qa_lite.py`) | system Vietnamese composer/JSON response instruction; user question/conversation_context/verified_claims/unverified_parts | 4.096; một generate, 48.000-character input guard, lỗi deterministic fallback |
| M7 legacy QA / report outline / grounded report writer | user JSON grounded payload, embedded schemas theo từng implementation | 1.600/1.600/2.048; deterministic assembly/fallback; chưa sampled |

Các code path trên được inventory trực tiếp, không mặc định M7 deterministic.
`deterministic` không gọi LLM cho M5/M6; `gemini` và `auto` chỉ gọi khi được bật
Gateway và branch có nhu cầu; auto có fallback. M7 Lite còn phụ thuộc release mode,
allow_gateway và có verified findings; cache/reuse có thể bỏ Supervisor hoặc M5.
20 scenario này không đại diện mọi legacy execution mode; không suy ngân sách
legacy 6K-output từ Lite 900-output.

Gateway `llm_gateway.py` validate/bind/schema attestation, không tự thêm prompt.
`request_gateway.py` giữ deadline/call budget, sửa timeout và cho tối đa một retry
429 đủ điều kiện; không thêm message. `qa_gateway.py` pool có credential rotation
theo policy chung, không đổi model/prompt; không retry vô hạn. Một retry transport
có cùng payload không biến thành context nối dài. Dataset thống kê **logical
generate requests**, không phải số HTTP attempts hay tổng tokens toàn execution;
per-call artifact giữ provider_attempt usage/error khi trace có. Usage cột Gemini
là response cuối của logical call, không cộng retry usage vào input context.

GeminiAdapter `_config` chuyển system thành `system_instruction.parts`, assistant
thành role `model`, nội dung còn lại vào `contents[].parts[].text`; temperature,
max_output_tokens, MIME JSON và timeout/retry HTTP tách khỏi text. `schema_ref`
nếu có được registry resolve thành `response_json_schema` ngoài prompt. **Mọi
sample hiện tại schema_ref=null**, không có native schema cần giả lập đưa vào
Qwen prompt; `analysis_schema` đã nhúng trong system được đếm đầy đủ.

## 3. Dataset and Payload Sources

- EF-CORE-02: repetition 1 của A1/B2/C1/D1/E2/F2, cả OFF/ON: 12 scenarios.
- CORE-PERIOD-01: L2-confirmation (CORE Q5 intent), L3 (C3), L5: 3 scenarios.
- EF-CORE-03: C1-C-retry1 (G3/C1), D1-C-final-retry1 (G5/D1), B2-C-retry1: 3.
- EF-CORE-03 semantic-probe: batch gần guard, 1 scenario.
- CORE-FLOW-01/live-initial Q6: 1 scenario, hai Specialists profitability và
  liquidity_and_leverage, giữ cả M6 và M7; graph chưa tích hợp ở checkpoint này.

A1 direct fact; B2 metric/gross margin; C1/L3/L5 cross-period; Q6 multi-indicator
và multi-specialist; D1 table/text/source context; E2 negative missing customers;
F2 follow-up có conversation_context. Không cộng calls của nhiều Specialists
thành một prompt. Source versions khác nhau được giữ trong source paths/scenario
IDs; không gọi các historical traces là fresh measurements của HEAD. EF03 retry
files được chọn để có payload sửa graph; các error calls trong file vẫn được đo.

Artifacts nguồn có request/response Gateway, không lưu SDK wire capture gốc.
Đã chạy chính GeminiAdapter `_config` offline để tái dựng provider-facing request,
assert exact message text/roles round-trip. Adapter source không thay đổi so HEAD.
Không tái chạy pipeline, OCR, Gemini hay M8. Hash trước/sau cho 20 source files
khớp; raw nguồn chỉ đọc. Schema/default null trong trace model_dump được bỏ ở
generation/constraints để phục hồi omitted defaults; explicit null thật sẽ bị
adapter từ chối. Đây là giới hạn reconstruction, không phải wire capture mới.

## 4. Tokenizers and Counting Methodology

- `Qwen/Qwen3-14B`: revision `40c069824f4251a91eefaf281ebe4c544efd3e18`, status `exact_local`
- `Qwen/Qwen3-8B`: revision `b968826d9c46dd6066d109eabc6255188de91218`, status `exact_local`
- `meta-llama/Llama-3.1-8B-Instruct`: revision `unavailable`, status `unavailable`

Transformers `4.57.6`, CPU, không torch/model weights.
Tải đúng tokenizer.json/tokenizer_config.json/config.json ở revision cố định;
hash files và chat template ở tokenizer-metadata.json. Tải Llama không dùng token
quyền truy cập, không vượt access gate. Llama metadata ghi unavailable.

`apply_chat_template(tokenize=True, add_generation_prompt=True,
enable_thinking=False)` đếm role delimiters/special tokens và assistant generation
prefix. Hai Qwen được load/đếm riêng; cùng tokenizer hash giải thích counts bằng
nhau, không lấy Gemini làm proxy. `enable_thinking=True` được đo riêng với reserve
sensitivity +4.096 reasoning tokens. Đây là **giả định thử budget**, không prediction
độ dài reasoning. Nếu vẫn giữ cap cũ, reasoning phải chia sẻ cap với JSON và có
nguy cơ thiếu output; không mặc định thinking miễn phí.

`exact_local` chỉ có nghĩa exact cho **rendered input template được chọn**.
Exact message text đã tái dựng; Gemini provider-side control/schema/wrapper
overhead **unknown**. Không có Gemini tokenizer local/countTokens call; không gọi
số đếm Qwen là exact Gemini. HTTP JSON keys, timeout, temperature không phải prompt
text tokens. Backend Qwen/Llama tương lai chưa triển khai; nếu backend thêm wrapper,
schema hoặc đổi template phải đo lại. Không chèn output Gemini vào request mới,
trừ phần history đã thật sự tồn tại trong captured request.

## 5. Per-Agent Token Statistics

Qwen3-14B **và** Qwen3-8B: cùng bảng sau, đơn vị tokens/call. P95 nội suy tuyến
tính `(n-1)*0,95`, là **sample percentile**, không bảo đảm production.

| Agent | n | Min | Median | P95 | Max | Mean | Output reserve |
| --- | --- | --- | --- | --- | --- | --- | --- |
| liquidity_and_leverage | 8 | 1,957 | 6,978.5 | 8,417.6 | 8,419 | 5,528.9 | 2500 |
| m6_semantic | 18 | 620 | 1,371.0 | 3,171.2 | 5,456 | 1,682.1 | 2500 |
| m7_composer | 19 | 770 | 3,045 | 6,994.2 | 8,886 | 3,573.4 | 4096 |
| profitability | 12 | 1,239 | 2,287.0 | 8,155.9 | 8,305 | 4,119.2 | 2500 |
| supervisor | 4 | 1,708 | 1,817.0 | 1,822.7 | 1,823 | 1,791.2 | 900 |

Gemini provider-reported input, tách riêng exact local; missing không biến thành 0:

| Agent | Known n | Unknown n | Min | Median | P95 | Max | Mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| liquidity_and_leverage | 8 | 0 | 1,975 | 7,336.5 | 8,833.6 | 8,835 | 5,782.1 |
| m6_semantic | 17 | 1 | 889 | 1,535 | 3,454.6 | 5,869 | 1,820.2 |
| m7_composer | 16 | 3 | 746 | 3,057.5 | 6,442.2 | 6,815 | 3,423.7 |
| profitability | 11 | 1 | 1,224 | 2,607 | 8,648.5 | 8,810 | 4,576.1 |
| supervisor | 4 | 0 | 1,763 | 1,871.5 | 1,877.8 | 1,878 | 1,846 |

Llama: request_count theo cùng agent, nhưng measured n=0; min/median/P95/max/mean
đều unavailable. Mẫu không có cash-flow Specialist provider request; không suy
ngân sách cash-flow từ profitability. Supervisor ít samples vì EF02 replay cached
plans và EF03 retry không chạy lại Supervisor; riêng Q6 có hai Specialists.

## 6. Model-Specific Context Requirements

Trong các ô fit: **FIT / NEAR_LIMIT / OVERFLOW / UNKNOWN**, kèm tỷ lệ từng loại.
Output reserve đã cộng, safety margin=10% toàn context window.

| Model | Agent | P95 input | Max input | 8K fit | 16K fit | 32K fit |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3-14B | liquidity_and_leverage | 8,417.6 | 8,419 | 3 (37.5%)/0 (0.0%)/5 (62.5%)/0 (0.0%) | 8 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 8 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Qwen3-14B | m6_semantic | 3,171.2 | 5,456 | 17 (94.4%)/1 (5.6%)/0 (0.0%)/0 (0.0%) | 18 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 18 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Qwen3-14B | m7_composer | 6,994.2 | 8,886 | 11 (57.9%)/1 (5.3%)/7 (36.8%)/0 (0.0%) | 19 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 19 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Qwen3-14B | profitability | 8,155.9 | 8,305 | 7 (58.3%)/0 (0.0%)/5 (41.7%)/0 (0.0%) | 12 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 12 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Qwen3-14B | supervisor | 1,822.7 | 1,823 | 4 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 4 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 4 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Qwen3-8B | liquidity_and_leverage | 8,417.6 | 8,419 | 3 (37.5%)/0 (0.0%)/5 (62.5%)/0 (0.0%) | 8 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 8 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Qwen3-8B | m6_semantic | 3,171.2 | 5,456 | 17 (94.4%)/1 (5.6%)/0 (0.0%)/0 (0.0%) | 18 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 18 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Qwen3-8B | m7_composer | 6,994.2 | 8,886 | 11 (57.9%)/1 (5.3%)/7 (36.8%)/0 (0.0%) | 19 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 19 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Qwen3-8B | profitability | 8,155.9 | 8,305 | 7 (58.3%)/0 (0.0%)/5 (41.7%)/0 (0.0%) | 12 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 12 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Qwen3-8B | supervisor | 1,822.7 | 1,823 | 4 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 4 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) | 4 (100.0%)/0 (0.0%)/0 (0.0%)/0 (0.0%) |
| Llama-3.1-8B-Instruct | liquidity_and_leverage | unavailable | unavailable | 0 (0.0%)/0 (0.0%)/0 (0.0%)/8 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/8 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/8 (100.0%) |
| Llama-3.1-8B-Instruct | m6_semantic | unavailable | unavailable | 0 (0.0%)/0 (0.0%)/0 (0.0%)/18 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/18 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/18 (100.0%) |
| Llama-3.1-8B-Instruct | m7_composer | unavailable | unavailable | 0 (0.0%)/0 (0.0%)/0 (0.0%)/19 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/19 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/19 (100.0%) |
| Llama-3.1-8B-Instruct | profitability | unavailable | unavailable | 0 (0.0%)/0 (0.0%)/0 (0.0%)/12 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/12 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/12 (100.0%) |
| Llama-3.1-8B-Instruct | supervisor | unavailable | unavailable | 0 (0.0%)/0 (0.0%)/0 (0.0%)/4 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/4 (100.0%) | 0 (0.0%)/0 (0.0%)/0 (0.0%)/4 (100.0%) |

Giữ reserve hiện tại tránh kết luận input vừa cửa sổ là FIT. Cửa sổ 16K phủ mẫu
hai Qwen ở non-thinking, không nói tất cả workload thực tế/legacy đều vừa 16K.

## 7. Graph ON/OFF Token Impact

Chỉ so matched EF02 r1 ở cùng checkpoint; không trộn EF03 prompts sửa đổi vào
paired delta. Cột tổng là **tổng input execution OFF/ON**, chỉ đo chi phí,
**không phải context window**.

| Pair | Specialist OFF | Specialist ON | Delta | Full graph tokens ON | Citations cost OFF/ON | Execution input OFF/ON |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 1239 | 1239 | 0 | 0 | 0/0 | 3035/2009 |
| B2 | 1765 | 6647 | 4882 | 4315 | 0/1348 | 6832/10693 |
| C1 | 2011 | 6891 | 4880 | 4313 | 0/1326 | 5831/13166 |
| D1 | 1957 | 6825 | 4868 | 4298 | 0/1557 | 5365/10519 |
| E2 | 1800 | 1800 | 0 | 0 | 0/0 | 4430/4472 |
| F2 | 2254 | 7132 | 4878 | 4307 | 0/1557 | 5028/8851 |

B2/C1/D1/F2 tăng lần lượt 4.882/4.880/4.868/4.878 tokens, mean **4.877**.
Tính cả A1/E2 không nhận graph: mean **3.251,3** trên sáu cặp. Graph ON flag không
đồng nghĩa graph text xuất hiện. Full graph chiếm khoảng 60–65% Specialist input
trong bốn cặp nhận graph; actual full projection counts ở bảng, đây là view có
chồng lặp citations với breakdown bên dưới.

| Scenario | Graph tokens | Unique node references | Unique edge projections | Relation types | Tokens/displayed edge |
| --- | --- | --- | --- | --- | --- |
| EF02-B2-on | 4315 | 5 | 4 | used_in, associated_with | 1078.8 |
| EF02-C1-on | 4313 | 5 | 4 | used_in, associated_with | 1078.2 |
| EF02-D1-on | 4298 | 6 | 4 | used_in, associated_with, from_source | 1074.5 |
| EF02-F2-on | 4307 | 5 | 4 | used_in, associated_with, from_source | 1076.8 |
| PERIOD-L2-confirmation | 4559 | 6 | 4 | used_in, associated_with, from_source, same_extraction_context | 1139.8 |
| PERIOD-L3 | 4559 | 6 | 4 | used_in, associated_with, from_source, same_extraction_context | 1139.8 |
| PERIOD-L5 | 4307 | 6 | 5 | used_in, associated_with, from_source | 861.4 |
| EF03-C1-C-retry1 | 4071 | 5 | 4 | used_in, associated_with, from_source | 1017.8 |
| EF03-D1-C-final-retry1 | 3928 | 5 | 4 | used_in, associated_with, from_source | 982.0 |
| EF03-B2-C-retry1 | 4071 | 5 | 4 | used_in, associated_with, from_source | 1017.8 |

Unique nodes tính bằng endpoint references, edges bằng canonical projection JSON;
đây là thông tin **trong prompt**, không phải tổng graph store. Token/edge là chi
phí per displayed relation, **không phải per useful relation**. Output mẫu không
trích explicit quoted G handles; Specialists có thể dùng evidence IDs/nội dung
relations mà không nhắc G ID. Vì không có causal attribution hoặc independent
usefulness labels, useful relation count và tokens/useful relation **UNKNOWN**.
Không kết luận graph vô ích hay tăng accuracy từ sự vắng G handles. Những call
graph dài mà không có attribution là ưu tiên đánh giá/relevance trimming sau này.

## 8. Component-Level Token Breakdown

Phân loại deterministic theo JSON keys: source_metadata/citations/sources vào
provenance trước; schema và history tokenize nguyên subtrees; phần graph còn lại,
facts/metrics/instructions/question tokenize leaf fragments độc lập. Null/empty
history vẫn có vài token serialization. Instruction có JSON response skeleton
không tách được exact khỏi tự nhiên. `other` chứa claim statements/scope/caveats
chưa phân loại, và chênh lệch boundaries/keys được ghi riêng per call.
**Không ép tổng bằng rendered total** vì keys/punctuation/BPE boundaries khác.
Số phần trăm dưới đây là cost-view chia tổng rendered input theo stage, không phải
partition accounting exact; full graph ở mục 7 overlap citations ở đây.

| Agent | Component | Isolated tokens (sum) | % stage rendered input |
| --- | --- | --- | --- |
| liquidity_and_leverage | instructions | 5,742 | 13.0% |
| liquidity_and_leverage | question | 598 | 1.4% |
| liquidity_and_leverage | conversation | 0 | 0.0% |
| liquidity_and_leverage | financial_facts | 2,401 | 5.4% |
| liquidity_and_leverage | calculated_metrics | 2,136 | 4.8% |
| liquidity_and_leverage | graph | 9,431 | 21.3% |
| liquidity_and_leverage | citations | 12,188 | 27.6% |
| liquidity_and_leverage | schema | 2,800 | 6.3% |
| liquidity_and_leverage | other | 0 | 0.0% |
| liquidity_and_leverage | boundary/key difference (not exact attribution) | 8,935 | 20.2% |
| m6_semantic | instructions | 4,258 | 14.1% |
| m6_semantic | question | 1,448 | 4.8% |
| m6_semantic | conversation | 0 | 0.0% |
| m6_semantic | financial_facts | 3,265 | 10.8% |
| m6_semantic | calculated_metrics | 1,562 | 5.2% |
| m6_semantic | graph | 0 | 0.0% |
| m6_semantic | citations | 5,922 | 19.6% |
| m6_semantic | schema | 0 | 0.0% |
| m6_semantic | other | 8,727 | 28.8% |
| m6_semantic | boundary/key difference (not exact attribution) | 5,095 | 16.8% |
| m7_composer | instructions | 6,534 | 9.6% |
| m7_composer | question | 949 | 1.4% |
| m7_composer | conversation | 161 | 0.2% |
| m7_composer | financial_facts | 32,108 | 47.3% |
| m7_composer | calculated_metrics | 13,777 | 20.3% |
| m7_composer | graph | 0 | 0.0% |
| m7_composer | citations | 0 | 0.0% |
| m7_composer | schema | 0 | 0.0% |
| m7_composer | other | 494 | 0.7% |
| m7_composer | boundary/key difference (not exact attribution) | 13,872 | 20.4% |
| profitability | instructions | 8,391 | 17.0% |
| profitability | question | 707 | 1.4% |
| profitability | conversation | 0 | 0.0% |
| profitability | financial_facts | 2,499 | 5.1% |
| profitability | calculated_metrics | 2,504 | 5.1% |
| profitability | graph | 11,143 | 22.5% |
| profitability | citations | 9,353 | 18.9% |
| profitability | schema | 4,200 | 8.5% |
| profitability | other | 0 | 0.0% |
| profitability | boundary/key difference (not exact attribution) | 10,633 | 21.5% |
| supervisor | instructions | 1,192 | 16.6% |
| supervisor | question | 185 | 2.6% |
| supervisor | conversation | 0 | 0.0% |
| supervisor | financial_facts | 4,068 | 56.8% |
| supervisor | calculated_metrics | 0 | 0.0% |
| supervisor | graph | 0 | 0.0% |
| supervisor | citations | 0 | 0.0% |
| supervisor | schema | 0 | 0.0% |
| supervisor | other | 372 | 5.2% |
| supervisor | boundary/key difference (not exact attribution) | 1,348 | 18.8% |

Trong các graph B2/C1/D1 ON của EF02 có 8 citation/source-metadata subtrees nhưng
chỉ 5 payload unique trong mỗi prompt; đây là lặp nội dung exact có thể rà soát.
Key source identity vẫn phải giữ trong mọi reference cần resolve.

Overhead lớn nhất của Specialist là graph projection, trong đó citation/source
metadata và selectors lặp chiếm phần đáng kể. Embedded analysis_schema có cost
thật nhưng nhỏ hơn graph/evidence; không có native schema overhead cần cộng giả.
M7 chủ yếu là verified claims/calculation rendering; citations nguồn chi tiết
được assembly giữ bên ngoài prompt M7 này, nên category citations có thể bằng 0.
Không diễn giải 0 là đầu ra mất provenance.

## 9. Context Overflow Analysis

Mỗi hai Qwen: aggregate non-thinking {"8192": {"FIT": 42, "NEAR_LIMIT": 2, "OVERFLOW": 17}, "16384": {"FIT": 61}, "32768": {"FIT": 61}}.
Llama: 61/61 UNKNOWN ở cả ba cửa sổ. 8K có nguy cơ cao nhất ở Specialists có graph
và M7 vì reserve 4.096; M6 semantic-probe sát giới hạn dù chưa overflow.
Thinking với **thêm** 4.096 output reserve: {"8192": {"NEAR_LIMIT": 12, "FIT": 5, "OVERFLOW": 44}, "16384": {"FIT": 56, "NEAR_LIMIT": 4, "OVERFLOW": 1}, "32768": {"FIT": 61}}.
Đây là sensitivity trên cùng payload, không suy thinking quality hay duration.

M6 batch lớn nhất có user JSON gần 16.000-character guard; còn ít margin tại 8K.
Không có evidence để khẳng định mọi batch đều quá nhiều claims; cần token-aware
batch sizing nếu giữ 8K, thay vì chỉ character/count limits. Conversation trong
F2 là ngắn (thực tế chủ yếu M7); chưa có long-history sample, do đó **chưa biết**
overflow của hội thoại dài. Các bounds characters hiện hữu không quy đổi cố định
sang token cho mọi ngôn ngữ/model.

## 10. T4 VRAM Feasibility Estimates

Ước tính, **không load/inference**. Một model/request, standard full attention,
FP16 KV, batch/concurrency=1. Qwen configs được tải chính thức theo revision ở mục
4: [14B config](https://huggingface.co/Qwen/Qwen3-14B/blob/40c069824f4251a91eefaf281ebe4c544efd3e18/config.json),
[8B config](https://huggingface.co/Qwen/Qwen3-8B/blob/b968826d9c46dd6066d109eabc6255188de91218/config.json).
Llama lấy arch_args Instruct 8B từ
[Meta SKU source](https://raw.githubusercontent.com/meta-llama/llama-models/0e0b8c519242d5833d8c11bffc1232b77ad7f301/models/sku_list.py); head_dim=dim/n_heads,
không suy KV heads từ parameter count. Cả ba không sliding-window trong cấu hình
baseline này. Nguồn/hash/config đã lưu trong configs/tokenizers artifacts.

`KV bytes = tokens × layers × KV_heads × head_dim × 2(K,V) × 2(FP16)`.
Weights lower bound dùng approximate params 14,8B/8,2B/8,03B ×0,5 bytes, không phải
đo checkpoint AWQ/GPTQ. Giả định quantization metadata/unquantized tensors cộng
10–30% weights; runtime/activation/allocator reserve 1,5–3 GiB. Đây là sensitivity
range chọn thử nghiệm, không là guaranteed upper bound; prefill lớn/kernel/backend
có thể dùng nhiều hơn. Dùng **GiB**, T4 quảng cáo 16GB không bảo đảm 16GiB usable.

| Model | Layers | KV heads | Head dim | KV bytes/token | 4bit weights lower GiB | KV GiB 8/16/32K | Total GiB 8/16/32K |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3-14B | 40 | 8 | 128 | 163840 | 6.89 | 1.250/2.500/5.000 | 10.33–13.21/11.58–14.46/14.08–16.96 |
| Qwen3-8B | 36 | 8 | 128 | 147456 | 3.82 | 1.125/2.250/4.500 | 6.83–9.09/7.95–10.21/10.20–12.46 |
| Llama-3.1-8B-Instruct | 32 | 8 | 128 | 131072 | 3.74 | 1.000/2.000/4.000 | 6.61–8.86/7.61–9.86/9.61–11.86 |

Qwen14B 8K có room VRAM hơn nhưng overflow context; 16K là thử nghiệm có rủi ro
OOM/margin tùy usable VRAM/backend, 32K đặc biệt rủi ro. Qwen8B 16K có headroom
ước tính tốt hơn; 32K là optional GPU experiment sau khi 16K ổn định. Llama 16K/32K
memory range có thể đáng thử nhưng tokenizer/context demand còn UNKNOWN.
Không mặc định T4/backend hỗ trợ BF16, FP8 hoặc quantized KV; nếu thử KV quantized
phải kiểm chứng kernel, memory và chất lượng riêng. Chưa chọn backend/quant format.

## 11. Recommended Token Budgets

Budget **thử nghiệm**, không sửa runtime trong task. Input cap dưới đây làm tròn
tăng từ max mẫu; reserve giữ nguyên cap JSON hiện có. Tổng phải còn margin 10%.

| Stage | Input budget thử | Output reserve non-thinking | Window |
| --- | ---: | ---: | --- |
| Supervisor Lite | 2.048 | 900 | 8K đủ mẫu; shared model có thể dùng 16K |
| Profitability | 9.216 | 2.500 | 16K |
| Liquidity/leverage | 9.216 | 2.500 | 16K |
| Cash-flow/other Specialists | TBD, chưa measured | giữ cap code 2.500 | đo sample trước kết luận |
| M6 semantic | 6.144 | 2.500 | 16K có margin; 8K không phủ budget |
| M7 Lite | 9.216 | 4.096 | 16K |

Output Gemini quan sát để tham khảo, **không đủ** cắt cap cho model mới:

| Stage | Known n | Median output | P95 output | Max output | Reserve |
| --- | --- | --- | --- | --- | --- |
| liquidity_and_leverage | 8 | 572.0 | 848.9 | 864 | 2500 |
| m6_semantic | 17 | 193 | 306.4 | 332 | 2500 |
| m7_composer | 16 | 646.5 | 865.5 | 879 | 4096 |
| profitability | 11 | 395 | 1,074.0 | 1,087 | 2500 |
| supervisor | 4 | 137.0 | 237.4 | 255 | 900 |

Giữ reserve theo stage vì chưa biết output tokenization/reasoning của Qwen trên
JSON thực tế. Thinking thêm 4.096 là sensitivity, chưa là budget được nghiệm thu;
không cộng 4.096 mà vẫn tuyên bố mọi stage FIT mặc định.

| Model | Context thử nghiệm | Stage rủi ro nhất | Output reserve | Kết luận |
| --- | --- | --- | --- | --- |
| Qwen3-14B 4-bit | 8K đối chứng, 16K mục tiêu | Graph Specialists/M7 tại 8K | 900/2.500/2.500/4.096 theo stage | 8K không phủ mẫu; 16K token-fit, GPU/OOM chưa kiểm chứng |
| Qwen3-8B 4-bit | **16K đầu tiên**, 32K optional | Graph Specialists/M7, M6 batch lớn | cùng cap stage, non-thinking | phù hợp nhất để thử T4 theo demand/memory, chưa kết luận chất lượng |
| Llama 3.1 8B 4-bit | 16K rồi cân nhắc 32K | UNKNOWN theo tokenizer | cap stage chỉ là khởi điểm, cần đo lại | cần quyền tokenizer trước budget exact; GPU benchmark sau |

## 12. Optimization Priorities

1. Đo/giảm source metadata, selectors và citations trùng trong graph; giữ source
   identity, page, quality/uncertainty và mapping quay về full source record.
2. Chỉ giữ graph neighborhood liên quan objective; bảo toàn operand roles,
   used_in/from_source/associated_with và phân biệt structural với semantic support.
3. Giảm lặp giữa evidence/numeric_choices/calculation/graph bằng reference có
   khả năng resolve; giữ đủ source facts, hai kỳ và calculation trace.
4. Với M7, giữ verified findings liên quan question, calculation display và gaps;
   không bỏ claim cần thiết để ép 8K. Không cắt ngẫu nhiên cuối prompt.
5. Nếu cần 8K, kiểm tra M6 token-aware batching và history summarization có giữ
   tham chiếu; mẫu ngắn hiện tại chưa chứng minh long conversation ổn định.
6. Schema verbosity là ưu tiên sau graph/source repetition; chỉ bỏ nhúng schema
   nếu backend structured output hỗ trợ và đã đo wrapper thực tế.

Không bắt buộc tối ưu prompt trước **thử serving 8B/16K** theo mẫu non-thinking;
nếu bắt buộc 14B/8K thì phải tối ưu có kiểm chứng trước khi phục vụ đầy đủ workload.
Không đổi prompt/EF-EG/runtime, không đưa ra optimization quality claim trong task.

## 13. Limitations and Validation Needs

Một company/report persisted, historical prompts có version khác nhau, sample
selection có chủ đích coverage chứ không random workload. Chỉ ba baseline period
Supervisor calls cộng một Q6; không long history/cash-flow/legacy serving samples.
Semantic-probe là controlled re-verification của claims thực, không fresh user E2E.
61 observations là logical requests; physical retry count/usage có thể khác và
không được dùng làm context sum. P95 nhỏ mẫu không bảo đảm percentile deployment.

Llama unavailable là giới hạn chấp nhận theo spec, không dùng approximate tokenizer
để điền bảng exact. Provider SDK wire capture không tồn tại; reconstructed text
exact nhưng Gemini native hidden overhead unknown. Chưa có backend OSS để xác nhận
response-format behavior. Ước tính VRAM không là benchmark. Chưa đánh giá chất lượng
Qwen/Llama, GPU latency/OOM, JSON completion, reasoning hoặc financial accuracy.

Bước tiếp theo thuộc task riêng: chọn tokenizer-access/backend/quant format, load
một model trên T4, đo usable VRAM, prefill/decode và JSON grounded output ở 16K
trước 32K. Không thực hiện Colab API/M8 trong MODEL-CTX-01.

## 14. Implementation/CI Evidence

Script: [profile_model_context.py](../scripts/profile_model_context.py).
Targeted tests: [test_model_context_profile.py](../tests/unit/test_model_context_profile.py).
Artifacts ignored: `artifacts/evidence/MODEL-CTX-01/`: per-call payloads/hashes,
source inventory/integrity, tokenizer metadata, per-component costs, percentile
statistics, fit matrix, graph comparison và VRAM configurations/calculations.
Raw financial prompts không commit. Script copy và report generator ở artifact dir.

Reproduce trong env riêng (không cần torch): cài project dependencies và
`transformers==4.57.6`, rồi chạy
`python scripts/profile_model_context.py --download-tokenizers`; sau lần đầu bỏ
flag để offline. Script dùng revision cố định, không tải weights. Cần có các local
ignored source traces nêu ở mục 3; không tự gọi Gemini để thay thế source thiếu.

Validation local: 3 targeted tests PASS; 4 actual Qwen deterministic/template
checks PASS; Ruff trên staged tree, planning và diff checks PASS.
Implementation [8b78f34](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/8b78f342433d639c09425e0cf513b6e14b82b3c5); [CI 42995134599](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42995134599) SUCCESS đúng implementation SHA; 234 Python PASS, Web/full regression SKIPPED. Các checks là engineering evidence cho profiler,
không phải financial-quality hoặc GPU-serving PASS.
Receipt local ghi implementation SHA, CI head SHA và scope/source integrity.
Checkpoint tài liệu sau implementation không được gán là SHA chạy CI.
Next action: Tech Lead review MODEL-CTX-01 và quyết định task Colab serving.
