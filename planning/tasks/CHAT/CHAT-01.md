# TASK CHAT-01 — Multi-turn Conversational QA

## Metadata

- Milestone: CHAT
- Status: IN_PROGRESS
- Priority: P1
- Dependencies: REC-01
- Estimated Complexity: M

## Objective

Hội thoại nhiều lượt tiếng Việt với context có cấu trúc, giữ authority M6/M7.

## Context

Owner giao09/11/2026 theo attachment CHAT-01; main baseline423514b.
REC-01 DONE có giới hạn; giữ pending GEN-01a/Web và source inputs read-only.

## Inputs

FinancialQAPipeline, approved BBS/BCC catalogs/compositions và contracts.

## Outputs

Conversation service, HTTP adapter, focused tests, runner và báo cáo
`docs/chat-01-multi-turn-qa.md`.

## Allowed Changes

Conversation layer/API, targeted CI simplification và planning; commit/push main.

## Out of Scope

OCR/REC, accounting formulas, M5–M7 redesign, Web UI, full regression/M8.

## Implementation Steps

Resolve deterministic context → QA binding → verified state update → real scenarios → REVIEW.

## Acceptance Criteria

- [ ] Kế thừa/chuyển công ty/kỳ/chủ đề, hỏi lại khi mơ hồ, session độc lập.
- [ ] Answer qua pipeline hiện hữu, claims/citations verified; không lấy answer cũ làm evidence.
- [ ] API/service create/send/history/reset và traces; storage lifecycle rõ ràng.
- [ ] 5–8 real scenarios, đo calls/latency, focused tests/CI, báo cáo và push main.

## Required Tests

Focused conversation/API/core QA; bảy real conversations offline; planning/diff/Ruff.
Không full regression; tối đa2 live Gemini calls nếu thực sự cần.

## Risks and Blockers

Giữ rõ giới hạn QA/source hiện hữu; không nâng smoke thành financial accuracy.

## Implementation Evidence

Chưa commit. Evidence local tại `artifacts/evidence/CHAT-01/`.

## Handoff Notes

Next action: triển khai và kiểm chứng CHAT-01; dừng REVIEW cho Tech Lead.
