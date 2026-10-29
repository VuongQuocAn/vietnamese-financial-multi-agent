# Trạng thái hiện tại

Cập nhật 2026-10-29 (Asia/Bangkok); nguồn [Registry](tasks.md).

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
