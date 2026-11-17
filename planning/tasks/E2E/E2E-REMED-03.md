# TASK E2E-REMED-03 — Canonical Mapping & Evidence Eligibility

## Metadata

- Milestone: E2E
- Status: DONE
- Priority: P1
- Dependencies: E2E-REMED-02
- Estimated Complexity: S

## Objective

Khôi phục facts có giá trị/kỳ/đơn vị/provenance từ JSON bằng sửa importer/catalog;
không thay kiến trúc hoặc nới M6/M7/Evidence Obligations.

## Context

Owner giao ngày17/11/2026, cho phép commit/push main. Baseline origin/main5917ea9;
worktree riêng giữ local edits checkout gốc. Ưu tiên MH0001/BBS2025 và NR0001/ADC2023.

## Inputs

Saved traces REMED-01/02, questions-only Pilot đã freeze, refined JSON và imported
EF-EG hiện có. Gold chỉ hậu kiểm, không đưa vào runtime.

## Outputs

Importer/catalog sửa tổng quát; projection mới riêng với hashes/provenance;
so sánh offline usable/retrieval và tối đa2QA Qwen; RCA/report/traces/implementation SHA.

## Allowed Changes

Importer, canonical catalog/context và eligibility khi có RCA; targeted tests,
runner và tracking. Giữ nguyên nguồn/các imported artifacts cũ.

## Out of Scope

M6/M7/Evidence Obligations, Agent/framework/architecture mới, doanh nghiệp/QA/Gold
hardcode, OCR/Gemini/Pilot mở rộng/Full600/fullCI; không tự nghiệm thu DONE.

## Implementation Steps

1. Đối chiếu saved traces với JSON và facts/tools/agent inventory.
2. Sửa rows/statement context/label mapping, kiểm negative controls.
3. Reimport riêng2filings bằng importer/EF-EG hiện có, kiểm fidelity/hashes/offline.
4. Freeze và retest đúng2QA một lượt; report, commit/push main, REVIEW.

## Acceptance Criteria

- [x] Hàng lỗi không loại các hàng có căn chỉnh rõ; không suy missing là zero.
- [x]130/131 tách nghĩa; label/code/statement bất đồng giữ unresolved.
- [x] Facts khôi phục qua Financial Tools/Agent với đúng kỳ/unit/pointer/hash.
- [x] Offline before/after, targeted tests và tối đa2QA có traces/coverage/limits.
- [x] Commit/push main, SHA verified; Owner/Tech Lead xác nhận DONE ngày17/11/2026.

## Required Tests

3controls logic chính, compatibility importer/context/mapping liên quan;
1offline integration thực tế2filings. Qwen tối đa2QA/20calls tổng/10calls mỗi câu,
300s/request/60sprovider/retries0, không nhiều vòng retest. Ruff/planning/diff.

## Risks and Blockers

Nguồn JSON chưa PDF-verified. Dữ liệu usable không đồng nghĩa verified goal coverage;
planning hoặc verification vẫn có thể chặn release. Không sửa các tầng đó.

## Implementation Evidence

Implementation `efc537ee6b92517465565a775681911b696ebf1f`;
[report](../../../docs/e2e-remed-03-canonical-mapping-eligibility.md).
37targeted PASS; projection2filings riêng, usable46→48/18→36,84Financial Tools lookups,
M5 candidates/graph/restart/fidelity đạt.2QA một lượt/13calls/97536tokens/0unknown;
NR10,56%/7citations/goal1of1;MH đúng131+inventory/3ACCEPT nhưnggoal0of4,
chưa document candidate.0of2→1of2 đúng/released, không Pilot accuracy.
186runtime/58raw JSON/14old-imported+index/132parent evidence/80local files bất biến;
M6/M7/Obligations/gates không đổi. Ruff/format/planning/diff đạt; không fullCI.
Traces/projection local artifacts/evidence/E2E-REMED-03; không commit raw/Gold/secrets.
Bàn giao9c19d8f đã push main/remote verified; Owner/Tech Lead xác nhận DONE
ngày17/11/2026 trong phạm vi mapping/eligibility. Giữ giới hạn MH/goal bindings/
document lane, chưa xác nhận readiness Pilot. Phiên đóng chỉ tài liệu/tracking và
planning/diff/Git; không runtime/artifacts/tests/Qwen/benchmark/CI.

## Handoff Notes

Next action: chờ Owner/Tech Lead giao nhiệm vụ tiếp theo; chưa tự tiếp tục Pilot45.
