# TASK ARCH-01a — Adaptive Evidence-Guided Multi-Agent Framework Review

## Metadata

- Milestone: ARCH
- Status: REVIEW
- Priority: P1
- Dependencies: -
- Estimated Complexity: M
- Related Modules: M5, Financial Tools/Python, EF-EG, M6, ledger, M7, Gateway

## Objective

Review kiến trúc E2E tổng quát và nghiên cứu liên quan; đề xuất cải tiến có thể
tái sử dụng V2, định hướng thực nghiệm và các quyết định cần đặc tả trong ARCH-02.

## Context

Owner giao ngày 17/11/2026 với tên ARCH-01. ID ARCH-01 đã DONE cho audit ngày
06/11; giữ lịch sử, dùng suffix chưa sử dụng ARCH-01a cho review mới. Các báo cáo
E2E/diagnostic còn REVIEW chỉ là inputs, không khai thành dependency DONE và
không yêu cầu mở lại implementation của chúng.

## Inputs

AGENTS, current-status, architecture/module-boundaries/data-contracts; code V2
working tree; VFB-E2E-03/04/05, ARCH-RESET-01, QWEN-DIAG-01; nghiên cứu gốc công
khai đến ngày review. HEAD `966b73a17dcf1a573f485ccc67f2ffb3be4bee0d` và local
edits có trước; không coi HEAD riêng là runtime live-v6.

## Outputs

[Báo cáo](../../../docs/arch-01-adaptive-multi-agent-review.md) gồm RCA/code
reuse, đối chiếu nghiên cứu, kiến trúc/technical decisions, hypotheses/evaluation
và nội dung ARCH-02. Registry/current-status/dashboard đồng bộ tối thiểu.

## Allowed Changes

Báo cáo và planning thuộc review này; bảo toàn local edits. Owner giao tiếp
commit/push tài liệu ARCH-01a lên main; không đưa code/task khác vào commit.

## Out of Scope

Không sửa runtime/schema/tests, không chạy Qwen/Gemini/OCR/benchmark/full CI,
không triển khai ARCH-02, không sửa riêng câu benchmark hoặc tự nghiệm thu DONE.

## Implementation Steps

1. Đọc status/spec liên quan, kiểm Git và code paths hiện tại.
2. Đối chiếu historical evidence với code; phân biệt observed/inferred/proposed.
3. Khảo sát primary sources, chú ý công trình gần hướng đề xuất và novelty limits.
4. Viết thiết kế/đánh giá có thể bác bỏ; kiểm docs/planning và bàn giao REVIEW.

## Acceptance Criteria

- [x] Đánh giá đủ M5/Python/EF-EG/M6/feedback/M7/LLM schema và phần tái sử dụng.
- [x] Phân tích E2E05 final regression, không lấy lượt tốt nhất làm code hiện tại.
- [x] Nguồn nghiên cứu gốc; nêu MoCA-Agent/CLAIR-Fin/AuditFlow gần hướng đề xuất.
- [x] Có hypotheses, fair baselines/ablations, held-out/PDF scan evaluation.
- [x] Có decisions/acceptance cần đặc tả trong ARCH-02, chưa triển khai.
- [ ] Tech Lead nghiệm thu thiết kế và chốt phạm vi bước tiếp theo.

## Required Tests

Docs-only: `python scripts/check_planning.py`, `git diff --check`; kiểm fingerprint
src/schema trước/sau. Không smoke/pytest/live calls hoặc chạy lại evidence cũ.

## Risks and Blockers

Chưa có kết quả live/ablation mới; novelty chưa xác lập. Endpoint schema
enforcement, Python isolation/proof boundary và ngân sách pilot cần Tech Lead
chốt trong đặc tả tiếp theo. Không dùng replay làm bằng chứng semantic correctness.

## Implementation Evidence

Baseline review đã xác minh ở Inputs. Bản publish chỉ tài liệu, đặt trên remote
main `2b3c2ab` để giữ bốn commit local ngoài task chưa push. Chi tiết validation
lịch sử/fingerprint tại report; phiên publish không chạy lại tests hoặc CI thủ công.
Commit publication tra bằng Git history của báo cáo; trạng thái giữ REVIEW.

## Handoff Notes

REVIEW; không mở ARCH-02. Next action duy nhất: Tech Lead review báo cáo và chốt
bốn quyết định tại §6 để giao phạm vi đặc tả ARCH-02.
