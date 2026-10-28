# Codex Handoff

## Active Task
M2-09 — Full-PDF Real-World Evaluation & Targeted Hardening

## Status
IN_PROGRESS

## Last Verified State
M2-08 DONE; M2-09 được user giao và cho phép live Gateway/commit/push/CI.
PDF BBS2025 24 trang, SHA256 6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1.
Discovery đúng 24/24; B01 5–6, B02 7, B03 8, B09 9–24. Full runtime không truyền pages.
Numeric precision/recall/kỳ/unit/grounding/usability đều 163/163; 7 dash sai glyph giữ
missing. Notes sample 6/6 riêng. Queries M2-08 giữ 25/26 answered đúng/grounded.

## Completed Work
Discovery/schema, optional pages trong runtime cũ, multi-page/uncertain/notes inventory,
evaluation CLI, source-image reference/corrections và re-evaluation. 25 calls mới,
37.382 tokens; recovery 0 vì không có lỗi numeric trọng yếu cần phục hồi.
Source/cache lịch sử hash khớp; report CONDITIONAL GO. 140 targeted PASS.

## Remaining Work
Checks cuối, commit/push implementation và xác minh CI full unit 3.11/3.12 đúng SHA;
sau đó chuyển REVIEW chờ Tech Lead, không tự DONE/demo/M3.

## Modified Files
src/document_processing/financial_discovery.py; src/accounting/financial_runtime.py;
scripts/evaluate_full_pdf.py; tests/unit/test_financial_discovery.py;
tests/unit/test_full_pdf_evaluation.py; docs/m2-09-full-pdf-evaluation.md;
planning/tasks/M2/M2-09.md; registry/dashboard/current-status/handoff/roadmap.
Artifacts private ignored: artifacts/evaluation/M2-09/.

## Tests
32 focused mới/query +108 extraction/quality/relationship/context =140 targeted PASS.
Ruff/planning/diff và CI exact SHA đang hoàn tất; không chạy full local suite.

## Blockers
Chưa có blocker runtime trong bốn bảng chính. Giới hạn: một PDF, chủ yếu replay,
reference do cùng agent đối chiếu chưa reviewer người thứ hai; 7 dash glyph sai;
notes chỉ inventory/M1 sample, chưa notes QA. Chưa có CI cho M2-09 trước push.

## Git Checkpoint
Baseline thực tế d0a82ea trên main sạch/trùng origin/main; không dùng SHA baseline
cũ trong handoff M2-08. Chưa commit implementation; working tree đang có thay đổi
M2-09. Source data/credentials/cache nguyên trạng, không stage raw/normalized/secrets.

## Exact Next Action
Hoàn tất checks, commit/push và xác minh CI đúng implementation SHA.
