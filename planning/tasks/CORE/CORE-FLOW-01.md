# TASK CORE-FLOW-01 — Consolidate and Repair the Multi-Agent QA Pipeline

## Metadata

- Milestone: CORE
- Status: DONE
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

Owner bổ sung: nối QA Gateway với FreeTierKeyPool hiện có và sửa tối thiểu projection
M7/numeric presentation cho calculation steps đã ACCEPT; targeted tests, fresh Q5 rồi
Q4/Q6/Q7/Q8. Một commit/push gộp khi đạt, xác minh CI đúng SHA, dừng REVIEW.
Không mở task FIX, không sửa M5/M6/Ledger.

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
- [x] Sửa Q5 được fresh live xác minh đúng; Q4/Q7 có kết luận semantic verified,
  Q6/Q8 hoàn tất cùng runtime; caveat Q6 ghi rõ để Tech Lead review.

## Required Tests

tests/unit/test_core_flow.py và nhóm M5/M6/M7 Lite/conversation; controls hiện có
cho Ledger tampering, scoped citation, calculation replay. Live E2E cùng câu hỏi,
không OCR hoặc benchmark mới. Engineering PASS không chứng minh financial quality.

## Risks and Blockers

Sửa key rotation/projection đạt fresh Q5; CONDITIONAL READY cho phạm vi này.
Q6 caveat về thiếu bảng cân đối còn mâu thuẫn giữa Specialists, không mở rộng sửa
M5/M6. Reporting_scope/page-level và generic M7 gaps giữ giới hạn, không financial
accuracy toàn hệ thống. Owner/Tech Lead nghiệm thu DONE về nhiệm vụ triển khai
ngày 11/11/2026, giữ các giới hạn đã báo.

## Implementation Evidence

Accepted implementation `0f6165546d2db7a130fbcca666d0e2abf95b7649`, parent f5baae3;
đã push main, gộp key rotation và sửa projection. [CI42958816077](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42958816077)
SUCCESS đúng SHA,207tests PASS; receipt local đã xác minh.37targeted PASS, Ruff/planning/
diff PASS; fresh Q5 đúng−8,66%/−14,35% với mẫu số đầu năm; Q4/Q6/Q7/Q8 cùng runtime.
28actual provider attempts/89857known tokens/3unknown,2HTTP429/1HTTP503.252focused
source/calculation/citation checks không mismatch;4204protected hashes unchanged.
Report chính dùng tên chỉ tiêu/số dễ đọc; câu trả lời nguyên văn và IDs ở raw trace.

## Handoff Notes

M7 nhận full operands/steps/results/units và kỳ gốc/mục tiêu của reasoning calculation
đã ACCEPT; không tính/verify lại. Giữ nguyên M5/M6/Ledger và local edits ngoài task.
Không tạo task mới, không OCR/M8/full local regression.

Phiên nghiệm thu chỉ cập nhật planning/report và chạy planning/diff checks;
không chạy lại tests/Gemini hoặc commit/push.

Next action: chờ Owner giao nhiệm vụ mới.
