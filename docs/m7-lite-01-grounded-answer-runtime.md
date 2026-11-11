# M7-LITE-01 — Simplified Grounded Answer Generation

Ngày 11/11/2026. **REVIEW — chưa đạt đầy đủ mục tiêu phát hành câu trả lời tự nhiên.**
Baseline tham chiếu và HEAD khi bắt đầu đều là
`b9d0cdb88417a344f1269dbfb6cf7300b18824bd`, branch `main`.
Implementation SHA và CI exact-SHA được bổ sung sau commit/push; không tự nghiệm thu DONE.

## Kiến trúc thực tế

`FinancialQARequest(m7_lite=True) → scope binding → VerifiedClaimLedger → scope/relevance selection → Answer Agent → presentation integrity/fallback → Lite citation projection → FinancialQAResponse`.

`m7_lite=False` mặc định. `FinancialQARequest` thêm flag; trace thêm `answer_mode`
và `m7_lite`, giữ các fields hiện có. Document-only/report tiếp tục dùng legacy.
Lite chỉ giải quyết financial findings trong một company/document/snapshot đã xác định;
cho phép nhiều kỳ được hỏi rõ trong cùng filing. Không mở cross-company/document fusion.

`src/outputs/qa_lite.py` sở hữu selection, một lời gọi `SharedLLMGateway.generate`,
integrity/fallback và renderer mỏng. Pipeline chỉ bổ sung context/reuse/release branch.
`scripts/evaluate_m7_lite.py` đọc Ledger/traces thật ở đúng baseline, không chạy lại
M5/M6/OCR, reserve bốn calls trước live và refuse chạy live lần thứ hai.
CI bổ sung đúng nhóm `test_qa_lite.py`; planning checker nhận Task ID M7-LITE-01.

M1–M6, Gateway/provider configuration, Ledger admission, legacy Composer,
CitationRenderer, InformationFirewall và Report Writer không được sửa bởi task này.
Các local edits có trước tại Composer/Specialists/GEN/Web/planning được giữ ngoài
implementation commit. Source financial approval vẫn chỉ thuộc M6.

## Các gate được bỏ qua trong Lite

- Không dùng `request_inventory`, Planner requirement coverage, formula-ID/target/
  interpretation-topic matching để chọn hoặc chặn ACCEPT findings.
- Không chạy protected-slot Composer, legacy QA renderer validation hoặc legacy
  InformationFirewall trên đầu ra Lite; không giả `validation_result.valid=True`.
- Không dùng legacy unsupported-comparison/formula-preparation để phủ quyết output
  đã có trong Ledger. Company/document/snapshot, period và confirmed scope vẫn được giữ.
- Không thêm Judge/Verifier, dependency DAG, accounting policy hoặc semantic approval.

Historical claims phải qua relevance selection; current-request IDs chỉ ưu tiên thứ tự.
Catalog aliases/source labels là gợi ý retrieval. Source/comparative periods nằm ngoài
câu hỏi, non-ACCEPT, citations lệch nguồn và conflicting facts bị loại riêng.
Có findings phù hợp thì ưu tiên reuse; `force_refresh=True` vẫn gọi M5/M6 hiện có.
Một refresh/Planner bị dừng không xóa findings độc lập đã được admission.
Reuse không phải bằng chứng toàn bộ câu hỏi đã được trả lời đầy đủ.

## Ranh giới integrity và fallback

Answer Agent được yêu cầu trả JSON nhỏ `segments[text, claim_ids]` và `gaps[type, text]`,
không provider-side schema, không citation/page/verdict tự sinh. Backend tự tạo labels,
PDF locators và bindings từ citations của ACCEPT entries.

Số đúng không chứng minh diễn giải đúng. Runtime hiện chỉ giữ một đoạn khi có thể
bảo toàn toàn bộ mệnh đề ACCEPT được dẫn, có thể ghép nhiều mệnh đề và làm tròn
Decimal ở cùng vị trí/đơn vị. Mọi paraphrase tự do chưa đủ chắc chắn bị thay bằng
nguyên văn findings tương ứng; những đoạn hợp lệ khác được giữ. Claim bị model bỏ sót
được nối lại bằng nội dung ACCEPT. Calculation display đọc proof hiện hữu, không
tính mới hoặc kiểm duyệt lại formula registry. Caveats/limitations nguồn được giữ.

**Giới hạn P1:** cơ chế fallback còn quá bảo thủ cho mục tiêu tổng hợp tự nhiên.
Không coi bảo toàn toàn mệnh đề là semantic verification. Trong live này, cả hai
đoạn do Gemini viết đều không được phát hành dưới dạng paraphrase. Chưa chứng minh
Lite đã vượt hạn chế diễn đạt của protected slots; cần Tech Lead quyết định tiếp.

Gaps A chỉ khi backend xác định không có source khả dụng; B là chưa có đủ kết luận
verified; C là lỗi kỹ thuật/provider. Một lời tự khai A/C của model không đủ chứng minh
nguồn vắng mặt/provider lỗi; raw diagnosis giữ trong trace, public dùng B thận trọng.
HTTP 503/429 không được báo thành NO_DATA. Fallback không có lời gọi LLM bổ sung.

## Engineering validation

- 155 targeted tests PASS trên Lite/pipeline/legacy Composer/citation renderer;
  nhóm này gồm 16 Lite controls ở bản trước chỉnh payload.
- Final Lite controls: 17 PASS sau compact payload, gồm INVESTIGATE và ABSTAIN.
  Những nhóm này có overlap, không cộng thành 172 tests độc lập.
- Final staged snapshot đã loại toàn bộ local edits ngoài task: 18/18 Lite + legacy
  integration smoke PASS, Ruff lint PASS/627 files format PASS, planning PASS/122 tasks
  và staged diff check PASS. Run 155 trước đó là working-tree validation, có local
  edits được giữ; không coi nó là kiểm thử exact committed tree.
- Real Q23 pipeline smoke PASS: giữ 5 selected findings, M5/M6/provider đều không chạy.
- Sau live, replay bốn immutable provider responses trên final compact payload:
  0 network calls, final answers và retained IDs giống bản live. Đây là offline replay,
  không phải bốn lượt Gemini mới và không chứng minh model sẽ trả tương tự với prompt mới.
- Ruff check/format, planning checker và `git diff --check`: kết quả chốt ở evidence.

Các negative controls bắt buộc đã được bao phủ: non-ACCEPT; sai company;
sai period/snapshot; citation lệch nguồn; unknown claim ID; số bịa; nhận định mới;
một đoạn/claim lỗi không xóa phần khác; Ledger rỗng; timeout/HTTP503 không retry;
làm tròn hợp lệ; phép tính/số đúng không phê duyệt nhận định tài chính mới.
Có kiểm tra scope/comparative periods, relevance, fresh admission/cache/refresh failure,
API model round-trip và legacy mặc định. Đây là engineering evidence, không phải
benchmark độc lập về chất lượng tài chính/PDF scan.

## Live thực tế và chi phí

Đúng bốn Answer Agent calls, Gemini `gemini-3.5-flash-lite` qua SharedLLMGateway và
adapter hiện có; một credential, không rotation/retry. Không OCR, không M5/M6 manifest.
Source run cố định: `FIX-02/final-acceptance/remediation-native-proof-final`, đúng b9d0cdb.
Không chọn các lượt cũ thành công hơn để thay kết quả của baseline này.

**Sự cố payload:** Q23 provider báo **317.297 input + 495 output = 317.792 tokens**.
Ba lỗi còn lại usage unknown, không tính bằng zero. Nguyên nhân input quá lớn:
phiên bản chạy live serialize cả evidence/calculation tree lồng nhau. Sau đúng bốn calls,
chỉ thu gọn input thành scalar evidence, scoped identities, accepted text/proof display
và caveats/limitations; thêm giới hạn 48.000 characters trước Gateway. Backend giữ
nguyên full proofs. Không gọi live thêm sau sửa này. Final compact prompt chưa được
kiểm chứng Gemini live; không tuyên bố chi phí thực tế đã giảm.

Final offline capture: Q21 4.555, Q23 4.604, L08 3.191, L09 2.241 prompt characters,
tất cả dưới giới hạn. Đồng thời bổ sung scope guard khi period khai báo mâu thuẫn
câu hỏi hoặc yêu cầu kỳ chưa resolve; các case đã ghi không đổi.

## Audit và giới hạn nghiệm thu

12/12 selected findings được giữ; 0 lost, 0 unsupported assertions được xác định
trong final output; 69 citation references, 0 binding mismatch. Audit kiểm tra exact
claim/source/locator/page và source citations từ Ledger hiện hành; không phải một
vòng visual PDF/financial verification mới. Tái sử dụng provenance thật đã lưu,
không tự cấp financial accuracy cho OCR hay M6.

10.087 protected files giữ hash, original Ledger giữ nguyên; 11 pre-existing local
files ngoài ba planning files đang tích hợp giữ nguyên bytes. Những edits có trước
trong ba planning files được giữ và không stage vào task.

Q21 thiếu đánh giá chất lượng lợi nhuận ACCEPT ngoài phép đối chiếu có giới hạn.
Q23 có bốn facts và một growth metric nhưng chưa có kết luận ACCEPT về ý nghĩa
sinh lời/gross-profit decline. L08 fallback đủ ratio/operands/diễn giải và giới hạn,
nhưng provider bị rate limit. L09 baseline không có ACCEPT proof cho phép trừ ad hoc;
Lite chỉ phát hành hai facts, không tự tạo kết quả 417.992.011.559 VND.
Formula display của growth còn dùng cùng label cho hai toán hạng; cần đọc kỳ ở
các dòng operands. Citation labels cũng còn dài/lặp theo các source selectors.

Không tuyên bố 4/4 live PASS, không tuyên bố natural-answer acceptance đã đạt.
Implementation sau compact payload/scope guards chỉ có offline validation.
Không mở vòng remediation mới, không chờ quota phục hồi, không mở M5/M6 Lite hoặc M8.

Next action: Tech Lead review M7-LITE-01 với các giới hạn live, chi phí và paraphrase nêu trên.

## So sánh nguyên văn từng ca

Các phần dưới được chép từ immutable saved results và bốn receipts của task;
nguyên văn legacy/raw/final được giữ, kể cả sự lặp và giới hạn trình bày.

| Case | Provider | Đánh giá final | Selected/retained/lost | References | Tokens biết | Latency ms |
| --- | --- | --- | --- | --- | --- | --- |
| Q21 | http_503 | PARTIAL | 3/3/0 | 21 | unknown | 2081.38 |
| Q23 | success | PARTIAL | 5/5/0 | 16 | 317792 | 27630.00 |
| L08 | http_429 | CORRECT_WITH_CAVEAT | 2/2/0 | 19 | unknown | 2069.25 |
| L09 | http_429 | PARTIAL | 2/2/0 | 13 | unknown | 518.58 |

### Q21

**Câu hỏi nguyên văn:** Đánh giá chất lượng lợi nhuận BBS 2025 qua lợi nhuận sau thuế và dòng tiền thuần từ hoạt động kinh doanh; dẫn số liệu và giới hạn kết luận.

**M6 ACCEPT findings thực tế được chọn:**

- `verified:30e9b898d8044f4a5440c68be7d9c53c8ea2140efc5802b353d46a7c7b7eb64d` — supported_interpretation; kỳ 2025; PDF 7,8: Lưu chuyển tiền thuần từ hoạt động kinh doanh (kỳ 2025) − Lợi nhuận sau thuế (kỳ 2025): 7.070.123.808,00 VND.
- `verified:672601266f3276bb39bc89d9df7a89fe929b2a656fb00b57a8537eecc6bcbe71` — fact; kỳ 2025; PDF 7: Lợi nhuận sau thuế của kỳ 2025 là 7.249.557.946 VND.
- `verified:f837b9fa21c690e3c640754234d71832d08be720ad363a1d5bbe74ab188e9823` — fact; kỳ 2025; PDF 8: Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 14.319.681.754 VND.

**Legacy baseline** (`partial_verified_coverage`; 2 released IDs):

```text
Theo các nội dung đã được xác minh trong ledger:
Kỳ 2025 — Lợi nhuận sau thuế của kỳ 2025 là 7.249.557.946 VND. [1][2][3][4][5][6][7][8][9][10]
Kỳ 2025 — Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 14.319.681.754 VND. [11][12][13][14][15][16][17][18][19][20][21]
Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.
Các yêu cầu chưa đáp ứng: nhận định về 17. Lợi nhuận sau thuế thu nhập doanh nghiệp (chưa có nhận định được xác minh phù hợp), nhận định về Lưu chuyển tiền thuần từ hoạt động kinh doanh (chưa có nhận định được xác minh phù hợp), yêu cầu chưa xác định (chưa đủ căn cứ hoặc cần làm rõ).
Lưu ý: Báo cáo kết quả kinh doanh và lưu chuyển tiền tệ có nguồn riêng; phạm vi báo cáo vẫn chưa được xác nhận.; Chưa đủ dữ liệu để xác nhận các điều chỉnh dòng tiền hoặc nguyên nhân chênh lệch.; Phép tính ad hoc phải nêu định nghĩa và không tự trở thành chỉ tiêu kế toán chuẩn.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Đối chiếu lợi nhuận và dòng tiền là tín hiệu trong kỳ, chưa phải đánh giá toàn diện chất lượng lợi nhuận.; Phạm vi báo cáo chưa được xác nhận trong claim đã chọn.
Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Thiếu claim trong ledger không có nghĩa là số liệu không tồn tại trong PDF.

Lưu ý nguồn: Báo cáo kết quả kinh doanh và lưu chuyển tiền tệ có nguồn riêng; phạm vi báo cáo vẫn chưa được xác nhận.; Chưa đủ dữ liệu để xác nhận các điều chỉnh dòng tiền hoặc nguyên nhân chênh lệch.; Phép tính ad hoc phải nêu định nghĩa và không tự trở thành chỉ tiêu kế toán chuẩn.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Đối chiếu lợi nhuận và dòng tiền là tín hiệu trong kỳ, chưa phải đánh giá toàn diện chất lượng lợi nhuận.; Phạm vi báo cáo chưa được xác nhận trong claim đã chọn.

Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Thiếu claim trong ledger không có nghĩa là số liệu không tồn tại trong PDF.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

## Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[2] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[3] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[4] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[5] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[6] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[7] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[8] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[9] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[10] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[11] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[12] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[13] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[14] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[15] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[16] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[17] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[18] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[19] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[20] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[21] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
```

**Gemini raw:** không có output; receipt ghi http_503 / provider_unavailable. Usage unknown.

**Final Lite answer nguyên văn** (`partial_verified_coverage`):

```text
Lưu chuyển tiền thuần từ hoạt động kinh doanh (kỳ 2025) − Lợi nhuận sau thuế (kỳ 2025): 7.070.123.808,00 VND. [1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19][20][21]

Lợi nhuận sau thuế của kỳ 2025 là 7.249.557.946 VND. [12][13][14][15][16][17][18][19][20][21]

Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 14.319.681.754 VND. [1][2][3][4][5][6][7][8][9][10][11]

Lưu ý: Báo cáo kết quả kinh doanh và lưu chuyển tiền tệ có nguồn riêng; phạm vi báo cáo vẫn chưa được xác nhận.; Chưa đủ dữ liệu để xác nhận các điều chỉnh dòng tiền hoặc nguyên nhân chênh lệch.; Phép tính ad hoc phải nêu định nghĩa và không tự trở thành chỉ tiêu kế toán chuẩn.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Đối chiếu lợi nhuận và dòng tiền là tín hiệu trong kỳ, chưa phải đánh giá toàn diện chất lượng lợi nhuận.

Giới hạn: Phép tính ad hoc dựa trên số liệu được cung cấp, không phản ánh toàn bộ bản chất điều chỉnh vốn lưu động hay các khoản phi tiền mặt.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[3] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[4] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[5] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[6] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[7] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[8] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[9] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[10] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[11] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[12] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[13] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[14] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[15] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[16] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[17] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[18] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[19] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[20] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[21] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

Retained 3/3; lost `[]`; citation binding errors `[]`. Final unsupported assertions: không phát hiện. Đánh giá nội dung: **PARTIAL**; fallback true.

### Q23

**Câu hỏi nguyên văn:** Doanh thu thuần BBS 2025 tăng nhưng lợi nhuận gộp giảm so với 2024: các số liệu cho thấy điều gì? Không suy đoán nguyên nhân.

**M6 ACCEPT findings thực tế được chọn:**

- `verified:26dc404fcbf3f4e16109d0461f19ecb1e721f6da834e62734487abc5246cb7d1` — fact; kỳ 2024; PDF 7: Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND.
- `verified:67ff3050a48e94e3c08f4cc10e7cec28f3940f6dbe80c4d21f92df43a25a82f5` — fact; kỳ 2025; PDF 7: Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.
- `verified:7e8c833a7f6061f2dfd7e3548fefcba9996daf056555eee953dbb15a72a50a7c` — fact; kỳ 2024; PDF 7: Doanh thu thuần kỳ 2024 là 355.507.372.286 VND.
- `verified:a78fb2107d7001da7a653241ed7e422df638e2c2391e5d9917ccce60e8b8f6c6` — fact; kỳ 2025; PDF 7: Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND.
- `verified:ae888ccd144875f55eb3b0a4a354f3a2ad665db58b740550012904846516f500` — approved_metric; kỳ 2025; PDF 7: Tăng trưởng doanh thu kỳ 2025 đạt 26,71%.

**Legacy baseline** (`partial_verified_coverage`; 4 released IDs):

```text
Theo các nội dung đã được xác minh trong ledger:
Kỳ 2025 — Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1][2][3][4][5][6][7][8][9][10]
Kỳ 2024 — Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. [1][2][3][4][5][6][11][8][9][12]
Kỳ 2025 — Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. [1][2][3][4][5][6][7][13][14][15]
Kỳ 2024 — Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND. [1][2][3][4][5][6][11][13][14][16]
Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.
Các yêu cầu chưa đáp ứng: nhận định về 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ (chưa có nhận định được xác minh phù hợp).
Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Phạm vi báo cáo chưa được xác nhận trong claim đã chọn.
Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Thiếu claim trong ledger không có nghĩa là số liệu không tồn tại trong PDF.

Lưu ý nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Phạm vi báo cáo chưa được xác nhận trong claim đã chọn.

Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Thiếu claim trong ledger không có nghĩa là số liệu không tồn tại trong PDF.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

## Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[2] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[3] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[4] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[5] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[6] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[7] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[8] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[9] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[10] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[11] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[12] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[13] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[14] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[15] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[16] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
```

**Gemini raw output nguyên văn:**

```json
{
  "segments": [
    {
      "text": "Doanh thu thuần của BBS năm 2024 đạt 355.507.372.286 VND và năm 2025 đạt 450.474.531.227 VND, ghi nhận sự tăng trưởng.",
      "claim_ids": [
        "verified:7e8c833a7f6061f2dfd7e3548fefcba9996daf056555eee953dbb15a72a50a7c",
        "verified:67ff3050a48e94e3c08f4cc10e7cec28f3940f6dbe80c4d21f92df43a25a82f5"
      ]
    },
    {
      "text": "Lợi nhuận gộp của BBS năm 2024 đạt 36.432.410.381 VND và năm 2025 đạt 32.482.519.668 VND, ghi nhận sự giảm sút.",
      "claim_ids": [
        "verified:26dc404fcbf3f4e16109d0461f19ecb1e721f6da834e62734487abc5246cb7d1",
        "verified:a78fb2107d7001da7a653241ed7e422df638e2c2391e5d9917ccce60e8b8f6c6"
      ]
    }
  ],
  "gaps": [
    {
      "type": "B",
      "text": "Chưa có kết luận verified giải thích hoặc đánh giá ý nghĩa cấu trúc sinh lời khi doanh thu thuần tăng nhưng lợi nhuận gộp giảm."
    }
  ]
}
```

**Final Lite answer nguyên văn** (`partial_verified_coverage`):

```text
Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND. [1][2][3][4][5][6][7][8][9][10]

Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1][2][3][4][5][6][11][12][13][14]

Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. [1][2][3][4][5][6][7][12][13][15]

Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. [1][2][3][4][5][6][11][8][9][16]

Tăng trưởng doanh thu kỳ 2025 đạt 26,71%.
Công thức đã xác minh: ((3. Doanh thu thuần về bán hàng và cung cấp dịch vụ - 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ) / 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ) × 100.
3. Doanh thu thuần về bán hàng và cung cấp dịch vụ: 450474531227 VND; hệ số đơn vị 1; kỳ 2025.
3. Doanh thu thuần về bán hàng và cung cấp dịch vụ: 355507372286 VND; hệ số đơn vị 1; kỳ 2024. [1][2][3][4][5][6][11][12][13][14][7][15]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[3] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[4] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[5] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[6] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[7] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[8] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[9] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[10] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[11] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[12] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[13] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[14] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[15] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[16] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

Retained 5/5; lost `[]`; citation binding errors `[]`. Final unsupported assertions: không phát hiện. Đánh giá nội dung: **PARTIAL**; fallback true.

### L08

**Câu hỏi nguyên văn:** Đánh giá mức độ sử dụng nợ của BBS cuối năm 2025 qua tỷ lệ nợ phải trả trên tổng tài sản; nêu số liệu, phép tính và giới hạn kết luận.

**M6 ACCEPT findings thực tế được chọn:**

- `verified:118c553011cb032addb662338d9c2b0753413061f832a8dd2dbd4d3fb7ab3780` — approved_metric; kỳ 2025-12-31; PDF 5,6: Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%.
- `verified:745d9ca1cd58095e23fe39d5e34c740863ad8eb6d8bf3fc458f4f4198f6ed921` — supported_interpretation; kỳ 2025-12-31; PDF 5,6: Trong kỳ 2025-12-31, cứ 100 đồng tổng tài sản tương ứng khoảng 59,06 đồng nợ phải trả.

**Legacy baseline** (`completed_with_caveats`; 2 released IDs):

```text
Theo các nội dung đã được xác minh trong ledger:
Kỳ 2025-12-31 — Trong kỳ 2025-12-31, cứ 100 đồng tổng tài sản tương ứng khoảng 59,06 đồng nợ phải trả. [1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19]
Kỳ 2025-12-31 — Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%.
Công thức: (C - NỢ PHẢI TRẢ / TỔNG CỘNG TÀI SẢN) × 100%.
Số liệu sử dụng trong phép tính đã xác minh:
- C - NỢ PHẢI TRẢ: 157146559558 VND; hệ số đơn vị 1; kỳ 2025-12-31.
- TỔNG CỘNG TÀI SẢN: 266086680765 VND; hệ số đơn vị 1; kỳ 2025-12-31. [1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19]
Lưu ý: Debt-to-Assets chỉ được diễn giải số học; chưa đủ căn cứ đánh giá khả năng thanh toán.; Tổng nợ phải trả không đồng nghĩa với riêng nợ vay có lãi.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Phạm vi báo cáo chưa được xác nhận trong claim đã chọn.
Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Lưu ý nguồn: Debt-to-Assets chỉ được diễn giải số học; chưa đủ căn cứ đánh giá khả năng thanh toán.; Tổng nợ phải trả không đồng nghĩa với riêng nợ vay có lãi.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Phạm vi báo cáo chưa được xác nhận trong claim đã chọn.

Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

## Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[2] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[3] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[4] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[5] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[6] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[7] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[8] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[9] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[10] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[11] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[12] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[13] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[14] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[15] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[16] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[17] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[18] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[19] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
```

**Gemini raw:** không có output; receipt ghi http_429 / rate_limit. Usage unknown.

**Final Lite answer nguyên văn** (`partial_verified_coverage`):

```text
Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%.
Công thức đã xác minh: (C - NỢ PHẢI TRẢ / TỔNG CỘNG TÀI SẢN) × 100.
C - NỢ PHẢI TRẢ: 157146559558 VND; hệ số đơn vị 1; kỳ 2025-12-31.
TỔNG CỘNG TÀI SẢN: 266086680765 VND; hệ số đơn vị 1; kỳ 2025-12-31. [1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19]

Trong kỳ 2025-12-31, cứ 100 đồng tổng tài sản tương ứng khoảng 59,06 đồng nợ phải trả.
Công thức đã xác minh: (C - NỢ PHẢI TRẢ / TỔNG CỘNG TÀI SẢN) × 100.
C - NỢ PHẢI TRẢ: 157146559558 VND; hệ số đơn vị 1; kỳ 2025-12-31.
TỔNG CỘNG TÀI SẢN: 266086680765 VND; hệ số đơn vị 1; kỳ 2025-12-31. [1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19]

Lưu ý: Debt-to-Assets chỉ được diễn giải số học; chưa đủ căn cứ đánh giá khả năng thanh toán.; Tổng nợ phải trả không đồng nghĩa với riêng nợ vay có lãi.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[3] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[4] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[5] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[6] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[7] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[8] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[9] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[10] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[11] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[12] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[13] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[14] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[15] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[16] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[17] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[18] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[19] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

Retained 2/2; lost `[]`; citation binding errors `[]`. Final unsupported assertions: không phát hiện. Đánh giá nội dung: **CORRECT_WITH_CAVEAT**; fallback true.

### L09

**Câu hỏi nguyên văn:** Tính chênh lệch doanh thu thuần và lợi nhuận gộp BBS 2025 bằng VND; dẫn nguồn và giải thích đây là phép đối chiếu, không phải chỉ tiêu kế toán chuẩn.

**M6 ACCEPT findings thực tế được chọn:**

- `verified:67ff3050a48e94e3c08f4cc10e7cec28f3940f6dbe80c4d21f92df43a25a82f5` — fact; kỳ 2025; PDF 7: Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.
- `verified:a78fb2107d7001da7a653241ed7e422df638e2c2391e5d9917ccce60e8b8f6c6` — fact; kỳ 2025; PDF 7: Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND.

**Legacy baseline** (`partial_verified_coverage`; 1 released IDs):

```text
Theo các nội dung đã được xác minh trong ledger:
Kỳ 2025 — Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. [1][2][3][4][5][6][7][8][9][10]
Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.
Các yêu cầu chưa đáp ứng: yêu cầu chưa xác định (chưa đủ căn cứ hoặc cần làm rõ), yêu cầu chưa xác định (chưa đủ căn cứ hoặc cần làm rõ), yêu cầu chưa xác định (chưa đủ căn cứ hoặc cần làm rõ).
Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Phạm vi báo cáo chưa được xác nhận trong claim đã chọn.
Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Thiếu claim trong ledger không có nghĩa là số liệu không tồn tại trong PDF.

Lưu ý nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Phạm vi báo cáo chưa được xác nhận trong claim đã chọn.

Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Thiếu claim trong ledger không có nghĩa là số liệu không tồn tại trong PDF.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

## Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[2] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[3] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[4] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[5] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[6] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[7] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[8] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[9] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

[10] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
```

**Gemini raw:** không có output; receipt ghi http_429 / rate_limit. Usage unknown.

**Final Lite answer nguyên văn** (`partial_verified_coverage`):

```text
Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1][2][3][4][5][6][7][8][9][10]

Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. [1][2][3][4][5][6][7][11][12][13]

Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.

Nguồn tham chiếu

[1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[2] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[3] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[4] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[5] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[6] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[7] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[8] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[9] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[10] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[11] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[12] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
[13] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
```

Retained 2/2; lost `[]`; citation binding errors `[]`. Final unsupported assertions: không phát hiện. Đánh giá nội dung: **PARTIAL**; fallback true.
