# TASK QA-Fix-01 — Grounded Requirement Coverage & Safe Financial Explanation

## Metadata

- Milestone: QA
- Status: IN_PROGRESS
- Priority: P1
- Dependencies: QA-Q01, M7-05
- Estimated Complexity: M

## Objective

Sửa F01 bằng dependency-aware requirements và explanation từ admitted calculation;
giữ factual premises khi thiếu interpretation, bảo toàn firewall/citation boundaries.

## Context

Owner giao06/11/2026, cho phép triển khai/test/commit/push main, dừng REVIEW.
Baseline HEAD/origin `2432bec`; chỉ có local `web/next-env.d.ts`, phải giữ nguyên.
QA-Q01 DONE:2correct/4partial/4abstention-clarification, không có incorrect released.

## Inputs

Đặc tả Owner QA-Fix-01 phases A–G; [QA-Q01 report](../../../docs/qa-q01-quick-qa-root-cause.md),
saved accepted M6 ledger, mười câu và independent PDF references QA-Q01 (local).

## Outputs

Typed requirement/explanation contracts, Composer/Firewall dùng chung policy,
regression tests, QA-only runner và báo cáo `docs/qa-fix-01-grounded-requirement-coverage.md`.
Actual outputs/evidence ở `artifacts/evidence/QA-Fix-01/` (local ignored).

## Allowed Changes

M7 QA contracts/composer/request binding và helpers explanation tối thiểu;
tests/scripts/docs/planning liên quan. Renderer/Firewall core chỉ sửa khi cần.

## Out of Scope

Không thay M1–M6 policy, orchestrator, ledger admission, PDF/facts/anchors/snapshots;
không tính mới, tạo interpretation mới, promote operands, live Gemini/OCR/extraction;
không QA-Fix-02–05 hoặc M8; giữ frozen oracles.

## Implementation Steps

1. Reproduce failing tests và actual plans trước sửa.
2. Typed dependent requirements; shared inventory từ trusted request + admitted ledger.
3. Bounded explanation từ ACCEPT calculation, protected slots/citations/caveats.
4. Focused/adversarial/compatibility controls; actual10 BBS + independent PDF check.
5. Integrity/Ruff/planning/diff; commit/push main, CI đúng SHA; dừng REVIEW.

## Acceptance Criteria

- [x] F01 reproduced trước sửa; generalized decomposition và paraphrases đạt.
- [x] Giữ facts + metric value/formula/operands dependencies, thiếu metadata → partial.
- [x] Không unverified calculation/interpretation/standalone operand promotion.
- [x] Composer/Firewall chung policy; independently rebind original trusted request.
- [x] Explanation tampering bị BLOCK, citation identity/caveats và fail-closed giữ nguyên.
- [x] Actual10 BBS trước/sau, claims/formula/operands/firewall và PDF reference audit.
- [x] Targeted/compatibility controls PASS; protected hashes/Web local unchanged.
- [ ] Commit/push main và CI SUCCESS đúng implementation SHA; chờ Tech Lead REVIEW.

## Required Tests

Failing regression trước sửa; decomposition/generalization, grounding,14 explanation
attacks, M7-01/04/05 và M6 boundary controls;10 actual BBS; Ruff/planning/diff/hashes.
Không full local suite hoặc benchmark framework; CI hiện hành chạy focused suites.

## Risks and Blockers

LNST/standalone assets chưa có ACCEPT; interpretation coverage thiếu; quick ratio
chưa approved; D03-B10 giữ nguyên. Engineering PASS không chứng minh financial gold.

## Implementation Evidence

- Implementation SHA: chưa commit.
- Before:13 regression cases FAIL, saved `plans-before.json`/`failing-tests.txt`.
- Main Changes: [báo cáo](../../../docs/qa-fix-01-grounded-requirement-coverage.md);
  typed dependent requirements/explanation, shared inventory, original request revalidation.
- Test Results:254final PASS (40new/211compatibility-boundary/3planning);
 10/10actual BBS, final-policy audit PASS;Q03formula+operands,Q08revenue+CFO/no verdict;
 16.849protected hashes/Web unchanged;Ruff changed files/planning/diff PASS.
- Review Notes: chưa nghiệm thu; chỉ Tech Lead chuyển DONE.

## Handoff Notes

Next action: hoàn tất implementation và validation trong QA-Fix-01; dừng REVIEW.
