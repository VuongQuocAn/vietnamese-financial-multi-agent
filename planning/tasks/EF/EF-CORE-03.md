# TASK EF-CORE-03 — Targeted Quality & Graph Efficiency Improvements

## Metadata

- Milestone: EF
- Status: DONE
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
- [x] Targeted final checks, commit/push và CI đúng SHA; bàn giao REVIEW.

## Required Tests

Targeted P1–P4, snapshot/citations, CORE-FLOW calculations; BBS C1/D1/B2/C3/Q5; mini diagnostic A/B/C; Ruff/planning/diff và CI.

## Risks and Blockers

Provider503; Q5 chưa tái hiện đủ phần trăm, C3 context/period cũ; graph definitions chưa chứng minh lợi ích relations hoặc endpoint entailment. Không mở period-policy redesign.

## Implementation Evidence

Status: **DONE — Tech Lead APPROVED có điều kiện ngày11/11/2026**, trong phạm vi P1–P4; giữ các quality limitations đã báo cáo. [Implementation cec9f44](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/cec9f44f5dc610e306e2cbfb20dde18f6984f1d1) đã push main; [CI42985614260](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42985614260) SUCCESS đúng SHA,217Python PASS; Web/full regression SKIPPED. 71staged targeted PASS; P1 isolation/P2 metadata/P3 coverage/P4 reuse. BBS setup−27,06%/traversal−16,12%,18rawresponses exact. C1 đủ biến động; D1 endpoints/C3/Q5 còn partial. 15fresh E2E+1semantic batch,56provider attempts/188331known tokens/4unknown invocations; 82fact/1287citation occurrences0mismatch;15unrelated tracked files/PDF digest giữ nguyên. [Report](../../../docs/ef-core-03-targeted-quality-graph-efficiency.md). Không M8/model khác, không tuyên bố accuracy tăng. Next action: chờ Owner/Tech Lead giao nhiệm vụ mới.

## Handoff Notes

Phiên nghiệm thu chỉ cập nhật tài liệu/planning; không tối ưu graph, chạy lại tests/live/CI hoặc thay đổi runtime/dữ liệu.

Next action: chờ Owner/Tech Lead giao nhiệm vụ mới.
