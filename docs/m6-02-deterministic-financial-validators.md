# M6-02 — Deterministic Financial Validators

Status: **IN_PROGRESS**; Owner giao03/11/2026, baseline main/origin
`51292cf0317b8019bdeb6cb7610d5e33818a5d2d`. M6-01 đã DONE.
Implementation chưa commit; CI exact-SHA chưa chạy. Không gọi Gemini/OCR.

## API và ranh giới

Public API: `DeterministicFinancialValidator(catalog: SnapshotCatalog)` và
`validate(batch: VerificationInput) -> ValidationResult` trong package verification.
Caller hydrate canonical facts, graph, source/scope reviews và approved policies
độc lập với candidate. Constructor copy catalog; input/output không sửa nguồn.
Không I/O ngầm, LLM, pipeline execution hoặc financial decision.

`ValidationCheck` kế thừa `VerificationFinding` M6-01, bổ sung check ID, status,
reason code, expected/observed và source citations. `kind` xác định nhóm kiểm tra;
status mới cho biết có mismatch hay không, kể cả khi tên kind chứa từ mismatch.
Trace mismatch giữ expected/observed full calculation trace; references/citations
giữ source/lineage identity. Candidate ID và toàn bộ conflict candidates được giữ.

| Status | Ý nghĩa |
| --- | --- |
| `pass` | Check cụ thể đã thực hiện và khớp nguồn độc lập |
| `fail` | Có sai lệch cụ thể so với nguồn/context đã xác định |
| `undetermined` | Thiếu nguồn, binding mơ hồ hoặc context chưa resolved |
| `not_applicable` | Check không áp dụng |

Không có aggregate verification verdict: một claim có thể numeric PASS đồng thời
scope UNDETERMINED. `financial_fact_verified` luôn false; candidates giữ pending,
decision null. Không ghi ledger hoặc chọn winner khi conflict.

## Những gì kiểm được

| Nhóm | Kiểm tra deterministic |
| --- | --- |
| Fact | Exact observation qua M4 retrieval; company/document/snapshot/period, canonical item, currency/unit/scale, prose value và supporting copy so với canonical |
| Metric | Replay `FinancialCalculator` bằng metric ID độc lập; ba formulas gross_margin/debt_to_assets/revenue_yoy, approval/version/digest, eligibility, Decimal result/rounding, roles/values/context và full trace/lineage |
| Provenance | Candidate citations phải khớp source citations độc lập; thiếu lineage/citations giữ unresolved, source identity sai bị FAIL; giữ nguyên page-level |
| Quality | Reuse M3 consistency và M4 source/quality gates, preserve caveats/limitations; insufficient/conflicted không trở thành verified |
| Conflict | Giữ conflict ID và tất cả candidate IDs; numeric PASS không giải quyết conflict |
| Interpretation | Chỉ kiểm numeric assertion có binding rõ; semantic conclusion luôn chờ M6-04 |

Numeric grammar nhận các mẫu fact/metric được M5 render: label đã có, `kỳ/năm/tại
ngày`, `là/đạt`, số âm/dấu thập phân, nhóm nghìn Việt Nam, %, VND/đồng/USD và scale
hiện có. Có các arithmetic paraphrases gross margin/debt-to-assets theo100 đồng,
revenue YoY tăng/giảm với prior period; ngoài grammar trả undetermined.
Không làm general NLP hoặc suy giá trị từ câu có nhiều assertions không phân giải.
Không tự convert scale hoặc làm tròn fact để khớp. Unit/scale sai có check riêng,
kể cả khi hai mantissa bằng nhau. Không tạo ROE/Current Ratio/FCF hoặc assumptions mới.

Scope overlay chỉ áp dụng exact document/snapshot: 2024 separate không truyền sang
năm khác; unknown scope là caveat cho single-document fact, không chặn numeric check.
Requested/stated scope trái nguồn resolved bị FAIL. Snapshot luôn explicit qua exact
reference; original/recovery2022 không tự chọn. Cross-document refs trả D03-B10
comparability blocked; không chứng minh comparability bằng cách so số.

## Evaluation và cách diễn giải

Runner: `scripts/evaluate_m6_02_validators.py --output artifacts/evidence/M6-02-validation-final`
(chạy bằng Python trong `.venv`). Chỉ đọc artifacts; output phải mới, dưới
`artifacts/evidence/`, không ghi đè. Results/raw JSON tiếp tục ignored.

Final:72 claim rows,30 persisted-source candidates (18 approved metrics và
12 facts B02/B03 trên2021–2025/original và recovery2022),26 claims từ21 saved
M6-01 batches,16 synthetic controls. Mỗi giá trị expected lấy trực tiếp canonical
fact hoặc independent Decimal arithmetic từ canonical operands; không dùng parser
hoặc arithmetic của validator làm oracle; có oracle cho từng saved claim.

Phân nhóm riêng: persisted-source candidates, M5 mock generation trên BBS,
saved Gemini response replay, saved replay có injection, upstream synthetic controls,
và corruption mới. Đây là agreement với persisted sources và sensitivity controls;
không phải financial verification accuracy tổng quát hoặc independent PDF gold.

| Nguồn candidate | Claim rows |
| --- | ---: |
| Render từ canonical/M4 persisted, không phải Gemini | 30 |
| M5 mock generation trên BBS persisted | 14 |
| Saved Gemini response replay | 3 |
| Saved replay kèm synthetic injection | 2 |
| Upstream synthetic controls trên BBS persisted | 7 |
| Corruption/uncertainty controls mới | 16 |

Final numeric statuses (đơn vị đếm là claim row; không phải acceptance decision):

| Claim kind | PASS | FAIL | UNDETERMINED |
| --- | ---: | ---: | ---: |
| fact | 37 | 1 | 2 |
| approved_metric | 28 | 1 | 0 |
| supported_interpretation | 3 | 0 | 0 |

Numeric-only table không phản ánh mọi lỗi: controls sai period/document/snapshot,
scope, currency/item, formula digest, result trace, operands hoặc lineage có FAIL
ở check tương ứng dù numeric có thể PASS.16 controls gồm12 proven mismatch và4
missing/unknown/interpretation cases. Conflicts từ accepted saved batch được giữ.
Final:924 check PASS,18 FAIL,73 UNDETERMINED,252 NOT_APPLICABLE.72/72 claim rows
được kiểm tra, mọi assertion kỳ vọng đạt; có21 saved batches, sáu batch rỗng không
tạo claims.12.753 protected hashes unchanged, bao gồm Web local, accepted artifacts
và initial outputs; original/recovery selection thiếu snapshot vẫn ambiguous.
Có13 claim rows chứa ít nhất một FAIL (có thể cùng chứa PASS/UNDETERMINED),
không quy đổi số này thành quyết định verification.

## Source limitations và fixes trong phạm vi

- Source independence: không so candidate.value với một candidate copy khác;
  fact lookup và calculator replay lấy từ canonical catalog caller hydrate riêng.
- Scope unresolved không phải lý do bỏ numeric/context checks đã đủ bằng chứng.
  Scope có check riêng, không fake PASS hoặc tự suy separate từ2024.
- M4 request có thể có optional document/snapshot guards hoặc chỉ metric ID;
  so guards như ràng buộc AND, không coi representation khác nhau là formula lỗi.
- Thiếu canonical fields/nested lineage/result trả undetermined; known differences
  vẫn FAIL. Usable-with-caveat giữ caveat, không tự fail hoặc nâng provenance.
- Ngữ pháp hẹp giúp tránh numeric PASS khi không bind chắc con số với financial item;
  câu mơ hồ, scope chưa rõ, semantic support và financial reasoning còn cần Critics.

M6-03 vẫn cần semantic citation support; M6-04 đánh giá conclusion/sign/causal
reasoning ngoài phần arithmetic đã bind; M6-05 mới quyết định và M6-06 mới ghi ledger.
Persisted source-review/quality/page limitations và D03-B10 còn nguyên.

## Engineering evidence

Local:30 validator/numeric/context/conflict tests PASS;78 compatibility tests
(M4 calculator, M6-01 contracts/serialization, M5 orchestrator) PASS; một warning
có sẵn từ M4 test cố tình đưa invalid Decimal. Không chạy full M1–M5 benchmark.
Initial12.683 và final12.753 protected hashes unchanged. Ruff file đã sửa,
planning checker101tasks và git diff --check PASS. CI exact-SHA sẽ cập nhật sau
commit/push được giao; không gán local results thành CI.

Next action: xác minh exact-SHA CI để bàn giao REVIEW.
