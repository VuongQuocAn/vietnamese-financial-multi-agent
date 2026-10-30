# Calculation Lineage và Evidence-Quality Context — M3-06

Đánh giá read-only ngày 30/10/2026 (Asia/Bangkok), reuse accepted M3-05 a4c8ff7.
Đây là khả năng truy nguyên và chuẩn bị inputs, chưa financial accuracy benchmark,
formula executor, financial claim hoặc verified result. Không đổi M1/M2/facts gốc,
compatibility engine, canonical mapping, metadata hoặc policy đã duyệt.

## API và contract

Public qua `vietnamese_financial_multi_agent.evidence`:
`MetricLineage`, `OperandLineage`, `LineageTaskContext`, `trace_metric_lineage()`.

```python
lineage = trace_metric_lineage(metric, graph, facts, evidence, expected_formula=definition)
```

`evidence=()` và `expected_formula=None` mặc định. Caller cung cấp persisted
catalogs có identity thật; expected_formula là definition/version caller muốn
đối chiếu, không tự lookup hoặc phê duyệt policy. API không I/O, không sửa inputs.
JSON round-trip dùng `MetricLineage.model_validate_json()`; không thêm repository.

Result giữ metric ID/request (document/snapshot và requested period từng role),
definition đầy đủ/reference/version/expression/policy; từng binding/candidates,
original CanonicalFinancialFact (raw/normalized value, unit/scale, period/scope,
company, metadata, quality/resolution issues), recovered anchors và exact
FactEvidenceAssociation. Không copy OCR/PDF hoặc toàn table vào lineage/graph.
Anonymous observations vẫn giữ payload và unresolved_identity, không tạo node ID.
Hai observations bằng semantic key/value vẫn độc lập theo document/snapshot/local ID.

Traversal lấy closure incoming `used_in` của metric, các expected operand/candidate
IDs và outgoing `from_source`/`associated_with`; reuse `validate_graph` trên closure.
Kiểm tra thêm missing metric/source node, anchor/edge và formula mismatch; không
rebuild graph để che mất references. Node/edge lỗi ở metric khác không là global
gate. Exact association phải có cạnh và đạt `associate_fact`, cùng trang chưa đủ.
Association chỉ biểu thị exact selector, không chứng minh semantic support.

| Chiều | Representation và ý nghĩa |
| --- | --- |
| Structural | `completeness`: complete / partial / ambiguous / broken; GraphAssessments giữ exact codes |
| Semantic | `compatibility`: fresh `build_metric` → M3-01 `assess_compatibility`, không sửa policy |
| Grounding | Anchors thật và per-role usability levels/statuses/provenance reasons; không nâng page thành cell |
| Operand quality | Mọi original quality_context/issues/caveats/resolution_issues trong observations; usability theo bound role |
| Formula | `reference_example`, chưa có approved execution policy |
| Readiness | Per-role direct display probe, arithmetic preparation, analytical interpretation, calculation, claim verification tách riêng |

Complete: mọi roles/references/anchors trace đủ; vẫn có thể missing company/scope,
uncertain provenance hoặc insufficient/conflicted quality. Partial: missing operands
hoặc source metadata chưa có reference. Ambiguous: nhiều candidate observations,
giữ tất cả, không chọn latest. Broken: known structural violation, dangling/stale
reference, missing node/edge từng tồn tại hoặc formula/identity mismatch. Broken
ưu tiên ambiguous; semantic incompatibility không tự làm structural broken.

`context_limitations` giữ cả company/scope/semantic-role thiếu của từng observation,
kể cả khi compatibility engine chỉ trả missing_operand cho pair chưa đủ. `unresolved`
và task blockers không thay original reason codes trong M2 hoặc compatibility.

Direct retrieval giữ `display_with_caveat` / blocked / undetermined trên mỗi bound
role theo probe M3-05; insufficient/conflicted không bị đổi thành usable. Caller
cần xem cả per-role unresolved/structural assessments trước trình bày citation.
Một role bị chặn không tự chặn display role khác. Arithmetic `prepared` chỉ nói
lineage đủ để bàn giao, còn blockers nằm riêng; chưa cấp phép thực thi.
Analytical interpretation giữ blocked khi thiếu inputs/known incompatibility hoặc
operand display bị chặn, còn lại undetermined; direct_qa usable không cấp phép
analysis. Calculation luôn blocked vì policy chỉ reference_example; claim
verification `not_verified` để M6 xử lý. Không aggregate quality decision,
confidence score, minimum/maximum quality hoặc numeric result. `result=None`,
result_status giữ record M3-05; computed vẫn bị từ chối tại contract M3-05.

## Inventory trực tiếp BBS 2021–2025

Năm trong bảng là thư mục/tên filing do owner cung cấp, chưa verified legal entity
hoặc financial period cho từng ô. Tất cả PDF mở được; PDFium đọc mọi trang và trả
0 text characters, nên phân loại scan/no text layer bằng kiểm tra nhẹ. Không OCR mới.

| Filing year | Đường dẫn tương đối | PDF pages | OCR JSON pages | OCR text/table elements |
| --- | --- | ---: | ---: | --- |
| 2021 | `data/raw/Financial_Report_pdf/BBS/2021/BB2_2021.pdf` | 28 | 28 | 795 / 30 |
| 2022 | `data/raw/Financial_Report_pdf/BBS/2022/BBS_2022.pdf` | 26 | 26 | 575 / 30 |
| 2023 | `data/raw/Financial_Report_pdf/BBS/2023/BBS_2023.pdf` | 29 | 29 | 687 / 36 |
| 2024 | `data/raw/Financial_Report_pdf/BBS/2024/BBS_2024.pdf` | 26 | 26 | 747 / 25 |
| 2025 | `data/raw/Financial_Report_pdf/BBS/2025/BBS_2025.pdf` | 24 | 24 | 745 / 25 |

File 2021 thực tế là **BB2_2021.pdf**, không có BBS_2021.pdf tại folder đó; giữ tên gốc.
OCR persisted tại `data/processed/Financial_Report_OCR/BBS/<year>/ocr_json/`.
Page/year metadata được đối chiếu nhưng chưa so pixel/hash PDF mới với ảnh OCR cũ;
trùng số trang không chứng minh content binding hoặc chất lượng nhận diện.

| Filing year | SHA-256 PDF |
| --- | --- |
| 2021 | bcf81efa8b41b7dc5221ce6cd12b7a62bdbf97ae52983c1e7ae58789e2740353 |
| 2022 | 480854b56c27737c9327e3f7650f8f6fde84fbcaab552b83dbbe72431c9da0ee |
| 2023 | 81d8035271a11a7421141dd8a4ce82c8280add30a8f75db35584c30b57d55a9a |
| 2024 | f4e696a85c65f33cb1a1fa982dbfc6b3dccb5a227d14084d5f02b0d673f57c54 |
| 2025 | 6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1 |

| Coverage | 2021 | 2022 | 2023 | 2024 | 2025 |
| --- | --- | --- | --- | --- | --- |
| PDF | Có | Có | Có | Có | Có |
| M1 raw OCR/text/table payload | Có | Có | Có | Có | Có |
| Full financial discovery inventory | Chưa tìm thấy | Chưa tìm thấy | Chưa tìm thấy | Chưa tìm thấy | Có |
| Structured financial extraction/M2 quality | Chưa tìm thấy | Chưa tìm thấy | Chưa tìm thấy | Chưa tìm thấy | Có |
| M3 canonical financial facts | Chưa tìm thấy | Chưa tìm thấy | Chưa tìm thấy | Chưa tìm thấy | Có |
| Typed M3 text/table evidence | Chưa tìm thấy | Chưa tìm thấy | Chưa tìm thấy | Chưa tìm thấy | Có, selected scope |
| Graph/metrics/lineage | Chưa có inputs | Chưa có inputs | Chưa có inputs | Chưa có inputs | Sáu metrics được trace |

Inventory còn tìm thấy references BBS/year trong classification/crop/reconstruction
M1 pilot artifacts (2021:20, 2022:5, 2023:7, 2024:5 artifact files; có overlap và
manifest-only). Đây là partial component evidence, không full-PDF discovery hoặc
canonical facts. `canonical-report.json` M1-04b là table/crop report, không phải
CanonicalFinancialFact. Không replay M1/M2 để lấp coverage.

Đã kiểm kê `data/canonical`, `data/normalized`, persisted canonical repositories
và runtime attempts dưới `artifacts`: sáu canonical snapshots là ba lượt M3-04 ×
hai W-07 attempts, không sáu datasets độc lập. Bảy runtime result paths đều bind
về PDF 2025 bằng SHA-256 original.pdf; gồm các bản sao validation/checkpoints,
không bảy tài liệu hoặc bảy năm. Detailed paths/identities ở ignored report.
2021–2024: **OCR_AVAILABLE_NO_CANONICAL_FACTS — NOT EVALUATED**, không PDF_ONLY
vì đã có OCR thật. Không year nào chỉ có PDF trong inventory này.

## Real-artifact lineage: sáu records M3-05

Scope cố định: hai W-07 attempts, 356 facts; thêm exact associations từ hai M3-03
W-07 repositories, không nạp M1 quarantine làm SourceFacts. Trace nguyên metric IDs
từ M3-05/review-final, không tự build lại sáu records để cải thiện kết quả.

| Attempt | Metric | Lineage | Resolved / expected roles | Anchor occurrences | Original M2 direct_qa |
| --- | --- | --- | --- | ---: | --- |
| storage | gross_margin | complete | 2 / 2 | 20 | insufficient / insufficient |
| storage | debt_to_assets | partial | 1 / 2; liabilities missing | 9 | assets usable |
| storage | revenue_yoy | complete | 2 / 2 | 20 | insufficient / insufficient |
| fresh-storage | gross_margin | complete | 2 / 2 | 20 | usable / usable |
| fresh-storage | debt_to_assets | partial | 1 / 2; liabilities missing | 9 | assets usable |
| fresh-storage | revenue_yoy | complete | 2 / 2 | 20 | usable / usable |

Tổng **4 complete / 2 partial / 0 ambiguous / 0 broken**; 10/12 roles resolved,
8 distinct observations, 98 anchor occurrences/48 distinct anchors, 68 exact
association occurrences. Cùng nguồn được dùng ở hai metrics nên occurrences khác
distinct; không merge observations giữa attempts. Tất cả recovered anchors giữ
page-level/uncertain, không có cell verification. Sáu formula reference/version
trace được; definition/policy giữ nguyên, cả sáu result=None/not_computed.

10/10 bound role observations giữ nguyên toàn bộ fact/context/quality payload;
M2 decisions 6 usable và 4 insufficient theo role occurrences. Không có conflicted
hoặc usable_with_caveat trong nhóm metric operands này; focused synthetic controls
kiểm tra bảo toàn cả bốn decisions, không giả dữ liệu thật có conflict. JSON restart
exact. Mọi scoped graph assessment valid; completeness partial vẫn thể hiện thiếu
liabilities. **6/6 semantic compatibility undetermined**, không metric nào đã được
phê duyệt execution hoặc verified financial accuracy.

## Coverage financial periods và chuẩn bị nhiều năm

Selected 356 facts có **56 canonical numeric observations**, không phải 56 unique
financial values. B02/B03: 18 observations kỳ 2024 và 18 kỳ 2025 (9 items/kỳ ×
2 attempts); B01: 10 tại 2025-01-01 và 10 tại 2025-12-31 (5 items/date ×2).
Do đó có **hai annual flow periods**, bốn context period labels khi tính cả instant
dates; không phải bốn hoặc năm năm tài chính đã extraction. Không suy kỳ từ
RawPageIdentity.year. Headers giữ nguyên `Năm 2024`, `Năm 2025`, dates B01.

| Chuẩn bị | Evidence thật | Thiếu/blockers |
| --- | --- | --- |
| Revenue YoY 2025/2024 | Một current và một prior revenue/attempt trong cùng document; đã trace | Identity/scope/roles/source/quality/formula policy |
| Gross margin 2024 và 2025 | Gross profit + net revenue đủ candidates có identities cho mỗi năm/attempt | Chưa execution policy/context approval; chỉ sáu metrics gốc được lineage evaluation |
| Debt/assets tại hai dates B01 | Assets có, liabilities canonical không có | `b01.total_liabilities` thiếu; không dùng raw code 300 làm mapping mới |
| Revenue comparison 2024–2025 | Hai observations có nguồn riêng trong report 2025, hai snapshots riêng | Chưa đủ cross-filing identity, source/semantic policy; không numerical comparison output |
| Revenue YoY 2024/2023 hoặc chuỗi 2021–2025 | Chưa đủ canonical inputs | Thiếu financial periods 2021, 2022, 2023; 2024 chỉ comparative trong report 2025 |
| Original filing 2024 vs comparative filing 2025 | Chỉ phía comparative có canonical fact | Không có fact từ PDF 2024; không deduplicate/chọn latest/kết luận restatement |

Không tạo thêm metric record khi thiếu canonical operands. Ignored report giữ
candidate identities cho margin/debt theo mỗi period và snapshot, không numerical
outputs. **Multi-year evaluation NOT PASS**: cần financial extraction cho **4 PDF
2021–2024** trong task được giao sau, gồm source binding/period/quality; OCR cũ có
thể là context nhưng chưa thay thế canonical extraction. Không dùng tên filing để
khẳng định công ty xuyên tài liệu hoặc periods chưa có dữ liệu.

## Blockers theo tác động và policy đề xuất (chưa triển khai)

1. Financial extraction/canonical coverage: thiếu bốn original filings 2021–2024;
   liabilities mapping thiếu ngay trong 2025. Cần task extraction/mapping có nguồn
   và ngân sách riêng, không sửa raw/facts tại M3-06.
2. Semantic context: company_id/scope/role unresolved ở current facts. Company name
   auto-accepted chưa user-confirmed và không verified legal ID. Thiếu scope vẫn
   là blocker dù cùng document. Document-scoped observations chỉ context evidence.
3. Source/M2: mọi selected source page/uncertain; storage B02 insufficient giữ
   nguyên. Page citation có thể phục vụ direct retrieval theo M2 nhưng không
   chứng minh correctness toàn PDF hoặc cell provenance.
4. Execution/analysis policy: reference examples chưa chốt semantics, ordered-year
   policy, denominator-zero, unit conversion, precision/rounding và task quality.

Đề xuất tối thiểu để Tech Lead xem xét trước M4:

| Tình huống | Policy cần phê duyệt | Có thể gỡ chặn gì |
| --- | --- | --- |
| Same document/snapshot | Cho phép document-scoped reporting-entity consistency như evidence riêng khi source binding đúng; không điền legal company_id, không đổi facts | Có thể thay yêu cầu legal ID cho intra-document arithmetic trong policy M4 mới; vẫn cần scope/period/roles/unit và quality phù hợp |
| Cross-document | Cần registry hoặc identity evidence có citation và xác nhận liên kết từng document; filename/ticker/name tự động không đủ | So sánh original/comparative filing sau khi có canonical extraction và identity binding thật |
| Cross-period | Chọn explicit observations/ordered periods và period_type; lưu filing year riêng với financial period/snapshot; không dùng year ảnh | Revenue YoY 2025/2024 trong report 2025 sau khi source/context được chấp nhận |
| Separate/consolidated | Scope có source citation hoặc confirmation; không suy từ same document/name; không combine hai scope | Margin/YoY/debt ratio khi operands cùng scope theo công thức được duyệt |
| Quality theo task | Cho phép display số có page citation/caveat theo M2; arithmetic/interpretation cần policy riêng về uncertainty và issues, không chuyển insufficient/conflicted thành usable | Chuẩn bị direct analytical calculations trên fresh-storage sau khi gỡ context/policy; storage B02 vẫn cần xử lý issues có evidence |

Các policy trên **chỉ đề xuất**; không nới `assess_compatibility()` hoặc cho phép
tính khi status còn undetermined. Same-document evidence tự nó chưa đủ unblock
calculation; cần approved input policy M4 và source-backed context chứ không xóa
reasons để đạt compatible. Không metadata reconciliation subsystem trong M3-06.

## Reproduction và validation

```powershell
.venv/Scripts/python.exe scripts/validate_m3_lineage.py --output artifacts/evidence/M3-06/review-final
.venv/Scripts/python.exe -m pytest tests/unit/test_metric_lineage.py tests/unit/test_derived_metrics.py tests/unit/test_evidence_graph.py tests/unit/test_evidence_contracts.py -q
```

Runner yêu cầu output directory mới, ghi `lineages.json` và `report.json` ignored;
chỉ read persisted artifacts, PDF text layer và OCR inventory, không replay extraction.
68 targeted tests PASS (21 lineage controls +47 M3-04/05/contracts regression).
Missing fact/anchor/edge, dangling used_in, wrong role/document/snapshot,
ambiguous/missing historical operand, company/scope unknown, quality bốn decisions,
page uncertainty, independent original/comparative identity, formula mismatch,
no invented result, unrelated graph isolation, unresolved source metadata đều covered.
Các tests synthetic là engineering evidence; bảng sáu metrics là real-artifact
evaluation, không accuracy benchmark.

171 input files SHA-256 unchanged trong review-final run, gồm năm PDF, 133 OCR JSON,
49-file M3-05 baseline (có overlap) và inputs/catalogs đã dùng; không ghi raw/processed.
Implementation `5300bcff4b49371dcaa5278b444a100b3beeec9a` đã push main;
Ruff/planning/diff PASS. Final run/checks và CI link được ghi tại task evidence.
Zero Gemini/OCR/extraction calls, không full regression/frontend build/Playwright.
CI remote báo riêng theo exact implementation SHA, không suy từ local PASS.

Next action: Tech Lead review M3-06; dừng REVIEW, không bắt đầu M3-07.
