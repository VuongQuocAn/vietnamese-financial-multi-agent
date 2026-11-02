# M4-03 — Calculator and Formula Executor

Status: **REVIEW**; baseline main `f433777935f8212d395ee80f0c2d5b5f75cc6805`.
Ngày02/11/2026 (Asia/Bangkok). Phạm vi: ba formulas được duyệt tại M4-01,
same-document/snapshot; không anomaly, cross-document, agents hoặc Web.

## Public API và execution gates

`src/tools/financial_calculator.py`, export qua `vietnamese_financial_multi_agent.tools`:

```python
from vietnamese_financial_multi_agent.tools import (
    CalculateFinancialMetricRequest,
    FinancialCalculator,
)

# catalog đã hydrate persisted facts, metrics, graph, reviews, policies/approvals.
calculator = FinancialCalculator(catalog)
response = calculator.calculate_financial_metric(
    CalculateFinancialMetricRequest(metric_id=metric_id)
)
```

Request chỉ nhận exact metric_id và optional document_id/snapshot_id làm AND guards;
không nhận operand values, formula expression hoặc calculation_eligible từ caller.
Calculator giữ isolated catalog và gọi M4-02 `get_financial_metric`. Chỉ `found`
duy nhất với production `MetricSnapshotClosure.status=closed` và
`calculation_eligible=True` mới đi vào arithmetic. Mọi compatibility, formula
ID/version/digest approval, operands, company/unit/currency/scale/period, source
reviews, accounting basis và lineage gates do production M4-01 closure đánh giá.
Không rebuild metric/graph, chọn latest hoặc lấy facts/reviews từ ancestors.

Các statuses: `computed`, `blocked`, `invalid_inputs`, `unavailable`, `ambiguous`.
`blocked` giữ eligibility blockers và evidence có thể trả được; lookup thiếu/sai
identity guard hoặc snapshot không chọn được trả unavailable; conflict/ambiguity
không tính. Missing/null/zero/negative denominator bị gates chặn với reason cụ thể.
Malformed/non-finite Decimal trả invalid_inputs trước phép so sánh của eligibility;
arithmetic exceptions trả invalid_inputs theo tên lỗi, không làm dừng evaluation.
Mọi failure đều `result=None`, `trace=None`.

## Arithmetic và result contract

Ba branches cố định, không eval/parser và không tạo formula mới:

- gross_margin: gross_profit / revenue ×100; revenue>0, gross profit được âm.
- debt_to_assets: liabilities / assets ×100; assets>0, liabilities≥0, cho phép >100%.
- revenue_yoy: (current_revenue−prior_revenue) / prior_revenue ×100;
  prior>0/current≥0, fiscal years liên tiếp cùng filing/snapshot.

Local Decimal context precision34/ROUND_HALF_EVEN, nhân100 và chỉ quantize0.01
ở final output; output_unit=percent. Không float, làm tròn operands hoặc chuyển
unit/scale. Context độc lập với ambient precision/rounding của caller.

`FinancialCalculationResponse` version `financial_calculation_v1` chứa exact
metric/document/snapshot IDs, formula ID/version/digest, result Decimal string,
full `FinancialMetricMatch` trong evidence và `CalculationTrace` version riêng.
Trace giữ approved policy/approval reference, original operand identities và
SourceFact node IDs, exact Decimal strings, company/context/period/unit/scale,
numerator, ratio và scaled value trước final quantization. Rounding policy nằm
trong `trace.formula`. Evidence giữ nguyên reviewed M3-06 MetricLineage, source
reviews/basis và original PDF/page citations, selectors cùng limitations.

Execution response là artifact riêng. Original `DerivedMetric.result=None` và
`result_status=not_computed` giữ nguyên, kể cả nested evidence. Không persist
execution result vào accepted facts/metrics hoặc thêm graph/storage engine.

Để replay sau restart: hydrate lại cùng accepted records/policies, parse execution
JSON bằng `FinancialCalculationResponse.model_validate_json`, gọi calculator bằng
saved request rồi so toàn bộ response/trace/result. Saved result/boolean không
cấp execution authority; lần replay vẫn đi qua production gates. Muốn tự tính lại
từ trace, dùng operands theo roles và full arithmetic policy trong trace.formula.

## Focused validation

54 calculator cases trên hai synthetic documents độc lập; ba formulas, lợi nhuận
âm, tỷ lệ nợ>100%, YoY âm/zero, zero/negative denominator và nonnegative guards;
null/missing/NaN/sNaN/Infinity/invalid Decimal; units/currency/scale, periods không
trùng/không liên tiếp, mixed document/snapshot/company, unknown/conflicting IDs;
missing/invalid approval, wrong digest/definition, missing execution approval,
review/basis/quality/lineage/closure blockers. Request không nhận caller eligibility.

Tie cases: 201/20000×100=1.005→1.00;203/20000×100=1.015→1.02 và hai tie âm;
large exact integers, trailing Decimal zeros và 1/6; JSON disk round-trip,
rehydrate/restart, returned-object isolation và original input immutability.
Quantization vượt34 digits trả arithmetic_InvalidOperation rồi request khác vẫn chạy.
Synthetic raw numbers tuân thủ SourceReview parser số nguyên VND hiện hành;
không sửa parser/gates để tạo test fractional operands.

Lượt local: **186 PASS** (calculator, typed retrieval, execution, snapshot closure,
reporting scope). Một warning chủ đích do synthetic mutable record chứa chuỗi
invalid thay Decimal trước catalog serialization; API vẫn trả invalid_inputs.
Ruff check/format toàn repository360 files PASS;planning100 và diff check PASS.

## BBS real-data acceptance

Runner: `python scripts/evaluate_m4_03_calculator.py --output artifacts/evidence/M4-03-final`.
Outputs riêng ignored: executions.json (full typed evidence/trace), results.json
(exact IDs/operands/pages), independent-arithmetic.json, negative-controls.json,
retrieval-regression và hashes-before/after/summary.json. Không commit dataset.

18 metrics đã computed, sáu mỗi formula; source pages dưới đây là PDF page index
1-based, năm là filing year (Revenue YoY dùng current/prior trong cùng filing).

| Filing / selection | Formula | Result (%) | PDF pages |
| --- | --- | ---: | --- |
| 2021 original | gross_margin | 8.18 | 8 |
| 2021 original | debt_to_assets | 71.99 | 6,7 |
| 2021 original | revenue_yoy | 6.75 | 8 |
| 2022 original | gross_margin | 9.26 | 7 |
| 2022 original | debt_to_assets | 68.26 | 5,6 |
| 2022 original | revenue_yoy | -14.32 | 7 |
| 2023 original | gross_margin | 9.81 | 7 |
| 2023 original | debt_to_assets | 64.19 | 5,6 |
| 2023 original | revenue_yoy | -20.69 | 7 |
| 2024 original | gross_margin | 10.25 | 9 |
| 2024 original | debt_to_assets | 62.98 | 7,8 |
| 2024 original | revenue_yoy | -0.03 | 9 |
| 2025 original | gross_margin | 7.21 | 7 |
| 2025 original | debt_to_assets | 59.06 | 5,6 |
| 2025 original | revenue_yoy | 26.71 | 7 |
| 2022 recovery | gross_margin | 9.26 | 7 |
| 2022 recovery | debt_to_assets | 68.26 | 5,6 |
| 2022 recovery | revenue_yoy | -14.32 | 7 |

Independent checker đọc exact values từ persisted canonical repositories theo
original observation identities, dùng code Decimal riêng; đối chiếu cả18 metrics.
Ba spot-check thuộc filing2021:

- 42823855975 / 523353809694 ×100 →8.18% (gross margin,p8).
- 284028643923 / 394565027353 ×100 →71.99% (debt-to-assets,p6–7).
- (523353809694−490253981976) /490253981976 ×100 →6.75% (Revenue YoY,p8).

Recovery2022 dùng target snapshot D-04 đã chọn; tất cả operand observations và
citations phải có chính document/snapshot đó. Result bằng original không có nghĩa
dùng chung observation IDs. Original evidence/lineage payload so exact với M4-02.

Final local evaluator PASS:18/18 JSON/restart/recompute exact,18 independent
arithmetic checks và3 real negative controls (bỏ execution approval vẫn đủ số
nhưng blocked/result=None).Regression:1.177 original/recovery +910 corrected
=2.087 exact fact lookups,18 metric retrievals,41 semantic/scope cases gồm partial
scope correction,15+3 eligibility,29 accepted queries,36 cross-document pairs vẫn
undetermined,5 D-07 scope views và D-06 QA09/QA15 exact.Persisted original metrics
computed0 là contract cũ được giữ;execution artifacts riêng computed18.
2.641 protected input hashes unchanged (nested M4-02 regression:2.626);original
facts/metrics/policies/reviews/lineage giữ nguyên;zero Gateway/Gemini/OCR/extraction.
Implementation `fd2ef5c27001a22b70760d52919abd096281aefd` đã commit/push trực tiếp main;
[CI41377619691](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41377619691)
completed/SUCCESS đúng SHA:Python3.12 và Web smoke SUCCESS (typecheck/lint/build/
routes/browser/proxy);full regression manual SKIPPED.Checkpoint tiếp theo chỉ
report/planning và sửa mã hóa tiếng Việt,không gán CI implementation cho SHA checkpoint.

## Disposition và limitations

Không phát hiện cần sửa M4-01 approvals/eligibility hoặc M3 runtime. Numeric
preflight trong calculator xử lý mutable non-finite/invalid records trước gates;
arithmetic errors được trả theo request. Lượt test đầu dùng fractional raw tokens
không thuộc parser số nguyên hiện hành nên bị SourceReview chặn đúng; đổi fixture
sang integer-ratio ties, không nới gate hoặc sửa accepted policies.

Provenance vẫn page-level/uncertain theo nguồn; value_row_verified là controlled
PDF review hiện có, không nâng thành cell-verified/independent gold. Mọi result
giữ financial_fact_verified=False. B10 reporting scope/cross-document restrictions,
EPS/restatement/anomaly và financial accuracy toàn PDF ngoài phạm vi.

D03-B03:đủ sáu criteria executor để **đề xuất DONE**,disposition **REVIEW** chờ
Tech Lead quyết định.Public API tích hợp,ba formulas thực thi thật,production
gates không nhận caller boolean,real18 có lineage/replay,blocked không numeric,
regressions/CI đạt.Không tự nghiệm thu DONE;M4-03 giữ REVIEW.

Next action: Tech Lead independent review M4-03, sau đó M4-04 — Evidence Retrieval Tools.
