# QWEN-DIAG-01 — Chẩn đoán partial QA với Qwen

Ngày 12/11/2026; **REVIEW**, chờ Tech Lead duyệt giải pháp. Chỉ chẩn đoán;
không sửa runtime, không gọi Qwen/Gemini, không full CI/M8.
Baseline HEAD `7ac4efddbd87a9f70345087da3c1156a7ace23b7`; replay dùng working tree
của lần smoke, có local edits. Hash code/input được lưu trong evidence ignored.

## Kết luận chính

**Không mất lineage ở case 2.** Nhận định “thiếu lineage” trong báo cáo
`docs/qwen-adapter-01-text-gateway.md` cần được thay bằng kết luận dưới đây:
Calculator tính đúng, model viết sai số trong statement; M6 từ chối statement
đúng thiết kế, nhưng M5 Lite không xuất riêng kết quả tính đã có proof.
Case 1 có hai lỗi riêng: analysis bị loại ở M5; **diễn giải đảo chiều xuất hiện
tại M7, sau M6**, được numeric-only release path cho qua.

Nguồn kiểm tra: `artifacts/evidence/QWEN-ADAPTER-01/live-01/{Q1,Q2}.json`,
`provider-events.json`, ledger của từng case. Traces dùng
`m5_lite=m6_lite=m7_lite=true`; 6 provider calls đều success.

## Case 1 — Đúng tỷ lệ, sai diễn giải

1. **M5 không chuyển được analysis sang M6.** Tại
   `response.trace.financial_execution.specialist_executions[0].result`,
   `raw_output.analyses[0].limitations` sao chép đúng **9** caveats của metric
   E003; `AnalysisProposal.limitations` giới hạn **8**. Replay schema cho lỗi
   `limitations / too_long`, khớp trace `grounding / excluded /
   invalid_analysis_schema`. Đây là lỗi tuân thủ contract của model, có yếu tố
   giao diện pipeline: source caveats do backend giữ lại bị model chép sang
   trường giới hạn của analysis, làm mất cả nhận định. Xem
   [specialist_common.py](../src/agents/specialist_common.py), dòng100–109,684–805.
2. Còn một lỗi khai báo bị lỗi schema trên che khuất: analysis chọn
   `evidence_ids=[E003]` (metric) nhưng khai `ratio(E001,E002)`. M5 chỉ tạo
   DynamicOperands từ **facts trong evidence_ids của analysis**, không từ toàn
   evidence bundle; do đó operands rỗng. Counterfactual chỉ rút limitations
   xuống8 vẫn gặp `dynamic_graph_bounds`. Hai facts có sẵn; không phải thiếu
   nguồn. Diễn giải metric đã tính phải dùng metric trực tiếp với operations
   rỗng, hoặc khai đầy đủ operands nếu thực sự cần phép tính mới.
3. M6 nhận duy nhất `kind=approved_metric`, content chỉ có tỷ lệ59,06%, không
   reasoning/interpretation. ACCEPT số liệu là đúng. Sai chiều “tài sản … tài
   trợ … nợ phải trả” **không nằm trong candidate này**; nó xuất hiện trong
   `response.trace.m7_lite.raw_output.segments[0].text`. Model tại M7 đã sinh
   thêm mệnh đề vượt finding ACCEPT, dù prompt cấm suy kết luận mới.
4. **Lỗi boundary M7:** `compose_lite()` chỉ kiểm tra claim IDs và
   `_numbers_supported()`, nên số59,06% đúng vẫn cho phép câu sai ngữ nghĩa.
   Replay guard trả `true`; trace `rejected_segments=[]`, `fallback=false`.
   [qa_lite.py](../src/outputs/qa_lite.py), dòng71–76,313–340,364–385;
   [financial_qa_pipeline.py](../src/api/financial_qa_pipeline.py), dòng683–719,
   gọi M7 sau ledger, dùng `LITE_INTEGRITY_RELEASE`, không chạy semantic lần nữa.
   Đây là giới hạn **đã được ghi nhận** trong
   [M7-LITE-02](m7-lite-02-natural-answer-release.md), không riêng adapter Qwen.

Partial phản ánh thiếu interpretation ACCEPT; thêm gap B không làm mệnh đề sai
trong đoạn đã phát hành trở thành hợp lệ. Không thể yêu cầu M6 bắt một mệnh đề
được sinh sau khi M6 đã hoàn tất.

## Case 2 — Proof còn nguyên, statement sai số

Trong `response.trace.financial_execution.candidates[0]`, M5 đã giữ đầy đủ:
`reasoning.calculation.operands` có2 source references/value/unit/scale/period;
`steps[0]` là `percentage_change(E001,E002)`, `across_periods`, kết quả
**26,713133494345…%**; có2 supporting evidences và citations. Replay
`execute_dynamic()` trả proof bằng đúng proof đã lưu. Handoff
[adapter.py](../src/verification/adapter.py), dòng90–105, giữ `reasoning` và
supporting evidence; không có mắt xích bị rơi tại M5→M6.

Model lại viết **26,8%** trong `raw_output.analyses[0].statement`; đây không phải
làm tròn đúng của26,713…%. `LiteFinancialValidator._analysis()` kiểm tra số trong
content với facts/kết quả tính và số làm tròn2 chữ số, phát `lite_unbound_number`;
`deterministic_state()` gặp fail thì ABSTAIN trước semantic. Xem
[lite_runtime.py](../src/verification/lite_runtime.py), dòng87–116,183–249.

**Điểm làm thiếu câu trả lời:** M5 giữ statement do model viết cho
`claim_type=reasoned_conclusion`, trong khi
[lite_orchestrator.py](../src/agents/lite_orchestrator.py), dòng483–492, đặt
`emit_derived=False`. Nhánh xuất thêm derived fact thuần tính toán ở
`specialist_common.py`, dòng780–798, vì thế không chạy. Statement sai bị loại kéo
theo việc không có **candidate độc lập cho kết quả đúng** để đưa vào ledger.
Hai fact vẫn ACCEPT; M7 chỉ nhận hai fact nên không được tự tính thêm phần trăm.
Không có `calculate_financial_metric` trong tool trace không có nghĩa Calculator
không chạy: dynamic arithmetic gọi trực tiếp `execute_dynamic()` trong M5 và
được giữ ở reasoning proof, không phải metric registry/tool request chuẩn.

## Vì sao semantic verifier không được gọi?

`m6_lite=true` chọn `LiteVerificationRuntime`: deterministic checks trước, chỉ
những claim đạt kiểm tra nhưng còn cần đánh giá nội dung mới vào `SEMANTIC`;
`pending` khác rỗng và có Gateway mới gọi một semantic batch
(`lite_runtime.py`, dòng315–319). Lite không chạy bộ Evidence/Logic Critic và
Judge legacy; đó là thiết kế đã ghi ở [M6-LITE-01](m6-lite-01-simplified-verification.md).

| Case | Đầu vào M6 | Vì sao pending=0 |
| --- | --- | --- |
| Q1 | Một approved metric | Analysis bị loại trước M6; mệnh đề sai của M7 chưa tồn tại |
| Q2 | Hai facts và một analysis | Facts được ACCEPT deterministic; analysis fail numeric binding nên ABSTAIN |

Không có bằng chứng hết budget, mất Gateway hay sai provider configuration:
max6calls/câu, thực tế3; deadline300s, thực tế54,09/42,79s; provider_errors rỗng.
Zero semantic calls là **đúng điều kiện routing**, nhưng chưa chứng minh chất lượng
semantic verifier. Không nên ép gọi critic cho mọi fact/phép tính hoặc dùng critic
để bỏ qua phép kiểm tra số đã fail.

## Replay offline và giới hạn bằng chứng

- Hai batch gốc replay M6 khớp quyết định đã lưu: Q1 ACCEPT1;
  Q2 ACCEPT2/ABSTAIN1, pending0 ở cả hai.
- Trên **bản sao chẩn đoán** Q1 với analysis đúng schema và dùng metric trực tiếp:
  pending1, không có provider nên INVESTIGATE/semantic_verification_required.
- Trên bản sao Q2, sửa riêng statement thành26,71%: pending1; xuất riêng
  `derived_fact` bằng `render_dynamic()` từ proof gốc: **ACCEPT deterministic**.
  Các control này chứng minh đường routing/phép tính có thể dùng lại, không phải
  kết quả live hay semantic verdict được phê duyệt.
- `_numbers_supported()` trên nguyên văn đoạn M7 sai ở Q1 trảtrue, tái hiện đúng
  giới hạn guard. Replay chặn socket; không thay input gốc hoặc ghi ledger gốc.

Evidence: `artifacts/evidence/QWEN-DIAG-01/replay.py`, `replay-summary.json`;
hash input Q1 bắt đầu `16b5b164`, Q2 `c23c8847`, kèm hash7 module liên quan.
Không kiểm tra lại PDF, OCR hay độ đúng độc lập của annual/comparative columns.
Page-level/uncertain/scope caveats của nguồn vẫn phải giữ; chúng chưa được chứng
minh là nguyên nhân của hai lỗi này. Model gây sai output; pipeline quyết định
phần nào được giữ/phát hành. Không quy mọi partial cho Qwen hoặc dữ liệu.

## Đề xuất một lần sửa có trọng tâm, chưa triển khai

| Ưu tiên | Thay đổi tổng quát nhỏ nhất | Ảnh hưởng |
| --- | --- | --- |
| Cần sửa trước khi coi câu trả lời tài chính là đáng tin | M7 chỉ tổ chức/hiển thị mệnh đề ACCEPT; dùng renderer/fallback hiện có cho numeric finding, không để M7 bổ sung interpretation chưa có claim. Interpretation cần được tạo ở M5 và đánh giá tại M6. Không khôi phục keyword/template gate hoặc thêm verifier ở M7. | Chặn tận nguồn việc phát minh quan hệ/nguyên nhân sau M6; áp dụng mọi model và chỉ tiêu. |
| Ưu tiên cùng đợt để phục hồi coverage | Cho nhánh Lite xuất derived fact độc lập từ proof đã thực thi, tái sử dụng `emit_derived`/`render_dynamic`; giữ analysis riêng và toàn bộ kiểm tra M6. Không sửa số sai trong statement rồi tự ACCEPT analysis. | Kết quả tính đúng không mất theo nhận định sai; áp dụng mọi dynamic operation có proof hợp lệ. Cần kiểm tra dedup/admission khi triển khai. |
| Cải thiện đầu vào semantic trong cùng phạm vi | Làm rõ ownership source caveats/model limitations và closure của operation inputs trong contract/prompt M5; metric có sẵn dùng trực tiếp. Ưu tiên schema/structured outputs của Gateway hiện có khi cần enforce envelope, không tăng cap tùy tiện hoặc cắt bỏ caveats nguồn. | Giảm analysis bị loại trước M6; không bảo đảm model luôn lập luận đúng và không thay vai trò verifier. |

Có thể chấp nhận trong prototype: trả phần đã xác minh kèm gap B; ABSTAIN số model
viết sai; zero semantic calls khi không có candidate hợp lệ; provenance chỉ page
level có caveat. **Không nên chấp nhận như output tài chính đúng:** quan hệ sai
được phát hành chỉ vì có số và citation đúng. Chưa có đủ evidence để so chất lượng
Qwen/Gemini hoặc đổ lỗi quantization/context/model size.

Phạm vi kiểm tra sau khi được duyệt: replay đúng hai traces này và control
semantic routing/derived calculation trên inputs khác, rồi một smoke nhỏ nếu
cần; không mở benchmark hoặc nhiều vòng FIX. Planning/diff checks bàn giao được
ghi ở receipt ignored; không thay runtime trong task này.

**Next action duy nhất:** Tech Lead duyệt phạm vi sửa boundary M5→M6→M7 nêu trên.
