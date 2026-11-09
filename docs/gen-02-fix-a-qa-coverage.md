# GEN-02-Fix-A — QA Coverage & False Abstention Recovery

Ngày 09/11/2026, Asia/Bangkok. Baseline `6f682c3`;
implementation `22b8c7c5b1c0a6756c0be2595874f8086ce47d30` đã push main,16 files.
[CI42542900770](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42542900770) completed/SUCCESS đúng implementation SHA:1157 Python/9 Web PASS; full regression manual SKIPPED.
Status **REVIEW**; GEN-02 vẫn REVIEW. Không M8, OCR, Gemini live hoặc sửa H08.

## Targeted audit và fixes

| Case | Expected evidence/behavior | Before và earliest failure | General fix |
| --- | --- | --- | --- |
| H03 | BCC2025 separate revenue_yoy, current/comparative revenue trong cùng filing | M5 materialization thiếu prepared metric → internal_error | Chuẩn bị metadata catalog riêng trong bộ nhớ từ approved formula/version/digest và các operands duy nhất; bổ sung graph nodes/edges, giữ dữ liệu gốc. M4 tính Decimal, accounting/scope compatibility và lineage; M6/Ledger/M7 xử lý như metric có sẵn. Thiếu operands và thiếu preparation authority có capability reasons riêng. |
| H06 | BCC2024 PDF17/11, khấu hao phần mềm theo đường thẳng 3–8 năm | M5 đòi cụm “khấu hao phần mềm…” liên tục; source đặt subject trước predicate | Giữ noun phrase chính xác, cho đảo predicate/subject trong cùng câu; không dùng bag-of-words hoặc suy ra quan hệ mới. |
| H07 | BBS2025 PDF11/9, phương pháp khấu hao tài sản hữu hình | M5 chọn heading PDF10 có quality flag; bỏ paragraph PDF11 đã có trong neighbors | Xét paragraph liên quan trong bounded retrieval pool, ưu tiên candidate không có pdf_review flag; không bỏ flag hoặc chuyển INVESTIGATE thành ACCEPT. Câu phương pháp trước bảng giữ quotation và giới hạn excerpt, không bịa số thời gian của bảng. |
| H11 | BBS2025 PDF11/17–20 và PDF12/6, hai requirements độc lập | M5 bỏ bare conjunct “về vay…”; M7 cùng parser cũng bỏ ý và báo completed | Kế thừa document intent qua conjunct “về”, giữ noun conjunction, deduplicate tương đương; IDs xác định theo request. M7/Firewall tự đọc original question, không tin inventory M5. Test cố nâng partial thành answered bị BLOCK. |
| H12 | BCC2024 PDF18/5–11; giữ restriction Gross Margin | M5 coi câu dẫn có dấu hai chấm là heading, tách parent topic khỏi danh sách | Câu dẫn không là heading riêng; giữ parent heading + đủ năm điều kiện liên tục. Financial gate không đổi; document lane độc lập, phát hành useful partial. QA-01b C1 được chạy riêng. |

## Phương pháp và phạm vi

H03/H06/H07/H11/H12 đã công bố trong GEN-02, nay là development regression,
không gọi lại là blind. Before lấy đúng traces/oracles GEN-02 đã lưu; không tạo lại
40 câu hoặc sửa original frozen data. Chỉ hai vòng sửa–kiểm thử chính; một final pass
cho focused regression và6 fresh cases, khóa runtime trước execution. Fresh expected
lấy accepted source selectors và Decimal độc lập runtime, trước output; chưa phải human gold.

Giữ M5 → M4/BM25/EF-EG → M6 → Ledger → M7/Firewall. M6 literal quotation proof vẫn
replay original references, citations, continuity và source-quality. Metadata metric mới
không tự là verified; không đổi formula/accounting/scope approval. Accepted source và
ledger cũ read-only. Các ledger mới nằm riêng dưới artifacts task.

## Validation

Vòng1:25 existing tests PASS; targeted actual pipeline cho4 full +1 useful partial.
Vòng2/final focused tests:122 PASS, gồm6 mới; Ruff/format9 Python files PASS.
Một test mới ban đầu thất bại do test tự render forged presentation trước Firewall;
đã sửa fixture để dùng original rendering, runtime không cần sửa cho lỗi test này.
Planning checker mở rộng grammar cho ID GEN có suffix `-Fix-A`, giữ Task ID Owner giao;
8 existing planning tests PASS. Planning PASS cho workingtree116 và staged115 tasks,
không đưa GEN-01a pending vào implementation. Ruff/format9 Python files PASS.

| Case | Before GEN-02 | Final after | Root cause fixed |
| --- | --- | --- | --- |
| H03 | internal_error | full, verified revenue_yoy | Missing preparation được phân biệt với missing operands; Decimal + lineage + M6 ACCEPT |
| H06 | abstain | full | Exact subject và reordered predicate, đúng PDF17/11 |
| H07 | abstain | full | Đoạn phương pháp đúng PDF11/9; quality gate vẫn giữ |
| H11 | partial nhưng M7 báo completed | full, đủ hai document requirements | Intent inheritance và original-request inventory |
| H12 | abstain | useful partial | Verified document được phát hành, Gross Margin vẫn bị chặn |
| C1 | useful partial QA-01b, regression cùng kiểu H12 trong GEN-02 | useful partial | Khôi phục B09 với đủ năm điều kiện, không mở accounting gate |

Final focused6cases:4full/2partial/0abstain/0incorrect; citations37/37 đúng source
support, unsupported released claims0/10. Document requirements6/6; financial1/3,
hai metric requirements H12/C1 vẫn accounting-basis restricted. C1 là regression
riêng, không cộng vào năm failure cases ban đầu để nâng score.

A7 actual source-quality control: partial, M6 ACCEPT1/INVESTIGATE1, không phát hành
document lỗi;0transport calls.17original accepted claims từ QA-01b ledgers replay
nguyên file/hash. Test Firewall cố đổi partial thành answered bị BLOCK.
Fresh hoàn tất trước khi chốt báo cáo; không tune sau execution. CI đã đối chiếu đúng implementation SHA.

## Six fresh checks

Expected đã lưu trước execution trong `fresh/development-oracles.json`, cùng source
selectors và công thức Decimal độc lập. `fresh/freeze.json` trước mọi actual output;
`fix-lock.json` khóa toàn bộ runtime. Chỉ chạy một lần, không dùng để tune tiếp.

| ID | Nhóm / nguồn | Expected source requirement | Actual audit |
| --- | --- | --- | --- |
| F01 | Metric BCC2025 | Gross Margin từ approved gross profit/net revenue | full |
| F02 | Metric BBS2025 | Debt/assets từ approved liabilities/assets | full |
| F03 | Document BCC2024 | Ngoại tệ, PDF18/17 | full |
| F04 | Document BCC2025 | Doanh thu hoạt động tài chính, PDF13/19 | full |
| F05 | Mixed BCC2025 | Net revenue và chi phí đi vay PDF13/23 | full |
| F06 | Nhiều yêu cầu BBS2025 | Chi phí trả trước PDF11/15 và xây dựng cơ bản dở dang PDF11/13 | full |

6/6full,0partial/abstain/incorrect; citations51/51, unsupported0/8released claims.
M6 ACCEPT8; Ledger stored8. Focused6cases M6 ACCEPT10/INVESTIGATE2,
Ledger stored8/idempotent2/rejected2. Agent/tool invocation theo nhu cầu: financial
planner/supervisor/orchestrator và profitability/liquidity specialists; document
search/excerpt/verification chạy độc lập, không gọi model. Traces và per-requirement
coverage nằm trong từng `actual/<ID>.json` và `independent-audit.json` của hai nhóm.

Median/P95 E2E: focused28,21s/60,70s; fresh29,90s/65,86s. Không phải cold-start hoặc
performance benchmark; không suy ra tốc độ cải thiện từ các tập nhỏ khác nhau.
Actual E2E có0Gateway/provider calls, không Gemini live/OCR. `summary.json` xác nhận38approved input files,
4original frozen files và runtime sau lock nguyên hash; inherited source/Web nguyên.

Artifacts local `artifacts/evidence/GEN-02-Fix-A/`: `baseline.json`, `round-1/`,
`fix-lock.json`, `final-inputs/actual/`, `fresh/actual/`, `final-tests.log`,
`source-quality-control/`, `legacy-compatibility.json`. Mỗi actual JSON chứa answer,
fulfilled/unfulfilled requirements, agent/tool traces, evidence, M6/admission/M7/Firewall
và citations. Independent audit đối chiếu accepted records/facts, exact quotation,
Decimal và expected requirements, không lấy pipeline status làm kết luận.
`fix-register.json` ghi RCA từng case; `summary.json` chứa numerator/denominator,
M6/admission/agent/tool counts và integrity checks. Không tái tính lại GEN-02 score.

## Limitations và điểm dừng

H08/Fix-B, OCR quality, PERF-01, WEB-02 và M8 ngoài phạm vi. Provenance tài chính
vẫn có page-level/uncertain caveats; không tuyên bố cell-level accuracy hoặc financial
quality toàn hệ thống từ engineering tests. Focused/fresh E2E dùng workingtree giữ nguyên
GEN-01a pending; CI được đối chiếu riêng với implementation SHA không chứa pending đó.
Các P1 đã giao Fix-A đều đạt expected targeted behavior; H08 vẫn là P1 ngoài phạm vi
Fix-B, không tuyên bố đã xử lý. P2 còn bounded exact-phrase matching, tối đa12selectors
cùng trang và chi phí graph/replay/startup. Đề xuất Tech Lead giữ scope Fix-B riêng;
chỉ đánh giá performance hoặc M8 khi có task mới, không mở quality/accounting gates.

Next action: dừng REVIEW, chờ Tech Lead nghiệm thu.
