# EF-CORE-03 — Targeted Quality & Graph Efficiency Improvements

Ngày11/11/2026, Asia/Bangkok. IN_PROGRESS, chưa commit.

## 1. Executive Summary

Đã sửa P1 candidate isolation, P2 source projection và P3 graph context coverage.
Setup graph giảm27,06%, traversal giảm16,12% trên ba runs BBS trước/sau.
C1 live đủ biến động hai chỉ tiêu; M6 probe bác caveat sai/unsupported implication.
D1 phân biệt bốn định nghĩa nhưng endpoint explanation còn PARTIAL; C3/CORE-Q5
chưa đầy đủ. Không tuyên bố graph tăng financial accuracy.

## 2. Scope and Baseline

Main48b9d78 gồm implementation EF-CORE-02 43c55aa. EF-CORE-02 chuyển DONE theo
nghiệm thu Tech Lead được Owner xác nhận trong task này; giữ limitations.
Evaluation dùng Git baseline + bốn file task, loại local with_assignment edits.
Dùng BBS2025/approved composition/oracle EF-CORE-02 đã đối chiếu scan PDF5/6/7,
bốn chỉ tiêu/hai kỳ/VND/page bindings. Không lấy M6/ON answer làm truth.
Không OCR/extraction, raw/canonical writes, period-policy redesign, Agent/edge/
database mới, M7 verifier, M8 hoặc model khác. Giữ local edits ngoài task.

## 3. Root Causes P1–P4

| Vấn đề | Root cause | Thay đổi | Offline | Live | Kết luận |
| --- | --- | --- | --- | --- | --- |
| P1 | generate_candidates: derived_fact/operations=[] tới render_dynamic(None), AttributeError vượt catch từng analysis | Guard theo semantics/trace exclusion | Baseline0candidates; patch giữ numeric/valid analysis | Không tái hiện batch AttributeError | Fixed trong hồi quy |
| P2 | Specialist/semantic_payload thiếu page/provenance đã pin | Citation binding projection trong batch hiện có | Page/page-level/missing/semantic wiring | Probe5cases; D1-A caveat sai, B hết dù OFF | Metadata có ích độc lập graph |
| P3 | Objective rút gọn; context đầu và metadata trùng chiếm budget | Giữ user question/đủ chỉ tiêu-kỳ; balance toàn bundle/compact endpoints | Final BBS đủ4types/roles | C1 đủ biến động; D1 có4định nghĩa | Endpoint grounding còn hạn chế |
| P4 | Recursive catalog deepcopy qua tool con; resolve lại node | Một detached owner/facade/node cache | Ba runs/phiên bản, responses exact | Timings từng run ở phụ lục | Overhead vẫn lớn |

Source và EF-CORE-02 traces xác nhận các nguyên nhân trên. M5 đã setup một lần/
request, không thêm persistent cache. cProfile chẩn đoán76,7triệu calls/39,5s,
deepcopy tích lũy25,1s; instrumentation không là denominator của benchmark.

## 4. Implementation Changes

specialist_common thêm source helper/derived guard. lite_orchestrator giữ câu hỏi,
nhắc đủ chỉ tiêu/kỳ và source/relation semantics, round-robin types toàn bundle.
Prompt endpoint dùng immutable node ID; full typed reference còn trong raw trace.
Caveats dedup theo row, không bỏ flags. lite_runtime thêm source bindings vào một
semantic batch hiện hữu; không thêm call/verifier. graph_retrieval dùng detached
catalog owner cho tools con/cache resolve; selection guards trước lookup, response
detached. Graph validation, Calculator, M7, depth/neighbor bounds giữ nguyên.
Scalar lookup vẫn có thể use_graph=false.

## 5. Candidate Isolation Fix

Baseline reproduction: AttributeError “NoneType object has no attribute operands”,
candidates=0. Regression dùng cấu trúc quan sát được: valid numeric claims, một
derived_fact rỗng, một derived_fact/subtract hợp lệ. Patch trace
derived_fact_requires_computation và giữ numeric/arithmetic độc lập.
Không chuyển claim sai thành reasoned claim, tự tạo phép tính hoặc ACCEPT.

## 6. Source Metadata and Semantic Grounding

Projection gồm document/snapshot/page/provenance, citation linked/missing, selector
availability/caveats. linked chỉ là citation binding, không chứng nhận mọi nội dung
trang đúng hoặc file luôn mở được. Selector không nâng page-level thành cell-level.
M6 nhận bindings sau canonical/provenance checks.

| Fresh Gemini probe trên BBS claims/arithmetic đúng | M6 |
| --- | --- |
| Nói thiếu trang dù có binding | ABSTAIN |
| Có trang nhưng page-level/uncertain | ACCEPT |
| Biến động do chi phí nguyên liệu | ABSTAIN |
| “Chênh lệch lợi nhuận từ nguyên liệu” mơ hồ | INVESTIGATE |
| Thật sự bỏ citations | INVESTIGATE |

Claims chủ động tạo cho hồi quy với fresh verification; không gọi replay là fresh
end-to-end. Offline mocks chỉ kiểm wiring/decision contracts. Một semantic batch.
Prompt không bảo đảm model luôn đúng.

## 7. Graph Context Coverage Improvements

Final deterministic BBS projection đủ from_source/associated_with/used_in/
same_extraction_context; trước chỉ used_in/same_extraction_context. Raw responses
giữ roles/quality/grounding/citations/caveats. M5 vẫn sáu starts/depth2/tám neighbors.
C1 live tạo subtract/percentage_change đúng inputs [mục tiêu,gốc], M6 ACCEPT,
M7 dùng kết quả sẵn có; không hardcode BBS/G3 trong production prompt.
D1 live có bốn định nghĩa/causal limits, chưa luôn gắn từng cạnh với endpoints.
Live trước compact-only cuối có projection3/4types; không gán coverage offline
cuối cho provider calls đó. Trace giữ đúng từng projection.

## 8. Graph Performance Before/After

Cùng BBS/composition/sáu starts/depth2/limit8; ba lần/phiên bản, không LLM/cProfile.

| Mean | Baseline | Patch |
| --- | ---: | ---: |
| Setup(s) | 10,538 | 7,686 |
| Sáu traversals tổng(s) | 3,578 | 3,001 |
| Calls | 6 | 6 |
| Unique nodes/edges | 39/54 | 39/54 |
| Projected types | 2 | 4 |
| Projection ký tự | 12.545 | 13.160 |

18/18 response pairs có cùng JSON SHA256, gồm status/depth/roles/evidence/citations/
caveats. Projection dài thêm4,90% để đủ types; không giảm completeness đổi tốc độ.
Snapshot/composition mismatch và mutation controls PASS. Setup giảm27,06%,
traversal giảm16,12%; không suy thành end-to-end Gemini speedup.
M5/total/input/output/calls live ở phụ lục; không fresh paired baseline live nên
chưa chứng minh giảm total latency/tokens. EF-CORE-02 mean15,91/5,23s dùng requests
khác, không làm denominator ở đây. Metadata mới có token cost; validation/
construction còn đắt, không refactor lớn.
Measure-only ban đầu lỗi xuất pstats sau khi persist đủ results; đã sửa export,
không bỏ timing hợp lệ hoặc lặp benchmark chỉ để lấy kết quả thuận lợi.

## 9. Real Gemini Validation

15 fresh end-to-end executions gồm technical failures/bounded retries/diagnostic;
một fresh semantic batch. Max32calls/300s/request, QA Gateway/key rotation hiện có.
Mọi câu hỏi/plan/Specialists/tools/relations/claims/M6 decisions, M7 nguyên văn/
citations, correctness/completeness và tokens/latency ở [phụ lục](ef-core-03-live-validation.md).

| Case | Kết quả |
| --- | --- |
| C1/G3 retry | Đủ10/10 oracle units: doanh thu tăng94.967.158.941VND/26,71%; lợi nhuận gộp giảm3.949.890.713VND/10,84%; hai kỳ/PDF7. Runtime partial_verified_coverage không đồng nghĩa thiếu nội dung. |
| D1/G5 | Bốn định nghĩa/causal limits; endpoint explanation còn PARTIAL. |
| B2 | Đúng32.482.519.668/450.474.531.227×100=7,21%; PDF7; caveat page-level đúng. |
| C3 | Có hướng giảm/cơ cấu nợ, thiếu absolute/% phát hành; context chọn đầu năm, issue cũ. PARTIAL. |
| CORE Q5 exact | Có bốn số dư/59,06%, thiếu −8,66%/−14,35%; PARTIAL. Pilot wording khác lưu riêng. |

Replay cùng Q5/C3 candidates qua baseline/patch, không LLM: calculations/decisions/
outputs giống nhau. Đây là deterministic non-regression, không chứng minh prompt/
model variance không thể giảm completeness. Q5 fresh chưa đạt chất lượng từng thấy
ở CORE-FLOW-01, không báo live regression PASS. Targeted Calculator/renderer tests
vẫn bảo toàn denominator/kỳ/steps.

Mini diagnostic B2/D1 chung fresh plan/câu, ledger riêng:
A=patched OFF bỏ source projection tại evaluator; B=OFF+metadata; C=ON+metadata.
A không là toàn runtime cũ, vẫn có P1/P3 prompt fixes. D1-A tái hiện caveat thiếu
trang dù citation PDF6; B/C hết caveat. B2 không tái hiện contradiction ở cả ba arms,
không suy rate. B/C đều có definitions tổng quát; C chưa chứng minh added lineage/
accuracy hơn B. Không lấy định nghĩa trong prompt làm chứng cứ đóng góp graph.

## 10. Remaining Limitations

C3 period policy ngoài scope. Q5 tổng quát chưa luôn tạo percentage operations dù
facts đủ. D1 chưa luôn nêu endpoints. M6 vẫn là semantic LLM/scalar sources, không
per-clause entailment engine cho graph/toàn PDF. Page-level/uncertain/scope caveats
giữ nguyên. HTTP503 gây fallback/retries, tính mọi chi phí.
Không blind benchmark hoặc accuracy toàn PDF.

## 11. Research Implications

Metadata tự sửa source-availability contradiction trong diagnostic; chưa quy được
lợi ích cho graph. Graph cung cấp structural/contextual paths nhưng chưa chứng
minh relations tăng financial accuracy. Performance là engineering result với
responses tương đương. M8/model khác chưa bắt đầu.

## 12. CI and Implementation Evidence

Chưa commit, chưa CI implementation. Final task-only staged tree:71 targeted PASS;
Ruff check và planning130tasks PASS. Workspace planning131tasks gồm GEN-01a local;
không đưa task local đó vào commit. Formatter-only newline normalization không đổi
logic đã test; không dùng CI EF-CORE-02 làm CI task này.
Artifacts ignored trong artifacts/evidence/EF-CORE-03: Owner task, reproduction/
profile/timings, fresh runs/ledgers/provider events, probe, period replay/hashes,
task-only staging. Local edits ngoài task giữ lại.

Next action: hoàn tất checks và commit/push/CI để bàn giao Tech Lead REVIEW.
