# TASK M6-LITE-01 — Simplified Financial Claim Verification

## Metadata

- Milestone: M6
- Status: REVIEW
- Priority: P1
- Dependencies: M6-06, M5-08, M7-05
- Estimated Complexity: M
- Related Modules: verification, Ledger admission, financial QA API

## Objective

M6 Lite kiểm chứng từng financial candidate bằng Python và một semantic verifier
khi cần; lưu ACCEPT vào Verified Ledger để M7 dùng nguyên contracts hiện có.

## Context

Owner giao task ngày11/11/2026, baseline main `9a6aaac`.
M5 Lite/M7 Lite đã triển khai; giữ legacy mặc định và local edits ngoài task.
Registry dependencies dùng các task nền đã DONE trong Git; code Lite hiện diện
ở baseline, các receipts nghiệm thu M5/M7 local được giữ ngoài commit này.

## Inputs

BBS và M5-LITE-01 artifacts hiện có, catalog độc lập, financial validators/tools,
Gateway chung và Ledger repository. Không OCR/extraction, không dựng lại EF-EG.
Ngân sách toàn task tối đa4Gemini live calls, không retry429/503, không M5/M7 live.

## Outputs

- Flag `m6_lite=False`, runtime deterministic→semantic→single final decision.
- Proof Lite trung thực và admission/reload tương thích Ledger, không giả critics.
- Targeted negative controls, real BBS smoke và bounded semantic live runner.
- [Báo cáo](../../../docs/m6-lite-01-simplified-verification.md), artifacts ignored.

## Allowed Changes

M6 Lite runtime/proofs, contract/admission tối thiểu backward compatible,
financial QA flag/integration/trace, targeted tests, runner, planning và CI.

## Out of Scope

Không sửa nghiệp vụ M1–M5/M7, historical Ledger hoặc financial source data.
Không thêm Judge, revision, Planner coverage gate, agent role, M8 hoặc remediation task.
Không fake EvidenceCriticResult/LogicCriticResult hay tự cấp approval bước chưa chạy.

## Implementation Steps

1. Audit M6/contracts và đối chiếu Git/local edits.
2. Triển khai một nhánh Lite, kiểm tra nguồn/số/calculation trước semantic.
3. Targeted controls và real BBS offline integration; live giới hạn sau offline đạt.
4. Báo cáo, một implementation commit/push main nếu validation đạt, xác minh CI.
5. Dừng REVIEW để Tech Lead nghiệm thu.

## Acceptance Criteria

- [x] Python kiểm tra facts/calculations và quan hệ số học có proof.
- [x] Semantic verifier đánh giá nội dung interpretation, không phụ thuộc mẫu câu.
- [x] Có supported interpretation live nếu provider khả dụng; negative controls rõ nguồn.
- [x] Không unsafe ACCEPT trong các ca đã chạy; sai deterministic không được LLM cứu.
- [x] Quyết định riêng từng claim, provider failure giữ deterministic ACCEPT.
- [x] Không revision loop, Planner/M7 coverage gate hoặc semantic pass thứ hai ở M7.
- [x] Ledger admission/reload giữ identity/provenance/citations/limitations và backward compatibility.
- [x] M5/M6/M7 Lite offline smoke và legacy targeted checks đạt.
- [x] Không vượt4live calls; có tokens/latency/provider receipts và báo giới hạn thực tế.

## Required Tests

Focused controls: facts đúng/sai, calculation/lineage đúng/sai, derived relation,
semantic support/causal rejection, citation/context sai, failure isolation,
provider failure và Ledger tamper/reload. Real BBS/M5 artifacts và offline pipeline smoke.
Không full regression local; Ruff, planning checker, diff check; CI đúng SHA.

## Risks and Blockers

Scope nguồn unresolved phải giữ caveat; không xác nhận scope mà nguồn chưa biết.
Provider429/503 không retry; engineering smoke không thay chất lượng tài chính.
Giữ giới hạn ngôn ngữ/numeric binding và upstream M5/M7 nếu phát hiện.

## Implementation Evidence

Implementation chưa commit; targeted/offline/live đã đạt trong phạm vi báo cáo. Baseline `9a6aaac9a60a4dc2b000bd4f0e86bce875cf3295`.
Evidence cuối ghi ở báo cáo; traces riêng `artifacts/evidence/M6-LITE-01/`.

## Handoff Notes

Next action: Tech Lead nghiệm thu M6-LITE-01 và các giới hạn trong báo cáo.
