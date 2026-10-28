# Codex Handoff

## Active Task
M2-01 — Financial Normalization Contracts

## Status
REVIEW

## Last Verified State
M1-16 DONE. Baseline sạch `8c351bee80b81f609074c94c502299ff94b83315` sau fetch/fast-forward
hai README-only commits. Contracts chạy được; 8 focused tests PASS.
CI exact implementation SHA sẽ được kiểm tra sau commit/push.

## Completed Work
FinancialValue/Context/SourceReference/NormalizationResult; strict models và version,
Decimal JSON strings, SourceAnchor M1 giữ nguyên, quality checks riêng, schema/export,
focused tests synthetic và [API/evidence](../docs/financial-normalization-contract.md).
Registry dependency M2-01 đổi M1-14 → M1-16; spec IN_PROGRESS trước implementation.

## Remaining Work
Xác minh CI exact SHA sau publication; Tech Lead review trước DONE.

## Modified Files
src/accounting/{__init__,contracts,validation}.py;
tests/unit/test_financial_normalization_contracts.py;
scripts/export_financial_normalization_schema.py;
schemas/financial_normalization_v1.schema.json;
docs/financial-normalization-contract.md, docs/data-contracts.md;
planning/tasks.md, progress.md, current-status.md, handoff.md, tasks/M2/M2-01.md.

## Tests
8 focused tests PASS; Ruff lint/format 5 Python files, planning checker 82 tasks và diff check PASS.
Không full local regression, benchmark, dataset evaluation hoặc API.

## Blockers
Không blocker implementation. Metadata/vocabulary kỳ/đơn vị/scale còn mở cho M2-02;
provenance caller cung cấp chưa được đối chiếu nguồn. Page-level không thành cell-level.
Không financial accuracy hoặc verified fact, kể cả khi không còn quality issues.

## Git Checkpoint
Stable baseline `8c351bee80b81f609074c94c502299ff94b83315`.
Implementation SHA xác định bằng `git log -1 --format=%H -- src/accounting/contracts.py`.
Chưa có CI trên implementation tại thời điểm chuẩn bị commit; không suy CI baseline cho code mới.

## Exact Next Action
Chờ Tech Lead review.
