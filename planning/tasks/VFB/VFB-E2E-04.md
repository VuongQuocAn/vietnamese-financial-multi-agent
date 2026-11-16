# TASK VFB-E2E-04 — Root Cause Analysis & Targeted Fix

## Metadata

- Milestone: VFB
- Status: DONE
- Priority: P1
- Dependencies: VFB-IMPORT-03
- Estimated Complexity: M

## Objective

Định vị15trace E2E03, sửa nguyên nhân gốc tác động lớn trong điều phối/truy xuất,
kiểm lại tối đa5câu đại diện với Qwen; Owner đã chấp thuận, đóng DONE sau commit.

## Context

Owner16/11/2026 tiếp tục E2E03 REVIEW; không tự nghiệm thu task cũ.
HEAD `f769a12e8f5cf62759018454e167ee9335153988`, giữ local edits có sẵn.
Owner chấp thuận kết quả và cho commit/đóng DONE ngày16/11/2026.

## Inputs

E2E03/run-v2 read-only,41JSON bundles IMPORT03, source JSON và Qwen Owner đã cấp.
Gold chỉ dùng phân tích/hậu kiểm, không đưa vào answering/prompt/mapping values.

## Outputs

RCA15câu, targeted code/tests, projection mới riêng nếu mapping đổi, live before/after
trên5câu: SH0016/SH0080/MH0018/NR0077/NR0103; report và artifacts ignored E2E04.

## Allowed Changes

Supervisor prompt/plan graph decisions, source-backed aliases, routing/context
và coverage binding nếu cần; tái sử dụng contracts/agents/tools/Gateway.

## Out of Scope

OCR, benchmark600/toàn15live, thêm agent/kiến trúc mới, hardcode Gold/answers,
loại gates thiếu authority, push hoặc sửa artifacts cũ. Commit đã được Owner cho phép khi đóng task.

## Implementation Steps

1. Phân biệt evidence có trong nguồn với canonical/retrieval/authority thiếu.
2. Sửa prompt bị ghi đè, kích hoạt graph theo composite evidence need,
   mapping alias và routing/context bugs đã có trace; kiểm offline có giới hạn.
3. Một pass5Qwen questions-only; tối đa30calls,6/câu; hậu kiểm trước/sau và REVIEW.

## Acceptance Criteria

- [x] RCA đủ15câu, xác định stage và evidence gap thực tế.
- [x] Fix tổng quát, không Gold answering; nguyên nguồn/artifacts cũ bất biến.
- [x] Có actual answers/citations/graph/tools/latency/usage trên nhóm đại diện.
- [x] Nêu rõ kết quả, residuals, tests thực chạy và next action.
- [x] Owner chấp thuận, implementation đã commit và SHA được xác minh trước DONE.

## Required Tests

1–3targeted controls + compatibility đúng phần sửa, offline source/plan probes;
5live E2E có budget. Ruff/planning/diff, không fullsuite/CI.

## Risks and Blockers

Qwen có thể vẫn sai schema/semantics; raw B09 có dữ liệu nhưng M5 chỉ có canonical
scalar facts. Graph structural không tự cấp semantic support; JSON chưa PDF verified.

## Implementation Evidence

Implementation [`2a683faf02318809f6a40bf7cc9a3511fcb63c17`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/2a683faf02318809f6a40bf7cc9a3511fcb63c17)
đã commit local/xác minh, chưa push; baseline HEADf769a12 + local edits.
[Report](../../../docs/vfb-e2e-04-targeted-fix.md).
RCA15/29anchors có nguồn; sửa Supervisor instruction/graph policy,2aliases,
routing bằng/bảng tiền,JSONscope và scalar/semantic binding guard.5live trước
0C/0P/1I/4N→2C/1P/0I/2N;8calls/41383tokens,5graph found, chưa multi-domain.
28targeted tests/4context probes đạt;2projection/68JSON riêng,25citation pointers,
1488hashes và72E2E03artifacts bất biến. Ruff/planning/diff kiểm tối thiểu.
AMEliability thiếu kỳ, B09/join vàstock/flow policy còn; không Gold answering,
full15/600/OCR/CI. Owner chấp thuận kết quả và cho đóng DONE sau commit.
Phiên đóng:29tests trên isolated staged source PASS, Ruff/planning/diff đạt;
13runtime files commit khớp live receipt. Không API hoặc benchmark mới.

## Handoff Notes

Next action: chờ Owner/Tech Lead giao task tiếp theo; không tự mở benchmark rộng.
