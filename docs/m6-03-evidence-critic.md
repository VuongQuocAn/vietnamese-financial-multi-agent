# M6-03 — Evidence Critic

Status: **REVIEW**; implementation đã push main và exact-SHA CI SUCCESS. Owner giao04/11/2026,
baseline main/origin5346644; M6-01/M6-02 DONE. Brief cho phép commit/push main.

## API và phạm vi

`EvidenceCritic(catalog, gateway=None, model=None, max_semantic_calls=6)` nhận
`assess(batch: VerificationInput, validation: ValidationResult)` và trả
`EvidenceCriticResult`. Caller hydrate canonical SnapshotCatalog độc lập với
candidate; Critic không đọc filesystem/PDF hoặc chạy calculator/validators lại.

Các trạng thái supported/partially_supported/unsupported/insufficient_evidence
mô tả evidence support. Không ACCEPT/REVISE/INVESTIGATE/ABSTAIN, financial logic
critic hoặc ledger; CandidateClaim vẫn pending, decision=null, verified=false.
Supported có nghĩa được nguồn hiện có hỗ trợ trong phạm vi đã đánh giá;
không có nghĩa nguồn tài chính đã được kiểm toán độc lập.

## Deterministic assessment

- Kiểm source SHA, exact candidate set/kind, conflicts, observed context/numeric
  và relevant reference bindings. Validation result mới có optional
  `verification_input_sha256` để bind toàn bộ M6 input, gồm prose/calculation.
- Accepted M6-02 artifacts cũ không bị sửa. Caller phải truyền
  `validated_batch=original_paired_input`; mismatch hoặc thiếu binding trả
  structured error/insufficient. Đây là caller attestation cho legacy pairing,
  không phải chữ ký hoặc independent cryptographic proof của artifacts cũ.
- Tái sử dụng `EvidenceRetrievalTools.get_evidence_sources` và
  `get_metric_evidence_lineage`; typed canonical facts, text/table và EF-EG lineage.
  Cache exact references trên catalog snapshot riêng, trả deep copies.
- Citation phải thuộc nguồn đã resolve, đúng document/snapshot/page/provenance;
  giữ source anchors nguyên bản. Page-level hợp lệ không bị đòi cell bounding box.
- Numeric/formula/context/provenance FAIL giữ unsupported, không gọi Gemini để
  đảo kết quả. UNDETERMINED không tự thành unsupported. Missing source, requested
  scope chưa resolve hoặc cross-document D03-B10 giữ insufficient với reason.
- Numeric prefix được tách khỏi tail chưa parse. Numeric PASS chỉ hỗ trợ prefix
  khi các context/quality/source/formula/lineage checks liên quan cũng PASS.
  Diễn giải như cải thiện hiệu quả phải đánh giá riêng; arithmetic paraphrase
  nằm trọn ngữ pháp M6-02 có thể không cần Gemini.
- Conflicts còn cả hai phía và conflict IDs, không chọn winner. Partial upstream
  vẫn đánh giá các claims hiện có. Một claim lỗi không làm mất claims khác.

## Semantic assessment qua Gateway

Default Gemini `gemini-3.5-flash-lite`, đổi model bằng constructor. Chỉ gọi shared
Gateway một lần cho mỗi claim còn semantic assertions; không retry/debate.
Giới hạn0–6 calls trên instance, gồm failure; evaluator reserve disk slots để
tổng actual calls toàn task, kể cả retest/interruption, không vượt6.
Credentials dùng composition hiện có, không đọc/in key trong Critic.

Prompt chứa relevant financial context, source-derived excerpts/structured facts,
exact references/citation IDs, findings M6-02 và caveats. Không conversation history,
unrelated statements hoặc toàn PDF. Tối đa16 references/claim,6000 ký tự/text/table,
16 semantic spans; truncation có caveat. Khi chỉ có anchor không có content thì
không yêu cầu Gemini đoán nội dung PDF.

Output JSON có schema Pydantic trong prompt và validate local với extra=forbid.
Model chỉ trả candidate_id, assertion_id, status, evidence_ids và các reason/missing
codes hữu hạn. Content/assertions/values/formulas/citations/quality/decision không
phải trường cho phép model sinh hoặc sửa. Validate exact assertion set, candidate,
allowed evidence set và consistency status/reason/missing; numeric assertions đã
khóa không nằm trong output set. Malformed/failed response giữ structured error và
undetermined semantic support; phần numeric đã hỗ trợ vẫn được giữ.

Kết quả giữ per-assertion scope, citations/source anchors, document/snapshot/period,
provenance/quality/source-review limitations, M6-02 finding IDs, model provenance,
usage/cost metadata và latency theo stage. Gemini assessment không là nguồn mới.
Financial logic được ghi rõ deferred to M6-04.

## Evaluation và giới hạn bằng chứng

Annotations tại `evaluation/m6-03-scenarios.json` được gán từ canonical/quality/gates
và nội dung candidate, độc lập với output Critic. Không independent human PDF gold.
Evaluator dùng30 persisted-source renderings và21 accepted M6-01 batches cùng
saved M6-02 results; không chạy lại accepted checks. Chỉ12 controls mới chạy
validator một lần để có kết quả phù hợp input đã mutate.

Lượt đầu dừng để sửa việc hydrate catalog lặp theo case; partial artifacts ở
`artifacts/evidence/M6-03-offline-initial`, zero live calls. Lượt hoàn chỉnh ở
`artifacts/evidence/M6-03-offline`. E35 ban đầu được gán nhầm partial vì chưa xét
supporting copy bị synthetic corruption. Saved M6-02 đã có supporting_fact FAIL
do lệch một đơn vị so canonical: annotation đúng là unsupported, không ghi winner.
`--rescore-from` chấm lại cùng outputs theo correction có source hash, không thực
thi Critic/M6-02/Gemini lại; giữ nguyên output và expected ban đầu.

Kết quả offline cuối cùng:63/63 cases,68 claim assessments (41facts,24metrics,
3interpretations). Trước correction annotation E35 là62/63; không có runtime fix
để biến case này thành PASS. Summary đã chấm lại ở
`artifacts/evidence/M6-03-offline-scored/summary.json`, bind hashes tới output gốc.

| Nhóm | Cases | Phân loại nguồn |
| --- | ---: | --- |
| Persisted-source renderings | 30 | 18 approved calculations +12 canonical facts; không Gemini-generated |
| Saved BBS mock-generated M5 candidates | 13 | Giữ nguồn thật, generation là mock |
| Saved M5 synthetic controls +12 controls mới | 18 | Tách riêng khỏi natural persisted cases |
| Saved Gemini-response replay | 1 | Candidate đã lưu, semantic Critic offline dùng mock |
| Saved replay với synthetic missing CFO | 1 | Không natural source failure |

| Evidence support | Assessments |
| --- | ---: |
| supported | 54 |
| partially_supported | 1 |
| unsupported | 9 |
| insufficient_evidence | 4 |

65 assessments deterministic,3 combined với mock semantic response; zero actual
Gemini offline. Three semantic outputs hợp schema/allowed evidence, không coi mock
agreement là empirical Gemini accuracy.12/12 controls mới gồm value/document/
snapshot/period/currency/scope/formula/citation sai, source thiếu, cross-document,
multi-assertion interpretation và stale ValidationResult. Các saved batches còn giữ
partial orchestration/no-candidate/conflicts/original-recovery ambiguity.

66/68 assessments giữ page_level_only,58 giữ scope unresolved,18 giữ source review
unverified; hai conflict candidates giữ conflict limitation.1.394 citation occurrences
trong resolved contexts đều page-level, không nâng thành cell-level. Một CFO source
không đủ quality giữ insufficient.13.060 protected hashes ở live run khớp before/after,
gồm Web local, raw/processed và accepted artifacts; offline12.858 hashes cũng khớp.

## Bounded Gemini pilot

Fresh Critic calls trên hai semantic candidates tự nhiên đã có trong M6-01: E06
diễn giải financing cash flow âm và saved replay-E11 diễn giải operating cash flow
dương. Chỉ có hai cases thích hợp trong accepted conversion set nên giảm từ mức
gợi ý3–6, không tạo workload semantic giả. Candidate origin M5 của E06 là mock;
replay-E11 là saved Gemini-generated candidate. Cả hai Critic assessments là
fresh live, không phải saved-response replay của Critic.

| Case | Expected / fresh semantic result | Actual tokens | Gateway latency |
| --- | --- | ---: | ---: |
| E06 | supported / supported | 4.450 | 1.268ms |
| replay-E11 | supported / supported | 4.542 | 838ms |

2 correct,0 incorrect,0 undetermined theo expected source-bound sign restatements;
2actual calls/8.992tokens, không retry/targeted retest hoặc live replay.3 claims
numeric còn lại trong hai batches được đánh giá deterministic;5/5 claim assessments
supported. Không cộng5 claims thành5 Gemini calls hoặc gộp mock/live success rates.
Model requested/provider-reported đều gemini-3.5-flash-lite; effective_model=null
theo Gateway metadata. Cost unknown, không tự suy giá. Lưu exact requests/responses,
citations/trace/usage/latency tại ignored `artifacts/evidence/M6-03-live`;
`M6-03-call-budget` có2 reserved attempts, cap6 cho cả task.

Semantic coverage thực nghiệm chỉ hai sign restatements; chưa có fresh B09
interpretation, causal/comparison uncertainty hoặc independent PDF annotations.
Text/table semantic retrieval được unit-test bằng synthetic source, không tuyên bố
B09/PDF extraction accuracy hoặc full claim verification accuracy. Numeric PASS
kèm kết luận cải thiện chưa có nguồn được kiểm offline bằng control riêng.

## Engineering và bàn giao

Engineering local:144 focused/compatibility PASS (Critic19, M6-02, M6-01,
M4 retrieval/calculator và M5 orchestration);19 Critic tests PASS sau cache change.
Một warning có sẵn do M4 test cố tình đưa invalid Decimal. Ruff/planning/diff PASS.
Không chạy full OCR/extraction/M1–M5 benchmark. Root causes trong phạm vi là
catalog hydration lặp (đã reuse cache trên immutable snapshot) và annotation E35
sai (đã sửa theo saved independent validator). Live không phát hiện P0/P1 cần sửa.
Implementation `198234a62d5cae8d4878eb249dac729b013c55c6` đã push trực tiếp main,
origin/main khớp sau push. [CI41745959202](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41745959202)
completed/SUCCESS đúng implementation SHA; Python3.12 và Web smoke SUCCESS,
full regression SKIPPED. Đã xác minh run metadata và từng job/step.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI cho checkpoint SHA.

Next action: Tech Lead review M6-03.
