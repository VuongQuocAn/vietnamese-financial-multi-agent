# CORE-PERIOD-01 — Comparative Period Verification

Ngày 11/11/2026 (Asia/Bangkok). Baseline `1fb2e39`; evidence riêng ignored
`artifacts/evidence/CORE-PERIOD-01/`. Không OCR/extraction hoặc sửa nguồn tài chính.

## Executive Summary

Sửa request binding và deterministic M6 để phân biệt ngày của một giá trị đơn lẻ
với các endpoints của phép so sánh. Replay nguyên hai derived claims của Q5-C:
`ABSTAIN reasoning_requested_period_mismatch` → `ACCEPT`; không sửa operands,
calculation hoặc Ledger. Fresh live sau đó xác định thêm output omission tại M7;
sửa tối thiểu để trình bày lại calculation đã ACCEPT. Kết quả ghi riêng bên dưới.

## Root Cause — request/claim/operand period

| Ranh giới | Nguyên nhân đã xác minh | Hệ quả |
| --- | --- | --- |
| Request → PlannerContext | `understand()` thấy năm 2025 và “đầu năm”, tự gán `2025-01-01` dù câu hỏi yêu cầu so sánh cuối năm. `_lite_context()` chọn filing, không gán ngày này; `FinancialQAPipeline.run()` lấy `bound.period or parsed.period`. Request lịch sử không truyền exact date. | Q5-C/C3-C mang một ngày duy nhất làm ràng buộc toàn batch. |
| Source → claim | Fact lấy kỳ canonical; approved metric lấy kỳ operand đại diện theo formula; `specialist_common` lấy `owner = sources[0]` cho derived/reasoned claim. | `claim.period` của analysis là owner của payload, không biểu diễn toàn bộ khoảng so sánh; không được dùng để quyết định kỳ mọi operand. |
| M6 derived | `_reasoning()` kiểm tra exact context với owner trước replay. Derived đi thẳng shared validator; Lite prose trước đây bỏ exact period trong premise batch. | Q5-C có đúng subtraction/percentage_change nhưng hai derived bị ABSTAIN; closing facts cũng context mismatch. |
| M6 operands | Canonical hydration, calculation replay, identity, unit/scale, period relation, reporting context và citations đã có. Executor dùng `(target-base)/base × 100`. | Không cần xóa period checks hoặc tạo verifier mới. Cần kiểm tra endpoint và hướng thay cho exact owner equality. |
| M7 | CORE-FLOW-01 `projection-q5-01/validation-summary.md` đã phát hành đúng 8,66%/14,35% với PDF5/6 khi proof được ACCEPT. Fresh L1/L2/L3 vẫn có đoạn dẫn claim nhưng bỏ kết quả, hoặc bị integrity guard loại và fallback chỉ giữ prose. | Period fix thuộc M6; output omission mới được chứng minh cần phục hồi display ở M7. |

Không đồng nhất traces: Q5-C-exact là câu Q5 tổng quát, context không có exact date;
hai reasoned conclusions cần semantic verifier, offline vẫn INVESTIGATE.
C3-C cũ không có dynamic calculation candidate để replay thành ACCEPT.
C1-C-retry1 có hai derived B02 đã ACCEPT, được dùng làm regression.
Không chạy lại EF-CORE-02 hoặc sửa evidence cũ.

## Before/After Validation Logic

Trước: cụm “đầu năm” → exact 01/01 → so `context.period == claim.period`;
nguồn đầu tiên tình cờ quyết định một derived comparison có được kiểm chứng không.

Sau: helper nhỏ đọc endpoints rõ trong câu hỏi (ngày cụ thể, đầu/cuối năm hoặc
các năm so sánh). Filing vẫn được chọn bởi document/snapshot/reporting year.
Lite pipeline không biến period suy ra từ câu hỏi comparative thành exact date.
M6 kiểm tra kỳ nguồn/claim với các endpoints, giữ exact-date check cho câu đơn kỳ;
đồng thời vẫn replay canonical sources và calculation độc lập.

Với proof `across_periods` hợp lệ, premise batch có thể không có một exact period;
company/document/snapshot/reporting scope giữ nguyên. Kỳ mỗi premise vẫn lấy từ
source canonical, nội dung premise phải khớp kỳ đó, source references/citations
phải khớp, và serialized computation phải bằng kết quả hydrate/replay độc lập.
Không thay toàn bộ period checks bằng `None`. Lite prose cũng giữ exact binding
của câu đơn kỳ; cross-period proof thiếu relation không được coi là calculation hợp lệ.

## Implementation Changes

- `question_understanding.py`: tái sử dụng normalization để tách comparison endpoints;
  giữ explicit date parsing và direct opening-date inference.
- `financial_qa_pipeline.py`: comparative Lite context giữ filing year, tránh implicit exact-date binding.
- `validators.py`: endpoint guards cho facts/reasoning; direct change operands cùng
  canonical indicator, target trước/base sau, replay vẫn kiểm tra kết quả và mẫu số.
- `lite_runtime.py`: giữ exact-date request cho premise validation; giữ period-relation guard.
- `qa_lite.py`: khi phần trình bày thiếu kết quả của across-period calculation đã
  ACCEPT, chèn nguyên public trace có sẵn, với claim/citations ban đầu. Không tính
  lại, đổi verdict, thêm verifier, retry hoặc suy luận từ số liệu.
- Targeted tests và CI thêm CORE-PERIOD; checker nhận Task ID mới.

Không đổi contracts, source facts, Ledger, EF-EG hoặc graph performance.

## Valid Comparative Cases

Nguồn BBS đã chuẩn bị, đã đối chiếu PDF trong EF-CORE-02/03; phép tính Decimal độc lập
từ canonical oracle, không dùng verdict M6 làm ground truth:

| Chỉ tiêu | Đầu kỳ 01/01/2025 | Cuối kỳ 31/12/2025 | Delta VND | Thay đổi |
| --- | ---: | ---: | ---: | ---: |
| Tổng tài sản, PDF5 | 291.306.659.104 | 266.086.680.765 | −25.219.978.339 | −8,66% |
| Tổng nợ phải trả, PDF6 | 183.476.510.255 | 157.146.559.558 | −26.329.950.697 | −14,35% |

Nợ/tài sản cuối kỳ 59,06%; B02 PDF7: revenue growth +26,71%, gross profit change
−10,84%, gross margin 7,21%. Source quality/provenance limitations lịch sử giữ nguyên.

## Negative Controls

Unit controls kiểm tra request đơn kỳ/comparative, valid replay, đảo hướng có tính lại
computation, sai mẫu số, company/snapshot/period/relation/citation và câu đơn kỳ.
Fixture dùng giá trị synthetic không bằng nhau để sai mẫu số thực sự khác kết quả đúng.
Không dùng synthetic PASS làm bằng chứng financial accuracy.

Real-source controls:20 trường hợp,4 ACCEPT/16 ABSTAIN; hai valid comparisons và hai closing facts được ACCEPT,14 biến thể sai và hai opening facts dưới request closing bị chặn. Sai mẫu số tính bằng closing, đảo hướng có tính lại proof, company/document/snapshot/period/citation đều bị chặn. `negative-controls.json` lưu nguyên verdict/reasons. Staged82 targeted PASS trước sửa M7; staged33 PASS sau sửa M7 (12 overlap), gồm test omission với Gateway giả và real Ledger admission. Ruff lint/format và planning/diff checks PASS. Engineering tests không thay research evaluation.

## Gemini Live Results

Một lượt fresh cho từng L1–L5, Graph ON, ledger riêng, Gateway/key rotation hiện có;
không dùng lại plan/answers của benchmark cũ. Raw `runs/L*.json` giữ answer M7,
M5 plan/Specialists/tool trace, calculation, M6 outcomes, periods, citations,
Gateway usage và provider attempts. Không log API keys.

| Case | Before | After | M6 verdict | M7 completeness | Kết luận |
| --- | --- | --- | --- | --- | --- |
| Q5/L1 | EF Q5-C: derived bị period mismatch; generic Q5-C-exact cần semantic | Fresh M6 có đúng cả hai phép change; final M7 offline replay giữ output provider cũ và phục hồi trace | 8 ACCEPT,1 ABSTAIN (qualitative limitation thiếu relation) | Đủ 4 số dư/2 delta/2%/59,06%; PDF5/6 sau replay | Numeric comparison đủ; runtime PARTIAL, chưa fresh lại toàn Q5 sau M7 patch |
| Explicit comparative/L2 | Exact opening date bó closing facts/derived | Một lượt đầu +đúng một lượt confirmation sau M7 patch | L2 đầu8 ACCEPT; final7 ACCEPT | Final fresh đủ tất cả quantities và PDF5/6 | Period verification sửa; numeric content đủ, generic coverage gap còn |
| C3/L3 | Trace cũ không có calculation candidate | Fresh M5 sinh hai proofs; M6 ACCEPT; final M7 offline replay phục hồi display | 8 ACCEPT | Đủ delta/%/số dư/59,06%, giới hạn thanh khoản và PDF5/6 sau replay | Numeric/reasoning đủ trong replay; runtime PARTIAL, chưa fresh lại toàn C3 sau M7 patch |
| Direct fact/L4 | Exact-date guard cần giữ | Fresh đúng closing assets | 2 ACCEPT | 266.086.680.765 VND tại31/12/2025, PDF5; không tráo opening | CORRECT_WITH_CAVEAT; final M7 replay không cần bổ sung |
| B02 cross-year/L5 | C1-C-retry1 đã ACCEPT | Fresh đúng revenue/gross-profit proof, final M7 replay phục hồi gross-profit display | 6 ACCEPT | +94.967.158.941/+26,71%; −3.949.890.713/−10,84%, PDF7 | Numeric regression giữ; runtime PARTIAL do generic gap |

Không gọi cả năm case PASS chỉ vì tools đúng. Năm fresh đầu dùng final M6 nhưng M7 trước display patch. Sau patch: offline replay đúng saved provider output cho cả năm, **0 provider calls**, và một fresh L2 confirmation trên cả M6/M7 cuối. Không gán replay thành fresh E2E. Tổng6 fresh E2E/25 Gateway invocations/25 provider attempts;111680 known tokens (100782 input/10898 output),1 unknown invocation/1 failure ở L2 đầu. Không suy billing cost từ known token subtotal.46fact/593citation occurrences đối chiếu oracle/canonical metadata0mismatch; PDF nguồn giữ digest. Đây là kiểm tra consistency với nguồn đã duyệt, không tái chứng nhận OCR accuracy.

Sau confirmation chỉ hoàn thiện trace để đếm riêng đoạn provider với đoạn display
được phục hồi, và giữ chặn explicit API period nằm ngoài comparison endpoints.
14 targeted controls cuối PASS; các câu live không truyền explicit API period này.
Không chạy thêm Gemini cho hai điều chỉnh đó; hashes từng runtime live lưu trong raw.

Plan L1/L2/L3 và confirmation: liquidity_and_leverage, Graph ON; financial facts6/evidence sources4/approved metric1/graph context5 mỗi lượt. L4: cùng Specialist, Graph OFF, fact1/source1. L5: profitability, Graph ON, cùng counts như comparative. Dynamic operations và periods lưu nguyên trong candidates; tool trace giữ riêng trong raw M5.

## M6 Decisions and M7 Answers

- `L1`: ACCEPT=8, ABSTAIN=1; 23006 known tokens; raw `L1.json`.
- `L2-confirmation`: ACCEPT=7; 20842 known tokens; raw `L2-confirmation.json`.
- `L2`: ACCEPT=8; 22395 known tokens; raw `L2.json`.
- `L3`: ACCEPT=8; 20228 known tokens; raw `L3.json`.
- `L4`: ACCEPT=2; 6222 known tokens; raw `L4.json`.
- `L5`: ACCEPT=6; 18987 known tokens; raw `L5.json`.

Ở L1/L3, provider từng viết số đúng nhưng đoạn bị numeric integrity loại (độ lớn dương của negative delta VND hoặc bindings); ở L2, prose chỉ nói “đã tính” không công bố result. Cả hai nhánh fallback trước đây có thể giữ accepted prose mà bỏ calculation. Không nới numeric guard: final presentation chỉ chèn public calculation trace đã ACCEPT với citations của claim đó.

Final fresh L2 — M7 nguyên văn:

```text
Tính đến cuối kỳ ngày 31/12/2025, tỷ lệ nợ phải trả trên tổng tài sản của BBS đạt 59,06%. [1][2]

Tổng tài sản (kỳ 2025-12-31) − Tổng tài sản (kỳ 2025-01-01): -25.219.978.339,00 VND. (Tổng tài sản (kỳ 2025-12-31) − Tổng tài sản (kỳ 2025-01-01)) / Tổng tài sản (kỳ 2025-01-01) × 100: -8,66 %. [2]

Tổng nợ phải trả (kỳ 2025-12-31) − Tổng nợ phải trả (kỳ 2025-01-01): -26.329.950.697,00 VND. (Tổng nợ phải trả (kỳ 2025-12-31) − Tổng nợ phải trả (kỳ 2025-01-01)) / Tổng nợ phải trả (kỳ 2025-01-01) × 100: -14,35 %. [1]

Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. [1]

Tổng nợ phải trả tại ngày 2025-01-01 là 183.476.510.255 VND. [1]

Tổng tài sản tại ngày 2025-01-01 là 291.306.659.104 VND. [2]

Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. [2]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

Q5/C3 final replay có cùng hai trace −25.219.978.339/−8,66% và −26.329.950.697/−14,35%; full answers giữ tại `m7-final-replay.json`, riêng raw provider/M7 trước patch tại `runs/L1.json`, `runs/L3.json`. Câu trả lời còn generic verification gap, không đổi thành full-answer PASS bằng hậu xử lý.


## Remaining Limitations

Đây là policy bounded cho periods có trong câu hỏi và canonical sources đã chọn;
không phải period engine, không hỗ trợ accounting comparability liên báo cáo mới.
Các phép change hai direct operands dùng convention target mới hơn/base cũ hơn.
Không suy diễn nguyên nhân, cấu trúc chi tiết hoặc thanh khoản từ tổng tài sản/nợ.
Generic M5 coverage, semantic/provider errors và M7 completeness phải chấm riêng. L1 còn một qualitative limitation bị ABSTAIN do nhiều kỳ nhưng không có explicit relation; không dùng để phát hành kết luận. Endpoint inference chỉ hỗ trợ những patterns rõ đã nêu; chưa hỗ trợ mọi cách diễn đạt kỳ tương đối hoặc so sánh ngược chiều thời gian. Các case Q5/C3 cuối chỉ có M7 replay sau presentation patch, không thêm nhiều live runs để làm đẹp kết quả.

## CI Evidence

Implementation [30710fed39abb1c84e712690d94180037241ac66](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/30710fed39abb1c84e712690d94180037241ac66) đã push main; [CI 42990278592](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42990278592) **SUCCESS**, head SHA được đối chiếu chính xác. Python 3.12 targeted smoke **231 PASS**; Web/full regression SKIPPED theo workflow. Ruff/planning/diff PASS; local staged82 trước M7 +33 final M7 (12 overlap), và14 final controls sau guard/trace metadata adjustment. Không dùng CI thay research evaluation. Status **REVIEW**; next action: Tech Lead review CORE-PERIOD-01, giữ các giới hạn đã ghi.
