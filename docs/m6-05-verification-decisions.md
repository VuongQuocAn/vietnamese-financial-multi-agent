# M6-05 — Verification Decisions & Bounded Verification Loop

Owner giao04/11/2026, baseline main/origin
`ce7b9c32966d37dbd34d18c75f9c7d5145a31b44`; M6-01–04 đã DONE.
Implementation đang xác minh; chưa commit/CI. Chỉ task M6-05, chưa ledger M6-06.

## API và contracts

`VerificationJudge.decide(batch, validation, evidence, logic, **original_pairing)`
trả `VerificationDecisionResult`. Không gọi Gateway, retrieval, calculator hoặc OCR;
không ghi quyết định vào accepted `CandidateClaim` và không sửa input/Critic results.

Mỗi `VerificationDecisionRecord` giữ full original claim/provenance/calculation,
typed validation/evidence/logic assessment nguyên vẹn, references/citations,
reason codes, caveats/limitations, blockers, proposal/investigation requirements.
Trace chứa source/input/validation/evidence/logic SHA256, policy version
`verification_decisions_v1`, required checks và passed gates. Serialization round-trip
và repeat cùng inputs được kiểm tra exact; không dùng latency mới làm decision input.

## Policy matrix

| Gate/tình huống | Kết quả/chính sách |
| --- | --- |
| Source SHA sai định dạng; input/result digest, IDs/kinds/content/conflicts/assertions/references không khớp | INVESTIGATE với structured errors và yêu cầu fresh paired inputs |
| Unresolved candidate conflict hoặc canonical source inconsistency | INVESTIGATE; giữ cả hai phía, không winner hoặc numeric correction |
| Cross-document/original-recovery mix, requested reporting scope chưa rõ | INVESTIGATE; D03-B10 vẫn blocked |
| Numeric FAIL duy nhất; các required checks khác PASS, exact canonical source, wording một số rõ ràng | REVISE với đúng canonical expected value, chưa ACCEPT |
| Formula/context/provenance FAIL hoặc numeric mismatch chưa sửa an toàn | INVESTIGATE exact findings/references |
| Required check thiếu/undetermined và có reference cần truy xuất/review | INVESTIGATE; PASS khác không ghi đè |
| Required evidence không có và không có reference/recovery cụ thể | ABSTAIN |
| Factual prefix đã supported, nhưng kết luận chưa supported/logic inconsistent/insufficient/provider error | REVISE, chỉ giữ numeric prefix; vẫn giữ source caveats |
| Không còn safe prefix; semantic assessment bắt buộc thất bại | ABSTAIN; lỗi provider không phải bằng chứng claim sai |
| Toàn bộ required financial checks PASS, toàn claim supported, applicable reasoning consistent | ACCEPT trong phạm vi nguồn, có thể kèm caveats |

Identity gate trước quyết định tài chính; mọi financial FAIL vẫn có trong blockers.
Conflict/comparability chặn sửa số dù đồng thời có numeric FAIL. Sau các gate này
mới xét repairability, evidence/logic và eligibility ACCEPT; không dùng quy tắc
“một FAIL → luôn ABSTAIN”. Không coi insufficient_context là inconsistent.

Required PASS chung: `handoff_structure`, `numeric`, `item`, `unit_scale`,
`context`, `provenance`, `quality`. Fact thêm `fact_reference`, `source_structure`,
`canonical_currency`, `supporting_fact`. Metric thêm `formula`, `calculation_request`,
`calculation_result`, `calculation_trace`, `calculation_lineage`, `operand_references`,
`supporting_metric`. Interpretation dùng nhóm premises tương ứng fact/metric,
thêm evidence support toàn bộ assertions và logic của các assertions áp dụng.
Mọi occurrence của check bắt buộc đều phải PASS, không lấy PASS cuối cùng.

Các checks `candidate_conflict`, `cross_document`, `reporting_scope` phải hiện diện.
Single-document/no-conflict có thể not_applicable. Reporting scope undetermined
được giữ như caveat khi không khẳng định/yêu cầu scope chưa xác định. Những
undetermined khác ngoài `semantic_conclusion` vẫn chặn ACCEPT; semantic conclusion
được quyết định qua cả hai Critics. Numeric-only logic được phép not_applicable;
reasoning thực sự không được gắn nhãn này để né đánh giá.

`usable_with_caveat`, `source_review_unverified`, page-level provenance và unknown
reporting scope không tự đồng nghĩa financial falsity. Batch partial/blocked không
tạo global abstention; từng candidate có gate riêng. Batch trống không tạo claim.

Legacy M6-02/03 không có full binding chỉ được dùng với `validated_batch`,
`evidence_batch`, `evidence_validation` gốc qua cơ chế M6-04 hiện có. Không backfill
digest vào artifact hoặc coi caller pairing là chữ ký xác thực độc lập. M6-04 phải
bind đúng các results thực tế này; result stale dẫn tới INVESTIGATE.

## Bounded loop

```python
loop = BoundedVerificationLoop()
history = loop.start(batch, validation, evidence, logic, candidate_id=candidate_id)
revision = loop.propose(history)  # chỉ khi attempt 0 là REVISE có safe proposal
child = revision.batch
fresh_validation = validator.validate(child)
fresh_evidence = evidence_critic.assess(child, fresh_validation)
fresh_logic = logic_critic.assess(child, fresh_validation, fresh_evidence)
outcome = loop.submit(history, revision, fresh_validation, fresh_evidence, fresh_logic)
```

Controller nhận fresh results từ caller; không tự điều phối LLM/M5. Proposal chỉ
thay content, kind và child ID; không đổi document/snapshot/formula/operands/sources/
citations/caveats/missing information. Prefix có thể hạ interpretation về fact/metric.
Không ghép mệnh đề mới. Numeric correction chỉ thay đúng một parser-bound token,
không tính công thức hay tự viết con số khác canonical expected value.

Child ID `revision:<digest>` khác original. `RevisionInput.parent_candidate_id` và
`parent_decision_sha256` bind toàn bộ original decision; attempt 1 cũng chứa parent ID.
Accepted M6-01 yêu cầu candidate ID bằng `provenance.m5_candidate_id`, nên child dùng
ID mới ở field đó; full original M5 ID/provenance ở attempt 0 và parent linkage,
còn origins/roles/references của child giữ nguyên. Không sửa accepted contract.

Chỉ submit đúng proposal cùng lineage/source mới được judge lại. Submission sai
parent/source/caveat trả ABSTAIN với reason; stale results không ACCEPT dù source
SHA vẫn giống. Một attempt mới kết thúc budget; REVISE lần nữa thành ABSTAIN,
INVESTIGATE/ABSTAIN giữ nguyên, lần submit thứ ba hoặc start từ child ID bị từ chối.
Controller giữ budget đã dùng trong bộ nhớ theo source/candidate, nên gửi lại cả
history attempt 0 cũ hoặc start lại original trong cùng controller cũng bị từ chối.
Không có persistence hoặc ledger; caller giữ history và controller cho một phiên.

## Evaluation và validation

Oracle cố định trước execution tại `evaluation/m6-05-scenarios.json`; SHA256
`1190e69fefdb4a35fb05a2633e8bf529d313655601c74611359cac4282ca3289`.
Nguồn là saved M6-04 offline-final-v2 với original paired M6-02/03, hai saved live
attempt sets và accepted canonical BBS2021–2025/recovery2022 cho controls/revisions.
Không chạy lại Critics cho saved cases. Chỉ controls và child candidates chạy fresh
M6-02/03/04 bằng APIs thật, không Gateway/mock replacement cho numeric revisions.

```powershell
.venv\Scripts\python.exe scripts/evaluate_m6_05_decisions.py --output artifacts/evidence/M6-05-decisions-initial
```

Output directory phải mới; không ghi đè. Full results/trace/oracle/hashes chỉ lưu
ở ignored artifacts. Run initial tại `artifacts/evidence/M6-05-decisions-initial/`:
94/94 batches khớp oracle, cộng6/6 bounded-loop scenarios;107 candidate decisions
gồm các final child decisions. Có30 persisted-source BBS renderings (18metrics,
12facts),21 saved M5/M6 batches (26claims),20 saved reasoning controls,
6 saved Gemini logic attempts và17 decision controls mới. Completed82/partial7/
clarification_required1/blocked2/failed2 batches; năm batches trống giữ trống.

| Expected \ Actual | ACCEPT | REVISE | INVESTIGATE | ABSTAIN |
| --- | ---: | ---: | ---: | ---: |
| ACCEPT | 57 | 0 | 0 | 0 |
| REVISE | 0 | 24 | 0 | 0 |
| INVESTIGATE | 0 | 0 | 23 | 0 |
| ABSTAIN | 0 | 0 | 0 | 3 |

Unsafe ACCEPT0/50 expected non-ACCEPT decisions; false abstention0/57 expected
ACCEPT (0%), unnecessary investigation0/57. Đây là precision theo policy oracle
đã pin, không phải independent financial accuracy. Fact `fact-02-b03` kỳ2022 có
direct_qa quality `insufficient`, vì vậy INVESTIGATE; không nâng thành caveat đủ
điều kiện ACCEPT.29/30 persisted renderings còn lại được ACCEPT. Hai conflict
candidates saved-E35 đều INVESTIGATE, giữ nguyên cả hai và conflict IDs.

| Bounded scenario | Final decision |
| --- | --- |
| Exact numeric correction + fresh M6-02/03/04 | ACCEPT child |
| Supported prefix + fresh M6-02/03/04 | ACCEPT child |
| Dùng upstream results cũ | INVESTIGATE |
| Fresh pass nhưng canonical facts không còn đủ | INVESTIGATE |
| Đổi snapshot | ABSTAIN |
| Đổi parent | ABSTAIN |

Mỗi history chứa attempt0/1; initial REVISE không tự thành ACCEPT. Source/input/
result digests, original provenance, nested upstream traces và caveats được đối
chiếu exact/round-trip.14.058 hashes của run (14.057 baseline protected files
cộng preflight receipt) unchanged, gồm Web local/accepted artifacts.0 Gemini/OCR.

Root cause của control snapshot mới: initial lấy base2025 và thêm original2022,
chỉ kiểm generic cross-document mix. Đã sửa evaluator dùng đúng cặp original/
recovery2022 từ accepted artifact; expected INVESTIGATE và oracle SHA không đổi.
Targeted final2/2 PASS ở `artifacts/evidence/M6-05-targeted-final/`: đúng cặp2022
trả INVESTIGATE; real-source prefix child fresh ACCEPT và old-history/restart
original bị từ chối.14.556 hashes unchanged, gồm toàn bộ run initial. Không ghi
đè initial; đây là initial94/94 + targeted2/2, không phải fresh full94 rerun sau fix.
Không chạy lại toàn bộ Critics cho các cases đã PASS. Oracle SHA vẫn nguyên.

Local:31 Judge/loop tests PASS;156 M6-01–04/M4-calculator/M5-orchestrator
compatibility PASS. Một warning có sẵn từ calculator invalid-decimal control.
Initial3 failures do unsupported tail bỏ dấu câu cuối trong proposal; đã giữ exact
đoạn tail gốc,31/31 PASS sau fix; không thay oracle để khớp implementation.
Review bổ sung chặn replay history cũ để vượt budget trong cùng controller;
7 targeted bounded tests PASS sau fix, gồm gửi lại history cũ và restart original.

Đây là persisted-source renderings, M5 mock-generated claims, saved Gemini claims,
synthetic controls và revised candidates được phân loại riêng trong summary.
Agreement theo policy oracle không phải independent PDF gold, full financial
verification accuracy hoặc đánh giá lợi ích Multi-Agent end-to-end. ACCEPT chỉ
xác nhận claim trong phạm vi nguồn/policy hiện tại, không phải kiểm toán độc lập.

Next action: hoàn tất targeted validation và xác minh CI đúng implementation SHA.
