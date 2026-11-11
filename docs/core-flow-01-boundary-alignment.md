# CORE-FLOW-01 — Boundary Alignment

**REVIEW / NOT READY**. Đã triển khai các sửa ranh giới, có bằng chứng live về
semantic planning, Calculator, interpretations, M6, Ledger và follow-up. Chưa đạt
nghiệm thu toàn bộ: Q5 từng trả sai tỷ lệ biến động trong câu trả lời; bản sửa cuối
đã qua controls offline nhưng lần live xác minh bị HTTP429 chặn. Không coi offline
hay source audit PASS là bằng chứng chất lượng câu trả lời tài chính.

Baseline `a92bc8f`. Implementation SHA là commit triển khai chứa báo cáo này;
SHA đầy đủ, remote và kết quả CI đúng SHA lưu trong receipt local
`artifacts/evidence/CORE-FLOW-01/receipt.json` sau commit, đồng thời báo trong bàn giao.
CI chưa chạy tại thời điểm viết commit. Không tự DONE; E2E-LITE-01 giữ REVIEW vì
chưa có xác nhận nghiệm thu riêng.

## Nguyên nhân và sửa đổi

- M5 ưu tiên Gemini hiểu ý định và chọn Specialists/metric handles; không thêm alias
  riêng cho tám câu. Inventory lấy các kỳ so sánh trong cùng filing/snapshot;
  bỏ trần payload 7.500/8.000 ký tự gây fallback âm thầm, giữ giới hạn 48.000.
- Specialists nhận schema analyses hiện có, facts/metrics, reasoning và limits;
  operations lấy đúng fact operands dù evidence có metric. M6 replay cùng tập fact
  operands, vẫn kiểm tra riêng toàn bộ premises/metrics. Không thêm agent.
- M6 bỏ literal display-label gate; canonical identity/value/unit/scale/citations
  vẫn qua validator và source builder. Giữ ý nghĩa multi-period khi tách batch thành
  từng claim; năm filing không được biến thành ràng buộc mọi supporting operand.
  Semantic verdict chấp nhận object verdicts hoặc array, mỗi phần tử vẫn kiểm tra
  schema, exact claim ID và tính duy nhất; không tự ACCEPT verdict thiếu/sai.
- Pipeline sở hữu retrieval và integrity trước M7 trong `api/claim_selection.py`.
  Current-request ACCEPT IDs đi trực tiếp tới M7; cached lookup còn lọc context và
  relevance ở pipeline. Bỏ M7 keyword/coverage/conflict/operand-year re-verification.
  Giữ company/document/snapshot, ACCEPT, citation ownership và reporting-scope checks.
- Context dùng reporting_year đã khai báo của tài liệu được chọn khi không có năm;
  năm báo cáo khác exact balance-sheet date. Conversation giữ câu hỏi follow-up và
  tham chiếu duy nhất tới topic, verified IDs và citations. Không tự kết luận tài chính.
- M7 tổng hợp tự nhiên, có thể tóm tắt mà không liệt kê mọi claim. Fallback giữ claim
  ACCEPT; deterministic chủ động không báo provider failure. Giữ kiểm tra số/đơn vị
  và citations của câu sinh ra; chuẩn hóa `percent` sang `%` khi đối chiếu hiển thị.
- Gateway thêm tối đa một retry cho HTTP429/503, cùng call/deadline budget, tôn trọng
  Retry-After ngắn và ghi từng attempt. Không đổi model hoặc dùng API trả phí.

## Lỗi mới phát hiện trong live và sửa cuối

Q5 trong `live-final` diễn giải biểu thức `(đầu kỳ-cuối kỳ)/cuối kỳ` thành mức giảm
trong năm: 9,48% tài sản và 16,76% nợ, trong khi mức giảm tính theo đầu kỳ lần lượt
là 8,66% và 14,35%. Đây là **INCORRECT**, không phải provider error. M6 đã xác minh
biểu thức số học nhưng M7 đổi nghĩa mẫu số khi paraphrase; numeric matching không
phát hiện được sai nghĩa này.

Bản sửa cuối ngừng tự sinh thêm standalone derived candidate cho mỗi interpretation
ở Lite; operations/proof vẫn nằm nguyên trong interpretation để M6 kiểm chứng.
Đã bổ sung chỉ dẫn chiều percentage_change và bảo toàn kỳ/mẫu số cho M7. Legacy
giữ tùy chọn emit_derived mặc định. Không thêm một semantic verifier ở M7.
Controls chứng minh interpretation có operations được giữ mà không phát hành
candidate phép tính trùng. **Chưa xác minh được sửa Q5 bằng Gemini thành công**;
không tuyên bố rủi ro paraphrase sai nghĩa đã được giải quyết hoàn toàn.

Q4 có một semantic response là array hợp lệ nhưng bị bỏ vì thiếu wrapper verdicts.
Bản sửa parser đã có control array + exact IDs và giữ kiểm chứng nội dung tại M6;
lần live sau sửa cũng bị429, nên chưa có live confirmation cho sửa parser này.

## Tám case trước/sau

Giữ nguyên questions trong `scripts/evaluate_e2e_lite.py`; không hardcode kết quả
trong runtime. `live-final` là một lần fresh đủ tám case/chín lượt trên runtime
đóng băng **trước các sửa cuối Q5/envelope**. `live-targeted-final` là lần fresh
xác minh lại sáu lượt bị ảnh hưởng, tất cả calls thực tế gặp429 tại Supervisor.
Không ghép artifacts thành một lần end-to-end PASS.

| Case | E2E-LITE-01 offline | Live đủ bộ trước sửa cuối | Lượt xác minh sửa cuối |
| --- | --- | --- | --- |
| Q1 | CORRECT_WITH_CAVEAT | CORRECT_WITH_CAVEAT: đúng doanh thu, có nguồn | Không chạy lại phần không bị lỗi |
| Q2 | PARTIAL | CORRECT_WITH_CAVEAT: tăng 26,71%, Calculator thật | Không chạy lại phần không bị lỗi |
| Q3 | PARTIAL | CORRECT_WITH_CAVEAT: 59,06% và ý nghĩa có M6 semantic ACCEPT | Không chạy lại phần không bị lỗi |
| Q4 | PARTIAL | PARTIAL: bốn số đúng, thiếu kết luận biên gộp thu hẹp; semantic array bị bỏ | PARTIAL do429; parser fix chưa live thành công |
| Q5 | PARTIAL | INCORRECT: đổi mẫu số khi diễn đạt mức giảm | PARTIAL do429; sửa candidate trùng chưa live thành công |
| Q6 | UNJUSTIFIED_REFUSAL | CORRECT_WITH_CAVEAT: hai Specialists, sinh lời + cơ cấu vốn có nguồn | TECHNICAL_FAILURE do429, không tái hiện bản sửa cuối |
| Q7 | UNJUSTIFIED_REFUSAL | PARTIAL: resolve kỳ2025, semantic verifier gặp503, trả phần số đúng | TECHNICAL_FAILURE do429, thiếu kết luận nhân quả verified |
| Q8 | UNJUSTIFIED_REFUSAL | CORRECT_WITH_CAVEAT về nội dung: hiểu tham chiếu, không kết luận mất khả năng thanh toán; M7 lỗi503 nên fallback dài | PARTIAL do429, chỉ giữ số liệu từ lượt1 |

Q8 trong `live-repaired` đã có answer tự nhiên, semantic ACCEPT và không provider
error ở lượt2; đây là bằng chứng riêng của revision trước, không phải PASS của
revision cuối. Q5 `live-repaired` có interpretations ACCEPT nhưng M7 gặp503.

## Engineering và integrity

Các targeted controls đã chạy cho semantic routing không exact keyword, Calculator,
multi-agent collection, mixed fact/metric operations, preservation qua adapter,
label/identity, Ledger tampering/reload, current IDs, comparative metric, context,
conversation, M7 summary/numeric/citation integrity và bounded retry429/503.
29 tests trên exact staged runtime cuối PASS; nhóm75 staged tests trước refinement
cũng PASS (có overlap, không cộng thành104 tests độc lập). Ruff lint toàn bản stage
PASS, format649files PASS; planning127tasks stage/128tasks local và diff check PASS.
Kết quả được ghi trong receipt; không chạy full1.000+
tests, OCR, extraction hoặc benchmark mới. CI chạy nhóm offline trọng tâm có thêm
test_core_flow, Web không đổi.

Source/provenance audit: 205 + 234 + 273 + 71 = 783 checks lặp giữa các revisions,
0 mismatch của canonical scalar/approved metric/citation bindings, 0 current ACCEPT
IDs bị mất trước M7. **Không phải783 câu hỏi độc lập hoặc0 lỗi câu trả lời**; sai
nghĩa phần trăm Q5 nêu trên vẫn tồn tại trong câu trả lời cũ. Các source datasets/
artifacts cũ được hash trước/sau từng run, không thay đổi. `integrity.json` của các
run đang phát triển có false do source code được sửa sau lúc freeze; `audit.json`
phân biệt intentional src changes với protected input data unchanged. Run cuối
chỉ bảo vệ input data và đóng băng effective runtime sources riêng.

Runtime đánh giá = Git archive baseline + task overlay; shared specialist_common
chỉ áp dụng task delta, không lấy các local prompt edits có trước. Commit chỉ stage
task delta; giữ các local edits và task GEN/CHAT ngoài scope. Planning local có128
tasks, bản stage loại các planning edits có trước có127 tasks; mỗi bản kiểm tra
theo registry tương ứng, không tự nghiệm thu milestone ngoài task.

## Gemini thực tế

Model `gemini-3.5-flash-lite`, tất cả qua Gateway. Calls dưới đây là attempts thực
tế, gồm503/429 và retry; usage lỗi không biết được giữ unknown, không coi là0 tokens.

| Run | Calls | Known tokens | Unknown usage | HTTP503 | HTTP429 |
| --- | ---: | ---: | ---: | ---: | ---: |
| live-initial | 25 | 44469 | 3 | 3 | 0 |
| live-repaired | 29 | 59877 | 6 | 6 | 0 |
| live-final | 46 | 77893 | 13 | 12 | 1 |
| live-targeted-final | 6 | 0 | 6 | 0 | 6 |

Tổng **106 attempts, 182.239 known tokens, 28 unknown-usage calls**, 21 HTTP503 và7 HTTP429.
Tổng thời gian provider attempts358,686giây, median3,023giây; đây là tổng calls,
không phải thời gian toàn task. Pipeline đủ bộ Q1→Q8.2 lần lượt26,217/36,211/
47,088/48,607/38,461/88,385/49,317/52,679/44,999giây (bao gồm tools/Ledger).
Không live thêm sau429 liên tiếp. Không xác nhận được429 là quota ngày hay rate window.

## Trace và câu trả lời nguyên văn

Mọi run có `freeze.json`, `provider-events.json`, `results.json`, Ledger riêng và `audit.json`
dưới `artifacts/evidence/CORE-FLOW-01/` (local ignored). Mỗi result giữ request, plan,
Specialists/tools, candidates, M6 reasons, exact Ledger IDs, M7 received/used,
source citations và conversation resolution. Không đưa raw traces/dataset vào Git.

Bảng sau thuộc lần đủ bộ `live-final`, để đối chiếu trước/sau; không gán cho revision cuối.

| Lượt | Specialists | Tools thực thi | M6 decisions | Ledger admitted | M7 nhận/dùng |
| --- | --- | --- | --- | ---: | ---: |
| Q1 | profitability | get_financial_fact×1, get_evidence_sources×1 | {'ACCEPT': 2} | 2 | 2/2 |
| Q2 | profitability | get_financial_fact×4, get_evidence_sources×2, calculate_financial_metric×1 | {'ACCEPT': 3} | 3 | 3/3 |
| Q3 | liquidity_and_leverage | get_financial_fact×4, get_evidence_sources×2, calculate_financial_metric×1 | {'ACCEPT': 2} | 2 | 2/2 |
| Q4 | profitability | get_financial_fact×8, get_evidence_sources×4, calculate_financial_metric×2 | {'INVESTIGATE': 1, 'ACCEPT': 6} | 6 | 6/6 |
| Q5 | liquidity_and_leverage | get_financial_fact×10, get_evidence_sources×8, calculate_financial_metric×1 | {'ACCEPT': 3} | 3 | 3/3 |
| Q6 | profitability, liquidity_and_leverage | get_financial_fact×22, get_evidence_sources×16, calculate_financial_metric×3 | {'ACCEPT': 24} | 24 | 24/18 |
| Q7 | profitability | get_financial_fact×10, get_evidence_sources×6, calculate_financial_metric×2 | {'INVESTIGATE': 2, 'ACCEPT': 8} | 8 | 8/3 |
| Q8.1 | liquidity_and_leverage | get_financial_fact×4, get_evidence_sources×2, calculate_financial_metric×1 | {'ACCEPT': 2} | 2 | 2/2 |
| Q8.2 | liquidity_and_leverage | get_financial_fact×4, get_evidence_sources×2, calculate_financial_metric×1 | {'ACCEPT': 4} | 4 | 5/5 |

### Live đủ bộ trước sửa cuối — giữ cả câu trả lời sai Q5

<details>
<summary>Q1</summary>

Doanh thu thuần của BBS năm 2025 là bao nhiêu?

```text
Doanh thu thuần của BBS trong năm 2025 đạt 450.474.531.227 VND theo số liệu được ghi nhận, tuy nhiên số liệu này chưa được kiểm chứng độc lập trong phạm vi dữ liệu hiện tại và bằng chứng lưu trữ còn có những giới hạn nhất định. [1]

Lưu ý: Số liệu chưa được kiểm chứng độc lập trong phạm vi dữ liệu này.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Giới hạn: Số liệu chưa được kiểm chứng độc lập trong phạm vi dữ liệu này.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q2</summary>

Doanh thu thuần của BBS năm 2025 tăng hay giảm bao nhiêu phần trăm so với năm 2024?

```text
Năm 2025, doanh thu thuần của BBS đạt 450.474.531.227 VND, tăng so với mức 355.507.372.286 VND của năm 2024. [1]

Tăng trưởng doanh thu kỳ 2025 đạt 26,71% với bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh. [1]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q3</summary>

Tỷ lệ nợ phải trả trên tổng tài sản của BBS tại ngày 31/12/2025 là bao nhiêu? Diễn giải ý nghĩa của tỷ lệ đó.

```text
Tại ngày 31/12/2025, tỷ lệ nợ phải trả trên tổng tài sản của BBS là 59,06%. Tỷ lệ này thể hiện mức độ tài trợ tài sản của doanh nghiệp thông qua các khoản nợ vay và nghĩa vụ phải trả so với tổng nguồn vốn đang quản lý. Tuy nhiên, chỉ số này chỉ phản ánh tương quan tĩnh tại thời điểm 31/12/2025 và không bao gồm biến động trong kỳ hay tính chất đáo hạn chi tiết của các khoản nợ. [1][2]

Lưu ý: Chỉ số này phản ánh tương quan tĩnh tại thời điểm 31/12/2025 và không bao gồm biến động trong kỳ hay tính chất đáo hạn chi tiết của các khoản nợ.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Giới hạn: Chỉ số này phản ánh tương quan tĩnh tại thời điểm 31/12/2025 và không bao gồm biến động trong kỳ hay tính chất đáo hạn chi tiết của các khoản nợ.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q4</summary>

So sánh doanh thu thuần và lợi nhuận gộp của BBS giữa năm 2024 và 2025. Kết quả cho thấy điều gì?

```text
Năm 2024, doanh thu thuần của BBS đạt 355.507.372.286 VND và lợi nhuận gộp đạt 36.432.410.381 VND. [1]

Sang năm 2025, doanh thu thuần tăng lên 450.474.531.227 VND, tương ứng mức tăng trưởng doanh thu đạt 26,71%. [1]

Tuy nhiên, lợi nhuận gộp trong năm 2025 lại giảm xuống còn 32.482.519.668 VND, với biên lợi nhuận gộp kỳ này đạt 7,21%. [1]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q5</summary>

Phân tích tình hình tổng tài sản và nợ phải trả của BBS năm 2025 dựa trên các số liệu đã có. Có thể kết luận gì và chưa thể kết luận gì?

```text
Trong năm 2025, tổng tài sản của BBS ghi nhận sự biến động từ 291.306.659.104 VND vào đầu năm xuống còn 266.086.680.765 VND vào cuối năm (giảm 9,48%). Tổng nợ phải trả cũng biến động từ 183.476.510.255 VND xuống còn 157.146.559.558 VND (giảm 16,76%). [1][2]

Tuy nhiên, các dữ liệu hiện tại mới chỉ phản ánh sự thay đổi về mặt số học giữa hai thời điểm đầu và cuối năm mà chưa rõ nguyên nhân cụ thể dẫn đến các biến động này. Đồng thời, chưa đủ cơ sở để khẳng định về tính an toàn hay rủi ro tài chính tổng thể nếu không có thêm thông tin về cơ cấu tài sản ngắn/dài hạn và khả năng thanh khoản chi tiết. [1][2]

Lưu ý: Chỉ quan sát được sự thay đổi về mặt số học giữa hai thời điểm đầu và cuối năm mà chưa rõ nguyên nhân cụ thể dẫn đến các biến động này.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Chưa đủ cơ sở để khẳng định về tính an toàn hay rủi ro tài chính tổng thể nếu không có thêm thông tin về cơ cấu tài sản ngắn/dài hạn và khả năng thanh khoản chi tiết.

Giới hạn: Chỉ quan sát được sự thay đổi về mặt số học giữa hai thời điểm đầu và cuối năm mà chưa rõ nguyên nhân cụ thể dẫn đến các biến động này.; Chưa đủ cơ sở để khẳng định về tính an toàn hay rủi ro tài chính tổng thể nếu không có thêm thông tin về cơ cấu tài sản ngắn/dài hạn và khả năng thanh khoản chi tiết.

Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q6</summary>

Dựa trên những dữ liệu hiện có, hãy nhận xét tình hình tài chính của BBS năm 2025, kết hợp khả năng sinh lời và cơ cấu nguồn vốn.

```text
Về khả năng sinh lời và kết quả kinh doanh năm 2025, doanh nghiệp đạt doanh thu thuần 450.474.531.227 VND (tăng 26,71% so với năm 2024), lợi nhuận gộp ghi nhận 32.482.519.668 VND với biên lợi nhuận gộp đạt 7,21%, đồng thời lợi nhuận trước thuế đạt 9.113.447.433 VND và lợi nhuận sau thuế đạt 7.249.557.946 VND. [1]

Về cơ cấu nguồn vốn và quy mô tài sản trong năm 2025, tổng tài sản tại thời điểm đầu kỳ (01-01-2025) ghi nhận 291.306.659.104 VND và giảm xuống 266.086.680.765 VND vào cuối kỳ (31-12-2025). Trong đó, tổng nợ phải trả biến động từ 183.476.510.255 VND đầu kỳ xuống 157.146.559.558 VND cuối kỳ, còn vốn chủ sở hữu tăng nhẹ từ 107.830.148.849 VND lên 108.940.121.207 VND. Tại thời điểm cuối năm 2025, tỷ lệ nợ phải trả trên tổng tài sản đạt 59,06%. [2][3]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Chỉ số liệu tại các thời điểm đầu kỳ và cuối kỳ, chưa phản ánh diễn biến trong suốt cả năm.; Chỉ dựa trên số liệu tuyệt đối và tỷ lệ tăng trưởng doanh thu được cung cấp, chưa phản ánh đầy đủ toàn bộ các yếu tố chi phí cấu thành.; Chưa có thông tin định tính về nguyên nhân biến động giá vốn hàng bán.; Chỉ phản ánh một lát cắt tại thời điểm cuối năm 2025, chưa đủ cơ sở để đánh giá xu hướng dài hạn nếu không có dữ liệu các năm trước.

Giới hạn: Chỉ số liệu tại các thời điểm đầu kỳ và cuối kỳ, chưa phản ánh diễn biến trong suốt cả năm.; Chỉ dựa trên số liệu tuyệt đối và tỷ lệ tăng trưởng doanh thu được cung cấp, chưa phản ánh đầy đủ toàn bộ các yếu tố chi phí cấu thành.; Chưa có thông tin định tính về nguyên nhân biến động giá vốn hàng bán.; Chỉ phản ánh một lát cắt tại thời điểm cuối năm 2025, chưa đủ cơ sở để đánh giá xu hướng dài hạn nếu không có dữ liệu các năm trước.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[3] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q7</summary>

Doanh thu BBS tăng có phải vì doanh nghiệp quản lý chi phí hiệu quả hơn không?

```text
Trong kỳ 2025, doanh thu thuần của BBS đạt 450.474.531.227 VND, tăng trưởng 26,71% so với mức 355.507.372.286 VND của kỳ 2024. [1]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q8.1</summary>

Tỷ lệ nợ trên tổng tài sản của BBS năm 2025 là bao nhiêu?

```text
Tại ngày 31 tháng 12 năm 2025, tỷ lệ nợ phải trả trên tổng tài sản của BBS được ghi nhận ở mức 59,06%. Tuy nhiên, chỉ số này phản ánh cơ cấu nguồn vốn tại thời điểm khóa sổ và chưa phản ánh diễn biến trong suốt cả năm. [1][2]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Chỉ số này phản ánh cơ cấu nguồn vốn tại thời điểm khóa sổ, chưa phản ánh diễn biến trong suốt cả năm.

Giới hạn: Chỉ số này phản ánh cơ cấu nguồn vốn tại thời điểm khóa sổ, chưa phản ánh diễn biến trong suốt cả năm.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q8.2</summary>

Vậy tỷ lệ đó có chứng minh doanh nghiệp đang mất khả năng thanh toán không?

```text
Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. [1]

Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. [2]

Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%. [2][1]

Tỷ lệ nợ phải trả trên tổng tài sản năm 2025 ở mức quan sát cho thấy phần lớn tài sản của doanh nghiệp được tài trợ bởi các khoản nợ phải trả, tuy nhiên chỉ số này phản ánh cấu trúc nguồn vốn chứ không đủ cơ sở để khẳng định doanh nghiệp đang mất khả năng thanh toán hay không. Giả định: Chỉ số nợ phải trả trên tổng tài sản phản ánh cơ cấu nguồn vốn tại thời điểm 2025-12-31 Giới hạn: Chưa xem xét cơ cấu kỳ hạn của các khoản nợ (ngắn hạn so với dài hạn) Giới hạn: Chưa xem xét tính thanh khoản của tài sản ngắn hạn hoặc dòng tiền thực tế Giới hạn: Không có thông tin về tài sản lưu động và các khoản nợ đến hạn thanh toán trong kỳ [2][1]

Tỷ lệ nợ phải trả trên tổng tài sản năm 2025 được ghi nhận ở mức 59.06%. Giới hạn: Chỉ số này phản ánh cơ cấu nguồn vốn tại thời điểm khóa sổ, chưa phản ánh diễn biến trong suốt cả năm. [2][1]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Chưa xem xét cơ cấu kỳ hạn của các khoản nợ (ngắn hạn so với dài hạn); Chưa xem xét tính thanh khoản của tài sản ngắn hạn hoặc dòng tiền thực tế; Chỉ số nợ phải trả trên tổng tài sản phản ánh cơ cấu nguồn vốn tại thời điểm 2025-12-31; Không có thông tin về tài sản lưu động và các khoản nợ đến hạn thanh toán trong kỳ; Chỉ số này phản ánh cơ cấu nguồn vốn tại thời điểm khóa sổ, chưa phản ánh diễn biến trong suốt cả năm.

Giới hạn: Chưa xem xét cơ cấu kỳ hạn của các khoản nợ (ngắn hạn so với dài hạn); Chưa xem xét tính thanh khoản của tài sản ngắn hạn hoặc dòng tiền thực tế; Không có thông tin về tài sản lưu động và các khoản nợ đến hạn thanh toán trong kỳ; Chỉ số này phản ánh cơ cấu nguồn vốn tại thời điểm khóa sổ, chưa phản ánh diễn biến trong suốt cả năm.

Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

### Fresh live xác minh sửa cuối — provider429

<details>
<summary>Q4</summary>

So sánh doanh thu thuần và lợi nhuận gộp của BBS giữa năm 2024 và 2025. Kết quả cho thấy điều gì?

```text
Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. [1]

Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1]

Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. [1]

Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND. [1]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Một bước xử lý chưa hoàn tất; chỉ trình bày phần đã xác minh.

Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q5</summary>

Phân tích tình hình tổng tài sản và nợ phải trả của BBS năm 2025 dựa trên các số liệu đã có. Có thể kết luận gì và chưa thể kết luận gì?

```text
Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. [1]

Tổng tài sản tại ngày 2025-01-01 là 291.306.659.104 VND. [1]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Một bước xử lý chưa hoàn tất; chỉ trình bày phần đã xác minh.

Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q6</summary>

Dựa trên những dữ liệu hiện có, hãy nhận xét tình hình tài chính của BBS năm 2025, kết hợp khả năng sinh lời và cơ cấu nguồn vốn.

```text
Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
```

</details>

<details>
<summary>Q7</summary>

Doanh thu BBS tăng có phải vì doanh nghiệp quản lý chi phí hiệu quả hơn không?

```text
Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
```

</details>

<details>
<summary>Q8.1</summary>

Tỷ lệ nợ trên tổng tài sản của BBS năm 2025 là bao nhiêu?

```text
Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. [1]

Tổng tài sản tại ngày 2025-01-01 là 291.306.659.104 VND. [1]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Một bước xử lý chưa hoàn tất; chỉ trình bày phần đã xác minh.

Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

<details>
<summary>Q8.2</summary>

Vậy tỷ lệ đó có chứng minh doanh nghiệp đang mất khả năng thanh toán không?

```text
Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. [1]

Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%. [1][2]

Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. [2]

Tổng tài sản tại ngày 2025-01-01 là 291.306.659.104 VND. [2]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Một bước xử lý chưa hoàn tất; chỉ trình bày phần đã xác minh.

Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

</details>

## Phần chờ nghiệm thu

NOT READY cho acceptance toàn bộ. Engineering changes có bằng chứng targeted và
live riêng từng tính năng, nhưng sửa Q5 cuối chưa live thành công, Q4 chưa xác nhận
semantic array bằng live, Q7 chưa có câu trả lời nhân quả verified thành công trong
lần đủ bộ. Provider503/429 là blocker validation riêng; không dùng nó để xóa lỗi
Q5 đã quan sát. Source reporting_scope/page-level caveats và rủi ro paraphrase của
M7 giữ nguyên. Không tuyên bố independent full-PDF financial accuracy.

Next action: chạy lại live Q4–Q8 trên implementation commit khi provider hết429,
đặc biệt đối chiếu mẫu số/chiều biến động Q5 trước khi Tech Lead nghiệm thu.
