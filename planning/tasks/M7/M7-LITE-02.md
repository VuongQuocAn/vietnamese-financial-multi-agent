# TASK M7-LITE-02 — Natural Answer Release

## Metadata

- Milestone: M7
- Status: DONE
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

Owner/Tech Lead APPROVED11/11/2026; M7-LITE-02 DONE, đóng giai đoạn M7 Lite.
Implementation [`a7da263db2e76e7ec07d8020f320c4b951dd9695`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/a7da263db2e76e7ec07d8020f320c4b951dd9695) đã push main; đúng1commit/7files thuộc task.
[CI42939001230](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42939001230) SUCCESS exactSHA:186Python/9Web;19staged tests/Ruff/planning/diff PASS.
Evidence live/offline giữ nguyên: L08 phát hành3đoạnGemini/no fallback/1945known tokens;Q23HTTP503/1unknown usage;
offline12/12findings/69→6references,live7/7findings/0binding errors; original sources/local work được giữ.
[Report](../../../docs/m7-lite-02-natural-answer-release.md). Phiên nghiệm thu chỉ cập nhật tài liệu; không chạy lại tests/CI/Gemini.

## Handoff Notes

Giai đoạn M7 Lite đã đóng; Q23 HTTP503 là lỗi provider, không sửa M7 tiếp hoặc mở M7-LITE-03/M5/M6 Lite/M8.
Giữ các giới hạn và evidence lịch sử; không tự triển khai task mới.
Next action: chờ Owner giao nhiệm vụ mới.
