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
Status REVIEW; không tự DONE. Next action: hoàn tất validation đã giao và bàn giao
Tech Lead nghiệm thu implementation cùng limitations.
