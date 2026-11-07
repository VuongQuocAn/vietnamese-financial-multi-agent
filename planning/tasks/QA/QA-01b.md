# TASK QA-01b — Multi-Agent Financial & Document Evidence Fusion

## Metadata

- Milestone: QA
- Status: REVIEW
- Priority: P1
- Dependencies: EF-01, EXT-01, QA-01a
- Estimated Complexity: L

## Objective

Thực hiện đề bài Owner giao 07/11/2026: mixed financial/document QA trên cùng
approved filing qua M5 → M4/BM25/EF-EG → M6 → Ledger → M7/Firewall.

## Context

EF-01/EXT-01/QA-01a đã DONE. Owner giao trực tiếp QA-01b, yêu cầu dừng REVIEW;
GEN-01a/Web đang pending được bảo toàn. Phạm vi L được chia thành planning,
binding/execution, verification/output và evaluation trong cùng task được giao.

## Inputs

Approved EXT-01 compositions, accepted BBS financial catalog và GEN-01 release
catalogs; giữ original identities, source quality và accounting gates.

## Outputs

Typed unified requirements, context binding, adaptive existing orchestration,
fusion trace, unified coverage/output, tests và 15–25 real QA cases/oracles.
[Report](../../../docs/qa-01b-multi-agent-evidence-fusion.md), local artifacts
`artifacts/evidence/QA-01b/`.

## Allowed Changes

M5–M7/application integration, bounded deterministic numeric generation,
source excerpt verification, runner/tests và planning QA-01b.

## Out of Scope

OCR, framework/database/agent mới, accounting-policy changes, cross-filing
comparison, GEN-01a/GEN-02/PERF-01/CHAT-01/M8/frontend redesign.

## Implementation Steps

Audit contracts → bind filing/composition → typed requirements → reuse existing
lanes → M6 individual proof → admitted Ledger → independently recomputed M7
requirements/Firewall → real QA/root-cause fixes/regression → commit/push/CI.

## Acceptance Criteria

Mixed QA có cả financial/document ACCEPT trên PDF thật, citations hai loại nguồn,
Firewall ALLOW hoặc ALLOW_WITH_CAVEAT. Partial không completed; causal inference
không có proof bị giữ là unmet. OCR defect INVESTIGATE, D03-B10/source/scope gates
giữ nguyên. Financial-only/document-only không hồi quy. Có trace/QA/oracles,
bounded live Gemini khi khả dụng, CI đúng SHA; dừng REVIEW.

## Required Tests

Relevant M4–M7, INT/QA-01a/EXT/EF regressions; source isolation, OCR/causal,
partial coverage, Firewall tampering và cache/restart controls; real PDF Quick QA.

## Risks and Blockers

Source excerpt chỉ là trích đoạn; không chứng minh toàn bộ thuyết minh hoặc quan
hệ nhân quả. Source-quality/accounting restrictions giữ nguyên.

## Implementation Evidence

Chưa commit; đang chạy targeted validation và real Quick QA.

## Handoff Notes

Giữ GEN-01a/Web local ngoài commit. Owner đã cho phép commit/push main.
Next action: hoàn thành integration và real Quick QA.
