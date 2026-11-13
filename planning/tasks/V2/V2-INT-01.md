# TASK V2-INT-01 — Minimal Integration Migration

## Metadata

- Milestone: V2
- Status: REVIEW
- Priority: P1
- Dependencies: ARCH-RESET-01
- Estimated Complexity: M
- Related Modules: Lite M5, API integration, M6 boundary, M7 coverage

## Phiên tối ưu latency QA — 13/11/2026

**REVIEW**, 13/11/2026; implementation `40745138e0c987fcfa05915726c2e530bbecab4d`, main/V2 opt-in.
Live C01/C07/C10 cùng source:9calls/35.845tokens/0unknown/error/retry, QA3PASS;
Numeric13/13,ClaimF1=100%,Citation29/29,AnswerAccuracy3/3 theo rubric Tech Lead
đã chấp nhận (C07 constraint riêng, C10 bounded observations). E2E182,83→119,64s /
132,86→90,46s /241,70→167,47s; calls giữ2/3/4. API internal ngoài provider
48,99→14,97s /43,80→20,46s /17,90→4,09s; không quy startup/provider gains cho code.
M6 dùng request snapshot, bỏ deepcopy claims/API thừa, C JSON encoder giữ atomicity,
selector index vẫn kiểm full page identity. Replay giữ exact clauses/M6 decisions/
citations/bindings/shared EF-EG. Paired no-API processing giảm29%/28%/58% so baseline
đo lại; lưu cả lần baseline chậm và intermediate runs.44targeted isolated PASS,
Ruff/planning/diff;không fullCI. Giữ caveats/page-level, không đổi agent/prompt/M6
policy hoặc local edits ngoài task; còn cold imports, provider latency và prose lặp.
[Báo cáo](../../../docs/v2-int-01-qa-validation.md).

### Baseline và chỉ đạo trước phiên tối ưu

Owner cho phép chủ động lựa chọn kỹ thuật và kiểm Qwen miễn phí; trực tiếp main,
giữ local edits, dừng khi API/hạ tầng lỗi, commit/push và bàn giao REVIEW. Chỉ đạo này
thay các giới hạn live cũ bên dưới; các Inputs/Evidence trước phiên là lịch sử.

Implementation `b113136f876b7fa2c1411c8295e0a09cdb97220c`. Sửa typed analysis envelope, tách notes chưa kiểm chứng
khỏi pure arithmetic, dynamic goal/source-anchor binding và runner một process,
atomic state, validate deadline 300s. Không thêm agent/đổi EF-EG/waive M6.
Final live đủ3case cùng source:14calls/50.688tokens,0unknown/retry/provider errors.
Numeric Accuracy13/13, numeric EM3/3; Claim P21/21, Recall16/19, microF1=91,43%;
citation accuracy21/21, Answer Accuracy0/3. C01/C07/C10 PARTIAL do còn thiếu tổng hợp/
giải thích giới hạn; mixed-period reasoning, prose và latency vẫn có giới hạn.
16isolated V2/M6 targeted PASS, runner/scoring/M7 controls, Ruff/planning/diff;
không full CI/OCR/Gemini. [Báo cáo](../../../docs/v2-int-01-qa-validation.md).

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

Chỉ đạo hiện hành: cải thiện giữ yêu cầu nhận xét/tổng hợp/giới hạn ở M5, M7 tự nhiên
và không lặp bằng claims M6/citations; không thêm agent/đổi kiến trúc. Live C01/C07/C10
trên dữ liệu thật; PARTIAL/FAIL tiếp tục câu kế, chỉ dừng API/hạ tầng. Sửa trong V2 có
bằng chứng, targeted checks; không full CI/milestone mới; commit/push main, REVIEW.

Chỉ đạo mới nhất: bỏ pre-count/token cap, chỉ ghi usage API; không sửa runtime hoặc
full tests/CI. Live C01/C07 một lượt trên474cc21, giữ config và không retry; API lỗi
dừng ngay, QA PARTIAL/FAIL thì lưu nguyên văn/traces, chấm Gold và dừng, không FIX.
Kết quả: C01 live PARTIAL, đã dừng; C07 chưa chạy theo điều kiện6.

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
- [ ] Tech Lead nghiệm thu QA trên source cuối và các giới hạn còn lại.
- [x] Live C01/C07/C10 hoàn tất trên cùng implementation SHA; chấm final answer với Gold.

- [x] QA live bản cuối đủ ba câu, đầy đủ nhận xét/tổng hợp/giới hạn có evidence.

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

Source cuối `5f717726f0e16010f1ce7a3335f249fa7ca369a3` (trước đó d0f0e7c,
9526fa0,6d3f834). M5 giữ discourse goals/dependencies/shared canonical evidence;
M6 giữ truth/goal binding và request period pin; M7 group/dedup, chỉ bound claims + operands.
Hai lượt live đủ3câu còn PARTIAL/PARTIAL/FAIL. LượtB9526fa0: Answer Accuracy0/3;
Claim F1 C01=66,67%,C07=88,89%,C10=0%. Đã sửa code cho ownership/named-goal contract/
inferred-date failures nhưng lượtC5f71772 bị ngắt process sau5success responsesC01,
chưa final, C07/C10NOT_RUN/metricsN/A. Tổng33calls/114935tokens/0unknown/0retry,
0provider errors quan sát. Dừng do hạ tầng, không rerun; chưa xác nhận quality bản cuối.
37targeted stagePASS,1shared-owner control và targeted cuối; Ruff/planning/diffPASS,
không fullCI/Gemini/OCR/benchmark. [QA và nguyên nhân còn lại](../../../docs/v2-int-01-qa-validation.md).

Live mới trên đúng `474cc218498512748aaaa96ab463c070b27f9228`: C01 một lượt,
5calls/26599tokens provider-reported/0unknown/0retry/130,06s,0APIerrors.
Pipeline completed_with_caveats,10ACCEPT/10ledger/10releases,3numeric bindings satisfied;
Gold QA PARTIAL: thiếu tổng hợp ba nhánh có giới hạn, ratio còn lặp; số/citations đúng.
Answer Accuracy0/1, Claim Precision9/9=100%, Recall7/8=87,50%, F1=93,33%.
Đã lưu nguyên văn final/traces và dừng; C07 NOT_RUN/metricsN/A. Runner đã bỏ pre-count/
hard token cap; không sửa runtime/rerun tests/CI. [Chi tiết](../../../docs/v2-int-01-qa-validation.md).

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

Next action: Tech Lead nghiệm thu latency/QA trên4074513 và các giới hạn đo lường còn lại; dừng REVIEW.
