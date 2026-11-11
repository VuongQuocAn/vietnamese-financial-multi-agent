# EF-CORE-01 — Tích hợp graph vào Multi-Agent QA

Ngày 11/11/2026, Asia/Bangkok. Baseline `0f6165546d2db7a130fbcca666d0e2abf95b7649`.
Status: **REVIEW — CONDITIONAL READY cho tích hợp**, chờ Tech Lead nghiệm thu.
Implementation [`f5bbac6b6d5befd0b3021654b48218feeab54942`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/f5bbac6b6d5befd0b3021654b48218feeab54942) đã push main;
[CI42964593478](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42964593478)
SUCCESS đúng SHA, **210 tests PASS**. Không tự chuyển DONE.

## Quyết định tích hợp

Khoảng trống nằm ở M5 Lite: inventory và retrieval chỉ chọn facts/metrics; không
gọi graph facade và không đưa quan hệ tới Specialist. Catalog đã có typed EF-EG;
financial QA còn có approved compositions trong pipeline, nhưng trước đây không
chuyển chúng cho Lite orchestrator. Không cần graph builder, database hay agent mới.

QA chọn đúng một composition có financial document/snapshot khớp request; nếu có,
M5 dùng `CompositionGraphView` và `GraphRetrievalTools` hiện có. Không suy đoán hoặc
tạo composition ID. Nếu chỉ có catalog đã pin, `from_catalog()` xác minh descriptor,
ancestry, graph validation và lọc cả hai endpoint đúng document/snapshot; dùng lại
resolution và traversal của cùng `GraphRetrievalTools`. Không fallback qua snapshot
cha hoặc document khác. Composition không hợp lệ được ghi unavailable; Financial
Tools tiếp tục. Document-only QA giữ đường hiện có, không mở rộng Lite thành một
document agent.

Supervisor chọn `use_graph` theo ý định nguồn, toán hạng, phân tích nhiều bước hoặc
ngữ cảnh. Mặc định của task là false; câu hỏi tra giá trị đơn giản không bị buộc gọi
graph. Request `m5_graph=false` tắt graph để đối chiếu, không tắt Financial Tools.
Fact ánh xạ bằng `graph_id("source_fact", observation_identity)`; metric dùng đúng
metric ID từ Calculator. Document nodes được resolve bằng typed identity hiện có
trong neighborhood hoặc API graph; không dùng similarity/LLM đoán ID.

Mỗi Specialist tối đa sáu starting nodes, depth 2, tám neighbors cho mỗi truy vấn;
API vẫn kiểm soát depth 1–3 và limit 1–50. Traversal xen kẽ các nhóm relation theo
thứ tự request truyền, giữ edge order ổn định trong mỗi nhóm, giúp
toán hạng/nguồn hoặc contextual links không bị associations nhiều cạnh chiếm chỗ.
Raw tool response giữ đủ nodes, edges, operand roles, quality, grounding, citations,
source metadata và caveats; bundle mới chỉ thêm `graph_contexts`.

Prompt nhận projection tối đa 14.000 ký tự, nằm trong cap 48.000 hiện có. Citations
gộp theo nguồn/snapshot/trang/provenance và giữ exact selectors, không lặp bbox/ảnh;
raw trace giữ nguyên original citations. Text excerpts chỉ từ records API trả về,
tối đa 600 ký tự và có cờ truncated. Không gửi toàn graph vào Gemini. Model chỉ được
dùng evidence IDs đã chọn; handles G chỉ để khai báo cách dùng quan hệ trong goal,
không tạo authority tài chính.

## Graph → Specialist → M6 → Ledger → M7

`get_graph_context` → typed bundle → projection trong prompt/selection trace →
Specialist facts/metrics/analyses → adapter M6 hiện có → verification → Ledger → M7.
Không sửa M6, M7 hoặc phép tính tài chính. Graph không tạo ACCEPT. Numeric candidates
vẫn giữ original fact references, approved calculation và citations; interpretations
vẫn qua semantic M6. `associated_with` là exact source association;
`same_extraction_context` là contextual-only; cả hai không chứng minh toàn bộ văn
bản hỗ trợ claim hoặc quan hệ nhân quả. `used_in` thể hiện operand role, không thay
Calculator hoặc kiểm chứng phép tính.

Trace phân biệt bốn mức: gọi tool; trả relations; relations được cung cấp và model
khai báo cách dùng; candidate tương ứng được M6 ACCEPT và được M7 chọn. Chỉ có prompt
chứa graph hoặc câu trả lời đúng không đủ chứng minh graph đóng góp.

Các file runtime thay đổi: `src/tools/graph_retrieval.py`,
`src/agents/lite_orchestrator.py`, `src/agents/supervisor.py`,
`src/api/financial_qa_pipeline.py`, `src/api/qa_pipeline_contracts.py`.
Tests: `tests/unit/test_ef_core.py`; runner: `scripts/evaluate_ef_core.py`;
CI chỉ thêm nhóm ba controls vào suite trọng tâm; planning checker chấp nhận ID mới.

## Phương pháp thực nghiệm

Dùng financial snapshot BBS 2025 được duyệt và EF-01 composition có thật; không
OCR/extraction, không thay raw/processed hoặc persisted financial inputs. Runtime
tách từ baseline Git, chỉ overlay năm file EF-CORE; không nạp các runtime local edits
ngoài task. Gemini qua QA adapter, Shared Gateway và key rotation CORE-FLOW-01.
Mỗi request giữ giới hạn 32 provider calls và 300 giây; không đặt task-wide call cap.

G2/G3/G4 chạy OFF trước; ON dùng lại đúng Supervisor plan của OFF. Cùng PDF, snapshot,
model, tools, M6/M7; ledger mới cho từng lượt. Planning call dùng chung, vì vậy latency
end-to-end ON/OFF không phải ước lượng nhân quả công bằng cho overhead; cần đối chiếu
riêng M5/tool timings và provider usage. Provider failure và numeric fallback được
ghi đúng thực tế. Đây là đối chiếu nhỏ, chưa phải ablation M8/EF-CORE-02.

Lượt pilot phát hiện projection citations quá lớn làm mất `used_in` trong prompt và
associations chiếm node budget trước contextual links; đã sửa tại projection/traversal.
G5 pilot hỏi chung bảng/thuyết minh; lượt cuối tập trung nợ phải trả và quan hệ ngữ
cảnh của đúng financial seed. Không sửa nguồn hoặc mở rộng graph để tạo kết quả đẹp.
Mọi pilot/offline/live lưu riêng trong `artifacts/evidence/EF-CORE-01/` (ignored).

## Kết quả live trên BBS thật

Lượt A (`live-final`) dùng projection đã sửa; lượt B (`live-context`) là runtime cuối với traversal xen kẽ các nhóm relation theo thứ tự request. B kiểm tra lại G2/G4/G5; G1/G3/G6 báo từ A, không giả là đã rerun trên B. Mọi cặp ON/OFF trong từng lượt giữ đúng cùng plan. G3 dùng A; G2/G4 dùng B. Raw freezes giữ hashes riêng cho từng runtime.

| Case | Graph calls | Relations trả về (unique) | Specialist dùng → M6 ACCEPT → M7 chọn | Đánh giá |
| --- | ---: | --- | --- | --- |
| G1 | 1 | from_source: 8 | 0 → 0 → 0 | CORRECT_WITH_CAVEAT |
| G2 | 3 | used_in: 3, from_source: 12, associated_with: 7 | 1 → 1 → 1 | CORRECT_WITH_CAVEAT |
| G3 | 6 | used_in: 4, from_source: 34 | 0 → 0 → 0 | PARTIAL |
| G4 | 3 | used_in: 2, from_source: 8, associated_with: 5, same_extraction_context: 2 | 1 → 1 → 1 | CORRECT_WITH_CAVEAT |
| G5 | 1 | from_source: 3, same_extraction_context: 2, associated_with: 2, used_in: 1 | 0 auto; 1 manual → 1 → 1 | PARTIAL |
| G6 | 3 | used_in: 2, from_source: 18 | 0 → 0 → 0 | CORRECT_WITH_CAVEAT |

Mức dùng graph là dấu vết về quy trình xử lý; không là ước lượng hiệu quả nhân quả hoặc chứng nhận tài chính.

## Đối chiếu Graph OFF/ON

| Case | OFF / ON kết quả | Tokens OFF / ON | Planning chung | Latency OFF / ON (s) | Kết luận |
| --- | --- | ---: | ---: | ---: | --- |
| G2 | completed_with_caveats / completed_with_caveats | 8612 / 11804 | 1939 | 18.650 / 30.635 | Cả hai đúng; ON nêu rõ dùng operand edges, không thêm số liệu. |
| G3 | completed_with_caveats / partial_verified_coverage | 13471 / 15459 | 1973 | 34.128 / 34.690 | OFF đầy đủ hơn; ON PARTIAL. Chưa có lợi ích về completeness. |
| G4 | completed_with_caveats / completed_with_caveats | 7763 / 12078 | 1954 | 19.430 / 32.889 | Cả hai đúng; ON dùng lineage, không thêm semantic evidence. |

Tokens gồm M5 và downstream, đối soát tổng với provider-events; planning chỉ gọi một lần ở OFF. Nếu trừ planning chung khỏi OFF, ON thêm lần lượt 5131 tokens ở G2, 3961 tokens ở G3, 6269 tokens ở G4. Không dùng chênh lệch latency một sample để kết luận tốc độ. Các cặp A/B nêu trên không có logical provider failure.

## Bằng chứng từng câu hỏi

### G1 — CORRECT_WITH_CAVEAT

Câu hỏi: Doanh thu thuần BBS năm 2025 là bao nhiêu? Hãy truy vết số liệu và chỉ rõ nguồn PDF.

Nguồn trace: `live-final`. Supervisor: Sinh lời.

Financial/Evidence Tools: get_financial_fact ×1, get_evidence_sources ×1. Graph Tool: get_graph_context ×1; relations: from_source.

Thông tin graph thực sự cung cấp: from_source ×4. Đúng Revenue FY2025 và PDF p.7; generic partial-coverage message còn thừa. Graph không thêm số liệu hoặc cách dùng được khai báo.

Candidates và M6 verdicts (nhãn nội dung; IDs đầy đủ chỉ trong raw trace):

- supported_interpretation: Số liệu doanh thu thuần năm 2025 được ghi nhận tại trang 7 của tài liệu nguồn với giá trị 450474531227 VND. Giới hạn: page_level_only Giới hạn: source_reference_uncertain — **ABSTAIN**.
- fact: Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. — **ACCEPT**.

Câu trả lời M7 nguyên văn (kèm citations):

> Doanh thu thuần của BBS năm 2025 là 450.474.531.227 VND. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### G2 — CORRECT_WITH_CAVEAT

Câu hỏi: Doanh thu thuần BBS năm 2025 tăng bao nhiêu phần trăm so với 2024? Truy vết các số liệu tạo ra tỷ lệ đó và nguồn của từng toán hạng.

Nguồn trace: `live-context`. Supervisor: Sinh lời.

Financial/Evidence Tools: get_financial_fact ×4, get_evidence_sources ×2, calculate_financial_metric ×1. Graph Tool: get_graph_context ×3; relations: used_in, from_source, associated_with.

Thông tin graph thực sự cung cấp: used_in ×2, associated_with ×2. Revenue FY2025/2024 và Revenue Growth 26,71% đúng. Hai used_in được Specialist dùng xác định operand roles; analysis ACCEPT và M7 chọn. Financial Tools đã đủ để tính, không chứng minh graph tăng accuracy.

Cách dùng được khai báo: “Sử dụng G1 và G2 để xác định quan hệ operand giữa doanh thu năm 2025 và 2024 với metric tăng trưởng doanh thu.”. M6: ACCEPT; M7 chọn: có.

Candidates và M6 verdicts (nhãn nội dung; IDs đầy đủ chỉ trong raw trace):

- supported_interpretation: Tỷ lệ phần trăm tăng trưởng doanh thu thuần được tính toán dựa trên số liệu doanh thu thuần của năm 2025 và năm 2024. Giới hạn: Chỉ phản ánh biến động số học giữa hai kỳ theo công thức đã thiết lập. — **ACCEPT**.
- fact: Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. — **ACCEPT**.
- fact: Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. — **ACCEPT**.
- approved_metric: Tăng trưởng doanh thu kỳ 2025 đạt 26,71%. — **ACCEPT**.

Câu trả lời M7 nguyên văn (kèm citations):

> Doanh thu thuần năm 2025 của BBS đạt 450.474.531.227 VND, trong khi doanh thu thuần năm 2024 là 355.507.372.286 VND. Mức tăng trưởng doanh thu kỳ 2025 so với kỳ 2024 đạt 26,71%. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Chỉ phản ánh biến động số học giữa hai kỳ theo công thức đã thiết lập.
>
> Giới hạn: Chỉ phản ánh biến động số học giữa hai kỳ theo công thức đã thiết lập.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### G3 — PARTIAL

Câu hỏi: Doanh thu và lợi nhuận gộp BBS thay đổi như thế nào từ 2024 sang 2025? Những dữ liệu và nguồn nào hỗ trợ kết luận?

Nguồn trace: `live-final`. Supervisor: Sinh lời.

Financial/Evidence Tools: get_financial_fact ×8, get_evidence_sources ×4, calculate_financial_metric ×2. Graph Tool: get_graph_context ×6; relations: used_in, from_source.

Thông tin graph thực sự cung cấp: used_in ×2, from_source ×2. Số liệu hai năm đúng, nhưng Graph ON không diễn giải rõ mức giảm gross profit, có câu tiếng Việt không dấu/vụng. Graph OFF đầy đủ hơn trong lượt A; không ghi ON tốt hơn.

Candidates và M6 verdicts (nhãn nội dung; IDs đầy đủ chỉ trong raw trace):

- supported_interpretation: Ty le tang truong doanh thu tu nam 2024 sang nam 2025 duoc ghi nhan thong qua phep tinh phan tram thay doi giua hai ky. Giới hạn: So lieu chua duoc kiem tra toan dien boi M6 — **ACCEPT**.
- supported_interpretation: Loi nhuan gop thay doi giua nam 2024 va nam 2025 dua tren gia tri thuc te tu nguyen lieu. Giới hạn: Chi phan tich bien dong so hoc chua suy luan nguyen nhan ngam dinh — **ACCEPT**.
- fact: Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. — **ACCEPT**.
- fact: Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. — **ACCEPT**.
- fact: Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. — **ACCEPT**.
- fact: Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND. — **ACCEPT**.
- approved_metric: Tăng trưởng doanh thu kỳ 2025 đạt 26,71%. — **ACCEPT**.

Câu trả lời M7 nguyên văn (kèm citations):

> Từ năm 2024 sang năm 2025, doanh thu thuần của BBS ghi nhận sự thay đổi từ 355.507.372.286 VND lên 450.474.531.227 VND, tương ứng mức tăng trưởng doanh thu đạt 26,71%. [1]
>
> Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND. [1]
>
> Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. [1]
>
> Loi nhuan gop thay doi giua nam 2024 va nam 2025 dua tren gia tri thuc te tu nguyen lieu. Giới hạn: Chi phan tich bien dong so hoc chua suy luan nguyen nhan ngam dinh [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Chi phan tich bien dong so hoc chua suy luan nguyen nhan ngam dinh; So lieu chua duoc kiem tra toan dien boi M6
>
> Giới hạn: Chi phan tich bien dong so hoc chua suy luan nguyen nhan ngam dinh; So lieu chua duoc kiem tra toan dien boi M6
>
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### G4 — CORRECT_WITH_CAVEAT

Câu hỏi: Hãy phân tích mối liên hệ giữa tổng tài sản, nợ phải trả và tỷ lệ nợ trên tổng tài sản của BBS năm 2025. Truy vết các thành phần và nguồn, không suy diễn nhân quả.

Nguồn trace: `live-context`. Supervisor: Thanh khoản và đòn bẩy.

Financial/Evidence Tools: get_financial_fact ×4, get_evidence_sources ×2, calculate_financial_metric ×1. Graph Tool: get_graph_context ×3; relations: used_in, from_source, associated_with, same_extraction_context.

Thông tin graph thực sự cung cấp: used_in ×2, associated_with ×1, from_source ×1. Assets, Liabilities và Debt/Assets 59,06% đúng; phân biệt tỷ trọng toán học với nhân quả. Specialist dùng used_in; contextual links được trả/cung cấp nhưng không tạo thêm kết luận ngữ nghĩa.

Cách dùng được khai báo: “Phân tích mối liên hệ toán học giữa các chỉ tiêu dựa trên cấu trúc nguồn G1 và G2”. M6: ACCEPT; M7 chọn: có.

Candidates và M6 verdicts (nhãn nội dung; IDs đầy đủ chỉ trong raw trace):

- supported_interpretation: Tổng tài sản và tổng nợ phải trả năm 2025 được ghi nhận làm thành phần cơ sở để xác định tỷ lệ nợ phải trả trên tổng tài sản. Giới hạn: Chỉ phản ánh quan hệ cấu trúc tỷ trọng số học, không ngụ ý quan hệ nhân quả. — **ACCEPT**.
- fact: Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. — **ACCEPT**.
- fact: Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. — **ACCEPT**.
- approved_metric: Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%. — **ACCEPT**.

Câu trả lời M7 nguyên văn (kèm citations):

> Tại ngày 31/12/2025, tổng tài sản của BBS ghi nhận là 266.086.680.765 VND và tổng nợ phải trả là 157.146.559.558 VND. [1][2]
>
> Dựa trên các thành phần cơ sở này, tỷ lệ nợ phải trả trên tổng tài sản tại cùng thời điểm là 59,06%. Mối liên hệ này phản ánh quan hệ cấu trúc tỷ trọng số học và không ngụ ý quan hệ nhân quả. [2][1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Chỉ phản ánh quan hệ cấu trúc tỷ trọng số học, không ngụ ý quan hệ nhân quả.
>
> Giới hạn: Chỉ phản ánh quan hệ cấu trúc tỷ trọng số học, không ngụ ý quan hệ nhân quả.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [2] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### G5 — PARTIAL

Câu hỏi: Tổng nợ phải trả BBS tại ngày 31/12/2025 là bao nhiêu? Truy vết nguồn và các liên kết ngữ cảnh trích xuất bằng EF-EG. Phân biệt association chính xác, cùng ngữ cảnh trích xuất và bằng chứng ngữ nghĩa; có thể suy ra nhân quả từ các liên kết này không?

Nguồn trace: `live-context`. Supervisor: Thanh khoản và đòn bẩy.

Financial/Evidence Tools: get_financial_fact ×1, get_evidence_sources ×1. Graph Tool: get_graph_context ×1; relations: from_source, same_extraction_context, associated_with, used_in.

Thông tin graph thực sự cung cấp: used_in ×1, same_extraction_context ×2. Có cả exact association và contextual links trong tool trace, giữ contextual_only và source usability. Specialist nhắc G1/G2/G3 trong statement thay vì goal, nên auto-use trace đếm 0; manual audit xác nhận một analysis dùng các links, ACCEPT và được M7 chọn. Chưa giải thích đủ exact selector association so với cùng extraction context; không coi đây là semantic support mới.

Candidates và M6 verdicts (nhãn nội dung; IDs đầy đủ chỉ trong raw trace):

- supported_interpretation: Tổng nợ phải trả của BBS tại ngày 31/12/2025 được ghi nhận với giá trị định danh là 157146559558 VND dựa trên nguồn dữ liệu được cung cấp. Giả định: Số liệu trích xuất từ nguồn phản ánh đúng giá trị ghi nhận tại kỳ báo c — **ACCEPT**.
- supported_interpretation: Các liên kết ngữ cảnh và đồ thị (như G1, G2, G3) thể hiện quan hệ cùng ngữ cảnh trích xuất và liên kết cấu trúc/trang tài liệu, nhưng không cung cấp bằng chứng ngữ nghĩa trực tiếp để khẳng định quan hệ nhân quả. Giả định — **ACCEPT**.
- fact: Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. — **ACCEPT**.

Câu trả lời M7 nguyên văn (kèm citations):

> Tại ngày 31/12/2025, tổng nợ phải trả của BBS được ghi nhận với giá trị là 157.146.559.558 VND dựa trên nguồn dữ liệu được cung cấp. [1]
>
> Các liên kết ngữ cảnh và đồ thị thể hiện quan hệ cùng ngữ cảnh trích xuất và liên kết cấu trúc hoặc trang tài liệu, nhưng không cung cấp bằng chứng ngữ nghĩa trực tiếp để khẳng định quan hệ nhân quả. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Cấu trúc liên kết trích xuất từ đồ thị phản ánh đúng vị trí tài liệu nguồn.; Liên kết cấu trúc hoặc cùng trang không đồng nghĩa với quan hệ nhân quả tài chính.; Thiếu thông tin ngữ nghĩa sâu để kiểm chứng mối quan hệ nguyên nhân - kết quả.; Chỉ số liệu ghi nhận tại nguồn, chưa bao gồm kiểm chứng kiểm toán hoặc đánh giá bản chất kinh tế sâu hơn.; Số liệu trích xuất từ nguồn phản ánh đúng giá trị ghi nhận tại kỳ báo cáo.
>
> Giới hạn: Liên kết cấu trúc hoặc cùng trang không đồng nghĩa với quan hệ nhân quả tài chính.; Thiếu thông tin ngữ nghĩa sâu để kiểm chứng mối quan hệ nguyên nhân - kết quả.; Chỉ số liệu ghi nhận tại nguồn, chưa bao gồm kiểm chứng kiểm toán hoặc đánh giá bản chất kinh tế sâu hơn.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### G6 — CORRECT_WITH_CAVEAT

Câu hỏi: Hãy truy vết nguồn số lượng khách hàng mới của BBS năm 2025 và giải thích vì sao làm doanh thu tăng. Nếu không có node hoặc quan hệ phù hợp hãy nói rõ giới hạn.

Nguồn trace: `live-final`. Supervisor: Sinh lời.

Financial/Evidence Tools: get_financial_fact ×4, get_evidence_sources ×2, calculate_financial_metric ×1. Graph Tool: get_graph_context ×3; relations: used_in, from_source.

Thông tin graph thực sự cung cấp: used_in ×2, from_source ×2. Không có customer-count node, không tạo cạnh khách hàng→doanh thu; M7 nói rõ thiếu số khách hàng mới và dữ liệu nhân quả. Revenue/Growth đúng nhờ Financial Tools, không phải phát hiện mới từ graph.

Candidates và M6 verdicts (nhãn nội dung; IDs đầy đủ chỉ trong raw trace):

- supported_interpretation: Nguồn dữ liệu hiện tại ghi nhận doanh thu thuần năm 2025 và năm 2024 lần lượt là các giá trị theo chỉ tiêu tài chính, đồng thời dữ liệu chưa cung cấp số lượng khách hàng mới của năm 2025 để phân tích nguyên nhân chi tiết — **ACCEPT**.

Câu trả lời M7 nguyên văn (kèm citations):

> Nguồn dữ liệu hiện tại ghi nhận doanh thu thuần năm 2025 đạt 450.474.531.227 VND và năm 2024 đạt 355.507.372.286 VND, tương ứng mức tăng trưởng 26,71%. Tuy nhiên, dữ liệu chưa cung cấp số lượng khách hàng mới của năm 2025 cũng như chưa có dữ liệu nhân quả chi tiết để giải thích biến động doanh thu. [1]
>
> Lưu ý: Chưa có dữ liệu nhân quả chi tiết giải thích biến động doanh thu; Không có số liệu về số lượng khách hàng mới; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Giới hạn: Không có số liệu về số lượng khách hàng mới; Chưa có dữ liệu nhân quả chi tiết giải thích biến động doanh thu
>
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

## Negative controls, nguồn và chất lượng

Ba controls mới kiểm tra lineage/citations và wrong snapshot/node; graph ON/OFF giữ candidate qua adapter M6; missing graph vẫn có Financial candidates. Control nguồn nhiều anchors kiểm tra contextual link không bị node budget che khuất; 40 lần lặp citations không làm mất used_in trong projection. Thêm 13 composition controls có sẵn kiểm tra wrong pointer/page/request/snapshot/company/legacy và tampered relations. Hai real controls trong mỗi runner trả unavailable cho snapshot không bind và not_found cho node không tồn tại. G6 live từ chối tạo quan hệ thiếu dữ liệu. Không coi engineering PASS là financial accuracy.

Các lượt `offline-final`, `offline-projection`, `offline-context`, `live`, `live-final`, `live-context` đều đối chiếu 1.366 protected files và unchanged=true. Đây là tập inputs đã chọn của EXT-01/D-04/M4-05, không phải hash toàn dataset. Không OCR, extraction hoặc ghi data/raw, data/processed. Full raw traces, original citations, source IDs, ledger proofs và audit mapping giữ ignored; local edits ngoài task được đối chiếu bản sao trước triển khai.

## Gemini usage và kiểm tra engineering

| Lượt | Logical Gateway calls | Known tokens | Calls unknown tokens | Provider errors |
| --- | ---: | ---: | ---: | --- |
| live | 33 | 113279 | 3 | http_503 ×3 |
| live-final | 32 | 103119 | 0 | 0 |
| live-context | 18 | 52822 | 0 | 0 |
| Tổng | 83 | 269220 | 3 | HTTP503 ×3 |

Model `gemini-3.5-flash-lite`, QA rotating adapter hiện có. Đây là logical generate calls quan sát ngoài Shared Gateway; không khẳng định số HTTP attempts nội bộ key pool, vì runner không lưu adapter.events. Cost API trả unknown, không ước tính tiền. Ba HTTP503 của pilot được lưu; numeric fallback/retry theo giới hạn request hiện có, không replay giả live.

Local final: **49 targeted PASS** (EF controls, M5 Lite, composition graph, CORE-FLOW, M6 Lite, QA Lite), và **49/49 trên bản staged tách biệt** để loại local edits ngoài task. Source audit: 33 fact occurrences khớp frozen inputs, 324 original citation occurrences giữ source, 13 metric occurrences khớp Decimal độc lập; 15 tracked local files ngoài planning giữ nguyên bytes. Năm staged runtime overlays khớp hashes của live-context. Ruff, planning và diff checks PASS; staged Ruff kiểm tra 654 files, planning 128 tasks (worktree có thêm GEN-01a local, 129 tasks).

[CI42964593478](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42964593478) completed/SUCCESS đúng implementation `f5bbac6b6d5befd0b3021654b48218feeab54942`: Python 3.12, Ruff lint/format, planning và **210 tests PASS** (44,92 giây; một warning). Web smoke và full regression SKIPPED theo phạm vi. Phiên chốt evidence chỉ sửa docs/planning; không chạy lại Gemini, tests hoặc pipeline và không gán CI implementation cho commit tài liệu sau đó.

## Giới hạn và đề xuất EF-CORE-02

Đã có đóng góp xác định ở mức dùng quan hệ toán hạng trong G2/G4, nối được nguồn Specialist → M6 ACCEPT → M7. Graph chưa bổ sung financial facts mới so với Financial Tools; không chứng minh tăng answer accuracy. G3 ON còn kém completeness; G5 chưa diễn giải đủ exact association, original UUID evidence vẫn unavailable qua guards dù structural/contextual sources được giữ. Không nới source guards hoặc mở rộng graph để che giới hạn.

Đề xuất EF-CORE-02: ablation cùng source/model và nhiều repetitions, tách planning dùng chung và graph setup/traversal latency; đo chất lượng lineage/citations/completeness, parser nhận use reports từ raw statement lẫn goal; chọn thêm câu hỏi graph có khả năng bổ sung bằng chứng thực sự. Đây chỉ là đề xuất, chưa bắt đầu task đó.

Next action: Tech Lead review tích hợp cùng các caveats G3/G5; không tự chuyển DONE.
