# Trạng thái hiện tại

Cập nhật 2026-11-05 (Asia/Bangkok); nguồn [Registry](tasks.md).

## M7-02 — Report Outline Planner

Status: **REVIEW**, Owner giao05/11/2026; baseline HEAD/origin
`445733426514cc0d8c3ce535c8b8fa931e93702f` đã xác minh. Cho phép commit/push main.
[Spec](tasks/M7/M7-02.md),[report](../docs/m7-02-report-outline-planner.md).
Typed verified-only outline/slots/local gate/bounded Gateway;48 engineering controls
(47 suite+1 corrected targeted),327 compatibility PASS;64/64 oracle (36 BBS/28 controls),
section/claim precision/recall1.0,zero safety leakage. Fresh3calls/4655tokens:
0/3 proposals accepted,fallback3/3 đúng oracle,LIVE PARTIAL;không retry.
15231 protected hashes/Web unchanged;Ruff/format/planning/diff PASS.
Implementation chưa commit,CI chờ push;chưa independent financial accuracy.
Next action: Tech Lead review M7-02 sau exact-SHA CI; không bắt đầu M7-03.

## M7-01 — Vietnamese QA Composer

Status: **DONE**, Tech Lead APPROVED ngày05/11/2026; chấp nhận implementation16065fae
và các giới hạn P2. Owner giao05/11/2026. Baseline local/origin main
`67700c3ff4e3aa170d9af8c0da872032dc2be1d0` đã xác minh; Tech Lead phê duyệt M6.
[Spec](tasks/M7/M7-01.md), [report](../docs/m7-01-vietnamese-qa-composer.md).
Typed/read-only QA, protected slots, bounded Gateway/local gate;35 QA tests
(34 suite+1 targeted sau fixture fix),236 M4/M5/M6 compatibility PASS.
66/66 oracle (40 BBS/26 controls),fresh3/3calls/5.555tokens;zero unsupported claims,
fabrication/mixing/lost caveats.15.118 protected hashes/Web unchanged.
Implementation `16065fae004335ae224b7b4a6e2e74f5098b26f8` đã push main;
[CI41948527583](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41948527583)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS,full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI cho checkpoint SHA.
66/66 là agreement với source-bound oracle, không phải độ chính xác tài chính độc lập.
Giữ D03-B10 và các giới hạn P2; phiên nghiệm thu chỉ cập nhật tài liệu/planning,
chạy planning/diff checks; không chạy lại tests/evaluation/Gemini hoặc sửa runtime.
Next action: chờ nhiệm vụ mới từ Owner/Tech Lead; không tự bắt đầu M7-02.

## M6-06 — Verified Claim Ledger

Status: **DONE**, Tech Lead phê duyệt M6 theo task M7-01 ngày05/11/2026; Owner giao04/11/2026; baseline main/origin
`9b807f370c144181588818c46de70e3d5f0fe485`, M6-01–05 DONE.
[Spec](tasks/M6/M6-06.md), [report](../docs/m6-06-verified-claim-ledger.md).
Proof admission/atomic JSON repository/read-only M7 facade;119 M6 compatibility
và22 final ledger tests PASS.109 replay cases:58stored/51rejected,27controls PASS,
29representative BBS,2accepted revisions,unsafe0/false rejection0.
Final-cache integrity57primary entries/27lineages/8filters PASS;
full replay trước cache, không fresh full negative replay sau cache.
Implementation `88ae91d40d5d4f0b4cf3f3526b96533b34a3d694` đã push main;
[CI41823101329](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41823101329)
completed/SUCCESS đúng SHA,Python3.12 SUCCESS;Web/full regression SKIPPED.
14.569 protected hashes/Web unchanged;0Gemini/OCR,giữ D03-B10;chưa M7 hoặc
independent PDF financial accuracy. Checkpoint sau chỉ docs/planning [skip ci].
Next action: triển khai M7-01 đã được giao.

## M6-05 — Verification Decisions

Status: **DONE**, Tech Lead nghiệm thu ngày04/11/2026, cho phép đồng bộ planning.
Owner giao04/11/2026; baseline main/origin
`ce7b9c32966d37dbd34d18c75f9c7d5145a31b44`, M6-01–04 DONE.
[Spec](tasks/M6/M6-05.md). Deterministic Judge và bounded revision controller;
31 Judge/loop +156 compatibility +7 final bounded PASS; initial94/94 batches,
6/6loops và targeted2/2 PASS.107 decisions, zero unsafe ACCEPT/false abstention.
Implementation `018798a25a8b232dfc5302ed17b12ed905d87dd8` đã push main;
[CI41756388273](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41756388273)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS,full regression SKIPPED.
14.057 baseline hashes unchanged; giữ Web local/accepted artifacts/D03-B10.
Checkpoint sau chỉ docs/planning [skip ci]; chưa ledger/independent financial accuracy.
Main e318461 đã xác minh chỉ thêm docs/planning sau implementation018798a.
Phiên đồng bộ nghiệm thu chỉ planning checker/diff check; không chạy lại tests,
evaluation/Gemini/OCR hoặc sửa runtime/accepted artifacts.
Next action: chờ Owner/Tech Lead giao nhiệm vụ mới; không tự bắt đầu M6-06.

## M6-04 — Financial Logic Critic

Status: **DONE**, Tech Lead nghiệm thu ngày04/11/2026, cho phép đồng bộ planning.
Owner giao04/11/2026; baseline main/origin94bf698 khớp.
[Spec](tasks/M6/M6-04.md), [report](../docs/m6-04-financial-logic-critic.md).
Typed per-assertion reasoning, deterministic-first và bounded Gemini qua Gateway;
không decisions/ledger.155 focused/compatibility PASS,29 final logic PASS;
71/71 offline final-v2 (20 new controls). Implementation
`4a09238d4d1bfe15b88e3090425e4319f947ab75` đã push main;
[CI41751757736](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41751757736)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS,full regression SKIPPED.
Initial live2/4, targeted1/2;3/4 unique scenarios có valid đúng oracle, không fresh4/4.
Đủ6calls/122.842recorded tokens, haiHTTP503 usage unknown; causal chưa live-assessed.
Đã rút prompt/làm rõ IDs,28logic+4post-prompt mock PASS;final balance-versus-flow fix
29logic PASS.13.077original protected hashes unchanged, giữ Web local/D03-B10.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI cho checkpoint SHA;
claims pending, chưa full verification accuracy. Không thêm calls.
Main e27b4fc đã xác minh chỉ thêm docs/planning sau implementation4a09238.
Phiên đồng bộ nghiệm thu chỉ planning checker/diff check; không chạy lại tests,
evaluation/Gemini/OCR hoặc sửa runtime/accepted artifacts.
Next action: chờ Owner/Tech Lead giao nhiệm vụ mới; không tự bắt đầu M6-05.

## M6-03 — Evidence Critic

Status: **DONE**, Tech Lead nghiệm thu ngày04/11/2026, cho phép đồng bộ planning.
Owner giao04/11/2026, baseline main/origin5346644 khớp.
[Spec](tasks/M6/M6-03.md), [report](../docs/m6-03-evidence-critic.md).
Typed evidence support/context/trace, deterministic-first, bounded Gemini qua Gateway.
144 focused/compatibility +19 post-cache PASS;63/63 offline cases sau annotation
correction E35,68 assessments/12controls;fresh Gemini2/2 semantic cases,
2calls/8.992tokens;13.060protected hashes unchanged. Chi tiết/phân loại trong report.
Implementation `198234a62d5cae8d4878eb249dac729b013c55c6` đã push main;
[CI41745959202](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41745959202)
completed/SUCCESS đúng SHA, Python3.12/Web smoke SUCCESS, full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI cho checkpoint SHA.
Giữ Web local/accepted artifacts/D03-B10/claims pending; chưa full verification accuracy.
Main d2a8746 đã xác minh chỉ thêm docs/planning sau implementation; phiên đồng bộ
nghiệm thu chỉ planning checker/diff check, không chạy lại tests/evaluation/Gemini/OCR.
Next action: chờ Owner/Tech Lead giao nhiệm vụ mới; không tự bắt đầu M6-04.

## M6-02 — Deterministic Financial Validators

Status: **DONE**, Tech Lead nghiệm thu ngày03/11/2026, cho phép đồng bộ planning.
Owner giao03/11/2026; baseline main/origin51292cf khớp.
[Spec](tasks/M6/M6-02.md), [report](../docs/m6-02-deterministic-financial-validators.md).
Typed per-check results, bounded prose checks và independent canonical/M4 replay.
30 validator +78 compatibility tests PASS; final72rows/16controls đúng kỳ vọng,
12.753 protected hashes unchanged. Không Gemini/OCR hoặc decision/ledger.
Implementation `58980d1abde246bfd6a8ec97a6fe34bd84919497` đã push main;
[CI41641546537](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41641546537)
completed/SUCCESS đúng SHA; Python3.12/Web smoke SUCCESS, full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI cho checkpoint SHA.
Giữ accepted artifacts và Web local; chưa decision/ledger/financial accuracy tổng quát.
Main39d41ef đã xác minh chỉ thêm checkpoint docs/planning sau implementation.
Parser chỉ hỗ trợ mẫu đã xác định; chưa chứng minh accuracy độc lập trên PDF
hoặc tính đúng đắn của diễn giải. Phiên nghiệm thu chỉ planning checker/diff check,
không chạy lại tests/evaluation/Gemini/OCR hoặc sửa runtime/accepted artifacts.
Next action: chờ Owner/Tech Lead giao nhiệm vụ mới.

## M6-01 — Candidate Claim Contracts

Status: **DONE**; Tech Lead APPROVED ngày03/11/2026 sau review trực tiếp
contracts/adapter/focused tests; không phát hiện P0/P1.
Owner giao03/11/2026, baseline main/origin8407897 khớp.
[Spec](tasks/M6/M6-01.md), [report](../docs/m6-01-candidate-claim-contracts.md).
Typed pending claims và M5→M6 adapter;95 bounded +10 final focused PASS;
21/21 final saved BBS conversions,26claims/5calculations/1conflict,zero live calls.
12.635 protected hashes unchanged, gồm Web local và accepted artifacts.
Implementation `f803ebfc8ca8f7c41ee83e09808da453299e53c5` đã push main;
[CI41636974349](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41636974349)
completed/SUCCESS đúng SHA; Python3.12/Web smoke SUCCESS, full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI cho SHA checkpoint.
Giữ D03-B10/scope/source quality/page-level caveats; claims vẫn pending/null decision.
21/21 conversions được ghi nhận từ report, chưa độc lập chạy lại.
Tech Lead xác nhận main047891d chỉ thêm docs/planning sau implementation.
Phiên đồng bộ nghiệm thu chỉ planning checker/diff check; không chạy lại tests,
conversions/Gemini/OCR hoặc sửa runtime/accepted artifacts.
Next action: chờ Owner/Tech Lead giao nhiệm vụ mới; không bắt đầu M6-02.

## M5-08 — Agent and Tool Orchestration

Status: **DONE**; Tech Lead APPROVED ngày03/11/2026, cho phép đồng bộ planning.
Owner giao03/11/2026; baseline main/origin `745cf46`.
[Spec](tasks/M5/M5-08.md),[report](../docs/m5-08-agent-orchestration.md).
Typed sequential pipeline, role projections/metric closure, deterministic aggregation;
Router metric-only operands và scoped prompts/coverage fixes từ actual live.
Offline36/36 hợp nhất (không fresh full rerun),8/8 post-fix representative;
live initial1/4 (11calls),targeted partial-live2/2 (4calls),saved replay2/2;
tổng15 actual calls/35.883tokens,không fresh4/4.339 bounded+85 final focused PASS;
9 Specialist/42 Router replays exact;18metrics/29queries/QA36/15contracts/19traces
và5.030protected hashes giữ nguyên. Implementation `18689287aaecc1257762564a9693948b4b273b96`
đã push main;[CI41562965030](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41562965030)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS,full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci]; không gán CI cho SHA checkpoint.
Giữ Web local/D03-B10/claims chưa verified; không OCR/extraction/benchmark cũ.
Phiên nghiệm thu chỉ cập nhật planning và chạy planning checker/diff check;
không chạy lại Gemini/OCR/tests/benchmark hoặc sửa runtime/accepted artifacts.
Giữ nguyên các limitations đã báo.
Next action: chờ Owner/Tech Lead giao nhiệm vụ mới; không bắt đầu M6.

## M5-07 — Adaptive Routing Rules

Status: **DONE**; Tech Lead APPROVED ngày03/11/2026, cho phép đồng bộ planning.
Owner giao03/11/2026; baseline main/origin86a8cc5.
[Spec](tasks/M5/M5-07.md),[report](../docs/m5-07-adaptive-routing.md).
Router deterministic/read-only, typed references/trace;không execution/M5-08.
Final42/42,precision/recall100%,partial9/9,risk20/20,determinism42/42;zero Gemini/tool.
250 bounded+4 final focused PASS;9 compatibility assertions exact;
18metrics/29queries/QA36/15contracts/19traces và4.725hashes unchanged.
Implementation `c40947687e1e9e62a21a7179a11ed2ef13447dcc` đã push main,remote khớp;
[CI41556677681](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41556677681)
completed/SUCCESS đúng SHA;Python3.12/Web smoke SUCCESS,full regression SKIPPED.
Checkpoint sau docs/planning [skip ci];không gán CI cho checkpoint SHA.
Giữ Web local/D03-B10,claims chưa verified. Initial36/41 reason scoring giữ riêng.
Phiên nghiệm thu chỉ cập nhật planning và chạy planning checker/diff check;
không gọi Gemini, chạy lại tests/benchmark hoặc sửa runtime/accepted artifacts.
Next action: chờ Owner/Tech Lead giao nhiệm vụ mới; không tự bắt đầu M5-08.

## M5-06 — Cash Flow and Earnings Quality Specialist

Status: **DONE**; Tech Lead APPROVED ngày03/11/2026, cho phép đồng bộ planning.
Owner giao03/11/2026, baseline main/origin7364acc đã xác minh.
[Spec](tasks/M5/M5-06.md), [report](../docs/m5-06-cash-flow-earnings-quality-specialist.md).
Reuse common/Gateway; B03 facts/sign và B02 profit nguồn riêng; chưa verification.
Offline v2 28/28; Gemini initial5/6, targeted2/2,8calls/17.103tokens, không fresh6/6.
245 bounded PASS ở vòng implementation,24 final focused PASS;7 compatibility
replays exact;18metrics/29queries/QA36/15contracts/19traces và4.135hashes giữ nguyên.
Initial failures/summary repair giữ riêng; source-review unverified giữ caveat.
Implementation `b7bd376530e84e93ab04189361ae07672c7c72d2` đã push main;
[CI41552323768](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41552323768)
completed/SUCCESS đúng SHA: Python3.12/Web smoke SUCCESS, full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI cho SHA checkpoint.
Giữ Web local/D03-B10, claims chưa verified.
Phiên nghiệm thu chỉ planning/checker/diff; không gọi thêm Gemini hoặc chạy lại
tests/benchmark/OCR/extraction, không sửa runtime/accepted artifacts.
Next action: chờ Owner/Tech Lead giao nhiệm vụ mới; không tự bắt đầu M5-07.

## M5-05 — Liquidity and Leverage Specialist

Status: **DONE**; Tech Lead APPROVED ngày02/11/2026, cho phép đồng bộ planning.

P1 scope correction theo Tech Lead: dùng explicit constraints M5-02, không dùng
“riêng” hoặc false scope ambiguity từ M4.43 targeted tests PASS; BBS2025 câu giữ
riêng evidence tạo2 candidates59,06% với exact lineage; M5-04 real compatibility3/3.
0 actual Gemini/OCR,4 saved-response replays;10 pinned hashes unchanged.
Fix `3f7e1ce46a51db0648243d1c8776a661e693133f` đã push main, remote khớp;
[CI41469949667](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41469949667)
completed/SUCCESS đúng fix SHA, Python3.12/Web smoke SUCCESS, full regression
SKIPPED. Chấp thuận gồm P1 scope fix; checkpoint sau chỉ docs/planning [skip ci].
Implementation/CI dưới đây là bản gốc.

Owner giao02/11/2026. Baseline main/origin
`348528fc6e39356b9ac2706307e9ade7db5f12fc` đã xác minh.
[Spec](tasks/M5/M5-05.md), [report](../docs/m5-05-liquidity-leverage-specialist.md).
Specialist/common grounding hoàn tất; offline21/21, live initial6/6,6calls/9.879tokens,
targeted0; grounding/numeric/citations100%, BBS2025 Debt-to-Assets59,06% full lineage.
217 bounded +2 evaluator tests PASS; M5-04 before/after13/13 exact; accepted
18metrics/29queries/QA36/M5-01 15cases giữ nguyên;3.818 protected hashes unchanged.
Implementation `ebea73076975acdd331f22ce6122d0c0aa48625d` đã push main, remote khớp.
[CI41466737325](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41466737325)
completed/SUCCESS đúng SHA; Python3.12/Web smoke SUCCESS, full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI cho SHA checkpoint.
Giữ Web local/D03-B10/financial_fact_verified=False; chưa M6.
Phiên nghiệm thu chỉ cập nhật planning và chạy planning checker/diff check; không
chạy lại tests/Gemini/benchmark/OCR hoặc sửa runtime/artifacts. Giữ claims chưa
verified và D03-B10 không thay đổi.
Next action: chờ Owner/Tech Lead giao task mới; không tự bắt đầu M5-06.

## M5-04 — Profitability Specialist

Status: **DONE**; Tech Lead APPROVED ngày02/11/2026, cho phép đồng bộ planning.
Không phát hiện P0/P1 mới cần sửa trước M5-05 trong phạm vi đã review.
Owner giao02/11/2026, baseline main/origin07a577f đã xác minh.
[Spec](tasks/M5/M5-04.md), [report](../docs/m5-04-profitability-specialist.md).
Profitability specialist/Gateway và per-candidate grounding, không verification M6.
Final offline13/13;21 focused PASS,199 bounded PASS trước focused fixes.
Initial live2/6, targeted4/4, tổng10calls/17.901tokens; không fresh6/6.
3 supported interpretations thật; Gross Margin2025=7,21%, full M4 lineage.
18metrics/29queries/QA36/M5-01 15cases exact; M5-02/M5-03 evidence giữ nguyên.
Evaluator ghi nhận3.379 protected hashes unchanged; Tech Lead chưa trực tiếp chạy
lại artifacts local. Giữ Web local/D03-B10 và financial_fact_verified=False.
Implementation `cf5b399d9fa65d071ff95753cde943c1c0013d05` đã push main;
[CI41461098831](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41461098831)
completed/SUCCESS đúng SHA, Python3.12/Web smoke SUCCESS;full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci]. Phiên nghiệm thu chỉ cập nhật planning
và chạy planning checker/diff check; không sửa runtime/artifacts hoặc gọi Gemini,
chạy lại tests/regression/benchmark. Giữ nguyên evidence implementation.
Next action: chờ Owner/Tech Lead giao task mới; không tự bắt đầu M5-05.

## M5-03 — Risk-Aware Supervisor

Status: **DONE**; Tech Lead APPROVED ngày02/11/2026, cho phép đồng bộ planning.
Owner giao02/11/2026, baseline main/origin03b7d23 đã xác minh.
[Spec](tasks/M5/M5-03.md), [report](../docs/m5-03-risk-aware-supervisor.md).
Supervisor/typed results/whitelist4 tools/internal operations, dependency/evidence
scheduler, risk/stops/budget và full M4 evidence propagation.19/19 scenarios:
13completed/3partial/3blocked; Gross Margin2025=7,21%; saved Gemini F01/F03/F04 đúng.
8 Supervisor+172 bounded tests PASS;18metrics/29queries/36pairs/QA36/M5-01 15cases/
D-06/D-07 exact;3.231 protected hashes unchanged,0 Gateway calls. Completion ở
`artifacts/evidence/M5-03-complete`, tái dùng19 traces đã thực thi cùng runtime,
không tính là executions mới. Implementation `1e43c2b0005d85b1905299761dcb462e55e1c692`
đã push main; [CI41421589655](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41421589655)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS;full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI trên cho SHA checkpoint.
Giữ Web local, D03-B10 và financial_fact_verified=False; không bắt đầu M5-04.
Phiên nghiệm thu chỉ planning/checker/diff; không sửa runtime hoặc chạy lại
Gemini/tests/benchmark/artifacts. Giữ nguyên evidence implementation.
Next action: chờ Owner/Tech Lead giao task mới; không tự bắt đầu M5-04.

## M5-02 — Evidence-Aware Query Planner

Status: **DONE**; Tech Lead APPROVED ngày02/11/2026, cho phép đồng bộ planning.
Owner giao02/11/2026,baseline main/origin `33a1f4e`.
[Spec](tasks/M5/M5-02.md),[report/examples](../docs/m5-02-evidence-aware-query-planner.md).
Gemini proposal → deterministic catalog/materializer → validate_plan, không execution.
Offline18/18; live14calls/59.428tokens:initial6/targeted2/fresh6. Fresh4/6;
fixed replay6/6,raw Gemini intent5/6; giữ làm baseline, không công bố Gemini live6/6.
197 focused +final13 Planner PASS; M4 36/18/29/36pairs/D-06/D-07 exact;
M5-01 giữ15cases. Evaluator ghi nhận2.701hashes unchanged; Tech Lead chưa chạy lại
artifacts trên môi trường local. Implementation `b5c7a02da82ed38378fbacd370b0a8734dd7fbf3` đã push main; [CI41414639830](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41414639830) SUCCESS đúng SHA (Python3.12/Web smoke SUCCESS; full regression SKIPPED).
Giữ Web local/D03-B10,không OCR/extraction;financial_fact_verified=False.
Phiên nghiệm thu chỉ planning/checker/diff; không sửa runtime hoặc chạy lại
Gemini/tests/benchmark/artifacts. Giữ nguyên evidence implementation.
Next action: chờ Owner/Tech Lead giao nhiệm vụ mới; không tự bắt đầu M5-03.

## M5-01 — Evidence Plan and Planner Contracts

Status: **DONE**; Tech Lead APPROVED ngày02/11/2026, cho phép đồng bộ planning.
Owner giao02/11/2026, baseline main/origin `ca9570d`.
[Spec](tasks/M5/M5-01.md),[report/example](../docs/m5-01-evidence-plan-contracts.md).
Public typed contracts, deferred bindings, combined DAG/selector validation và
read-only catalog preflight; chưa có agent runtime.35 M5/tổng131 targeted PASS;
15 real cases:10valid/4blocked/1invalid, BBS2021–2025/recovery2022;2.681 hashes
unchanged,zero Gateway/calculation calls. Ruff382/planning101/diff PASS.
Final implementation `adb4738bcb3024c79998f8695fe868d17a3cf61d` đã push main;
[CI41408676517](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41408676517)
completed/SUCCESS đúng SHA:Python3.12/Web smoke SUCCESS,full regression SKIPPED.
Scope cấp query/selector được gate dù step không lặp lại constraint; real case đúng.
Checkpoint sau docs-only [skip ci],không gán CI implementation cho SHA checkpoint.
M4-05/M4-05a DONE;giữ D03-B10/web local.
Phiên nghiệm thu chỉ planning/checker/diff; không sửa runtime, chạy lại tests,
benchmark hoặc Gemini/OCR. Giữ nguyên accepted evidence và Web local.
Next action: chờ Owner/Tech Lead giao task tiếp theo; không tự bắt đầu M5-02.

## M4-05a — Gemini Live Integration & QA Validation

Status: **DONE**,Tech Lead APPROVED ngày02/11/2026,cho phép đồng bộ planning;
không P0/P1 mới cần sửa trong phạm vi task. Baseline main/origin `6b5e05d`.
[Spec](tasks/M4/M4-05a.md),[report](../docs/m4-05a-gemini-live-validation.md).
Implementation `23faa718d952fc90682973fac485180c37b014d8` đã push main;local key0
hoạt động. Resolver/CLI và bounded semantic fallback/prompt
fix;30 focused PASS. Live5 câu giữ4answers đúng/grounded+negative đúng,ban đầu3/5;
9API attempts,8recorded success,1provider outcome unknown do writer bug đã sửa.
Known10.798tokens,total9 N/A;provider model gemini-3.5-flash-lite,không rotation.
Offline36/18metrics/29queries/36pairs/D-06/D-07/2.670hashes exact;live2.665hashes
unchanged. [CI41387830765](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41387830765)
attempt2 SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS;full regression SKIPPED.
Attempt1 Web PDF retry counter fail2/1,rerun failed jobs một lần PASS cùng SHA,
không sửa web. Checkpoint sau docs-only [skip ci],không gán CI cho SHA checkpoint.
QA baseline đã được nghiệm thu ở hai chế độ:deterministic36 câu/28answers đúng có
nguồn và Gemini live hiểu paraphrases,dispatch M4 tools,compose grounded answers.
Phiên nghiệm thu chỉ docs/planning và planning/diff checks;không gọi Gemini hoặc
chạy lại tests/regression/OCR/extraction. Giữ M4-05 DONE,D03-B10 BLOCKED và các
limitations/history đã báo;không sửa runtime/web/raw hoặc bắt đầu M5-01.
Next action: chờ Tech Lead gửi brief M5-01.

## M4-05 — Question Answering Baseline

Status: **DONE**, Tech Lead APPROVED ngày02/11/2026,cho phép đồng bộ planning,
không cần sửa thêm. Owner giao02/11/2026; baseline main/origin `eca8cc8`.
[Spec](tasks/M4/M4-05.md), [report](../docs/m4-05-qa-baseline.md).
QA API/rules/optional một Gateway call/dispatcher/composer/CLI;193 targeted PASS.
Final36 câu:28 answered đúng/grounded,6 abstained/unsupported,2 clarification;
intent/tools36/36.18 metrics/29 queries/36 pairs/D-06/D-07/inventory giữ nguyên,
2.670 protected hashes unchanged;zero Gateway,live Gemini NOT RUN vì thiếu process
credentials/live configuration. Implementation `359babb9dcfbf40275ef693399c5bdf204aea150`
đã push main, origin khớp;
[CI41384217552](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41384217552)
completed/SUCCESS đúng SHA;Python3.12 và Web smoke/typecheck/lint/build/browser
SUCCESS,full unit regression SKIPPED theo workflow. Checkpoint sau chỉ docs/planning
[skip ci],không gán CI implementation cho SHA checkpoint.
**M4 hoàn tất trong phạm vi phê duyệt**:Financial Retrieval,Calculator,Evidence
Retrieval và QA Baseline đã triển khai/kiểm thử trên dữ liệu thật.
D03-B10 vẫn BLOCKED đối với so sánh liên tài liệu. Phiên nghiệm thu chỉ docs/planning
và planning/diff checks;không sửa runtime hoặc chạy lại tests/benchmark/Gemini/OCR.
Giữ local web/next-env.d.ts. M5-01 là task tiếp theo của M5;Tech Lead xác nhận sẽ
gửi brief riêng,giữ TODO,chưa soạn spec hoặc bắt đầu implementation.
Next action: chờ Tech Lead gửi brief M5-01 — Evidence Plan and Planner Contracts.

## M4-04 — Evidence Retrieval Tools

Status: **DONE**; Tech Lead APPROVED ngày 02/11/2026, cho phép đồng bộ planning.
Owner giao 02/11/2026, baseline main749d37f.
[Spec](tasks/M4/M4-04.md), [report](../docs/m4-04-evidence-retrieval-tools.md).
Năm typed read-only tools;203 focused PASS;real139 text/24 tables/2.973 anchors/
18 lineages exact.18 accepted executions/arithmetic/restart exact;25 priority sources.
M3 get_sources sửa false-found khi thiếu reference/image hoặc sai binding;
2.087 fact sources/163 evidence sources/29 queries/7 real negative controls PASS.
15+3 eligibility/36 pairs/D-07 scopes/D-06 QA09/QA15 giữ nguyên;
2.657 protected hashes unchanged,zero Gateway. Implementation
`304da3a6a95873acd88fc3b49a5fd0268e07653f` và format fix
`a36493b60834c32b5629f23dc4bfa0062359db01` đã push main;
[CI41381388861](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41381388861)
completed/SUCCESS đúng fix SHA,Python3.12 lint/format/planning/focused tests SUCCESS;
Web smoke/full regression SKIPPED. Giữ web local;không P0/P1 còn mở trong phạm vi
kiểm tra. Checkpoint sau chỉ docs/planning,không gán CI fix cho SHA checkpoint.
Phiên nghiệm thu chỉ docs/planning và planning/diff checks; không chạy lại tests,
evaluation/Gemini/OCR/extraction hoặc sửa runtime/evidence/web. Web smoke/full
regression SKIPPED theo workflow, không phải failure; không P0/P1 mới cần sửa.
D03-B10 giữ BLOCKED đối với so sánh liên tài liệu.
Next action: chờ Owner/Tech Lead giao task tiếp theo; không tự bắt đầu M4-05.

## M4-03 — Calculator and Formula Executor

Status: **DONE**; Tech Lead APPROVED ngày02/11/2026, cho phép đồng bộ planning.
Owner giao02/11/2026, baseline main f433777.
[Spec](tasks/M4/M4-03.md), [report](../docs/m4-03-calculator-executor.md).
Public FinancialCalculator qua M4-02 retrieval/M4-01 production closure;
Decimal34/HALF_EVEN/final0.01, result/trace riêng, original DerivedMetric bất biến.
186 focused PASS;real18 computed (6 mỗi formula),independent18/restart exact,
3 real negative controls;2.087 facts/18 retrievals/41 cases/15+3 eligibility/29 queries/
36 undetermined pairs/5 D-07 scopes/D-06 QA09/QA15 PASS;2.641 hashes unchanged,
zero Gateway/Gemini/OCR/extraction. D03-B03 DONE trong phạm vi production formula
executor. D03-B10 vẫn BLOCKED đối với so sánh liên tài liệu; không ảnh hưởng các
phép tính cùng filing đã phê duyệt.
Implementation `fd2ef5c27001a22b70760d52919abd096281aefd` đã push main;
[CI41377619691](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41377619691)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS; full regression SKIPPED.
Phiên nghiệm thu chỉ docs/planning và planning/diff checks,không gán CI trên cho
SHA checkpoint. Giữ runtime/web local/accepted evidence; không chạy lại tests,
evaluation/Gemini/OCR hoặc bắt đầu task mới.
Next action: chờ Owner/Tech Lead giao task tiếp theo; không tự bắt đầu M4-04.

## M4-02 — Typed Financial Retrieval Tools

Status: **DONE**; Tech Lead nghiệm thu ngày02/11/2026 và cho phép đồng bộ planning.
Owner giao02/11/2026, baseline075222a; accepted correction3dba041.
[Spec](tasks/M4/M4-02.md), [report](../docs/m4-02-financial-retrieval-tools.md).
Bốn typed tools,145 focused PASS;real2.087 exact facts/40 cases/18 metrics;
15+3 eligible/computed0;29 queries/36 pairs/5 scopes/QA09/QA15 không regression.
2.626 input hashes unchanged,zero Gateway. Implementation
`3ac01c02ef1ba6d713bf67706ade436da3ebb97f` đã push main;
[CI41373589020](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41373589020)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS.
Giữ web local và accepted artifacts;không executor hoặc M3 runtime changes.
Review correction:partial scope coverage không chặn found khi có valid match;
conflicting evidence/snapshot selection giữ fail-closed.146 focused PASS và một
real BBS regression found/1 original2024/four unresolved;2.626 hashes unchanged.
Fix `3dba041bcc61b41cec92b04d950212805d78a45e` đã push main;
[CI41375092119](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41375092119)
completed/SUCCESS đúng fix SHA,Python3.12/Web smoke SUCCESS;
không chạy lại baseline real acceptance.
Phiên chốt DONE chỉ cập nhật planning và chạy planning/diff checks; giữ nguyên
code/evidence/web local, không chạy lại tests/evaluation/Gemini hoặc bắt đầu task mới.
Next action: chờ Owner/Tech Lead giao M4-03; không tự bắt đầu.

## D-07 — Reporting Scope Source Resolution

Status: **DONE**, Tech Lead nghiệm thu ngày02/11/2026:đạt mục tiêu điều tra và sửa
lỗi xác định được; [spec](tasks/D/D-07.md).
Baseline mainf0b4328e68597b0ff37760ffe2507203c4c19e51;giữ web local.
Kiểm tra5 PDFs/cache,source-backed scope hoặc insufficient với reason cụ thể;
không đổi M4-01 policies hoặc mở cross-document execution. Original2024 PDFp1
selected BCTC riêng,scope overlay resolve/restart;2021/2022/2023/2025 insufficient,
giữNone. Generic Raw OCR checkbox adapter/selected-option resolver và SnapshotCatalog
scope lookup;273 focused PASS. Real133 cached pages/38 direct pages,15+3 closures/
lineages và36 pairs/29 queries exact,2.573 hashes unchanged,zero Gateway.
B10 giải quyết một phần,còn BLOCKED với cross-document vì thiếu nguồn bốn filings.
[Report](../docs/d07-reporting-scope-resolution.md). Implementation cuối
`54663b92cc7881a63c37b68729d0749998963522` đã push main;
[CI41370688198](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41370688198)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS. Final read-only fix/five
scope views exact;Ruff350/planning100/diff PASS. B10 giữ BLOCKED một phần;
không audit lặp bốn PDF2021/2022/2023/2025,không cho phép so sánh liên tài liệu
khi thiếu điều kiện tương thích. Phiên nghiệm thu chỉ planning/Blocker Registry và
planning/diff checks;giữ runtime/report/artifacts/web local,không chạy lại tests/
evaluation/Gemini hoặc tự bắt đầu M4-02.
Next action: chờ Owner/Tech Lead giao task tiếp theo.

## M4-01 — Execution Compatibility, Formula Approvals & Tool Contracts

Status: **DONE**, Tech Lead APPROVED ngày02/11/2026, cho phép đồng bộ planning;
accepted implementation `49e793eb82b60b1fd22108cac472f094a91f184c`.
[Spec](tasks/M4/M4-01.md). Baseline main8bddff4; profile
M4/same-document-execution-v1 và ba formula semantics được duyệt; giữ web local.
246 focused PASS;final real original15/recovery3 eligible,global18 undetermined,
computed0;29 queries/36 pairs/QA09/QA15/D-06 exact,2.545 hashes unchanged,zero Gateway.
Ruff345/planning99/diff PASS. Implementation
`49e793eb82b60b1fd22108cac472f094a91f184c` đã push main;
[CI41365782993](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41365782993)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS. [Policy/report](../docs/m4-01-execution-policy.md),
ignored evidence M4-01/verified. B01/B02 DONE trong phạm vi execution eligibility;
B03 thuộc M4-03,B10 UNKNOWN,ưu tiên điều tra PDF trước phát triển so sánh liên tài liệu.
Computed0 chưa numeric PASS. Phiên nghiệm thu chỉ planning/Blocker Registry và
planning/diff checks;không chạy lại tests/evaluation/Gemini hoặc sửa runtime/artifacts,
giữ web local. Không tự bắt đầu M4-02/M4-03 hoặc điều tra PDF.
Next action: chờ Owner/Tech Lead giao task tiếp theo.

## D-06 — Canonical Mapping & Financial Validation Fix

Status: **DONE**, Tech Lead nghiệm thu theo xác nhận Owner 01/11/2026;
[spec](tasks/D/D-06.md), [report](../docs/d06-canonical-mapping-validation.md).
Baseline main004957b; implementation `7cc4dec9e8afb381e386b5b1fd2f1b2431928a01`
đã push main; [CI41319706092](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41319706092)
completed/SUCCESS đúng SHA,Python3.12/Web smoke SUCCESS. Checkpoint sau chỉ docs.
Generic catalog
16→24 IDs, corrected D-06/mapping-v2.1 parent D-05/corrected-v1 riêng:910 slots,
mapped160→240 (+80;73 numeric/11 quality-blocked),unmapped670/71 code pairs.
QA09 found đúng2024-12-31/source; QA15 assets=L+E và assets=funding residual0.
100 checks:65 consistent/35 insufficient,8 rules thực sự tính;B01 cả5 filings.
322 focused PASS;baseline15/recovery3,graph/18 lineages/29 queries/36 pairs exact,
1.177 exact accepted lookups. 2.506 input hashes unchanged,zero Gateway.
Giữ10 EPS per-share/5 corrections/terminal coverage;new snapshots không tự ready,
không trộn D-04 recovery2022,không mở M4/scope/cross-year gates. B05/B11 DONE
trong phạm vi tám items/shared validation;670 slots ngoài scope giữ unmapped.
Checkpoint nghiệm thu chỉ planning/Blocker Registry và planning/diff checks;
không chạy lại tests/Gemini/OCR/extraction/evaluation;giữ report/artifacts và web local.
Next action: chờ Owner giao task tiếp theo;không tự bắt đầu M4 hoặc corrective task khác.

## D-05 — Extraction Completeness & Data Corrections

Status: **DONE**, Tech Lead nghiệm thu ngày 01/11/2026; [spec](tasks/D/D-05.md),
[report](../docs/d05-extraction-corrections.md). Implementation
`401c12a4f5172e186b820252c6bcce9adb47d9df` đã commit/push trực tiếp main;
[CI41316310651](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41316310651)
completed/SUCCESS đúng SHA, Python3.12/Web smoke SUCCESS. Baseline `53a7836`;
checkpoint sau chỉ docs/planning. Generic completeness/roles/
numeric-token issues/basic EPS units, immutable source-backed overlays. Real
981 original giữ nguyên; corrected910, bỏ73 structural/note và thêm2 EPS;
5 raw corrections/7 exact SourceReviews. Coverage rows_missing→covered;
baseline15/15 và D-04 recovery3/3, graph/15 lineages exact;2.457 hashes unchanged.
243 focused PASS sau hai generic review fixes;20 cached pages/18 lineages exact,
39 D-05 files unchanged;Ruff/planning98/diff PASS. Lượt chuẩn bị review zero Gateway;
implementation trước có một attempt/5.966 tokens đúng target page, không full-PDF accuracy/
restatement approval. B06 DONE cho classification/projection; B07 DONE cho targeted
EPS recovery/generic completeness; B14 DONE cho source-backed correction; B15 DONE
cho basic EPS semantic unit. Diluted EPS/cases thiếu bằng chứng vẫn uncertainty.
Phiên đồng bộ nghiệm thu chỉ planning/Blocker Registry và planning/diff checks;
không chạy lại tests/Gemini/OCR/extraction/evaluation. Giữ web local và evidence.
Next action: chờ Owner/Tech Lead giao task tiếp theo; không tự bắt đầu D-06/M4.

## D-04 — Snapshot & Source Closure Fix

Status: **DONE**, Tech Lead nghiệm thu 01/11/2026 theo chỉ đạo Owner;
[spec](tasks/D/D-04.md),
[report](../docs/d04-snapshot-source-closure.md). Generic catalog/closure,
exact SourceReview lookup và optional lineage overlay; arbitrary parent chains,
explicit selection, không auto-inherit/merge/latest. Local122 focused PASS gồm18
generic controls/hai synthetic documents. Real BBS recovery3/3,6/6 operands,
baseline15/15;32 reviews exact;15 baseline lineages/29 queries/36 pairs unchanged;
persisted restart exact;eligible0. 2,437 input hashes unchanged,zero Gateway.
Implementation `73e2f9e9cc412dc86a2dbf7e45903d8a6449d5dd` đã push main;
[CI41311527741](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41311527741)
completed/SUCCESS đúng SHA, Python3.12/Web smoke SUCCESS; checkpoint sau chỉ docs.
Ruff toàn repository/planning97/diff PASS. Giữ web/next-env.d.ts.
Không suy full-PDF/other-company accuracy; D03-B04 DONE, D03-B08 DONE trong phạm vi
typed review lookup/lineage overlay; các blockers khác giữ nguyên. Checkpoint nghiệm
thu chỉ planning/Blocker Registry và planning/diff checks; không chạy lại tests,
Gemini/OCR/extraction hoặc evaluation, không gán CI implementation cho SHA checkpoint.
Next action: chờ Owner/Tech Lead giao task tiếp theo; không tự bắt đầu D-05/M4.

## D-03 — System-Wide Blocker Root Cause Investigation & Resolution Plan

Status: **DONE**, Tech Lead APPROVED ngày 31/10/2026 theo chỉ đạo nghiệm thu;
[spec](tasks/D/D-03.md), [audit/registry](../docs/d03-system-blocker-audit.md).
16 mục:14 confirmed/1 probable/1 unknown, P0=0/P1=12/P2=4;15 mở/1 đã recovery D-02.
20 QA cases:8 answer-data-with-caveat/12 bị chặn ở bước cụ thể. Snapshot recovery2022
chưa khép kín reviews/basis/metrics; EPS2024 bị bỏ dòng, EPS restatement có nguồn
PDF2025:23; Web chưa bridge canonical. M4 NO-GO execution-ready, minimum decisions
và corrective groups đã đề xuất. Diagnostic981 exact/36 pairs exact;5 targeted PASS,
2,421 hashes unchanged,zero Gemini. Implementation `e11821b153871f34b44bcbd7ea08293aafe4b039`
đã push main; [CI41211560836](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41211560836)
completed/SUCCESS đúng SHA, Python3.12 SUCCESS/Web smoke SKIPPED; checkpoint sau chỉ docs.
Phiên nghiệm thu chỉ planning/diff checks, không chạy lại diagnostics/tests/Gemini;
giữ nguyên report/blocker registry/stable IDs và web/next-env.d.ts. Owner cho đồng bộ
D-02 DONE vì đã được Tech Lead nghiệm thu ở lượt trước; không mở execution gates.
Next action: chờ Owner/Tech Lead giao corrective task theo D-03; không tự bắt đầu M4.

## D-02 — Blocker Resolution & Analytical Readiness

Status: **DONE**, Tech Lead đã nghiệm thu final fix; Owner xác nhận đồng bộ planning
ngày 31/10/2026 cùng nghiệm thu D-03; accepted implementation
`f80b84254765d9a5e73208e80f8fb7c577b72668` đã push main.
[CI41208806188](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41208806188)
completed/SUCCESS đúng SHA, Python 3.12/Web smoke SUCCESS; checkpoint sau chỉ docs.
[Spec](tasks/D/D-02.md), [report](../docs/d02-blocker-resolution.md).
Approved preparation-ready **0/15 → 15/15** theo document-statement-v1;
global15 undetermined, calculation eligible0. Ba formula definitions/draft có
preflight/negative controls, execution approvals rỗng. Signing date overlay riêng.
36 cross-year pairs vẫn undetermined;29 queries exact với D-02 (23 available,
4 ambiguous/1 mapping gap/1 absent snapshot).981 exact retrieval/15 lineages exact.
124 focused/core PASS;zero Gemini/tokens;2,406 input hashes giữ nguyên, web local giữ.
Phiên đồng bộ chỉ planning/diff checks, không chạy lại tests/diagnostics/Gemini;
giữ nguyên limitations/blockers, chưa execution approval hoặc full-PDF accuracy.
Next action: chờ Owner/Tech Lead giao corrective task theo D-03; không tự bắt đầu M4.

## D-01 — BBS Multi-Year Canonical Coverage & Analytical Readiness

Status: **DONE**; Tech Lead APPROVED ngày 30/10/2026, main-first,
accepted implementation `0f2ca6124cd4a4c994f38c32557d3f9b88f42e7c`.
Giữ local web/next-env.d.ts và artifacts ngoài commit.
[Spec/evidence](tasks/D/D-01.md), [report](../docs/d01-multi-year-readiness.md).
Năm PDFs/133 pages inventory; 109 pages discovery và 16 primary + 4 fallback
extraction pages mới, reuse 2025. 981 observations/165 mapped; exact retrieval và
restart PASS. 119 targeted PASS; 48 cells khớp mẫu PDF, chưa full-PDF accuracy.
29 queries: 22 available/1 quality blocked/4 ambiguous/1 mapping gap/1 source limit.
15 metrics complete nhưng undetermined (scope/provenance), không executor.
129 Gemini attempts/260,593 known tokens/4 provider errors; 173 unique input hashes
unchanged. Implementation `0f2ca6124cd4a4c994f38c32557d3f9b88f42e7c` đã push main;
CI41064083725 completed/SUCCESS đúng SHA, Python 3.12/Web smoke SUCCESS.
Phiên nghiệm thu chỉ cập nhật planning và chạy planning/diff checks; không chạy lại
tests/Gemini/OCR/extraction hoặc real evaluation. Giữ nguyên các limitations đã báo.
Next action: chờ giao nhiệm vụ mới; không bắt đầu M4-01.

## M3-07 — Evidence Retrieval Interface

Status: **DONE**, Tech Lead APPROVED ngày 30/10/2026 theo chỉ đạo nghiệm thu;
accepted implementation
`e8f293de4445f91860ff8820f123502da649d2e6` đã push main, origin/main khớp.
Unified typed retrieval/citations giữ original M2 quality/provenance.
102 focused/regression PASS; Ruff toàn repository/planning/diff PASS.
Real 356/356 exact, 18/18 fixed queries PASS; 292 display có caveat/64 blocked.
14 questions: 9 complete/3 partial-quality-blocked/2 canonical-unavailable.
JSON restart exact, 172 hashes unchanged; zero Gemini/OCR/extraction/raw changes.
[Spec/evidence](tasks/M3/M3-07.md), [API/report](../docs/evidence-retrieval.md).
[CI41056561499](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41056561499)
completed/SUCCESS đúng implementation SHA; Python 3.12 và Web smoke đều SUCCESS.
Checkpoint sau implementation chỉ docs/planning, không gán CI cho SHA checkpoint.
Phạm vi nghiệm thu là unified evidence retrieval; chưa financial accuracy toàn PDF,
formula execution hoặc historical canonical coverage. Phiên chuyển DONE chỉ cập nhật
planning và chạy planning/diff checks; không refactor, mở rộng tests hoặc chạy lại
test suite/real evaluation/Gemini/OCR/extraction. Giữ local web/next-env.d.ts.
Next action: chờ giao nhiệm vụ mới; không bắt đầu M4-01.

## M3-06 — Calculation Lineage

Status: **DONE**, Tech Lead APPROVED ngày 30/10/2026 theo chỉ đạo nghiệm thu,
main-first; accepted implementation
`5300bcff4b49371dcaa5278b444a100b3beeec9a` đã push main, origin/main khớp sau push.
[Spec/evidence](tasks/M3/M3-06.md),
[API/inventory/real report/policy proposal](../docs/calculation-lineage.md).
68 targeted PASS; sáu persisted metrics: 4 complete/2 partial, 10/12 roles resolve,
98 anchor occurrences, 10/10 original quality/context preserved; 6 undetermined.
PDF năm 2021 tên BB2_2021.pdf; cả năm PDF mở được, scan/no text layer.
2021–2024 có OCR nhưng chưa canonical financial facts; current scope chỉ có annual
periods 2024/2025 từ report 2025, chưa multi-year evaluation PASS. Final runner:
171 input hashes unchanged, restart exact; zero Gemini/OCR/extraction calls.
Không executor/compatibility-policy changes; giữ local web/next-env.d.ts ngoài stage.
CI41053294032 của implementation FAILURE do Ruff formatting code fence trong docs.
Tech Lead independent review xác nhận chức năng lineage đạt phạm vi M3-06.
Formatting fix `c91cecae099a58124c36ccfad9d65bd9be0faf04` đã push trực tiếp main;
[CI41054170265](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41054170265)
SUCCESS đúng fix SHA: Python 3.12 lint/format/planning/focused offline tests đạt,
Web smoke skipped vì docs-only. Local Ruff format/check toàn repository,
planning checker và diff check PASS. Không chạy lại real-artifact evaluation,
Gemini/OCR/extraction hoặc sửa code lineage/raw/M3 results; web local hash giữ nguyên.
Phạm vi nghiệm thu: lineage và evidence-quality context, chưa formula execution
hoặc financial accuracy toàn PDF/multi-year. Phiên chốt DONE chỉ planning/diff
checks, không chạy lại tests/pipeline/Gemini/OCR/extraction hoặc sửa dữ liệu.
Next action: chờ giao nhiệm vụ mới; không bắt đầu M3-07.

## M3-05 — Derived Metric Records

Status: **DONE**, Tech Lead APPROVED ngày 29/10/2026, main-first; accepted implementation
`a4c8ff7b6265180b35906098af12c1b0447138f2` đã push main, origin/main khớp sau push.
[Spec/evidence](tasks/M3/M3-05.md), [API](../docs/derived-metrics.md),
[real report](../docs/m3-05-real-readiness.md). DerivedMetric/formula/operand contracts,
DerivedMetricNode/used_in; reuse compatibility, không executor hoặc quality propagation.
47 targeted PASS; hai W-07 attempts/356 facts tạo 6 metrics/10 used_in, 4 complete và
2 incomplete; cả 6 undetermined. Company/scope/roles/context/source còn unresolved,
liabilities thiếu canonical mapping. M2 insufficient của storage B02 giữ nguyên.
Metadata auto-accepted chưa user-confirmed; không policy name→company_id, scope/roles
thiếu; 0 bindings applied, before=after. JSON restart exact, 49 source hashes unchanged.
Không Gemini/OCR/extraction/raw changes; giữ local web/next-env.d.ts ngoài stage.
[CI40837854096](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40837854096)
completed/SUCCESS đúng implementation SHA đã xác minh (Python 3.12 và Web smoke).
Phạm vi nghiệm thu: Derived Metric Representation, chưa phải khả năng tính toán
tài chính hoàn chỉnh. Phiên nghiệm thu chỉ cập nhật planning và chạy planning/diff
checks; không chạy lại tests/Gemini/OCR/extraction hoặc sửa raw.
Next action: chờ giao nhiệm vụ mới; không bắt đầu M3-06.

## M3-04 — EF-EG Nodes and Edges

Status: **DONE**, Tech Lead APPROVED ngày 29/10/2026, main-first.
[Spec/evidence](tasks/M3/M3-04.md), [API](../docs/typed-evidence-graph.md),
[real-artifact report](../docs/m3-04-real-graph-validation.md).
Đã khắc phục CHANGES REQUESTED: status cũ gộp structural với uncertainty/context.
Correction tách status/reasons structural, grounding metadata và evidence_context
giữ nguyên M2 quality/resolution issues. Cùng selected scope hai W07 attempts/bốn
M3-03 repositories: 356 facts + 99 evidence; 1747 nodes/7407 edges structural valid,
zero invalid/unresolved trong indexed graph. 1299 anchors vẫn page/uncertain;
7 missing identities giữ quarantine, zero orphan/collision/binding conflict.
Direct display có caveat 292/356, blocked64; gross-margin readiness2 pairs đều
undetermined do thiếu company/scope/semantic roles và uncertain source; không tính.
M2 direct_qa decisions giữ 46 usable/246 caveat/64 insufficient/0 conflicted.
1299 selectors resolve/page binding đúng, 53 hashes unchanged; 10/10 controls giữ
status/reasons. B09 graph/full-PDF accuracy NOT VERIFIED, không semantic support.
Accepted implementation `76fa534f4bd82a8fc615091af2fd79b8ef99ded6` đã push trực tiếp main,
HEAD/origin/main khớp sau push. Local56 targeted/Ruff/planning/diff PASS;
[CI40835632968](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40835632968)
completed/SUCCESS đúng accepted SHA đã xác minh.
Zero Gemini/OCR/extraction/raw changes.
Phiên nghiệm thu chỉ planning/diff checks; không chạy lại tests/runtime/Gemini/OCR.
Giữ local web/next-env.d.ts ngoài stage và mọi limitations đã báo.
Next action: chờ giao nhiệm vụ mới; không bắt đầu M3-05.

## M3-03 — Text and Table Evidence

Status: **DONE**, Tech Lead APPROVED ngày 29/10/2026, main-first. Accepted implementation
`3fca2b4ccba922c688acfc404477e655024dcb44` đã push trực tiếp main.
[Spec/evidence](tasks/M3/M3-03.md), [API/coverage](../docs/text-table-evidence.md).
Models/adapters DU/unified/W-04 payload, local JSON riêng và exact source association.
40 targeted PASS (8 M3-03 + 32 compatibility); persisted BBS_2025 24 text/4 tables,
19 headers/417 cells, 178 facts có associations (150 unmapped), restart/idempotence
và canonical-facts/source hash unchanged PASS. Mọi reference smoke vẫn page-level.
Validation bổ sung: [real-artifact report](../docs/m3-03-real-evidence-validation.md).
99/99 records từ hai M1-16 exports và hai W-07 attempts exact preservation/restart;
7 missing document binding giữ quarantine. PDF B01/B02/B03/B09 đã đọc trực tiếp:
72/72 numeric token occurrences khớp mẫu, 6/72 period bindings unresolved;
B09 2/21 glyph mismatch,5/21 null; không full-PDF/independent human gold accuracy.
13/13 PDF/image/dimension bindings khớp;49 source hashes unchanged. Validation bổ sung
`b12eebe299e40c766031b011943bd506c44e3414` đã push main;
[CI40832246367](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40832246367)
completed/SUCCESS đúng accepted validation SHA đã xác minh. DU v1 còn synthetic;
BBS_2024 coverage chưa xác minh.
Zero Gemini/OCR/extraction/raw changes; giữ local web/next-env.d.ts ngoài stage.
[CI40830297216](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40830297216)
completed/SUCCESS đúng runtime SHA đã xác minh. Ruff/planning/diff PASS local trước đó;
smoke không chứng minh financial accuracy.
Phiên nghiệm thu chỉ cập nhật planning và chạy planning/diff checks; không chạy lại
tests/Gemini/OCR/extraction. Giữ nguyên limitations, không nâng thành financial accuracy.
Next action: chờ giao nhiệm vụ mới; không bắt đầu M3-04.

## M3-02 — Canonical Financial Facts

Status: **DONE** — Tech Lead APPROVED ngày 29/10/2026, main-first.
[Spec/evidence](tasks/M3/M3-02.md); adapter M2 và local JSON repository implemented,
43 targeted tests PASS; persisted 178 observations restart round-trip PASS,
Ruff/planning/diff PASS. Implementation `8471064820b681aef403d7bc784a627a0f5f5bda`
đã push main; [CI40828484743](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40828484743)
completed/SUCCESS đúng SHA đã xác minh (Python 3.12 và Web smoke).
Documentation checkpoint `12bfa8a`; phiên nghiệm thu chỉ planning/diff checks,
không chạy lại tests/build/Gemini/extraction hoặc benchmark.
Giữ local web/next-env.d.ts; không Gemini/extraction hoặc sửa raw.
Next action: chờ giao nhiệm vụ mới; không bắt đầu M3-03.

W-03 DONE — Tech Lead APPROVED ngày 29/10/2026, engineering scope. PR #1/#2/#3
đã merge main; CI40718128314/refinement7048d92 và CI40791847627/launcherd8e7026
SUCCESS đã có. Live Gemini synthetic PASS, chưa đánh giá accuracy trên PDF
BBS_2025 thực tế tại checkpoint W-03; W-04 được giao mới bên dưới.

## M3-01 — Canonical and Provenance Contracts

Status: **DONE** — Tech Lead APPROVED code/contracts/phạm vi nghiên cứu ngày29/10/2026.
[Spec/evidence](tasks/M3/M3-01.md). Implementation sau fix provenance
`b1ed933425647b6bab6230175055580d75ef7f58`;
[CI40827007004](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40827007004)
completed/SUCCESS đúng SHA đã xác minh (Python 3.12 và Web smoke).
[PR #10](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/10)
MERGED main tại `fe664ba4b82a5712e367471ee6f7ceb3a0c46b06`; local main đã đồng bộ.
20 focused tests PASS sau fix; không chạy lại tests/build/Gemini/extraction hoặc
benchmark trong phiên nghiệm thu. Housekeeping chỉ planning/diff, không runtime/raw changes.
Giữ hai observations 2024 cross-document; consistency/compatibility không xác minh số liệu.
Next action: chờ giao nhiệm vụ mới; M3-02 vẫn TODO, chưa bắt đầu.

## M3 Preflight — Research Alignment (checkpoint trước)

Status: **DONE** — Tech Lead APPROVED ngày 29/10/2026 tại `18ff8e0`;
[PR #9](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/9)
đã MERGED vào main tại `0ac2b98471ba99a49d2a18c2fe14055a5ab3e65a`.
Xem [registry](tasks.md#registry) và
[decision](decisions.md#2026-10-29--m3-preflight-research-alignment).
Chỉ đồng bộ tài liệu typed EF-EG/semantic compatibility/quality propagation;
M3-01–M3-07 giữ TODO, chưa bắt đầu implementation. Planning checker và diff check
PASS tại preflight; không suy CI từ W-07. Phiên nghiệm thu chỉ planning/diff,
không chạy tests/build/Gemini/benchmark hoặc đổi runtime/schema.
Next action: chờ Tech Lead giao việc; không bắt đầu M3-01.

## W-07 — End-to-End Acceptance

Status: **DONE** — Tech Lead APPROVED 29/10/2026 trên
[PR #8](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/8).
Web Demo V1 **COMPLETED — CONDITIONAL GO (local research demo)**; W-01–W-07 DONE.
Implementation `c65cef2616ad548e6cb2c12c10e5848c8533172f`;
[CI40821580233](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40821580233)
SUCCESS đúng SHA. BBS persisted và một fresh live browser run PASS, 30 Gemini calls;
178 observations/163 numeric; restart đọc lại 0 calls. 45 backend + 11 Playwright
PASS, typecheck/lint/build/Ruff/planning đạt. Không phát hiện P0/P1 cần sửa runtime.
Chưa đánh giá accuracy toàn PDF/multi-document, chưa verified financial facts;
IDM chưa xác nhận trên browser người dùng; live phụ thuộc Gemini Free Tier.
[Evidence](tasks/W/W-07.md). Phiên chốt trạng thái không chạy lại tests/Gemini,
fresh extraction hoặc benchmark.
Next action: chờ chỉ đạo tiếp theo; không bắt đầu M3 hoặc task mới.

## W-06 — Financial Evidence Tables & Source Linking

Status: **DONE** — Tech Lead APPROVED Engineering Scope 29/10/2026 trên
[PR #7](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/7).
Implementation `b5de0a2d5e1c3305dff335ce1f771e9b27814300`;
[CI40805486808](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40805486808)
SUCCESS đúng SHA đã xác minh. BBS_2025 178 observations, source linking B01/B02/B03
PASS; zero/precision/conflict chỉ synthetic, chưa accuracy toàn báo cáo.
[Evidence](tasks/W/W-06.md). Phiên nghiệm thu không chạy lại tests/Gemini/extraction/benchmark.
Next action: chờ chỉ đạo tiếp theo; không bắt đầu W-07.

## W-05 — PDF Viewer & Page Navigation

Status: **DONE** — Tech Lead APPROVED Engineering Scope 29/10/2026 trên
[PR #6](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/6).
Implementation `705d07f90591ce0880a6d9d9b470c74273a9e14e`; refinements
`41ce4f2bd7fd686c14e9021a39b569b267479c95`, `5fb03cd5a6a669291dc52583bfcd0ac658075c73`.
[CI40801877913](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40801877913)
SUCCESS đúng 5fb03cd đã xác minh; BBS_2025 viewer PASS. [Evidence](tasks/W/W-05.md).
IDM chưa xác nhận giải quyết trên trình duyệt người dùng; inventory cần reload;
chưa có financial cell linking. Phiên nghiệm thu không chạy lại tests/CI/Gemini/extraction.
Next action: chờ chỉ đạo tiếp theo; không bắt đầu W-06.

## W-04 — Financial Processing Sessions

Status: **DONE** — Tech Lead APPROVED Engineering Scope 29/10/2026;
implementation `ff10062b26bd311123b19c9c65d17949679729df`,
[PR #5](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/5)
đã MERGED vào main tại `00f77351cfaf14389a78b5d9d08581c217e8cced`, local main đã đồng bộ. Người dùng giao task và cho
phép commit/push/PR trên `feat/w-04-processing-sessions`; baseline `4de9948`,
main khớp origin/main và Lean đã merge qua PR #4.
Sessions/API/UI đã nối runtime M1–M2. Live BBS_2025 24 trang, 29 calls, 178 evidence;
mẫu PDF/reference 6/6 khớp, không phải accuracy toàn PDF. [Evidence](tasks/W/W-04.md).
CI40797755852 SUCCESS đúng ff10062: Python 18 PASS, desktop browser 3 PASS;
lint/format/planning/typecheck/build PASS. Checkpoint sau chỉ tài liệu [skip ci].
Chưa đánh giá accuracy toàn báo cáo/chưa verified financial facts.
Next action: chờ chỉ đạo tiếp theo; không bắt đầu W-05.

## Housekeeping — Research MVP Workflow Simplification

Status: **REVIEW**. Implementation SHA: `cd2783e35cc5ddd5ac12b695e7e53739d2bf8248`;
baseline main `e69a837`. Nhánh `chore/research-mvp-lean`; commit sau implementation
chỉ ghi checkpoint này. PR/CI remote xem PR cùng nhánh, không gán CI cho SHA khác.
Đã cập nhật AGENTS, task template và quy tắc registry theo Research-First,
Minimal Engineering, Low Codex Quota. Giữ provenance, secrets, storage boundaries,
giới hạn upload/request, Gateway/ngân sách và quyền Tech Lead nghiệm thu.
CI mặc định Python 3.12: Ruff/planning và unit tests trọng tâm offline;
typecheck/lint/build + ba browser smoke desktop khi web/backend/dependencies/CI
thay đổi. Docs-only bỏ qua web; full unit/browser regression qua workflow_dispatch
với `full_regression=true`, không xóa suites hoặc validations hiện có.
Validation local: YAML/kiểu input/điều kiện cấu trúc CI và Bash syntax PASS;
planning checker PASS (89 tasks); nhóm CI offline 15 PASS trong `.venv`;
diff check PASS. Python hệ thống thiếu package nên collection ban đầu lỗi;
đã dùng đúng `.venv` và PASS. Không chạy lại W-03/full regression/benchmark/live.
CI remote chưa chạy tại checkpoint này; kết quả sẽ ở PR, không suy từ local.
Next action: Tech Lead review PR housekeeping; không bắt đầu W-04.

## Checkpoint trước housekeeping

Housekeeping sau W-03 được người dùng giao: PR #1→#2→#3 đã MERGED vào main,
không conflict/force push/xóa branch. Merge SHA lần lượt167e8fa/cb9efeb/6dd0d1d;
CI main sau từng merge SUCCESS. PR#1 cần backport formatting fence5779d45 đã
CI PASS trước merge. W-01/W-02/W-03 DONE; W-03 được Tech Lead nghiệm thu29/10,
engineering scope. Không bắt đầu W-04.

Đã có root dev.ps1: một lệnh chạy FastAPI+Next.js, tự đọc key local/env/.env,
check dependencies, không hỏi/lộ key, Ctrl+C dừng sạch process tree sở hữu.
Đã test startup/health/proxy, busy port/custom ports/failure cleanup và Ctrl+C.
Upload scan synthetic2 trang qua launcher auto-ready live PASS:1 call Gemini
gemini-3.5-flash-lite,2794 tokens; không benchmark dữ liệu thật hoặc thêm AI calls.

Launcher/docs d8e7026c20116031c12c34828a22be664eb3d47d đã push main, remote khớp.
[CI40791847627](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40791847627)
SUCCESS exact launcher SHA: Python3.11/3.12 mỗi job1502 PASS/11 SKIP; Web13 PASS,
mọi steps đã kiểm. Commit evidence tiếp theo chỉ docs/planning [skip ci], không
gán CI implementation cho SHA documentation mới. Giữ next-env local byte-for-byte
ngoài stage; temporary worktree/stash đã cleanup.
[Usage](../docs/web-demo-v1/local-development.md),
[evidence](../docs/web-demo-v1/w-03-validation.md#10-housekeeping-sau-w-03--2026-10-29).

Next action tại checkpoint cũ: Chờ chỉ đạo tiếp theo; không bắt đầu W-04.
