# M7-ANSWER-01 — Grounded Natural Answer Generation

Trạng thái **DONE — Owner xác nhận ngày17/11/2026**. Nghiệm thu implementation và
evidence đã bàn giao tại `0d6daf1`, đã push main và xác minh remote SHA; giữ nguyên
các giới hạn đã báo. Phiên đóng chỉ tài liệu/tracking và planning/diff/Git,
không sửa runtime hoặc chạy lại tests/API; chưa triển khai E2E-ARCH-02. Implementation
`5414b699e63758270d80cc36390ecc6eb7149134`, sau bản đầu `45dca05`;
baseline remote `fcd0675`. Worktree riêng giữ local edits của checkout gốc.

M7 Lite gửi câu hỏi gốc, verified claims/proofs, goal bindings, coverage và
citations qua Gateway Qwen. Model viết prose kèm claim IDs; backend gắn đúng
sources và giữ missing goals/caveats. Không group lại từng claim khi đã có prose
tổng hợp. Không thêm agent, pipeline, retrieval, phép tính hoặc semantic verifier;
M5/M6/Ledger, ACCEPT và goal bindings giữ nguyên.

Đã dùng **3actual Qwen calls,24.442tokens**,0retry/unknown usage. Dùng saved
M5/M6/Ledger trên JSON/EF-EG BBS2025; không gọi lại M5/M6. Bản đầu live tạo
prose tự nhiên ở2ca full; ca partial bị numeric guard chặn vì thêm số ngoài Ledger.
Bản cuối giữ nguyên các câu vượt qua cùng numeric check, bỏ câu chứa số không
được hỗ trợ; không sửa số hoặc viết lại kết luận. Replay nguyên3responses đã lưu,
assert model/messages/generation/output_spec/constraints khớp, **0API calls mới**.
Đây là saved-response replay của bản cuối, không phải fresh final Qwen.

| Câu hỏi thực tế | Kết quả trên bản cuối | Claims / references |
| --- | --- | --- |
| Doanh thu thuần năm2025 của BBS là bao nhiêu? | Natural:450.474.531.227VND; coverage đầy đủ, completed_with_caveats; không fallback. | 1 / 6 |
| BBS2025: nêu lợi nhuận sau thuế, dòng tiền kinh doanh và tính dòng tiền trừ lợi nhuận | Một đoạn thống nhất:7.249.557.946VND,14.319.681.754VND và chênh lệch7.070.123.808VND, đúng cả3claims đã ACCEPT; coverage đầy đủ, không fallback. | 3 / 12 |
| Chọn năm có dòng tiền kinh doanh lớn hơn2024/2025, nêu doanh thu cùng năm, tính doanh thu trừ dòng tiền và nêu LNST2025 độc lập | Partial: giữ dòng tiền2024 là27.996.254.086VND và LNST2025 là7.249.557.946VND. G1/G4 satisfied; G2/G3 unverified, nêu rõ phần thiếu. | 2 / 12 |

Ca partial Qwen đã tự thêm doanh thu2024 là103.544.664.644VND dù không có claim
tương ứng trong payload. Bản live đầu chặn cả đoạn, fallback về admitted text;
bản cuối chỉ giữ hai câu có số được hỗ trợ. Số tự thêm **không xuất hiện trong
câu trả lời phát hành**. Gaps do model viết chỉ advisory, không được phát hành
hoặc dùng để sửa coverage. Trace giữ raw response và unsupported_number để audit.

Audit thủ công prose cuối của3ca không thấy thêm công thức, nguyên nhân hoặc nhận
xét tài chính ngoài claims. **30citation references/6exact claim-source bindings**
khớp Ledger; coverage khớp nguyên saved M6 release. Request context và entry payloads
không đổi.185runtime hashes khớp implementation;24JSON nguồn bất biến và các saved
trace/Ledger được hash trước/sau. Receipt cuối có33input hashes, gồm saved responses.

**28targeted tests PASS** trên code cuối:3controls mới, M7 Lite/coverage compatibility
và integration smoke fresh/cache/failure/legacy hiện có. Kiểm supported synthesis,
không nhân đôi prose chung, citations, partial/unbound, numeric mismatch, model
citation, sentence filtering và fallback. Ruff lint/format, planning checker và
diff check đạt. Không full CI/benchmark/OCR/Gemini/PDF; commits dùng skip-ci theo
phạm vi validation được giao. Synthetic tests không là financial accuracy.

Evidence local, không đưa dataset/trace tài chính hoặc credentials vào Git:

- `artifacts/evidence/M7-ANSWER-01/live-v1/provider-events.json`, `receipt.json`
  và3case JSON:3actual calls tại `45dca05`, gồm hallucination đã bị chặn.
- `artifacts/evidence/M7-ANSWER-01/final-replay/receipt.json`, `provider-events.json`
  và3case JSON: kết quả cuối tại `5414b69`, exact saved-response replay0calls.
- `artifacts/m7-final-targeted.xml`:28targeted PASS.

Giới hạn: kiểm số/citation không chứng minh ngữ nghĩa mọi paraphrase; kết quả chỉ
được audit trên3câu, không tuyên bố accuracy chung. Hai goals của ca partial vẫn
thiếu support M6. Nguồn giữ JSON-only/source_reference_uncertain/page-level,
không nâng thành PDF-verified. References có thể trùng nhãn trang JSON vì giữ các
source pointers khác nhau. Chưa fresh final Qwen sau sentence-filter fix.

Next action: chờ Owner/Tech Lead giao nhiệm vụ tiếp theo.
