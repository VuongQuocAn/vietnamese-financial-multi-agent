# E2E-VAL-01 — ViFinBench Pilot: dừng sau gate9/45

Ngày17/11/2026 (Asia/Bangkok). **REVIEW — chưa sẵn sàng Full600**.
Implementation runner/evaluator
[`2d96f1574551e4a38b80b668066be9940497da46`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/2d96f1574551e4a38b80b668066be9940497da46).
Runtime cuối giữ baseline remote main `d72f7c032b69abe94a53b71106e2fb448bbc2160`;
candidate sửa prompt bị loại sau retest. Không sửa corpus/Gold, thêm Agent hoặc
thay kiến trúc. Worktree riêng giữ checkout gốc/local edits.

## Phương pháp và quyết định

Chỉ mở ba `pilot.jsonl` (mỗi nhóm15QA) và metadata định danh tài liệu. Chọn
**câu đầu tiên của mỗi difficulty easy/medium/hard trong từng nhóm** trước khi
đọc Gold: SH/MH/NR0001,0006,0013. Đây là mẫu cố định9câu, không ngẫu nhiên và
không đại diện thống kê cho45/600. Không mở Full600, OCR, Gemini hoặc PDF.
JSON/EF-EG tái dùng từ VFB-IMPORT-03/full-final, không import lại.

Prepare chỉ xuất id/group/difficulty/question/document_alias. Process answering
đọc manifest riêng và kiểm hashes, không parse Gold hoặc truyền Gold vào Gateway.
Sau answering, evaluator riêng mở Pilot Gold và saved outputs; verdict do agent
đánh giá thủ công, không dùng LLM judge, chưa có reviewer thứ hai. Không có
Gold-specific handles/formula, gán scope hoặc nới gate để cứu câu trả lời.

Cap baseline90calls/10mỗi câu, timeout300s/câu,60s/provider call, retries0;
runtime có một repair khi đủ điều kiện. Thực tế22calls, không đụng cap.
Chỉ retest SH0006/0013 với candidate prompt, cap20calls/10mỗi câu; dùng5calls,
không chạy lại câu khác. Dừng vì toàn bộ MH/NU abstain và các lỗi nguồn/planning
còn nghiêm trọng. **36QA còn lại chưa chạy; Full600 chưa chạy.**

## Kết quả baseline trên9QA

Accuracy = correct/N; answer coverage = (correct+partial+incorrect)/N, chỉ tính
nội dung trả lời thực sự phát hành. Partial không nhận điểm accuracy. Abstain
bao gồm clarification/verification_blocked/internal_error không có đáp án.
Không lấy số ACCEPT hoặc coverage do planner tự đặt thay cho Gold completeness.

| Nhóm | N | Correct | Incorrect | Partial | Abstain | Accuracy | Answer coverage | Calls | Wall s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SH | 3 | 1 | 0 | 0 | 2 | 33,33% | 33,33% | 14 | 371,011 |
| MH | 3 | 0 | 0 | 0 | 3 | 0% | 0% | 2 | 76,456 |
| NU | 3 | 0 | 0 | 0 | 3 | 0% | 0% | 6 | 105,160 |
| Tổng | 9 | 1 | 0 | 0 | 8 | **11,11%** | **11,11%** | **22** | **552,627** |

Wall gồm load/validate JSON/graph, tổng pipeline491,634s, median wall57,485s/câu.
131299known tokens,0unknown usage. Selective accuracy1/1chỉ có một câu trả lời,
không có ý nghĩa chứng minh chất lượng chung. Chi phí tiền tệ chưa có price source.

| QA | Verdict/status | Citations | Calls | Wall s | Nguyên nhân chính |
| --- | --- | ---: | ---: | ---: | --- |
| SH0001 | correct / completed_with_caveats | 6 | 4 | 71,581 | Đúng Gold, kỳ/unit và verified binding |
| SH0006 | abstain / verification_blocked | 0 | 7 | 241,945 | Lookup khoảng thời gian bị đổi thành tính từ số dư hai kỳ; thiếu retrieval thuyết minh |
| SH0013 | abstain / verification_blocked | 0 | 3 | 57,485 | Thêm số hạn mức/thời gian còn lại ngoài câu hỏi; nguồn điều khoản không tới specialist |
| MH0001 | abstain / clarification_required | 0 | 0 | 5,414 | Mixed/document lane thiếu approved composition/repository |
| MH0006 | abstain / clarification_required | 0 | 0 | 3,951 | requested_scope_unconfirmed trước M5 |
| MH0013 | abstain / internal_error | 0 | 2 | 67,091 | Demand retrieve12 vượt schema max6; dependent branches blocked |
| NR0001 | abstain / verification_blocked | 0 | 3 | 42,925 | net_revenue không có source usable; dependency output unavailable |
| NR0006 | abstain / verification_blocked | 0 | 3 | 58,658 | Sai target/operand, json_fact_unbound_or_ineligible |
| NR0013 | abstain / clarification_required | 0 | 0 | 3,577 | requested_scope_unconfirmed trước M5 |

Per-QA **Gold nguyên cấu trúc, câu hỏi, output đầy đủ, verdict/lý do, pointers,
latency/calls/tokens, coverage và link agent/tool trace/Ledger** ở local:
`artifacts/evidence/E2E-VAL-01/baseline-nine/qa-report.md` và `evaluation.json`.
Gold/dataset và raw traces không commit. Bảng trên là bản tổng hợp để review code.

## Trace và RCA

- **SH0001:** planner→liquidity_and_leverage→get_financial_fact/get_evidence_sources
  →M6 semantic2ACCEPT/G1→Ledger v2 hai entries→M7 natural.6references resolve đúng
  JSON pointers/source hashes, bindings nằm trong released claims.5anchors trang5
  cho số/nhãn/header và1anchor trang1 cho unit; không coi6references là6nguồn độc lập.
  Không phát hiện sai số/kỳ trong câu trả lời duy nhất; chỉ JSON-only, chưa PDF-verified.
- **SH0006/0013 — planning drift lặp lại:** ví dụ mặc định ba goals có hai operands
  và calculation bị model áp vào lookup. SH0006 đổi khoảng thời gian thành giá trị
  còn lại2025/2024 và tính khấu hao; SH0013 thêm tính thời gian còn lại. Nội dung
  cần có trong JSON BED2025 trang15 và BBS2025 trang19, nhưng inventory/demand
  chủ yếu source handles của canonical numeric items, chưa có đường lấy named
  note/table cells cho những goals này. SH0006 có3ACCEPT scalar nhưng binding rỗng;
  M7 chặn, không lấy arithmetic/truth thay goal coverage. SH0013 dừng trước M6.
- **MH0001 — integration/configuration gap:** document_intent phân loại mixed,
  `run_fusion` đòi approved composition/document_repository. Loader hiện chỉ cấp
  SnapshotCatalog; runner theo E2E-ARCH-02 không có composition được duyệt. Vì vậy
  chưa đến M5, chưa kiểm selection/join. Đây là giới hạn đường tích hợp đang đánh
  giá; không khẳng định pipeline note lane có đủ cấu hình đã thất bại reasoning.
- **MH0006/NR0013 — dữ liệu/ngữ cảnh:** câu hỏi yêu cầu báo cáo riêng, catalog chưa
  xác nhận scope tương ứng; `_context` trả requested_scope_unconfirmed. Không dùng
  metadata/Gold để tự nâng scope. Cần xem xét khả năng bind scope từ nguồn hiện có
  theo contract, không bỏ gate hoặc suy loại BCTC từ việc thiếu chữ “hợp nhất”.
- **MH0013 — handles/schema và capability:** planner cấp12handles cho task chọn
  ngân hàng, demand lặp cả12vượt retrieve max6, làm T1 technical_error và chặn
  ba task phụ thuộc. Không cắt6đầu hoặc tăng cap vì không chứng minh đủ miền. Kể cả
  schema hợp lệ, inventory item/kỳ không có miền named banks và exact entity join
  sang subsidiary/ownership được hỏi. Đây chưa phải lỗi M6: chưa có candidate.
- **NR0001/0006 — eligibility/operand:** ADC net_revenue source_unknown dù số có
  trong raw JSON; ALT chọn biên lợi nhuận như input và sales_revenue, rồi bị
  json_fact_unbound_or_ineligible. Phải phân biệt mapping/quality với raw absence.
  G3 bị blocked do dependency output unavailable. Python power không cần thiết
  còn được đề xuất cho percentage_change; không có Calculator/Python/M6 execution
  thành công ở ba câu NU để đánh giá arithmetic. Không suy quality toán học từ abstain.

Baseline có21get_financial_fact,21get_evidence_sources,6get_graph_context;
model stages6planner/3demand/10specialist/2M6/1M7. Graph calls là truy xuất cấu trúc,
không chứng minh nghĩa kế toán. Docker worker preflight ready nhưng0Python execution
trong mẫu này. Chỉ SH0001 đi đủ M5→M6→Ledger→M7; không gán thành công full chain
cho những câu dừng sớm. Chưa có bằng chứng lợi ích Multi-Agent/ablation trong task.

## Sửa thử và retest riêng

Candidate chỉ thêm luật giữ nguyên lookup/goal và ví dụ một goal vào Supervisor;
giữ ví dụ dependent calculation, không sửa M6/M7 hoặc data. Runtime candidate
khác baseline đúng một file; patch/source copy và receipt được giữ local.

| QA | Trước | Sau candidate | Calls trước→sau | Wall s trước→sau |
| --- | --- | --- | --- | --- |
| SH0006 | abstain / verification_blocked | abstain / internal_error | 7→3 | 241,945→63,903 |
| SH0013 | abstain / verification_blocked | abstain / verification_blocked | 3→2 | 57,485→41,144 |

SH0013 còn một goal đúng nghĩa nhưng vẫn thiếu source. SH0006 vẫn thêm kỳ2024/
trung bình, tạo4goals và bỏ owner G1; integration_plan_incomplete và
goal_owner_unresolved:G1. **Candidate không cải thiện accuracy/coverage và có
regression trạng thái nên đã restore toàn bộ runtime**, không giữ sửa thiếu bằng chứng.
Không chạy retest thứ hai. Giảm latency do đường lỗi khác không phải speedup.

After riêng2QA:0correct/2abstain,5calls/14125tokens/105,047s. Không trộn vào
baseline9 hoặc gọi đó là kết quả final45. Tổng task **27actual calls/145424known
tokens/0unknown**,657,674s cộng wall11lượt. Không retry transport hoặc gọi judge.

Evidence sau ở `artifacts/evidence/E2E-VAL-01/after-planning-fix/`; baseline giữ
nguyên. Hai `qa-report.md`/`evaluation.json`, receipts, requests/responses, outcomes,
workspace/selection/joins, tool traces và Ledger được hash trong `integrity-audit.json`.

## Validation, giới hạn và bàn giao

3controls mới PASS trên final runner/evaluator: sampling Pilot/Gold isolation,
manifest tamper chặn trước Gateway và exact escaped JSON pointers. Offline
evaluation/audit hai lượt PASS,6citations resolve/hash/bindings hợp lệ.
Hai coordinator controls PASS. Test cũ
`test_pipeline_flag_keeps_existing_m6_m7_and_opt_out` FAIL trên candidate và
**FAIL y hệt trên baseline d72f7c0** (deterministic không có released binding);
không sửa test hoặc coi đây là regression của code cuối. Ruff/planning/diff PASS.
Không fullsuite/browser/fullCI; commits dùng skip ci theo phạm vi đã giao.

Audit xác minh185runtime blobs khớp Git baseline và runtime restored; candidate
184files giữ nguyên, một file khớp source copy đã pin.264JSON source hashes và
3Pilot hashes trước/sau khớp;80local files của checkout gốc nguyên byte.
Import manifests/graph được loader validate khi chạy; audit pre/post ở đây ghim
raw JSON/runtime/Pilot, không tuyên bố có prehash riêng toàn bộ imported bundle.
Runner blob trong implementation khớp receipt; evaluator/tests pin bằng commit.

Ưu tiên remediation đề xuất cho review: bind scope/composition có căn cứ từ JSON
đã import; nguồn thuyết minh/named-row có handles/domain đầy đủ; planning giữ nghĩa
question và owner, demand tuân cap, operands eligible rồi mới giải quyết coverage.
Không giải quyết bằng thêm agent, hardcode Gold, nâng cap hay nới M6 admission.
Pilot mới có9/45QA và không PDF-verified; chưa đủ readiness Full600.

**Next action:** Tech Lead review gate9/45, RCA và thứ tự remediation trước khi
cho phép chạy tiếp36Pilot; không tự chạy Full600.
