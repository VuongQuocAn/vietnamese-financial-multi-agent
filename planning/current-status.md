# Trạng thái hiện tại

Cập nhật 2026-10-29 (Asia/Bangkok); nguồn [Registry](tasks.md).

W-03 DONE — Tech Lead APPROVED ngày 29/10/2026, engineering scope. PR #1/#2/#3
đã merge main; CI40718128314/refinement7048d92 và CI40791847627/launcherd8e7026
SUCCESS đã có. Live Gemini synthetic PASS, chưa đánh giá accuracy trên PDF
BBS_2025 thực tế tại checkpoint W-03; W-04 được giao mới bên dưới.

## W-07 — End-to-End Acceptance

Status: **IN_PROGRESS**; người dùng giao 29/10/2026. Main/origin/main `391c230`,
PR #7 merged, W-01–W-06 DONE. Nhánh `feat/w-07-web-demo-acceptance`.
[Spec/evidence](tasks/W/W-07.md). Chưa commit, chưa gọi Gemini.
Next action: nghiệm thu tích hợp PDF BBS thực theo W-07.

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
