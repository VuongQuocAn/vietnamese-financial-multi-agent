# Codex Handoff

## Active Task

M4-04 — Evidence Retrieval Tools

## Status

REVIEW

## Last Verified State

Baseline main/origin main/remote `749d37fbe832f7aa2701162269eb8e42402a2ba5`.
[Spec](tasks/M4/M4-04.md), [report](../docs/m4-04-evidence-retrieval-tools.md).
Implementation `304da3a6a95873acd88fc3b49a5fd0268e07653f` và format fix
`a36493b60834c32b5629f23dc4bfa0062359db01` đã push main;
[CI41381388861](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41381388861)
completed/SUCCESS đúng fix SHA;Python3.12 lint/format/planning/focused tests SUCCESS;
Web smoke/full regression SKIPPED. Format fix chỉ code fence tài liệu, runtime giữ nguyên.

## Completed Work

Năm typed tools cho document evidence, anchors, sources và metric lineage.
Sửa M3 get_sources false-found khi source thiếu reference/image hoặc sai binding;
ba regression controls FAIL trước/PASS sau. Không refactor graph/engine/policies.

## Remaining Work

Tech Lead independent review trước DONE.

## Modified Files

src/tools, src/evidence/retrieval.py, hai test files, evaluator, focused CI list,
docs/planning. Giữ web/next-env.d.ts ngoài stage và byte-for-byte.

## Tests

203 focused PASS; Ruff/planning/diff PASS trước commit.
Real139 text/24 tables/2.973 anchors/18 lineages exact;25 priority sources;
18 accepted executions/independent arithmetic/restart exact.
Sau correction:2.087 fact sources/163 evidence sources/29 queries/7 real controls PASS.
15+3 eligibility/36 undetermined pairs/D-07 scopes/D-06 QA09/QA15 giữ nguyên;
2.657 protected input hashes unchanged,zero Gateway/Gemini/OCR/extraction.
Ignored outputs:artifacts/evidence/M4-04 và M4-04-source-check.

## Blockers

Không P0/P1 còn mở trong phạm vi kiểm tra. All real anchors uncertain/page-level;
financial_fact_verified=False. Cross-document approval vẫn ngoài scope.

## Git Checkpoint

Implementation/fix và CI trên đã xác minh; checkpoint sau chỉ docs/planning
[skip ci], không gán CI fix cho SHA checkpoint. Web SHA256 trước task:
`0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`.
Không stage artifacts/dataset/secrets, không branch/PR/worktree/force-push.

## Exact Next Action

Tech Lead independent review M4-04; chưa bắt đầu M4-05.
