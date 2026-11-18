# TASK E2E-GATE-09 — Ổn định Qwen và kiểm thử 9 QA

## Metadata

- Milestone: E2E
- Status: REVIEW
- Priority: P1
- Dependencies: QWEN-THINK-01
- Estimated Complexity: S

## Objective

Xác minh Multi-Agent E2E trên dữ liệu thật sau ARCH-SIMPLIFY-02 và bàn giao
căn cứ để Tech Lead quyết định Pilot 45.

## Context

Baseline `17ab3ff`. Hai call từ ARCH-SIMPLIFY-02 dừng ở giới hạn HTTPX 60 s
dù deadline QA còn thời gian. Worktree riêng bảo toàn checkout gốc.

## Inputs

Manifest 9 QA cố định của E2E-VAL-01, corpus pin E2E-REMED-04 và Qwen Thinking
đang phục vụ với context 24K.

## Outputs

Runtime đã freeze, receipts preflight và [báo cáo 9 QA](../../../docs/e2e-gate-09-live.md).

## Allowed Changes

Đồng bộ ngân sách client/Gateway, kiểm thử trọng tâm và tài liệu bàn giao.

## Out of Scope

Colab, model, context, corpus, Gold, thay kiến trúc, OCR, Gemini, full CI,
Pilot 45 và Full600.

## Implementation Steps

Đọc trace timeout, kích hoạt profile Thinking có sẵn, giữ cap output của từng
stage trong context 24K, dùng tối đa hai probes rồi freeze một SHA cho 9 QA.

## Acceptance Criteria

- [x] Lỗi timeout được định vị và deadline được kiểm offline.
- [x] Có kết quả hai probes và cả 9 QA trên cùng SHA.
- [x] Bàn giao metrics, lỗi và SHA đã xác minh cho Tech Lead.

## Required Tests

11 targeted tests PASS, gồm RequestGateway/adapter và đường tích hợp M5–M7.
Hai probes riêng lẻ là giới hạn preflight.

## Risks and Blockers

Hai QA gặp HTTP 524. Các lỗi model gồm mở rộng goal, sai tool request,
chọn sai phạm vi chỉ tiêu và diễn giải sai ratio.

## Implementation Evidence

Implementation `5022a42e9634dc6718e562b65f8122cfc8834441`. Hai probes, 9/9 QA,
1 correct, 2 partial, 0 incorrect và 6 abstain.

## Handoff Notes

Next action — Tech Lead quyết định có chuyển sang Pilot 45.
