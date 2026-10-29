# Codex Handoff

## Active Task

M3-01 — Canonical and Provenance Contracts

## Status

REVIEW

## Last Verified State

Main/origin khớp `ca2586f356b0cbbbede27fc3f66c46af4675c6f6`; PR #9 MERGED.
Owner cho phép implementation/branch/commit/push/một PR M3-01 ngày29/10/2026.

## Completed Work

Canonical/source models, observation/semantic/source identity và binary operation
compatibility validator; reuse M1/M2. Cross-document 2024 giữ hai observations.
Chi tiết [spec/evidence](tasks/M3/M3-01.md), [API/TBD](../docs/canonical-provenance-contracts.md).

## Remaining Work

Chờ Tech Lead nghiệm thu, chưa DONE; M3-02–07 vẫn TODO.

## Modified Files

src/evidence/{__init__,contracts,compatibility}.py, tests/unit/test_evidence_contracts.py,
docs/canonical-provenance-contracts.md và planning task/status/progress/roadmap/handoff.
`web/next-env.d.ts` có sẵn trước task, giữ ngoài commit.

## Tests

25 targeted PASS local (17 evidence + 8 normalization contracts); Ruff check/format đạt.
Không full suite/build/browser/Gemini/benchmark/PDF processing; không sửa raw/M1/M2 runtime.
Planning checker 93 tasks và diff check PASS. SHA/PR checkpoint tại spec sau bàn giao.

## Blockers

Không blocker implementation. Approval/IDs/bindings do caller cung cấp;
metadata consistency không xác minh financial accuracy. Rules/conversions M4 còn TBD.

## Git Checkpoint

Branch `feat/m3-01-canonical-provenance`; implementation chưa commit.
Không merge; không stage dữ liệu, secrets hoặc next-env local.

## Exact Next Action

Tech Lead review M3-01; không bắt đầu M3-02.
