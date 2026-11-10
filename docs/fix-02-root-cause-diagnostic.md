# FIX-02 — Root Cause Diagnostic & Latency Profiling

Ngày 09/11/2026; diagnostic-only. **FIX-02 REVIEW — WAITING FOR TECH LEAD DECISION**
là trạng thái lúc bàn giao diagnostic. Owner/Tech Lead đã giao remediation ngày
10/11/2026; xem [kết quả tiếp theo](fix-02-adaptive-llm-agents.md#correctness--performance-remediation--10112026).
Không sửa runtime, prompt, policy, claims, dữ liệu nguồn hoặc Ledger đã có; không gọi
Gemini/network, không chạy lại bộ 40 câu hay full regression trong phiên diagnostic.
Bản diagnostic được đưa vào checkpoint remediation, giữ nguyên evidence09/11.

## 1. Executive Summary

Q21 không thiếu PAT/CFO: hai nguồn đã retrieval và bound. Hai analysis bị chặn vì
hai nguyên nhân khác nhau: semantic support chỉ một phần ở Profitability; regex
formula chặn cả lời thừa nhận **chưa đủ cơ sở tính tỷ lệ** ở Cash Flow. Native M6
giữ các quyết định này; Judge PASS bỏ sót coverage. M7 sử dụng đủ ba claim ACCEPT
duy nhất, nhưng thiếu hai interpretation requirements.

Q11 tính được gross_margin, M6 ACCEPT và M7 dùng metric. Pipeline biến hai
`find_financial_facts` prerequisites thành answer targets độc lập. Không có hai
fact claims độc lập nên output PARTIAL dù mục tiêu người dùng đã được đáp ứng.

F08 có lỗi generation JSON ở **Evidence Critic**, không phải JSON của Semantic
Judge: property `_missing` không được quote. RequestGateway truyền failure này
sang các calls sau, làm AdaptiveJudge trả JUDGE_ERROR mà không gọi provider.

Q11 chỉ dành 2,753s cho Gateway/provider trong 100,825s. Supervisor 20,113s,
M6 6,755s nằm trong M5 64,347s. Ngoài các stage có tên còn 25,842s trong pipeline;
M5 cũng còn 29,704s chưa được timer con bao phủ. Offline profiler xác nhận ba
hotspots: deep copies149,015s, metric/lineage reassessment35,160s và schema-path
generation23,017s inclusive. Đây là số replay có profiler overhead, không phải
phân bổ thời gian live chính xác; xem mục6.

## 2. Runtime và evidence

- HEAD/branch tại bắt đầu: `2a3d82ba59750add94731e82a67db386fd96921f`, `main`.
  `git diff 321f09e HEAD` chỉ có docs/planning; runtime implementation được đo là
  `321f09e91cd4e32bcfcb0584d84f70d5c31e13e4`.
- Ký hiệu **P** dưới đây: `artifacts/evidence/FIX-02/review-completion/proof-binding-live/`.
  `P/results.json` có đúng năm ca; `P/freeze.json`, `P/integrity.json`,
  `P/provider-attempts.json`, `P/provider/*.json`, `P/runtime/src/`,
  `P/ledger/verified-claims.json` là evidence gốc. Không giả định tên `live` đồng
  nghĩa cùng implementation: lượt `review-completion/live/` là lượt trước.
- Đã đối chiếu toàn bộ runtime files với manifest: khớp. Kiểm tra lại 414
  protected inputs: nguyên hash. Reference vẫn được đối chiếu với freeze.
- Baseline: `artifacts/evidence/E2E-02/turns/Q21.json`, `turns/Q11.json`,
  freeze/runtime SHA `39d796acba7c9eebc9ca74c6c6f564238910d3b5`; deterministic,
  zero provider calls, startup excluded.
- Evidence mới riêng tại **D** = `artifacts/evidence/FIX-02/diagnostic/`:
  `profile_q11.py`, `q11.prof`, `q11-profile.txt`, `q11-replay.json`,
  `live-timing-summary.json`, `targeted-checks.json`, `evidence-hashes.json`,
  `final-integrity.json`. Các file này được ignore; không commit private
  outputs/PDF text. Replay dùng source archive P, response Planner đã lưu,
  Ledger mới ở D; không thay P hoặc nguồn accepted.
- Workspace có pending GEN-01a/CHAT/planning/Web từ trước. Không stage/commit
  những thay đổi đó. Không coi workspace source đang sửa là runtime đã đo.

## 3. Q21: truy vết từng candidate

Planner giao Profitability trích xuất/diễn giải PAT; Cash Flow đối chiếu PAT/CFO
và giới hạn kết luận. Bốn tool operations: hai fact retrieval và hai source
retrieval. Cash Flow nhận cả PAT/CFO; Profitability chỉ nhận PAT theo capability.
`evidence_inventory` và `supporting_evidence` xác nhận có nguồn, không phải dự đoán
từ candidate count. PAT nằm PDF7 và CFO PDF8; đây là page provenance với caveats,
không phải cell-level proof hay chứng nhận toàn PDF.

Mọi ID trong bảng có prefix `candidate:`. Native decisions và critic findings
được khôi phục từ `results[0].actual.trace` và **shared batch context** trong
Ledger: `entries[].history.contexts[].{batch,validation,evidence,logic}`. Context
của một accepted entry giữ cả batch, bao gồm hai candidate không được admit.

| Claim | Specialist / nhiệm vụ | Evidence bound | Evidence Critic | Logic Critic | M6 / Validator | Semantic Judge | Ledger / M7 | Nguyên nhân |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `5c79c92dc30bb6a6ee784147` | Profitability: PAT làm cơ sở đánh giá sinh lời | PAT; E001 local → E1 critic; một numeric premise | partially_supported; missing financial_context; không có check_references cho semantic assertion | insufficient_context / supported_numeric_premise_missing | Numeric/context/provenance PASS; semantic_conclusion undetermined; INVESTIGATE / additional_evidence_required | PASS toàn batch, không issue riêng | NOT_EXECUTED; M7 không có claim để chọn | SEMANTIC_SUPPORT_INSUFFICIENT → LOGIC_VALIDATION_BLOCKED; không chứng minh M6 từ chối nhầm |
| `83a9ab5ec40205fb56a75062` | Profitability: PAT fact | PAT, PDF7 | supported | not_applicable | ACCEPT; required financial checks PASS | PASS toàn batch | stored; M7 dùng | Đúng phạm vi fact |
| `112f65ed99bd78670e26130d` | Cash Flow: PAT/CFO và giới hạn tính tỷ lệ/kết luận | PAT+CFO, PDF7/8; E001/E002; hai numeric premises còn nguyên | unsupported, deterministic do failed validation; không gọi semantic critic cho claim này | insufficient_context / failed_validation_premise | `_analysis`: formula FAIL analysis_requires_approved_calculation; INVESTIGATE / financial_checks_failed | PASS dù candidate bị chặn | NOT_EXECUTED; M7 không có claim để chọn | NEGATED_FORMULA_FALSE_POSITIVE; regex bắt “tỷ lệ” trong lời abstention |
| `78af57f77834c9588e2e3216` | Cash Flow: PAT fact | PAT, PDF7 | supported | not_applicable | ACCEPT | PASS toàn batch | idempotent cùng verified ID với PAT trên; M7 dùng một lần | Hai cách diễn đạt cùng fact, không mất claim |
| `8c18742df8148d5ff208d169` | Cash Flow: CFO fact | CFO, PDF8 | supported | not_applicable | ACCEPT | PASS toàn batch | stored; M7 dùng | Đúng phạm vi fact |
| `30623054b0ea0970e2a4cfaa` | Cash Flow: dấu CFO dương và ý nghĩa dòng tiền vào thuần | CFO, PDF8 | supported, gồm numeric prefix + semantic tail | not_applicable + consistent | ACCEPT | PASS toàn batch | stored; M7 dùng | Sign restatement hợp lệ; chưa thay thế kết luận quan hệ PAT/CFO |

Hai unanswered obligations là `adaptive-2` và `adaptive-3`, cùng PAT target,
`interpretation=true`, topic `metric_meaning`, reason `no_supported_interpretation`.
Chúng đến từ assignment indicators. Câu hỏi yêu cầu đánh giá chất lượng lợi nhuận
dựa trên quan hệ PAT/CFO và giới hạn; output chỉ có facts và CFO sign. Generic
topic không biểu diễn chính xác yêu cầu quan hệ này; không nên chỉ bỏ requirements
để đổi nhãn PARTIAL thành answered.

### Bất đồng Judge/M6

- **CONFIRMED:** Judge đánh giá thiếu coverage: PASS giải thích dựa trên số liệu
  có sẵn và accepted facts; không xử lý hai analysis bị chặn. Prompt
  `AdaptiveJudge.assess` đã yêu cầu xét coverage và không nâng deterministic
  blockers, nhưng integration chỉ kiểm tra schema/IDs/revision consistency.
  `AdaptiveFinancialController.run` dừng khi `revision_required=false`; PASS
  không có deterministic check đối chiếu answer obligations.
- **CONFIRMED:** `DeterministicFinancialValidator._analysis` quét `ty le|ty so|...`
  trước khi kiểm tra premises, không phân biệt phủ định. Claim Cash Flow chứa lời
  chưa đủ cơ sở tính tỷ lệ, không yêu cầu phát hành một ratio/value mới. Vì vậy
  formula gate là false positive đối với phần abstention; **không suy ra toàn
  claim đã đủ điều kiện ACCEPT** sau khi sửa gate.
- **CONFIRMED:** Không mất `analysis_premises` qua Specialist → aggregation → M6
  batch. Với Profitability, `_analysis` thực sự sinh numeric checks PASS. Nhưng
  Evidence Critic chỉ partial support nên không bind numeric checks vào semantic
  finding; `premise_gate` chặn Logic Critic trước semantic call. Đây là hành vi
  contract hiện tại, chưa có bằng chứng PROOF_BINDING_ERROR ở claim này.
- **CONFIRMED:** Trace projection `validation={check_id:status}` che mất formula
  FAIL: `_analysis` thêm FAIL rồi `_claim` thêm formula not_applicable.
  Raw `validation.checks` giữ cả hai; M6 dùng raw và vẫn chặn. Không đọc dictionary
  tóm tắt để kết luận tất cả financial checks đều qua.
- M7 dùng đủ ba verified IDs duy nhất: PAT `verified:6a3a4c4b…`, CFO
  `verified:9472f457…`, CFO-sign `verified:3f0a1f24…`. Không có ACCEPT bị M7 bỏ.
  Không xác nhận MISSING_SOURCE_EVIDENCE hay EVIDENCE_RETRIEVED_NOT_BOUND tại Q21.
  LEGITIMATE_ABSTENTION vẫn cần cho đánh giá tốt/xấu toàn diện khi thiếu context;
  quyền abstain không chứng minh regex chặn câu phủ định là đúng.

## 4. Q11: answer obligations

Intent gốc chỉ hỏi giá trị **gross_margin năm 2025**. Proposal có sáu operations:

| Operation | Vai trò thực tế | Requirement được tạo |
| --- | --- | --- |
| op_fact_1 / b02.gross_profit | Operand prerequisite | adaptive-0, fact, no_verified_claim |
| op_fact_2 / b02.net_revenue | Operand prerequisite | adaptive-1, fact, no_verified_claim |
| op_metric_1 / gross_margin, depends_on hai facts | User-requested answer target | adaptive-2, metric, satisfied |
| op_sources_1/2 | Supporting provenance | Không tạo answer target |
| op_lineage_1 | Supporting calculation lineage | Không tạo answer target |

`FinancialQAPipeline.run.refresh` tại block `obligations` (dòng ~750–798) tạo
fact requirement từ **mọi** find_financial_facts, không xét dependency role hay
intent; thêm metric từ formula_ids. `QARequirement`/VietnameseQARequest chỉ mang
các answer requirements, không có role phân biệt internal prerequisite. Trong
`firewall_qa_binding.request_inventory`, requirements được sao lại; `_matches_target`
ở `qa_composer` yêu cầu `kind=fact` được đáp ứng bằng fact claim, không lấy toán
hạng nhúng trong metric làm fact claim độc lập.

Tool-only Specialist tạo duy nhất metric candidate `candidate:4b77f5eaed6f772311f99b63`.
M6 ACCEPT, Ledger stored `verified:166548da…`, M7 dùng chính metric đó. Không có
hai fact claims độc lập, nên inventory/composer/firewall nhất quán với obligations
đã bị sinh thừa. Root cause tại chuyển plan → obligations, không ở Calculator hay
M7 loại metric. Phạm vi: mọi auto metric plan có fact operations chỉ để tính toán.

Nguyên tắc đề xuất: khai báo user-requested answer targets riêng; DAG operations
mang internal dependencies; provenance/lineage là optional supporting evidence
(hoặc yêu cầu nguồn nếu người dùng hỏi). Không suy target từ toàn bộ execution DAG;
không phát hành facts chưa qua M6 để lấp coverage; không hardcode Q11.

## 5. F08: lỗi structured output chính xác

Artifact: `P/provider/evidence-critic-7f456146cef441ad84cb59b78c373139.json`.
Đây là call thứ sáu của F08, đánh giá CFO sign candidate `30623054…`.

- Adapter nhận SDK response có candidate text và finish_reason STOP; status
  chuẩn hóa `malformed`, output.validation_status `invalid_json`, payload null.
  HTTP status **không được lưu**: không gán HTTP200 khi không có raw HTTP evidence.
- JSON là object, không array/markdown. Parser báo `Expecting property name
  enclosed in double quotes`, dòng11/cột7: property `_missing: []` không quote,
  đồng thời sai tên field `missing`. Không phải lỗi JudgeFeedback validation.
- SHA256 raw_text UTF-8:
  `339fbad87ded47b37b0fc96bcba173e0b846acf556f5312f4952c699d97ecf91`.
  Không chép PDF/source text vào báo cáo.
- `GeminiAdapter._map_response` → `parse_json_output` trong llm_contracts nhận
  invalid JSON → structured_output_invalid. `EvidenceCritic._semantic` nhận
  malformed response nên không tới SemanticEvidenceAssessment validation.
- RequestGateway.generate đặt `failure_category`; mọi generate sau trả `_failure`
  ngay, không transport/event mới. Native M6 của các analysis trở thành ABSTAIN
  / required_semantic_assessment_unavailable. AdaptiveJudge trả JUDGE_ERROR trong
  0,013s; không có request adaptive-judge mới trong provider artifacts của F08.
  Hai successful Evidence Critic calls trước đó đã trả supported, không bị mất
  semantic findings; phần Logic Critic/AdaptiveJudge tiếp theo bị ngắt bởi shared
  failure latch. Không gộp lỗi gốc generation và cách integration lan lỗi.
- Budget output1800, provider output102 tokens, finish STOP: không có dấu hiệu
  truncation. Input4518 tokens; độ dài một mình không chứng minh context quá dài
  hoặc mâu thuẫn gây lỗi. UNKNOWN vì sao model sinh key malformed.
- Đã kiểm tra bản sao riêng: đổi property thành `"missing"` thì strict
  SemanticEvidenceAssessment schema và `_validate_semantic` (candidate/assertion
  IDs, evidence IDs đã gửi, status/reason/missing) PASS. Đây là kiểm tra contract,
  không chứng minh semantic correctness; không sửa raw hoặc runtime.
  Semantic proposition CFO sign có native consistent finding
  ở Q21; điều đó không làm F08 raw output trở thành hợp lệ.

## 6. Latency: khôi phục từ live traces

Đơn vị giây; wall-clock, không phải CPU. Provider column là Gateway elapsed
(bao gồm adapter/network/server/generation + overhead nhỏ), không có TTFT hoặc
stream timing để tách network/token generation. Provider-attempt adapter sums
Q21/F08/Q11 tương ứng 9,771 / 11,664 / 2,741s; không cộng chúng với Gateway sums.

| Stage / quan hệ | Q21 | F08 | Q11 |
| --- | ---: | ---: | ---: |
| Outer elapsed | 85.602 | 86.263 | 100.825 |
| Pipeline total | 85.423 | 86.076 | 100.675 |
| context | 1.462 | 1.489 | 1.633 |
| ledger_lookup | 0.002 | 0.622 | 0.634 |
| m5 (parent) | 52.912 | 57.021 | 64.347 |
| m6_validators (child M5) | 1.797 | 1.675 | 2.309 |
| m6_evidence (child M5) | 4.475 | 5.391 | 4.009 |
| m6_logic (child M5) | 0.164 | 0.227 | 0.189 |
| m6_judge_revision (child M5) | 0.152 | 0.240 | 0.247 |
| admission | 2.024 | 0.000 | 2.967 |
| ledger_reload | 1.021 | 0.638 | 2.472 |
| composer | 0.470 | 0.394 | 1.784 |
| citations | 0.016 | 0.016 | 0.007 |
| firewall | 0.453 | 0.494 | 0.989 |
| planning (child M5) | 6.652 | 6.765 | 6.019 |
| supervisor (child M5) | 8.915 | 9.369 | 20.113 |
| context_projection (child M5) | 0.471 | 0.579 | 0.786 |
| specialist_execution (child M5) | 3.448 | 5.497 | 0.616 |
| Semantic Judge (child M5) | 1.337 | 0.013 | 0.000 |
| Gateway/provider (nested) | 9.831 | 11.734 | 2.753 |
| Tools (child Supervisor) | 3.739 | 4.107 | 11.816 |
| Unattributed M5 | 25.411 | 27.149 | 29.704 |
| Unattributed pipeline | 27.064 | 25.402 | 25.842 |

Quan hệ timer: pipeline → M5 adaptive controller → orchestrator agent stages và
M6 validators/evidence/logic/native judge, rồi Semantic Judge. Supervisor chứa
tool calls. Planner chứa provider và validation/materialization. Specialist stage
chứa Specialist provider. M6 evidence chứa critic provider. M6 placeholder ở
pipeline chỉ ~0ms vì reuse adaptive histories; không phải M6 không chạy.

`Unattributed pipeline = pipeline total − context − ledger_lookup − M5 − admission
− ledger_reload − composer − citations − firewall − M6 placeholder`.
`Unattributed M5 = M5 − sum(agent_stages) − sum(M6 child stages) − semantic Judge`.
Đây là residual của timers có tên, không phải một function đo riêng. Không cộng
M5 và residual/children thành tổng độc lập. Outer trừ pipeline là0,179/0,187/0,150s:
conversation/request/export overhead, chưa tách serialization chính xác.

### Q11: vì sao hơn 100 giây?

Live có một Planner provider2,753s, zero Specialist/critic LLM calls. Supervisor
20,113s gồm tools11,816s và overhead8,296s. Tool breakdown: fact4,133+0,334s,
calculator2,434s, sources1,875+0,322s, lineage2,719s. Planner stage6,019s gồm
provider và local3,266s (không tách riêng validation/materialization). Specialist
deterministic0,616s; projection0,786s. M6 validators2,309s/evidence4,009s/
logic0,189s/native Judge0,247s; Ledger admission2,967s/reload2,472s;
M7 composer1,784s/firewall0,989s/citations0,007s/context1,633s/lookup0,634s.

Hai khoảng lớn chưa có timer con là M5 residual29,704s và pipeline residual25,842s.
Source chỉ ra constructors catalog deepcopy, M5→M6 full wire revalidation và
proof serialization có thể nằm đây. Profiler replay bên dưới dùng để kiểm chứng;
không gán chính xác thời gian live của một function từ thời gian replay khác máy tải.

Replay thực tế: Python3.12.0, Windows, source321f09e, fresh isolated Ledger,
1replayed Planner response / **0network calls**. Kết quả: metric ACCEPT, PARTIAL,
hai unanswered operands giống live. Wall221,483s, process CPU204,000s (92,1%).
Profiler overhead làm số này không so trực tiếp với100,825s live; đây là bằng chứng
hotspots và tính chất CPU-heavy, không phải phép đo speedup/regression.

| Hotspot replay / file-function | Calls | Inclusive s | Quan hệ / diễn giải |
| --- | ---: | ---: | --- |
| copy.deepcopy | 27.983.763 total /33.763 primitive | 149,015 | 67,3%wall; self56,444s; bao gồm Pydantic/catalog/proof copies |
| FinancialQAPipeline._m5 | 1 | 68,627 | Ngoài timer M5; RiskAwareSupervisor.__init__60,584s nằm trong đây |
| VerificationRuntime.__init__ | 1 | 60,391 | Trong M5, ngoài M6 check timers; validator ctor38,531s và EvidenceCritic ctor21,860s |
| FinancialRetrievalTools.__init__ | 6 | 73,427 | Nested trong Supervisor/Calculator/Validator/Evidence tools; catalog deepcopy45,161s; không phải6database loads |
| SnapshotCatalog.select → entry → assess_metric | 13select /39assess | 35,210 /35,160 | Re-assess metrics khi chọn snapshot; get_lineage19,197s nằm trong assess |
| EvidenceRetrieval.get_lineage | 49 | 23,711 | Bao gồm trace_metric_lineage19,714s; validate_graph49calls13,683s là con, không cộng thêm |
| EvidencePlan.structural_contract → _schema_path_exists | 28 /84 | 23,106 /23,017 | Schema traversal dựng model_json_schema lặp; tổng model_json_schema86calls23,039s |
| to_verification_input | 2 | 7,443 | Controller handoff rồi pipeline chuyển lại dù đã có histories; full wire validate/hash |
| VerifiedClaimRepository.admit_many | 1 | 7,588 | Proof/JSON work; atomic_json3,920s nằm trong đây |
| VerifiedClaimRepository._load /Path.read_bytes | 3 /1 | 0,371 /0,018 | Không có repeated disk read lớn ở fresh replay này |

**Ba bottlenecks theo measured hotspot:** (1) deep copies149,015s;
(2) snapshot metric/lineage reassessment35,160s;
(3) repeated schema-path generation23,017s. Các số inclusive có phần giao nhau,
không cộng thành207,192s exclusive. Constructors68,627/60,391s là các địa điểm
copy nặng, giải thích vì sao live residual nằm ngoài named stages. Không tách được
CPU riêng từng hotspot từ wall cProfile; CPU204s chỉ đo cho cả replay request.

CONFIRMED có repeated catalog construction, deepcopy và graph/schema work;
PROBABLE chúng chi phối phần residual của live tương tự replay. Chưa có live
per-function timers để gán149s replay thành một số giây tương ứng trong live.
Không có bằng chứng network timeout hoặc filesystem/SQLite blocking gây100s.


Không có bằng chứng cho SQLite blocking: VerifiedClaimRepository ở đường này là
local JSON. BM25/document EF-EG search không được gọi trong financial Q11; financial
retrieval/lineage vẫn dùng catalog và graph. Stage evidence gồm hydration/validation,
chưa có live timer riêng từng phần. Không có M6 revision/replay vòng lặp vô hạn:
một adaptive round, một M6 verify; admission vẫn kiểm tra proof theo policy hiện có.

### So sánh deterministic baseline

| Case | E2E-02 elapsed | FIX-02 elapsed | Chênh quan sát | M5 baseline → FIX-02 |
| --- | ---: | ---: | ---: | ---: |
| Q21 | 37,804 | 85,602 | +47,798 | 15,504 → 52,912 |
| Q11 | 36,271 | 100,825 | +64,554 | 18,990 → 64,347 |

Latency local lớn đã tồn tại trước FIX-02 (0provider). Adaptive controller đưa M6
vào M5 nên không so hai M5 như cùng nội dung. Q21 thêm6provider calls9,831s;
Q11 thêm1call2,753s, không giải thích toàn chênh lệch. FIX-02 thêm adaptive
verification handoff/proof work và thêm operations theo Planner; baseline/final
khác plan, Ledger trạng thái, catalog metrics/cache và tải máy. Chưa có paired
benchmark cùng inputs/plan/cache/hardware-load để quy toàn chênh thành regression
do kiến trúc. Không suy “tối ưu thành công” từ token ít hơn.

## 7. Tokens và context overhead

Theo API usage; round0 cho mọi call trong bảng. `?` là unknown, không phải0.
Latency là Gateway wall, nằm trong stage cha. Total không cộng thêm reasoning
tokens khi provider không báo. Cost unknown, không quy thành giá tiền.

| Case / Call (theo thứ tự) | Agent | Round | Input | Output | Thinking | Total | Latency s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q21/1 | planner | 0 | 4948 | 849 | ? | 5797 | 3.118 |
| Q21/2 | profitability | 0 | 1809 | 211 | ? | 2020 | 1.286 |
| Q21/3 | cash-flow-earnings-quality | 0 | 2772 | 454 | ? | 3226 | 1.771 |
| Q21/4 | evidence-critic | 0 | 4442 | 115 | ? | 4557 | 1.075 |
| Q21/5 | evidence-critic | 0 | 4524 | 102 | ? | 4626 | 1.256 |
| Q21/6 | adaptive-judge | 0 | 5263 | 137 | ? | 5400 | 1.325 |
| F08/1 | planner | 0 | 5772 | 966 | ? | 6738 | 2.973 |
| F08/2 | profitability | 0 | 1786 | 223 | ? | 2009 | 2.505 |
| F08/3 | cash-flow-earnings-quality | 0 | 2743 | 427 | ? | 3170 | 2.500 |
| F08/4 | evidence-critic | 0 | 4376 | 100 | ? | 4476 | 1.201 |
| F08/5 | evidence-critic | 0 | 7627 | 107 | ? | 7734 | 1.254 |
| F08/6 | evidence-critic | 0 | 4518 | 102 | ? | 4620 | 1.301 |
| Q11/1 | planner | 0 | 4927 | 867 | ? | 5794 | 2.753 |

Q21: input23758, output1868, total25626; F08: input26822, output1925, total28747; Q11: input4927, output867, total5794.
Cached/thinking tokens đều null; không có call thiếu total tokens ở13calls này.
Q21 Evidence Critics + Judge chiếm14583/25626 (56,9%); F08 ba Evidence Critics
chiếm16830/28747 (58,5%). Phần lớn usage là input lặp để kiểm chứng evidence,
không phải response generation; F08 không có AdaptiveJudge provider call.

Prompt JSON/Schema gửi dạng text, output_spec format=json; không có schema_ref.
Character sizes sau đây chỉ chẩn đoán cấu trúc, **không phải token attribution**:

- Q21 Planner system16469 ký tự: schema4369, instructions4192,
  canonical indicators3895, approved formulas2531; context197. F08 context2422
  (conversation), system18694; không có previous plan/Judge revision context.
- Q21 Judge payload14326 ký tự: candidates8111, proposal2319, schema1551,
  inventory791. Candidate summaries/evidence lớn hơn schema riêng của Judge.
- Critic mỗi call có system2056 ký tự, schema1177; Q21 user~9,1k, F08 lớn nhất
  ~15,6k: evidence7155, deterministic findings4507, limitations3355. Việc lặp
  evidence/checks/caveats tạo input overhead; không thể phân bổ exact tokens từng
  key từ API aggregate.
- Cash Flow prompt~9,5k ký tự, Profitability~6,25k; schema, instructions và
  evidence/caveats đều có mặt. Không suy generation/thinking là bottleneck từ
  output length; không có riêng timing server/generation.
- Trước đó `post-fix-reasoning/results.json` có actual2replans,133034known tokens;
  phiên P chỉ25626 Q21 tokens, **không revision**. Khác calls/plan/output/provider
  failures: chưa đo được hiệu quả live của compact replanning; không gọi mức giảm
  giữa hai sessions là80,7% lợi ích compaction. Không gọi live bổ sung để chứng minh.

## 8. Findings và hướng xử lý để Tech Lead lựa chọn

| Vấn đề / ID / severity | Root cause | Confidence | Impact / phạm vi | Hướng xử lý khả thi |
| --- | --- | --- | --- | --- |
| D01 / High / Q21 Cash Flow | `_analysis` chặn keyword tỷ lệ bất kể phủ định | CONFIRMED | Analysis abstention có ratio words bị chặn trước premise validation | Phân biệt assertion phép tính và lời giới hạn; giữ approved formula authority |
| D02 / High / Q21 Judge PASS | Judge bỏ sót thiếu accepted interpretation; controller tin revision flag | CONFIRMED | Reasoning requests có facts đủ nhưng analysis bị chặn dừng sớm | Coverage feedback dựa user targets và native blockers; không ép ACCEPT |
| D03 / Medium / Q21 Profitability | Partial semantic support, thiếu bound supported premise → logic gate | CONFIRMED về luồng; UNKNOWN full semantic sufficiency | Non-numeric interpretation; chưa chứng minh numeric proof binding lỗi | Review policy distinction factual premise/semantic conclusion; giữ abstention khi chưa đủ |
| D04 / High / Q11 PARTIAL | Mọi find_financial_facts thành answer requirement | CONFIRMED | Auto calculation plans có operand dependencies | Tách user targets / dependencies / supporting evidence |
| D05 / Medium / F08 malformed | Model sinh unquoted, sai field `_missing`; JSON parser đúng khi reject | CONFIRMED lỗi; UNKNOWN nguyên nhân generation | Evidence Critic semantic output | Schema-constrained generation nếu Gateway/provider hỗ trợ; strict validation và ngân sách giữ nguyên |
| D06 / Medium / F08 lan lỗi | RequestGateway.failure_category chặn mọi calls tiếp theo | CONFIRMED | Một critic malformed làm Logic/AdaptiveJudge unavailable | Tech Lead chọn fail-stop hiện tại hoặc phân loại lỗi/call recovery có giới hạn; không retry vô hạn |
| D07 / High / latency | Repeated catalog deepcopy, metric/lineage reassessment và schema-path generation | CONFIRMED replay; PROBABLE attribution live | Financial fresh/mixed runtime; caller/counters ở mục6 | Giảm copy đúng scope, reuse immutable schema/selection có kiểm chứng; không bỏ provenance gates |
| D08 / Low / observability | `{check_id:status}` ghi đè duplicate formula check | CONFIRMED | Debug summary khiến FAIL trông như N/A | Giữ findings theo finding_id hoặc list; runtime gate không bị bypass |

Reproduction cho D01–D03/D08: đọc shared Q21 Ledger context, đối chiếu
validators._analysis, EvidenceCritic._semantic, logic_rules.premise_gate,
AdaptiveJudge.assess/AdaptiveFinancialController.run; regex trên nguyên statement
match keyword dù phủ định. D04: Q11 proposal operations → trace.answer_requirements
→ one stored metric → unanswered adaptive-0/1; replay Planner được lưu. D05/D06:
parse raw_text đúng artifact bằng json.loads; đối chiếu RequestGateway.generate
và sáu provider events, không có AdaptiveJudge provider request. D07: chạy script
profile offline trong D, source frozen và fresh Ledger; timing là profiling, không
research evaluation hoặc live benchmark.

## 9. Thứ tự sửa đề xuất và kiểm thử sau sửa

Tech Lead chọn giải pháp cuối; chưa triển khai bất kỳ phương án nào:

1. Chốt answer targets contract và xử lý D04; đồng thời xác định target quan hệ
   PAT/CFO, tránh topic metric_meaning quá rộng. Trade-off: cần thay plan→M7
   boundary, nhưng tránh thêm fact claims chỉ để làm đầy inventory.
2. D01 + D02: bảo toàn phép abstain không chứa phép tính mới; chỉ cho PASS khi
   coverage/native blockers phù hợp intent. Trade-off: có thể tăng revisions/calls;
   giữ caps và không đổi Native M6 authority.
3. D05/D06: strict structured generation và lựa chọn failure isolation/recovery.
   Trade-off: fail-stop tiết kiệm chi phí nhưng mất feedback; retry có giới hạn tốn
   thêm quota và phải ghi mọi attempt, không tự sửa financial content từ JSON lỗi.
4. D07/D08: giảm catalog/proof copy và bổ sung attribution tối thiểu tại hotspots
   được đo; cân nhắc snapshot read-only/reuse theo exact identity. Trade-off: phải
   chứng minh mutation isolation/source-policy freshness; không cache bỏ qua gates.

Targeted checks cần sau implementation: metric-only vs user explicitly asks operands;
negated ratio limitation vs actual unapproved ratio; partial evidence không thành
ACCEPT; Judge facts-only không PASS relation target chưa đáp ứng; malformed critic
giữ strict schema/call budget. Một offline replay có evidence/proof tương đương
và paired wall/CPU timings đủ kiểm tra engineering. Chỉ khi Owner/Tech Lead cho
phép mới chạy targeted live Q21/F08/Q11 để đánh giá answer quality và một revision
thành công; không dùng replay/synthetic PASS thay financial research evidence.

## 10. Validation và bàn giao

Đã chạy: offline Q11 replay + cProfile; hai targeted checks (negated-ratio regex,
strict schema/identity validation trên F08 response copy) PASS; runtime manifest
và414protected hashes nguyên; planning checker PASS122tasks; git diff --check PASS.
Lần khởi chạy profiler đầu bị request validation từ chối timeout1200>300, trước
pipeline/network; đã đổi script diagnostic thành300 và chạy một request thành công.
Không có live call hoặc unit suite mới. Báo cáo không thay acceptance evidence
engineering/research cũ; SHA điều tra vẫn321f09e, diagnostic chưa commit.

**Next action duy nhất:** Tech Lead đọc diagnostic và quyết định phạm vi/giải pháp
sửa tiếp trong FIX-02. Giữ REVIEW; không tự DONE, mở task khác hoặc tối ưu runtime.
