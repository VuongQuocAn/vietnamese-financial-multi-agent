# Codex Handoff

## Active Task
M2-04b — Gemini-First Automated Financial Extraction & Numeric Linking

## Status
REVIEW

## Last Verified State
PDF BBS2025 trang5/7/8 → render200DPI → Gemini → validation → mapping → numeric links.
28 accepted đúng/0 sai sau đọc ảnh, không ManualReview runtime;28 Decimal,
0 uncertain,108 unresolved. Baseline40:28 accepted/12 unresolved.
70 targeted PASS; chờ Ruff/planning/diff cuối và CI exact implementation SHA.

## Completed Work
Automated schema/API, Decimal parser, Gateway/rendering reuse, giữ manual path.
Pilot B01/B02/B03:14 mapped đúng/0 sai,accepted10/10/8 đúng; PDF hash giữ nguyên,
image hashes khớp SDK. 5 calls gồm2 recovery row-count B01/B02,0 transport retry;
không gọi lại B03 cache tốt. [API/evidence](../docs/automated-financial-extraction.md),
[spec](tasks/M2/M2-04b.md), [issue](tasks/M2/issues/M2-04-numeric-linking.md).

## Remaining Work
Commit/push implementation, xác minh CI Python3.11/3.12 đúng SHA và ghi evidence;
chờ Tech Lead review. Không tự DONE hoặc bắt đầu M2-05.

## Modified Files
src/accounting/automated_extraction.py, __init__.py; scripts/run_gemini_ingestion.py;
tests/unit/test_automated_extraction.py; docs/automated-financial-extraction.md;
planning/tasks.md, progress.md, current-status.md, handoff.md, tasks/M2/M2-04b.md,
tasks/M2/issues/M2-04-numeric-linking.md.

## Tests
70 targeted PASS:36 automated,14 manual recovery,12 item mapping,8 Gemini ingestion.
Không full local suite; mock Gemini trong tests. Pilot thật không phải benchmark.

## Blockers
Không có blocker pilot. Chỉ ba trang mục tiêu, catalog14 items, không verified facts,
không đánh giá accuracy toàn PDF. 108 unresolved ngoài phạm vi catalog/ô thiếu.

## Git Checkpoint
Baseline ổn định `8a3b5ce`; implementation local đã targeted PASS, chờ commit/push
và xác minh CI đúng implementation SHA. Không gán CI task trước cho thay đổi mới.

## Exact Next Action
Xác minh CI đúng implementation SHA sau push.
