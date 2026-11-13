# V2-INT-01 — Minimal Integration Migration

**REVIEW — chờ Tech Lead nghiệm thu**, 13/11/2026 (Asia/Bangkok).
Baseline kiểm toán `3475a3af8a2d1635bfa6037c0743245ba2a3e9e5` + existing local edits.
Bàn giao qua nhánh `review/v2-int-01`, không push hoặc merge vào `main`.
ARCH-RESET-01 đã được Owner/Tech Lead APPROVED; không audit lại hoặc triển khai
report writer/Ledger refactor lớn. Không coi 12/12 Qwen PASS là điều kiện duy nhất.

## Thay đổi đã triển khai

- Request opt-in `integration_v2=true` chọn M5/M6/M7 Lite nhất quán; default paths
  vẫn giữ. Không bật V2 toàn bộ frontend hoặc tự đổi model/provider.
- [lite_orchestrator.py](../src/agents/lite_orchestrator.py): supervisor có một
  contract requirements/tasks; task có IDs/assignments/dependencies. Parse từng
  task độc lập, giữ task hợp lệ, ghi lỗi phần hỏng thay vì thay toàn plan bằng
  lexical fallback. Plan không đủ vẫn hiện trạng thái unresolved/technical.
- [integration_workspace.py](../src/agents/integration_workspace.py): workspace
  chỉ sống trong request. Retrieve các nguồn đã chọn trước, gộp exact evidence/
  lineage, cấp handles theo reference; cả ba specialists dùng được nguồn khác
  domain trong cùng scope. Task sau nhìn task results và calculation proofs;
  task liên nhánh có owner hiện có, không thêm agent/DAG framework/database.
- Numeric source candidates tồn tại độc lập với analysis/model failure. Renderer
  V2 chọn fiscal/as-of wording theo evidence, không theo domain của specialist.
  Candidate aggregation giữ origins; task lỗi không xóa siblings.
- [lite_runtime.py](../src/verification/lite_runtime.py): M6 V2 kiểm nguồn/phép tính
  bằng validator/tools hiện có; typed premises dùng exact backend rendering và
  independently stored row label khi grammar cũ không hiểu. Value/unit/period/
  identity/citations vẫn hydrate và đối chiếu. Không ACCEPT global absence từ
  retrieval miss. Semantic batch không nhận whole question ngoài claim scope;
  relevance tới requirement được trả riêng qua `supported_requirement_ids`.
- Arithmetic claim đúng có thể ACCEPT nhưng chưa đáp ứng một named requirement.
  Binding của derived/interpretation cần semantic confirmation trong **cùng một
  M6 batch**, không thêm verifier hoặc semantic call thứ hai. Không có verdict
  relevance thì giữ arithmetic đúng và coverage chưa đủ.
- Policy mới `verification_lite_v2`; readers và decision replay cũ giữ nguyên.
  Requirements/coverage ở request sidecar, không sửa historic claim identity,
  content hoặc digests. Binding sang verified IDs xử lý cả admission dedup/reuse.
- [qa_lite.py](../src/outputs/qa_lite.py): V2 dùng requirement bindings từ M6 và
  ledger admission cho coverage; không dựng lại requirement list từ prose. M7
  render ACCEPT, nêu tên phần chưa đáp ứng, không thêm calculations hoặc nhận định.
  Không cần reorder LLM call trong profile tối thiểu.
- [financial_qa_pipeline.py](../src/api/financial_qa_pipeline.py),
  [fusion_pipeline.py](../src/api/fusion_pipeline.py): mixed/document V2 vào cơ chế
  composition/fusion hiện có dù bật M7 Lite; subrequest được ghim financial/document
  lane để không phân rã lại đệ quy. Document source verification/final fusion composer
  vẫn tái sử dụng code hiện có, chưa thay toàn bộ document/report coverage bằng V2.
- Qwen boundary chỉ unwrap **một** outer `json` markdown fence đúng hình dạng,
  vẫn giữ raw text và transport metadata qua serialization; không sửa nội dung
  JSON, unknown IDs hoặc retry. JSONOutput/schema có optional wrapper metadata;
  default serialization cũ không thêm field null.
- Checker planning nhận `ARCH-RESET-01` và `V2-INT-01`; nghiệm thu ARCH ghi DONE
  trên đúng report-only SHA đã push. V2 vẫn REVIEW; implementation chỉ đưa lên nhánh review.

## Offline evidence

Lệnh: `.venv/Scripts/python.exe scripts/replay_v2_integration.py`.
Artifacts riêng ignored: `artifacts/evidence/V2-INT-01/offline/`.

| Control | Kết quả thực tế | Giới hạn |
| --- | --- | --- |
| C01 saved supervisor plan + explicit requirement binding fixture | 3 task thực thi; 7 shared evidence identities; handles nhất quán giữa roles, assignments giữ; valid root-field salvage | Counterfactual có gắn nhãn: backend fixture thêm IDs, không giả Qwen đã sinh decomposition V2. Không suy PASS toàn câu từ numeric candidates. |
| C04 saved M5 candidates | Ba absence claims không ACCEPT; independent supported numeric claims vẫn ACCEPT | Không chạy lại retrieval/model, không khẳng định corpus search đã đầy đủ. |
| C10 saved M5 candidates | Hai proofs đúng -600.656.455.132 VND và 0,560933688… ratio cùng current-assets fact được ACCEPT; model subtraction sai không ACCEPT | Kiểm boundary/canonical replay, không chứng minh Qwen mới chọn đúng operands hoặc sinh đúng câu trả lời. |
| Historic ledger | 22/22 entries validate/replay và serialize nguyên vẹn, không migrate | Replay consistency không chứng minh financial correctness của false ACCEPT lịch sử. |
| Data preservation | E2E source JSON unchanged; 607/607 non-runtime protected files khớp freeze | Runtime chủ ý thay; không nói cả778protected hashes vẫn unchanged sau implementation. |

Ba tests integration mới kiểm plan/transport round-trip, shared context/dependent
task và sibling failure, native M6→ledger→M7 IDs, local semantic/relevance binding,
mixed routing không bị presentation flag bỏ qua, bound lane không re-enter fusion,
schema failure có `internal_error` thay vì giả API unavailable. Fixtures synthetic
chỉ là engineering controls.

Các runs thực tế (có overlap, không cộng thành số tests độc lập):

- Nhóm Lite/API/Gateway/adapter: 272 PASS, 1 FAIL do schema artifact chưa cập nhật.
- Sau đồng bộ schema: integration + schema drift + Qwen adapter **7 PASS**.
- Sau sửa prompt/lane: integration + financial pipeline + fusion **43 PASS**.
- Sau refinement M6 binding: integration + M6 Lite **6 PASS**.
- Sau thêm control phân loại plan error: integration cuối **3 PASS**.
- Ruff lint/format, planning checker **143 tasks**, diff check đạt. Không full CI,
  browser/OCR/Gemini/M8. Không gọi engineering tests là financial quality.

## Một lượt Qwen được duyệt

Owner duyệt 3 case / tối đa18 calls / 180.000tokens, 6calls và300giây/case,
không retry, dừng khi API lỗi hoặc chạm ngân sách. Đã chạy đúng một lượt
C01 coordination, C10 derived boundary, C07 financial+document bằng config riêng
ignored. Không preflight inference riêng; không ghi URL/key vào source/report.

**8 calls / 15.876 tokens, 0 retry, 0 lỗi API**. Provider trả success cho cả8calls;
model alias `qwen3-8b-awq-t4`, chưa xác minh weights/revision độc lập.

| Case | Kết quả của snapshot đã chạy | Nguyên nhân có bằng chứng |
| --- | --- | --- |
| C01 | 1call,14,89s;0released claims; public status provider_unavailable | Prompt còn chứa instruction envelope cũ `{tasks:...}` cùng contract V2 mới. Model trả ba tasks đúng kiểu cũ, thiếu requirements/IDs; parser báo invalid task/plan incomplete. API vẫn success: status unavailable là phân loại lỗi tích hợp sai. |
| C10 | 1call,11,07s;0released claims; public status provider_unavailable | Cùng prompt conflict; model trả một liquidity task không requirement IDs. Chưa tới tools/M6 nên không dùng case này đánh giá typed verifier mới. |
| C07 | 6calls,194,22s;0released claims; verification_blocked | Fusion planner đã gọi cả financial/document lane nhưng còn gán policy mục tiêu vào financial lane; child được phân rã lại do không ghim lane, tiêu hết6calls. Đây là lỗi tích hợp cộng với routing của model, không bằng chứng B09 không có nguồn. |

### C01 — Coordination: câu hỏi và câu trả lời thực tế

**Câu hỏi nguyên văn:**

> Lập nhận xét ngắn về BBS năm 2025 gồm ba phần: tăng trưởng doanh thu thuần so với 2024, tỷ trọng nợ trong tài sản cuối năm và dòng tiền kinh doanh. Nêu số liệu cho từng phần, không dùng một chỉ tiêu để kết luận toàn bộ sức khỏe tài chính.

**Final `answer_vi` nguyên văn:**

> Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.

Thiếu cả ba nhánh: doanh thu 2025/2024 và tăng26,71%; nợ/tài sản59,06%;
CFO dương14.319.681.754VND cùng kết luận có giới hạn. Không có số liệu,
claim hoặc citation được phát hành. Không có tool call hay M6 outcome.

Provider trả JSON success, gồm ba tasks profitability/liquidity/cash-flow nhưng
không có `requirements`/`requirement_ids`. Trace ghi
`supervisor_invalid_task:T1/T2/T3`, `requirement_plan_incomplete`. Model đã làm theo
instruction envelope cũ vẫn còn trong prompt: đây là lỗi tích hợp có bằng chứng,
không đủ căn cứ quy cho giới hạn Qwen. Public status `provider_unavailable` cũng
sai nghĩa vì API không lỗi. Chi phí:3.200tokens,1call,14,89giây.

### C10 — Derived boundary: câu hỏi và câu trả lời thực tế

**Câu hỏi nguyên văn:**

> Tại 31/12/2025, BCC có vốn lưu động ròng (tài sản ngắn hạn trừ nợ ngắn hạn) bao nhiêu và hệ số thanh toán hiện hành mấy lần? Đặt hai kết quả bên cạnh CFO dương năm 2025 và nêu giới hạn khi đánh giá thanh khoản.

**Final `answer_vi` nguyên văn:**

> Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.

Thiếu vốn lưu động ròng-600.656.455.132VND, current ratio khoảng0,56lần,
CFO314.097.335.438VND và giới hạn khi suy về thanh khoản tương lai. Không phát
hành claim/citation; không chạy tools/M6 trong live case này.

Provider trả success nhưng chỉ có một liquidity task theo schema cũ, thiếu
requirement IDs; trace ghi `supervisor_invalid_task:T1` và
`requirement_plan_incomplete`. Cùng lỗi prompt conflict và public status như C01.
Không được lấy live C10 này làm bằng chứng M6 mới vẫn từ chối phép tính đúng:
case chưa đi tới M6. Bằng chứng sửa typed verifier là replay saved C10 riêng.
Chi phí:3.889tokens,1call,11,07giây.

### C07 — Mixed financial/document: câu hỏi và câu trả lời thực tế

**Câu hỏi nguyên văn:**

> Nêu LNST BBS năm 2025 rồi đối chiếu chính sách chi phí đi vay trong thuyết minh: khoản nào ghi chi phí, khoản nào có thể vốn hóa? Không suy ra số lãi vay vốn hóa thực tế từ chính sách.

**Final `answer_vi` nguyên văn:**

> Chưa có đủ claim đã xác minh cho yêu cầu này trong ledger.
> Các yêu cầu chưa đáp ứng: 17. Lợi nhuận sau thuế thu nhập doanh nghiệp (chưa có nội dung đã xác minh), chính sách chi phí đi vay (chưa có nguồn đủ căn cứ), có thể vốn hóa theo chính sách năm 2025 (chưa có nguồn đủ căn cứ), yêu cầu chưa xác định (chưa đủ căn cứ hoặc cần làm rõ).
> Giới hạn: Nguồn đã đối chiếu chỉ bao phủ các phần có bằng chứng được lưu.
>
> Giới hạn nguồn: Nguồn đã đối chiếu chỉ bao phủ các phần có bằng chứng được lưu.

Thiếu LNST7.249.557.946VND; nội dung ghi chi phí khi phát sinh; các điều kiện vốn
hóa theo nguồn, kể cả ngoại lệ vay riêng xây dựng TSCĐ; và giải thích rõ không thể
suy số vốn hóa thực tế từ chính sách. Không bịa số vốn hóa nhưng cũng chưa trả
lời đúng/đủ yêu cầu negative đó. Chi phí:8.787tokens,6calls,194,22giây.

**Quan sát liên nhánh quan trọng:** ledger có **một document claim ACCEPT** với
lý do `exact_source_support`, ID
`verified:51a072f22f60714682823b1c9c84a755a7c31beb8eefb28c68cafb28795fb9b0`.
Child R002 trả `completed_with_caveats`, phát hành đúng ID đó và đoạn chính sách
chi phí đi vay tại PDF trang12, với giới hạn provenance cấp trang. Nhưng final
root `used_verified_claim_ids=[]`: nội dung ACCEPT của child **không tới câu trả
lời tổng cuối**. Kết quả22/22released của E2E-GEN-01 trước đây không áp dụng cho
lượt V2 live này.

| Child | Kết quả live | Cơ chế |
| --- | --- | --- |
| R001 financial | 1call, không tools/claim | Supervisor dùng schema cũ, plan invalid như C01/C10. |
| R002 document | 1call, có nguồn và một ACCEPT; child trả đoạn chính sách có citations trang12 | Retrieval và source-bound verification đã chạy; không thể gọi đây là corpus không có chính sách. |
| R003 financial | 3calls, không final claim | Planner gán “khoản chi phí/khoản có thể vốn hóa” vào financial; câu policy lại vào fusion, lặp decomposition tới budget. |
| R004 unsupported | Không inference riêng | Negative constraint bị để unsupported; final chưa giải thích đúng giới hạn. |

Root fusion planner dùng1call; tổng1+1+1+3=6calls. Ngoài recursion còn có vấn đề
binding ở output được xác nhận từ trace: child R002 giữ target=`chi phi di vay`,
root requirement `R002:R1` lại dùng target=`thuyết minh`, không có verified IDs.
Root plan còn ghi `missing_information=['approved_document_composition_required']`.
Ở `firewall_qa_binding._fusion_inventory`, financial subrequest bị xóa composition
pins rồi gọi lại lexical `request_inventory`; policy span có thể vào document
inventory và kích hoạt guard thiếu composition. `VietnameseQAComposer.compose`
kiểm inventory/status trước retrieval, nên có thể trả sớm dù child ledger đã có
quote đúng. Đây là bằng chứng lỗi tích hợp/coverage của mixed output, không phải
M6 từ chối quote hoặc API lỗi. Source functions này **chưa được thay** trong bản cuối.

### Lỗi đã sửa, chưa được xác nhận và vẫn còn

| Vấn đề | Tình trạng bản cuối | Bằng chứng / điều chưa thể kết luận |
| --- | --- | --- |
| Prompt chứa cả envelope cũ và contract V2 | **Đã sửa mã, kiểm offline** | Supervisor V2 đặt một root instruction requirements/tasks; test kiểm prompt và decode. Chưa có Qwen rerun để chứng minh model sinh đúng IDs. |
| Bound financial child bị phân rã lại vào fusion | **Đã sửa mã, kiểm offline** | integration_lane ghim lane và chặn re-entry; test kiểm không gọi fusion lại. Không chứng minh phân lane do model luôn đúng. |
| Plan/schema error bị gọi provider_unavailable | **Đã sửa mã, kiểm offline** | Không có released claims + local plan error + không provider errors → internal_error; có control. Saved live response vẫn giữ status cũ. |
| C10 typed premise/proof bị grammar loại | **Đã sửa boundary, real-data replay đạt** | Hai proofs và current-assets fact ACCEPT; số sai không ACCEPT. Live chưa đi tới M6; không có xác nhận end-to-end. |
| C04 retrieval miss bị ACCEPT thành corpus absence | **Control offline đã chặn** | Ba saved absence claims không ACCEPT. Chưa chứng minh semantic coverage cho mọi paraphrase/corpus. |
| M6→M7 financial V2 requirement binding | **Đã nối, offline controls đạt** | Supported IDs riêng, mapping sang verified IDs; arithmetic đúng không tự làm named requirement complete. Chưa xác nhận trên live snapshot cuối. |
| C07 child ACCEPT biến mất ở final root | **Vẫn còn điểm lỗi trong code mixed output** | Target/pin/inventory logic cũ vẫn tồn tại ở firewall_qa_binding/qa_composer; lane fix không thay cơ chế final lookup này. Không tuyên bố đã sửa hoặc chỉ cần đổi model. |
| Planner chọn policy vào financial lane, bỏ/sai mục tiêu | **Chưa được giải quyết tổng quát** | Có trong C07 trace. Ghim lane giữ route nhất quán nhưng không làm phân loại sai thành đúng; năng lực model và contract enforcement còn cần đánh giá. |
| Unified document/report coverage, table/numeric probes | **Chưa triển khai đầy đủ** | Vẫn reuse legacy document/fusion composer; chưa phải hoàn tất toàn Target V2 hoặc GO cho QA/report tự do. |

Không thay runtime thêm trong phiên đóng gói review này và không gọi API mới.
Phân loại “đã sửa” ở trên chỉ theo code/tests/replay đã có, không chuyển thành
live PASS. Phần C07 làm rõ một giới hạn nghiêm trọng hơn bản tóm tắt ban đầu.

Evidence: `live/manifest.json`, `provider-events.json`, `execution/C01.json`,
`C10.json`, `C07.json`, `results.json` trong artifacts riêng. Các provider requests,
plan thô và child lane traces được giữ; không sửa lại trạng thái saved execution.
Không có claim phát hành nên không có grounded-claim ratio để báo PASS.

**Sửa sau live, chỉ kiểm offline:** đặt instruction V2 thành contract duy nhất;
ghim lane ở fusion subrequest; phân biệt plan technical error với API failure.
Tests 43/6/3 ở trên kiểm các corrections và boundary liên quan. Không chạy lại ba
case hay thêm Qwen call. Vì vậy **snapshot cuối chưa được xác nhận bằng Qwen thật**;
không dùng lượt live trước correction để tuyên bố bản cuối đạt chất lượng hoặc
quy toàn bộ thất bại cho năng lực Qwen. Manifest giữ runtime hashes của lượt đã
chạy; final runtime hashes và sáu file runtime sửa sau live ghi riêng tại local
`artifacts/evidence/V2-INT-01/final-integrity.json`. Đối chiếu47existing local files
không có thay đổi ngoài phạm vi;607protected non-runtime files vẫn unchanged.

## Phạm vi hoàn thành và giới hạn

Migration primitives và các invariants chính đã chạy offline; chưa có cơ sở GO
cho QA/report tự do. Supervisor vẫn có thể bỏ mục tiêu hoặc chọn sai nguồn; policy,
table/numeric binding và các capability probes không được giả thành đã hỗ trợ.
Document/fusion final output còn dùng adapter/composer cũ; không refactor toàn M7
hoặc Ledger để ép ba case PASS. V2 opt-in, chưa bật mặc định và chưa triển khai M8,
CHAT-02, REPORT-01 hoặc một task FIX khác.

## Đóng gói nhánh review — 13/11/2026

Nhánh `review/v2-int-01` tách từ `3475a3a`; không commit/push vào `main`, không
thay runtime sau bản cuối. Implementation:
[`544d56abb6ff5ab9a64b67e3b22ce2c94533bf48`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/544d56abb6ff5ab9a64b67e3b22ce2c94533bf48).
Qwen transport/text gateway và ba adapter controls vốn có ở local nhưng chưa có
trên main được đưa vào prerequisite riêng
[`3edc7c0`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/3edc7c0),
kèm khai báo httpx runtime từ cấu hình local hiện có. Không đưa cấu hình/API key,
dataset, raw traces, notebooks, hoặc các runtime fixes/planning ngoài task vào nhánh.

Mười hai file runtime thuộc V2 trong checkout review khớp SHA256 với snapshot
cuối trước đóng gói. `specialist_common.py`, `qa_composer.py`, financial discovery/
runtime và các thay đổi local ngoài task không được gom vào commit; vì vậy không
gán toàn bộ working-tree live evidence cho riêng commit mới.

Kiểm lại trên **checkout review độc lập**: 7 targeted controls PASS (3integration,
3Qwen adapter,1schema drift); saved-data C01/C04/C10 replay PASS và22historic
entries unchanged,0model calls. Đã kiểm imports trỏ vào checkout review, không
trỏ nhầm editable install của working tree gốc. Ruff lint/format và diff checks
đạt; planning checker **139 tasks** tại nhánh review. Số143 ở phần lịch sử là
working tree gốc có các task local khác, không đổi trạng thái của chúng khi tách
nhánh. Không chạy thêm Qwen hoặc full CI trong phiên này.

**Next action duy nhất:** Tech Lead review implementation, offline invariants và
giới hạn live snapshot trước quyết định nghiệm thu V2-INT-01.
