# TASK GEN-02-Fix-A — QA Coverage & False Abstention Recovery

## Metadata

- Milestone: GEN
- Status: DONE
- Priority: P1
- Dependencies: GEN-01, QA-01b, EF-01, EXT-01
- Estimated Complexity: S

## Objective

Sửa H03/H06/H07/H11/H12 theo Owner giao 09/11/2026; baseline `6f682c3`.
GEN-02 vẫn REVIEW; findings là development regression, không còn blind evaluation.

## Context

[GEN-02 report](../../../docs/gen-02-cross-company-generalization.md). GEN-02 REVIEW
là nguồn findings, không yêu cầu nghiệm thu GEN-02 trước khi sửa. Dependencies kỹ thuật
đã DONE. Yêu cầu đầy đủ lưu local `artifacts/evidence/GEN-02-Fix-A/task-request.md`.

## Inputs

Persisted accepted BBS/BCC evidence, frozen GEN-02 questions/oracles (read-only),
traces năm cases và QA-01b C1. Giữ GEN-01a/Web pending.

## Outputs

[Report](../../../docs/gen-02-fix-a-qa-coverage.md); local artifacts
`artifacts/evidence/GEN-02-Fix-A/`: RCA, targeted before/after, traces, 6 fresh checks.

## Allowed Changes

Bounded metric preparation, M5 topic/excerpt/requirement selection, M7 coverage;
focused tests và planning/report. Commit/push main và đối chiếu CI đúng SHA.

## Out of Scope

H08/Fix-B, OCR, source/ledger mutation, Gemini live, M8, Web, PERF-01.

## Implementation Steps

Targeted audit → tối đa hai vòng sửa/test → khóa runtime → final targeted +6 fresh
một lần → report/commit/push/CI → REVIEW. Không chạy lại 40 câu GEN-02.

## Acceptance Criteria

- [x] H03 không internal error; verified metric hoặc explicit capability gap.
- [x] H06/H07 selection grounded; H11 giữ requirements; H12/C1 useful partial.
- [x] Không unsupported/citation/snapshot leakage; giữ quality/accounting/M6 gates.
- [x] Focused actual pipeline và6 fresh expected trước execution; CI đúng SHA.

## Required Tests

Focused changed modules, source-quality/accounting/snapshot controls, QA-01b C1;
Ruff/planning/diff. Không Gemini/OCR hoặc full40 regression.

## Risks and Blockers

Các P1 Fix-A đã đạt targeted behavior. H08/Fix-B ngoài scope; còn giới hạn12selectors
cùng trang và exact-phrase predicates. CI đúng implementation đã SUCCESS; Tech Lead APPROVED ngày09/11/2026.

## Implementation Evidence

Implementation `22b8c7c5b1c0a6756c0be2595874f8086ce47d30` đã push main,16 files.
[CI42542900770](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42542900770)
completed/SUCCESS;1157 Python/9 Web PASS, full regression manual SKIPPED. Final local122focused +8planning PASS;
vòng1 có25existing tests (overlap). H03/H06/H07/H11 full; H12/C1 useful partial,
giữ accounting gate.6fresh/6full,0incorrect/unsupported. Citations37/37focused,
51/51fresh; A7 ACCEPT1/INVESTIGATE1;17legacy claims replay nguyên file.
Không Gateway/Gemini/OCR;38inputs/4frozen GEN-02 files và runtime sau lock nguyên hash.
RCA/traces/summary local trong artifacts; [report](../../../docs/gen-02-fix-a-qa-coverage.md).

## Handoff Notes

Tech Lead APPROVED ngày09/11/2026; GEN-02-Fix-A DONE. Phiên closure chỉ cập nhật planning, chạy planning/diff checks;
không chạy lại CI/QA hoặc sửa runtime.
Next action: chờ Owner/Tech Lead giao nhiệm vụ tiếp theo; không tự bắt đầu Fix-B hoặc task khác.
