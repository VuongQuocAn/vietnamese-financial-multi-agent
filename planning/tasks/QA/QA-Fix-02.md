# TASK QA-Fix-02 — M5 Planner & Downstream Recovery

## Metadata

- Milestone: QA
- Status: REVIEW
- Priority: P1
- Dependencies: QA-Fix-01, QA-Q01
- Estimated Complexity: M

## Objective

Sửa F02 Planner từ chối sai domains đã hỗ trợ; bounded HTTP503 recovery và fresh
Planner → Supervisor → Router → Specialists → Aggregation trên BBS. Dừng REVIEW.

## Context

Owner giao06/11/2026, cho phép implement/test/live tối đa20provider attempts,
commit/push main và CI đúng SHA. Baseline main/origin0451b37; giữ Web local.
QA-Q01 saved4M5 attempts:3HTTP503/1unsupported,0downstream. Chỉ đạo đầy đủ giữ
local ở artifacts/evidence/QA-Fix-02/task-request.md.

## Inputs

[QA-Q01 diagnosis](../../../docs/qa-q01-quick-qa-root-cause.md), saved Q07,
M5-02/03/07/08 contracts/runtime, Gateway/Gemini adapter, persisted BBS facts,
approved M4 formulas và independent PDF reference từ QA-Q01. QA-Fix-01 DONE.

## Outputs

Minimal generalized fix, failing/passing controls, bounded fresh BBS runner,
[report](../../../docs/qa-fix-02-m5-planner-downstream-recovery.md), structured
traces riêng trong ignored artifacts/evidence/QA-Fix-02/.

## Allowed Changes

Planner prompt/semantic policy, bounded recovery tại Gateway, additive metadata
và consumers liên quan; tests/runner/docs/planning/CI focused test entry.

## Out of Scope

Không OCR/extraction/M8; không sửa facts/formulas/ledger/M6/M7 policy, không tự
chọn metrics/scope, fake success, đổi model/key, retry vô hạn hoặc hash toàn bộ
dataset. Không triển khai task tiếp theo.

## Implementation Steps

1. Preflight Git/config/saved traces; xác định confirmed/probable/unresolved.
2. Failing regressions trước sửa logic; semantic validation giữ raw proposal.
3. Explicit targets qua catalog/gates; broad clarify; partial giữ restriction.
4. Provider HTTP503 retry tối đa1lần, backoff ngắn, total timeout/budget.
5. Fresh Q03 → Q06 → câu2domains mới → câu3domains mới → Q07 → Q08.
6. Audit stages/tools/evidence/claims với independent reference; kiểm tra riêng correction nếu có.
7. Focused/boundary tests, Ruff/planning/diff, commit/push main/CI đúng SHA.

## Acceptance Criteria

- [x] F02 tái hiện; supported/unsupported/clarification/partial phân biệt đúng.
- [x] Multi-domain explicit targets có valid plan; broad không tự chọn metric.
- [x] Raw/effective proposals và policy trace; scope/year/snapshot/D03-B10 gates giữ nguyên.
- [x] HTTP503 bounded recovery;429/auth/schema/timeout không retry như503.
- [x] Actual6BBS questions; fresh full downstream hoặc provider blocker rõ.
- [x] Thử2/3Specialists; stages/tools/evidence projection/aggregation dễ đọc.
- [x] Gross margin≈7,21%; debt/assets≈59,06%; revenue450.474.531.227/CFO14.319.681.754 VND đúng independent reference.
- [x] Không financial-policy bypass/verified claims/M6-M7 release từ candidates.
- [x] Focused M5/consumer boundary tests, Ruff/planning/diff PASS.
- [ ] Commit/push main, CI SUCCESS đúng SHA; dừng REVIEW.

## Required Tests

F02:2/3domains explicit/broad, contradiction, partial/true unsupported, paraphrases
khác BBS2025, scope/year/cross-document/missing evidence, single-target compatibility.
F03:503→success/503;429/auth/JSON/timeout no retry; attempts/provenance/usage/latency;
downstream NOT_EXECUTED khi Planner failed. Focused M5-02/03/07/08,3Specialists và
M6candidate/M7composer/firewall; không full local suite.

## Risks and Blockers

Provider503 nguyên nhân sâu unresolved; không suy quota. Giữ unknown usage,
candidate caveats/page-level uncertainty. Clarification đúng không là provider
failure; engineering PASS không chứng minh accuracy toàn PDF.

## Implementation Evidence

Implementation là commit chứa report; exact SHA/CI ghi local delivery checkpoint
và final handoff.19failed/3passed trước sửa;305focused/consumer PASS; Q08 alias gap
2failing trước correction/66focused PASS; clarification-reason1failing trước sửa.
Final27new/133M5-Gateway PASS.15Gemini attempts/50.598tokens/0HTTP503/429,
4completed downstream/7fresh runs/6questions;8Specialists/21candidates.
Independent financial/provenance audit PASS;15selected hashes/Web unchanged.

## Handoff Notes

Next action: Tech Lead review QA-Fix-02 và quyết định nghiệm thu.
