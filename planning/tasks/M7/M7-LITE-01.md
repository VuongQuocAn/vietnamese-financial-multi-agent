# TASK M7-LITE-01 — Simplified Grounded Answer Generation

## Metadata

- Milestone: M7
- Status: REVIEW
- Priority: P1
- Dependencies: M7-05
- Estimated Complexity: M

## Objective

Triển khai M7 Lite sau feature flag, dùng Verified Ledger và Answer Agent qua Gateway.

## Context

Owner giao 11/11/2026; baseline/HEAD b9d0cdb88417a344f1269dbfb6cf7300b18824bd. Không tiếp tục FIX-02. Giữ local work.

## Inputs

Spec Owner M7-LITE-01; contracts M7/API/Gateway, Ledger và saved evidence FIX-02.

## Outputs

Lite runtime, flag mặc định false, tests, báo cáo docs/m7-lite-01-grounded-answer-runtime.md.

## Allowed Changes

M7 Lite, tích hợp API tối thiểu, tests/CI/planning; tối đa một implementation commit và push main.

## Out of Scope

M1–M6 nghiệp vụ, OCR, manifest M5/M6, M8, thay đổi dữ liệu gốc hoặc Ledger.

## Implementation Steps

Implementation → offline controls → tối đa 4 live Answer Agent calls (Q21/Q23/L08/L09) → so sánh → REVIEW.

## Acceptance Criteria

Legacy giữ nguyên; claims ACCEPT phù hợp được giữ; citations đúng; fallback; gaps A/B/C; live thật hoặc blocker trung thực; dừng REVIEW.

## Required Tests

Targeted selection/scope/numeric/citation/fallback/API/legacy, 12 negative controls theo spec Owner; planning/Ruff/diff; không full regression.

## Risks and Blockers

Không có semantic approval mới tại M7. Đoạn diễn giải không đủ chắc chắn phải fallback về nội dung ACCEPT. Không gọi live quá 4 lần hoặc retry.

## Implementation Evidence

Implementation `e6411ec06297676080052385a1e7199867fd37b3` đã push main; [CI42935098419](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42935098419) SUCCESS đúng SHA:185Python/9Web PASS.
155targeted +17final Lite PASS (overlap), real Q23 pipeline smoke không M5/M6/provider.
Live4calls:1success/1HTTP503/2HTTP429,317792known tokens/3unknown;12/12findings giữ,69refs/0binding errors.
3PARTIAL/1CORRECT_WITH_CAVEAT; chưa đạt phát hành paraphrase tự nhiên. Compact payload sau live chỉ offline replay.
[Report](../../../docs/m7-lite-01-grounded-answer-runtime.md);10.087protected files và11unrelated local files nguyên hash.

## Handoff Notes

Next action: Tech Lead review M7-LITE-01 với giới hạn live/chi phí/paraphrase; không tự DONE hoặc tiếp tục task khác.
