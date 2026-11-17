# TASK M6-GOAL-FIX-01 — Fix Incorrect Goal Binding

## Metadata

- Milestone: M6
- Status: REVIEW
- Priority: P1
- Dependencies: M6-OBL-01
- Estimated Complexity: S

## Objective

Loại binding sai chỉ tiêu/kỳ/selection/formula trước khi M6 công nhận support,
giữ truth ACCEPT độc lập và bindings hợp lệ.

## Context

Owner giao17/11/2026, cho commit/push main. Baseline remote1aec917;
worktree riêng giữ local edits. M5-COORD-03 vẫn REVIEW, là nguồn trace của lỗi;
không tự nghiệm thu task đó hoặc mở M5-PY-01.

## Inputs

Saved M5-COORD-03 JSON/EF-EG trace, Ledger v2 và structured semantic verdict.

## Outputs

M6 binding filter dùng obligations/aliases/operation matcher hiện có; raw Qwen
và effective support có trace; targeted controls, saved replay/live và report ngắn.

## Allowed Changes

M6 obligations/runtime, targeted tests/runner và planning/report/contracts tối thiểu.

## Out of Scope

Coordinator/M7, verifier mới, G3 thiếu candidate, Python Agent, source mutation,
PDF/OCR/Gemini, full CI/benchmark và task khác.

## Implementation Steps

1. Tái hiện raw SUPPORTED→binding sai bằng saved trace.
2. Lọc concrete contradictions tại M6, tách truth khỏi goal support.
3. Targeted controls và1–2Qwen calls saved M5→M6→Ledger→M7; commit/push REVIEW.

## Acceptance Criteria

- [x] Sai item/year/selected period/formula không được cấp binding từ SUPPORTED.
- [x] Claim đúng vẫn ACCEPT; bindings hợp lệ giữ nguyên.
- [x] Saved Ledger/current support cùng áp dụng lọc; M7 chỉ phát hành phần hợp lệ.
- [ ] Targeted validation, live trace và implementation SHA đã xác minh; REVIEW.

## Required Tests

Ba controls mới, compatibility M6/goal/ledger liên quan;1–2live calls qua Gateway
trên saved M5 và nguồn JSON thật. Không chạy lại M5/Coordinator, không retry
transport hoặc full CI. Ruff/planning/diff check.

## Risks and Blockers

Chặn mâu thuẫn có anchors rõ, không thay semantic reasoning bằng bộ hiểu mọi
paraphrase. Ties/selection mơ hồ giữ gap, không đoán kỳ. JSON-only provenance.

## Implementation Evidence

Chưa commit; [report](../../../docs/m6-goal-fix-01-validation.md).
36targeted PASS;1actual Qwen call/15918tokens,0unknown/retry. Qwen vẫn trả
2G2 sai, M6 loại cả2; giữ G1/G4 và4truth ACCEPT→4Ledger v2→M7 2claims/12citations.
4proof payloads khớp actual semantic input;180runtime/24source hashes verified.
Encoder runner đã sửa và xuất M7 từ saved Ledger, không gọi API lại. Không sửa
Coordinator/M7/G3, OCR/PDF/Gemini hoặc full CI. Chờ Tech Lead nghiệm thu REVIEW.

## Handoff Notes

Next action: Tech Lead review implementation và trace để nghiệm thu M6-GOAL-FIX-01.
