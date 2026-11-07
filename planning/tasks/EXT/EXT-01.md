# TASK EXT-01 — Full-Document Evidence Coverage & Extraction Completion

## Metadata

- Milestone: EXT
- Status: REVIEW
- Priority: P1
- Dependencies: QA-01a, INT-01a, INT-01b
- Estimated Complexity: L

## Objective

Hoàn thiện source-bound document evidence trên năm PDF; đo coverage và QA riêng biệt.

## Context

Owner giao EXT-01 ngày 07/11/2026, baseline main `7187075`.
GEN-01a tạm dừng, giữ nguyên pending code/artifacts và Web.

## Inputs

BBS 2025 (24 trang), BCC 2025 (30), BCC 2024 (41); BBS 2022/2024
chỉ bổ sung prose gaps đã xác định. Existing caches, INT-01a compositions,
QA-01a. Yêu cầu đầy đủ giữ local `artifacts/evidence/EXT-01/task-request.md`.

## Outputs

Page inventory, saved responses, UnifiedPage, repository, composition mới,
BM25, 12–20 QA cases, usage và báo cáo
`docs/ext-01-full-document-evidence-coverage.md`. Artifacts local tại
`artifacts/evidence/EXT-01/`, không commit dữ liệu tài chính gốc.

## Allowed Changes

Planner/resume script; ingestion prose/layout; adapter/materialization/retrieval
integration; targeted tests và planning. Owner yêu cầu commit/push main và CI đúng SHA.

## Out of Scope

Không sửa financial facts, EF-EG, accepted artifacts, GEN-01a/Web;
không M8/EF-01/QA-01b, agent mới hoặc RAG mới.
Tech Lead cho phép ngoại lệ closure ngắn: negative QA trên OCR sai trang 13,
source-quality gate M6 nếu cần và xác minh Q29 trên baseline trước EXT-01.

## Implementation Steps

Inventory/cache → targeted Gemini từng trang → PDF review → existing
materialization/composition → BM25/QA before-after → regression → commit/push/CI.

## Acceptance Criteria

- [x] Inventory năm PDF, phân biệt Discovery/extraction/full prose.
- [x] Audit BBS 2025 trang 4 và signer 7–8 có nguồn/layout review.
- [x] B09 gaps trong phạm vi được xử lý; giữ exact pointers/citations và OCR caveats.
- [x] Composition giữ accepted evidence; BM25 scope đúng.
- [x] Có 18 real QA cases, negative controls, financial regression và CI đúng SHA; extended Q29 limitation được ghi riêng.
- [x] Báo usage/coverage trung thực; dừng REVIEW, không còn missing page bắt buộc.
- [x] Closure P1: đoạn OCR sai BBS 2025 trang 13 không được M6 ACCEPT hoặc M7 xuất citation; proof cũ bị chặn admission/replay.
- [x] Closure P2: tái hiện Q29 bằng code baseline `7187075`, chỉ lệch fixture ở `semantic_role` như EXT-01.

## Required Tests

Focused ingestion/planner; INT-01a/INT-01b/QA-01a và financial compatibility;
real PDF samples, 12 negative controls, planning checker và diff check.

## Risks and Blockers

Quota/provider, OCR fidelity, bbox chưa xác minh; opinion/signature semantic policy
có thể giữ INVESTIGATE dù retrieval có evidence. Không coi OCR là verified claim.

## Implementation Evidence

Implementation `34209fc02c065557cb9b1596c511f4d4feb22471` đã push main; baseline `7187075`.
[CI42343884351](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42343884351)
completed/SUCCESS đúng SHA: 1.115 Python/9Web PASS; lint/format/planning,
frontend typecheck/build đạt; full regression manual SKIPPED.
99 unique pages retrievable, gồm 95/95 trang của ba PDF ưu tiên và bốn trang lịch sử;
89 trang mới/18 cache pages, 107 attempts/648.845 known tokens/7 HTTP503.
1.787 approved records (1.629 text/158 tables), giữ nguyên 151 records cũ.
18 QA: retrieval 4/16→16/16 positive; M6 ACCEPT 3→12 claims; M7 citations 3→10 câu.
20 source/reload/scope controls PASS; 62 targeted trước tối ưu resume và 25 targeted
sau tối ưu PASS. QA-01a10/10, INT-01b30probes/8controls giữ kết quả.
36 financial QA/restart và18 metric assertions đạt; extended runner dừng Q29 do
gold `semantic_role=null` cũ so với GEN-01 `revenue`, không sửa ngoài scope.
[Report](../../../docs/ext-01-full-document-evidence-coverage.md).
Giữ các OCR/geometry caveats, semantic opinion/layout policy và quoted-query
parser limitations; không tuyên bố full financial/OCR accuracy.

## Handoff Notes

Closure chưa commit: source-quality gate theo cờ `pdf_review:*`, không sửa OCR;
review hiện gắn cờ theo trang nên gate chặn toàn bộ records có cờ trên trang đó.
Negative thực tế trước sửa ACCEPT 1/citation 1; sau sửa INVESTIGATE `source_quality`,
ACCEPT 0/citation 0; admission/replay proof cũ đều rejected. Q29 baseline
`718707503a55fccc023d465645506954ea0df26b` giống hệt kết quả EXT-01, chỉ lệch
fixture `semantic_role=null` so với `revenue`; giữ nguyên fixture lịch sử.
Traces local: `artifacts/evidence/EXT-01/closure/`.
Local closure 91 tests PASS (document QA/ledger/firewall); Ruff lint/format,
planning và diff check PASS. CI closure chờ implementation commit.
Next action: Tech Lead nghiệm thu hai điểm closure để quyết định DONE.
