# Codex Handoff

## Active Task

M5-01 — Evidence Plan and Planner Contracts

## Status

REVIEW

## Last Verified State

Baseline main/origin `ca9570d61f9fc0dd45d78956f27590631e601120` đúng brief.
M4-05/M4-05a DONE; [spec](tasks/M5/M5-01.md),
[report](../docs/m5-01-evidence-plan-contracts.md). Chưa commit.

## Completed Work

Public Pydantic contracts, M4 request/response registry, deferred bindings,
structural/combined DAG validation và catalog-backed read-only preflight.
Không agent runtime, Gemini, formula execution hoặc M4 production changes.

## Remaining Work

Commit/push main và xác minh CI đúng implementation SHA, ghi checkpoint;
chờ Tech Lead independent review.

## Modified Files

src/agents, focused tests/evaluator/CI list, report và planning.
Giữ web/next-env.d.ts local ngoài stage; không stage artifacts/dataset/secrets.

## Tests

35 M5 controls; tổng131 targeted PASS với M4 retrieval/calculator/evidence/Gateway.
Final run:15 real cases,10valid/4blocked/1invalid;2.681 hashes unchanged,
JSON round-trip/records exact. Ruff382/planning101/diff PASS;
không full local regression hoặc Gemini/OCR/calculation calls.

## Blockers

D03-B10 giữ BLOCKED;2024 separate, filings khác unresolved. Scope caveats,
page-level provenance và financial_fact_verified=False giữ nguyên.

## Git Checkpoint

main; chưa commit implementation. Owner đã cho phép commit/push trực tiếp main,
không branch/PR/worktree. Chỉ stage files M5-01; web local giữ byte-for-byte.

## Exact Next Action

Tech Lead independent review M5-01; không bắt đầu M5-02.
