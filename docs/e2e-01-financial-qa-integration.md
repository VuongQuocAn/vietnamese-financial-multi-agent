# E2E-01 — Tích hợp Financial QA

Status: **DONE** theo quyết định review06/11/2026: chấp nhận implementation về
kiến trúc, đóng task sau khi đồng bộ docs/planning bằng kết quả đã lưu và không
phát hiện sai lệch mới. Phiên chốt này chỉ sửa tài liệu; không chạy lại Gemini,
runtime, tests/benchmark hoặc hash dataset. P1 cold lookup giữ ngoài E2E-01.

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

E01–E05 chạy actual application pipeline trên catalog persisted, ledger riêng ban
đầu trống. Không replay M6 historical proof, không OCR/extraction. Tổng19 candidate
verification occurrences: **17 ACCEPT, 2 INVESTIGATE, 0 ABSTAIN**; **10 mới lưu**,
7 ACCEPT idempotent. Hai INVESTIGATE không admission là cùng một interpretation
lặp ở E03/E04. Không nhầm số ACCEPT với số ledger entries mới.

| Kết quả cuối E01–E05 | Số lượng |
| --- | ---: |
| Candidate verification occurrences | 19 |
| M6 ACCEPT | 17 |
| M6 INVESTIGATE, không admission | 2 |
| M6 ABSTAIN | 0 |
| Ledger newly stored | 10 |
| ACCEPT idempotent, không lưu trùng | 7 |

Nguồn đối chiếu: `financial-audit.json` và admission outcomes trong các JSON
E01–E05 đã lưu. Đây là tổng lượt verification/admission, không phải19claims unique.

| Case | Mode | Specialists thực thi | Tool calls | ACCEPT / INVESTIGATE | New / reused trong answer | M7 / citations / Firewall |
| --- | --- | --- | ---: | --- | --- | --- |
| E01 | fresh | profitability | 6 | 2 / 0 | 2 / 0 | answered / 13 / ALLOW_WITH_CAVEAT |
| E02 | fresh | profitability | 4 | 2 / 0 | 2 / 0 | answered / 13 / ALLOW_WITH_CAVEAT |
| E03 | fresh | liquidity_and_leverage | 6 | 3 / 1 | 3 / 0 | answered / 19 / ALLOW_WITH_CAVEAT |
| E04 | partial reuse + refresh | cả ba Specialists | 14 | 9 / 1 | 3 / 2 | answered / 43 / ALLOW_WITH_CAVEAT |
| E05 | partial reuse + refresh | profitability, cash_flow_and_earnings_quality | 4 | 1 / 0 | 0 / 2 | partial / 21 / ALLOW_WITH_CAVEAT |

Tổng8 Specialist invocations (7generated/partial,1provider failure),34 M4 tool
calls. E05 M5 partial vì cash-flow Specialist failed. E03/E04 interpretation về
debt có numeric/content_period undetermined và logic insufficient_context →
INVESTIGATE. Metric59,06% có ACCEPT riêng; không bỏ gates để nhận interpretation.
Actual không có revision; synthetic control xác minh one-child revision chạy lại
đầy đủ validator/evidence/logic trước admission.

Planner planned/Supervisor completed ở cả5 câu. Planner intent E01 là
evidence_explanation; E02–E05 multi_step_analysis. Router routed E01–E04,
partial E05. Trace JSON giữ từng tool name/status/duration và Specialist stages.

Các trích đoạn sau giữ nội dung thực, lược inline markers/registry để đọc. JSON
E01–E05 giữ đầy đủ answer_vi, citations và mọi caveat/limitation nguyên văn.

### E01

> Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 đạt 7,21%.
> Công thức: (5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ / 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ) × 100%.
> Số liệu sử dụng trong phép tính đã xác minh:
> 5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ (gross_profit): 32482519668 VND; hệ số đơn vị 1; kỳ 2025.
> 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ (revenue): 450474531227 VND; hệ số đơn vị 1; kỳ 2025.

### E02

> Kỳ 2025 — Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.
> Kỳ 2025 — Lợi nhuận sau thuế kỳ 2025 là 7.249.557.946 VND.

### E03

> Kỳ 2025-12-31 — Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND.
> Kỳ 2025-12-31 — Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%.

### E04

> Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 đạt 7,21%.
> Kỳ 2025-12-31 — Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%.
> Kỳ 2025 — Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 14.319.681.754 VND.

### E05

> Kỳ 2025 — Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.
> Kỳ 2025 — Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 14.319.681.754 VND.
> Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.
> Các yêu cầu chưa đáp ứng: r3 (nhận định về 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ: chưa có nhận định ACCEPT phù hợp), r4 (nhận định về Lưu chuyển tiền thuần từ hoạt động kinh doanh: chưa có nhận định ACCEPT phù hợp).

E05 không kết luận “chất lượng lợi nhuận tốt”; hai facts doanh thu/CFO giữ từ
ledger. Một ACCEPT duplicate mới không trở thành authority cho quality verdict.
E03/E04 có partial verification thực; E05 có provider failure thực. Synthetic
controls bổ sung mixed ACCEPT/ABSTAIN/INVESTIGATE, all-nonaccept, source mismatch,
wrong identity/year/scope, duplicate, conflict, revision và Firewall BLOCK.

## D. Financial correctness

Post-runtime audit tách khỏi pipeline: đọc lại repository đã admitted và so sánh
10 selected-claim occurrences với số đọc PDF độc lập ở QA-Q01 và reference Owner
cung cấp. **10/10 match**, gồm company/document/snapshot/year, ACCEPT authority,
operand value/unit/scale và PDF page. Runtime không đọc reference file. Không có
visual PDF audit mới; kết quả không chứng minh accuracy toàn báo cáo.

| Target | Reference và actual | PDF page |
| --- | --- | --- |
| Gross margin | 7,21% | 7 |
| Debt-to-assets | 59,06% | 5–6 |
| Revenue | 450.474.531.227 VND | 7 |
| Gross profit (operand) | 32.482.519.668 VND | 7 |
| Total assets | 266.086.680.765 VND | 5 |
| Total liabilities (operand) | 157.146.559.558 VND | 6 |
| CFO | 14.319.681.754 VND | 8 |
| Net profit after tax | 7.249.557.946 VND | 7 |

Citations giữ page-level/uncertain/source scope caveats; không nâng thành
cell-level independent audit. Scope separate/consolidated chưa confirmed, giữ
unknown. M7 chỉ hiển thị operands trong explanation admitted, không tự tính số.

## E. Performance và provider usage

Đơn vị giây; wall gồm copy/serialization/admission/reload ngoài các bước chính.
M7 là tổng Composer + CitationRenderer + Firewall. Không suy một lượt thành
benchmark toàn hệ thống; E01 chạy đồng thời focused tests.

| Case | Lookup | M5 | M6 | M7 | Wall | Rerun wall / mode |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| E01 | 0.001 | 44.857 | 9.519 | 1.274 | 80.745 | 5.465 / CACHE_HIT |
| E02 | 2.988 | 37.077 | 4.441 | 2.392 | 68.938 | 5.564 / CACHE_HIT |
| E03 | 1.740 | 53.423 | 14.192 | 4.194 | 113.884 | 11.326 / CACHE_HIT |
| E04 | 4.630 | 74.343 | 28.250 | 10.642 | 188.340 | 21.289 / CACHE_HIT |
| E05 | 9.480 | 71.007 | 12.088 | 25.570 | 183.466 | 23.186 / PARTIAL_REUSE_ONLY |

E01–E04 rerun CACHE_HIT; E05 PARTIAL_REUSE_ONLY. Cả5 reruns giữ nguyên selected
IDs và answer, M5/M6 NOT_EXECUTED,0provider calls. E05 không báo cache đầy đủ khi
còn thiếu verdict. Ledger task10 entries khoảng60,22MB; không load lại JSON cho
từng M7 consumer trong cùng request, nhưng parse/proof payload vẫn đáng kể.

Final-code cache check trên đúng implementation9811a44 sau commit, repository
instance mới và ledger10entries: CACHE_HIT,0calls,74,525s wall/44,145s lookup;
answer/IDs giữ nguyên E01. Lượt này chạy đồng thời read-only financial audit,
không phải isolated latency benchmark. Cold JSON/proof replay vẫn là blocker
cho demo tương tác; warm5,46s không che limitation này.
Actual fresh E01–E05 capture trước commit implementation; hai final guards
(unsupported formula/conflict refresh) không bị kích hoạt ở những câu này.
Final-code cache/admission-proof replay và CI xác minh implementation đã commit;
không gọi lại Gemini chỉ để đổi nhãn evidence SHA.

**18/25 provider attempts**,64.847 known tokens;3provider errors/3attempts unknown
usage. Hai Planner HTTP503 (E04/E05) retry đúng một lần và thành công; một
cash-flow Specialist E05 provider_unavailable không retry. Model giữ
`gemini-3.5-flash-lite`, không rotation/model switch, mọi call qua Shared Gateway.
Chi phí tiền chưa có metadata, không suy ra0. Durable budget dùng chung mọi
output subdirectories, giữ started attempts khi resume; không reset budget.

Integrity checks mỗi invocation:8selected hashes (Web +7accepted M5 run traces)
và hydrated facts/metrics/source reviews unchanged. Git chỉ đổi task files;
không hash toàn protected dataset, không ghi raw/processed/accepted artifacts.

## F. Remaining issues và validation

- P0 integration: chưa phát hiện trong phạm vi đã kiểm tra.
- P1 performance blocker cho demo tương tác → đề xuất QA-Fix-04: whole JSON/proof
  payload60MB và cold/warm parse/copy/revalidation gây latency đáng kể. Functional
  flow PASS; chưa đạt interactive latency. Nên khảo sát shared proof contexts và
  storage/query có giới hạn, giữ nguyên admission replay authority.
  Tech Lead xác nhận cold lookup44,1s không cần sửa trong E2E-01; giữ follow-up riêng.
- P1 external availability:3provider failures thực; nguyên nhân503 bên ngoài chưa
  xác định. Recovery bounded/fail-closed đã chạy, không che usage unknown.
- E05 thiếu supported earnings-quality verdict; partial đúng coverage, không tự
  thêm threshold/agent/formula hoặc bắt đầu GEN/M8.
- P2: chưa có incremental missing-target contract an toàn; full-request fallback
  lặp verification (7duplicate ACCEPT); M7 legacy caveats/citation registry dài.
  CLI dùng composition root catalog nghiên cứu persisted hiện có; class pipeline
  nhận catalog/documents bất kỳ, không hardcode company/financial values.

Local:399 focused M5/M6/M7/planning PASS +2conflict controls PASS (401distinct
cases;24integration cases). Initial collection fail trước implementation; vòng
đầu12fail/6pass, sau sửa18pass; mở rộng21pass/1fixture bookkeeping fail rồi test
correction PASS; final compatibility399pass/conflict2pass. Không sửa frozen
M6/M7 expected outputs. Ruff changed files/format/planning105tasks/diff PASS;
không full local regression/frontend build/M8. CI được ghi riêng bên dưới.

## G. Handoff / reproduce

Implementation `9811a4443f24a8b8083491f1968ab641ee69b63a` đã push main.
[CI42145875699](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42145875699)
completed/SUCCESS đúng SHA:1068Python tests/9Web smoke PASS; lint/format/planning,
frontend typecheck/lint/build PASS; full regression SKIPPED.
Evidence checkpoint sau chỉ docs/planning;
không gán CI implementation cho SHA docs khác.

Checkpoint tài liệu `5826f33d1162034b260553d700510be3b46935fb` đã có kết quả cuối
trên GitHub `main`; phiên review này kiểm tra trực tiếp ba file report/spec/current
status trên remote và đối chiếu summary/admission outcomes đã lưu, không thấy
sai lệch mới. Bổ sung bảng tổng hợp rõ ràng và đồng bộ trạng thái DONE theo quyết
định Tech Lead. Chỉ chạy planning checker và diff check cho thay đổi tài liệu.

Actual commands từ root (Python trong `.venv`):

```powershell
python scripts/run_e2e_financial_qa.py --case E01 --allow-gateway
python scripts/run_e2e_financial_qa.py --case E02 E03 E04 E05 --allow-gateway
python scripts/audit_e2e_financial_qa.py
```

Cache review trên ledger đã tạo, không credentials/provider calls:

```powershell
python scripts/run_e2e_financial_qa.py --question "Biên lợi nhuận gộp của BBS năm 2025 là bao nhiêu? Hãy nêu công thức và các số liệu sử dụng." --label review-e01
```

CLI hỗ trợ `--document`, `--snapshot`, `--company`, `--period`, `--reporting-scope`,
`--force-refresh`, `--allow-gateway`, `--output`. Không cần sửa proof JSON hoặc
truyền hàng chục source paths. Output exclusive; chọn label mới khi review, không
ghi đè E01–E05. Fresh demo riêng dùng output subfolder mới nhưng vẫn chia sẻ tổng
25attempt budget E2E-01.

Local ignored artifacts tại `artifacts/evidence/E2E-01/`: `E01.json`–`E05.json`,
các `*-rerun.json`, `ledger/verified-claims.json`, `financial-audit.json`,
`provider-attempts.jsonl`, `integrity-*.json`, `final-code-cache-e01.json` và console
captures. Không commit full ledgers/source citations/datasets/secrets.

Next action: chờ Owner/Tech Lead giao task tiếp theo; không tự bắt đầu QA-Fix-04.
