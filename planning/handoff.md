# Codex Handoff

## Active Task
M2-08 — M1/M2 End-to-End Audit, Simplification & Answerability Optimization

## Status
IN_PROGRESS

## Last Verified State
M2-08 IN_PROGRESS — implementation/audit/pilot hoàn tất local, đang chờ CI.
Runtime primary: PDF → Gemini structured/cache bound → raw evidence → task-aware query.
26 structured queries: 23/26 → 25/26 answered (88,46% → 96,15%); correct 23→25,
incorrect/unsupported 0; partial 1→0; abstained 2→1; grounding 23/23→25/25.
Gain từ targeted recovery mã300 trang6, không từ nới quality gate trên ba trang cũ.
136→138 slots,121→123 numeric usable,28 canonical,93→95 ngoài catalog;
28 accepted extraction không đổi. Một Gemini call/2.037 tokens; không đo monetary cost/live latency.
17 focused +134 regression =151 targeted PASS; Ruff local PASS.
PDF/cache/reference hash trước/sau khớp; không commit artifacts/dataset/secrets.
Giới hạn: một PDF, intent khai báo trước; không là free-form chatbot accuracy.
[Audit/API/benchmark](../docs/m1-m2-end-to-end-audit.md), [spec](tasks/M2/M2-08.md).


## Completed Work
Audit code paths/checks, đối chiếu PDF 5/6/7/8, query/recovery/runtime composition, benchmark trước/sau và source immutability. Không xóa M1 hoặc thay policy M2-07.

## Remaining Work
Commit/push implementation, CI đúng SHA; sau PASS chuyển REVIEW chờ Tech Lead.

## Modified Files
src/accounting/{automated_extraction,financial_runtime}.py; src/tools/financial_query.py; scripts/{run_gemini_ingestion,run_financial_query_probe}.py; tests/unit/test_financial_query.py; docs/{architecture,m1-m2-end-to-end-audit}.md; planning/{tasks,progress,roadmap,current-status,handoff}.md; planning/tasks/M2/M2-08.md.

## Tests
17 focused +134 regression =151 targeted PASS; Ruff lint/format PASS. Planning/diff kiểm tra trước commit. Benchmark final 25 correct/0 incorrect/0 unsupported; còn 1 dấu gạch abstained.

## Blockers
Không blocker local; CI chưa chạy cho implementation mới.

## Git Checkpoint
Baseline sạch local/origin `2c9c63dbcfd8fd86cf5eb0b81090fc49f8bf5469`. Implementation đang uncommitted, đã qua targeted checks. Artifact benchmark-label-regression SHA256 `ef9c33e30816ef2f2bb4586f2a46f745892c1f7bba46f3adde2e732575ce598d`.

## Exact Next Action
Commit/push implementation M2-08 và xác minh CI đúng SHA.
