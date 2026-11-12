# TASK E2E-GEN-01 — Kiểm thử tích hợp Multi-Agent trên dữ liệu tài chính thực tế

## Metadata

- Milestone: E2E
- Status: REVIEW
- Priority: P1
- Dependencies: QWEN-GEN-02
- Estimated Complexity: M
- Related Modules: M5, EF-EG/tools, M6, ledger, M7, document planner

## Objective

Đánh giá phối hợp thực tế trên12case tài chính đã freeze; không phải benchmark M8.

## Context

Owner giao nguyên task ngày12/11/2026. Baseline73525f6, implementation451d9fd;
working tree có local edits từ trước, ghi hashes thực tế và không sửa runtime.

## Inputs

PDF BBS2025/BCC2025, financial snapshots đã chấp nhận và verified document pins;
Qwen configuration hiện có, không đổi model/Thinking/timeout/credentials.

## Outputs

[Báo cáo](../../../docs/e2e-gen-01-multi-agent-integration.md), runner/tests;
references/config/freeze/provider events/per-case responses/ledger ở local ignored
`artifacts/evidence/E2E-GEN-01/`. Không commit financial source payloads hoặc secrets.

## Allowed Changes

Harness, focused offline checks, báo cáo và planning; commit/push file thuộc task
sau hoàn tất theo Owner. Không stage local changes khác.

## Out of Scope

Không sửa runtime/prompt/data, thêm agent/verifier, chạy Gemini/OCR/M8/full CI,
rerun QWEN-GEN-01 hoặc tối ưu từng câu. Không tự nghiệm thu DONE.

## Implementation Steps

Đối chiếu PDF, chọn3coordination/3cross-statement/2financial-document/2multi-step/
2negative; kiểm binding hai namespaces và freeze reference/config trước API.
Một preflight nhẹ qua Gateway, rồi đúng một pass12case, max6calls/case.
Lưu trace ngay mỗi call/case; lỗi endpoint hoặc HTTP400/401/403 dừng tức thì,
không retry/fallback; case lỗi INTERRUPTED, còn lại NOT_RUN.
Trạng thái báo cáo **PAUSED — WAITING FOR OWNER** khi dừng vì API; registry dùng
BLOCKED tương ứng tập trạng thái hợp lệ. Chỉ resume sau Owner xác nhận API,
giữ references/config/kết quả và bỏ qua COMPLETED, không chạy lại case thành công.

## Acceptance Criteria

- [x]12reference độc lập, công thức/operands, required points và source identities.
- [x]Coverage và financial/document binding được kiểm offline; freeze trướcAPI.
- [x]Một pass12case sau preflight; hoặc lưu rõ điểm dừng theo quy tắcAPI.
- [x]Phân tích correctness/completeness/grounding/citations/coordination/tools/M6/M7.
- [x]Kiểm toàn vẹn artifacts và báo cáo có giới hạn/đúng một next action.

## Required Tests

3focused offline harness controls, Ruff, planning checker, git diff --check.
Live evaluation là bằng chứng riêng; smoke không chứng minh financial accuracy.

## Risks and Blockers

Colab/tunnel có thể ngừng; dừng chờ Owner nếuAPI lỗi.6capability probes vẫn giữ,
không loại case khó hoặc coi M6ACCEPT là đáp án đúng. Reference do Codex đối chiếu
PDF, chưa independent human gold; citations còn page-level/uncertain geometry.

## Implementation Evidence

Đánh giá đã hoàn tất một pass12case:0PASS/5PARTIAL/7FAIL,7/35points;
19/22released claims grounded,3false-positive absence assertions C04.
33evaluation calls/94806tokens +1preflight/23tokens;0transport/retry.
22ACCEPT/8INVESTIGATE/4ABSTAIN; giữ22/22ledger claims sau final release.
3offline harness controls PASS;60retrieved facts/133source identity checks,
16proof operands/9arithmetic steps đúng;boolean greater đối chiếu trực tiếp.
778protected files vàreference/config hashes unchanged. Baseline đãxácminh
`73525f6e451bb85bc4965f8e3dec460e88a79334`; implementation/checkpoint SHA
sau commit/push nằm trong local completion-receipt và bàn giao. Không gánCI.

## Handoff Notes

Status REVIEW. Next action: Tech Lead nghiệm thu báo cáo trước CHAT-02/REPORT-01.
