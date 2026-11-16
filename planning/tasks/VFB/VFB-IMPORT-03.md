# TASK VFB-IMPORT-03 — Full Corpus Import

## Metadata

- Milestone: VFB
- Status: DONE
- Priority: P1
- Dependencies: -
- Estimated Complexity: M

## Objective

Import toàn bộ 41 tài liệu/1.488 trang refined JSON thành Canonical Evidence và
EF-EG, dùng lại pipeline pilot để chuẩn bị benchmark toàn corpus.

## Context

Owner giao ngày16/11/2026, tiếp tục IMPORT01/02 và E2E02 đang REVIEW; không tự
nghiệm thu các task trước. Baseline `2b3c2ab`, có local implementation trước đó.

## Inputs

`ViFinBench/refined/` read-only; adapter/context/graph/JSON catalog và M4/M5 hiện có.

## Outputs

Runner toàn corpus, artifacts thực tế riêng dưới `artifacts/evidence/VFB-IMPORT-03/`,
coverage41 tài liệu, kiểm tra restart/retrieval/graph và báo cáo readiness/exclusions.

## Allowed Changes

Importer/runner/catalog integration khi cần, targeted tests, report và planning.

## Out of Scope

Sửa JSON nguồn, OCR, Gold Answer để xây evidence, benchmark600, Gemini hàng loạt,
framework mới, tự phê duyệt PDF grounding hoặc push. Người dùng cho phép commit
khi Tech Lead phê duyệt đóng task ngày16/11/2026.

## Implementation Steps

1. Inventory nguồn, mở rộng runner pilot, giữ bundle riêng theo document.
2. Import41, persist/reload và graph/pointer/hash validation.
3. Financial Tools và M5 offline trên nhiều công ty ngoài pilot; coverage/exclusions.
4. Targeted checks và bàn giao REVIEW, nêu một next action.

## Acceptance Criteria

- [x] 41 tài liệu/1.488 trang được import; source hashes không đổi.
- [x] Evidence/facts/EF-EG persist/reload và graph validation có bằng chứng thực tế.
- [x] Financial Tools/M5 truy xuất qua JSON catalog hiện có ngoài pilot.
- [x] Coverage41 có Text/Table, observations, mapping, kỳ, unit và eligible facts.
- [x] Báo cáo hạn chế/readiness, targeted tests và planning/diff checks đạt.

## Required Tests

1–3 targeted controls cho corpus runner; một offline full-corpus import/smoke,
không full regression/API/benchmark.

## Risks and Blockers

JSON fidelity chưa phải PDF accuracy; catalog chỉ tiêu hữu hạn, context thiếu,
bảng ragged và tài liệu chỉ text phải giữ exclusions trung thực.

## Implementation Evidence

**DONE — Tech Lead APPROVED ngày16/11/2026**, người dùng chỉ đạo đóng task và commit.
Implementation [b23bb807b70fecdabb69c94f6597bf8cd591f52a](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/b23bb807b70fecdabb69c94f6597bf8cd591f52a)
đã commit local/xác minh; chưa push.10runtime fingerprints khớp nội dung Git
(chuẩn hóa newline); summary và bằng chứng kiểm thử giữ nguyên. Commit kèm
dependencies pilot JSON adapter/catalog/M4/M5 cần cho full import; local edits
ngoài phạm vi giữ riêng. Không phê duyệt benchmark600 hoặc nâng thành PDF accuracy.

Baseline `2b3c2ab`, kế thừa local IMPORT01/02/E2E02; không đổi trạng thái task trước.
[Report](../../../docs/vfb-import-03-full-corpus.md),
[coverage41](../../../docs/vfb-import-03-coverage.csv), artifacts ignored
`artifacts/evidence/VFB-IMPORT-03/full-final/`.
13.199Text/2.068Table/26.126observations/1.270mapped/1.043eligible trên37filing;
1.043lookups/31calculations, M5 36completed/1partial/2blocked/2clarification.
Graph134.073nodes/518.276edges valid/zero orphan; restart/hash/fidelity41 và
current projection equivalence41 đạt. Cover BCC_2024 p3 được bind nguồn;
AME/ATS thiếuunit, BCC2025 text-only và C69 company binding còn exclusions.
13targeted/compatibility PASS; Ruff/planning/diff đạt,0OCR/Gemini/Gold/benchmark.
Phiên đóng task chỉ planning/diff và đối chiếu Git/evidence; không chạy lại tests,
import, API, benchmark hoặc fullCI.

## Handoff Notes

Next action: chờ Owner/Tech Lead giao công việc tiếp theo.
