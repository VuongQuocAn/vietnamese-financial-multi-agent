# TASK GEN-02-Fix-B — OCR Source Quality & Controlled Evidence Correction

## Metadata

- Milestone: GEN
- Status: REVIEW
- Priority: P1
- Dependencies: GEN-02-Fix-A, QA-01b, EXT-01
- Estimated Complexity: M

## Objective

Owner giao09/11/2026; baseline `46aa45f`. Xác minh H08 bằng PDF, chặn source sai,
chuẩn bị correction/version có provenance và approval riêng. Dừng REVIEW.

## Context

[GEN-02](../../../docs/gen-02-cross-company-generalization.md),
[Fix-A](../../../docs/gen-02-fix-a-qa-coverage.md),
[EXT-01](../../../docs/ext-01-full-document-evidence-coverage.md).
GEN-02 REVIEW là nguồn findings; Fix-A đã DONE. Không chạy lại Fix-A QA.

## Inputs

Accepted composition/repository, BCC2024 PDF16/selector7, saved response/render và
GEN-02 discrepancy/oracle read-only. Request đầy đủ local
`artifacts/evidence/GEN-02-Fix-B/task-request.md`. Giữ GEN-01a/Web pending.

## Outputs

[Report](../../../docs/gen-02-fix-b-ocr-source-quality.md); local artifacts
`artifacts/evidence/GEN-02-Fix-B/`: PDF review, correction/validation, candidate
manifest, H08 states, negative controls, compatibility, CI.

## Allowed Changes

Text correction records, versioned composition, current source-quality policy;
M6/admission/replay và focused tests. Commit/push main, đối chiếu CI đúng SHA.

## Out of Scope

Accepted source/ledger mutation, OCR/Gemini live, full40QA, Fix-A fresh rerun,
Web, PERF-01, M8, fake approval hoặc semantic OCR detector.

## Implementation Steps

PDF/source audit và tối đa5 additional excerpts → tối đa2vòng fixes/tests →
final targeted H08/control/compatibility → report/CI → REVIEW.

## Acceptance Criteria

- [x] PDF discrepancy xác minh; original inputs/ledger bất biến.
- [x] Correction provenance, validation, versioning và approval tách biệt.
- [x] Original confirmed defect và unapproved correction không phát hành.
- [x] Wrong bindings/content, old proof và flag removal bị chặn.
- [x] Real H08 và A7, ledger/verification/search compatibility đạt.
- [x] CI đúng SHA; báo rõ actual release với isolated fixture.

## Required Tests

Focused correction/M6/replay/search tests và real H08/A7; một final pass.
Không Gemini/OCR/full40QA hoặc lặp full suite local. Ruff/planning/diff checks.

## Risks and Blockers

PDF thực tế ghi “khó có khả năng thanh toán”, không phải “không có” như RCA cũ.
Giữ RCA/oracle cũ bất biến, lập record mới đúng PDF. Chưa có phê duyệt Tech Lead
cho text correction release; chỉ engineering validation, candidate chưa accepted.

## Implementation Evidence

Implementation `d78f1159517de6437bd039d5030040f2d05013b6` đã push main,14files.
[CI42549793493](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42549793493) completed/SUCCESS đúng implementation SHA; 1169 Python/9 Web PASS; full regression manual SKIPPED.
66final focused tests PASS (12correction/10negative controls); A7 PASS;
H08 original/pending INVESTIGATE, isolated approved-state fixture ACCEPT đúng PDF;
17legacy claims replay nguyên file. Independent audit phát hiện1extra material claim
PDF30/9, đã quarantine và filter warm cache;2P2lexical giữ ngoài scope.5additional
excerpts;0actual approvals/accepted corrected releases.38inputs/4frozen/runtime
và inherited changes nguyên hash. CI đã đối chiếu đúng implementation SHA; chưa actual release approval.

## Handoff Notes

## Closure09/11/2026

Tech Lead chấp nhận implementation `d78f115`, chưa approve promotion H08; giao closure
nhỏ về persistent quarantine/approval, startup/transfer và preflight release thật.
86packaged tests PASS (gồm18correction/API), process/API mới với moved storage/cwd nạp đúng policy pin,
giữ2quarantines/0actual approvals. H08 candidate đúng digest/PDF/content, preflight
pending_approval; wrong digest blocked; old bad claims không visible, ledger/source
bytes giữ nguyên. Không tạo approval thật hoặc accepted promotion.
Closure `28bfb6d8d5a9a071061444f26745454c0066e4aa`; [CI42554771165](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42554771165) SUCCESS đúng SHA;86packaged tests PASS,18correction/API trong nhóm này; real H08 preflight đúng digest/PDF, pending_approval;2quarantines/0actual approvals. PDF30 giữ quarantine; accepted release không đổi.

Next action: Tech Lead review closure và quyết định approval H08 theo exact release digest; PDF30 tiếp tục quarantine.
