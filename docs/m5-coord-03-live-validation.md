# M5-COORD-03 — Verification-Driven Feedback

**REVIEW, 17/11/2026**. Implementation
`bfe1e0b43de3e34d4fa3998fbbcb75364f35e99f` đã push main, remote SHA verified;
baseline `7cb4a03`.180runtime files trong commit khớp receipt controlled replay.
Worktree riêng giữ local edits ngoài task. Chỉ Tech Lead nghiệm thu DONE.

## Kết quả và implementation

Feedback M6 đã kích hoạt **một repair chỉ T4**, giữ T1/T2 và trạng thái lỗi cũ T3,
reuse **3 M6 histories** không đổi; một candidate revision2 qua M6 → persisted
Ledger v2 → M7. Bằng chứng positive cuối là **controlled live replay trên M5 output
thực đã lưu**, có cố ý làm sai một scalar candidate; không gọi là phục hồi tự nhiên.

- Routing giữ task/goal/evidence/action, dùng task ID của replay check hoặc owner
  của goal còn thiếu; selection/join có thể quay về producer trong dependency closure.
- Goal đã có M6 support hợp lệ không bị repair vì claim phụ thiếu binding hoặc một
  candidate khác bị từ chối. Lỗi source/proof còn ảnh hưởng descendant chưa đạt vẫn
  đóng frontier bảo thủ theo DAG. Không tuyên bố lineage tối thiểu theo từng operand.
- Tái dùng vòng thực thi Coordinator/Workspace, không gọi lại Supervisor hoặc mở
  task mới trong repair. Root cũng có thể demand-retrieve lại nguồn từ feedback.
  Evidence của specialist giữ selected observations và dependency closure.
- Result revision2 giữ input handle/version/digest, candidate mới có suffix `:r2`
  và lineage trong trace. Snapshot trước không bị mutation bởi workspace sau.
- M6 chỉ kiểm lại candidates mới/context thay đổi; history độc lập giữ nguyên.
  Không tự cấp ACCEPT/bindings, không sửa nguồn hay M7. Gateway/model thay được như cũ.
- Tối đa một repair/request. So proposal trước khi gọi lại M6; không có thay đổi thì
  dừng. Không tăng tập goals đã verify hoặc làm mất coverage cũ thì giữ frontier
  partial ban đầu. Call/deadline budget chung và unknown usage chặn repair tùy chọn.

## Live Qwen trên JSON/EF-EG

Ba câu hỏi mới, không đọc PDF/OCR/Gemini/Gold. Tổng **20actual API calls,
178.629known tokens, 1unknown usage** do timeout; không retry transport.
Budget toàn task28calls; đã dừng20. Fresh requests tối đa16calls/300giây;
controlled replay tối đa8calls/240giây, dùng4calls.

| Probe | Calls | Kết quả |
| --- | ---: | --- |
| BBS mới: revenue/PAT2025 → PAT/revenue%, CFO2024 độc lập | 5 | 3ACCEPT/G1,G2,G4 → M7 partial/15citations. T3 lỗi `demand_source_unknown_or_not_fact` trước candidate; không dựng feedback M6 cho lỗi đó. |
| ADC mới: chọn revenue nhỏ hơn → PAT/revenue%, CFO2021 độc lập | 0 | `requested_scope_unconfirmed`, dừng trước API/M5/M6. Cụm “Riêng …” trong câu hỏi bị scope resolver giữ lại; chưa sửa resolver ngoài scope. |
| BBS mới: chọn CFO lớn hơn có dấu → revenue cùng năm → revenue−CFO, PAT2025 độc lập | 11 | Bản frontier ban đầu kéo cả4tasks do binding thừa và candidate phụ lỗi; timeout/semantic payload limit, rollback giữ4ACCEPT/1ABSTAIN, M7 partial/18citations. Kết quả này dẫn tới sửa routing theo unmet goals; không tính là positive selective repair. |
| Controlled replay câu BBS cuối, cố ý đổi scalar PAT candidate thành999999999, giữ nguyên evidence | 4 | Final runtime: M6 ban đầu3ACCEPT/2ABSTAIN; feedback numeric/binding → chỉT4 revision2; reuse3histories; M6 cuối4ACCEPT/G1,G2,G4 →4entries v2 → M7 partial/4claims/18citations. |

Final replay dùng nguyên câu hỏi và nguồn thực đã lưu, không gọi lại planner,
không thay giá trị/source records. Fault chỉ nằm trong text của một candidate
trước M6, được ghi rõ trong `controlled-input.json`. Đây là kiểm tra phục hồi
có chèn lỗi, không phải accuracy benchmark hoặc một câu hỏi mới thứ tư.

## Giới hạn cần Tech Lead xem xét

G3 vẫn thiếu vì M5 không tạo được phép tính hợp lệ trước M6; không có feedback
claim để repair nhánh đó. Không tự mở retry cho lỗi kỹ thuật ngoài feedback M6.

**M6 còn false-positive semantic binding G2 trong probe BBS chọn năm**: selection
chọn2024 nhưng Qwen cấp G2 cho revenue2025 và cả gross-profit2025. Coordinator giữ
authority M6, không tự sửa verdict; saved bindings/admission hợp lệ về cơ chế
không chứng minh nghĩa tài chính đúng. Replay reuse các verdict đó, nên kết quả
positive chỉ chứng minh selective repair và preservation, không nghiệm thu chất
lượng goal semantics/QA. M7 không được sửa trong task này. Provenance vẫn JSON-only,
giữ page-level/uncertain; chưa đối chiếu PDF.

## Kiểm tra và trace

- 31targeted tests PASS trên final runtime:3controls mới và28compatibility
  Coordinator/evidence obligations/V2/Lite. Controls gồm routing5loại lỗi,
  binding về đúng goal owner, không repair goal đã covered, reuse history,
  revision/digest, Ledger/M7, one-round/budget/no-progress và giữ partial khi repair lỗi.
- Một smoke deterministic cũ `test_pipeline_flag_keeps_existing_m6_m7_and_opt_out`
  fail vì ACCEPT thiếu binding; đã xác minh cũng fail trên baseline `7cb4a03`.
  Không xóa/sửa test hoặc nới M6 để phát hành. Không full suite/CI/benchmark.
- Ruff lint/format, planning checker và diff check;4saved ledger entries reload
  và `build_verified_claim(history)` round-trip PASS.180runtime hashes khớp receipt
  controlled replay;57source JSON hashes của hai filings bất biến.

Artifacts local, không commit corpus/config/secrets/raw traces:

- `artifacts/evidence/M5-COORD-03/live-v1/results/`: hai câu mới đầu.
- `artifacts/evidence/M5-COORD-03/live-final/results/M5C3-BBS-03.json`: natural
  run trước sửa frontier, before/after và rollback đầy đủ.
- `artifacts/evidence/M5-COORD-03/controlled-replay/controlled-input.json`: fault
  và SHA của saved input; `provider/001…004`: M6 → demand → specialist → M6 live.
- `artifacts/evidence/M5-COORD-03/controlled-replay/result.json`: final
  `trace.adaptive_rounds[0]` chứa feedback/routed issues, task/result snapshots,
  tools/evidence, candidate lineage, M6 trước/sau, reused IDs; trace M7 có bindings/citations.
- `artifacts/evidence/M5-COORD-03/controlled-replay/ledger/verified-claims.json`:
 4entries v2; `implementation.json`: runtime/source receipt; `publication.json`:
 implementation SHA đã đối chiếu hashes và thông tin publish.
- `artifacts/evidence/M5-COORD-03/final-targeted-tests.log`: final targeted run.

Next action: Tech Lead review selective-repair evidence và các giới hạn M6/G3 trước nghiệm thu.
