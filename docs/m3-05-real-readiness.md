# M3-05 — Analytical readiness trên W-07 persisted artifacts

Đánh giá ngày 29/10/2026 (Asia/Bangkok), scope chốt trước khi đọc kết quả: ba metric
examples × hai attempts BBS_2025 (`storage`, `fresh-storage`), mỗi attempt 178 facts.
Gross margin B02 kỳ 2025; debt/assets B01 tại 2025-12-31; revenue YoY B02 theo thứ
tự 2025/2024, fiscal_year. Đây là reference period rule cho evaluation, chưa accounting
policy executable. Không chọn thêm metrics/subset để tăng PASS.

```powershell
.venv/Scripts/python.exe scripts/validate_m3_metrics.py --output artifacts/evidence/M3-05/review-final
```

Output phải là thư mục mới. `metrics.json`, `graph.json`, `graph-assessments.json`,
`readiness.json` giữ chi tiết identities/candidates/context/M2 annotations/metadata
origin/acceptance và source hashes trong ignored storage; không commit payload tài chính.
`initial`/`final` là các lượt development trước `review-final`. Không OCR/extraction, không replay M1/M2.
Facts materialize thuần bằng adapter M3-02 trên quality projection đã persist.

## Kết quả từng metric/attempt

Mỗi role có đúng một candidate khi ghi số 1; không ambiguous ở cả sáu records.

| Attempt | Metric | Candidate facts theo role | Bound / missing | Structural | Compatibility | M2 direct_qa theo bound roles |
| --- | --- | --- | --- | --- | --- | --- |
| storage | gross_margin | gross_profit=1, revenue=1 | 2 / 0 | complete | undetermined | insufficient / insufficient |
| fresh-storage | gross_margin | gross_profit=1, revenue=1 | 2 / 0 | complete | undetermined | usable / usable |
| storage | debt_to_assets | liabilities=0, assets=1 | 1 / liabilities | incomplete | undetermined | assets: usable |
| fresh-storage | debt_to_assets | liabilities=0, assets=1 | 1 / liabilities | incomplete | undetermined | assets: usable |
| storage | revenue_yoy | current_revenue=1, prior_revenue=1 | 2 / 0 | complete | undetermined | insufficient / insufficient |
| fresh-storage | revenue_yoy | current_revenue=1, prior_revenue=1 | 2 / 0 | complete | undetermined | usable / usable |

10 bound role occurrences, 8 distinct observations (current revenue dùng lại ở
gross margin và YoY mỗi attempt); không deduplicate source/attempt. Tất cả operands
bind có raw/normalized value, page-level provenance và uncertain source status.
Storage B02 bị chặn display theo M2 insufficient dù numeric values có tồn tại;
fresh-storage B02 và assets cả hai attempts chỉ display_with_caveat. Không đổi M2
decisions; usable direct_qa không tự đủ điều kiện analytic calculation.

Exact compatibility reason counts **trên từng record gross_margin hoặc revenue_yoy**,
giống nhau ở hai attempts:

| Code | Occurrences/record | Roles |
| --- | ---: | --- |
| source_reference_uncertain | 20 | 10 trên mỗi role |
| unresolved_operand_context | 2 | mỗi role 1 |
| missing_semantic_role | 2 | mỗi role 1 |
| missing_company_id | 1 | cả hai |
| missing_reporting_scope | 1 | cả hai |

Hai debt_to_assets records trả đúng `missing_operand` (1, role liabilities).
Engine M3-01 chỉ kiểm tra pair khi đủ hai operands; không diễn giải absence của
company/scope/source reasons ở partial pair thành đã đạt. Bound assets vẫn giữ
`missing_company_id`, `missing_reporting_scope` trong evidence context. Storage
B02 còn giữ hai `m2_extraction_issue` mỗi fact; fresh B02 không có hai codes này.

Tổng: **0 compatible / 0 incompatible / 6 undetermined**, 4 complete / 2 incomplete.
Không có numeric output, cả sáu `result=None`, `not_computed`; M4 chưa được thực thi.
Gross/YoY có thể trở thành inputs M4 sau khi gỡ các metadata/evidence/policy blockers;
debt/assets cần thêm canonical liabilities mapping trước. Không có metric nào được
phê duyệt để tính tại checkpoint này. Đây không phải financial accuracy benchmark.

## Metadata audit và trước/sau binding

Đã đọc `document.json` tương ứng chính xác document_id của từng persisted result,
metadata_revision=1 khớp current revision=1 và snapshot values khớp current values.
Cả hai accepted=true, confirmed=false, acceptance_origin=auto; không có user-confirmed
company/scope/roles. Acceptance history và source candidates giữ ở readiness.json.

| Metadata | Evidence đã có | Có thể bind trong M3-05? |
| --- | --- | --- |
| company_name | resolved, auto accepted, PDF page 1 ở storage / page 5 ở fresh; content_id/source citations được persist | Không chuyển thành company_id: chưa có identity policy được duyệt |
| reporting_year/main period | resolved, auto accepted; storage page 1; fresh year page 5, period page 7 | Không dùng document main period ghi đè comparative operands; contexts 2025/2024 và B01 dates đã có sẵn |
| reporting_scope | unresolved, null, không candidate ở cả hai | Không; không suy từ symbol/filename/statement |
| stock_ticker | unresolved/null ở cả hai | Không là identity fallback |
| semantic_role | Không có trong metadata contract hoặc facts | Không gán từ formula role/raw label; canonical mapping không tự chứng minh role policy |
| runtime symbol/year | document runtime hints | Không dùng để xác nhận company/scope hoặc kỳ operand |

Không có field mới đủ căn cứ đúng ngữ nghĩa để bind: **0 bindings applied**,
before=after: sáu undetermined, không thay đổi readiness. Có metadata tốt về tên/kỳ
nhưng metadata ấy chưa giải quyết company identity/roles/scope; không bỏ qua một
accepted scope/identity field có sẵn. Không tạo metadata reconciliation subsystem.

## Nguyên nhân và can thiệp tối thiểu để gỡ chặn

- Dữ liệu/contract: thiếu company_id, scope và semantic role; source page uncertain,
  resolution issues còn nguyên. Cần source-backed identity policy và accepted scope
  evidence; explicit accounting role policy cần được Tech Lead phê duyệt. Thực hiện
  trong follow-up metadata/canonical binding được giao riêng hoặc M4 input policy,
  không tự sửa facts M2/M3-02 tại M3-05. Không chỉ xóa issue để đạt compatible.
- Mapping: B01 code 300 có hai unmapped observations/attempt, nhưng chưa canonical
  `b01.total_liabilities`; chỉ có total_assets tại 2025-12-31/2025-01-01. Cần review
  mapping có provenance trong accounting task được giao; raw code không tự thành operand.
- Formula policy: cả ba vẫn reference_example. M4 phải phê duyệt semantics, ordered
  fiscal-year relation, denominator-zero, ratio/output unit và precision/rounding;
  M3-06 cung cấp lineage/result/quality contracts trước execution. Không thêm công thức
  executable chỉ vì expression đã được ghi.
- Implementation: binding/graph hoạt động trên actual facts; không phát hiện known
  structural violation ở scope này. Không đủ evidence để gọi đây là lỗi executor
  (executor chưa tồn tại). Numeric/source correctness toàn PDF chưa được đánh giá.

## Validation và bảo toàn nguồn

Graph evaluation chỉ facts + metrics, không nạp lại bốn text/table repositories M3-04:
356 SourceFacts + 776 unique anchors + 6 metrics = 1138 nodes; 3588 from_source +
10 used_in = 3598 edges, tất cả structural valid. Counts khác graph M3-04 do scope
khác; không tuyên bố chạy lại full graph evaluation. Existing topology/IDs trên cùng
facts và backward-compatible payload được targeted regression kiểm tra.
Metrics incomplete vẫn có node hợp lệ; financial readiness giữ ở record, không bị
structural valid thay thế. JSON restart exact, deterministic build/order controls đạt.

47 focused tests PASS: 11 M3-05 và 36 graph/contracts regression. Negative controls
bao phủ missing/duplicate roles, multiple candidates/duplicate observations,
document/snapshot isolation/mismatch, wrong statement/semantic role/period pair,
scope/unit/currency/scale, missing company/provenance, unsupported cell provenance,
missing SourceFact, wrong/missing operand edge/domain, computed/LLM number rejection
và existing M3-04 graph. Không dùng synthetic PASS làm financial quality evidence.

49/49 source files hashes unchanged trong M3-03 validation manifest, đã bao gồm
hai result + hai document snapshots W-07; runner kiểm tra lại bốn snapshots này. Không sửa raw/processed,
existing canonical facts hoặc quality output. Không Gemini/OCR/extraction/LLM calls,
không full regression, frontend build hoặc Playwright local. CI tự động theo workflow
hiện có và được báo riêng theo implementation SHA ở task evidence.
