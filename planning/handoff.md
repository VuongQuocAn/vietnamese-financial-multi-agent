# Codex Handoff

## Active Task

M1-11a — Bounded Real Classification Pilot

## Status

IN_PROGRESS

## Last Verified State

Baseline HEAD/origin `e5ae508c69bbbe7e2543e8c9b5973cbaa5fa51b5`, M1-11 DONE.
Dry-run verified 19 pages/3 symbols/14 strata. Live 6 actual API requests (smoke +5 pages),
12307 input/176 output/12483 total tokens, nguồn không đổi. Live subset 1 symbol/5 years.

## Completed Work

Runner/CLI bounded dry-run và sequential Gateway/Gemini/guard/cache/checkpoint integration.
Smoke đạt; 0 resolved/5 unresolved real pages (4 OCR quality/1 insufficient), 8 anchors checked.
Cache HIT 5 probes không API thêm; checkpoint HIT live 0, synthetic có resolved resume.
Dừng local pre-send token reservation, 1 budget denial, không actual provider/schema errors.
Fix metrics runner và regression test; original live report giữ nguyên + private interpretation,
không rerun live. User xác nhận export/free/quota/no other apps; duy nhất key index 0.

## Remaining Work

Commit/push, exact-SHA CI 3.11/3.12, chuyển REVIEW; Tech Lead nghiệm thu độc lập.
Không bắt đầu M1-12.

## Modified Files

src/document_processing/classification_pilot.py; scripts/run_classification_pilot.py;
tests/unit/test_classification_pilot.py; docs/classification-pilot.md;
docs/reviews/M1-11a-evidence.md; planning/{tasks,progress,current-status,handoff,decisions}.md;
planning/tasks/M1/M1-11a.md. Runtime artifacts ignored, không stage keys/dataset.

## Tests

17 focused +146 related regression passed; final Ruff/planning/diff trước publication.
Full unit suite chỉ CI, không rerun API.

## Blockers

Pilot chỉ 5 real pages thay vì mục tiêu 10–20 do token upper-bound cap; không nới budget.
Project aliases/quota/tier user-attested; actual project ID/quota remaining/billing
không independently verified. USD 0 estimated conditional free tariff; guard money
NOT_CONFIGURED. Taxonomy provisional, gate bảo thủ; không ground truth/accuracy.
OCR run identity gốc chưa verified; dùng exact verified artifact locators page-only.
Live checkpoint HIT chưa chứng minh (0 resolved); synthetic có HIT, không giả live results.

## Git Checkpoint

Baseline `e5ae508c69bbbe7e2543e8c9b5973cbaa5fa51b5`; implementation chưa commit.
Live trước metrics-only fix; không claim rerun live trên corrected runner/CI SHA.

## Exact Next Action

Commit/push M1-11a và xác minh exact-SHA CI trước REVIEW.