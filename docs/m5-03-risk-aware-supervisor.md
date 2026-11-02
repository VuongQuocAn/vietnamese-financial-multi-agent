# M5-03 — Risk-Aware Supervisor

Status: **REVIEW**; baseline main/origin `03b7d23`, Owner giao02/11/2026.
Implementation chưa commit;19 scenarios và bounded regressions PASS, đang chờ CI
và Tech Lead review. Không gọi Gemini mới.

## API và lifecycle

```python
from vietnamese_financial_multi_agent.agents import RiskAwareSupervisor, SupervisorResult

supervisor = RiskAwareSupervisor(catalog=catalog)
result = supervisor.execute(plan=evidence_plan, max_steps=20)
saved = result.model_dump_json(indent=2)
restored = SupervisorResult.model_validate_json(saved)
```

`supervisor.py` dùng M5-01 typed contracts và các tools M4 hiện có; không thêm
framework, agent hoặc policy tài chính. Public `SupervisorResult`,
`StepExecutionResult`, `ExecutionEvidenceBundle` giữ typed responses và JSON replay.
Request trong trace là JSON của đúng request model trong `TOOL_CONTRACTS`.

Preflight gọi `validate_plan(catalog=...)`; structural invalid trả failed,
global policy block trả blocked, cả hai không gọi tool. Runtime nhận fresh plan,
không tin trạng thái completed/resolved do caller gán sẵn, không tự resume hoặc
retry. Optional missing/conflicted chưa resolve không tự thành global blocker.

Scheduler xét cả prerequisite steps và requirement dependency edges. Mỗi bước
thực thi đi qua pending → ready → running → completed; lỗi trả blocked/failed,
dependent steps skipped, nhánh độc lập tiếp tục. Requirements và state được cập
nhật chung trước khi validate lại EvidencePlan; completed cần required outputs
đã resolve từ payload thật. Hai outputs lineage/citations cùng step không tạo
dependency giả lên một step tương lai.

`max_steps` và `plan.execution_limit` lấy giới hạn nhỏ hơn, tính cả internal steps
và attempted tool calls; không retry. Trace có execution_order, transitions,
bound request, typed response, resolved output IDs, reasons/risks/caveats/latency.
Khi hết budget không chạy bước tiếp. Điều kiện dừng an toàn được ghi kể cả khi
plan không liệt kê hết điều kiện; không cho plan vô hiệu hóa production gates.

## Dispatcher và ba internal operations

Whitelist chỉ gồm bốn operations Planner M5-02 sinh: find_financial_facts,
get_evidence_sources, calculate_financial_metric, get_metric_evidence_lineage.
Tên khác bị chặn trước execution, kể cả tool khác có trong M5-01 registry.
Mọi request qua `bind_step_request()` rồi M4 model validation. Response được
revalidate bằng registry và kiểm tra request identity; found không tự là resolved.

- resolve_snapshot gọi `SnapshotCatalog.select()` và chỉ nhận selected; không
  fallback latest/parent. Toàn bộ selection được giữ trong trace/bundle.
- check_compatibility lấy đúng metric/formula/snapshot và production closure,
  cần calculation_eligible; so exact resolved fact identities với metric operands.
  Không tự cấp approval bằng boolean. Calculator tiếp tục kiểm production policy,
  formula/version/digest, unit/period/scope và approved execution metadata.
- prepare_bundle gom outputs đã completed; giữ facts, calculation responses,
  sources/lineage, citations, closure, original reviews/quality và limitations.
  Không tạo câu trả lời hoặc nhận định tài chính.

Result completed khi required evidence và required work hoàn tất. Optional failure
có thể đi cùng completed; bundle.complete chỉ phản ánh required evidence, optional
absence vẫn hiện ở missing_requirements. Partial giữ phần đã resolve, không đưa
response thất bại vào bundle. Blocked preflight không được lách bằng partial mode.

RiskSignal giữ mã M5-01, không risk score mới. D03-B10, snapshot ambiguity,
explicit unresolved scope, unapproved formula, unit/period mismatch, conflicted
source và incomplete lineage giữ fail-closed. usable_with_caveat theo M4 được giữ
đầy đủ. Mọi result/bundle vẫn `financial_fact_verified=False`; M6 chưa triển khai.

## Gross Margin BBS2025

Plan nguồn: M5-02 offline P05 đã lưu, không dựng lại bằng hardcoded plan.
Trace đầy đủ local ở `artifacts/evidence/M5-03-verified/execution-S03_gross_margin2025.json`.

| Step | Operation | Phụ thuộc | Evidence |
| --- | --- | --- | --- |
| snapshot | resolve_snapshot | — | đúng filing/snapshot2025 |
| op_0_operand_0 | find_financial_facts | snapshot | gross_profit, kỳ2025 |
| op_0_operand_1 | find_financial_facts | snapshot | net_revenue, kỳ2025 |
| op_0_gate | check_compatibility | hai operands | approved formula + closure |
| op_0 | calculate_financial_metric | op_0_gate | calculation + full trace |
| op_1 | get_metric_evidence_lineage | op_0 | lineage + citations |

Reference accepted M4-03: gross_profit32.482.519.668 và revenue450.474.531.227,
cùng kỳ2025, kết quả7,21%; citations trang7 giữ original granularity/limitations.
Formula gross_margin, version `M4/formula-execution-v1`, digest
`f9fb82dfdd9330056e6eafb7fd1518de45ef8899d6d5727038ead52ecb4dc4f7`;
approval reference `M4-01/design-decision/2026-11-02`.
Evaluator so toàn bộ FinancialCalculationResponse với accepted executions.json,
đồng thời kiểm Decimal arithmetic độc lập; không lấy Supervisor làm ground truth.
Thực tế6/6 steps completed,8/8 required requirements resolved,0 missing;
tool statuses found/found/computed/found, gate closed. Final bundle giữ13 citations
khác nhau; calculation response vẫn giữ nguyên danh sách20 citations M4.

## Gemini multi-step và provenance của plans

F01 được đọc nguyên EvidencePlan trong `M5-02-live-final/response-F01.json`:
ba facts BBS2024 (doanh thu, giá vốn, lợi nhuận gộp), sources riêng từng fact,
prepare_bundle phụ thuộc ba sources. Không chỉnh plan hoặc gọi Gemini lại.
F03 metric2023 và F04 recovery2022 cũng dùng nguyên saved live plans.
Evaluator ghi relative path và SHA256 của từng input plan; plan trước/sau unchanged.
F01 thực tế8/8 steps completed: snapshot → op_0(fact doanh thu) → op_1(sources) →
op_2(fact giá vốn) → op_3(sources) → op_4(fact lợi nhuận gộp) → op_5(sources) →
op_6(prepare_bundle). Ba fact steps chỉ cần snapshot; bundle cần ba source steps.
Tất cả transitions pending/ready/running/completed; JSON đầy đủ local ở
`artifacts/evidence/M5-03-verified/execution-S06_multi2024_Gemini.json`.

Giữ M5-02 baseline: offline18/18, fresh live4/6, raw intent5/6, replay6/6.
Các số này không phải Supervisor accuracy và replay không là live6/6.

Snapshot2022 baseline có origin normalized_projection. Ca baseline2022 chọn
snapshot ID tường minh qua PlannerContext; ca recovery dùng saved F04.
Planner không sinh plan cho ambiguity/cross-document; evaluator dùng negative
control M5-01 hoặc explicit cross-document query trên copied P01 để kiểm độc lập
cổng Supervisor, ghi rõ nguồn và không gọi đó là Gemini-generated negative plan.

## Đánh giá thực tế và correctness

19/19 scenarios đạt disposition/correctness mong đợi:13 completed,3 partial,
3 blocked. Trong13 completed có optional failure control; không coi19/19 là
financial accuracy. Runtime missing/conflicted/optional controls dùng typed responses được inject sau
preflight trên BBS plan, phân biệt với execution nguyên dữ liệu thật.

| Scenario | Preflight | Executed steps | Final status | Correct | Grounded | Stop reason |
| --- | --- | ---: | --- | --- | --- | --- |
| S01 tổng tài sản2025 | valid | 3/3 | completed | Có | Có | required resolved |
| S02 doanh thu2024 | valid | 3/3 | completed | Có | Có | required resolved |
| S03 Gross Margin2025 | valid | 6/6 | completed | Có | Có | required resolved |
| S04 Debt-to-Assets2025 | valid | 6/6 | completed | Có | Có | required resolved |
| S05 Revenue YoY2025 | valid | 6/6 | completed | Có | Có | required resolved |
| S06 Gemini F01 multi2024 | valid | 8/8 | completed | Có | Có | required resolved |
| S07 dòng tiền/lợi nhuận trước thuế2025 | valid | 6/6 | completed | Có | Có | required resolved |
| S08 Gemini F04 recovery2022 | valid | 7/7 | completed | Có | Có | required resolved |
| S08b baseline2022 explicit ID | valid | 6/6 | completed | Có | Có | required resolved |
| S09 snapshot2022 ambiguous | blocked | 0/2 | blocked | Có | — | unresolved_ambiguity |
| S10 cross-document2021/2025 | blocked | 0/3 | blocked | Có | — | compatibility_gate_blocked |
| S11 consolidated scope2025 | blocked | 0/3 | blocked | Có | — | compatibility_gate_blocked |
| S12 injected runtime missing | valid | 6/8 | partial | Có | Phần giữ lại | missing_required_inputs |
| S12b injected runtime conflict | valid | 6/8 | partial | Có | Phần giữ lại | conflicting_evidence |
| S13 injected optional sources missing | valid | 3/3 | completed | Có | Fact | required resolved |
| S14 budget3 | valid | 3/6 | partial | Có | Operands | execution_limit_reached |
| S15 Gemini F03 metric2023 | valid | 6/6 | completed | Có | Có | required resolved |
| S16 equity2021 | valid | 3/3 | completed | Có | Có | required resolved |
| S17 operating cash flow2023 | valid | 3/3 | completed | Có | Có | required resolved |

required resolved là `all_required_evidence_resolved`. Grounded chỉ nói phần
evidence thực sự trả về đã so nguồn, không có nghĩa verified fact hoặc partial
bundle đầy đủ. S12/S12b có2 skipped steps (sources của fact lỗi và bundle), hai
nhánh fact/sources độc lập vẫn completed. S14 có3 skipped steps và không gọi gate,
calculator hoặc lineage sau budget. S09–11 có0 tool calls. S13 required fact resolved,
optional citations missing và risk không blocking; fact vẫn giữ original citations.

Artifacts cuối ở `artifacts/evidence/M5-03-verified/`: từng plan/execution/score,
scores.json, independent-checks.json, implementation.json và hash manifests.
S01/S02 tái dùng immutable traces từ đợt writer lỗi cùng Supervisor source hash,
đối chiếu độc lập lại;17 scenarios còn lại thực thi trong đợt verified. Không đếm
việc đọc lại hai traces thành hai lần execution mới.

Completion ở `artifacts/evidence/M5-03-complete/summary.json` có exit0:
19/19 traces được đọc lại/đối chiếu cùng Supervisor hash, không tạo19 executions mới.
Đợt verified đã PASS bounded M4, QA36 và14 contract cases trước lỗi lookup file cuối;
checkpoint recovery ghi rõ assertions đã hoàn tất. Completion tái dùng các phase đó,
chạy nốt invalid_period_binding và xác nhận15cases exact,3.231 hashes unchanged.
Không sửa original artifact để ép validation PASS.

Reference độc lập gồm persisted facts và sources, original source reviews,
accepted M4-03 calculations, M4-04 metric-lineages. So exact số/formula/operands/
periods/identities/quality/caveats/trace/citations; lineage response khớp artifact M4.
Không coi execution success hoặc synthetic smoke là financial verification.

```powershell
.venv/Scripts/python.exe scripts/evaluate_m5_03_supervisor.py --output artifacts/evidence/M5-03-new
.venv/Scripts/python.exe -m pytest tests/unit/test_supervisor.py -q
```

Output folder phải mới, ở dưới artifacts/evidence; không overwrite accepted files.
Traces/plan JSON/hash manifests ở local ignored storage, không commit dataset.

## Lỗi phát hiện và giới hạn

Scheduler cần phân biệt requirement dependency nội bộ trong cùng step với producer
ngoài step (lineage + citations). Đồng thời phải xét evidence edges khi không có
explicit prerequisite tương ứng; tests kiểm bundle được schedule sau producers.
Hai vấn đề được xử lý trong Supervisor, không cần đổi contracts/materializer M5-01/02.
Selector được kiểm tiếp trên fact payload, không chỉ trên deferred request; false
found với sai kỳ bị chặn. Không tin response success nếu thiếu trace/lineage/citations.

Lần chạy engineering đầu phát hiện lỗi đọc status của internal closure như tool
response; đã giới hạn success-status check theo đúng response type và test lại.
Lần evaluator đầu dừng trước execution do nhãn original không khớp snapshot origin;
đã chọn explicit ID. Đợt run2 dừng sau S01 để dùng fix runtime cuối. Đợt final
dừng sau S02 vì save helper không cho ghi đè scores.json; đã sửa lưu score riêng từng
ca và aggregate một lần, tiếp tục vào verified với17 executions mới. Giữ các thư
mục lỗi trước; không công bố chúng như các đợt evaluation hoàn tất.
Lookup invalid_period_binding trong manifest khác tên file invalid-period-binding;
đã sửa đúng đường dẫn và kiểm targeted case cuối qua completion. Không sửa reference.

Chưa specialists/adaptive routing/claim verification/Web UI. Runtime hiện chỉ hỗ trợ
bốn operations M5-02, không resume state đang chạy, không tạo financial claims.
Preflight/closure trên catalog đầy đủ còn tốn thời gian; latency được giữ trong traces.

## Validation và bàn giao

8 Supervisor tests PASS; 172 bounded tests contracts/Planner/M4/Gateway PASS.
Bounded real regression:18calculations (full response + independent arithmetic),
29queries,36undetermined pairs,D-06/D-07,QA36,M5-01 15cases exact;139text/24tables/
2.973anchors/18lineages giữ nguyên.3.231 protected hashes unchanged, bao gồm Web local.
Ruff modified files/planning101/diff PASS; không full regression, OCR/extraction
hoặc live Gemini. Đang chờ commit/push và CI đúng implementation SHA.

Next action: push implementation main và kiểm CI đúng SHA.
