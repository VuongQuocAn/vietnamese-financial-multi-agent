# TASK EF-CORE-03 — Targeted Quality & Graph Efficiency Improvements

## Metadata

- Milestone: EF
- Status: IN_PROGRESS
- Priority: P1
- Dependencies: EF-CORE-02
- Estimated Complexity: M

## Objective

Sửa đúng P1–P4, bảo toàn grounding và giảm chi phí graph có đo lường.

## Context

Owner giao ngày11/11/2026; main48b9d78, giữ local edits ngoài task.

## Inputs

Task Owner đầy đủ trong artifacts/evidence/EF-CORE-03/owner-task.md (ignored); BBS2025, EF-CORE-02 oracle và Gateway hiện có.

## Outputs

[Báo cáo](../../../docs/ef-core-03-targeted-quality-graph-efficiency.md), regression tests, performance và fresh live traces ignored.

## Allowed Changes

M5 candidate isolation/source/context projection, M6 scalar source metadata, graph facade tối ưu có giới hạn, evaluator và planning.

## Out of Scope

Không OCR/extraction, raw/canonical writes, period-policy redesign, agents/edges/database mới, M7 verifier, M8 hoặc model khác.

## Implementation Steps

Root causes → P1–P3 → profile/P4 → targeted offline → BBS Gemini → báo cáo/commit/push/CI → REVIEW.

## Acceptance Criteria

- [x] P1 isolation và P2 source metadata/semantic regression.
- [x] P3 projection coverage và P4 đo trước/sau giữ isolation.
- [x] Fresh BBS validation và báo cáo cả partial/technical failures.
- [ ] Targeted final checks, commit/push và CI đúng SHA; bàn giao REVIEW.

## Required Tests

Targeted P1–P4, snapshot/citations, CORE-FLOW calculations; BBS C1/D1/B2/C3/Q5; mini diagnostic A/B/C; Ruff/planning/diff và CI.

## Risks and Blockers

Provider503; Q5 chưa tái hiện đủ phần trăm, C3 context/period cũ; graph definitions chưa chứng minh lợi ích relations hoặc endpoint entailment. Không mở period-policy redesign.

## Implementation Evidence

Chưa commit; baseline48b9d78. Offline70 targeted PASS và23 final incremental PASS; fresh semantic probe5cases; xem báo cáo cho các live/quality limits. Không dùng engineering PASS để chứng nhận financial accuracy.

## Handoff Notes

Next action: hoàn tất checks và commit/push/CI.
