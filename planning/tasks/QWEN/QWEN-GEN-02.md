# TASK QWEN-GEN-02 — Pipeline Generalization Fix

## Metadata

- Milestone: QWEN
- Status: DONE
- Priority: P1
- Dependencies: QWEN-QA-01
- Estimated Complexity: M
- Related Modules: M5 Lite, M6 Lite, M7 Lite, document routing/harness

## Objective

Sửa nguyên nhân coverage/binding/semantic và status từ QWEN-GEN-01 trong một task giới hạn.

## Context

Owner giao bốn ưu tiên; QWEN-GEN-01 vẫn REVIEW, không tự nghiệm thu DONE.
Baseline8f9fde9 và local edits ngoài task giữ nguyên. Tech Lead đã yêu cầu focused final fix, commit/push và DONE có điều kiện.

## Inputs

QWEN-GEN-01 frozen references/traces, contracts hiện có, config Qwen local ignored.

## Outputs

Runtime fixes nhỏ, targeted offline controls/replays, một smoke nhỏ và report.

## Allowed Changes

M5 inventory/tool binding, prompt/context M6 hiện có, M7 coverage/confirmed scope,
routing thuyết minh và harness chọn snapshot theo loại nguồn. Không rewrite pipeline.

## Out of Scope

Không thêm agent/verifier, hardcode doanh nghiệp/câu hỏi, full CI hoặc rerun25câu;
không tạo scope review/approval mới hoặc sửa source data. Không FIX lặp sau smoke.

## Implementation Steps

Sửa bốn boundary; offline targeted failures+controls; một preflight và smoke4câu
(fact ngoài inventory cũ, phép tính, document note, negative), max6calls/câu,
không retry/fallback. API lỗi thì dừng ngay, giữ kết quả/NOT_RUN và chờ Owner.

## Acceptance Criteria

- [x] M5 inventory/selection dùng mapped EF-EG facts có binding; targeted inventory probes đạt.
- [x] M6 có evidence/operand IDs và prompt kiểm định nghĩa/qualifiers; một semantic call, không thêm verifier.
- [x] M7 giữ confirmed scope; bốn saved coverage replays đạt, missing-conclusion controls vẫn partial/blocked.
- [x] Routing note/harness không giới hạn sai financial snapshot; offline+live note đạt.
- [x] Một smoke4câu và [report](../../../docs/qwen-gen-02-pipeline-generalization-fix.md); focused final offline do Tech Lead cho phép, không API thêm.
- [x] Focused Q05 numeric binding offline: fact đúng ACCEPT, M7 phát hành; negative controls không false ACCEPT. Không tuyên bố mọi mapped fact đã được đánh giá.

## Required Tests

1–3 nhóm tests tổng quát, targeted compatibility, saved failures replay; Ruff/planning/diff.
Không full CI/25case benchmark; smoke thực4câu một lượt.

## Risks and Blockers

Model semantic còn có thể sai; không bảo đảm financial accuracy bằng engineering PASS.
Scope chưa confirmed vẫn chặn. SmokeQ05 lấy đúng fact nhưng final blocked bởi grammar M6; chưa chứng minh false semantic acceptance đã hết. Tech Lead cho phép một focused numeric binding fix cuối cùng; không live calls mới hoặc FIX tiếp.

## Implementation Evidence

Implementation 451d9fd52bca3c32075cce867d832ff854f0ae1e, đã push main/remote SHA verified; baseline8f9fde9. Tám runtime files,
3targeted tests mới, harness smoke và report.38targeted PASS;4saved replays+4controls,
3inventory+3note probes,0offline API. Smoke4câu:3dispositions đạt/1blocked;
8evaluation calls/19023tokens, cộng preflight9calls/19046tokens,0provider errors/retries.
Ruff/planning/diff checks đạt; runtime hashes nguyên từ freeze đến smoke cuối.
[Report](../../../docs/qwen-gen-02-pipeline-generalization-fix.md); local receipts ignored.
Focused final: shared numeric grammar dùng aliases canonical và xử lý row ordinal;
không đổi parse_number/numeric equality hoặc semantic gate.71focused PASS working tree và71PASS isolated staged source;
actual Q05 replay+4mutations offline,0API; isolated staged71PASS/planning136tasks; Python blobs đúng implementation đã commit.
Không full CI/25case rerun; giữ local edits khác; Tech Lead cho phép commit/push/DONE
khi điều kiện numeric binding/negative controls đạt. Điều kiện đã đạt, DONE theo Tech Lead;
không tuyên bố loại bỏ mọi semantic error hoặc full-PDF accuracy.

## Handoff Notes

Next action: dừng chuỗi QWEN-GEN, chờ Owner giao nhiệm vụ mới.
