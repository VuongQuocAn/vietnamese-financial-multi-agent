# TASK E2E-ARCH-02 — Full Pipeline Integration

## Metadata

- Milestone: E2E
- Status: DONE
- Priority: P1
- Dependencies: M5-PY-01, M6-PY-01, M7-ANSWER-01
- Estimated Complexity: S

## Objective

Kiểm tra Question → Adaptive Coordinator → Financial Tools/EF-EG/Python →
M6 obligations/verification → Ledger → M7 trên câu hỏi mới, xác định lỗi tích hợp.

## Context

Owner giao ngày17/11/2026, cho phép commit/push main. Remote baseline `28cabc4`;
worktree riêng bảo toàn local edits của checkout gốc. Theo ARCH-02 và contracts
M5/M6/M7 hiện có; không mở rộng kiến trúc hoặc thêm agent.

## Inputs

Qwen `qwen3-8b-awq-t4` qua Gateway; JSON/EF-EG đã import tại
`VFB-IMPORT-03/full-final`. Credentials chỉ ở cấu hình local bị ignore.
Bảy câu tự soạn, không đọc/dùng 45Pilot hoặc 600Full ViFinBench.

## Outputs

Runner giới hạn calls; trace từng câu, sources/runtime hashes, báo cáo kết quả,
coverage/citations/latency/agents/tools và phân loại nguyên nhân lỗi.

## Allowed Changes

Runner, sửa nhỏ lỗi tích hợp quan trọng có nguyên nhân rõ, targeted tests liên
quan, báo cáo và tracking tối thiểu. Giữ source JSON/EF-EG read-only.

## Out of Scope

Không OCR/Gemini, full CI, benchmark, tối ưu theo từng câu, vòng FIX kéo dài,
thay schema/pipeline hoặc thực hiện E2E-VAL-01.

## Implementation Steps

1. Xác minh Git baseline, cấu hình worker/model và dữ liệu đã import.
2. Chạy7câu mới gồm single-hop, multi-hop, numerical, Python và data gap.
3. Đối chiếu số/nguồn/goal bindings; tái dùng trace khi debug.
4. Chỉ sửa lỗi tích hợp rõ ràng, targeted checks và bounded retest nếu cần.
5. Commit/push main; bàn giao REVIEW, không tự nghiệm thu DONE.

## Acceptance Criteria

- [x] Pipeline chạy E2E trên câu hỏi thực tế, Python chỉ khi cần capability.
- [x] Báo cáo từng câu có kết quả, coverage, citations, latency và trace.
- [x] Lỗi quan trọng được phân loại, nêu sửa gì và giới hạn còn lại.
- [x] Source/local edits bất biến; không commit dữ liệu/secrets.
- [x] Có implementation SHA đã xác minh và trạng thái REVIEW.

## Required Tests

Live E2E là chính: tối đa40provider calls,10/câu,300s/câu, không chủ động retry
transport. Chỉ1–3targeted controls nếu sửa runtime, một smoke luồng liên quan.
Ruff file sửa, planning checker, git diff --check; không full CI.

## Risks and Blockers

Coverage theo inventory goals do model tạo, không phải nhãn completeness độc lập.
Nguồn JSON-only/page-level chưa chứng minh scan/PDF accuracy. Worker/model lỗi
được ghi rõ; không thay bằng execution giả hoặc provider khác.

## Implementation Evidence

**DONE — Owner xác nhận ngày17/11/2026**; nghiệm thu implementation và evidence
tại bàn giao `b4c84b3`, đã push main/remote SHA verified. Giữ các giới hạn đã báo.
Phiên đóng chỉ tài liệu/tracking và planning/diff/Git; không sửa runtime hoặc
chạy lại tests/Qwen/benchmark/CI, không triển khai E2E-VAL-01.

Implementation `84ae70a9172dc63b105f57663a5dd2eb31d321f2`;
[report](../../../docs/e2e-arch-02-full-pipeline-integration.md).
Sửa API ép tắt Gateway M7 trong V2; giữ quyền M6/Ledger và flags/budget.
7câu mới/8lượt,36calls/243807known tokens/1unknown;0retry. Final SH02 full1/1,
natural/5refs; PY07 cross-role→Python/Docker→M6 replay/3ACCEPT/G1–G3→Ledger v2→
M7 full3/3/8refs,99,037s. Giữ2partial/3không phát hành của mẫu unique, không GO Pilot.
6targeted PASS;185runtime blobs khớp SHA,57JSON/80local files bất biến.
Ruff/planning/diff; không fullCI/OCR/Gemini/benchmark. Owner đã nghiệm thu.

## Handoff Notes

Next action: chờ Owner giao E2E-VAL-01.
