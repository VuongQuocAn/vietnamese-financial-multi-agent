# D-03 — Điều tra blockers toàn hệ thống và kế hoạch khắc phục

Ngày 31/10/2026, Asia/Bangkok. Trạng thái **REVIEW**; Implementation Engineer đề
xuất severity, Tech Lead independent review và quyết định corrective tasks.
Baseline `fe1df29916d53d12ca8f0b4a636a7551895b9db1`, sau accepted D-02 final fix
`f80b84254765d9a5e73208e80f8fb7c577b72668`. Không sửa production code, policy,
financial facts hoặc dữ liệu. Không Gemini/OCR/extraction, không full regression.

## 1. Executive summary

Phát hiện **16 mục: 14 CONFIRMED, 1 PROBABLE, 1 UNKNOWN**. Trong đó 15 mục còn
mở; một lỗi layout đã được D-02 recovery xử lý trong snapshot mới. Phân loại sơ
bộ: **P0: 0; P1: 12; P2: 4**, tính cả mục đã xử lý. Không có bằng chứng để báo
accuracy toàn dataset hoặc gán mọi limitation thành lỗi extraction.

Năm root causes/nhóm ảnh hưởng lớn nhất:

1. **Snapshot recovery không khép kín dependency**: ba metrics/5 value reviews và
   accounting-basis review của 2022 vẫn trỏ snapshot gốc. View retrieval recovery
   không resolve sáu operand references cũ; readiness trên operands recovery là
   **0/3**, dù selected baseline vẫn 15/15 preparation-ready.
2. **Execution chưa được cấp phép và chưa có executor**: 15 metrics đều vượt
   preflight, nhưng thiếu formula approval và execution compatibility. Preparation
   approval không thay thế hai quyết định này; không phải thiếu operands.
3. **Extraction không kiểm tra độ đầy đủ dòng**: PDF B02/2024 có EPS, payload dừng
   ở lợi nhuận sau thuế, mất hai value slots. Các kiểm tra 981 exact lookups không
   thể phát hiện dòng chưa được tạo thành observation.
4. **Catalog và validation registry còn phạm vi pilot**: 748 unmapped slots là
   financial items thuộc 79 cặp statement/code; balance rule vẫn báo trang nguồn
   vốn chưa ở pilot mặc dù cả năm filing đã có dòng 440.
5. **Web chưa nối M3/D-01/D-02**: GET thực tế chỉ có một W-07 snapshot/178 items;
   D-01 snapshot bị trả `404 attempt_not_found`. SourceReview, readiness và
   lựa chọn canonical snapshot chưa có adapter/API/UI.

Restatement là rủi ro đã có nguồn thật: PDF 2025 trang 23 ghi rõ EPS so sánh 2024
được trình bày lại do trích quỹ. EPS chưa mapped và EPS/2024 còn bị bỏ sót; bởi
vậy **36 equal pairs không bao phủ restatement này**. 36 cặp chỉ gồm 20 B02 và
16 B03, không có B01 hoặc EPS. Cùng legal entity không chứng minh cùng scope.

**M4 hiện NO-GO để tuyên bố financial execution sẵn sàng.** Có thể Conditional Go
cho việc triển khai M4 sau khi Tech Lead nghiệm thu kế hoạch và chốt execution
policy + snapshot contract tối thiểu. Executor là output của M4, không phải yêu
cầu xây executor trước khi được giao M4. Không cần map toàn bộ 816 observations.

## 2. Phạm vi, dữ liệu và tái hiện

Một nguồn dữ liệu gốc, hai cách chọn snapshot được tách rõ:

- **Baseline**: `artifacts/evidence/D-01/evaluation/{2021..2025}/`,
  `normalized-result.json`, `canonical/canonical-facts.json`; mỗi năm
  `D-01/normalized-v2`. 981 observations, 165 mapped/816 unmapped, 881 numeric.
- **Effective retrieval D-02**: thay toàn document 2022 bằng
  `artifacts/evidence/D-02/recovery-2022/normalized-result.json`, snapshot
  `D-02/recovery-2022-v1`; vẫn 981 observations. Không ghép duplicate snapshots
  rồi tự chọn một kết quả. 15 persisted metrics vẫn thuộc baseline.
- Reviews: `D-02/source-reviews.json` (25), `accounting-basis-reviews.json` (5),
  `recovery-source-reviews.json` (2); policy `configs/d02-analytical-policies.json`.
- PDF identity lấy từ `D-01/inventory.json`: 2021 `bcf81efa…`, 2022 `480854b5…`,
  2023 `81d80352…`, 2024 `f4e696a8…`, 2025 `6c261d2a…`; đầy đủ SHA trong inventory.
  Mọi page trong báo cáo là **PDF page, bắt đầu 1**, không phải số trang in.

Chạy diagnostic ở root, dùng một output directory **chưa tồn tại**:

```powershell
.venv/Scripts/python.exe scripts/diagnose_d03_blockers.py --output artifacts/evidence/D-03-reproduce
```

[Script](../scripts/diagnose_d03_blockers.py) chỉ đọc repositories/records/reviews,
gọi các hàm assessment thuần và GET ASGI. Không vào API lifespan, không mở
worker, không load keys, không gọi Gateway. Chỉ render thêm PDF 2025 trang 23 để
đọc note restatement. Output nghiệm chứng cuối:
`artifacts/evidence/D-03-final-audit/` (**ignored, không commit dataset**):

- `observations.json`, `effective-observations.json`: exact observation identity,
  code/label/year/period/value, reasons, source binding, review status.
- `unmapped-groups.json`: từng statement/code/raw label/year/period/numeric,
  structural/subtotal/detail candidate và observation IDs. Không chỉ tổng số.
- `quality-by-year-statement.json`, `metrics.json`, `snapshot-closure.json`,
  `cross-year.json`, `validation.json`, `arithmetic-signals.json`.
- `qa.json`: 20 structured questions, answer data/raw values, exact fact references,
  citations, gates và outcomes. Giá trị tài chính chi tiết chỉ ở ignored outputs.
- `web.json`: HTTP status/body, default storage, document/attempt IDs, route list;
  `visual-sources.json`, `2025-23.png`; `summary.json`, hashes trước/sau.

So sánh trực tiếp lại readiness/cross-year với persisted D-02-final; exact retrieval
981/981. **2.421 input hashes trước = sau**, gồm accepted D-02 scope 2.406 paths,
D-02-final outputs, policy và web storage/local file. Đây là phạm vi inputs đã dùng,
không phải hash mọi dataset nghiên cứu không liên quan. Không thay evidence cũ.

Các lượt diagnostic ban đầu chỉ tạo ignored outputs riêng; có một lượt dừng ở bước
hash do phạm vi quá rộng và một lượt lỗi resolve `review_reference` dạng JSON:index.
Script cuối hash accepted scope và resolve ảnh review theo document/page đúng như
D-02. Các lỗi runner này không được tính là lỗi production hoặc bằng chứng tài chính.

## 3. Blocker Registry duy nhất và resolution plan

Stable IDs dưới đây không phải task IDs. `TODO`: đề xuất còn mở, chưa được giao sửa;
`DONE` ở D03-B16 chỉ ghi disposition đã có trong accepted D-02. Severity P1 chặn
workflow core/claim tương ứng; P2 giới hạn phạm vi mở rộng hoặc chất lượng projection.
Effort XS/S/M là ước lượng tương đối. Chi tiết reproduction/first point/risk ở §4–§8.

| ID | Root cause / điều kiện gây chặn | Confidence | Severity | Affected components / impact | Fix proposal cụ thể | Effort | Dependency | Acceptance test | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D03-B01 | `assess_analytical_readiness` bắt global compatible cho execution; approval hiện có chỉ purpose preparation, không có execution profile xử lý scope/source exception | CONFIRMED | P1 | 15/15 metrics, financial tools | Chốt record execution compatibility riêng, giới hạn same document/statement/snapshot, reviewed operands/basis; evaluator nhận record đúng purpose, giữ global assessment gốc | S | Tech Lead quyết định scope execution | 15 selected baseline metrics clear compatibility execution nếu approved; cross-doc/known conflict/quality blocked vẫn từ chối | TODO |
| D03-B02 | `formula_execution_approvals=[]`; ba version/digest không có matching approval | CONFIRMED | P1 | 15 metrics/3 formulas | Tech Lead duyệt/bác semantics, denominator/sign/rounding và negative controls; persist explicit formula/version/digest/authority/reference, không đổi status cờ | XS | Tech Lead review definitions | 15 preflight clear + matching approvals; wrong digest/version hoặc denominator không hợp lệ vẫn blocked | TODO |
| D03-B03 | `src/tools` chưa triển khai; DerivedMetric chỉ cho result None/not_computed | CONFIRMED | P1 | M4 execution; anomaly QA chưa có rule | Trong M4 được giao, thêm executor Decimal ba formulas sau gates; anomaly chỉ thêm khi có rule/threshold/baseline được duyệt, hoặc trả unsupported rõ ràng | M | B01, B02, B04 | Tính ba metric types với citations/lineage từ selected real operands; invalid inputs không có numeric answer | TODO |
| D03-B04 | Evaluator recovery đổi snapshot của cả 2022, nhưng reviews/basis/metrics vẫn bind snapshot gốc | CONFIRMED | P1 | 3 metrics, 5 reviews, 1 basis review; 6 operand occurrences không resolve trong effective view | Thêm snapshot catalog/selection giữ original và recovery; pin metric vào snapshot đóng dependency. Nếu chọn recovery cho metric: rebind reviews/basis sau exact source check và build metric/lineage mới, không sửa identity cũ | S | B08; không cần Gemini | Với từng snapshot được công bố ready: mọi metric reference resolve, reviews/basis khớp; 2022 không còn 15/15 baseline bị dùng nhầm cho recovery | TODO |
| D03-B05 | ITEM_CATALOG chỉ 16 IDs; 748 financial slots/79 statement-code pairs không có rule | CONFIRMED | P1 | QA nợ ngắn hạn, validation và expanded analysis | Ưu tiên rules B01 100/200/310/440, B02 01/02, B03 50/60; code + source-backed labels/statement, snapshot projection mới; không map header/signature | S theo nhóm | B06; Tech Lead chốt IDs/labels | QA09 tìm đúng 310; balance/asset decomposition đủ mapped operands; negative code/label/statement không nhầm | TODO |
| D03-B06 | Header filter chỉ bỏ “chỉ tiêu/mã số/thuyết minh”, bỏ lọt “Thuyết số”; financial projection còn giữ section/signature | CONFIRMED | P2 | 25 note slots (20 unmapped), 48 structural slots; 10 numeric note references | Sửa phân loại header role tại validate_automated_extraction và projection: note reference/text giữ ở table evidence, không tạo monetary slot; lưu snapshot mới | S | Không đổi raw/M2 cũ | PDF2021 B01 p6 không tạo 25 slots “Thuyết số”; source code 411a/421b vẫn giữ financial; structural count không làm tăng mapping denominator | TODO |
| D03-B07 | B02/2024 source có EPS nhưng response payload kết thúc ở code60, limitations rỗng; chưa có coverage check dòng cuối | CONFIRMED | P1 | Mất 2 EPS slots; exact lookup không thấy omission | Thêm source/table coverage review cho p9 và recovery riêng đúng dòng/trang; đối chiếu source inventory trước projection. Chưa kết luận vì sao model bỏ dòng | S | B13 sampling; không cần chạy lại PDF khác | Source code70/current+comparative xuất hiện trong attempt mới, values/labels/headers được đối chiếu PDF; giữ original attempt | TODO |
| D03-B08 | Page anchors uncertain theo thiết kế; SourceReview overlay chỉ bao phủ mẫu, retrieval/lineage không nhận overlay | CONFIRMED | P1 | 981 page-level; baseline25 reviewed, effective22; 61/72 cross-year operand occurrences chưa reviewed | Adapter trả original citations + exact-bound review status riêng; chọn/review thêm đúng operands được dùng, validate selectors/hash/row, không nâng thành cell provenance | S | B04 cho snapshot chọn | Baseline25 và recovery2 được lookup đúng identity; mismatch vẫn blocked; citation hiển thị original page/uncertain và review level riêng | TODO |
| D03-B09 | Bộ 36 pairs chỉ dùng mapped IDs; EPS/restatement notes chưa có semantic binding/record | CONFIRMED | P1 | Cross-document QA, EPS comparisons, M6 claim checks | Thêm item-period/document-specific restatement review liên kết B02 và B09 p23/2025; giữ original/comparative versions, không chọn winner từ equality | S | B07, B05 EPS nếu giao, B08 | EPS2024 original/comparative được phân biệt, trả source note và reason trình bày lại; numeric equality của chỉ tiêu khác không lan sang EPS | TODO |
| D03-B10 | ROOT_CAUSE_UNKNOWN: chưa xác định PDF có explicit reporting perimeter bị bỏ sót hay nguồn thật không ghi; resolver nhận 0 scope và mọi fact scope=None | UNKNOWN | P1 | 981 contexts, 36 pairs, execution/cross-doc policy | Kiểm cover/audit opinion + scope/consolidation notes đúng document; nếu không có explicit source, Tech Lead quyết định bounded document-pair profile thay vì tự separate/consolidated | S điều tra | Phép thử §5; B08/B09 trước approval pair | Source-backed scope record hoặc approved pair exception có document hashes/item-period/basis/restatement reviews; insufficient source vẫn undetermined | TODO |
| D03-B11 | Rule registry giữ unavailable_reason thời pilot và IDs b01.liabilities/equity lệch total_liabilities/total_equity hiện tại | CONFIRMED | P1 | Balance identity, asset/funding decomposition, cash reconciliation | Cập nhật đúng ARITHMETIC_RULES/RELATIONSHIP_RULES sau source review: map440, dùng total_* IDs; bỏ unavailable_reason chỉ ở rule có đủ evidence; không xóa guards adjustments/exchange-effect | S | B05, B08 | QA15 chạy balance identity với 440 thật; five filings không còn báo funding page ngoài pilot khi đã bind; thiếu điều chỉnh vẫn insufficient | TODO |
| D03-B12 | API dùng WEB_STORAGE_ROOT/W-04 items, chưa compose M3-07 và canonical snapshot catalog; UI pin latest_result | CONFIRMED | P1 | Web chỉ 178 W-07 items, không dùng 2021–2024/D-02 overlays | Bridge document UUID ↔ content hash và allowed snapshot catalog; read API dùng EvidenceRetrieval + quality/review overlay; document/snapshot picker. Giữ giới hạn storage hiện có | M | B04, B08; không Web V2 trong D-03 | Web/API chọn 5 filings/snapshot, B01/B02/B03 giữ period+source; 2022 recovery OCF và original metric selection rõ ràng; blocked/uncertain không bị ẩn | TODO |
| D03-B13 | Chưa có independent gold/sample gồm cả omissions; exact retrieval/spot checks chỉ kiểm phần đã chọn | CONFIRMED | P1 | Accuracy, M6/M7 research claims | Lập gold tách extraction: stratified random + risk + omission sample, independent reviewer đọc original PDF, chấm value/period/unit/label/source và coverage riêng | S vòng đầu | B07/B09/B15 cho risk strata | Có numerator/denominator và uncertainty theo stratum; gold độc lập; không gọi 48 spot checks hoặc 10 residual zero là full accuracy | TODO |
| D03-B14 | Response B01/2023 p5 sinh token `-turc` ở 5 slots, PDF in dash; parser giữ null đúng | CONFIRMED | P2 | 5 raw-value displays, không ảnh hưởng 15 metric operands | Source-backed overlay/attempt mới chỉ sửa transcription của 5 slots; giữ missing/null, không biến dash thành0; không Gemini toàn bộ | XS | Controlled source review | Raw display phản ánh nguồn, normalized vẫn null; lịch sử response giữ nguyên | TODO |
| D03-B15 | PROBABLE item-unit ambiguity: 8 EPS observations kế thừa unit=VND/scale1 từ toàn bảng, không có per-share semantic policy | PROBABLE | P2 | EPS mapping/execution tương lai; chưa nằm trong 15 metrics | Xác nhận EPS item semantics/unit với source note và Tech Lead; trước mapping phải có policy per-share, không cộng/sum như monetary total | XS xác minh | B09; source/Tech Lead verification | EPS retrieval ghi item semantics đúng; unit/scale controls từ chối aggregate-money operation trên EPS | TODO |
| D03-B16 | B03/2022 p8 khai columns3 nhưng header/cells có column3 zero-based; validator đúng khi chặn table | CONFIRMED | P2 | Baseline60 insufficient, 4 missing-position slots; Q07 trước recovery | Reuse accepted D-02 recovery columns4, không sửa validator/bỏ bounds check hoặc re-extract lại | Đã có | Accepted D-02 | Effective B03 quality 8 usable/43 caveat/9 insufficient; source positions resolve; original60 vẫn giữ nguyên | DONE |

Mỗi giải pháp chỉ là kế hoạch, chưa cấp quyền thực thi corrective task. B10 cần
phép thử trước giải pháp chắc chắn; B15 cần xác minh semantics trước canonical ID.

## 4. A — Calculation eligibility và snapshot closure

Điểm phát sinh đầu tiên của execution blocker là
[assess_analytical_readiness](../src/evidence/analytical_readiness.py), phần xây
`eligibility_blockers`: preparation approval waive unknown scope/source uncertainty
trong **candidate/profile**, nhưng execution vẫn yêu cầu
`original.status == compatible`. Global
[assess_compatibility](../src/evidence/compatibility.py) không nhận SourceReview hay
preparation approval; 15 metrics có đúng ba reason codes:
`unresolved_operand_context`, `missing_reporting_scope`, `source_reference_uncertain`.
30 operand occurrences chỉ còn context issue `missing_reporting_scope`, không phải
thiếu company/period/currency/scale/semantic role.

15 results tái hiện đúng stored final fix: preparation=true, candidate/profile
compatible, formula preflight không có blocker, execution=false. Exact eligibility
codes đều là `formula_policy_not_approved` và
`global_execution_compatibility_not_established`. Formula policy kiểm semantics,
ordered years và denominator; global compatibility kiểm nguồn/context. Có kiểm tra
period/roles giao nhau nhưng **hai approvals có purpose khác nhau**, không phải
hai bản ghi duyệt cùng một việc. `reference_example` của FormulaDefinition cũng
không phải execution approval. [check_formula_policy](../src/evidence/preparation_policy.py)
đòi matching formula ID/version/digest; registry không có execution record.

Phân biệt cụ thể:

- **Data blocker trong baseline selected operands: 0/15** ở input preflight,
  đủ 30 bindings, 25 source reviews/5 basis records; không đồng nghĩa toàn bộ
  source đã verified. Nếu chỉ nhìn metadata số liệu thì hai gates còn lại là policy.
- **Compatibility blocker: 15/15** global undetermined; preparation đã có exception,
  execution chưa được approve exception. Cần quyết định có giới hạn, không sửa scope=None.
- **Formula policy blocker: 15/15**, ba definitions chưa được approve để execute.
- **Missing executor: toàn bộ**; [DerivedMetric](../src/evidence/metrics.py) chỉ nhận
  `result=None`, [tools](../src/tools/__init__.py) chưa triển khai. Eligibility=true
  trong tương lai vẫn chưa tạo ra phép tính nếu không có M4 executor.

**Reproduction B04**: `evaluate_d02_final.evaluate` đổi `scopes[2022].snapshot_id`
và replace toàn document trong `after`, nhưng đánh giá metrics/lineages trên facts
baseline trước đó. Đây là hai scope báo cáo hợp lệ riêng biệt; lỗi sử dụng sẽ xảy
ra nếu consumer dùng “15 ready” cho selected recovery view. `snapshot-closure.json`
chứa exact IDs của ba metric names gross_margin/debt_to_assets/revenue_yoy và hai
operand references mỗi metric. `get_fact` trên effective view trả 6 `not_found /
no_matching_fact`; không phải mất dữ liệu trong repository gốc.

Rebind truy vấn **chỉ để chẩn đoán** theo canonical item/period trong recovery
tìm đủ sáu numeric operands, nhưng cả sáu có `source_status=unverified`, với
`{role}:source_unverified`, `{role}:accounting_basis_unknown_or_ambiguous`,
`missing_reporting_scope`, `source_reference_uncertain`. Cả ba preparation=false.
Năm unique reviews và một basis record của 2022 trỏ `D-01/normalized-v2`, không
phải `D-02/recovery-2022-v1`. Review matching không tự migrate là hành vi đúng.

Rủi ro khi sửa B01/B02/B04: scope exception quá rộng, auto-approve từ tests,
rebind bằng equality không kiểm selector, hoặc metric trỏ nhầm snapshot. Acceptance
phải giữ negative controls khác scope/document/period/unit/scale, quality blocked,
unknown basis, source conflict và wrong formula digest. Không giải quyết bằng
đổi tên `approved_compatibility` alias hoặc sửa persisted fact.

## 5. B — Cross-year, reporting entity/scope và restatement

Tái hiện `compare_observations` trong
[D-01 evaluator](../scripts/evaluate_d01_coverage.py): 36 pairs, 36 numeric equal,
36 `undetermined`, mỗi pair `reasons=[reporting_scope]`. Đây là so sánh metadata
nhỏ trong evaluator, không kiểm SourceReview, accounting-basis review hay
restatement. Nếu chỉ điền scope vào dữ liệu để code trả consistent thì vẫn chưa
đủ chứng cứ; không đề xuất cách này.

Nguồn entity đã có: thuyết minh PDF2021:10, 2022:9, 2023:9, 2024:11, 2025:9,
registration ID khớp qua `metadata-bindings.json`. D-02 basis records có VAS/TT200,
niên độ và cơ sở kế toán B01/B02. D-03 đọc lại headers2023, notes2023:9–10,
2024:11 và note EPS2025:23; reuse D-02 controlled reads các năm còn lại. Những
đoạn này chứng minh entity/basis được chọn, **chưa chứng minh reporting perimeter**.
Không khẳng định đã đọc hết 133 trang và không khẳng định PDF hoàn toàn không ghi scope.

First point scope=None: payload context không cung cấp resolved scope;
[resolve_financial_context](../src/accounting/context_resolution.py) chỉ chấp nhận
title “báo cáo tài chính hợp nhất/riêng”, mention trong câu giữ
`scope_mention_not_title`; adapter phát `missing_reporting_scope`. Không thấy bằng
chứng adapter làm mất scope đã resolved. B10 UNKNOWN ở **nguồn scope cuối cùng**,
không UNKNOWN ở reason code/code gate. Phép thử tiếp: đọc cover/audit opinion
PDF pages1–4 của đúng năm filings và section consolidation/subsidiaries trong
notes; ghi positive quote/page/PDF hash hoặc ledger các trang đã kiểm, không suy
separate từ tên Công ty/ticker/registration/không thấy từ “hợp nhất”.

Coverage thực tế của 36 pairs:

- 20 B02 = 5 mapped IDs × 4 năm chồng lấp, 16 B03 = 4 mapped IDs × 4 năm.
- Không có B01: headers đầu năm là `YYYY-01-01`, filing trước kết thúc
  `YYYY-1-12-31`; group key đòi literal period bằng nhau. Cần endpoint policy
  có nguồn trước đối chiếu, không tự đổi ngày hoặc gọi là lỗi số liệu.
- Chỉ 11/72 operand occurrences có value-row review đúng effective snapshot;
  61 còn unverified. Numeric equal không xóa limitation nguồn.
- EPS chưa mapped nên không vào 36 pairs. Tại PDF2025:23, note ghi EPS2024
  “đã được trình bày lại” do trích quỹ; PDF2024:9 in original EPS khác comparative
  trên PDF2025:7/23. B02/2024 extraction còn thiếu hoàn toàn dòng này.
  Đây là **CONFIRMED restatement case ngoài sample**, không phải tự kết luận
  restatement của 36 pairs. Chênh EPS các năm khác cần notes riêng, chưa phân loại.

Document-pair profile có thể đề xuất, chưa phê duyệt: exact hashes/snapshots hai
filings, cùng source-backed legal entity, item/statement/period và endpoint relation
được xác nhận, currency/scale/item-unit tương thích, basis của cả hai filings,
đủ review operands, ghi original/comparative/restated và note liên quan. Unknown
scope chỉ được exception có authority/reference và phạm vi item-period rõ; known
scope/basis conflict luôn veto. B03 không được dùng basis review chỉ dành B01/B02.

Rủi ro: profile legal-entity-only bỏ qua consolidation perimeter; auto-reconcile
EPS original/restated thành conflict extraction; policy đầu năm/cuối năm xóa dấu
điều chỉnh. Acceptance B09/B10 phải gồm EPS restatement và period-end negative cases.

## 6. C — Phân loại 816 unmapped và ưu tiên mapping

`unmapped-groups.json` giữ exact labels/IDs/periods; dưới đây là thống kê deduplicated
theo observation, không suy canonical mapping từ code đơn độc.

| Filing | Unmapped | Numeric / nonnumeric | Financial slots | Note slots | Structural |
| --- | ---: | --- | ---: | ---: | ---: |
| 2021 | 186 | 158 / 28 | 150 | 20 | 16 |
| 2022 | 164 | 150 / 14 | 156 | 0 | 8 |
| 2023 | 166 | 147 / 19 | 158 | 0 | 8 |
| 2024 | 154 | 134 / 20 | 146 | 0 | 8 |
| 2025 | 146 | 131 / 15 | 138 | 0 | 8 |
| Tổng | 816 | 720 / 96 | 748 | 20 | 48 |

B01 **420** = 400 financial +20 note; B02 **136** financial; B03 **260** =
212 financial +48 structural. 748 financial slots gồm **711 numeric/37 null**, thuộc
**79 statement/source-code pairs** (43 B01/14 B02/22 B03). Code 411a/421b là financial,
không được loại vì có hậu tố chữ. 130 subtotal candidates và 618 detail candidates
theo code inventory; đây là phân loại diagnostic, cần source/parent context trước taxonomy.
48 structural gồm 40 section-heading slots B03 và 8 signature/blank slots B03/2021.
20 note slots có 9 số tham chiếu note, không phải số tiền.

First point B05: [ITEM_CATALOG/map_item_label](../src/accounting/item_mapping.py)
chỉ có 16 IDs, exact NFC/casefold/whitespace aliases; cả 79 financial code groups
không có catalog rule. **Alias-only cho ID hiện có: 0 financial slots; rule mismatch
với ID hiện có: 0; cần xem xét ID/rule mới: 79 groups/748 slots.** Không có bằng
chứng cần map tất cả. Số canonical IDs cuối cùng vẫn cần semantics/parent review;
79 groups không phải approval tạo 79 IDs.

Ambiguity cần phòng ngừa: các bare labels “- Nguyên giá”, “- Giá trị hao mòn luỹ/lũy
kế” xuất hiện ở nhiều codes 222/228 và 223/229: **40 financial slots**. Cùng label
không có nghĩa cùng item; mapping mới cần code/parent asset group. Catalog cũ còn
giữ inventory140/141 cùng label với ordinal; không làm mất guard đã hoàn thành.

Ưu tiên bounded source-backed mapping:

1. **Validation/core QA**: B01 `100` “A - TÀI SẢN NGẮN HẠN” → candidate
   `b01.current_assets`; `200` “B - TÀI SẢN DÀI HẠN” → `b01.noncurrent_assets`;
   `310` “I. Nợ ngắn hạn” → `b01.short_term_liabilities`; `440` “TỔNG CỘNG NGUỒN
   VỐN” → `b01.total_funding`. Mỗi group10 financial slots, giữ note slots riêng.
2. **Revenue/cash validation**: B02 `01` “1. Doanh thu bán hàng và cung cấp dịch vụ”
   → `b02.sales_revenue`; `02` “2. Các khoản giảm trừ doanh thu” →
   `b02.revenue_deductions`; B03 `50` “Lưu chuyển tiền thuần trong năm” →
   `b03.net_cash_flow`; `60` “Tiền và tương đương tiền đầu năm” → `b03.opening_cash`.
   Code02 có 3 numeric/7 null, không biến dấu gạch thành0 để chạy rule.
3. **Expanded Vietnamese QA/analysis** khi được giao: B02 21/22/23/25/26/30
   (financial income/cost/interest/selling/admin/operating profit), B01 111/131/320/421,
   rồi EPS70 sau B07/B09/B15. Giữ aliases ordinal/luỹ-lũy/code phụ có source review.

Nhóm ưu tiên1+2 chỉ khoảng80 financial slots, không yêu cầu sửa mọi unmapped trước
M4. Các 15 metric operands hiện tại đã mapped. Rủi ro mở catalog: code01/20/60
khác semantics giữa statements, parent codes trùng nhãn, labels ordinal thay đổi;
acceptance cần source-label-code-statement positive/negative, không fuzzy match đơn độc.

## 7. D/E — Quality, provenance và financial accuracy

Quality baseline theo từng statement/year; reasons đếm mỗi code một lần/observation,
các cột không cộng thành tổng unique blocked:

| Năm/statement | Items | Insufficient | Missing mapping | Missing numeric | Missing period | Extraction error | Ambiguous item |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021/B01 | 121 | 25 | 102 | 15 | 25 | 0 | 0 |
| 2021/B02 | 36 | 1 | 26 | 1 | 0 | 0 | 0 |
| 2021/B03 | 66 | 16 | 58 | 16 | 0 | 0 | 4 |
| 2022/B01 | 98 | 2 | 84 | 2 | 0 | 0 | 0 |
| 2022/B02 | 38 | 3 | 28 | 3 | 0 | 0 | 0 |
| 2022/B03 | 60 | 60 | 52 | 9 | 0 | 60 | 0 |
| 2023/B01 | 100 | 7 | 86 | 7 | 0 | 0 | 0 |
| 2023/B02 | 38 | 3 | 28 | 3 | 0 | 0 | 0 |
| 2023/B03 | 60 | 9 | 52 | 9 | 0 | 0 | 0 |
| 2024/B01 | 92 | 7 | 78 | 7 | 0 | 0 | 0 |
| 2024/B02 | 36 | 4 | 26 | 4 | 0 | 0 | 0 |
| 2024/B03 | 58 | 9 | 50 | 9 | 0 | 0 | 0 |
| 2025/B01 | 84 | 3 | 70 | 3 | 0 | 0 | 0 |
| 2025/B02 | 38 | 4 | 28 | 4 | 0 | 0 | 0 |
| 2025/B03 | 56 | 8 | 48 | 8 | 0 | 0 | 0 |

Exact codes từ [quality](../src/accounting/quality.py):
`missing_canonical_mapping=816` (caveat, **không tự blocking direct QA**),
`missing_source_data=100`, `missing_period=25`, `ambiguous_item=4`,
`extraction_error=60`. Baseline 161 insufficient/668 caveat/152 usable; recovery
view **110 insufficient/711 caveat/160 usable**. Không thay quality/status để đạt số này.

Phân nguyên nhân chặn, không cộng trùng:

- **60** có extraction/layout blocker B03/2022; first point payload table dimensions,
  validator [validate_automated_extraction](../src/accounting/automated_extraction.py)
  đúng khi phát `table_position_conflict`. Recovery đã có, không gọi Gemini nữa.
  Adapter giữ hai extraction issue details/observation nên `m2_extraction_issue`
  có120 occurrences trên60 records, không phải120 records lỗi.
- **25** thiếu period chỉ vì cột “Thuyết số” B01/2021 bị coi là value column,
  không phải thiếu financial-year metadata của dòng thật. 5 slots còn được mapped
  (110/130/140/141/270); 10 note references numeric. Sửa header role/projection,
  không re-extract PDF và không “điền period” vào notes.
- **100** null/nonnumeric =48 structural +15 blank note +37 financial placeholders.
  15 blank note đã nằm trong25 missing-period. Quality validator giữ null đúng.
  B03 section/signatures làm denominator xấu, không có nghĩa số liệu mất48 chỉ tiêu.
- **0 direct-QA records bị chặn chỉ vì missing mapping**; mapping caveat vẫn làm
  canonical-ID query không tìm được. **0 blocking direct-QA chỉ vì scope missing**;
  scope chặn compatibility. 981 `missing_reporting_scope`, 816 missing mapping,
  25 period/type issues giữ trong resolution context, không phải981 numeric errors.
- Chưa chứng minh quality validator chặn nhầm financial numeric row nào sau recovery.
  Effective110 =100 null +10 numeric note references. Không đề xuất bỏ validators.

**Nguồn**: cả981 facts có anchors/citations, source identity/reference/selector
resolve; không tìm missing anchor, inconsistent source binding hay invalid cell
provenance. Baseline4 missing value positions là structural placeholders B03/2022,
effective0. Cả981 consistency=`unresolved`, không có `inconsistent`: page anchors
được tạo `status=uncertain`, `provenance_level=page`, không exact cell bbox/IDs.
`get_sources` trả page/raw-payload selectors, hỗ trợ navigation và review binding,
không chứng minh token đúng pixel trên ảnh. Phân biệt missing anchor với uncertain
anchor; không sửa anchor thành resolved để mở gate.
Kiểm tra read-only bổ sung đối chiếu document/snapshot/page/image với parent record:
**9.645 baseline anchor occurrences khớp**, không chỉ kiểm source_pointer tồn tại.

Source review baseline25 verified/956 unverified; effective22 verified/959 unverified
(mất coverage5 của snapshot2022 cũ, có thêm2 recovery OCF). Đây là mức **controlled
value-row read**, không independent human gold hay cell geometry. Không được nói
956/959 còn lại “số liệu đúng nhưng chưa xác nhận”: độ đúng của chúng chưa xác lập.
Những record25/22 có controlled evidence và source binding đúng mới được nói rõ
đã review ở mức đó.

**Các loại lỗi/limitations có evidence**:

- B07 omission: PDF2024:9 có row70 nhưng payload `tables[0].rows=19`, row18 kết thúc
  code60, `limitations=[]`,36 B02 observations. First point response payload, trước
  normalization/mapping. Cơ chế vì sao model bỏ dòng (crop/truncation/attention)
  **ROOT_CAUSE_UNKNOWN**; kiểm cached input image dimensions/full-page binding,
  request/finish metadata và source row inventory là phép thử tiếp. Không coi
  mọi omitted row đã được giải thích bởi “Gemini sai”.
  Response thực tế `success/stop`, ảnh khai1656×2339; không có evidence schema/parse
  failure. Dimensions và stop chưa giải thích được omission; cần kiểm nội dung
  input binding trước khi chọn recovery strategy.
- B14 transcription: 2023/B01/page5 codes152 (prior),227 (hai kỳ),260/261 (current)
  có raw `-turc`; ảnh D-02/2023-5.png và original PDF in dash. Five tokens không
  phải numeric; parser trả null an toàn. Không có bằng chứng năm giá trị số sai.
- D-02 recovery signing-date sai năm đã có overlay final-fix riêng,
  `usable_for=signing_date_only`; không thay financial period từ ngày ký.
- EPS original/comparative có restatement source-backed, không tự gọi discrepancy
  đó là extraction error. B15 unit semantics mới PROBABLE: source table dùng VND,
  nhưng EPS là chỉ tiêu per-share; phải review trước khi map/execute như money total.
- Chưa phát hiện thêm numeric mismatch trong mẫu D-03 này; không suy toàn881 numeric đúng.

**Arithmetic signals**: `arithmetic-signals.json` kiểm 5 năm current B01 assets
trừ liabilities/equity và B02 revenue trừ cost/gross profit: **10/10 residual=0**.
Chỉ là diagnostic, không execution approval/financial gold; lỗi chung dấu/scale,
omissions, restatements và correlated extraction vẫn có thể cùng cân. Existing
relationship evaluator còn trả5 current closing-cash `consistent` có
`scope_unconfirmed` caveat; không audit lại phần hoạt động này.

`validation.json` tái hiện balance identity vẫn `insufficient_data`, missing
`b01.total_funding`, issue exact
`source_unconfirmed:b01.total_funding;funding_page_not_in_pilot`. Raw440 có10 financial
slots trong5 filings. First point là unavailable registry trong
[relationships](../src/accounting/relationships.py) và
[arithmetic](../src/accounting/arithmetic.py), không phải trang nguồn thật thiếu.
Arithmetic funding còn reserve `b01.liabilities/b01.equity` trong khi catalog hiện
có `b01.total_liabilities/b01.total_equity`. Với retained earnings cần adjustments,
cash reconciliation cần evidence exchange effect; đây là limitations thật, không
được bỏ unavailable flag hàng loạt hoặc xem missing là0.

**Đề xuất evaluation độc lập, chưa chạy trong D-03**: 60 numeric cells lấy random
seed cố định trước khi đọc, stratify5 năm ×3 statements ×4 cells; thêm20 risk
cases (âm/ngoặc, null/zero, EPS/restatement, period headers, notes column, page cuối)
và10 source rows kiểm omission, chọn trên PDF trước khi lookup extraction. Tách
random estimate khỏi risk/omission sample và báo overlap; không cộng chúng thành
accuracy toàn dataset. Reviewer độc lập đọc PDF, chấm value exact Decimal, dấu,
label/code, period/type, unit/scale và citation đúng document/page/selector; báo
cell accuracy, row completeness, source accuracy riêng, khoảng bất định và
disagreements. Mẫu chưa đủ thì mở rộng theo lỗi đã thấy, không full extraction.

## 8. F — Web Demo integration

First point composition: [create_app](../src/api/main.py) chọn `WEB_STORAGE_ROOT`,
default `artifacts/web-demo-v1`; environment hiện không override. Không đọc `.env`
để đoán một server khác đang chạy. GET qua ASGI không lifespan trên persisted default
storage: `/api/documents`200, một document UUID, original PDF hash khớp2025,
latest W-07 attempt `6f8197c3-6c3e-489c-88b8-4390ce73f442`.

GET evidence200: **178 items** (B01=84/B02=38/B03=56), periods
`2025-12-31`, `2025-01-01`, `2025`, `2024`; sources có page/pointer và original hash
đúng. Không tái đánh giá browser rendering; code
[groupEvidence/contextLabel](../web/lib/evidence.ts) giữ period/type/currency/scale/
raw header và source, không có bằng chứng regression hiển thị period ở sample này.

[read_result/evidence_response](../src/api/extraction_sessions.py) đọc
`documents/{uuid}/attempts/{attempt}/result.json`, trả W-04 `items`, không gọi
M3-07 EvidenceRetrieval. Truyền `attempt_id=D-01/normalized-v2` cho document này
trả404 `attempt_not_found`. Đổi WEB_STORAGE_ROOT sang D-01/evaluation đơn thuần
không giải quyết vì khác UUID/content identity và storage schema.

[DocumentExplorer](../web/components/evidence/document-explorer.tsx) và
[DocumentPicker](../web/components/evidence/document-picker.tsx): có document
picker, chọn attempt bằng `latest_result`/job; không có snapshot picker. SourceDetails
chỉ có original quality/page pointers, không SourceReview/basis/readiness overlay.
Không có route canonical/retrieval/source-review trong API hiện có.

Phân loại: không có bằng chứng dữ liệu D-01 mất hoặc M3-07 lookup hỏng; đây là
**bridge/API chưa triển khai** sau giới hạn chủ ý V1. Với yêu cầu xem2021–2025 thì
trở thành integration gap. Snapshot picker và review overlay là chức năng thiếu;
B09 semantic QA/graph/chatbot/report vẫn ngoài V1. Rủi ro B12: UUID↔hash sai nguồn,
latest snapshot che metric cũ, quality caveats mất khi chuyển projection. Acceptance
phải kiểm những trường này qua API rồi một browser smoke bounded, không Web V2 ở D-03.

## 9. G — 20 structured financial QA cases

Không LLM/NL parser. Pipeline diagnostic: structured query → M3-07 retrieval → facts
→ existing gates/validation → answer data + citations. `qa.json` có exact identities,
raw/normalized values, reasons và citations. Bảng không công bố numeric answer thành
financial claim. “Citations có” chỉ đủ page display, vẫn page/uncertain. “Kỳ/unit đúng”
ở đây là metadata source-bound VND/scale1; EPS được giữ chưa xác nhận item-unit.

| Case / câu hỏi | Facts, kỳ/unit, operands | Calculation / citations | Điểm chặn và exact cause |
| --- | --- | --- | --- |
| QA01 Doanh thu thuần2023 | 1; đúng; đủ | Không yêu cầu; có | Answer data với caveat, không missing chatbot blocker |
| QA02 Tổng tài sản cuối2024 | 1; đúng; đủ | Không yêu cầu; có | Answer data với caveat |
| QA03 Lợi nhuận sau thuế2025 | 1; đúng; đủ | Không yêu cầu; có | Answer data với caveat |
| QA04 OCF2022 | 1 recovery; đúng; đủ | Không yêu cầu; có | Available có caveat; reuse B16 recovery |
| QA05 Equity cuối2021 | 1; đúng; đủ | Không yêu cầu; có | Answer data với caveat |
| QA06 Giá vốn2024 | 1; đúng; đủ | Không yêu cầu; có | Answer data với caveat |
| QA07 Tiền cuối2025 | 1; đúng; đủ | Không yêu cầu; có | Answer data với caveat |
| QA08 Dòng tiền đầu tư2023 | 1; đúng; đủ | Không yêu cầu; có | Answer data với caveat |
| QA09 Nợ ngắn hạn cuối2024 | 0 canonical; raw310 có; chưa bind | Không; chưa có citation cho requested ID | Retrieval `unavailable/canonical_mapping_missing`, B05 |
| QA10 Doanh thu2024 không chọn filing | 2; metadata đúng nhưng khác filing | Không chọn winner; có hai sets | `ambiguous_candidates`, phải chọn original/comparative; B09/B12 |
| QA11 Assets filing2023 không chọn kỳ | 2; current/as-of và opening | Không chọn winner; có hai sets | `ambiguous_candidates`, caller cần period selector; B12 |
| QA12 Revenue2022→2023 cùng filing2023 | 2; đúng; đủ | Không; có | Preparation true; `formula_policy_not_approved` + `global_execution_compatibility_not_established`, B01/B02/B03 |
| QA13 Gross margin2024 | 2; đúng; đủ | Không; có | Cùng hai gates như QA12 |
| QA14 Debt/assets2025 | 2; đúng; đủ | Không; có | Cùng hai gates như QA12 |
| QA15 Balance identity2023 | 3 numeric; đúng; thiếu canonical440 cho formal rule | Không formal answer; có citations cho3 | `canonical_mapping_missing`; validator `source_unconfirmed:b01.total_funding;funding_page_not_in_pilot`, B05/B11; residual diagnostic không thay formal validation |
| QA16 Chỉ tiêu bất thường2021–2025 | Inventory retrieval981; chưa có anomaly operands/rule | Không; nguồn inventory có, chưa có claim citations chọn | Rule/threshold/baseline chưa triển khai, B03; không phải retrieval failure |
| QA17 Revenue2023 ở filings2023/2024 so được? | 2; đúng; đủ | Không kết luận comparable; có | Pair evaluator `reasons=[reporting_scope]`, B10; còn review/basis/restatement policy theo B08/B09 |
| QA18 Gross margin2022 khi chọn recovery | 0 original references; recovery query có2 numeric | Không; old refs không có, recovery có page citations | `no_matching_fact`; readiness recovery có source_unverified/accounting_basis_unknown_or_ambiguous, B04; không phải số tiền bị mất |
| QA19 EPS2024/current+comparative | 0 raw rows; unit chưa đánh giá | Không; thiếu fact citations | Row70 không tồn tại trong payload dù PDF2024:9 có; B07 |
| QA20 EPS2025/current+comparative và restatement | 2 raw facts; periods có; item-unit chưa review | Không financial interpretation; có | Canonical EPS/semantic restatement binding thiếu, B05/B09/B15; note2025:23 chứng minh trường hợp thật |

Outcomes: **8 answer-data-with-caveat; 12 chưa có final answer**: 1 mapping,
2 selection ambiguity,3 execution,1 formal validation,1 anomaly rule,1 comparability,
1 snapshot closure,1 extraction omission,1 restatement interpretation. Đây là readiness
diagnostic của20 structured cases, không phải QA accuracy hay chatbot benchmark.

## 10. Thứ tự corrective groups và milestone Go/No-Go

Các tên G1–G6 là nhóm đề xuất, **chưa tạo task mới hoặc tự bắt đầu triển khai**.

1. **G1 — Chốt source/snapshot contract** (B04/B08, S): catalog chứa original/recovery,
   explicit selection; mọi metric thuộc snapshot có fact/review/basis/lineage closure.
   Có thể pin baseline cho15 metrics hiện tại và dùng recovery chỉ OCF nếu công bố
   rõ; muốn metric recovery-ready phải rebind/build mới sau nguồn được xác nhận.
2. **G2 — Chặn sai nguồn/thiếu dòng trong bounded data** (B06/B07/B14/B15, S theo phần):
   p9/2024 EPS row completeness, p6/2021 note-column classification, p5/2023 dash
   overlay; xác minh EPS semantics. Ghi thêm coverage/source cases vào independent
   sample B13. Recovery/Gemini chỉ được đề xuất đúng p9 khi cần, không mặc định gọi.
3. **G3 — Quyết định execution và M4 scope** (B01/B02/B03): Tech Lead duyệt/bác
   ba definitions và bounded execution compatibility với G1. Sau đó mới giao M4
   executor. Không cần chờ G2 xử lý mọi expanded row nếu15 operands dùng đã reviewed,
   nhưng phải công khai phạm vi không gồm EPS/unverified facts.
4. **G4 — Mapping + validation tối thiểu** (B05/B11, S): bốn B01 IDs trước, rồi
   B02 01/02 và B03 50/60 theo nhu cầu; align reserved IDs/rule source references,
   bỏ stale unavailable flags có evidence. Không nới retained-earnings/exchange guards.
5. **G5 — Cross-document evidence/restatement** (B09/B10/B13, S rồi quyết định):
   targeted scope lookup, EPS note binding, independent source sample; chỉ approve
   bounded pairs có đủ evidence. Không dựa vào36 equality để cấp blanket approval.
6. **G6 — Web canonical bridge** (B12, M): sau G1/G4 và review overlay contract,
   nối5 filings/snapshot qua M3-07. Có thể demo retrieval có caveat trước financial
   execution nếu UI nói đúng readiness. Không phụ thuộc map toàn79 code groups.

| Milestone | Critical dependencies / confirmed blockers | Nonblocking limitations | Minimum corrective actions | Quyết định hiện tại |
| --- | --- | --- | --- | --- |
| M4 Financial Tools | B01/B02 chưa execution approval, B04 snapshot closure; B03 executor là output chưa triển khai; B11 nếu nhận balance validation | 816 unmapped không chặn ba mapped metric types; full-PDF gold chưa có không được suy verified claims | Tech Lead approve scope/definitions, G1 closure; giao executor sau quyết định. G4 chỉ rules được chọn; giữ errors/lineage | **NO-GO** cho execution-ready; **Conditional Go** để bắt đầu implementation sau minimum decisions/contract và Owner giao việc |
| M5 Multi-Agent | agents mới namespace; tools runtime/result/eligibility contract M4 chưa có | Không cần toàn taxonomy hay Web V2 để nghiên cứu orchestration | M4 bounded executor + traceable failures; câu hỏi/routes cố định, resource budget; chưa tự thêm agent | **NO-GO** cho real financial agent workflow; thiết kế chỉ sau dependency acceptance |
| M6 Claim Verification | B08 source review adapter, B09 original/restated, B13 independent gold; verification mới namespace | Page citations có thể dùng để review khi gắn caveat; không cần verify981 thủ công trước bounded prototype | G1/G5, explicit supported claim types, preserve null/unverified; gold sample độc lập và claim lineage | **NO-GO** cho verified financial claims; bounded design conditional sau contracts/evidence |
| M7 Grounded QA/Reports | outputs mới namespace; QA12–20 còn gates/rules; M4/M6 chưa có verified answer contract | 8 direct structured answers đã có source-bound data; thiếu chatbot không phải lỗi M3-07 | Bounded M4/M6 accepted, supported-question catalog, refusal/caveat rules; G6 chỉ nếu giao web delivery | **NO-GO** cho grounded financial QA/report milestone; retrieval-only local demo có điều kiện giữ đúng scope |

Không dùng Go/No-Go này để tự thay trạng thái M4–M7 hoặc đòi xây tất cả milestones
trước nhau. Tech Lead chốt severity/scope, Owner giao từng task sau review D-03.

## 11. Validation, Git và bàn giao

Diagnostic final trên real artifacts PASS: readiness baseline exact15, current
cross-year exact36, exact lookup981,20 QA cases, snapshot closure reproduction,
GET web evidence và unavailable snapshot,2.421 hashes unchanged. Zero Gemini/tokens.

Existing targeted tests: **5 PASS**:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_d02_readiness.py::test_candidate_is_separate_from_approval_and_preserves_original_sources tests/unit/test_d02_readiness.py::test_formula_preflight_and_explicit_execution_approval tests/unit/test_relationships.py::test_unavailable_never_evaluates_fake_equality -q
```

Ruff lint/format script, planning checker và git diff --check được chạy trước commit.
Không full regression, frontend build/browser, benchmark hoặc Gemini calls.
CI là engineering checks của commit audit; không xác nhận chất lượng tài chính.

Audit implementation `e11821b153871f34b44bcbd7ea08293aafe4b039` đã push main;
[CI41211560836](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41211560836)
completed/SUCCESS đúng SHA. Python3.12/lint/format/planning/focused offline tests
SUCCESS; Web smoke SKIPPED vì không đổi web/backend, full regression SKIPPED.
Checkpoint sau chỉ docs/planning, không gán CI implementation cho SHA checkpoint.
Ruff script/planning96/diff checks local PASS. D-02 vẫn giữ REVIEW trong registry cũ: task mới
xác nhận accepted fix làm input, D-03 không tự nghiệm thu D-02 DONE.

**Next action duy nhất:** Tech Lead independent review Blocker Registry và quyết
định phạm vi/thứ tự corrective groups; không bắt đầu M4 hoặc áp dụng fixes ở D-03.
