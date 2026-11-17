# TASK M6-OBL-01 — Evidence Obligations & Goal Binding

## Metadata

- Milestone: M6
- Status: REVIEW
- Priority: P1
- Dependencies: M5-COORD-02
- Estimated Complexity: S

## Objective

M6 kiểm chứng evidence obligations và goal support, truyền verified bindings
qua Ledger để M7 phát hành phần hợp lệ; giữ lại phần thiếu căn cứ.

## Context

Owner giao17/11/2026; ARCH-02 §7 và M5-COORD-02 DONE. Baseline main9a3adba;
worktree riêng bảo toàn local edits. M6 là authority duy nhất.

## Inputs

JSON/EF-EG đã có của BBS2025/ADC2021; Qwen qua SharedLLMGateway.

## Outputs

Obligations/replay selection/join; history/entry v2 lưu goal support và semantic
payload digest; feedback theo claim/task/goal/input/action. Báo cáo và trace local.

## Allowed Changes

M6 Lite/contracts/admission, M5 proposed bindings, API projection tối thiểu,
runner/targeted tests và tracking/report liên quan.

## Out of Scope

Coordinator Feedback Loop, Python Agent, semantic verifier/refactor M7, OCR/PDF,
Gemini, corpus mutation, full CI hoặc benchmark rộng.

## Implementation Steps

1. Đọc status/spec, kiểm Git và tạo worktree bảo toàn local edits.
2. Replay selection/join và lưu proof-bound goal support; tái dùng validators.
3. Targeted controls/live giới hạn, dừng REVIEW và commit/push main theo Owner.

## Acceptance Criteria

- [x] Replay nguồn/kỳ/context, domain/comparator/ties, join/cardinality và calculation.
- [x] Truth và goal support riêng; arithmetic không cấp selection/join/formula support.
- [x] Saved binding v2 round-trip/admission; goal thay đổi không reuse; v1 đọc được.
- [x] Non-ACCEPT/ACCEPT thiếu binding có feedback gắn claim/task/goal/evidence.
- [x] M6 live2ACCEPT với2bindings→ledger v2→M7 phát hành; phần còn lại giữ gap.
- [ ] Tech Lead nghiệm thu phạm vi và giới hạn live G1/ADC.

## Required Tests

51targeted PASS:3controls mới,24M6/V2/coordination và24ledger/fast-path.
Ruff/planning/diff check; không full CI.2câu mới fresh và1exact saved M5/live M6;
9actual Qwen calls/72284tokens. Chi tiết và trace tại report.

## Risks and Blockers

G1 selection chưa live positive:Qwen false-negative dù deterministic replay PASS.
ADC dừng trước M6 vì selection domain thiếu. BBS còn một nhánh M5 technical;
M7 phát hành phần đã verify kèm gap hiện có. JSON-only provenance, chưa PDF-verified
hoặc accuracy benchmark. REVIEW, không tự nghiệm thu DONE.

## Implementation Evidence

Implementation `801a6fd32dbd20dc62babfb95fb80bc8a5a1b51b`. [Report](../../../docs/m6-obl-01-live-validation.md).
Code đúng hashes receipt verify-release; local artifacts không commit nguồn/secrets.

## Handoff Notes

Next action: Tech Lead review implementation và giới hạn live G1/ADC.
