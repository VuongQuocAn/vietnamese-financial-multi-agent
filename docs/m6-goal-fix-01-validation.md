# M6-GOAL-FIX-01 — Fix Incorrect Goal Binding

**DONE — Owner xác nhận hoàn thành ngày17/11/2026**; implementation
`a3519778f8356bd394b059cef1229c5e6543ca6f` đã push main/remote SHA verified;
baseline `1aec917`.180runtime files trong commit khớp receipt live.
Worktree riêng giữ local edits; không sửa Coordinator/M7 hoặc G3 thiếu candidate.

Nguyên nhân: parser M6 chỉ kiểm tra IDs Qwen trả về thuộc allowlist M5 đề xuất.
Replay obligations kiểm tra nguồn/số học/selection records, nhưng chưa đối chiếu
binding cụ thể với item và kỳ mà goal yêu cầu. Child có nguồn2025 vẫn hợp lệ về
truth trong dependency closure có selection2024. Ledger replay quyết định truth
và giữ verdict đó; vì thế raw `SUPPORTED/G2` đi tiếp thành support không phù hợp.

Sửa tại M6: `goal_binding_issue` trong Evidence Obligations đối chiếu aliases/
required indicators, kỳ rõ trong goal hoặc kỳ từ selection đã replay, selected
reference/comparator, operation/ordered operands/formula ID và requested unit.
Tái dùng resolver/operation matcher hiện có; không thêm verifier/agent hay LLM call.
Runtime lọc IDs trước khi lưu proof mới; `supported_goals` áp dụng cùng phép lọc
cho history v2 cũ khi đọc, không mutate bytes hoặc ACCEPT lịch sử. Semantic truth
và quyền quyết định ACCEPT vẫn ở M6; raw provider output giữ trong trace.

## Saved trace và live

Dùng nguyên final M5 output của M5-COORD-03 controlled replay đã lưu, không chèn
lỗi mới, không chạy M5/Coordinator hoặc feedback repair. Một live Qwen call tái
lặp đúng binding sai; backend loại binding độc lập với raw verdict.

| Claim trong saved trace | Truth trước/sau | Raw Qwen binding | M6 binding sau sửa |
| --- | --- | --- | --- |
| CFO2024, đúng selection | ACCEPT → ACCEPT | G1 | G1 |
| Revenue2025, selection chọn2024 | ACCEPT → ACCEPT | G2 | Không; `goal_selected_period_mismatch` |
| Gross profit2025, goal yêu cầu revenue | ACCEPT → ACCEPT | G2 | Không; `goal_indicator_mismatch` |
| PAT2025, goal độc lập | ACCEPT → ACCEPT | G4 | G4 |

Ledger mới admit/reload đủ4claims v2; M7 từ4claims/18citations trong trace cũ
thành **2claims/12citations**, chỉ G1/G4; G2/G3 giữ gap, không gọi trả lời đầy đủ.
Lọc saved Ledger cũ cũng giữ G1/G4 và loại2G2, không đổi4truth ACCEPT.

**1actual Qwen call,15.918tokens,0unknown,0retry**; không PDF/OCR/Gemini/full CI.
Runner lỗi serialize CitationReference khi xuất report sau khi M6/Ledger hoàn tất;
đã sửa encoder và hoàn tất M7 từ saved Ledger, không gọi lại API. Payload semantic
của4proofs khớp đúng rows gửi Qwen;4entries round-trip `build_verified_claim` PASS.

## Validation và giới hạn

36targeted PASS trên final runtime:3controls mới và33M6/obligations/feedback/ledger
controls. Kiểm tra wrong item/year/selected period/operator/operand order/unit,
truth/binding độc lập, old v2 đọc an toàn và M7 chỉ dùng effective support.
Ruff/planning/diff PASS; planning checker chỉ thêm pattern cho task ID được giao.
180runtime hashes khớp live receipt,24source JSON bất biến; không stage dữ liệu/secrets.

Guard chặn concrete contradictions có anchors rõ, không phải bộ hiểu mọi
paraphrase hoặc chứng minh mọi công thức phức tạp; semantic pass vẫn cần cho nghĩa
chưa resolve tường minh. Không đánh giá accuracy toàn PDF; G3 ngoài scope giữ nguyên.

Trace local, không commit raw data: `artifacts/evidence/M6-GOAL-FIX-01/live-v1/`
gồm `saved-m5-input.json`, `historical-binding-replay.json`, `provider/001-request.json`,
`provider/001.json`, `ledger/verified-claims.json`, `result.json`, `implementation.json`
và `publication.json` (implementation SHA đã đối chiếu receipt).
Final targeted log ở `artifacts/evidence/M6-GOAL-FIX-01/final-targeted-tests.log`.

Phiên đóng chỉ cập nhật tài liệu/tracking và kiểm planning/diff/Git, không sửa
runtime hoặc chạy lại tests/API. Giữ giới hạn semantic/paraphrase và JSON-only ở trên.

Next action: chờ Owner giao nhiệm vụ tiếp theo; không tự bắt đầu M5-PY-01.
