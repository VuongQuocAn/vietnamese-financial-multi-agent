# Codex Handoff

## Active Task

M4-05a — Gemini Live Integration & QA Validation

## Status

REVIEW

## Last Verified State

Baseline main/origin `6b5e05d4305b5d3278987d8fedc75022bbfccf67` đã xác minh.
[Spec](tasks/M4/M4-05a.md),[report](../docs/m4-05a-gemini-live-validation.md).
Chưa commit. M4-05 giữ APPROVED/DONE;D03-B10 vẫn BLOCKED với cross-document.

## Completed Work

Local credential resolver/CLI,soft semantic fallback một call,approved-policy prompt
semantics,typed provenance/errors và bounded live runner. Gemini thật hiểu paraphrases;
không truyền sẵn target vào context,không thay Gateway/adapter hoặc accepted facts.

## Remaining Work

Commit/push/CI đúng SHA và Tech Lead nghiệm thu;không M5-01.

## Modified Files

src/api/qa_gateway.py,QA tools,CLI/live runner,hai test files,live question config,
focused CI list và docs/planning. Giữ web/next-env.d.ts ngoài stage và byte-for-byte.

## Tests

30 focused PASS;Ruff377/planning101/diff PASS. Live5 câu:4 answers đúng/grounded,
negative đúng;sau targeted prompt fix.9API attempts,8responses lưu đầy đủ/8success,
6/8correct qua lịch sử;1response unknown do lỗi artifact writer đã sửa.
Known tokens10.798,total cả9 N/A.Model provider gemini-3.5-flash-lite,key0 không rotation.
Offline regression PASS:36/36disposition,28answered đúng/grounded,18metrics/29queries/
36pairs/D-06/D-07/2.670hashes exact,replay exact;live2.665hashes unchanged.
Outputs riêng M4-05a-regression/live/validation;không OCR/extraction.

## Blockers

Không thiếu credentials:local file đã dùng qua composition. One lost response/tokens
giữ unknown;các failures v1 giữ evidence. Nguồn vẫn page-level/scope unresolved,
financial_fact_verified=False,D03-B10 chặn cross-document;không bắt đầu M5-01.

## Git Checkpoint

Chưa commit;không stage key file/artifacts. Web SHA256 trước task giữ nguyên:
`0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`.
Không stage artifacts/dataset/secrets, không branch/PR/worktree/force-push.

## Exact Next Action

Tech Lead independent review M4-05a.
