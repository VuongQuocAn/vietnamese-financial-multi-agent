# TASK QWEN-QA-01 — Sửa claim Calculator và trình bày ACCEPT

## Metadata

- Milestone: QWEN
- Status: REVIEW
- Priority: P1
- Dependencies: -
- Estimated Complexity: S
- Related Modules: M5 Lite/shared grounding, M7 Lite

## Objective

Thực hiện ba ưu tiên Owner duyệt sau QWEN-DIAG-01: M7 chỉ trình bày ACCEPT,
derived calculation độc lập và contract M5 rõ source/analysis/operands.

## Context

Owner giao12/11/2026; không thêm verifier hoặc ép semantic mọi claim.
Baseline HEAD82781f9 và local edits hiện có. Owner giao tiếp: commit đúng task,
chạy fresh hai câu BBS qua Qwen và báo đầy đủ answer/M6/agent/tools/latency/errors.
Chỉ DONE khi cả hai đúng, đầy đủ và không phát hành nhận định sai.

## Inputs

Spec trực tiếp từ Owner; QWEN-DIAG-01; captured Qwen payloads và catalogs BBS/BCC.

## Outputs

3 runtime files,3 tests mới và expectations M7 liên quan;
[báo cáo](../../../docs/qwen-qa-01.md); evidence ignored QWEN-QA-01, ledger riêng.

## Allowed Changes

M5 Lite/shared grounding và M7 Lite, targeted tests; docs/planning/checker nhận ID QA.
Giữ các hunks local có sẵn trong specialist_common và các file khác.

## Out of Scope

Không M6/Gateway/Vision/OCR changes, thêm verifier, Gemini calls, full CI/M8 hoặc
rewrite source data. Chỉ commit task hunks; fresh Qwen giới hạn hai câu, tối đa12
provider calls/run và6/câu,300s/câu; không replay/fallback hoặc tự mở FIX tiếp.

## Implementation Steps

M7 render từ entries ACCEPT; bật derived độc lập; chuẩn bị source caveats/operands
đúng ownership; replay hai BBS cases và control BCC, targeted tests và checks.

## Acceptance Criteria

- [x] Replay tỷ lệ nợ/tài sản không phát hành diễn giải đảo chiều.
- [x] Replay tăng trưởng có26,71% từ derived claim được M6 ACCEPT dù analysis26,8% sai.
- [x] Control ngoài BBS xác nhận tổng quát, không hardcode figures/questions trong runtime.
- [ ] Hai câu fresh Qwen đúng, đầy đủ và không phát hành nhận định sai (chờ auth hợp lệ).

## Required Tests

3 tests mới +29 existing targeted,2 BBS replay và2 BCC pipeline controls.
Ruff, planning checker, diff checks; hai fresh Qwen questions theo ngân sách trên;
không full CI. Dùng config ngoài source và ledger riêng.

## Risks and Blockers

Replay Q1 chưa có semantic verdict live; Q2 giữ gap lịch sử. BCC là nguồn thật
nhưng agent payload control synthetic; không suy thành live financial accuracy.
Hai lần fresh bị DNS11001 và HTTP401; chưa có Qwen output để xét DONE.

## Implementation Evidence

Implementation local `019d85260b5fadf2d88c2bc4d605a1e7b3da9fee`, đúng12task files/hunks,
chưa push. Isolated commit tree:32targeted/planning134/Ruff/diff PASS.
Offline:2BBS replay,2BCC controls PASS. Fresh lần1:6attempts/DNS11001;
lần2 theo URL Owner cập nhật:2attempts/HTTP401, Gateway ngừng model stages sau auth.
Chưa có successful inference, usage UNKNOWN. M6 fallback Q1 ACCEPT3/ABSTAIN1,
Q2 ACCEPT2; cả hai partial, thiếu interpretation/%tăng trưởng, không DONE.
Full answers/latency/traces tại báo cáo; M6 và original evidence giữ nguyên.

## Handoff Notes

Next action: Owner cung cấp API key hiện hành hoặc api_info.json mới để tiếp tục
hai câu fresh còn chờ nghiệm thu.
