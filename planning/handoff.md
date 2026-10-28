# Codex Handoff

## Active Task

W-03 — PDF Upload & Gemini Vision Metadata Preflight

## Status

REVIEW

## Last Verified State

Fetch: W-02 HEAD 78a50c6, W-01/W-02 DONE; PR #1/#2 OPEN.
Nhánh feat/w-03-pdf-upload-metadata, stacked base feat/w-02-web-skeleton.
Giữ thay đổi có sẵn web/next-env.d.ts ngoài task. Không merge/W-04/M3.

## Completed Work

PDF upload/list/detail/file Range, validation/limits/hash/UUID và local atomic
snapshots; một metadata worker có bounds/polling/retry/idempotency/restart.
Vision schema có candidates/raw text/page provenance, GeminiAdapter qua shared
Gateway/guard/cache/registry; review/edit/confirm với revision và ticker nullable.
Runtime namespace document:<UUID>, không gọi financial extraction M1–M2.
Docs/usage/config example/tests đã có, không commit PDF/keys/cache.

## Remaining Work

Tech Lead nghiệm thu độc lập. Live smoke chưa chạy vì chưa có scope budget W-03
được xác nhận. W-04 orchestration/extraction và W-05 viewer ngoài task này.

## Modified Files

src/api/{main,document_store,metadata_service,preflight_jobs}.py,
src/document_processing/metadata_preflight.py, pyproject.toml/.env.example/config
example, web upload/list/detail/navigation/proxy/styles/tests; Python tests,
docs API/architecture/UI/local guide/usage/evidence, boundaries/contracts và planning.
web/next-env.d.ts là thay đổi có sẵn, được khôi phục sau build và không stage.

## Tests

36 focused unit/integration PASS; 139 Gateway/Gemini/quota/cache regression PASS.
Ruff lint/format; TypeScript/lint/build; 11 browser/proxy tests PASS.
Planning/diff/index kiểm tra trước publication; CI xác minh sau PR.
PDF scan synthetic tạo local, không text layer; mock SDK/Gateway không có network.
Live smoke NOT RUN, không đánh giá chất lượng metadata/financial trên dataset thật.

## Blockers

Không blocker implementation. Live cần policy/budget/exclusive accounting scope
mới đã xác nhận; key local không đủ xác định quota/project. Không tự reset guard.
Một API process/worker, quota/cache in-memory; scope marker không là durable guard.

## Git Checkpoint

Baseline ổn định 78a50c6 trên W-02, chưa gán SHA tương lai cho implementation.
Publication SHA/remote/PR/CI ghi sau khi xác minh trong evidence/checkpoint tiếp.
Không stage next-env, PDF, private data, key, snapshots hoặc artifacts.

## Exact Next Action

Tech Lead nghiệm thu độc lập W-03.
