# TASK CORE-FLOW-01 — Consolidate and Repair the Multi-Agent QA Pipeline

## Metadata

- Milestone: CORE
- Status: REVIEW
- Priority: P1
- Dependencies: M5-LITE-01, M6-LITE-01, M7-LITE-02
- Estimated Complexity: M

## Objective

Khôi phục luồng semantic M5 → M6 → Ledger → M7, đo bằng câu trả lời có nguồn.

## Context

Owner giao 11/11/2026; baseline a92bc8f. Một task tích hợp thống nhất theo spec
Owner; không tách FIX, thêm agent hay revision loop. E2E-LITE-01 còn REVIEW,
chưa có xác nhận nghiệm thu để chuyển DONE.

## Inputs

Spec Owner đính kèm; báo cáo E2E-LITE-01 và cùng tám case/chín lượt BBS2025.
Gemini thật qua Gateway, không giới hạn tổng 4/8 calls; giữ giới hạn từng request.

## Outputs

[Báo cáo](../../../docs/core-flow-01-boundary-alignment.md), runner
scripts/evaluate_core_flow.py; artifacts riêng ignored artifacts/evidence/CORE-FLOW-01/.

## Allowed Changes

M5 Lite, contract operands tối thiểu, M6 Lite, điều phối/context/conversation,
M7 Lite, targeted tests, planning/checker và báo cáo. Một implementation commit/push
main nếu validation đạt; xác minh CI đúng SHA.

## Out of Scope

Không sửa raw/OCR/canonical/EF-EG đầu vào, extraction, Web, M8 hoặc kiến trúc mới.
Giữ mọi local edits trước task; runtime đánh giá dùng baseline + task overlay riêng.

## Implementation Steps

1. Đọc E2E/root causes, bảo toàn local edits.
2. Sửa thống nhất ranh giới và contracts cần thiết.
3. Targeted controls và live E2E; sửa tiếp khi có lỗi thực tế, không replay giả live.
4. Báo cáo, commit/push/CI khi đủ điều kiện, dừng REVIEW.

## Acceptance Criteria

- [x] Semantic plan/tools, facts/metrics/interpretations được chuyển M6 đúng nguồn.
- [x] M6 kiểm chứng interpretations, không dùng display label làm identity.
- [x] Current-request claims và comparative operands giữ qua Ledger/M7.
- [x] Context từ báo cáo và follow-up một tham chiếu rõ hoạt động.
- [x] Tám case được đánh giá trên câu trả lời cuối, có citations và provider trace.
- [x] Targeted tests/Ruff/planning/diff đạt; không dữ liệu/secrets trong commit.
- [ ] Sửa Q5 cuối được live xác minh đúng; Q4/Q7 có kết luận semantic verified
  và câu trả lời đáp ứng phạm vi trên implementation cuối khi provider hết429.

## Required Tests

tests/unit/test_core_flow.py và nhóm M5/M6/M7 Lite/conversation; controls hiện có
cho Ledger tampering, scoped citation, calculation replay. Live E2E cùng câu hỏi,
không OCR hoặc benchmark mới. Engineering PASS không chứng minh financial quality.

## Risks and Blockers

Provider503/429 chặn live cuối; Q5 từng sai mẫu số trong paraphrase. Đã sửa và có
control offline, chưa live xác minh thành công. NOT READY; không tự DONE.

## Implementation Evidence

Implementation là commit chứa spec/report này; SHA và CI đúng SHA tại receipt
local artifacts/evidence/CORE-FLOW-01/receipt.json và bàn giao sau commit.
75 targeted trên bản stage trước retry refinement; 6 controls cuối local PASS;
29staged final PASS; Ruff/planning/diff PASS, CI exactSHA chờ sau push và ghi receipt.
Live106attempts/182239known tokens,
28unknown,21HTTP503/7HTTP429; tám case/chín lượt đủ bộ trước sửa Q5 cuối.
783source/metric/citation checks không mismatch, nhưng Q5 câu trả lời sai nghĩa
phần trăm được ghi riêng, không gọi financial accuracy PASS.

## Handoff Notes

Next action: chạy lại live Q4–Q8 trên implementation commit khi provider hết429,
đối chiếu Q5 trước Tech Lead nghiệm thu.
