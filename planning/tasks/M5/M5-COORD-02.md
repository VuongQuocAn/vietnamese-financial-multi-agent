# TASK M5-COORD-02 — Evidence-Guided Coordination

## Metadata

- Milestone: M5
- Status: REVIEW
- Priority: P1
- Dependencies: M5-COORD-01
- Estimated Complexity: S

## Objective

Consumer dùng output thực tế của parent để truy xuất bổ sung, chọn và liên kết
evidence có provenance; đi qua pipeline M6/M7 hiện có.

## Context

Owner giao ngày17/11/2026; ARCH-02 mục5, V2, IntegrationWorkspace, Financial
Tools/EF-EG và corpus JSON đã import. Baseline main `a12f0e9`; worktree riêng
bảo toàn local edits ngoài scope. Qwen qua Gateway, không lưu secrets.

## Inputs

ARCH-02 mục5, existing Financial Tools, pinned EF-EG và JSON BBS2025/ADC2021.

## Outputs

Demand retrieval theo result handle/digest; source-bound observations và
selection/exact-context join records; một append expansion tối đa6 task identities;
targeted controls, live trace và báo cáo ngắn.

## Allowed Changes

M5 workspace/coordinator, runner và tests liên quan; tracking/report của task.

## Out of Scope

Python Agent, M6 Feedback/obligations, sửa M7, graph database/workspace mới,
OCR/PDF/manual verification, benchmark rộng, thay đổi raw/canonical corpus.

## Implementation Steps

1. Demand retrieval đọc dependency outputs có identity/digest và nguồn.
2. Selection/join records giữ context và provenance trong workspace hiện có.
3. Targeted controls, live probe giới hạn; ghi REVIEW và commit/push main.

## Acceptance Criteria

- [x] Có trace downstream lấy output parent để retrieve evidence mới.
- [x] Selection giữ domain/header/kỳ/selector/quality, ties/dấu/null; join exact keys, cardinality/unmatched.
- [x] Không promote raw evidence; lỗi chỉ chặn nhánh phụ thuộc, giữ kết quả độc lập.
- [x] Targeted controls và live Qwen câu mới; lưu tools/agents/evidence/M6/M7.
- [x] Commit/push main và xác minh SHA; REVIEW chờ Tech Lead.

## Required Tests

Ba controls demand/selection/expansion, compatibility Coordinator/V2 và smoke M6/M7;
Ruff, planning checker, diff check. Live tổng3câu mới, cap toàn task18 calls, không retry transport;
mỗi câu tối đa một retest. Đã dừng17calls; không full CI mặc định.

## Risks and Blockers

M6 cũ chưa có typed selection/join obligations; records không tự cấp authority.
Kỳ/entity mơ hồ, context/unit thiếu hoặc miền thiếu phải giữ gap. Chỉ probe năng
lực, không accuracy benchmark hoặc PDF-verified.

## Implementation Evidence

Implementation `1874166c3506994926a87f993458543d76a50806`;
178runtime files trong commit khớp receipt live-release. [Report](../../../docs/m5-coord-02-live-validation.md).
24targeted PASS;17Qwen calls/115085tokens. Final selection→retrieve→join→
Calculator3,18%→M6 3ACCEPT; M7 verification_blocked vì thiếu goal bindings.
Không sửa M6/M7, không OCR/PDF/benchmark; chờ Tech Lead nghiệm thu.

## Handoff Notes

Tech Lead review implementation và live trace; không tự chuyển DONE.
