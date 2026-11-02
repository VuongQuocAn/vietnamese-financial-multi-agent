# Codex Handoff

## Active Task

M4-05 — Question Answering Baseline

## Status

REVIEW

## Last Verified State

Baseline main/origin `eca8cc84c626556e7f1fa5e6faab92797e3e06d8` đã xác minh.
[Spec](tasks/M4/M4-05.md), [report](../docs/m4-05-qa-baseline.md).
Chưa commit; final real-data evaluation/replay/regressions PASS.

## Completed Work

Public QA API/contracts, deterministic rules/dispatcher/composer, optional một
Gateway call với schema/allowlists, CLI và benchmark 36 câu có references độc lập.

## Remaining Work

Commit/push/CI đúng SHA và Tech Lead independent review; không tự DONE/M5.

## Modified Files

src/tools, tests/unit/test_financial_qa.py, hai scripts, evaluation question config,
focused CI list và docs/planning. Giữ web/next-env.d.ts ngoài stage và byte-for-byte.

## Tests

193 targeted PASS; sau chỉnh rendering/cache, 25 QA PASS. Ruff372/planning100/diff
PASS. Final benchmark36:28 answered đúng/grounded,6 abstained/unsupported,2 clarification;
intent/tools36/36.18 metrics/29 queries/36 pairs/D-06/D-07 và2.670 hashes giữ nguyên.
Final outputs riêng artifacts/evidence/M4-05-final; zero Gateway/Gemini/OCR/extraction.

## Blockers

Chưa live Gemini do không có process credentials/live config; financial_fact_verified=False.
Nguồn vẫn page-level; D03-B10 chặn cross-document. Không bắt đầu M5.

## Git Checkpoint

Chưa commit. Web SHA256 trước task, đã kiểm giữ nguyên:
`0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`.
Không stage artifacts/dataset/secrets, không branch/PR/worktree/force-push.

## Exact Next Action

Tech Lead independent review M4-05.
