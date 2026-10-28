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
Planning/diff/index PASS. [CI 40710376652](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40710376652)
SUCCESS exact implementation SHA: Python 3.11/3.12 mỗi job 1494 PASS/11 SKIP;
Web 11 PASS, mọi required steps PASS. Không chạy lại full local suite/CI.
PDF scan synthetic tạo local, không text layer; mock SDK/Gateway không có network.
Live smoke NOT RUN, không đánh giá chất lượng metadata/financial trên dataset thật.

## Blockers

Không blocker implementation. Live cần policy/budget/exclusive accounting scope
mới đã xác nhận; key local không đủ xác định quota/project. Không tự reset guard.
Một API process/worker, quota/cache in-memory; scope marker không là durable guard.

## Git Checkpoint

Baseline W-02 78a50c6285a37063463b30ec2e6c991ce23bf0b5.
Implementation ổn định đã push/remote khớp: b494788ec2a6938bc7e50d15ad347eadccf2aaa5.
[Draft PR #3](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/3)
OPEN base W-02, PR #1/#2 vẫn OPEN/chưa merge. CI exact implementation SHA SUCCESS.
Commit evidence tiếp theo chỉ docs/planning [skip ci], không gán CI cho SHA mới.
Không stage next-env, PDF, private data, key, snapshots hoặc artifacts. Đã dừng
hai server chạy riêng cho browser tests, không dừng process có sẵn của người dùng.

## Exact Next Action

Tech Lead nghiệm thu độc lập W-03.
