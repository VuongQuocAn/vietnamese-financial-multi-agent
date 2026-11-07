# TASK QA-01a — Document Claim Verification & End-to-End Integration

## Metadata

- Milestone: QA
- Status: REVIEW
- Priority: P1
- Dependencies: INT-01b
- Estimated Complexity: M

## Objective

Trả lời câu hỏi về tài liệu qua M5, M6, Verified Claim Ledger và M7 bằng evidence
đã pin của PDF thật.

## Context

INT-01a đã materialize nguồn gốc. INT-01b đã có BM25 và neighboring evidence.

## Inputs

Approved compositions, original snapshots, evidence repository và metadata của
PDF từ caller. Đề bài QA-01a do Owner giao ngày 07/11/2026.

## Outputs

Đường chạy document trong FinancialQAPipeline, typed proof, yêu cầu M7 và
[báo cáo](../../../docs/qa-01a-document-claim-verification.md).

## Allowed Changes

M5–M7, application pipeline, test/runner và planning liên quan.

## Out of Scope

Hybrid QA, OCR, EF-EG enrichment, M8 và GEN-01a.

## Implementation Steps

Bind composition, lập kế hoạch BM25, tạo candidate, phân giải lại nguồn tại M6,
replay khi nhập Ledger và kiểm tra độc lập khi xuất qua M7.

## Acceptance Criteria

B09 và TableEvidence chạy trên nguồn thật. Vai trò thiếu quan hệ được giữ là
chưa xác minh. Thiếu nguồn, trộn request và thay đổi citation đều bị chặn.

## Required Tests

Quick QA trên saved evidence, controls về proof/coverage/firewall và hồi quy
financial. Kiểm tra CI đúng SHA.

## Risks and Blockers

OCR và tọa độ chưa được xác minh độc lập. Chưa có semantic review cho audit
opinion. Luồng document chạy xác định với saved evidence.

## Implementation Evidence

Implementation `d2b28634adc6a24b0d019de00897cbf3ce26a781`, [CI42318884258](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42318884258) SUCCESS.
Quick QA 10/10, 67 targeted PASS sau bản sửa định tuyến. Xem báo cáo và artifacts local tại `artifacts/evidence/QA-01a/verified-run/`.

## Handoff Notes

Next action: Tech Lead nghiệm thu QA-01a.
