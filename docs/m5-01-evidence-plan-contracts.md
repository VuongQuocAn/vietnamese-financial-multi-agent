# M5-01 — Evidence Plan and Planner Contracts

Status: REVIEW, chờ Tech Lead independent review. Baseline main
`ca9570d61f9fc0dd45d78956f27590631e601120`; implementation SHA được ghi ở
[spec](../planning/tasks/M5/M5-01.md). Chưa có automated planner/supervisor,
specialist runtime hoặc claim verification. Không gọi Gemini/OCR/extraction.

## Public contracts

Import từ `vietnamese_financial_multi_agent.agents`; implementation tập trung ở
`src/agents/contracts.py`. Models kế thừa strict `FinancialModel`, extra forbid.

| Contract | Trách nhiệm và quan hệ |
| --- | --- |
| QuerySpecification | Original Vietnamese question, intent, selectors công ty/document/snapshot, periods, indicators, formula requests, analysis type, scope, missing/ambiguity. Có `multi_step_analysis`, `unsupported`, `ambiguous`; không giới hạn yêu cầu vào ba formulas |
| EvidenceSelector | Tái sử dụng M3 EvidenceQuery, filters AND; mỗi operand giữ selector/kỳ riêng |
| EvidenceRequirement | ID/type/item/formula/selector, dependencies, required/optional, resolution/reasons, typed references/citations, original quality decisions/caveats |
| PlanStep | Operation, M4 tool/arguments, deferred input bindings, prerequisites, input/output requirement IDs, expected result type, status/failure/skip reason |
| EvidencePlan | ID/version `evidence_plan_v1`, query, ordered steps, requirements, stop conditions, risks, limitations, specialist roles, state/optional execution limit |
| RiskSignal | Chín loại tín hiệu thiếu/mâu thuẫn/ambiguity/quality/scope/period-unit/formula/cross-document/lineage; reason và affected IDs; không score hoặc kết luận dữ liệu sai |
| ExecutionState | pending, ready, running, completed, partial, blocked, failed, skipped |
| StopCondition | all_required_evidence_resolved, missing_required_inputs, unresolved_ambiguity, conflicting_evidence, unsupported_operation, compatibility_gate_blocked, execution_limit_reached |
| SpecialistRole / SpecialistBoundary | Profitability; Liquidity and Leverage; Cash Flow and Earnings Quality. Responsibility/capabilities đã khai báo; không phê duyệt formula/compatibility hoặc xác minh claims |

Output chỉ có boundary `candidate_claim_inputs_for_M6`, không schema CandidateClaim
hoặc Verified Claim Ledger. Chưa có thuật toán chọn specialist.

`QuerySpecification.from_understanding(question, QAUnderstanding, reasons=...)`
nhận structured output M4-05/05a mà không parse lại câu hỏi. Adapter giữ alias,
reporting year/scope, item/formula/period và reasons; document selection vẫn cần
catalog/context thật, không suy filing từ alias/năm. Query M5 cho phép nhiều targets
và formulas mới ở mức nhu cầu; execution chỉ đi qua approved M4 policies.

## Structural validation và execution preflight

`EvidencePlan.model_validate` / JSON round-trip kiểm:

- Unique IDs, existing references và cycles trong steps, requirements **và đồ thị
  producer/consumer kết hợp**; steps theo thứ tự prerequisites.
- Mười tool names từ M4-02/03/04; arguments được validate bằng chính M4 request
  models, expected result type phải khớp response model. Ba operation nội bộ
  `resolve_snapshot`, `check_compatibility`, `prepare_bundle` chỉ là mô tả công việc,
  không phải công cụ M4 mới và chưa có executor.
- Bindings chỉ tới explicit prerequisite và đường dẫn có thật trong response
  schema; arguments chưa có phải có binding, không duplicate/overwrite arguments.
- Không bind document/snapshot/company/item/period/scope/statement mâu thuẫn giữa
  query selectors, steps, requirements, references và citations.
- `found` khác `resolved`; không có trạng thái `verified`. `resolved` chỉ nói nhu
  cầu evidence đã thỏa mãn, không xác minh tài chính. Quality insufficient/conflicted
  không được resolved; usable_with_caveat phải giữ caveat. Financial verification
  flag luôn false. Required evidence/dependencies chưa resolved không được completed;
  optional evidence thiếu không ngăn hoàn tất required work.

`validate_plan(plan, catalog=..., executed_steps=...)` trả `PlanValidation`:

| disposition | Ý nghĩa |
| --- | --- |
| invalid | Không qua structural validation; không được thực thi |
| blocked | Cấu trúc hợp lệ nhưng thiếu inputs/ambiguity/quality/scope/approval/compatibility hoặc hết execution limit |
| valid | Đủ căn cứ để bắt đầu trong catalog hiện tại; chưa đồng nghĩa evidence đã hoàn thành |

Preflight chỉ đọc SnapshotCatalog/M3 retrieval: snapshot selection, usable facts,
source-review conflicts, scope overlay và production metric closure. Formula approval,
operand compatibility, periods/units, nguồn và execution eligibility được giữ theo M4;
không dùng caller boolean để cấp phép. Catalog thiếu → blocked. Explicit stop/risk
conditions không làm tắt safety gate nếu planner bỏ sót chúng trong danh sách.

`bind_step_request(plan, step_id, outputs)` chỉ tạo request M4 từ outputs đã có,
validate concrete response/status/path/type và kiểm lại selector. Không dispatch tool,
không tự chạy dependencies. Schema path hợp lệ vẫn có thể thiếu record/index ở runtime;
khi đó helper từ chối thay vì chọn fallback. M5-03 phải recheck sau binding và gọi M4
production APIs để gate từng invocation; preflight không phải token cấp quyền runtime.
Optional work không là điều kiện khởi động toàn plan; nếu được chọn chạy vẫn cần M4 gate.

## Ví dụ hoàn chỉnh: gross margin BBS 2025

Factory `metric_plan` trong evaluator tạo plan bằng actual selected metric/request
và persisted operands. Full serialized plan cùng citations/caveats/probes nằm ở
ignored `artifacts/evidence/M5-01-scope-final/gross_margin.json`; không commit canonical
records hoặc private dataset. Có thể đọc lại bằng public contract:

```python
import json
from pathlib import Path

from vietnamese_financial_multi_agent.agents import EvidencePlan

payload = json.loads(
    Path("artifacts/evidence/M5-01-scope-final/gross_margin.json").read_text(encoding="utf-8")
)
plan = EvidencePlan.model_validate(payload["plan"])
assert EvidencePlan.model_validate_json(plan.model_dump_json()) == plan
assert len(plan.steps) == 7
assert plan.state == "pending"
```

Question: “Phân tích biên lợi nhuận gộp BBS 2025 và nguồn số liệu.” Selector lấy
document ID thật từ persisted inventory, snapshot `D-01/normalized-v2`, fiscal year2025.

| Step ID | Operation / tool | Prerequisites | Required → output evidence |
| --- | --- | --- | --- |
| select | resolve_snapshot → SnapshotSelection | — | → snapshot |
| gross_profit | find_financial_facts, b02.gross_profit, B02/2025 | select | snapshot → gross_profit |
| revenue | find_financial_facts, b02.net_revenue, B02/2025 | select | snapshot → revenue |
| gate | check_compatibility, gross_margin → MetricSnapshotClosure | gross_profit, revenue | gross_profit + revenue → formula + compatible |
| calculate | calculate_financial_metric → FinancialCalculationResponse | select, gate | formula + compatible → metric |
| lineage | get_metric_evidence_lineage → EvidenceToolResponse | calculate | metric → lineage |
| bundle | prepare_bundle → candidate_claim_inputs_for_M6 | calculate, lineage | metric + lineage → bundle |

Tám requirements có IDs như bảng; formula/compatible phụ thuộc hai operands,
metric phụ thuộc formula/compatible, lineage phụ thuộc metric, bundle phụ thuộc
metric/lineage. Required tất cả; role profitability; cả bảy stop conditions đã khai báo.
Calculate giữ metric ID thật; document/snapshot bind từ
`select.candidates.0.descriptor.{document_id,snapshot_id}`. Lineage bind metric ID từ
`calculate.metric_id`. Evaluator kiểm bindings bằng catalog selection và accepted
calculation response M4-03; không thực thi bước calculate hoặc tạo metric mới.

M4 probes tìm đúng hai operands/trang7; accepted gross margin7,21% và full
FinancialMetricMatch/lineage giữ exact equality với accepted M4-03 evidence.
Plan structurally valid và eligible trong approved same-filing execution profile,
vẫn pending; scope2025 unresolved là caveat, không được tự gán separate/consolidated.
Source grounding/approved arithmetic không phải independent financial verification.

## Real-data validation

Chạy offline, output mới, không ghi đè accepted artifacts:

```console
.venv/Scripts/python.exe scripts/evaluate_m5_01_contracts.py --output artifacts/evidence/M5-01-scope-final
```

| Case | Kết quả contracts và đối chiếu M4/catalog |
| --- | --- |
| Direct total assets2025 | valid; exact fact/sources trang5; scope caveat giữ nguyên |
| Gross Margin2025 | valid; hai operands cùng filing, approved closure, accepted7,21%, sources trang7 |
| Revenue YoY lineage2025 | valid; riêng roles current2025/prior2024 cùng filing; accepted26,71%; lineage exact |
| Multi-step revenue/gross profit | valid; hai independent fact requirements cùng document/snapshot2025 |
| Debt-to-Assets operands/sources | valid; assets trang5, liabilities trang6, accepted59,06%; metric evidence exact |
| Snapshot ambiguity2022 | blocked; original/recovery candidates giữ nguyên, không chọn latest |
| Cross-document2024/2025 | blocked; D03-B10, không tự cấp compatibility |
| Canonical item chưa có data | blocked; ID lấy từ ITEM_RULES thật, không có usable record; M4 probe không found |
| Explicit original2021/2022/2023/2024 | valid, bốn case; selectors thật và sources đúng;2024 scope resolved separate |
| Explicit recovery2022 | valid; recovery identity riêng, không merge/fallback về original |
| Required separate scope2025 | blocked; constraint chỉ ở query vẫn gate đúng, M4 scoped probe unavailable; không giả định separate |
| Period binding cố ý sai | invalid; arguments2024 mâu thuẫn requirement/selector2025 |

Tổng15 cases:10 valid,4 blocked,1 invalid, lấy trực tiếp từ `summary.json`. Persisted years2021–2025
và recovery2022 được đọc thật. JSON round-trip exact; 2.681 protected hashes unchanged,
bao gồm nguồn/PDF/accepted artifacts trong manifest kế thừa M4 và web local.
Facts/evidence/metrics in-memory unchanged; zero Gateway/calculation calls.

Đây là kiểm thử khả năng biểu diễn/validation bằng plans viết thủ công, không
benchmark chất lượng automated planning, financial accuracy toàn PDF hoặc lợi ích
Multi-Agent. Found records, original quality, source limitations và scope reviews
được giữ trong mỗi case JSON, không nâng page-level thành cell-level.

## Engineering validation và quyết định kế thừa

35 focused M5 controls; tổng131 targeted PASS khi chạy cùng M4 financial retrieval,
calculator, evidence tools và QA Gateway. Một Pydantic warning đến từ negative
control invalid_decimal hiện có của M4, không phải failure. Ruff/check format382 files,
planning checker101 tasks và diff check PASS; exact CI ghi ở spec.
CI focused list đã thêm test_agent_contracts; không chạy full regression local.

Trong phạm vi task không phát hiện lỗi M4/data cần sửa. Các lỗi contracts phát hiện
trong triển khai đã sửa: combined dependency cycle; deferred selector guard sau bind;
required scope chỉ xuất hiện ở requirement; controlled source-review conflict;
optional evidence vô tình trở thành global gate. Negative controls giữ các root causes
này. Self-review sau initial commit phát hiện scope cấp query chưa truyền vào
preflight khi step không lặp lại constraint; đã sửa cả query-level/selector-level
scope, thêm hai focused controls và real2025 query-only scope case. Initial CI
success thuộc SHA34a96d1; final implementation/CI ghi riêng ở spec.
Không đổi accepted accounting semantics hoặc production M4 code.

M5-02 kế thừa version/API này, tạo plan bằng structured understanding và catalog;
không suy document từ năm/alias, không coi unknown scope là compatible. M5-03 quản lý
transition và bounded execution; execution limit do caller cấu hình, không đặt ngưỡng
số học mặc định. Formulas ngoài approved policy chỉ biểu diễn nhu cầu, chưa thực thi.

Next action: Tech Lead independent review M5-01; không bắt đầu M5-02.
