# E2E-02 — Issue Log

Checkpoint E2E-02 ngày09/11/2026: **REVIEW; discovery only.** 9 issues: 1 Critical / 3 High / 4 Medium / 1 Low. Tại discovery, root_cause=`NOT_ANALYZED`, status=`OPEN_FOR_FIX_02`; không sửa lỗi. Phân tích tiếp theo trong FIX-02 ghi ở cuối tài liệu, không sửa artifacts đóng băng. [Báo cáo](e2e-02-real-pdf-evaluation.md). Dữ liệu có cấu trúc: artifacts/evidence/E2E-02/issues.json.

## Tái hiện chung

Dùng runtime `39d796a` và accepted inputs cùng hashes trong `freeze.json`.
Khởi tạo ledger ở thư mục mới, giữ ledger nguồn read-only. Từ Python với `scripts`
trên `sys.path`, gọi `evaluate_real_pdf.runtime(base, freeze["runtime_head"])`, rồi
`build(Path.cwd(), new_output)`. Với câu financial/document, gọi
`pipeline.run(FinancialQARequest(question=..., execution_mode="deterministic", allow_gateway=False, force_refresh=True))`.
Với hội thoại, tạo `ConversationService(pipeline)` và session mới, gửi đúng thứ tự.
Các ca reuse cần giữ prefix được ghi trong từng issue. Đây là hướng dẫn tái hiện;
E2E-02 không chạy lại issues để chọn kết quả.

## Danh mục

| ID | Severity | Questions | Triệu chứng |
| --- | --- | --- | --- |
| E2E02-I001 | Critical | Q08 | Trích dẫn dự phòng mất từ “khó”, đảo nghĩa điều kiện thanh toán |
| E2E02-I002 | High | Q05 | Không trả lời được ba người ký có trên PDF |
| E2E02-I003 | Medium | Q10 | BBS 2024 có PDF nhưng financial catalog thiếu số liệu |
| E2E02-I004 | High | Q15,Q20,Q23,Q24 | So sánh trong cùng báo cáo bị chặn như cross-document |
| E2E02-I005 | Medium | Q06,Q26 | Đoạn định nghĩa quản lý chủ chốt chưa đủ reference |
| E2E02-I006 | Medium | Q21 | Phân tích chất lượng lợi nhuận còn thiên về liệt kê facts |
| E2E02-I007 | High | Q03,Q11,Q12,Q13,Q14,Q16,Q21,Q22,Q38 | Độ trễ financial/mixed QA lớn dù không gọi provider |
| E2E02-I008 | Low | Q01,Q13,Q22 | Output dài với reason codes và nguồn lặp cấp trang |
| E2E02-I009 | Medium | Q34 | Follow-up hỏi trang của đoạn vừa trả lời bị chặn |

## E2E02-I001 — Trích dẫn dự phòng mất từ “khó”, đảo nghĩa điều kiện thanh toán

- Severity: **Critical**; Questions: Q08.

- PDF/Document: BCC_2024 / PDF 16.

- Expected: PDF 16: “người nợ khó có khả năng thanh toán” phải được giữ nguyên; không phát hành nội dung đảo nghĩa.

- Actual: Output verified: “người nợ có khả năng thanh toán”; completed_with_caveats,2 citations PDF 16, một citation selector7 không hỗ trợ quotation thực tế.

- Symptom: Nguồn đúng trang nhưng lời trích sai ngữ nghĩa tài chính.

- Evidence: `turns/Q08.json` + `traces.json#Q08` + pdf-review/BCC_2024-p16.jpg. Mọi đường dẫn artifact tương đối với `artifacts/evidence/E2E-02/`; reference đóng băng trước QA.

- Latency: Q08=14.673s.

- Reproduction: Snapshot runtime39d796a; loader accepted hiện hữu; ledger rỗng; chạy nguyên Q08 deterministic, force_refresh=True. Đối chiếu PDF 16, /text_elements/7 và used_verified_claim_ids.

- Preliminary category: `Source`. Chỉ phân nhóm triệu chứng, không phải root cause.

- Root cause: `NOT_ANALYZED`; Status: `OPEN_FOR_FIX_02`.

- Evidence bổ sung: `{"pointer": "/text_elements/7", "observed_claim_ids": ["verified:76075b7069398614920331ca027990481680c0cc201d77340be2c46bc12f8ea7"]}`.

## E2E02-I002 — Không trả lời được ba người ký có trên PDF

- Severity: **High**; Questions: Q05.

- PDF/Document: BBS_2025 / PDF 7.

- Expected: Tên và vai trò Phạm Thị Thanh Hòa/người lập, Dương Minh Tuấn/kế toán trưởng, Trần Ngọc Hưng/giám đốc, PDF 7.

- Actual: verification_blocked; ba requirements thiếu claim, không citation.

- Symptom: Basic document QA coverage gap; không phải negative control.

- Evidence: `turns/Q05.json` + `traces.json#Q05` + pdf-review/BBS_2025-p7.jpg. Mọi đường dẫn artifact tương đối với `artifacts/evidence/E2E-02/`; reference đóng băng trước QA.

- Latency: Q05=13.253s.

- Reproduction: Ledger mới; chạy Q05; inspect document_candidates, tool_calls và PDF 7; không dùng mock/không sửa nguồn.

- Preliminary category: `Retrieval`. Chỉ phân nhóm triệu chứng, không phải root cause.

- Root cause: `NOT_ANALYZED`; Status: `OPEN_FOR_FIX_02`.

## E2E02-I003 — BBS 2024 có PDF nhưng financial catalog thiếu số liệu

- Severity: **Medium**; Questions: Q10.

- PDF/Document: BBS_2024 / PDF 9.

- Expected: PDF 9 có doanh thu355507372286VND; trả dữ liệu có nguồn nếu khả dụng hoặc giới hạn nguồn cụ thể.

- Actual: verification_blocked/no_usable_context_evidence; financial catalog BBS 2024 trống.

- Symptom: Source coverage hiện có không đáp ứng truy vấn doanh thu cơ bản.

- Evidence: `turns/Q10.json` + `traces.json#Q10` + pdf-review/BBS_2024-p9.jpg. Mọi đường dẫn artifact tương đối với `artifacts/evidence/E2E-02/`; reference đóng băng trước QA.

- Latency: Q10=0.013s.

- Reproduction: Build cùng4catalog; ledger mới; Q10. Không lấy cột2024 của BBS 2025 gán ngầm thành source BBS 2024.

- Preliminary category: `Source`. Chỉ phân nhóm triệu chứng, không phải root cause.

- Root cause: `NOT_ANALYZED`; Status: `OPEN_FOR_FIX_02`.

## E2E02-I004 — So sánh trong cùng báo cáo bị chặn như cross-document

- Severity: **High**; Questions: Q15,Q20,Q23,Q24.

- PDF/Document: BCC_2025 / PDF 7; BBS_2025 / PDF 7; BBS_2025 / PDF5,6.

- Expected: Đọc các cột so sánh cùng báo cáo; yoy chỉ dùng approved revenue_yoy; mô tả hướng thay đổi không cần phát minh công thức.

- Actual: unsupported/cross_document_comparison_blocked_D03_B10;0 agents / 0 tools trong cả bốn ca.

- Symptom: Câu hợp lệ về cùng PDF/kỳ so sánh bị từ chối trước execution.

- Evidence: `turns/Q15.json` + `traces.json#Q15` + pdf-review/BCC_2025-p7.jpg; `turns/Q20.json` + `traces.json#Q20` + pdf-review/BBS_2025-p7.jpg; `turns/Q23.json` + `traces.json#Q23` + pdf-review/BBS_2025-p7.jpg; `turns/Q24.json` + `traces.json#Q24` + pdf-review/BBS_2025-p5.jpg,pdf-review/BBS_2025-p6.jpg. Mọi đường dẫn artifact tương đối với `artifacts/evidence/E2E-02/`; reference đóng băng trước QA.

- Latency: Q15=0.007s; Q20=0.003s; Q23=0.019s; Q24=0.008s.

- Reproduction: Ledger mới; chạy nguyên từng question, nhất là Q15 nói rõ cùng báo cáo riêng. Đối chiếu errors và PDF 7 hoặc B01PDF 5/6; không đổi câu để lấy kết quả đẹp.

- Preliminary category: `Planner`. Chỉ phân nhóm triệu chứng, không phải root cause.

- Root cause: `NOT_ANALYZED`; Status: `OPEN_FOR_FIX_02`.

## E2E02-I005 — Đoạn định nghĩa quản lý chủ chốt chưa đủ reference

- Severity: **Medium**; Questions: Q06,Q26.

- PDF/Document: BBS_2025 / PDF 14; BBS_2025 / PDF 7,14.

- Expected: Ngoài vai trò/người thân, frozen reference có luận điểm doanh nghiệp liên quan qua biểu quyết/nhân sự chung ở PDF 14.

- Actual: Chỉ trích định nghĩa nhân sự/người thân; phần liên kết doanh nghiệp chưa được nêu.

- Symptom: PARTIAL theo reference đóng băng, không phải số liệu sai.

- Evidence: `turns/Q06.json` + `traces.json#Q06` + pdf-review/BBS_2025-p14.jpg; `turns/Q26.json` + `traces.json#Q26` + pdf-review/BBS_2025-p7.jpg,pdf-review/BBS_2025-p14.jpg. Mọi đường dẫn artifact tương đối với `artifacts/evidence/E2E-02/`; reference đóng băng trước QA.

- Latency: Q06=12.929s; Q26=10.361s.

- Reproduction: Q06 fresh; Q26 sauQ01/Q06 trong cùng ledger cho reuse; so body với hai đoạn đầu PDF 14. Không đồng nhất source citations đúng với answer complete.

- Preliminary category: `Composer`. Chỉ phân nhóm triệu chứng, không phải root cause.

- Root cause: `NOT_ANALYZED`; Status: `OPEN_FOR_FIX_02`.

## E2E02-I006 — Phân tích chất lượng lợi nhuận còn thiên về liệt kê facts

- Severity: **Medium**; Questions: Q21.

- PDF/Document: BBS_2025 / PDF 7,8.

- Expected: NêuPAT/CFO, diễn giải mô tả CFO dương/lớn hơnPAT, giữ giới hạn không kết luận chất lượng cao/thấp.

- Actual: Hai values đúng nhưng các yêu cầu nhận định bị để unanswered; caveats đúng, thiếu diễn giải mô tả.

- Symptom: PARTIAL; không coi việc thận trọng trước suy luận vượt evidence là lỗi.

- Evidence: `turns/Q21.json` + `traces.json#Q21` + pdf-review/BBS_2025-p7.jpg,pdf-review/BBS_2025-p8.jpg. Mọi đường dẫn artifact tương đối với `artifacts/evidence/E2E-02/`; reference đóng băng trước QA.

- Latency: Q21=37.804s.

- Reproduction: ChạyQ01/Q02 trước để tạo claims, rồiQ21; kiểm traPARTIAL_REUSE_AND_REFRESH, unanswered_requirements và PDF 7/8.

- Preliminary category: `Agent`. Chỉ phân nhóm triệu chứng, không phải root cause.

- Root cause: `NOT_ANALYZED`; Status: `OPEN_FOR_FIX_02`.

## E2E02-I007 — Độ trễ financial/mixed QA lớn dù không gọi provider

- Severity: **High**; Questions: Q03,Q11,Q12,Q13,Q14,Q16,Q21,Q22,Q38.

- PDF/Document: BCC_2025 / PDF5; BBS_2025 / PDF 7; BBS_2025 / PDF5,6; BCC_2025 / PDF 7; BCC_2025 / PDF5,6; BBS_2025 / PDF 7,8; BBS_2025 / PDF5,6,12.

- Expected: Local demo cần thời gian trả lời sử dụng được;30/60s chỉ là tín hiệu chẩn đoán, không chuẩn SLA.

- Actual: Có 9 lượt trên 30 giây; Q22=74,486s và Q38=85,312s. Trace Q22 có các unit U1/U2/U3 và graph_context; Q38 có M5/M6/ledger, không provider.

- Symptom: Độ trễ lớn trên câu có trả lời; không dùng fast abstention để kết luận nhanh.

- Evidence: `turns/Q03.json` + `traces.json#Q03` + pdf-review/BCC_2025-p5.jpg; `turns/Q11.json` + `traces.json#Q11` + pdf-review/BBS_2025-p7.jpg; `turns/Q12.json` + `traces.json#Q12` + pdf-review/BBS_2025-p7.jpg; `turns/Q13.json` + `traces.json#Q13` + pdf-review/BBS_2025-p5.jpg,pdf-review/BBS_2025-p6.jpg; `turns/Q14.json` + `traces.json#Q14` + pdf-review/BCC_2025-p7.jpg; `turns/Q16.json` + `traces.json#Q16` + pdf-review/BCC_2025-p5.jpg,pdf-review/BCC_2025-p6.jpg; `turns/Q21.json` + `traces.json#Q21` + pdf-review/BBS_2025-p7.jpg,pdf-review/BBS_2025-p8.jpg; `turns/Q22.json` + `traces.json#Q22` + pdf-review/BBS_2025-p5.jpg,pdf-review/BBS_2025-p6.jpg,pdf-review/BBS_2025-p12.jpg; `turns/Q38.json` + `traces.json#Q38` + pdf-review/BCC_2025-p7.jpg. Mọi đường dẫn artifact tương đối với `artifacts/evidence/E2E-02/`; reference đóng băng trước QA.

- Latency: Q03=30.401s; Q11=36.271s; Q12=38.276s; Q13=40.981s; Q14=39.624s; Q16=47.002s; Q21=37.804s; Q22=74.486s; Q38=85.312s.

- Reproduction: Cùng máy/config/ledger-order; dùng force_refresh như questions.json và perf_counter. Không chạy song song QA. VớiQ22 giữQ13 trước để có reuse. Xem latency.csv và native trace; không cộng timings lồng nhau.

- Preliminary category: `Performance`. Chỉ phân nhóm triệu chứng, không phải root cause.

- Root cause: `NOT_ANALYZED`; Status: `OPEN_FOR_FIX_02`.

## E2E02-I008 — Output dài với reason codes và nguồn lặp cấp trang

- Severity: **Low**; Questions: Q01,Q13,Q22.

- PDF/Document: BBS_2025 / PDF 7; BBS_2025 / PDF5,6; BBS_2025 / PDF5,6,12.

- Expected: Trả lời tài chính và giới hạn/citations dễ đọc trong local demo.

- Actual: Q01 có10references cùng PDF 7; Q13 có19references và nhiều raw reason codes lặp trong caveats/source sections.

- Symptom: Khó đọc và nhiều chi tiết implementation trong phần trả lời.

- Evidence: `turns/Q01.json` + `traces.json#Q01` + pdf-review/BBS_2025-p7.jpg; `turns/Q13.json` + `traces.json#Q13` + pdf-review/BBS_2025-p5.jpg,pdf-review/BBS_2025-p6.jpg; `turns/Q22.json` + `traces.json#Q22` + pdf-review/BBS_2025-p5.jpg,pdf-review/BBS_2025-p6.jpg,pdf-review/BBS_2025-p12.jpg. Mọi đường dẫn artifact tương đối với `artifacts/evidence/E2E-02/`; reference đóng băng trước QA.

- Latency: Q01=25.425s; Q13=40.981s; Q22=74.486s.

- Reproduction: ChạyQ01/Q13; đọc toàn bộ answer_vi, so số ký tự/body và repeated PDF pages; không coi citation occurrence là unique evidence độc lập.

- Preliminary category: `Composer`. Chỉ phân nhóm triệu chứng, không phải root cause.

- Root cause: `NOT_ANALYZED`; Status: `OPEN_FOR_FIX_02`.

- Evidence bổ sung: `{"answer_chars": {"Q01": 4426, "Q13": 8216, "Q22": 10296}}`.

## E2E02-I009 — Follow-up hỏi trang của đoạn vừa trả lời bị chặn

- Severity: **Medium**; Questions: Q34.

- PDF/Document: BBS_2024 / PDF 21.

- Expected: Sau Q33 đã có citation PDF 21 của BBS 2024, Q34 phải giữ chủ đề và trả lại vị trí đó.

- Actual: verification_blocked; company/year vẫn là BBS 2024, resolved_question đổi thành truy vấn thuyết minh khoản vay; không có citation.

- Symptom: Không trả được follow-up về nguồn dù lượt trước đã có evidence.

- Evidence: `turns/Q34.json` + `traces.json#Q34` + pdf-review/BBS_2024-p21.jpg. Mọi đường dẫn artifact tương đối với `artifacts/evidence/E2E-02/`; reference đóng băng trước QA.

- Latency: Q34=19.332s.

- Reproduction: Session mới: gửi nguyên Q33 rồi Q34 qua ConversationService.send; cùng runtime/catalog và ledger đánh giá. Inspect original/resolved_question, context và tool_calls.

- Preliminary category: `Conversation`. Chỉ phân nhóm triệu chứng, không phải root cause.

- Root cause: `NOT_ANALYZED`; Status: `OPEN_FOR_FIX_02`.

## Bàn giao

Next action: Tech Lead nghiệm thu E2E-02 và quyết định phạm vi FIX-02. Không issue nào được đóng trong task này.

## Phân tích FIX-02 — 09/11/2026

Các mô tả `NOT_ANALYZED` phía trên giữ lịch sử discovery. Bảng này là phân tích
tiếp theo từ code và traces; **không tự đóng issue**. Chi tiết và giới hạn trong
[báo cáo FIX-02](fix-02-adaptive-llm-agents.md).

| Issue | Nguyên nhân xác định | Thay đổi/bằng chứng và trạng thái |
| --- | --- | --- |
| I001 | Runner import source archive ngoài checkout; `default_project_root()` thất bại, policy/release loaders fallback empty khi không cấu hình. Q08 dùng composition không corrected; M6 chỉ replay OCR cũ nên fidelity không chứng minh PDF đúng. | Runner truyền storage roots tường minh; project root có cấu hình. Live Q08 dùng approved corrected composition,2ACCEPT,1citation correction +1original,PDF16; giữ từ “khó”. OPEN chờ Tech Lead xác nhận phạm vi; không tuyên bố sửa mọi lỗi OCR. |
| I002 | `source_assertion(entity_role)` yêu cầu một text projection dạng `Vai trò: Họ tên`; layout tách vai trò/tên không đủ relationship proof. Q05 có3candidates nhưng không được M6 chấp nhận. | Adaptive BM25 không tạo được relationship provenance còn thiếu. OPEN; không hardcode tên hoặc đoán liên kết. |
| I003 | Loader BBS2024 chỉ có descriptor/document evidence, không có canonical financial facts. | OPEN, thiếu accepted financial coverage; không mượn cột2024 của filing2025 làm tài liệu2024. |
| I004 | Parser single-target coi nhiều năm/“so sánh” là cross-document trước Planner; inventory M7 cũng chặn. | Auto chuyển quyết định sang validated Planner; period riêng từng fact operation và answer obligation trong cùng filing. Synthetic2030/2029 có cùng snapshot PASS; chưa rerun Q15/Q20/Q23/Q24 thật. OPEN; D03-B10 liên filing giữ nguyên. |
| I005 | Definition route/exact-text và `source_assertion` cho “nhân viên quản lý chủ chốt” dừng tại đơn vị kết thúc câu; đoạn doanh nghiệp liên quan là nghĩa vụ chưa được biểu diễn đầy đủ. | OPEN; LLM retrieval không tự nâng excerpt thiếu thành câu trả lời đầy đủ. |
| I006 | Baseline tắt Gemini; specialist grammar chỉ fact/sign; validator cũ yêu cầu một fact reference cho interpretation. | Có assignments, analysis premises kiểm tra độc lập và semantic critics/Judge. Q21 live có2specialists và2feedback/replans; vẫn partial/provider failure, chưa đạt Judge PASS sau revision. OPEN cải thiện một phần. |
| I007 | Trace baseline có0provider nhưng M5/M6 lớn; constructors deepcopy catalog và proof/context serialization lặp. Live replan còn gửi context quá lớn. | Giữ stage timings; live Q21 bổ sung114,672s/13calls/133034known tokens. Đã rút gọn context sau lượt đo, chưa live đo lại. OPEN, không gọi fast failure là tối ưu thành công. |
| I008 | Composer/citation renderer giữ từng protected source reference và đưa nhiều caveats/reason codes vào prose. | OPEN; chưa thay presentation hoặc gộp citations mất identity. |
| I009 | Resolver biến câu hỏi vị trí thành truy vấn thuyết minh mới, mất exact source topic của lượt trước. | Auto exact verified-source lookup replay câu gốc với binding hiện tại. Live Q33→Q34:Q34 completed_with_caveats,0calls,PDF21,165ms; OPEN chờ review, chưa khẳng định mọi follow-up đã đạt. |

### Bổ sung hoàn thiện FIX-02

Source321f09e sửa inventory độc lập với claims, schema isolation và liên kết
numeric premises→semantic proof; không nới M6/Ledger. Hai lượt5ca được cho phép
đã chạy trên committed archives. I001 tiếp tục có quotation đúng/“khó”/PDF16.
I006 còn PARTIAL: Judge PASS nhưng M6/M7 không chấp nhận đủ analyses; chưa live
revision thành công. I007 còn OPEN: Q21cuối25626known tokens/85,602s,không có
replan call để đo compaction; local processing vẫn lớn. F08dependency đã đi qua,
nhưng Judge có structured_output_invalid; Q11calculator/M6 ACCEPT nhưng answer
obligations dư operands làm partial. Q01cuốihttp503. Không đóng issue hoặc gọi
hai lượt này thành final5/5PASS; xem [báo cáo](fix-02-adaptive-llm-agents.md).

### Remediation tiếp theo — 10/11/2026

Source9a356bf sửa typed goals/operand completeness, negated-ratio routing,
native/M7 coverage, strict JSON isolation và request catalog/lineage/schema reuse.
I006 còn OPEN: một lượt live6748da7 lộ goal-binding integration failures; đã sửa
và replay chính Planner outputs, nhưng chưa final live Specialists/Judge/revision.
I007 còn OPEN: paired offline Q11,6mẫu/version,median40,001→9,947s (−75,1%);
calculation/provenance equivalent, không dùng profiler inclusive làm wall speedup.
CI42729994715 SUCCESS đúng9a356bf63Python/9Web; không coi CI là financial accuracy.
Cả9issues giữ OPEN chờ Tech Lead; chi tiết/limitations trong phần remediation của
[báo cáo FIX-02](fix-02-adaptive-llm-agents.md#correctness--performance-remediation--10112026).

### Controlled live9a356bf — 10/11/2026

Một lượt Q11→Q21→F08 theo phê duyệt mới,17calls/101834API tokens/0provider failures,
runtime/inputs cố định. I006:Q21vẫnPARTIAL;analysis lời giới hạn “dữ liệu chưa đủ để
tính toán tỷ lệ…” bị formula gate chặn (D01tái diễn,High/P1),không thiếu PAT/CFO.
Raw Judge PASS bị native/M7 coverage guard đổi INSUFFICIENT_EVIDENCE. F08có natural
coverage revision thành công:backend phát feedback→Planner sửa affected task→tools
CACHE_HIT→native ACCEPT interpretation→M7answered/Judge PASS. Không ép verdict hoặc
sửa runtime để tạo loop. Q11completed_with_caveats,metricM6 ACCEPT/M7answered.
I007không benchmark thêm;wall liveQ11/Q21/F08=22,394/29,874/50,412s,không ghép với
offline timings. I008prose/caveats/internal reason codes còn. Giữ9issuesOPEN,không
coi F08 đạt là Q21đạt;chi tiết ở phần controlled live của
[report](fix-02-adaptive-llm-agents.md#kiểm-chứng-live-có-kiểm-soát-trên9a356bf--10112026).
