# Codex Handoff

## Active Task

D-06 — Canonical Mapping & Financial Validation Fix

## Status

REVIEW

## Last Verified State

Baseline main/origin/main `004957b06972635ea35cc5e27ead7888f35174c4`.
[Spec](tasks/D/D-06.md), [report](../docs/d06-canonical-mapping-validation.md).
Implementation chưa commit; Owner cho commit/push main và chờ Tech Lead nghiệm thu.

## Completed Work

Generic mapping16→24 IDs, registry sửa total_* refs/stale flags; snapshot-bound
source-validation adapter gọi existing M2 evaluators. Projection riêng910 slots,
+80 mapped; QA09 found đúng kỳ,QA15 hai balance identities residual0. Real100
checks65 consistent/35 insufficient,8 rules thực sự tính. B05/B11 REVIEW.

## Remaining Work

Commit/push main và ghi CI đúng implementation SHA; chờ Tech Lead nghiệm thu.

## Modified Files

Accounting mapping/extraction/recovery/arithmetic/relationships, evidence adapter,
focused tests/CI, bounded evaluation và docs/planning. Giữ web/next-env.d.ts ngoài stage.

## Tests

322 focused PASS gồm30 D-06 generic cases/hai synthetic documents. Real baseline15,
recovery3,29 queries/graph/18 lineages/36 pairs/1.177 lookups exact. Replay29 ở D-06
còn selection ambiguity;2.506 protected hashes unchanged,26 projection files giữ
nguyên;10 EPS VND/share/5 overlays/terminal coverage preserved;zero Gateway.
Ruff/planning/diff kiểm tra trước bàn giao. Chưa có CI implementation mới.

## Blockers

Không có blocker core D-06 sau fix. 670 financial slots ngoài bounded mapping;
null/layout B03/2022/required exchange effect/adjustments giữ insufficient. Không
full-PDF accuracy, scope/cross-year approvals hoặc M4 execution. D-04 recovery2022
là explicit alternative, không trộn vào D-05/D-06 corrected projection.

## Git Checkpoint

Main-first, chưa commit. Accepted D-05 `401c12a4f5172e186b820252c6bcce9adb47d9df`;
giữ nguyên accepted artifacts và web local. D-06-final là projection riêng,
D-06-review chứa final validation/source outputs, đều ignored.

## Exact Next Action

Tech Lead independent review D-06 và disposition B05/B11.
