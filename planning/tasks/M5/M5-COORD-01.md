# TASK M5-COORD-01 — Adaptive Coordinator & Task DAG

## Metadata

- Milestone: M5
- Status: REVIEW
- Priority: P1
- Dependencies: ARCH-02
- Estimated Complexity: S

## Objective

Qwen lập kế hoạch nhỏ, specialist dùng kết quả và bằng chứng của dependencies
qua coordinator V2 hiện có; có bằng chứng live, không yêu cầu accuracy cao.

## Context

Owner giao17/11/2026 theo [ARCH-02](../../../docs/arch-02-technical-specification.md).
Local HEAD966b73a và remote9678cb5 khác lịch sử; đồng bộ trong worktree riêng,
không đưa toàn bộ VFB-E2E-05/local edits vào implementation.

## Inputs

V2 IntegrationWorkspace/specialists, Financial Tools, EF-EG, corpus JSON tài chính
thật đã import; Qwen qua Shared Gateway, cấu hình môi trường, không lưu key.

## Outputs

Plan adapter, Task DAG/result revision1, API opt-in, targeted controls và báo cáo
Live Test ngắn có trace planning→tasks→specialist→tools/evidence→M6→M7.

## Allowed Changes

M5 wire/scheduling/workspace, API flag, runner tái dùng E2E hiện có,
targeted tests và tracking liên quan. Đồng bộ histories đã commit trước.

## Out of Scope

Python Agent, M6 feedback/repair, expansion patches, demand entity retrieval/join,
benchmark rộng, OCR/Gemini, thay M6/M7, xử lý toàn bộ local edits hoặc CI đầy đủ.

## Implementation Steps

1. Wire goals/tasks dùng indexes; backend cấp identity và giữ metadata unresolved.
2. Lập DAG độc lập thứ tự; execute/retrieve khi ready; giữ nhánh độc lập.
3. Lưu result refs/version, proof và source closure; downstream nhận dependencies.
4. Targeted validation, tối đa18 calls lượt live đầu; tối đa6 calls retest nếu cần
   sửa nguyên nhân tổng quát, không tối ưu từng câu hỏi.
5. Ghi REVIEW, commit/push main và xác minh SHA; Tech Lead nghiệm thu.

## Acceptance Criteria

- [x] Qwen lập plan hợp lệ qua schema goals/tasks nhỏ, không sinh internal IDs.
- [x] Forward dependencies chạy đúng; cycle/unknown task chỉ chặn closure liên quan.
- [x] Downstream nhận và sử dụng kết quả trung gian kèm source/proof closure.
- [x] Task lỗi/rỗng không xóa kết quả độc lập; M6/M7 và opt-out giữ đường cũ.
- [x] Live Test câu mới single-hop/multi-hop, trace và hạn chế rõ; không gọi smoke PASS là accuracy.
- [x] Implementation đã commit, trạng thái REVIEW; push/remote SHA xác minh khi bàn giao.

## Required Tests

Ba targeted controls adapter/DAG/pipeline, compatibility V2 liên quan;
Ruff, planning checker, diff check. Ưu tiên live Qwen trên dữ liệu thật.

## Risks and Blockers

Schema local validation không chứng minh endpoint constrained decoding. Proposal
chưa verified vẫn cần M6; phiên bản1 chưa hỗ trợ invalidation/repair. Chất lượng
OCR/canonical/unit/period và schema specialist cũ có thể giới hạn đáp án cuối.

## Implementation Evidence

Implementation SHA đã xác minh:
[`05289a439f2d5248065f4b8cc727ac7ea2aac215`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/05289a439f2d5248065f4b8cc727ac7ea2aac215).
177file runtime trong commit khớp receipt live-v2; chưa nghiệm thu DONE.
[Report](../../../docs/m5-coord-01-live-validation.md):21targeted/compatibility PASS;
3câu mới+1retest,7Qwen calls/29459known tokens/0unknown. V2 cuối phối hợp hai
specialist, Calculator7070123808VND,3ACCEPT có goal support và12M7citations.
Ruff lint/format, planning/diff local; không full CI/OCR/Gemini/benchmark.
57source hashes lượt đầu và24retest unchanged, runtime receipt v2 khớp code cuối.
Chờ Tech Lead review; giữ limitations/các task trước.

## Handoff Notes

Next action: Tech Lead review M5-COORD-01 và bằng chứng phối hợp v2.
