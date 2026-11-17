# M6-OBL-01 — Evidence Obligations & Goal Binding

**DONE — Owner/Tech Lead nghiệm thu phạm vi ngày17/11/2026. Implementation `801a6fd32dbd20dc62babfb95fb80bc8a5a1b51b`**, baseline `9a3adba`.
Worktree riêng bảo toàn local edits ngoài task. Giữ nguyên kết quả và giới hạn
G1/ADC bên dưới; nghiệm thu không mở rộng thành mọi trường hợp E2E.
Phiên đóng chỉ cập nhật tài liệu/tracking và kiểm planning/diff/Git, không sửa
runtime hoặc chạy lại tests/API/benchmark.

M6 đã truyền được binding đã kiểm chứng qua persisted Ledger v2 tới M7:
final probe có **2 ACCEPT, 2 bindings (G2/G3), 2 claims phát hành, 9 citations**;
M7 trả `partial_verified_coverage`. Chưa chứng minh positive live binding G1.

## Thay đổi

- M5 adaptive chuyển cả đề xuất selection/assigned goals tới M6; proposal không
  tự cấp support. M6 replay pinned observations bằng retrieval/validators cũ,
  domain/comparator/ties bằng `select_observations`, exact keys/cardinality/
  unmatched bằng `join_observations`; chặn operands ngoài selected closure.
- Arithmetic tiếp tục replay hiện có; selection/join và derived computations
  cần semantic M6 kiểm đúng mục tiêu/định nghĩa. Truth riêng với goal support.
- `LiteProofV2`/`lite_verification_history_v2` và `verified_claim_v2` lưu local
  goal context, semantic support/issues và digest của đúng payload gửi model.
  Projection deduplicate observations, không nâng giới hạn payload 48KB.
  V1 đọc được; legacy non-adaptive giữ đường cũ.
- Admission replay proof; API đưa binding từ admitted history tới M7, kiểm câu
  hỏi/local goal còn đúng. Không dùng dedup theo assertion để tráo proof mới
  sang entry cũ thiếu binding. Không thêm semantic verifier hoặc sửa renderer M7.
- Feedback chứa candidate/version/task IDs, obligations/checks/reason codes,
  goal/evidence refs, action/repairability. Chưa chạy repair loop.

## Live và giới hạn

| Probe | M5 → M6 → Ledger → M7 |
| --- | --- |
| BBS mới, chọn doanh thu nhỏ hơn giữa2024/2025→PAT cùng năm→PAT/revenue% | Fresh M5 chọn2024, join đúng, backend Calculator ra1,74%; một nhánh T3 lỗi `demand_source_unknown_or_not_fact`, nhưng T2 có proof cần thiết. M6 ban đầu dừng ở payload trùng lặp vượt48KB; sửa projection tổng quát, giữ nguyên gate. |
| ADC mới, chọn doanh thu lớn hơn giữa2020/2021→CFO cùng năm→CFO/revenue% | Fresh2calls; M5 `selection_domain_incomplete`, consumers blocked;0claims/0M6/0released. Không sửa Coordinator hoặc suy đoán nguồn thiếu. |
| BBS exact saved M5 → live M6 → persisted ledger/reload → M7 | Dùng nguyên `trace.financial_execution` của probe BBS mới, không viết lại claims/operands/selection/goals.1actual M6 call;2ACCEPT/G2–G3,1INVESTIGATE/G1;M7 phát hành2claims,9citations. Đây là live M6 trên saved M5, không gọi là fresh E2E PASS. |

Final trace:

| Candidate suffix | Truth | Goal support | Ledger/M7 |
| --- | --- | --- | --- |
| `789e744aabb5e9c3463ca41c` — doanh thu2024 | INVESTIGATE | không | Không admit/release;Qwen INSUFFICIENT dù source/selection replay PASS. False-negative còn lại. |
| `136b722bf0720e1ac143305a` — PAT/revenue2024=1,74% | ACCEPT | G3 | Entry `33593829…`;persist/reload và phát hành. Không bind G2 chỉ vì operands đúng. |
| `e805bb0abfeeea07f4519d8c` — PAT2024 | ACCEPT | G2 | Entry `1db8093e…`;persist/reload và phát hành. |

M7 giữ cảnh báo kỹ thuật của nhánh M5 lỗi và gap G1; không khẳng định trả lời đủ
câu hỏi. Source là refined JSON trang7 và anchor đơn vị/issuer trang1 của BBS2025;
giữ page-level/uncertain, không gọi PDF-verified hoặc chất lượng tài chính toàn bộ.
Không nới ACCEPT để cứu G1 hoặc hardcode theo câu hỏi.

Tổng **9actual Qwen calls/72.284known tokens**,0unknown usage, không transport
retry/Gemini/OCR/PDF. Một thử replay M5 cũ dừng vì request-local UUID/result digest
thay đổi; chỉ2responses cached và1M6 malformed JSON trong thử đó, không tính cache
là live calls, không giữ replay wrapper đó trong runner cuối. Final dùng nguyên
serialized M5, không remap digest. Dừng API sau probe final, không lặp thêm câu.

## Engineering và evidence local

- **51targeted PASS**: `test_evidence_obligations.py`3tests (mở rộng các assertions
  về arithmetic/formula và partial release), M6/V2/coordination24tests,
  ledger/fast-path24tests. Không full suite/CI/financial accuracy benchmark.
- Controls: goal thay text/kỳ/unit hoặc câu hỏi không reuse; wrong domain/source/
  join không ACCEPT; arithmetic đúng nhưng wrong goal không support; wrong formula
  semantic không ACCEPT; ledger v2 round-trip và M7 giữ phần chưa verify.
- Ruff/planning/diff PASS.179runtime hashes khớp receipt live M6,2saved semantic
  payloads khớp đúng rows gửi Qwen và2entries reload/admission PASS.57source JSON hashes của hai
  filings bất biến; final saved-M5 receipt giữ24BBS JSON. Không commit raw trace,
  corpus, normalized/canonical data hoặc API config.

Local root: `artifacts/evidence/M6-OBL-01/` tại worktree task.

- `live-v1/results/M6O-SEL-JOIN-01.json`: fresh M5 và lỗi payload ban đầu.
- `live-final/`: thử replay đã dừng, chỉ dùng làm lịch sử chẩn đoán.
- `live-release/results/M6O-SEL-JOIN-02.json`: fresh ADC, lỗi domain M5.
- `verify-release/saved-m5-input.json`: exact M5 từ fresh BBS và SHA nguồn trace.
- `verify-release/provider/001-request.json`, `001.json`: đúng M6 input/output live.
- `verify-release/ledger/verified-claims.json`:2admitted v2 entries, saved bindings.
- `verify-release/result.json`:M6 feedback/admission/reload/verified_requirements/M7.
- `verify-release/implementation.json`:runtime/source hashes; receipt publication
  bổ sung liên kết SHA commit với đúng runtime đã live, không chạy lại API.

Next action: chờ Owner/Tech Lead giao nhiệm vụ tiếp theo.
