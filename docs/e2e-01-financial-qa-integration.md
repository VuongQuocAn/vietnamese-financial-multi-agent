# E2E-01 — Tích hợp Financial QA

## A. Architecture audit (trước implementation)

Trước: M5 dừng ở candidates; M7 đọc ledger đã lưu. Chưa có application service
điều phối M5→M6→admission→M7. `FinancialQABaseline` là baseline M4 riêng,
không có verification authority; không biến baseline này thành M6.

| Boundary | Input | Output | API/adapter |
| --- | --- | --- | --- |
| User → M5 | question, explicit document/snapshot/company/period | OrchestrationResult | FinancialMultiAgentOrchestrator.run + PlannerContext hiện có |
| M5 → M6 | AggregatedCandidate, origins, supporting references, citations, calculation | VerificationInput | to_verification_input hiện có; giữ conversion issues/conflicts/caveats |
| M6 → Ledger | validation + evidence + logic + bounded Judge outcome | VerifiedClaim | thêm runtime coordinator tạo VerificationProofContext/VerificationHistory mới; repository.admit_many hiện có |
| Ledger → M7 | exact identity query + original question | VietnameseQAResponse | request_inventory + VietnameseQAComposer hiện có |
| M7 → Final | protected response + citations + original request + ledger | safe released view | CitationRenderer + InformationFirewall hiện có |

M6 có runtime components thực: DeterministicFinancialValidator đọc catalog độc lập;
EvidenceCritic tự resolve M4 sources qua EvidenceContextBuilder; FinancialLogicCritic
đọc đúng các upstream outputs. Judge deterministic, không phải LLM Judge.
BoundedVerificationLoop yêu cầu caller chạy lại cả ba checks cho revision một lần.
Repository replay Judge để admission, không tự chạy lại validators/critics.
Các evaluator M6 cũ chủ yếu lưu/replay proof contexts; runtime mới phải tạo proof
từ chính candidates hiện tại, không dùng historical results làm fresh verification.

M5 đã giữ candidate IDs, origins/execution IDs, fact/metric references, evidence,
calculation trace và citations. Scope thiếu không được adapter tự điền.
Không cần đổi accounting contracts hoặc nhân bản verification/QA policies.

## B. Integration behavior

Entrypoint: `api.financial_qa_pipeline.FinancialQAPipeline.run(FinancialQARequest)`.
Không có application service M5/M6/M7 hiện hữu để mở rộng; service này nằm ở
composition/application layer, không sửa M4 baseline hoặc verification authority.

Context resolve bằng registered document/company aliases và SnapshotCatalog,
không dùng filename/similarity/latest. Filing year chỉ chọn metadata document khi
caller chưa chỉ định document; request period/year/scope conflicts fail-closed.
Scope không được tự điền; explicit scope chưa confirmed trả clarification.
Unsupported formula/cross-document/no-context evidence không gọi Gateway.

Lookup dùng exact company/document/snapshot/explicit period; `request_inventory`
M7 hiện có quyết định target/year/scope/explanation coverage, không coi metric
operand là standalone fact. Cache đủ coverage bỏ qua M5/M6/Gateway. Một request
dùng ledger query cache read-only; invalidate sau admission rồi đọc lại repository.
Không bỏ repository validation để giảm latency.

Partial reuse dùng fallback M5 cho yêu cầu đầy đủ, giữ verified claims và chống
admission trùng theo accepted assertion signature M7. Trace ghi
`full_request_refresh_fallback`; khi tắt Gateway vẫn trả verified subset bằng
`PARTIAL_REUSE_ONLY`. Planner clarification/provider failure khi đã có subset
không làm mất subset; vẫn phải qua M7/Firewall. Conflicting candidates chặn
release cả khi force-refresh gặp ledger cũ, không dùng cache che xung đột mới.

`VerificationRuntime` chạy validator→EvidenceCritic→FinancialLogicCritic→bounded
Judge cho fresh input; revision một lần chạy lại cả ba checks, proof contexts
không có legacy pairing. `admit_many` chỉ nhận ACCEPT histories; không ghi JSON
ledger trực tiếp. M7 luôn đọc lại admitted entries; API chỉ trả
`FirewallDecision.validated_output`, không trả draft bị BLOCK.

Policy native là `ACCEPT/REVISE/INVESTIGATE/ABSTAIN`, **không có REJECT/DEFER**.
Trace giữ cả initial/final decisions. Summary `rejected_claims` đếm terminal
ABSTAIN, `deferred_claims` đếm INVESTIGATE; đây là nhãn tổng hợp không đổi Judge.
Technical trace tách khỏi `answer_vi`, gồm agents/tools thực thi, native decisions,
admission IDs, calls/tokens/unknown usage/errors, stage status/duration và wall time.
M7 dùng deterministic protected-slot composition; cache không gọi model reorder.

## C. Actual results

E01 đã có actual fresh PASS và cache rerun0calls. E02/E03 cũng đã release từ
fresh verification; E04/E05 đang chạy. Chi tiết cuối cùng cập nhật sau audit.

## D. Financial correctness

Synthetic tests chỉ là bằng chứng engineering. Reference BBS chỉ dùng sau runtime.

## E. Performance và provider budget

Tối đa 25 actual provider attempts cho validation của E2E-01, model hiện có.
Không OCR/extraction, không thay accepted artifacts. Đo riêng lookup/M5/M6/M7.

## F. Remaining issues

Focused compatibility399 PASS, cộng2conflict controls PASS. Bộ integration có24
cases (gồm parameterized controls); synthetic/replayed provider không phải accuracy.
Chờ hoàn tất actual suite và CI.

## G. Handoff

Implementation chưa commit; chưa có CI E2E-01. Dừng tại REVIEW sau bàn giao.
