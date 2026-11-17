# M5-COORD-02 — Evidence-Guided Coordination

Ngày17/11/2026 (Asia/Bangkok). **REVIEW**, chờ Tech Lead; implementation
[`1874166c3506994926a87f993458543d76a50806`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/1874166c3506994926a87f993458543d76a50806)
đã commit và xác minh178runtime hashes khớp receipt live-release.
Baseline main `a12f0e9`, worktree riêng giữ các
local edits ngoài task. Không thay runtime M6/M7, corpus, OCR hoặc PDF.

## Thay đổi

- Tái dùng V2/IntegrationWorkspace/Financial Tools/EF-EG. Một demand pass cho
  task phụ thuộc hoặc root nhiều nguồn, qua Shared LLM Gateway và budget hiện có.
  Consumer có Gateway chờ demand trước khi retrieve; nguồn cùng kỳ được resolve
  từ output parent có handle/revision/digest, không đoán kỳ thắng từ objective.
- Observation request-local giữ raw/normalized value, label/header/context,
  selectors, citations, source digest và quality. Đây là projection của SourceFact
  đã import, không tạo mapping/canonical fact hoặc ghi ngược corpus. Specialist
  nhận closure cả dependencies bắc cầu; projection prompt gọn, backend giữ đầy đủ.
- Selection trên canonical item và tập kỳ khai báo trong pinned inventory:
  Decimal `max|min|max_abs|min_abs`, đủ domain mới chọn, giữ ties, exclusions và
  nguồn của cả miền so sánh. Blank/null/context thiếu/conflict giữ gap. Đây chưa
  phải rank mọi entity/row của một bảng thuyết minh bất kỳ; total/subtotal và
  source-bound numeric observations từ raw cells chưa mapped còn ngoài khả năng
  thực nghiệm của bản này, không được tự biến thành operands canonical.
- Join identity theo company/document/snapshot/period, có scope khi nguồn resolve;
  lưu hai phía, keys/normalization, cardinality/unmatched/ambiguity và digest.
  Corpus live chưa resolve reporting scope: giữ nguyên None và caveat, chỉ xác
  nhận membership trong cùng snapshot, không gán separate/consolidated hay
  xác nhận nghĩa kế toán. Không fuzzy join đối tác hoặc thêm authority cho EF-EG.
- Một append expansion được validate atomically, giữ goals và cap6 task identities.
  Patch sai được ghi rejected riêng, không xóa retrieval/selection hợp lệ. Lỗi
  task chặn dependents, không xóa nhánh độc lập. Không repair/M6 Feedback/Python.
  Selection goal không được thỏa bằng ACCEPT của riêng scalar đã chọn.

## Live Test có giới hạn

Ba câu mới do task tạo, không đọc benchmark/Gold. JSON thật từ corpus đã import
`VFB-IMPORT-03/full-final`; API Qwen `qwen3-8b-awq-t4` qua Gateway, không retry
transport/provider. Không lưu endpoint/key vào artifacts. Runner
`scripts/run_m5_evidence_coordination_live.py prepare|run --ids ...`.

| Câu | Lượt | Kết quả | Calls / tokens | Ghi nhận |
| --- | --- | --- | --- | --- |
| SEL01 BBS: năm doanh thu cao hơn → CFO cùng năm → % | live-v1 | internal_error | 2 /10352 | Demand root tự tham chiếu và expansion sai role; chặn trước selection |
| SEL02 ADC: CFO lớn hơn có dấu → LNST cùng năm → chênh lệch | live-v1 | internal_error | 2 /8326 | Cùng lỗi demand/expansion |
| SEL02 giữ nguyên câu | live-final | internal_error | 2 /8837 | Bỏ tự tham chiếu nhưng expansion sai làm mất nhánh chính |
| JOIN03 BBS: CFO nhỏ hơn có dấu → doanh thu cùng năm → % | live-new | verification_blocked | 4 /27805 | Selection/retrieval/join có nguồn; prompt lặp closure vượt cap, Calculator chưa chạy; M6 2ACCEPT, M7 giữ gap |
| JOIN03 giữ nguyên câu | live-release | verification_blocked | 7 /59765 | Calculator **3,18%**, M6 **3ACCEPT**, semantic không bind G3, M7 không phát hành |

Tổng **17provider calls /115085known tokens /0unknown usage**, cộng wall344,471s;
cap toàn task18, mỗi câu tối đa một retest, không chạy thêm sau lượt cuối.
Không coi kết quả này là accuracy benchmark. Chỉ lượt `live-release` được gán
cho implementation cuối; các lượt đầu dùng code trước sửa tổng quát.

Nguyên nhân và sửa tổng quát: ví dụ demand root dùng T1 khiến model sao chép
self-reference; bổ sung vocabulary dependency, root null và existing task states.
Tách atomic validation của append patch khỏi retrieval/selection độc lập, giữ
raw response/rejection. Cuối cùng bỏ closure/citations lặp trong specialist prompt,
giữ projection có headers, raw values, context, source pointers và digest. Không
hardcode doanh nghiệp, source handle, câu hỏi hay năm thắng; không sửa M6/M7 để
cứu câu trả lời.

## Bằng chứng consumer dùng output parent — live-release

1. Provider001 giao T1 root CFO hai kỳ, T2 `after:[0]`, T3 `after:[1]`, các
   consumer `input_handles:[]`. Execution order T1→T2→T3; cả ba dùng specialist
   cash_flow_and_earnings_quality. Đây là nhiều task phụ thuộc của cùng role;
   bản cuối chưa có live success mới giữa hai specialist roles khác nhau.
2. T1 retrieve CFO2024 **27996254086** và CFO2025 **14319681754** VND;
   provider002 chọn `min` trên hai kỳ. Backend lưu đủ hai rows, chọn2025,
   `E-6764d600e2efe8005216`, JSON trang8, pointer
   `/blocks/3/table/rows/15/2`, cùng label/header/unit anchors và caveats.
   `result:T1:v1`, digest
   `20e9ad7f737e2845ae2e6732117a6481a84be722c984b84a99089266bf953cad`.
   Expansion sai bị rejected; selection vẫn tồn tại, không tạo task T4/T5.
3. Provider003-request có dependency result đó; response003 yêu cầu S27 với
   `period_from_task:T1`. Backend lấy kỳ **2025** từ selected observation rồi
   mới gọi T2 `get_financial_fact`/`get_evidence_sources`: doanh thu thuần
   **450474531227** VND, `E-e75db5e688409e163762`, JSON trang7,
   `/blocks/3/table/rows/2/4`. Input của demand chưa chứa doanh thu này.
   Join CFO↔revenue matched1:1, cùng company/document/snapshot/period;
   reporting_scope unresolved vẫn giữ caveat. `result:T2:v1`, digest
   `639f4535d3a7b5e509820e3a9487fea6c412c12a770f5b1697fc4e56cd98b7c7`.
4. T3 nhận T2 và closure T1 dù planner chỉ khai direct dependency T2.
   Provider005 chọn S38 (CFO2024) với `period_from_task:T2`; backend resolve
   thành **S37/CFO2025** theo kỳ của output T2, không dùng nhầm cột2024.
   Dữ liệu đã có được reuse, không query fact lại. Join giữ cardinality1:2
   vì T3 dùng hai canonical items, không coi đó là ambiguous duplicate cùng item.
5. Provider006 đề xuất operation `percentage_of(CFO,revenue)` với đúng hai IDs;
   prose model sai **31.77%** bị đường derived_fact thay bằng Calculator replay:
   `3.178799412920444404141150257970875 percent`, render **3,18%**.
   Result T3 digest
   `b76d5d59c47d70014d2df9a43232f193968231d48b250886f261b430ba321179`.
6. M6 replay3candidates và gọi semantic một lần cho calculation
   `candidate:a944c101c65614100922a783`: provider007 SUPPORTED nhưng
   `supported_requirement_ids:[]`, dù proposal có G3. Ba claims vào ledger,
   không có verified goal binding. M7 giữ **verification_blocked/0citations**,
   không nâng arithmetic ACCEPT thành selection/goal coverage. G1 cần selection
   obligations chưa thuộc task; G2 vẫn source_ambiguous từ initial plan.

Full requests/responses, observations/results/selection/joins, tools/graph,
M6 ledger và M7 trace lưu local tại `artifacts/evidence/M5-COORD-02/`.
Không commit raw evidence/dataset. Receipt live-release pin178runtime Python
files và24BBS JSON; toàn bộ runtime/source hashes và ba TaskResult digests đã
đối chiếu. Hợp57source JSON BBS/ADC giữ nguyên qua các lượt.

## Validation và giới hạn còn lại

**24targeted PASS**:3controls demand/selection/expansion mới và21Coordinator/V2
compatibility, gồm pipeline M6/M7 opt-out, branch isolation, forward dependencies,
null/ties/max_abs, rejected patch giữ nhánh chính, consumer chưa prefetch và
transitive input closure. Ruff lint/format, planning checker, diff check local.
Không full unit/browser suite, full CI, Gemini, OCR hay PDF verification.

Git: implementation đã push main, remote `6a7d8da14001e7705a5b04d88a3660509eefdf4d`
được xác minh trước commit bàn giao tài liệu này; không suy CI từ local tests.
Giữ74local files ngoài task nguyên byte, reverse-merge bốn file có sửa chồng
khớp local patch cũ và recount dashboard theo registry local; không đưa local
VFB-E2E-05 hoặc dữ liệu/secrets vào commit.

Final live chứng minh selection→demand retrieval→join→computation và handoff
M6/M7, chưa có câu trả lời phát hành. Chưa có typed M6 replay cho selection/join;
source scope/JSON-only caveats, arbitrary raw-table/entity joins, model tự thêm
expansion sai và goal bindings còn hạn chế. Expansion hợp lệ mới có engineering
control, chưa live positive. Không gán kết quả lượt đầu cho code cuối hoặc tuyên
bố đã giải quyết mọi câu tài chính nhiều bước.

**Next action:** Tech Lead review implementation và trace ở trạng thái REVIEW.
