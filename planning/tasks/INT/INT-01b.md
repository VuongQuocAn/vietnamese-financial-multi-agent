# TASK INT-01b — Evidence-Aware BM25 Retrieval

## Metadata

- Milestone: INT
- Status: REVIEW
- Priority: P1
- Dependencies: INT-01a
- Estimated Complexity: S

## Objective

Tìm nội dung Text/TableEvidence từ approved compositions bằng BM25, giữ
source/snapshot identity, citations và typed context cho QA-01a sau này.

## Context

Owner giao task đầy đủ ngày06/11/2026, cho phép commit/push main và kiểm tra CI
đúng implementation SHA. Baseline main `8324d0e`; INT-01a DONE tại `d531c76`.
GEN-01a BLOCKED; bảo toàn mọi pending runtime/tests/CI/planning và Web local.

## Inputs

Đề bài Owner; ARCH-01 audit; INT-01a report, năm manifest/repository source-bound
151records/17pages, original JSON/PDF đã có. Không gọi Gemini/OCR.

## Outputs

SQLite FTS5 projection, typed public search, Vietnamese normalization,
table/context handling, focused tests, reproducible targeted evaluator.
`artifacts/evidence/INT-01b/`: before/final inventory/probes/actual ranked results,
expected IDs/source checks/metrics/failure analysis/latency/citations/regression.
[Report](../../../docs/int-01b-evidence-aware-bm25-retrieval.md).

## Allowed Changes

Module search nhỏ trong evidence, operation tools mới, tests/evaluator,
CI search entry và task planning/report. Index chỉ từ `load_composition()`.

## Out of Scope

GEN-01a/Web, full extraction/OCR, vector DB/embeddings/reranker, EF-EG/facts,
M5/M6/M7 integration, verified claims, official M8 benchmark.

## Implementation Steps

Approved composition → rebuildable FTS5 body/context → typed search →
real source-derived probes → failure fixes/re-evaluation → regression/CI → REVIEW.

## Acceptance Criteria

- BM25 thật; text/table, accent/case/đ/Unicode/exact phrase, bounded top_k.
- Original IDs/raw text/cells/citations/quality và neighbor boundaries giữ nguyên.
- Không lẫn document/snapshot/composition hoặc dùng legacy/unselected nguồn.
- Public typed tool; exact/page/source APIs cũ giữ semantics; rebuild determinism.
- 20–30 probes thật năm PDF; Recall@1/3/5, MRR, no-answer, tables và latency.
- Retrieval misses/false positives quan trọng được phân tích và sửa, before/after.
- Regression liên quan, CI SUCCESS exact implementation SHA; không Gemini/OCR.
- Không commit private corpus hoặc pending GEN-01a/Web; dừng REVIEW.

## Required Tests

Search/composition/document/exact-M4/financial calculator/M6 Judge/M7 firewall,
30 targeted real probes và selection/rebuild controls. Ruff, planning, diff.

## Risks and Blockers

Lexical threshold/role variants được tune trên development probes, chưa held-out.
Financial cache không full prose; source binding không claim verification.
Section hint lexical; source array order không spatial reading order đã xác minh.

## Implementation Evidence

151units (127text/24tables);30probes,31expected occurrences đối chiếu original JSON.
Recall@1/3/5=85,42%/100%/100%,MRR1,00,no-answer6/6,tablehit11/11,leakage0.
8/8real selection/rebuild controls;14search controls PASS.
Implementation SHA/CI và regression tổng ghi ở checkpoint bàn giao; không gán
CI INT-01a hoặc local tests thành CI INT-01b.

## Handoff Notes

Next action: Tech Lead review INT-01b; không tự DONE hoặc bắt đầu QA-01a.
