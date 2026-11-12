# TASK QWEN-GEN-01 — Kiểm thử tổng quát hóa Multi-Agent với Qwen

## Metadata

- Milestone: QWEN
- Status: REVIEW
- Priority: P1
- Dependencies: QWEN-QA-01
- Estimated Complexity: S
- Related Modules: M5, EF-EG/Financial Tools, M6, M7

## Objective

Quick evaluation25câu mới với Qwen và reference độc lập, không M8.

## Context

Owner giao12/11/2026; checkpoint837975a đã pause do preflight lỗi API.
Owner sau đó cung cấp config mới và yêu cầu thử lại; preflight mới có inference.
Hoàn thành25attempts một lượt,4case UNCERTAIN vì snapshot binding của harness,
không tự rerun/sửa pipeline để tăng điểm. REVIEW chờ Tech Lead đánh giá bằng chứng.

## Inputs

PDF/evidence hiện có BBS2025, BCC2025 riêng và BCC2024 hợp nhất;
Qwen current config mới ignored; pipeline/tracing hiện có, runtime local edits giữ nguyên.

## Outputs

[Report](../../../docs/qwen-gen-01-generalization.md); references/freeze/execution/provider
traces/ledgers và independent audit tại artifacts/evidence/QWEN-GEN-01/resume-01 (ignored).

## Allowed Changes

Docs/planning; helpers evaluation chỉ trong ignored evidence, không runtime/model prompt.

## Out of Scope

Không sửa M5/M6/M7/Gateway, thêm agent/verifier, retry provider, fallback model, full CI/M8.

## Implementation Steps

Đã preflight, chọn5câu/nhóm, đọc13trangPDF và freeze reference trước case inference;
chạy25requests một lượt, ledger mới/case, max6calls/case/300s. Giữ cấu hình;
đối chiếu độc lập nội dung, source, formulas, schema và metrics; ghi UNCERTAIN rõ nguyên nhân.

## Acceptance Criteria

- [x] 25câu đa dạng, không lặp hai câu QWEN-QA-01; reference cố định trước inference.
- [x] 25attempts và25response contracts có traces; ghi rõ4harness-confounded cases, không tuyên bố25case hợp lệ.
- [x] Metrics độc lập, unsupported claims và root causes; báo cáo REVIEW chờ Tech Lead.
- [x] Preflight cũ thất bại đã dừng ngay; chỉ resume sau Owner cấp config mới, không auto retry/fallback.

## Required Tests

Offline artifact audit/contract/ledger/citation/count/hash checks và transcript replay;
planning checker, git diff --check. Không unit/full CI hoặc provider calls bổ sung.

## Risks and Blockers

API hoạt động trong lượt hiện tại.4case Q16/Q17/Q19/Q20 UNCERTAIN do harness bind
financial snapshot cho document notes; không quy thành lỗi Qwen/BM25 và không rerun.
Source-answerable coverage thấp;2released claims thiếu hỗ trợ; pipeline chưa ổn định.
Đây là task evaluation, không yêu cầu chất lượng model PASS để nộp report REVIEW.

## Implementation Evidence

Runtime baseline837975adf2f56dcb02441691e7dfaf405365f207 + các local dependencies/edits
có sẵn; source snapshot/hash receipts local, unchanged sau run. Không implementation runtime mới.
25attempts:4PASS/7PARTIAL/10FAIL/4UNCERTAIN.21evaluable:4/16answerable đúng,
4/5abstention đúng, completeness13/40. M6ACCEPT48/ABSTAIN4/INVESTIGATE1.
61evaluation calls,121812input+11897output=133709tokens,0transport errors/retries;
preflight mới thêm1call/23tokens.2/37released claims unsupported, citations support12/14.
JSON60/61, stage shape55/61; engineering response contracts25/25 và trace counts/hash checks PASS.
Checkpoint task là docs/planning của commit chứa report này; SHA push được xác minh
trong final handoff/local receipt. Không stage local edits khác hoặc dữ liệu/secrets.

## Handoff Notes

Next action: Tech Lead review báo cáo, bốn harness confounds và thứ tự ưu tiên tiếp theo.
