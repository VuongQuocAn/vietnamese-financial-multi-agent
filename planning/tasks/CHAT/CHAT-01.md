# TASK CHAT-01 — Multi-turn Conversational QA

## Metadata

- Milestone: CHAT
- Status: REVIEW
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

- [x] Kế thừa/chuyển công ty/kỳ/chủ đề, hỏi lại khi mơ hồ, session độc lập.
- [x] Answer qua pipeline hiện hữu, claims/citations verified; không lấy answer cũ làm evidence.
- [x] API/service create/send/history/reset và traces; storage lifecycle rõ ràng.
- [x] Bảy real scenarios, đo calls/latency, focused tests/CI, báo cáo và push main.

## Required Tests

Focused conversation/API/core QA; bảy real conversations offline; planning/diff/Ruff.
Không full regression; tối đa2 live Gemini calls nếu thực sự cần.

## Risks and Blockers

Giữ rõ giới hạn QA/source hiện hữu; không nâng smoke thành financial accuracy.

## Implementation Evidence

Implementation `21eec27791a8ea06ef7770803cc693bb72727fea` đã push main.
[CI42582799192](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42582799192)
SUCCESS đúng SHA:18Python/9Web PASS; full regression SKIPPED.
Local23supporting+3conversation tests PASS; Ruff/planning/diff PASS.
Bảy scenarios/20turns:13completed_with_caveats/1partial/5clarify/1blocked;
142citations/sáuclaims audit không mismatch/leakage;396source hashes unchanged;
0Gemini; resolver median5,730ms/max24,484ms. Chi tiết và giới hạn tại
[report](../../../docs/chat-01-multi-turn-qa.md).
Evidence local `artifacts/evidence/CHAT-01/run4/` + `document-fix/` cho S3 sau fix.

## Handoff Notes

Chờ Tech Lead nghiệm thu; session in-memory mất sau restart; Web inject approved
pipeline qua service contract. Giữ source-readiness/QA limitations S2/S7 và pending
GEN-01a/Web; không bắt đầu CORE-Check, WEB-02 hoặc M8.
Next action: Tech Lead review CHAT-01.
