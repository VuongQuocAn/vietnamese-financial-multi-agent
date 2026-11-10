# TASK FIX-02 — Adaptive LLM Multi-Agent & Bounded Judge Feedback Loop

## Metadata

- Milestone: FIX
- Status: REVIEW
- Priority: P1
- Dependencies: REC-01
- Estimated Complexity: L

## Objective

Planner Gemini hiểu, lập và sửa kế hoạch động; Specialists suy luận trên evidence;
Judge Gemini phản biện và chuyển structured feedback về Planner. Python thực thi
và giữ deterministic release authority M6/M7.

## Context

Owner giao09/11/2026 theo chỉ đạo FIX-02 đính kèm; baseline `20694b2` trên main.
E2E-02 REVIEW:40 lượt deterministic/0Gemini,9issues OPEN. Tái sử dụng CHAT-01;
giữ thay đổi nghiệm thu CHAT-01 local riêng, pending GEN-01a/Web và evidence cũ.

## Inputs

PlannerProposal/EvidencePlan/PlannerResult, ba Specialists, M6 critics/Judge/Ledger,
M7/CHAT-01; issue log E2E-02; BBS/BCC accepted inputs và PDF gốc local.

## Outputs

Adaptive runtime/typed contracts, focused tests, runner tám ca thật và
`docs/fix-02-adaptive-llm-agents.md` với actual calls/tokens/latency/issues/limitations.

## Allowed Changes

Planner assignments/tool routing, Specialist reasoning, Judge synthesis/feedback,
request budgets và tối đa2revisions/3Judge assessments; financial/document/mixed/
conversation entrypoints; root cause và fixes trực tiếp liên quan9issues.
Commit/push main được Owner yêu cầu trong chỉ đạo nguồn.

## Out of Scope

Không framework agent mới, Vector DB, công thức mới, OCR pipeline, Web UI/M8,
full regression1000+tests hoặc sửa raw/processed/accepted evidence.

## Implementation Steps

Khảo sát M5/M6/M7 → typed contracts → adaptive execution → bounded loop
→ QA integration → focused/live checks → report/commit/push REVIEW.

## Acceptance Criteria

Planner chọn tool-only hoặc Specialists theo mục tiêu; Judge phản biện thật;
feedback/replan đúng phần ảnh hưởng, tối đa2revisions và không vòng M6 lồng nhau.
M6 Decimal/formula/company/period/snapshot/provenance gates không bị bypass.
Trace phân biệt LLM/tool/deterministic/cache/degraded; usage và latency thật.
Có Gemini live tám ca và ít nhất một feedback loop live; I001 không phát hành
quotation đảo nghĩa trên đường đã kiểm thử. Không gọi mock/smoke là accuracy.
Issues chưa đủ bằng chứng giữ OPEN; thiếu core acceptance thì REVIEW, không DONE.

## Required Tests

Focused mock Planner/tool-only/reasoning/feedback/budget/source gates; targeted
integration baseline/reuse/document/conversation; tám ca BBS/BCC thật có trace,
usage/errors/latency và đối chiếu source. Không retry để chọn output đẹp.
Ruff, planning checker, diff check; CI nhẹ implementation cuối.

## Risks and Blockers

Provider failures và source coverage/trust phải được ghi minh bạch; không tạo
evidence hoặc approval để đóng issues. Giữ toàn bộ kết quả lỗi trước bản sửa.

## Implementation Evidence

Implementation `b7eb2bf838c6c194cb7a55910a4937bfc043e731` đã push main, SHA xác minh.
[CI42600674784](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42600674784)
completed/SUCCESS đúng SHA:27Python/9Web PASS, full regression SKIPPED.
[Báo cáo](../../../docs/fix-02-adaptive-llm-agents.md);
evidence local artifacts/evidence/FIX-02/ giữ toàn bộ lượt lỗi và bổ sung Q21.
Live loop có2feedback/replans,13calls/133034known tokens,partial do provider failure;
I001 corrected và I009 source replay được kiểm chứng trên đường đã chạy.
Chưa Judge PASS sau revision hoặc full live final SHA;9issues giữ OPEN.
Local78compatibility/47focused/28CI-smoke và9adaptive cuối PASS, có overlap.

## Handoff Notes

Status REVIEW. Next action: Tech Lead review FIX-02 cùng limitations, không tự DONE.

## Hoàn thiện REVIEW theo Owner — 09/11/2026

Giữ cùng FIX-02, không mở task mới/không chạy lại40câu. Kiểm tra missing CFO thật
hay evidence đã có nhưng chưa được giao/dùng; rút gọn context replanning và chặn
yêu cầu lặp không tiến triển. Sau khi code ổn định, chạy đúng một lượt live:
Q21→F08, Q01/Q11 tool-only sau period fix, Q08 quotation giữ từ “khó”.
Runtime phải import source từ implementation commit, giữ input/reference bất biến;
không thay code runtime sau lượt live rồi dùng kết quả đó chứng nhận code mới.
Kết quả cải thiện hoặc dừng có lý do đúng phải có trace; CI không thay live acceptance.

### Evidence hoàn thiện REVIEW

Source cuối `321f09e91cd4e32bcfcb0584d84f70d5c31e13e4` đã push main;
[CI42606529703](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42606529703)
SUCCESS đúng SHA31Python/9Web;61local focused PASS. Không full regression.
Hai lượt5ca được Owner cho phép, không retry. Source archive/imports/runtime
hashes verified,414protected inputs/reference unchanged. Q21cuối6calls/25626known
tokens/85,602s nhưng PARTIAL; không có revision mới nên chưa chứng minh successful
replanning live. F08không dependency error nhưng Judge invalid output;Q01http503;
Q11metric M6 ACCEPT nhưng partial do operand obligations;Q08quotation đúng.
Giữ REVIEW, không ghép kết quả tốt nhất của hai source versions thành5/5PASS.

### Diagnostic-only — 09/11/2026

[Root cause diagnostic](../../../docs/fix-02-root-cause-diagnostic.md) đối chiếu
runtime321f09e, raw traces Q21/F08/Q11 và offline Q11 cProfile/replay,0network calls.
Xác nhận Q21 negated-ratio gate/semantic coverage, Q11 dư operand obligations,
F08 malformed Evidence Critic JSON lan qua shared Gateway; local copying,
metric/lineage reassessment và schema generation là hotspots đo được trong replay.
Không sửa runtime/accepted data/Ledger, không gọi Gemini hoặc đổi status.
Diagnostic chưa commit; FIX-02 REVIEW — WAITING FOR TECH LEAD DECISION.
Next action: Tech Lead chọn phạm vi và giải pháp sửa theo diagnostic.

### Remediation được giao — 10/11/2026

Owner/Tech Lead duyệt A1–A4 correctness và B2–B4 performance trong cùng FIX-02;
cho phép commit/push main và tối đa một lượt live Q21/Q11/F08 sau focused/offline
validation. Tách typed user targets khỏi operations/dependencies; scope-aware
limitation routing, native coverage dùng rules M7; strict JSON failure isolation;
request snapshot/lineage/schema cache không bỏ source/proof/mutation gates.
Giữ pending GEN-01a/Web/CHAT, raw/reference/approved data và historical Ledger.
Kết quả/SHA/CI ở [báo cáo](../../../docs/fix-02-adaptive-llm-agents.md#correctness--performance-remediation--10112026).
Implementation cuối `9a356bfaf53f0003b5f19edb031de9a3da4f6f39` đã push main;
[CI42729994715](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42729994715)
SUCCESS đúng SHA63Python/9Web,lint/format/planning/typecheck/build PASS;full regression
SKIPPED. Local63CI-smoke/69focused PASS (overlap),4historical financial entries replay
unchanged. Paired Q11 median40,001→9,947s (−75,1%),3cold/3warm mỗi version,
164runtime files benchmark khớp commit;12calculations/provenance equivalent.
Một lượt live Q11/Q21/F08 trên6748da7:3Planner calls/19639tokens,provider success
nhưng integration FAIL; correction sau đó validated bằng chính saved responses,
không live lần hai. Q11offline completed;Q21/F08 planned/dispatch đúng nhưng thiếu
archived Specialist responses nên fail closed. Chưa final live/ successful live
revision;414inputs/reference và pending GEN/Web/CHAT giữ nguyên;9issues OPEN.
Status REVIEW, chưa đề xuất DONE. Next action: Tech Lead review9a356bf và quyết định
nghiệm thu/phạm vi kiểm chứng tiếp theo theo limitations.

### Kiểm chứng live cuối được giao — 10/11/2026

Tech Lead chấp nhận remediation engineering và cho phép một lượt Q11→Q21→F08
trên cố định9a356bf;Q11stop gate PASS,không runtime changes/retry/benchmark mới.
Artifacts `artifacts/evidence/FIX-02/controlled-live-9a356bf/`;imports/164runtime
files/414protected inputs/reference/local changes nguyên.17actual Gemini calls,
101834API tokens,0provider errors. Q11completed_with_caveats22,394s/1call/5981tokens,
computed7,21%,M6 ACCEPT metric,M7answered3/3. Q21partial29,874s/4calls/19883tokens:
3ACCEPT/1INVESTIGATE,M7covered3/5,negated-ratio formula false positive còn với
“dữ liệu chưa đủ để tính toán tỷ lệ…”,D01CONFIRMEDHigh/P1;raw Judge PASS bị backend
coverage đổi INSUFFICIENT_EVIDENCE/STOP. F08completed_with_caveats50,412s/12calls/
75970tokens,M7answered1/1;round0thiếu interpretation coverage thật→backend feedback
REVISION_NEEDED→Planner sửa task→4tools CACHE_HIT→Specialist/Critics/native ACCEPT
analysis→round1Judge PASS+coverage true. Có successful live revision trên9a356bf,
không ép LLM Judge hoặc tạo lỗi giả;raw Judge round0vẫn PASS,feedback từ coverage
guard. Không thêm ca thứ4 vì F08đã cung cấp tình huống thiếu sót/sửa thực tế.
6new Ledger entries proof replay PASS,không đổi bytes;numeric/source audit PASS.
[Report](../../../docs/fix-02-adaptive-llm-agents.md#kiểm-chứng-live-có-kiểm-soát-trên9a356bf--10112026).
Status REVIEW,không tự DONE/đóng9issues. Next action: Tech Lead quyết định blocker
Q21D01tái diễn và nghiệm thu phạm vi đã có evidence;không tự sửa/live thêm/Web/M8.

### Tech Lead giao sửa P1 Q21 — 10/11/2026

Q11/F08được chấp nhận;chỉ sửa phạm vi phủ định tổng quát,regression Việt+negative
controls,replay exact analysisQ21,giữ independent M6gates. Answer coverage đã có
trong input Judge9a356bf;nhắc model xét complete/goals,backend guard giữ quyền chặn.
113targetedPASS;exact replay2numeric premisesPASS/0formula false positive nhưng
M6ABSTAIN khi thiếu semantic response,Ledger rejected;6historical proofs unchanged.
Cho phép đúng1liveQ21sau offlinePASS trên source mới;không Q11/F08/benchmark/full
suite. Kết quả/SHA/CI trong phần P1Q21 của report. Status REVIEW,không tự DONE.

Implementation `8eadc84d98928ec4b53e6589e723bbeb8e617009` đã push main;candidate164files
khớp archive. Một liveQ21 trên đúngSHA:verification_blocked9,415s/1Plannercall/
6858API tokens;provider success/STOP/validJSON nhưng assignments[1].depends_on
có3items,max2;Pydantictoo_long,application invalid_proposal_schema_schema. Không
provider failure,không thiếu financial evidence.0Specialist/Critics/Judgecalls,
M6rỗng/M7không chạy/0claim phát hành;chưa livevalidate negation fix đầu-cuối.
Khôngnới schema/sửa runtime/retry lần2.164runtime/414inputs/reference/pending
local nguyên.113targeted tests và exact saved-Q21replayPASSgiữ evidenceoffline.
Next action: Tech Lead review8eadc84 và quyết định chặn Planner schema/liveacceptance;
giữ FIX-02REVIEW,không tựDONE/Web/M8.

[CI42735324025](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42735324025)
SUCCESS đúng8eadc84:85Python/9Web,Ruff/planning/typecheck/buildPASS;full regression
SKIPPED. Không dùng CI thay liveacceptance. Checkpoint tiếp theo chỉ docs/planning;
không runtimechanges sau lượtQ21,không gán CI choSHAdocs.

### Tech Lead giao sửa Planner dependency contract — 10/11/2026

Giữ REVIEW; chỉ mở `SpecialistAssignment.depends_on` từ 2 lên 35 references,
theo 32 operations/3 roles. Kiểm tra toàn DAG: tồn tại, unique, không vòng,
không operation→role hoặc ID nhập nhằng. Router giữ capability boundaries và
chặn role phụ thuộc không đủ điều kiện dispatch; không thay M6/Judge/M7.
77 targeted tests PASS (63 Planner/router/adaptive/negation và 14 orchestrator;
10 dependency controls đã chạy lại sau bổ sung assertions, không cộng trùng).
Replay nguyên JSON Planner live 8eadc84 PASS: ba refs giữ nguyên, Supervisor
completed, hai Specialist generated bằng deterministic dispatch smoke;
không gọi provider/không cấp M6 ACCEPT. 414 inputs giữ nguyên.
Tiếp theo đúng một Q21 live trên implementation SHA mới đã commit/freeze.
Không Q11/F08/benchmark/full E2E; nếu nguyên nhân mới thì báo, không retry/sửa tiếp.

Implementation `0b6c8d74b3674198a4a6b259ea2ade033fbc57de` đã push main;164candidate
files khớp archive. Một Q21live:partial_verified_coverage23,226s/7calls/44344tokens,
0provider errors. Ba dependencies schema/materialization PASS,1LLMSpecialist,
2Evidence/1Logic/1Judge,4nativeM6ACCEPT nhưng relational coverage thiếu;rawJudge
PASS dù input complete=false,backend REVISION_NEEDED. Planner round1success/schema
PASS nhưng non-null fact targets kind=explanation/aspect=formula bị
answer_target_outside_plan_formulas;STOP execution_unavailable,không downstream
round1. M7partial/covered3of6/ALLOW_WITH_CAVEAT;hai facts đúng,thiếu relational
interpretation. Không kết luận thiếu evidence thật hoặc provider outage.
Không sinh lại negated Q21sentence;offline scope replay vẫn là evidence chính.
Không runtime fix/retry;164runtime/414inputs/reference/local giữ nguyên.
CI42737707767FAIL vì workflow indentation (83testsPASS rồi shell exit126),
checkpoint sửa riêng YAML/docs,không đổi source/tests hoặc gán live sang SHA mới.
Next action: Tech Lead review partial Q21 và quyết định revision-target blocker;
FIX-02REVIEW,không tựDONE/Web/M8.

CI42738238199SUCCESS trên b0b4a0d85363e0dc194b7b43f640ba3e0d3495bc:
95Python/9Web,Ruff/planning/typecheck/buildPASS,fullregressionSKIPPED.
Checkpoint chỉ YAMLindent/docs/planning;source/tests giống live0b6c8d7 từng byte.
Không gán CI cho liveSHA hoặc gọi Q21PASS. Docs cuối không sửa runtime/workflow.

### Flexible contracts được giao — 10/11/2026

Owner giao tiếp cùng FIX-02: semantic target normalization/raw-effective trace,
independent partial goals, relational M7 matching/dedup, Specialist failure
isolation và compatibility review. Giữ native M6/source/period/formula gates.
Exact Q21 revision baselineFAIL→planned/materialized/dispatch;5captured Planner
responses replay,10historical proofs unchanged,414inputs nguyên.
165earlier/81final/13preservation targetedPASS (overlap);một unrelated fixture
failure được xác nhận có trên baseline. [Report](../../../docs/fix-02-adaptive-llm-agents.md#flexible-contracts--10112026).
Implementation chưa commit tại offline checkpoint; live sau commit/freeze.
Status REVIEW — WAITING FOR TECH LEAD ACCEPTANCE.
Next action: đúng một Q21 live trên implementation commit đã đóng băng.

Implementation `a320e8cf04905e012982ad4e06f0f881b3e67c79` đã push main.
Một Q21live57,088s/12calls/77174tokens/0providererrors:hai rounds planned/dispatch
PASS;round1 dùng4CACHE_HIT;native final4ACCEPT,M7partial3/4,hai facts phát hành đúng.
Model revision vẫn tạo generic co-presence/limitation,không relational analysis;
backend chặn rawJudgePASS/coveragefalse và dừng không tiến triển. Final renderer
còn nối raw PLANNER_TASK/codes sau sanitized composer;đã ghi root cause,không hotfix.
4newproofs replay/164runtime/414inputs/reference/unrelatedlocal unchanged.
[CI42765017155](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42765017155)
SUCCESS đúng a320e8c:107Python/9Web,lint/format/planning/typecheck/buildPASS;
full regressionSKIPPED. Không gọi live financial acceptancePASS;checkpoint sau
chỉ docs/planning,không runtime changes hoặc gán live cho SHA docs.
Status REVIEW — WAITING FOR TECH LEAD ACCEPTANCE.
Next action: Tech Lead review a320e8c và quyết định hai giới hạn còn lại.
