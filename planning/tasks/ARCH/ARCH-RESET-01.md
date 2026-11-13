# TASK ARCH-RESET-01 — Rà soát và đơn giản hóa kiến trúc Multi-Agent

## Metadata

- Milestone: ARCH
- Status: DONE
- Priority: P1
- Dependencies: -
- Estimated Complexity: M
- Related Modules: M5, M6, ledger, M7, EF-EG/tools, financial/document/fusion integration

## Objective

Audit kiến trúc thực tế bằng source/traces; đề xuất Target Architecture V2 cụ thể,
đơn giản và khả thi, giữ EF-EG, Multi-Agent và Claim Verification. Chỉ audit/design.

## Context

Owner giao ARCH-RESET-01 ngày13/11/2026 qua task đính kèm. E2E-GEN-01 có
0/12PASS, 7/35required points, 19/22released claims grounded. Tạm dừng FIX/refactor
và tính năng mới. E2E-GEN-01 là input audit đã lưu, không tự nghiệm thu task đó
hoặc khai dependency DONE khi registry vẫn REVIEW.

## Inputs

`docs/e2e-gen-01-multi-agent-integration.md`, local ignored
`artifacts/evidence/E2E-GEN-01/`, source runtime, architecture/module-boundaries/
data-contracts. HEAD main `a5ebc212a083bde625adf7fb19de9b519210941e`; working tree
có local edits từ trước, 171 runtime files khớp E2E frozen hashes.

## Outputs

[Báo cáo](../../../docs/arch-reset-01-multi-agent-simplification-review.md) gồm
execution paths, RCA C01–C10, contract losses/gates, vai trò Multi-Agent/M6/M7,
V2 diagram/responsibilities/contracts, decisions, comparison/trade-offs,
migration tối thiểu, acceptance, risks và quyết định cần duyệt.
Inspection read-only ở local ignored `artifacts/evidence/ARCH-RESET-01/`.

## Allowed Changes

Tài liệu task/report/planning và inspection offline trong artifacts riêng;
bảo toàn local edits. Không stage/commit/push trong phiên này.

## Out of Scope

Không sửa runtime, refactor M5/M6/M7, thêm agent/verifier, đổi EF-EG/raw/canonical,
gọi API/Qwen/Gemini/OCR, chạy E2E mới/M8/full CI, triển khai V2, mở FIX hoặc bắt
đầu CORE-INT-01/CHAT-02/REPORT-01/M8. Không sửa code chỉ để tạo báo cáo.

## Implementation Steps

1. Đọc AGENTS/current status/task và kiểm Git, bảo toàn existing edits.
2. Đối chiếu source với frozen runtime và saved provider/execution/ledger traces.
3. Audit flow/contracts/gates, tách Observed/Inferred/Proposed, inspect offline hữu hạn.
4. Thiết kế V2/migration/acceptance và bàn giao REVIEW để Tech Lead/Owner quyết định.

## Acceptance Criteria

- [x] Báo cáo đủ14nhóm nội dung Owner yêu cầu, evidence code/function/case/input-output/cơ chế.
- [x] Phân biệt financial/document/mixed và Lite/legacy; không quy mọi lỗi cho Qwen/M7.
- [x] RCA đại diện C01–C10; giữ cả false ACCEPT C04 và false negatives C10.
- [x] V2 giữ ba thành phần nghiên cứu, không thêm agent; schema/boundaries và synthesis owner rõ.
- [x] KEEP/SIMPLIFY/MERGE/REMOVE/REPLACE có evidence, tác động và thay thế.
- [x] Migration tối thiểu + measurable E2E criteria, không tự triển khai hoặc claim cải thiện chưa đo.
- [x] Runtime/raw/evidence E2E không đổi;0model calls; chưa commit; dừng REVIEW.
- [x] Tech Lead/Owner APPROVED ngày13/11/2026: workspace request-local, không refactor M7/Ledger diện rộng; tách architecture invariants khỏi năng lực Qwen/capability probes.

## Required Tests

Docs-only không smoke/full suite. Chạy offline source/hash/schema/proof inspection,
`python scripts/check_planning.py` và `git diff --check`.
Checker hiện chưa nhận immutable ID `ARCH-RESET-01`; không đổi scripts/check_planning.py
trong audit. Kiểm cấu trúc bổ sung bằng chính hàm check với regex cho phép đúng ID
này trong bộ nhớ, báo riêng kết quả và giới hạn của lệnh chuẩn.

## Risks and Blockers

Không có V2 implementation/live evidence; không tuyên bố accuracy hay lợi ích
Multi-Agent. Legacy judge-veto là code-observed, không gán cho E2E Lite path.
Planning checker chưa hỗ trợ tên task mới là tooling limitation, không đổi ID
hoặc code để làm lệnh PASS. Local artifacts ignored nên cần workspace để replay.

## Implementation Evidence

Report-only commit [3475a3af8a2d1635bfa6037c0743245ba2a3e9e5](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/3475a3af8a2d1635bfa6037c0743245ba2a3e9e5) đã push main và remote SHA verified;
baseline HEAD `a5ebc212a083bde625adf7fb19de9b519210941e` đã xác minh;
không gán chất lượng working runtime cho SHA riêng lẻ.
Offline inspection:171/171runtime và778/778protected hashes unchanged,
5frozen inputs khớp;22/22saved ledger entries được release,0ngoài ledger.
C01 tái hiện extra_forbidden root use_graph; C06 exact fence removal cho3tasks
hợp schema (syntax-only); C10 hai dynamic proofs exact replay, asset premise parser
không bind. Kết quả ở `artifacts/evidence/ARCH-RESET-01/inspection.json`.
Planning chuẩn FAIL `Invalid Task ID: ARCH-RESET-01`; chính hàm check với regex
thêm đúng ID trong bộ nhớ PASS142tasks (status/dependency/dashboard/spec/links).
`git diff --check` PASS; không sửa checker, không có CI mới.

## Handoff Notes

Status: **DONE — APPROVED**, Owner/Tech Lead ngày13/11/2026.
Audit không sửa runtime, không API/OCR/full tests; chỉ report được commit/push.
Next action duy nhất: thực hiện V2-INT-01 trong phạm vi migration tối thiểu Owner giao.
