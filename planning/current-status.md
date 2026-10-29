# Trạng thái hiện tại

Cập nhật 2026-10-29 (Asia/Bangkok); nguồn [Registry](tasks.md).

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
CI PASS trước merge. W-01/W-02 DONE; W-03 giữ REVIEW, không tự bắt đầu W-04.

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
