# TASK EF-CORE-02 — Controlled EF-EG Ablation & Quality Evaluation

## Metadata

- Milestone: EF
- Status: DONE
- Priority: P1
- Dependencies: EF-CORE-01
- Estimated Complexity: M

## Objective

Đánh giá contribution retrieval/analysis/grounding và overhead của EF-EG bằng
paired Graph OFF/ON trên BBS thật; kết quả âm tính được chấp nhận.

## Context

Owner giao ngày 11/11/2026 qua task đính kèm. Baseline runtime
`f5bbac6b6d5befd0b3021654b48218feeab54942`, giữ local edits ngoài task.

## Inputs

BBS 2025 PDF, canonical facts, EF-01 approved composition, Gateway Gemini hiện có.
Task đầy đủ lưu riêng trong artifacts/evidence/EF-CORE-02 (ignored).

## Outputs

Runner resumable, source oracle, 15 câu hỏi/sáu nhóm, hai OFF và hai ON/câu;
raw answers/traces/assessments ignored. Báo cáo:
`docs/ef-core-02-graph-ablation-quality-evaluation.md`.

## Allowed Changes

Evaluation runner, targeted tests, báo cáo và planning liên quan. Chỉ sửa runtime
khi xác định rõ P1 lặp lại và có regression test, theo điều kiện Owner giao.

## Out of Scope

Không OCR/extraction, rebuild graph, edge/agent/database mới, M8, model khác,
refactor M5/M6/M7 hoặc sửa local edits ngoài phạm vi.

## Implementation Steps

Preparation/oracle → pilot bốn câu → main paired repeated runs → independent
assessment/diagnosis G3/G5/M6 → report/targeted validation → commit/push/CI → REVIEW.
Cùng plan sinh thật/câu, ledger riêng/lượt, tách planning costs; resume không lặp
lượt đã lưu, provider failures không tính lỗi chất lượng.

## Acceptance Criteria

- [x] Oracle source/PDF/calculator và relations có thật, đủ provenance.
- [x] Repeated controlled OFF/ON và chấm độc lập M6.
- [x] Correctness/completeness/grounding/citations/graph contribution/efficiency.
- [x] Chẩn đoán G3/G5 và semantic grounding; limitations và M8 hypothesis.
- [x] Tests/checks, commit/push main, CI SUCCESS đúng SHA; dừng REVIEW.

## Required Tests

1–3 targeted evaluator tests, offline integration, live pilot và 60 execution;
Ruff/planning/diff checks, CI đúng SHA. Không full regression/M8.

## Risks and Blockers

Quota/provider 429/503 có thể làm thiếu lượt; lưu từng lượt và không retry vô hạn.
Graph use/ACCEPT không đồng nghĩa added value; không dùng ON answer làm oracle.

## Implementation Evidence

Implementation [43c55aa3ac7b3f9cb6dc9c6b35fcbb6a61d117e1](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/43c55aa3ac7b3f9cb6dc9c6b35fcbb6a61d117e1) đã push main;
[CI42976641605](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42976641605) SUCCESS đúng SHA,213 Python tests PASS;
Web/full regression SKIPPED. Tech Lead nghiệm thu DONE trong task EF-CORE-03; giữ limitations. 60 primary +20 bounded
replacements/Gemini thật,80 assessments;52 clean slots/23 clean pairs. Không có
hai clean repetitions cho mọi câu; giữ rõ attrition và mọi failure/cost.
ON14/23 vs OFF11/23 CWC, completeness84/111 vs82/111; không có financial facts mới.
Tokens mean +60,22%, latency mean +61,23%; graph setup/traversal chiếm phần lớn.
230 Gateway calls/679767 known tokens/18 logical usage unknown; comparison218
provider attempts. 198 fact/62 metric/89 citation occurrences audit0 mismatch.
169 baseline Python files/10670 protected/19 unrelated pre-existing files unchanged.
3 evaluator tests/staged Ruff check/format/planning/diff PASS; CI213 PASS.
[Report](../../../docs/ef-core-02-graph-ablation-quality-evaluation.md);
raw traces/oracle/assessments/question appendix ignored. Không sửa runtime/M8.

## Handoff Notes

Next action: theo dõi remediation trong EF-CORE-03.
