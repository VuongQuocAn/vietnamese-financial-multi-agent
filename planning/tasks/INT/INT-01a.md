# TASK INT-01a — Existing Evidence Binding & Materialization

## Metadata

- Milestone: INT
- Status: REVIEW
- Priority: P1
- Dependencies: ARCH-01, GEN-01, E2E-01
- Estimated Complexity: S

## Objective

Materialize Gemini caches hiện có, xác minh nguồn PDF/trang và load qua M4 với
composition pin nguồn/snapshot gốc. Không cần QA cuối.

## Context

Owner giao 06/11/2026. Baseline main `2c38929`; ARCH-01 đã DONE.
GEN-01a BLOCKED và Web pending giữ nguyên. Vòng chốt Tech Lead cho phép
commit/push riêng INT-01a và yêu cầu CI trên implementation SHA.

## Inputs

Đề bài Owner; audit ARCH-01; M1-15/M1-16/M3; D-01 saved B09 và GEN-01 BCC.
Chỉ PDF/cache đã tồn tại, không gọi Gemini/OCR.

## Outputs

`artifacts/evidence/INT-01a/`: inventory, binding decisions, compositions,
repository, retrieval results, local samples/trace/coverage và ảnh đối chiếu.
[Report](../../../docs/int-01a-existing-evidence-binding-materialization.md).

## Allowed Changes

Source binding, loader composition nhỏ, replay script, focused tests, planning.
Giữ TextEvidence/TableEvidence, repository và public M4 APIs hiện có.

## Out of Scope

BM25, vectors, M5–M7 document QA, M8, fresh OCR, GEN-01a, thay financial contracts.

## Implementation Steps

Inventory → hash PDF + exact rerender → existing adapters → persist riêng →
composition preflight → M4 ID/page/text/cells/sources → real PDF spot checks.

## Acceptance Criteria

- 0 Gemini/OCR calls; source/snapshot identities và citations giữ nguyên.
- BBS2025 footer/p14/15, BBS2022 p11/18, BBS2024 p21/24 và BCC có real results.
- Unverified legacy không vào approved catalog; conflict/missing không fallback.
- Fidelity, idempotence/reload, negative cases và financial compatibility đạt.
- Artifacts riêng, report có mẫu thật local; dừng REVIEW chờ Tech Lead.

## Required Tests

Focused composition/M3/M4 và M6/M7 gates liên quan; real source-bound probes;
planning checker, Ruff file sửa, git diff check. Không benchmark/full Gemini E2E.

## Risks and Blockers

Financial context không là full prose. BCC narrative ngoài accepted primary pages
chưa có extraction. CI exact SHA chưa có khi chưa commit/push.

## Implementation Evidence

Implementation chưa commit; baseline `2c389296bdeedb965c1eeeb53dc55ef2bf274b00`.
151 records verified source binding/retrievable trên17trang;127text/24tables,
1.805cells/headers fidelity exact.34real acceptance checks;193targeted PASS,
sau loader batch read30composition/M4 PASS;0Gemini/OCR.72source hashes và8inherited
files unchanged. CI exact SHA chưa có, chờ commit/push được giao.
Artifacts `artifacts/evidence/INT-01a/final/`;18mẫu actual trong local report.
Ruff lint/format, planning109tasks và diff check PASS. Chờ Tech Lead nghiệm thu;
không coi CI exact SHA hoặc financial accuracy toàn PDF đã đạt.

## Handoff Notes

Next action: Tech Lead review INT-01a và phần CI implementation SHA còn chờ.
