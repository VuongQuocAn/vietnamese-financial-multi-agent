# TASK QA-Q01 — Quick QA Execution & Root-Cause Diagnosis

## Metadata

- Milestone: QA
- Status: REVIEW
- Priority: P1
- Dependencies: M5-08, M6-06, M7-05
- Estimated Complexity: M
- Related Modules: agents, tools, verification, outputs; chỉ đọc runtime.

## Objective

Kiểm tra mười câu tài chính BBS do Owner cung cấp, đối chiếu độc lập PDF và
điều tra nguyên nhân sai lệch. Đây là QA bổ sung, không phải M8 hoặc benchmark.

## Context

Owner giao ngày 05/11/2026; baseline main/origin
`34a3fec1171b23bc9c9c268aded4a2205ae68936`, accepted M7-05 `b22d831`.
M5 actual orchestration và M7 ledger QA phải đánh giá riêng. Dừng REVIEW.

## Inputs

Mười câu nguyên văn trong runner/báo cáo; PDF BBS 2021–2025 local read-only;
persisted catalog/OCR; accepted M6 ledger và các public M5/M7 APIs. Không dùng
ledger/frozen oracle làm ground truth độc lập. Gemini qua Gateway hiện có,
tối đa 16 provider calls cho Q03/Q06/Q07/Q08, không retry/chuyển model trả phí.

## Outputs

- `docs/qa-q01-quick-qa-root-cause.md`: báo cáo A–I, giá trị tài chính đọc được,
  kết quả từng câu, findings P0/P1/P2 và QA-Fix đề xuất.
- `artifacts/evidence/QA-Q01/`: ignored local traces, outputs, source renders,
  independent reference, integrity hashes; output mới, không overwrite.
- `scripts/run_qa_q01.py`: QA-only capture qua production public APIs.

## Allowed Changes

QA-only runner, báo cáo và planning. Cho phép commit/push main theo task Owner.
Planning checker chỉ mở rộng nhận Task ID QA-Q01 và nhóm QA, giữ IDs cũ.

## Out of Scope

Không sửa runtime/facts/mappings/formulas/policies/ledger/oracle; không extraction
lại, không fake agents/tools, không triển khai QA-Fix/M8. Web local giữ nguyên.

## Implementation Steps

1. Git/environment/PDF/catalog preflight; đọc execution paths và trace contracts.
2. M7 actual mười câu: Composer → Renderer → Firewall; chỉ released output là final.
3. M5 actual Q03/Q06/Q07/Q08 một lần/câu hoặc blocker có bằng chứng; full traces.
4. Đọc PDF trực quan, kiểm kỳ/scope/unit/operands; Decimal tính lại metrics.
5. Phân loại execution, financial accuracy và independent coverage riêng;
   điều tra earliest faulty stage, confirmed vs hypothesis; đề xuất fix/regression.
6. Integrity/targeted checks, commit/push tài liệu/QA tooling; dừng REVIEW.

## Acceptance Criteria

- [x] Đủ mười case với actual result hoặc blocker cụ thể; independent PDF evidence.
- [x] Bốn M5 actual attempts hoặc blocker; activation/tool/collaboration diagnostics.
- [x] Tách ACTUAL_EXECUTION/SAVED_TRACE/EVIDENCE_LINEAGE/NOT_AVAILABLE;
      không tuyên bố fresh M6 verification khi M7 chỉ đọc saved ledger.
- [x] Findings/root causes/backlog/retest và performance metadata đầy đủ, dễ đọc.
- [x] Protected inputs/Web unchanged; targeted validation đạt.
- [x] Commit/push main, ghi SHA đã xác minh tại checkpoint.
- [x] REVIEW chờ Tech Lead; chưa tự nghiệm thu DONE.

## Required Tests

Các focused M5/M7 smoke phù hợp; Ruff cho tooling sửa; planning checker;
git diff --check; kiểm protected hashes. Không full regression/live extraction.

## Risks and Blockers

Quota/billing remaining không có API kiểm trong runtime; provider có thể từ chối.
M7 có giới hạn supported intents và chỉ đọc ledger; D03-B10 giữ nguyên.
Traces chứa dữ liệu nguồn chỉ lưu local ignored; không commit datasets/secrets.

## Implementation Evidence

- Implementation SHA: `6b245b53b4a17d94279717a214428b3638bb52a6`, đã push main,
  HEAD/origin khớp sau push; baseline `34a3fec1171b23bc9c9c268aded4a2205ae68936`.
- Main Changes: [báo cáo](../../../docs/qa-q01-quick-qa-root-cause.md), QA-only public
  API capture, registry/checker nhận nhóm QA. Không runtime fixes.
- Test Results: 6 focused engineering controls PASS;16.745protected files unchanged;
  M7 actual10/10, M5 actual4attempts/0downstream; independent output audit19entries/
  10cases PASS; Ruff/format/planning102tasks/diff PASS. Không full regression local.
- CI: [42050329839](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42050329839)
  đúng implementation SHA; đang chạy tại checkpoint ban đầu, không suy từ CI cũ.
- Review Notes: 0P0/3P1/3P2, chờ Tech Lead. Gemini503 chặn3cases; Q07unsupported.

## Handoff Notes

Next action: Tech Lead nghiệm thu QA-Q01 và quyết định nhóm QA-Fix ưu tiên.
