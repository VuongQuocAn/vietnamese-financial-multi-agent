# TASK REC-01 — Conditional OCR Recovery & Approved Release Activation

## Metadata
- Milestone: REC
- Status: REVIEW
- Priority: P1
- Dependencies: PERF-01, GEN-02-Fix-B
- Estimated Complexity: M

## Objective
Recovery OCR có điều kiện và persistent approved-release activation.

## Context
PERF-01 DONE; H08 có approval thật; PDF30 tiếp tục quarantine.

## Inputs
Đặc tả Owner bên dưới, accepted EXT-01 và correction/policy Fix-B.

## Outputs
Runtime, focused tests, docs/rec-01-conditional-ocr-recovery.md và artifacts local REC-01.

## Allowed Changes
Conditional recovery, QA hook, exact release selection và targeted evaluation.

## Out of Scope
Không redesign M1/M5–M7; giữ frozen inputs và pending GEN-01a/Web.

## Implementation Steps
Theo Phase A–F trong đặc tả Owner bên dưới.

## Acceptance Criteria
Theo E1/E2/F1/F2; không tự approval; fail closed; không unsafe ACCEPT.

- Clean QA không thêm network, render/crop/PDF loading hoặc heavy recovery init.
- Trigger cần exact evidence/page/selector, OCR-quality flag, verified PDF/image,
  chưa có approved corrected version và còn request budget. Không trigger vì search
  miss, missing operands, sai scope/logic, ambiguity hoặc semantic-provider failure.
- Một Gemini attempt cho evidence/version/request, timeout mặc định khoảng8s,
  không retry429/503/timeout; đúng image binding, full page khi không có trusted bbox.
- Transcription structured có uncertainty/spans/page/selector/provider/usage/latency;
  không dùng self confidence như calibrated probability. Lưu proposal riêng, original
  read-only; unchanged không clear flag; uncertain/pending không sửa accepted source.
- Reviewer dùng DocumentCorrection/PDFTextReview/validate_correction/build_correction_version,
  CorrectionRelease/Approval/DocumentSourcePolicy hiện có; không giả independent review
  hoặc Tech Lead approval. Approved release không gọi Gemini lại.
- Persistent selection ghim logical document/composition/release/policy; only ready
  promotion với actual approval và original PDF/image provenance mới activate.
  Sai/thiếu config/source/pin phải unavailable, không fallback OCR quarantine.
- H08 BCC2024 PDF16 dùng actual approval đã có, một targeted QA E2E sau activation,
  restart vẫn đúng selection; đi qua M5/M6/Ledger/M7/Firewall, audit citations đúng
  trang/selector/snapshot. Không mặc định phải ACCEPT. PDF30/9 tiếp tục quarantine,
  không approval/activation, old defective claims/proofs vẫn blocked.
- Tối đa2fresh real passages/2live calls toàn task; ít nhất1qua trigger thật.
  Provider unavailable dùng recorded fixture và ghi rõ chưa xác minh live.
- Ba clean cases PERF-01 financial/document/mixed before/after cùng local config;
  ghi stage overhead và thực tế latency/output/citation/verification, không giả kết quả.

## Required Tests
Focused controls, một H08 E2E, tối đa hai fresh passages/calls; ba clean cases before/after.

13controls: clean; missing-no-flag; flagged+valid binding; wrong page/image/selector;
timeout; ambiguous; unapproved release; approved exact H08; wrong digest; PDF30;
warm ledger không hồi sinh defect; restart; không cross-snapshot leakage.
Focused lint/format/planning/diff checks; một CI đúng implementation SHA, chỉ chạy
lại nếu CI phát hiện regression mới. Không full40cases, corpus OCR, M8 hoặc live tuning.

## Risks and Blockers
Ghi trung thực provider timeout/quota; không retry. Tối đa hai vòng sửa/focused test.

Đã được Owner ủy quyền commit/push main và kiểm tra CI; chỉ stage task files,
giữ pending GEN-01a/Web. PERF-01 đã APPROVED, đồng bộ DONE nếu còn REVIEW.
Không reset/clean/force-push. Dừng REVIEW, không tự nghiệm thu DONE.

## Implementation Evidence
Implementation chưa commit/CI. Local vòng2:99focused PASS; H08 actual activation/
restart/2ACCEPT/stored/M7answered/2PDF16citations; PDF30/9 giữ quarantine.
Live1call invalid_request,usage/tokens unknown; recorded proposal/uncertainty riêng.
Clean3cases không OCR/PDF; detection0–0,0062ms; raw financial proof IDs khác do
timing/random origins, source citations/accepted content/decisions tương đương.
[Report](../../../docs/rec-01-conditional-ocr-recovery.md).

## Handoff Notes
Next action: Tech Lead review; không tự DONE hoặc bắt đầu task khác.
