# TASK E2E-REMED-01 — Source & Scope Readiness

## Metadata

- Milestone: E2E
- Status: REVIEW
- Priority: P1
- Dependencies: E2E-ARCH-02
- Estimated Complexity: S

## Objective

Sửa binding scope/composition và đường truy xuất nguồn JSON, dùng RCA/saved traces
E2E-VAL-01. Không thay M6/M7 hoặc suy dữ liệu thiếu.

## Context

Owner giao sau Pilot gate9/45; giữ E2E-VAL-01 REVIEW, không tự nghiệm thu.
Baseline remote main f4d598e; worktree riêng giữ80local files của checkout gốc.

## Inputs

Manifests/imported EF-EG, JSON nguyên trạng và saved Pilot traces. Không mở Full600.
Scope chỉ từ source title hoặc checkbox được đánh dấu rõ, đúng snapshot/hash.

## Outputs

JSON scope/source binding có provenance; truy xuất text/table qua tools hiện có,
diagnostics phân biệt import/mapping/eligibility với raw absence; report/traces.

## Allowed Changes

Evidence/loader/composition, source retrieval và M5 context tích hợp cần thiết;
targeted tests, retest runner, tracking/report của task.

## Out of Scope

M6/M7, Evidence Obligations/ACCEPT policy, kiến trúc/Agent mới, đổi raw JSON/EF-EG,
hardcode Gold/QA/doanh nghiệp, OCR/Gemini/PDF, fullCI,36Pilot còn lại/Full600.

## Implementation Steps

1. Đối chiếu saved traces và source bindings, giữ negative/missing/conflict.
2. Bổ sung binding/truy xuất JSON trên contracts và tools hiện có.
3. Targeted controls rồi tối đa4QA duy nhất bị ảnh hưởng; không tuning planning.
   Nếu lộ lỗi binding mới, giữ trace trung gian và kiểm riêng câu đó sau sửa.
4. Báo trước/sau và limits, commit/push main, bàn giao REVIEW.

## Acceptance Criteria

- [x] Scope có source hợp lệ không bị chặn vì bỏ sót checkbox/title; thiếu/conflict vẫn chặn.
- [x] JSON text/table tới tools/Agent với exact identity/pointer/hash/caveats, không promote thành verified fact.
- [x] Composition JSON giữ semantics khác PDF, không giả approval/image hoặc thay M6/M7.
- [x] Có targeted tests và tối đa4QA duy nhất retest/traces, SHA và REVIEW.

## Required Tests

1–3controls chính scope positive/negative, composition/source fidelity và retrieval;
compatibility tests liên quan, một smoke real JSON. Retest tối đa4QA,40actual calls,
10/câu, timeout300s/câu, không transport retry; không API judge/fullCI.

## Risks and Blockers

Document M6 hiện kiểm pdf_page; JSON binding không tự cấp document ACCEPT.
Ragged table import có thể bỏ cả các hàng đúng; thiếu unit/mapping vẫn không có
numeric authority. Giữ chẩn đoán riêng, không sửa M6 hoặc raw để cứu Gold.

## Implementation Evidence

Implementation `02093495863bec10424659bcad7175e69edad457`;
[report](../../../docs/e2e-remed-01-source-scope-readiness.md).4QA duy nhất/5attempts,
18calls/102082tokens/0unknown; accuracy/coverage0/4→0/4, không đồng nghĩa source gate chưa sửa.
MH0006 qua scope→planner invalid envelope; MH0001 qua composition/scope→sai handles/query;
SH0006 nhận bảng khấu hao D context nhưng thiếu coverage/malformed specialist;
NR0001 còn query mơ hồ và canonical import exclusion. Không rebuild canonical/EF-EG.
3new controls PASS; compatibility61PASS và71PASS/2legacy FAIL y hệt baseline.
186runtime blobs khớp commit;143raw JSON/28imported files/3Pilot hashes/80local
files và52parent evidence files bất biến; M6/M7 không đổi. Không36Pilot/Full600.
Traces/Gold/output/before-after local artifacts/evidence/E2E-REMED-01, không commit dataset.
Chờ Tech Lead nghiệm thu phạm vi binding/retrieval và giới hạn còn lại, không tự DONE.

## Handoff Notes

Next action: Tech Lead review binding/source fixes và các lỗi Planning/query/source handles/canonical eligibility còn lại trước khi cho phép tiếp tục Pilot45.
