# D-04 — Khép kín snapshot và truy xuất source review

Ngày 01/11/2026 (Asia/Bangkok). Status **REVIEW**, chờ Tech Lead nghiệm thu;
baseline main `74ddea30891a61ba5a84ae3fbc61a2e61c06aa05`. Implementation
`73e2f9e9cc412dc86a2dbf7e45903d8a6449d5dd` đã push main;
[CI41311527741](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41311527741)
completed/SUCCESS đúng SHA; Python3.12 và Web smoke đều SUCCESS, full unit regression
SKIPPED. Checkpoint sau chỉ docs/planning, không gán CI cho SHA checkpoint. D03-B04/B08
được sửa trong runtime và có evidence review; chưa tự chuyển DONE.

## Runtime tổng quát và contracts

`src/evidence/snapshots.py` cung cấp `SnapshotDescriptor`, `SnapshotCatalog`,
`SnapshotSelection`, `MetricSnapshotClosure`, `ClosureIssue` và
`rebuild_snapshot_metrics`. Catalog nhận records do caller cung cấp; không đọc
folder, suy doanh nghiệp/năm hoặc mặc định chọn latest. `select(document_id)`
trả ambiguous khi có nhiều candidates; `select(document_id, snapshot_id)` pin
chính xác một snapshot. Parent lookup cùng document, kiểm hash, duplicate, missing
parent và cycle bằng vòng lặp không giới hạn một recovery level. Parent chỉ biểu
diễn provenance; không lấy facts/reviews/basis từ parent để điền thiếu.

Closure trả `closed`, `partial`, `blocked` cùng reason codes và affected references
(metric ID, observation identity hoặc source selector). Kiểm request/binding/catalog
identity, toàn bộ operands, exact source/document evidence associations, source
reviews, basis, graph `from_source`/`associated_with`/`used_in` và lineage. Không
rebuild graph trong assessor để che missing edge. Missing dependency giữ partial;
identity/hash/duplicate/conflict và broken graph bị blocked. `closed` chỉ nói đủ
dependencies; `preparation_ready` còn đi qua approved profile và quality; execution
vẫn theo global compatibility/formula approvals. Không thay các policies này.

Builder nhận danh sách `(FormulaDefinition, operand_periods)` và selected descriptor,
gọi existing `build_metric`; caller gọi existing `build_graph`. Runtime duyệt
`metric.operands`/contract roles, không phân nhánh theo tên công thức. Contract
`OperationCompatibilitySpec` đã nghiệm thu hiện giới hạn đúng hai operands; D-04
không mở rộng global policy. Tests dùng hai bộ role names khác nhau; real regression
dùng cả ba metric definitions hiện có. Nếu contract sau này mở rộng số roles,
closure không có giả định hai/sáu operands; compatibility engine vẫn cần task riêng.

`src/evidence/source_reviews.py` cung cấp typed `SourceReviewView`,
`SourceReviewLookup`, `ReviewedMetricLineage`, `OperandSourceReview` và generic
`bind_source_review`. `EvidenceRetrieval.get_source_review(observation)` trả exact
document/snapshot/local identity; không tìm parent hoặc dùng numeric equality.
Status phân biệt page_resolved/value_row_verified/unverified/source_inconsistent/
source_missing. View giữ original sources, anchor statuses, verification method/
reference, selectors, coverage count và original quality caveats. Coverage đếm
selectors value/label/header đã review, không gọi mọi context anchor là verified.

`get_reviewed_lineage(metric_id)` là optional wrapper typed của existing lineage;
`SnapshotCatalog.reviewed_lineage(descriptor, metric_id)` thêm parent chain đã
kiểm tra. Snapshot request phải khớp. Original `get_fact/get_sources/get_lineage`
và original citations không bị thay thế; page/uncertain vẫn page/uncertain. Không
thêm edges nối facts giữa snapshots, không gán cell geometry hoặc financial gold.

`SourceReview` và `AccountingBasisReview` thêm optional verification reference và
parent provenance. Evidence có thể reuse sau source checks, nhưng binding mới có
verification record mới. Reused review thiếu explicit verification bị inconsistent;
reused basis thiếu record bị closure blocked. Existing reviews giữ nguyên.
`scripts/evaluate_d02_blockers.py::bind_review` dùng wrapper tới generic binder,
không duy trì thuật toán binding riêng trong evaluation.

## Inputs để dùng một PDF mới

Không cần sửa runtime để nhận doanh nghiệp/năm/snapshot mới. Caller cung cấp:

1. Document identity theo content SHA (`sha256:<PDF hash>`), PDF SHA-256, snapshot
   identity, origin và explicit parent snapshot identity nếu có. Persist descriptors
   như metadata sidecar riêng; giữ toàn bộ ancestors cần trace.
2. `CanonicalFinancialFact` với observation identities, canonical mapping, semantic
   role, period/type/statement, units/scales, raw/normalized values và M2 quality;
   `TextEvidence/TableEvidence` cùng exact source anchors/selectors. Dùng existing
   repositories/adapters, không suy schema từ tên PDF.
3. Controlled source readings với PDF/page/render hash, value/label/header/period,
   selectors; basis review có source quote cho statements được hỗ trợ. Với snapshot
   mới phải kiểm binding theo source thực và persist record riêng. Generic binder
   kiểm selector uniqueness/row/column/payload; caller chịu trách nhiệm đối chiếu
   PDF/render/hash trước khi cung cấp reading. Binder không tự chứng minh ảnh đúng.
4. Formula definitions/version, explicit kỳ theo từng role và policies/approvals
   đã được duyệt. Thiếu mapping/quality/reviews/basis/approvals trả blockers đúng
   contract; việc thêm doanh nghiệp không tự cấp approval mới.
5. Metrics build lại từ selected facts; graph từ existing builders. Khi restart,
   nạp descriptors, repositories, reviews/bases, metrics và persisted graph vào
   catalog. Assessor giữ graph caller cung cấp để phát hiện broken references.

Không thêm workflow engine, database, plugin architecture, Web API hoặc agent.

## Evaluation BBS riêng và real-data before/after

Chỉ `scripts/evaluate_d04_closure.py` chọn BBS 2021–2025, D-01/D-02 ignored paths
và recovery mẫu. Runtime không import script/config/artifact path này. Mẫu/queries
D-03/D-02 giữ nguyên. Không Gemini/OCR/extraction hoặc xử lý lại 133-page pipeline.

Controlled visual read mới từ original PDF 2022: trang PDF 5 (assets), 6
(liabilities), 7 (net revenue hai kỳ và gross profit), 9 (basis VAS/TT200, accrual,
historical cost). Năm observations phục vụ sáu operand occurrences; normalized
values, periods, units/scales, exact source selectors và current quality khớp.
Không suy same value = same source. Recovery B01/B02 giữ request IDs và source
references; source metadata thiếu hai annotations projection cũ (`d01_binding`,
`parent_snapshot`). Verification records liệt kê parent-only metadata, kiểm toàn
bộ metadata còn lại và giữ parent provenance thay vì sửa facts/review cũ.

Tạo năm SourceReviews và một AccountingBasisReview mới exact-bound recovery;
reuse source evidence sau controlled read, kèm verification reference riêng và
`reused_from`/`reused_from_snapshot`. Giữ 25 original reviews và hai recovery OCF
reviews đã có: catalog lookup đủ 32 bindings. Persist corrected projection bằng
existing CanonicalFactRepository/DocumentEvidenceRepository, build ba metric IDs
mới từ definition/period contracts và graph/lineage mới. Không edit IDs/refs cũ.

| Check | Before | After |
| --- | ---: | ---: |
| Original 2022 preparation-ready | 3/3 | 3/3 |
| Recovery 2022 preparation-ready | 0/3 | 3/3 |
| Recovery old/new operand references resolve | 0/6 | 6/6 |
| Recovery source-review closure cho metrics | thiếu năm bindings | năm exact-bound reviews mới |
| Recovery accounting basis | thiếu binding | một binding mới verified |
| Recovery metric/lineage closure | broken selected view | 3/3 closed, exact |
| Baseline preparation-ready | 15/15 | 15/15 |
| Calculation eligibility | 0 | 0 |

Local real-artifact evidence tại ignored `artifacts/evidence/D-04-review/`:
`summary.json`, `before.json`, `verification-records.json`, `basis-verification.json`,
`source-reviews.json`, `accounting-basis-reviews.json`, `metrics.json`, `lineages.json`,
`snapshots.json`, `catalog.json`, `graph.json`, hai existing repository outputs,
source renders và hashes-before/after. Các lần runner trước giữ riêng; dùng
`D-04-review` cho kết luận cuối, không lấy partial run làm PASS.

Baseline 15 readiness dicts và 15 lineages khớp exact accepted persisted evidence,
gồm bounded regression 2021/2023/2024/2025. 29 fixed queries và 36 cross-year pairs
không đổi; 1.177 exact fact lookups gồm 981 original + 196 recovery giữ độc lập.
Không chọn snapshot trả ambiguous; original vẫn truy xuất được. Catalog/reviewed
lineage rebuild từ persisted descriptors/facts/evidence/reviews/basis/metrics/graph
khớp sau restart. 2.437 input hashes trước=sau, gồm PDF/OCR/extraction/persisted
inputs/policies/local web file trong accepted bounded scope; zero Gateway calls.

## Validation và giới hạn

Local 122 focused tests PASS: canonical facts, document evidence, graph, metrics,
lineage, retrieval, approved preparation và 18 D-04 generic controls. Generic fixtures
có hai documents độc lập, tám snapshots (original, recovery v1/v2, sibling attempts),
hai bộ role names và source pages/selectors riêng. Controls bao gồm parent-review
không tự kế thừa, wrong identity/hash/row, same value different selector, missing/
duplicate/conflicting reviews, missing/ambiguous fact, missing/wrong basis, missing
graph/evidence edges, cycles/missing parents, ambiguous selection và quality veto.
Ruff lint/format, planning checker và diff check chạy trước bàn giao.

Đây là **generic contracts PASS với synthetic tests và real BBS regression PASS
trong phạm vi đã đánh giá**. Chưa kiểm chứng mọi mẫu PDF, full-PDF numeric accuracy,
independent human gold hoặc chất lượng tài chính doanh nghiệp khác. Closure không
chứng minh semantic compatibility của cross-document comparisons.

## Tác động tới blockers còn lại

- D03-B01/B02: giữ global undetermined và execution approvals rỗng; eligible 0.
- D03-B09: source overlays/snapshot identities hỗ trợ downstream chọn bằng chứng;
  36 pairs giữ undetermined, không cấp cross-document compatibility.
- D03-B10: missing reporting scope và quality caveats giữ nguyên; approved preparation
  profile chỉ áp dụng như cũ, không suy separate/consolidated.
- D03-B12: backend consumer có typed catalog/retrieval/lineage, chưa tích hợp Web.

Next action: Tech Lead independent review và nghiệm thu D-04; không bắt đầu D-05/M4.
