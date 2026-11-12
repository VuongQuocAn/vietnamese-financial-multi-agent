# TASK QWEN-GEN-01 — Kiểm thử tổng quát hóa Multi-Agent với Qwen

## Metadata

- Milestone: QWEN
- Status: BLOCKED
- Priority: P1
- Dependencies: QWEN-QA-01
- Estimated Complexity: S
- Related Modules: M5, EF-EG/Financial Tools, M6, M7

## Objective

Quick evaluation25câu mới với Qwen và reference độc lập, không M8.

## Context

Owner giao12/11/2026; PAUSED — WAITING FOR OWNER sau preflight thất bại.

## Inputs

PDF/evidence hiện có BBS/BCC, Qwen current config ignored, harness/tracing hiện có.

## Outputs

[Report](../../../docs/qwen-gen-01-generalization.md), references/traces local ignored.

## Allowed Changes

Docs/planning và nhận diện ID trong planning checker; không runtime.

## Out of Scope

Không sửa pipeline, thêm agent/verifier, retry provider, fallback model, full CI/M8.

## Implementation Steps

Preflight nhẹ; chọn5câu mỗi nhóm single/multi-hop/numerical/interpretation/unanswerable;
freeze reference có provenance và phép tính độc lập trước inference;25câu một lượt,
giữ cấu hình, chấm độc lập, ghi UNCERTAIN nếu thiếu chắc chắn. Dừng ngay khi API lỗi.

## Acceptance Criteria

- [ ] 25câu mới, đa dạng và reference cố định trước inference.
- [ ] Một lượt pipeline thật, đủ outputs/traces/usage/errors và metrics độc lập.
- [ ] Báo cáo nguyên nhân lỗi và kết luận, chuyển REVIEW chờ Tech Lead.
- [x] Preflight thất bại: dừng ngay,25NOT_RUN, không retry/fallback/đổi config.

## Required Tests

Planning checker và git diff --check; không full CI/smoke pipeline khi API lỗi.

## Risks and Blockers

BLOCKED tương ứng PAUSED — WAITING FOR OWNER:1preflight provider_unavailable,
HTTP status/usage UNKNOWN; không case thành công, còn25. Chưa freeze reference.

## Implementation Evidence

Baseline cbc307733fc76a92f0def390fd4cee11e9b9b8eb;1attempt/0,094s,0evaluation;
local evidence QWEN-GEN-01. Giữ local edits khác, không thay pipeline/dữ liệu.

## Handoff Notes

Next action: Owner kiểm tra/khởi động lại API và thông báo đã hoạt động.
