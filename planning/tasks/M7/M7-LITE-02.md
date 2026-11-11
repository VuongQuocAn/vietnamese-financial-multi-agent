# TASK M7-LITE-02 — Natural Answer Release

## Metadata

- Milestone: M7
- Status: REVIEW
- Priority: P1
- Dependencies: M7-05
- Estimated Complexity: S

## Objective

Phát hành câu trả lời diễn đạt tự nhiên từ verified findings mà không khớp nguyên văn.

## Context

Owner giao11/11/2026 sau review e6411ec. HEAD c102b8956356af6562c2558729a0e7ff373b09f3; M7-LITE-01 tiếp tục REVIEW, không DONE. Dependency kỹ thuật M7-05; follow-up không đòi nghiệm thu M7-LITE-01.

## Inputs

Quyết định Owner; qa_lite.py, tests và saved real Ledger b9d0cdb. Không đổi upstream.

## Outputs

Bỏ verbatim gate; numeric/ID/source checks; citations theo trang và bindings chi tiết backend; targeted tests; docs/m7-lite-02-natural-answer-release.md.

## Allowed Changes

M7 Lite, targeted tests và planning/report. Tối đa2 Gemini live calls sau offline PASS; payload compact, không retry. Owner đã cho phép đúng một commit/push với diff chỉ thuộc task và các checks vẫn PASS.

## Out of Scope

M1–M6, OCR, source/Ledger, legacy/report, semantic verifier mới, M5/M6 Lite, M8.

## Implementation Steps

Bỏ verbatim gate → numeric/claim/source integrity → gộp trang → offline controls/smoke → live Q23/L08 tối đa2calls → REVIEW.

## Acceptance Criteria

Paraphrase có numeric/ID/source hợp lệ được phát hành; fallback chỉ lỗi xác định hoặc output không dùng được; detailed source bindings không mất; live outcome trung thực.

## Required Tests

Targeted Lite/renderer + một integration smoke; malformed/unknown ID/unsupported number/rounding/provider fallback; planning/Ruff/diff. Không full regression.

## Risks and Blockers

Numeric matching không chứng minh semantic correctness. Không thêm gate ngữ nghĩa; prompt và manual live audit kiểm tra nhận định. Các kết luận M6 còn thiếu được ghi B, không cứu upstream.

## Implementation Evidence

Owner duyệt một commit/push sau final review diff/L08; SHA/CI đối chiếu sau push tại ignored commit-receipt.json; baseline `c102b8956356af6562c2558729a0e7ff373b09f3`; runtime hashes exact trước/sau live tại ignored artifacts/evidence/M7-LITE-02.
19targeted PASS; realQ23 pipeline smoke0calls/M5/M6; replay2natural segments; offline12/12findings/69→6references/0binding errors.
Live đúng2calls:L08success/3đoạnGemini được phát hành/no fallback/1945tokens;Q23HTTP503/unknown usage/fallback. Live7/7findings/0binding errors.
Ruff/planning/diff PASS; recheck19tests trên staged snapshot trước commit, CI exactSHA sau push; không full regression/live mới. Giữ8source/old receipts và11unrelated local files theo hash.
[Report](../../../docs/m7-lite-02-natural-answer-release.md). L08 CORRECT_WITH_CAVEAT; Q23 PARTIAL, chưa có natural-answer live success.

## Handoff Notes

Owner xác nhận Q23 HTTP503 là lỗi provider; dừng giai đoạn triển khai M7 Lite, không mở M7-LITE-03.
Next action: Owner/Tech Lead nghiệm thu implementation commit đã push; giữ REVIEW đến nghiệm thu.
