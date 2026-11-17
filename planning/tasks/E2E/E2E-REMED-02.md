# TASK E2E-REMED-02 — Planning & Evidence Routing

## Metadata

- Milestone: E2E
- Status: DONE
- Priority: P1
- Dependencies: E2E-ARCH-02
- Estimated Complexity: S

## Objective

Giữ mục tiêu câu hỏi và goal ownership; sửa kỹ thuật schema/handles, truyền
dependency evidence/source context đúng bản sắc, không cắt nguồn để né cap.

## Context

Owner giao sau E2E-VAL-01/REMED-01; giữ hai task REVIEW, không tự nghiệm thu.
Baseline remote9fec038; worktree riêng giữ80local files của checkout gốc.

## Inputs

RCA và saved traces hai task trước, pinned JSON/EF-EG, bốn câu hỏi Pilot đã freeze.
Không mở Full600 hoặc truyền Gold vào answering. Qwen qua Gateway, key local ignored.

## Outputs

Schema/plan owner và original-question fallback có raw trace; bounded demand
batches đầy đủ, exact dependency refs/digests/context; report/traces before-after.

## Allowed Changes

Coordinator/M5/fusion planning/routing, runner/tests/contracts/tracking liên quan.
Sửa tối thiểu, không nhiều vòng tuning prompt; freeze trước live retest.

## Out of Scope

M6/M7/Evidence Obligations/ACCEPT, raw/canonical JSON/EF-EG, thêm Agent/kiến trúc,
Gold/QA/doanh nghiệp hardcode, OCR/Gemini/fullCI,36Pilot/Full600.

## Implementation Steps

1. RCA saved planning over-cap/goal drift, S/T/E confusion và missing dependencies.
2. Root schema/ownership, exact item binding, all-input batches và source context closure.
3.3targeted controls/compatibility; freeze rồi một lượt4QA thực tế, không prompt tuning tiếp.
4. Báo before/after/calls/limits, commit/push main, bàn giao REVIEW.

## Acceptance Criteria

- [x] Backend giữ nguyên câu hỏi/goal owners khi raw plan sai, có raw failure/fallback trace.
- [x] S/task/result/E/D tách namespace; dependency có digest/context, source-only không thành claim.
- [x]12demands chia6+6 trong control, không cắt nguồn hoặc tăng ACCEPT authority; chưa positive live12.
- [x]3new controls/25compatibility PASS,4QA/4attempts live với RCA/traces, commit/push REVIEW.

Giới hạn nghiệm thu: raw model vẫn sai namespace/owner;3câu dùng fallback toàn
câu hỏi nên chưa chứng minh phân rã/role assignment tốt. Accuracy/coverage vẫn0/4;
chưa đáp ứng readiness Pilot. Owner/Tech Lead xác nhận **DONE có giới hạn**
ngày17/11/2026 trong phạm vi planning/routing và bằng chứng đã báo.

## Required Tests

3controls chính planning/owned fallback, batches+handles, dependency source-only
đến consumer; targeted compatibility liên quan.40actual calls task,10/câu,
300s/câu/60sprovider, retries0; chỉ4QA duy nhất/4attempts, không judge API.
Ruff/planning/diff, không fullCI hoặc full regression.

## Risks and Blockers

Fallback một goal giữ toàn câu hỏi không chứng nhận semantic completeness.
Source-only D context không numeric authority; thiếu canonical hoặc M6 verification
vẫn abstain và dừng. M6 document PDF-specific vẫn nguyên, không sửa để cứu QA.

## Implementation Evidence

Implementation `78a5e67202429cdd76556f883597abed35c939e4`;
[report](../../../docs/e2e-remed-02-planning-evidence-routing.md).4QA/4attempts,
17calls/95473known tokens/1unknown timeout,0/4→0/4/0citations, không prompt tuning sau freeze.
SH0006/MH0013 source_only, MH0006 thiếu M6 goal support; MH0001 DAG T1→T2 và fusion
parent context hoạt động nhưng target130 thay131 thiếu canonical, M6 timeout.
3new controls và25targeted compatibility PASS, fusion recheck PASS; Ruff/planning/diff.
186runtime blobs/146raw JSON/28imported files/3Pilot hashes verified;80local files
và evidence hai task trước bất biến, M6/M7/evidence không đổi.5result digests,
4owned Coordinator goals và14source-cell pointer occurrences khớp. Không36Pilot/Full600.
Evidence local artifacts/evidence/E2E-REMED-02; raw model errors/fallbacks giữ riêng.
Owner/Tech Lead nghiệm thu DONE có giới hạn; bàn giao f8d2b6a đã push main và
remote verified. Giữ nguyên mọi số liệu/limits. Phiên đóng chỉ tài liệu/tracking
và planning/diff/Git; không sửa runtime, chạy lại tests/API/benchmark/fullCI.

## Handoff Notes

Next action: chờ Owner/Tech Lead giao nhiệm vụ tiếp theo.
