# Codex Handoff

## Active Task

W-03 — PDF Upload & Gemini Vision Metadata Preflight

## Status

REVIEW

## Last Verified State

Baseline refinement f617e68295f79de1c5702fe8c27f7b0fcfcea0b1 sau fetch.
PR #1/#2/#3 OPEN; #3 draft base W-02. W-01/W-02 DONE.
Giữ next-env local, không core/M1–M2/Stitch/CI/merge/W-04/M3.

## Completed Work

Key-file-only rotation/cooldown/auth/retry-after/cap chung qua existing
Gateway/adapter/cache, không giả confirmed project. Counters persist, bỏ manual
policy/fingerprint/scope. Metadata_v2 flat/one SDK user turn, runtime strict.
Auto-ready core có nguồn, accepted/auto và confirmed/user tách riêng; revisions/
history/user edits/suggestions giữ. UI neutral, form tùy chọn, desktop-first.
Live scan synthetic 2 trang PASS + edit PASS; 3 attempts tổng, không thêm live calls.

## Remaining Work

Publication/CI exact refinement SHA và Tech Lead review. Không W-04/M3.

## Modified Files

src/api metadata composition/store/jobs/list summary, metadata_preflight, web
detail/labels/styles/tests; key-pool tests và smoke script, .env example, docs/
planning. Xóa config example manual policy obsolete. next-env có sẵn không stage.

## Tests

8 targeted browser documents PASS, có auto-ready 1440/1366 không form bắt buộc.
Python focused 44 cases và lint/format/TS/ESLint/build/planning/diff kiểm trước commit.
Live: 2 HTTP400 ban đầu, sau flat schema/coalesce turn 1 success, 2805 tokens,
tên/năm/scope đúng nguồn trang2, ready auto + user edit PASS. Không benchmark.

## Blockers

Không blocker implementation. Key file không chứng minh project/billing; Free
Tier dựa trên user confirmation, cap chung bảo thủ và provider enforce quota thực.
Live chỉ synthetic, chưa chất lượng metadata trên dataset thực.

## Git Checkpoint

Baseline ổn định f617e68; implementation refinement chưa commit/push tại checkpoint
này. CI40710376652/b494788 là lịch sử, không coi CI refinement đã PASS.
Không stage key/PDF/images/cache/usage counters/next-env. Publication SHA/CI ghi sau.

## Exact Next Action

Commit/push refinement và xác minh CI.
