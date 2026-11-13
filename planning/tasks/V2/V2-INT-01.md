# TASK V2-INT-01 — Minimal Integration Migration

## Metadata

- Milestone: V2
- Status: REVIEW
- Priority: P1
- Dependencies: ARCH-RESET-01
- Estimated Complexity: M
- Related Modules: Lite M5, API integration, M6 boundary, M7 coverage

## Objective

Triển khai requirement IDs, shared evidence workspace trong một request và phối hợp
ba specialists hiện có; nối M6/M7 bằng binding tối thiểu, không xây orchestration
framework mới hoặc refactor Ledger/M7 diện rộng.

Owner giao tiếp13/11/2026: hoàn thiện C07 mixed child→root binding, kiểm C01/C10;
làm trực tiếp main, V2 opt-in, không tạo task/nhánh/agent/policy mới. Offline đạt
mới chạy đúng một lượt C01/C07/C10, max6calls/câu/18tổng, không retry; API lỗi dừng.
Không sửa runtime hoặc chạy lại sau khi live FAIL. Commit/push đúng phạm vi lên main.

Owner giao tiếp13/11/2026: sửa ba nguyên nhân M5 source resolution, M6 claim-local
verification và M6→M7 requirement coverage; giữ V2-INT-01, trực tiếp main, V2 opt-in.
Dùng nguyên saved Qwen responses C01/C07, saved execution C04/C10 và negative controls.
Không gọi Qwen trong task này; config được cấp không thay thế quyền live riêng.
Commit/push thay đổi tối thiểu lên main; dừng REVIEW, không tự nghiệm thu DONE.

## Context

Owner/Tech Lead APPROVED ARCH-RESET-01 ngày13/11/2026 trên báo cáo commit
`3475a3af8a2d1635bfa6037c0743245ba2a3e9e5`. Ba điều chỉnh: workspace request-local,
thay boundary tối thiểu, nghiệm thu kiến trúc bằng offline invariants, không lấy
12/12Qwen PASS làm điều kiện duy nhất. Không audit lại.

## Inputs

Owner cấp phép sau offline: chỉ C01/C07,6calls/câu,12calls/60.000tokens tổng;
không thay model/endpoint/config, không retry. API lỗi hoặc kết quả PARTIAL/FAIL
thì dừng, không sửa tiếp. C10 hoãn. Lượt này dừng trước API do tokenizer subprocess
local timeout;0APIcalls/0tokens, C07 chưa chạy, chưa có kết quả Qwen mới.

[Thiết kế](../../../docs/arch-reset-01-multi-agent-simplification-review.md),
E2E-GEN-01 saved traces/catalogs/proofs, source hiện có và local edits đã ghi hashes.
Qwen config Owner cung cấp giữ ngoài Git/log; Owner duyệt3case/18calls/180000tokens,
6calls/300s mỗi case, không retry và fail-stop khi API lỗi/ngân sách hết.

## Outputs

Opt-in integration V2, focused offline controls/replay và báo cáo ngắn
[báo cáo](../../../docs/v2-int-01-minimal-integration-migration.md); artifacts riêng local ignored
`artifacts/evidence/V2-INT-01/`. Không ghi đè evidence E2E hoặc raw/processed.

## Allowed Changes

Lite orchestration/requirements/workspace, localized M6 numeric/semantic binding,
M7 coverage/dedup, targeted tests/replay và docs/planning. Giữ legacy readers,
contracts/module boundaries và default paths. Owner yêu cầu commit/push main đúng
phạm vi; không gom local edits ngoài task.

## Out of Scope

Không OCR/Gemini/M8/full CI, thêm agents/framework/database, đổi EF-EG hoặc corpus,
refactor Ledger/report writer toàn diện, mở task khác, lặp FIX cho đủ12PASS.
Không gọi Qwen trước offline integration đạt và có ngân sách/điều kiện dừng.

## Implementation Steps

1. Đăng ký nghiệm thu ARCH và V2-INT-01, lưu baseline local edits.
2. Requirements/assignments + request-local shared evidence; giữ nhánh hợp lệ khi task lỗi.
3. Nối M6 local verification và M7 coverage bằng sidecar, không migrate ledger cũ.
4. Focused tests và saved-data replay; sau đó live một lượt nếu được duyệt budget.

## Acceptance Criteria

- [x] Requirement IDs giữ qua tasks, candidates, verification admission và answer coverage.
- [x] Specialists đọc được shared evidence cùng scope, IDs không va chạm; phối hợp task phụ thuộc có owner.
- [x] Task/schema/model failure không xóa kết quả độc lập; lỗi kỹ thuật khác missing evidence.
- [x] M6 kiểm claim/local evidence; typed premises không bị prose label grammar từ chối; số sai vẫn chặn.
- [x] M7 dùng binding đã kiểm, không tự dựng lại requirement list của financial V2; ledger lịch sử không đổi.
- [x] Offline real-data replay kiểm requirements/evidence/claims/branch preservation; không coi synthetic PASS là financial quality.
- [x] Planning checker/diff/lint và targeted tests liên quan đạt; live chỉ theo ngân sách duyệt.
- [x] Bàn giao REVIEW, phân biệt lỗi kiến trúc/model/capability; không tự DONE.
- [ ] Tech Lead nghiệm thu implementation và giới hạn snapshot cuối chưa được live xác nhận.

## Required Tests

Focused integration controls cho plan/requirements/shared evidence/failure isolation,
M6/M7 boundary và offline saved-data replay. Regression suites chỉ những module chung
đã sửa; không full CI/browser. `python scripts/check_planning.py`, Ruff, `git diff --check`.

## Risks and Blockers

Qwen target/meaning/serialization có thể vẫn sai. Mixed capability/table financial
binding không được giả là có nếu tools chưa hỗ trợ.3case live0root released claims;
C07 child có1ACCEPT nhưng root không phát hành. Prompt/lane/status errors đã sửa
offline, không rerun; mixed final target/pin/inventory binding vẫn còn trong code.
Snapshot cuối chưa live xác nhận; không dùng kết quả trước sửa làm quality bản cuối.

## Implementation Evidence

Lượt xác nhận mới trên source main `811112a08c9f0d9cad9f37f5123c0c30aa4ecad3`
dừng trước provider: local token-count subprocess timeout45s, `m5:TimeoutExpired`;
pipeline provider_unavailable,0calls/0tokens/0releases, case51,76s. Đây là lỗi runner,
không phải API timeout hay FAIL chất lượng Qwen. Không chạy C07/sửa/rerun; giữ traces
ở `artifacts/evidence/V2-INT-01/live-confirmation-20261113/`. [Báo cáo](../../../docs/v2-int-01-qa-validation.md).

Implementation `474cc218498512748aaaa96ab463c070b27f9228` trên main, base `68c22ee`.
Raw replay C01:11ACCEPT/1ABSTAIN/2INVESTIGATE,9unique releases,3numeric requirements
satisfied,26,71%mộtlần; nợ/tài sản và ratio hết false ABSTAIN do global period.
C07:resolve đúng LNST2025/2024,2financial facts ACCEPT qua numeric fallback V2 sẵn có;
document ACCEPT nguyên ID/citationPDF12,final citations7/12. Không sửa raw Qwen outputs.
Source stage riêng46targetedPASS;1test M7 restoration đã FAIL ở baseline được giữ
nguyên/deselect. SavedC04absence khôngACCEPT,C10đúngproof/factACCEPT/sốsai khôngACCEPT;
negative source/value/period/type/unit/item/operand controls đạt. Ruff/planning/diffPASS.
0API,không fullCI/OCR/benchmark. C01 thiếu saved semantic verdict; synthesis/constraint
và live end-to-end chưa được chứng minh. [Chi tiết](../../../docs/v2-int-01-qa-validation.md).

### Lịch sử trước lần sửa source/period/coverage

Phiên hoàn thiện QA V2 theo Owner13/11: implementation
`2783e7dd71b1a53db91c1a363d757fff67630622`, trực tiếp main, V2 opt-in.
Offline giữ C07 child ACCEPT ở root/citations7+12, C01assignments/shared evidence,
C04chặn3absence,C10đúngproof/chặnsốsai;22historic/607protected unchanged.
Targeted cuối27PASS,Ruff/planning/diff đạt; không fullCI/API mới sau timeout.
Live đúng1lượt: C01PARTIAL5calls/26802tokens/156,45s; C07PARTIAL5calls/8851tokens/
107,40s,document1/1childACCEPT đếnroot nhưng thiếuLNST; C10INTERRUPTED1call timeout,
usage/timeE2Eunknown. Tổng11attempts,35653knowntokens+1unknown,0retry.
Đã dừng ngay API timeout, không sửa runtime hoặc rerun; giữ lỗi target/source handles,
M6comparisonperiodscope và thiếu synthesis/constraint trong báo cáo.
[Báo cáo QA thật](../../../docs/v2-int-01-qa-validation.md).


Implementation [544d56abb6ff5ab9a64b67e3b22ce2c94533bf48](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/544d56abb6ff5ab9a64b67e3b22ce2c94533bf48)
trên nhánh review/v2-int-01; baseline `3475a3af8a2d1635bfa6037c0743245ba2a3e9e5`.
Qwen prerequisite riêng3edc7c0; không gom local edits ngoài task hoặc sửa runtime thêm.
Offline replayC01shared7evidence/3tasks; C04baabsence khôngACCEPT; C10hai proof/fact
đúngACCEPT,sốsai khôngACCEPT;22historic entries nguyên vẹn,607non-runtime protected
unchanged.3tests integration cuốiPASS,43API/fusionPASS,6M6/integrationPASS;
schema drift sửa rồi7PASS (runs overlap). Planning143/Ruff/diffPASS.
Live một lượt3case,8calls/15876tokens,0retry/APIerrors;0released claims,không rerun.
Code corrections sau live chỉ offline-tested. [Chi tiết](../../../docs/v2-int-01-minimal-integration-migration.md).
Đóng gói review:7targeted PASS + real-data replayC01/C04/C10/22historic entries PASS
trên isolated checkout,0API; package imports verified. Planning139/Ruff/diffPASS.
Số143 phía trên thuộc working tree lịch sử, không phải số task trên nhánh review.

## Handoff Notes

Next action: Owner/Tech Lead review lỗi runner trước API và quyết định bước tiếp theo.
