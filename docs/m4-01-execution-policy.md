# M4-01 — Execution compatibility và formula approvals

Ngày02/11/2026 (Asia/Bangkok), baseline main
`8bddff415df98239f507802dc3b55e2e51f2c3b8`. Status **IN_PROGRESS**, chờ chốt
validation/Git/CI trước REVIEW. Phạm vi là eligibility, chưa numeric execution.

## Quyết định thiết kế

Decision ID **`M4-01/design-decision/2026-11-02`**, authority **Tech Lead**,
theo task Owner/Tech Lead đã giao và M4 CONDITIONAL GO. Phê duyệt profile
**`M4/same-document-execution-v1`**, purpose **`formula_execution_compatibility`**.
Đây là authority riêng, không dùng D-02 preparation approval hoặc M3 reference
examples làm execution approval.

Đúng hai operands, semantic items/roles/statements và quan hệ kỳ của formula;
cùng document/snapshot/statement và company có giá trị, khớp nhau. Inputs phải
resolved finite Decimal, không missing/conflicting; unit/currency/positive scale
đầy đủ, nhất quán, không conversion. Mỗi operand có đúng một exact-bound
value-row SourceReview, đúng raw/normalized value, label/header/period, source
selectors và PDF hash; không dùng cùng selector cho value/label/header. Basis
đúng document/snapshot/hash và statement; reused review/basis cần verification
reference. Không insufficient/conflicted ở bất kỳ quality annotation nào, cần
direct_qa usable/usable_with_caveat. Extra resolution issues/inconsistencies veto.

Chỉ waive unresolved `missing_reporting_scope` khi cả hai scope unknown và toàn
bộ điều kiện cùng tài liệu/statement/snapshot đã đạt. Both-known scopes phải
khớp; mixed known/unknown bị chặn. Source uncertainty chỉ waive sau exact value-row
review. Không áp dụng cho cross-document. Giữ nguyên global M3 assessment,
persisted facts, source anchors, quality/caveats; không gán separate/consolidated.

## Formula registry

`configs/d02-analytical-policies.json` giữ nguyên historical baseline, execution
approvals vẫn rỗng. Registry mới **`configs/m4-execution-policies.json`**, version
`M4/execution-registry-v1`; ba policies version **`M4/formula-execution-v1`** dùng
lại PreparedFormulaPolicy/FormulaExecutionApproval/definition_digest SHA256.

| Formula | Biểu thức trước multiplier | Kỳ và guards |
| --- | --- | --- |
| gross_margin | gross_profit / revenue | B02, cùng fiscal year; revenue>0, gross profit được âm |
| debt_to_assets | liabilities / assets | B01, cùng as-of date; assets>0, liabilities>=0 |
| revenue_yoy | (current_revenue - prior_revenue) / prior_revenue | B02, hai fiscal years liên tiếp theo thứ tự giảm dần, cùng filing/snapshot; prior>0, current>=0 |

Arithmetic Decimal precision34, ROUND_HALF_EVEN; multiplier100, percent,
quantum0.01 chỉ ở final output. Không missing/null=0, không đổi currency/unit/scale.
Task này chỉ kiểm inputs/guards, không divide/multiply/quantize hoặc tạo result.

| Formula | SHA256 definition digest |
| --- | --- |
| gross_margin | `f9fb82dfdd9330056e6eafb7fd1518de45ef8899d6d5727038ead52ecb4dc4f7` |
| debt_to_assets | `396bcc315e2c625b650a46917d2e1e1ec2006b4cb4b68e8712387e8cd918838b` |
| revenue_yoy | `612581e60d99c55b5cddbde15fa5875bd1e7d85cbf36e8bbb1740ff295d62e32` |

Mỗi approval có authority/purpose/decision reference và negative-controls reference
tới mục bên dưới, được encode **sau** lượt110 controls/regression PASS thực sự.
Sai version/digest, duplicate cùng formula (kể cả duplicate có digest sai), purpose
hoặc authority sai không được chấp nhận. FormulaDefinition của metric phải khớp
name/expression/operands/relation với approved policy; giữ original M3 definitions
và IDs, không biến reference_example thành execution authority.

## Runtime và tool contracts

`evidence.execution_compatibility` thêm typed, versioned
ExecutionCompatibilityApproval, ExecutionCompatibilityDecision và
ExecutionCompatibilityAssessment. Assessor dùng lại M3 qua D-02 readiness checks,
không lấy preparation_ready/candidate_compatibility làm authority. Trả riêng
global_compatibility, approved_execution_compatibility, execution_profile_approved,
execution_blockers và calculation_eligible. Assessor yêu cầu formula policy để
đối chiếu cả semantic roles/statement, kỳ/type và guards, kể cả khi spec do caller
cung cấp có vẻ compatible. Compatibility assessor riêng luôn giữ
eligibility false vì chưa kiểm snapshot closure/formula. Final eligibility thuộc
typed MetricSnapshotClosure của SnapshotCatalog.

Catalog nhận explicit `execution_approval`, formula policies/approvals và selected
descriptor. Gate cuối là **snapshot closed + execution compatibility approved +
formula approved + preflight clear**. Readiness nested giữ global M3 và D-02
preparation fields, bổ sung execution fields và blockers cuối. Không nhận boolean
`snapshot_closed` hay `formula_execution_approved` do caller tự cấp. Callers thiếu
execution approval giữ eligibility false, kể cả global compatible/preparation
ready/formula approved. Không chọn latest, merge hoặc inherit parent reviews/basis.
DerivedMetric.result vẫn None và result_status vẫn not_computed.

Các lỗi existing implementation được tái hiện và sửa trong phạm vi:

- Mutable formula approval chưa được revalidate purpose/authority; matching từng
  digest có thể bỏ qua duplicate sai digest. Nay revalidate và yêu cầu đúng một
  approval cho formula, exact version/digest.
- Preflight chỉ đối chiếu spec, chưa đối chiếu metric expression. Nay kiểm cả
  FormulaDefinition và guards, kể cả metric đã rebuild có identity hợp lệ.
- Closure phát hiện invalid metric nhưng vẫn đưa vào typed retrieval/lineage,
  gây exception khi definition bị sửa. Nay giữ blocked/invalid_metric_record và
  không tiếp tục lineage của invalid record.
- Preparation+formula approval có thể mở eligibility khi global compatible mà
  chưa có execution approval/closure. Nay preparation luôn chưa đủ để tính.
- SourceReview từng chấp nhận value_selector trùng label_selector nếu cùng nằm
  trong sources. Nay ba selectors phải khác nhau; accepted bindings không đổi.

## Negative controls

**PASS**: lượt đầu110 M4/D-02/D-04 targeted tests trước khi encode approvals;
JUnit ignored `artifacts/evidence/M4-01/negative-controls.xml`, SHA256
`e855465b5535bb6110bc36946d35a9ac6e54645c577dcfec44d75908c1f47e5a`.
Sau các fixes cuối, **246 focused PASS**, JUnit
`artifacts/evidence/M4-01/final-focused-tests.xml`, SHA256
`ad11afa1a2f2cf3a3a8081ed7f677071fef9e62240da00cbe72d9ac63bbd9933`.
Gồm74 M4 cases và M3/D-02/D-04/D-06 regressions liên quan. Hai synthetic documents
độc lập, company/source pages/selectors khác nhau; cả ba formulas/restart/immutability.

Controls: thiếu/sai profile/version/purpose/authority, formula missing/version/
digest/duplicate, cross-document/snapshot/statement/company, scope conflict/mixed,
period/type/nonconsecutive years, missing/ambiguous operands/reviews/basis,
raw/normalized value/selectors/source binding/PDF hash, reuse verification,
unit/scale/currency, unresolved numeric/quality/extra context, nonpositive
denominator/sign guards, partial/blocked closure, broken evidence/lineage và
mutated expression/roles/guards. Kiểm riêng preparation=true+formula-approved=true
vẫn không eligible khi thiếu execution authority; gross loss hợp lệ được giữ.
Đây là engineering controls, không phải full-PDF financial accuracy.

## Real-data acceptance

Runner read-only `scripts/evaluate_m4_01_eligibility.py`; final output ignored
`artifacts/evidence/M4-01/verified/`. Load original15 D-01 metrics, D-02 exact reviews/
bases và D-04 persisted recovery3/descriptors/graph/repositories. Không rebuild
accepted metrics hoặc sửa artifacts, không trộn D-06 projection vào recovery.
Baseline catalog/source/lineage giữ exact với accepted D-04; global18 undetermined.

| Filing / selected snapshot | gross_margin trước→sau | debt_to_assets trước→sau | revenue_yoy trước→sau |
| --- | --- | --- | --- |
| 2021 / D-01/normalized-v2 | 0→1 | 0→1 | 0→1 |
| 2022 / D-01/normalized-v2 | 0→1 | 0→1 | 0→1 |
| 2023 / D-01/normalized-v2 | 0→1 | 0→1 | 0→1 |
| 2024 / D-01/normalized-v2 | 0→1 | 0→1 | 0→1 |
| 2025 / D-01/normalized-v2 | 0→1 | 0→1 | 0→1 |
| 2022 / D-02/recovery-2022-v1 | 0→1 | 0→1 | 0→1 |

Preparation baseline15/15 và recovery3/3; execution eligibility **0→15+3**.
Mỗi formula5 baseline+1 recovery eligible. **Computed0**, không numeric calculation
PASS hoặc verified claim. metrics.json ghi mỗi year/formula/metric/snapshot,
exact operand observations/facts, SourceReview lookup/status/selectors, basis,
global/execution compatibility, formula approval/digest, blockers, source references
và full reviewed lineage/source_fact node IDs.

Regression:29 accepted queries exact (cả citations),36 pairs vẫn undetermined và
execution-approved0;1.177 exact fact lookups, graph và15 original+3 recovery lineages
exact. D-06 QA09 exact found;QA15 hai identities consistent/residual0;100 source
validations exact (65 consistent/35 insufficient). **2.545 protected hashes
before=after**; zero Gateway/Gemini/OCR/extraction. Chưa đánh giá independent gold,
financial accuracy toàn133 trang hoặc doanh nghiệp thật khác.

```powershell
.venv/Scripts/python.exe scripts/evaluate_m4_01_eligibility.py --output artifacts/evidence/M4-01-reproduce
.venv/Scripts/python.exe -m pytest tests/unit/test_m4_execution.py -q
```

## Blocker disposition và bàn giao

D03-B01/B02: runtime đã xử lý, đề xuất DONE sau Tech Lead independent review,
hiện giữ REVIEW. D03-B03: M4-03 executor, dependency explicit M4-01/M4-02;
chưa thực thi. D03-B10 vẫn UNKNOWN, chưa có source-backed reporting scope.
Corrective action trước cross-document approval: đọc cover/audit opinion và
consolidation notes của từng5 PDFs, ghi exact nguồn scope hoặc insufficient.
Không mở B09 restatement/Web integration/independent gold.

Implementation chưa commit; CI chưa chạy. Ruff/planning/diff sẽ chốt trước push.
**Next action duy nhất:** Tech Lead independent review M4-01 sau bàn giao REVIEW.
