# M7-LITE-02 — Natural Answer Release

Ngày 11/11/2026. **REVIEW**, chờ Tech Lead nghiệm thu; M7-LITE-01 vẫn REVIEW.
Baseline Git `c102b8956356af6562c2558729a0e7ff373b09f3`.
Owner đã duyệt **đúng một commit/push** sau khi kiểm tra diff và ba đoạn L08.
Implementation là commit chứa thay đổi `src/outputs/qa_lite.py` của task này; SHA và CI
được đối chiếu sau push trong receipt local `artifacts/evidence/M7-LITE-02/commit-receipt.json`.
Runtime hashes được ghim trong `artifacts/evidence/M7-LITE-02/live-results.json` (local, ignored).

## Thay đổi đúng phạm vi

- Xóa `_same_proposition()` và `_supported_text()`, không còn so câu, keyword,
  template hoặc cấu trúc mệnh đề với nguyên văn claims. Không thêm semantic gate/verifier.
- Giữ selection từ Ledger ACCEPT, scope và source integrity. Mỗi segment phải có
  claim IDs tồn tại trong selected set; số chỉ được đối chiếu với **claims đoạn đó dẫn**.
- `_numbers_supported()` kiểm tra Decimal, dấu, số/đơn vị và làm tròn; hỗ trợ cách viết
  tỷ/triệu/nghìn. Không tự tính thêm chỉ tiêu. Không dùng số của claim không được dẫn
  để hợp thức hóa một đoạn. Khác cách diễn đạt không kích hoạt fallback.
- Fallback giữ phần khác hợp lệ và phục hồi findings bị output lỗi/bỏ sót. Các lý do
  là JSON/segment hỏng, ID sai, số/đơn vị không được hỗ trợ, provider lỗi hoặc budget.
- Gộp reference theo `(document_id, snapshot_id, pdf_page)`; vị trí không có page
  vẫn giữ identity riêng. Public locator hạ xuống page, không mạo nhận một cell/anchor
  đại diện cho mọi evidence trên trang.
- Mỗi page reference giữ đủ `source_citations`. Trace thêm `citation_bindings`:
  segment → verified claim → exact source IDs; không mất ánh xạ chi tiết theo claim.
- Giữ payload scalar đã thu gọn, cap 48.000 prompt characters và một Gateway call;
  prompt yêu cầu diễn đạt tự nhiên, dẫn đủ IDs, giữ caveats và không suy kết luận mới.

Chỉ sửa runtime `src/outputs/qa_lite.py` và nhóm tests tương ứng. M1–M6, Ledger,
legacy/report renderer, API/frontend và model/provider configuration không thay đổi.
`m7_lite=False` vẫn là mặc định. Giữ toàn bộ local work có trước.

## Ranh giới được chấp nhận trong task này

Numeric/source checks **không chứng minh đúng ngữ nghĩa**. Một đoạn có thể dùng số
đúng nhưng gán sai chủ thể hoặc thêm quan hệ nhân quả. Task này chủ động không dựng
semantic approval thay thế; prompt chỉ được tổng hợp findings ACCEPT và live output
được đọc/audit thủ công. Không tuyên bố cơ chế này loại được mọi unsupported assertion.

Các kết luận M6 còn thiếu ở Q21/Q23 và phép tính ad hoc chưa ACCEPT ở L09 tiếp tục
là giới hạn thượng nguồn. Không sửa M5/M6 để cứu các ca. Khi model bỏ một finding
đã chọn, backend giữ finding đó bằng fallback, đồng thời giữ các đoạn model hợp lệ.

## Offline và integration smoke

**19 targeted tests PASS**: 18 Lite controls và một legacy pipeline smoke.
Bao phủ paraphrase được phát hành; số/đơn vị sai; unknown ID; malformed JSON;
INVESTIGATE/ABSTAIN; scope; Decimal/làm tròn/đổi thang trình bày;
timeout/503 không retry; partial preservation; API round-trip;
page grouping và exact per-claim source bindings. Cập nhật expectations của test
verbatim cũ theo contract mới, không giảm số lượng tests.

Replay **offline** raw Q23 thật từ M7-LITE-01: hai đoạn paraphrase trước đây bị chặn
đều được phát hành; growth metric bị model bỏ sót được giữ riêng bằng fallback.
Replay này không phải Gemini live mới và không thay kết quả live Q23 bên dưới.

Một real Q23 pipeline smoke dùng approved catalog + original saved Ledger:
giữ đủ 5 findings, một page reference, M5/M6/provider đều NOT_EXECUTED/0 calls.
Audit offline bốn ca giữ 12/12 findings; references **69 → 6**:

| Case | M7-LITE-01 references | Page references mới | Findings giữ |
| --- | ---: | ---: | ---: |
| Q21 | 21 | 2 | 3/3 |
| Q23 | 16 | 1 | 5/5 |
| L08 | 19 | 2 | 2/2 |
| L09 | 13 | 1 | 2/2 |

Exact source IDs của từng segment/claim đều khớp citations Ledger; full source
variants còn trong backend, 0 binding mismatch. Đây là provenance binding audit,
không phải một vòng visual PDF/financial verification độc lập.

## Gemini live trên final code và compact payload

Đúng **2 calls**, L08 rồi Q23, không retry/rotation/resume. Cùng Gateway, adapter
và model `gemini-3.5-flash-lite`; chỉ Answer Agent, không OCR/M5/M6.
Task-local runner tự chạy offline assertions trước network và reserve cả run
hai calls một lần; live preflight còn chặn input trên 12.000 characters.
Không sửa runtime sau live. Saved source run vẫn là real Ledger/traces
`FIX-02/final-acceptance/remediation-native-proof-final` ở b9d0cdb; không dùng
synthetic claims hoặc chọn lịch sử tốt hơn thay kết quả mới.

| Case | Provider | Prompt chars | Input/output/total tokens | LLM segments phát hành | Fallback | Page refs | Đánh giá final |
| --- | --- | ---: | --- | ---: | --- | ---: | --- |
| L08 | success | 3.430 | 1.401 / 544 / 1.945 | 3 | Không | 2 | CORRECT_WITH_CAVEAT |
| Q23 | HTTP503 | 4.843 | unknown | 0 | Có | 1 | PARTIAL; chưa có live natural-answer evidence |

Tổng **1.945 known tokens, 1 call usage unknown**; không coi lượt lỗi là 0 tokens.
L08 giữ cả 2 ACCEPT IDs, Q23 giữ cả 5; 0 lost, 0 citation binding errors.
L08 latency ~6.471 ms; Q23 ~905 ms, gồm compose/validation/render.

L08 đã chứng minh câu trả lời tự nhiên do Gemini sinh được phát hành nguyên văn
(chỉ thêm backend citation labels/caveats), không trở về ghép claims. Manual audit:
số liệu ratio/operands và diễn giải per100 đều từ ACCEPT findings; phần giới hạn
phù hợp caveats đã lưu; không phát hiện nhận định mới trong câu trả lời này.
Không suy kết quả một ca thành bảo đảm semantic correctness toàn hệ thống.

Q23 HTTP503 sau đúng một attempt; raw output không có, runtime trả grounded partial
với gap C, không báo NO_DATA. Không chạy lại vì ngân sách đã dùng đủ.

## Evidence và trạng thái bàn giao

Ruff check/format và planning checker: PASS; `git diff --check`: PASS.
Không full regression hoặc Gemini mới khi chốt. Trước commit kiểm tra lại 19 tests trên
staged snapshot riêng, Ruff/planning/diff; CI được kiểm tra đúng SHA sau một push.
CI185Python/9Web của e6411ec thuộc M7-LITE-01, không dùng làm CI cho code mới.
Protected saved source/receipts và các file local ngoài task được đối chiếu hash.
Các artifacts mới chỉ nằm trong `artifacts/evidence/M7-LITE-02`; dữ liệu gốc read-only.

Còn hạn chế: Q23 chưa có lần live thành công với payload mới; upstream conclusions
còn thiếu; caveats backend có thể lặp ý model đã diễn đạt; formula fallback cũ còn
cùng label cho toán hạng khác kỳ. Không triển khai thêm ngoài phạm vi task này.

Owner xác nhận Q23 HTTP503 là lỗi provider, không là lý do sửa tiếp M7.
Dừng giai đoạn triển khai M7 Lite; không mở M7-LITE-03.
Next action: Owner/Tech Lead nghiệm thu implementation commit đã push.

## Raw và final output thực tế

Các phần sau chép nguyên văn hai receipts mới, không dùng replay thay live.

### L08

**Câu hỏi:** Đánh giá mức độ sử dụng nợ của BBS cuối năm 2025 qua tỷ lệ nợ phải trả trên tổng tài sản; nêu số liệu, phép tính và giới hạn kết luận.

**ACCEPT findings:**

- `verified:118c553011cb032addb662338d9c2b0753413061f832a8dd2dbd4d3fb7ab3780` — Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%.
- `verified:745d9ca1cd58095e23fe39d5e34c740863ad8eb6d8bf3fc458f4f4198f6ed921` — Trong kỳ 2025-12-31, cứ 100 đồng tổng tài sản tương ứng khoảng 59,06 đồng nợ phải trả.

**Gemini raw output:**

```json
{
  "segments": [
    {
      "text": "Tại thời điểm ngày 31/12/2025, tỷ lệ nợ phải trả trên tổng tài sản của BBS đạt 59,06%, được tính toán từ số liệu nợ phải trả là 157.146.559.558 VND chia cho tổng cộng tài sản là 266.086.680.765 VND.",
      "claim_ids": [
        "verified:118c553011cb032addb662338d9c2b0753413061f832a8dd2dbd4d3fb7ab3780"
      ]
    },
    {
      "text": "Về mặt diễn giải số học, cứ 100 đồng tổng tài sản của doanh nghiệp tại kỳ này sẽ tương ứng với khoảng 59,06 đồng nợ phải trả.",
      "claim_ids": [
        "verified:745d9ca1cd58095e23fe39d5e34c740863ad8eb6d8bf3fc458f4f4198f6ed921"
      ]
    },
    {
      "text": "Tuy nhiên, kết luận này có những giới hạn nhất định: chỉ tiêu tỷ lệ nợ trên tài sản chỉ được diễn giải mang tính số học và chưa đủ căn cứ để đánh giá khả năng thanh toán; bên cạnh đó, tổng nợ phải trả không đồng nghĩa với riêng nợ vay có lãi, và bằng chứng lưu trữ còn giới hạn về nguồn hoặc ngữ cảnh.",
      "claim_ids": [
        "verified:118c553011cb032addb662338d9c2b0753413061f832a8dd2dbd4d3fb7ab3780",
        "verified:745d9ca1cd58095e23fe39d5e34c740863ad8eb6d8bf3fc458f4f4198f6ed921"
      ]
    }
  ],
  "gaps": []
}
```

**Final answer** (`completed_with_caveats`):

```text
Tại thời điểm ngày 31/12/2025, tỷ lệ nợ phải trả trên tổng tài sản của BBS đạt 59,06%, được tính toán từ số liệu nợ phải trả là 157.146.559.558 VND chia cho tổng cộng tài sản là 266.086.680.765 VND. [1][2]

Về mặt diễn giải số học, cứ 100 đồng tổng tài sản của doanh nghiệp tại kỳ này sẽ tương ứng với khoảng 59,06 đồng nợ phải trả. [1][2]

Tuy nhiên, kết luận này có những giới hạn nhất định: chỉ tiêu tỷ lệ nợ trên tài sản chỉ được diễn giải mang tính số học và chưa đủ căn cứ để đánh giá khả năng thanh toán; bên cạnh đó, tổng nợ phải trả không đồng nghĩa với riêng nợ vay có lãi, và bằng chứng lưu trữ còn giới hạn về nguồn hoặc ngữ cảnh. [1][2]

Lưu ý: Debt-to-Assets chỉ được diễn giải số học; chưa đủ căn cứ đánh giá khả năng thanh toán.; Tổng nợ phải trả không đồng nghĩa với riêng nợ vay có lãi.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

Released IDs 2/2; LLM segments 3; rejected segments 0; lost `[]`; binding errors `[]`.

### Q23

**Câu hỏi:** Doanh thu thuần BBS 2025 tăng nhưng lợi nhuận gộp giảm so với 2024: các số liệu cho thấy điều gì? Không suy đoán nguyên nhân.

**ACCEPT findings:**

- `verified:26dc404fcbf3f4e16109d0461f19ecb1e721f6da834e62734487abc5246cb7d1` — Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND.
- `verified:67ff3050a48e94e3c08f4cc10e7cec28f3940f6dbe80c4d21f92df43a25a82f5` — Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.
- `verified:7e8c833a7f6061f2dfd7e3548fefcba9996daf056555eee953dbb15a72a50a7c` — Doanh thu thuần kỳ 2024 là 355.507.372.286 VND.
- `verified:a78fb2107d7001da7a653241ed7e422df638e2c2391e5d9917ccce60e8b8f6c6` — Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND.
- `verified:ae888ccd144875f55eb3b0a4a354f3a2ad665db58b740550012904846516f500` — Tăng trưởng doanh thu kỳ 2025 đạt 26,71%.

**Gemini raw output:**

Không có output; http_503 / provider_unavailable, usage unknown.

**Final answer** (`partial_verified_coverage`):

```text
Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND. [1]

Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1]

Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. [1]

Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. [1]

Tăng trưởng doanh thu kỳ 2025 đạt 26,71%.
Công thức đã xác minh: ((3. Doanh thu thuần về bán hàng và cung cấp dịch vụ - 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ) / 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ) × 100.
3. Doanh thu thuần về bán hàng và cung cấp dịch vụ: 450474531227 VND; hệ số đơn vị 1; kỳ 2025.
3. Doanh thu thuần về bán hàng và cung cấp dịch vụ: 355507372286 VND; hệ số đơn vị 1; kỳ 2024. [1]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

Released IDs 5/5; LLM segments 0; rejected segments 0; lost `[]`; binding errors `[]`.

Runtime SHA-256 đã xác minh khớp byte trước/sau live:

- `src/outputs/qa_lite.py`: `0762ce632563e41f305667068fec7df1bcc3aa9f7f9ecaa5dca3764c50e07fbd`
- `tests/unit/test_qa_lite.py`: `9b34a5b22b28c7644bb26768b3e743ae7cc5e82201db07b2baa572c874638572`
