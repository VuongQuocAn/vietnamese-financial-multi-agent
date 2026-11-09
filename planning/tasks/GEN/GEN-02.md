# TASK GEN-02 — Cross-Company End-to-End Generalization & Blind QA Validation

## Metadata

- Milestone: GEN
- Status: DONE
- Priority: P1
- Dependencies: GEN-01, QA-01b, EF-01, EXT-01
- Estimated Complexity: L

## Objective

Status: **REVIEW**, có P1 blockers để Tech Lead quyết định. Owner giao ngày 08/11/2026; baseline
`02a160fdca013ac55972949c9002622dc643de01`, main khớp origin/main.
Dependencies: GEN-01, QA-01a, QA-01b, EXT-01, EF-01 DONE.

## Context

QA-01b DONE; GEN-02 được Owner giao mới. Giữ thay đổi GEN-01a/Web hiện hữu.

## Inputs

Accepted BBS catalog, BCC normalized-release/audit-release, EXT-01 compositions,
PDF gốc và QA-01b controls. Full request lưu local với fingerprint.

## Outputs

Engineering validation, không M8 benchmark: 40 câu tiếng Việt, 25 development và
15 blind holdout. Cố định câu hỏi/oracle/provenance trước output GEN-02; holdout chỉ
chạy sau development fixes. Đối chiếu accepted inputs và mẫu PDF gốc, không lấy
pipeline output làm oracle. Phân biệt source-answerability/capability/restrictions.

Chạy actual M5 → M4/BM25/EF-EG → M6 → Ledger → M7/Firewall, giữ source identities,
D03-B10 và quality gates. Audit requirement coverage, semantic relevance, citation
support, false abstention và unsupported claims. Sửa tổng quát P0/P1 có RCA/tests;
báo blockers chính sách, không bypass. Báo development before/after và holdout riêng,
numerator/denominator/case IDs, latency và provider usage. Giữ negative controls riêng.

Output: [report](../../../docs/gen-02-cross-company-generalization.md), local artifacts
`artifacts/evidence/GEN-02/` gồm environment, frozen dataset, traces, audits, failure/fix
register, metrics và regression. Bản yêu cầu đầy đủ lưu local cùng artifacts.

Không sửa/commit GEN-01a/Web pending; không OCR/extraction lại, đổi model, M8,
CHAT-01, Web redesign hoặc tối ưu PERF-01 diện rộng. Task cho phép commit/push main
các file GEN-02, xác minh CI đúng SHA; dừng REVIEW, Tech Lead quyết định DONE.

## Allowed Changes

Runner/audit và fixes tổng quát trong routing, retrieval, M6/M7 có RCA; planning/report.

## Out of Scope

M8, extraction lại, Web, PERF-01 diện rộng, đổi restrictions hoặc approved evidence.

## Implementation Steps

Audit → freeze → development → RCA/fixes → retest → holdout → report/CI → REVIEW.

## Acceptance Criteria

- [x] 40 questions/oracles cố định trước execution, holdout không dùng tuning.
- [x] Actual E2E 25 development before/after và15holdout, requirement/citation audit.
- [x] P0/P1 có RCA, fixes hoặc technical blocker; safety controls không regression.
- [x] Report có metrics/IDs, latency, limitations; CI đối chiếu đúng SHA.

## Required Tests

Focused regression theo fixes, QA-01a/b controls, Ruff/planning/diff và CI.

## Risks and Blockers

Quota/provider availability, source quality và approved capability gaps cần báo riêng.

## Implementation Evidence

Implementation: `fcba4ff64ae0e5958300e6eeb408601cd62f4d20` đã push main; [CI42494041844](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42494041844) completed/SUCCESS; 1151 Python/9 Web PASS; full regression manual SKIPPED đúng implementation SHA.
Runtime seal/oracle bất biến sau holdout; clean staged-tree smoke D03/D18 full,
khớp exact implementation tree, không gồm3GEN-01a source edits. Development10full/4partial/10abstain/1sai mục tiêu →22full/1partial/2abstain;
Full Answer Rate10/22→22/22. Holdout7full/1partial/7abstain, Full Answer Rate7/12,
5/13source-answerable abstentions;0incorrect/unsupported releases. Citations191/191,
249/249 và84/84 theo từng phase. H03 pipeline-capability oracle clarification giữ
original denominator; không nâng score bằng đổi nhãn. [Report](../../../docs/gen-02-cross-company-generalization.md).

P1 holdout: thiếu prepared revenue_yoy BCC2025; topic/boundary selection dù retrieval
có nguồn; H11 mất loan requirement; H12 useful partial C1→abstain regression. H07
quality block đúng trên selected page, H08 original PDF phát hiện OCR thiếu negation.
Không sửa runtime theo holdout; cần follow-up/fresh blind set và source review/release
riêng. Giữ M6 replay policy;17accepted claims từ3legacy ledgers đọc lại nguyên file.

4targeted final/25document-fusion compatibility PASS;138related/70specialist/43router-
orchestrator/35search-document groups PASS (overlap). Real7binding controls PASS;
live6Gateway invocations/19742known tokens/0reported provider errors, BBS full nhờ
numeric fallback, BCC full qua model.38approved input hashes/original frozen dataset
vàruntime sau seal không đổi; inherited GEN-01a/Web giữ ngoài implementation.
Next action: Chờ Owner/Tech Lead giao nhiệm vụ tiếp theo; không tự triển khai follow-up hoặc bắt đầu task khác.

## Handoff Notes

Giữ toàn bộ inherited pending. Chỉ stage phần GEN-02; DONE theo quyết định nghiệm thu ngày09/11/2026.

## Nghiệm thu có giới hạn09/11/2026

Owner/Tech Lead chấp nhận GEN-02 và GEN-02-Fix-B DONE ngày09/11/2026 với các giới hạn đã ghi nhận. Đây là nghiệm thu có giới hạn, không xác nhận H08 đã promote hoặc M8-ready. H08 actual approval đã lưu nhưng accepted-release activation còn thiếu; E2E sau promotion chưa chạy; PDF30 tiếp tục quarantine; các hạn chế research/QA còn nguyên. Checkpoint chỉ cập nhật planning, không sửa runtime hoặc chạy lại CI/QA.
Implementation và bằng chứng CI giữ nguyên; documentation checkpoint trước nghiệm thu `1b19d82f4bff228a59e481385af7c715147c8693`.
Next action: Chờ Owner/Tech Lead giao nhiệm vụ tiếp theo; không tự triển khai follow-up hoặc bắt đầu task khác.
