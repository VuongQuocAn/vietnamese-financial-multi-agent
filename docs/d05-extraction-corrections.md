# D-05 — Extraction completeness và hiệu chỉnh theo nguồn

Ngày 01/11/2026, Asia/Bangkok. Baseline main `53a7836`, sau accepted D-04
`73e2f9e9cc412dc86a2dbf7e45903d8a6449d5dd`. Owner giao commit/push trực tiếp main;
SHA và CI được ghi ở checkpoint sau implementation. Status **REVIEW**, chờ Tech Lead nghiệm thu.
Main-first, giữ local web/next-env.d.ts.
Report này không chứng nhận full-PDF accuracy hoặc independent human gold.

## Nguyên nhân và bằng chứng

**B07:** original PDF 2024 trang 9, dòng cuối bảng trước chữ ký có code70,
hai cột năm 2024/2023. Re-render bằng existing `load_pages` tại 200dpi khớp
image binding đã lưu. `response.output.raw_text` parse ra chính xác `payload`;
payload gốc kết thúc ở code60, không có code70. Response success/finish=stop,
4.414 output tokens, dưới cap16.384; limitations rỗng. Parser chỉ decode JSON,
không bỏ dòng. EPS đã mất trong model output, trước parsing/normalization/quality/
projection; không có evidence cho response truncation hoặc rendering crop.
Không suy đoán nguyên nhân nội bộ attention của Gemini.

Đã kiểm prompt/schema tại accepted D-01 code: yêu cầu ALL rows, physical positions,
raw tokens, period/unit và limitations; schema không có source inventory hoặc
coverage obligation ở terminal boundary. **Exact historical request envelope không
được lưu**; chỉ reconstruct prompt/schema từ accepted code cùng response request ID,
model và source image binding. D-05 lưu request metadata cho attempts mới và nhắc
kiểm dòng cuối; prompt không thay thế completeness check.

**B14:** năm tokens bất thường đã có nguyên văn trong raw response B01/2023 p5,
raw JSON = parsed payload. PDF hiển thị dash tại code152/cột đầu kỳ, code227/hai
cột, code260/cột cuối kỳ và code261/cột cuối kỳ. Parser cũ giữ normalized=null;
lỗi là transcription ở model output, không phải serializer biến null thành chữ.

**B06:** validator cũ nhận value columns bằng cách loại ba header strings; header
“Thuyết số” lọt qua, numeric note references thành observations. Projection cũ cũng
giữ blank/section/signature records. Classification mới kết hợp label/code columns,
period-header shape, body values và row context; không dựa riêng vào từ khóa.

## Runtime và contracts

`accounting/extraction_semantics.py` giữ catalog có version
`financial-table-semantics-v1`. Column roles tách note_reference/column_header/
financial_value/unknown; row roles gồm financial_item/subtotal/column_header/
section_header/signature_or_footer/unknown. Financial projection chỉ tạo slots
ở financial rows/value columns. Code nhận cả chữ hậu tố như 411a/421b. Notes,
headers, section/signature và unknown vẫn nằm trong TableEvidence/raw response.
Mapping catalog không mở rộng; không dùng mapping rate làm acceptance.

`accounting/completeness.py` nhận `SourceRowInventory` version1, bound đúng document
content identity, PDF page, statement, table và reviewed render/reference. Source
rows có label/code/selector, expected value-column positions, trạng thái observed/
ambiguous/unreadable/not_applicable. Kết quả từng row: row_present/row_missing/
row_ambiguous/source_unreadable/not_applicable. Aggregate: rows_missing/covered/
coverage_uncertain. Chỉ covered khi full-table inventory, terminal boundary,
matching rows/positions và không có extraction limitations. Đây là **coverage của
bảng được chỉ định**, không phải chứng nhận số liệu hay toàn bộ PDF. Ô raw null
vẫn là slot tồn tại; row coverage không khẳng định null transcription đúng glyph.

Không có/incomplete inventory hoặc nguồn mơ hồ thì coverage_uncertain. Không so
với fixed template để kết luận một optional row bị thiếu. Caller chịu trách nhiệm
resolve/đối chiếu PDF và reviewed-image hash trước khi đưa inventory vào pure
checker; không coi self-report của model là source review. `run_automated_pdf` và
`process_financial_pdf` nhận optional `source_inventories` theo trang, giữ bounded
existing pipeline, không tự phát sinh API recovery hoặc approve coverage.

`numeric_token_issues` phát hiện alphabetic numeric tokens, malformed numbers và
null/numeric conflicts. Không thay token bằng số hoặc zero. Các issues được đưa
vào extraction/quality; direct-qa quality vẫn theo existing assessor.

`accounting/raw_corrections.py::extraction_payload` tạo effective payload từ bản
copy cộng explicit reviewed overlays. Raw correction pin document/page/request ID,
exact cell selector, original text, reviewed glyph và image/reference. Phạm vi
hiện tại chỉ correction malformed placeholders thành dash; normalized vẫn null.
Original response/raw_text không bị sửa. Structural overlay riêng kiểm exact
original bounds và toàn bộ cell positions; chỉ áp bounds đã source-reviewed khớp
max index + 1. Không tự sửa bounds im lặng trong parser. Quality và document-evidence
adapters dùng cùng effective payload và giữ overlay metadata.

## EPS semantics và recovery

PDF 2024 p9 và note21 p25: **basic earnings per ordinary share**, lợi nhuận phân
bổ cho cổ đông phổ thông chia số cổ phiếu phổ thông lưu hành bình quân. Note ghi
profit bằng VND, denominator là quantity cổ phiếu; vì vậy semantic unit là
**VND/share**, scale1. Bảng B02 chỉ in đơn vị chung VND; không in riêng unit ở dòng
EPS. Kết luận per-share dựa vào label/code và note numerator/denominator, không
coi EPS là monetary total. Raw unit context VND được giữ riêng trong metadata.

Code70/basic EPS có trong extracted B02 cả năm filings; không thấy diluted EPS
riêng trong các bảng B02 đã chọn. Catalog hiện chỉ có basic/code70 đã kiểm nguồn;
diluted/code71 giữ item_unit_uncertain đến khi có source-backed rule riêng.
Không kết luận toàn filing không có diluted EPS.
Label EPS mơ hồ, sai code/statement, thiếu currency hoặc table scale khác1 giữ
unit/scale unknown + item_unit_uncertain. Monetary rows khác giữ VND. Arithmetic
hiện có từ chối cộng per-share với monetary qua unit/currency compatibility;
không thêm formula/executor hoặc EPS mapping.

Note2024 p25 nói comparative2023 được trình bày lại; note2025 p23 trình bày lại
EPS2024. Hai số của filing2024 là **1.032 (2024), 917 (2023 comparative)**. EPS2024
trong filing2025 là **1.008**, không được overwrite vào filing2024 hoặc coi equal
pairs là restatement consistency. B09/cross-document approval giữ ngoài scope.

Đúng một live full-table request cho PDF2024 p9 qua existing Gateway/model
gemini-3.5-flash-lite: success/stop, **5.966 tokens** (1.340 input/4.626 output),
một provider attempt. Response mới có code70, label/note21, đúng hai headers/values.
Giữ nguyên response mới dù nó khai rows19 với max row index19; reviewed structural
overlay đặt rows20/columns5 theo ảnh nguồn. Không gọi model thêm lần nữa.

36 existing value slots của B02 giữ normalized values và periods. Bốn raw dash
slots ở codes02/52 được model trả null text, normalized vẫn null; report không
coi đây là glyph verification toàn bảng. Chỉ EPS values được SourceReview riêng.
Không thêm thủ công hai observations vào snapshot cũ.

## Dữ liệu thật trước/sau

Original D-01/D-02/D-04 evidence giữ nguyên; corrected projection tách riêng.

| Filing | Original observations | Corrected observations | Loại bỏ |
| --- | ---: | ---: | --- |
| 2021 | 223 | 182 | 25 note slots, 8 section, 2 signature/footer, 6 unknown |
| 2022 | 196 | 188 | 8 section |
| 2023 | 198 | 190 | 8 section; năm raw corrections giữ null |
| 2024 | 186 | 180 | 8 section, thêm 2 EPS slots |
| 2025 | 178 | 170 | 8 section |
| Tổng | 981 | 910 | 73 structural/note slots bỏ khỏi financial view, thêm2 EPS |

Sáu unknown slots: bốn blank slots và hai signatory-name strings ở B03/2021 footer;
không có valid financial code hoặc numeric amount. Không xóa raw/table evidence.
25 note slots gồm năm mapped artifacts; giữ toàn bộ mapped monetary operands có
kỳ hợp lệ. Tỷ lệ mapping sau filter không được dùng để claim accuracy tăng.

Trước recovery checker phát hiện đúng terminal code70 missing theo full source
inventory19 rows; sau recovery19/19 row coverage covered. Không có inventory cho
các bảng khác thì vẫn coverage_uncertain. Năm B01/2023 slots raw sửa bằng overlay
có exact source selector; originals còn trong response. EPS10 slots trong corrected
view dùng VND/share, không còn kế thừa monetary VND.

## Snapshot và integrity

Mỗi document có explicit `D-05/corrected-v1`, parent `D-01/normalized-v2`;
descriptor origin là recovery cho 2024, normalized_projection cho các năm khác.
Giữ original document content identity, evidence pointers và parent chain; không
silent overwrite hoặc trùng identity khác payload. Persist bằng existing
CanonicalFactRepository/DocumentEvidenceRepository; restart exact.

Giữ accepted D-04 recovery2022 riêng, không tự kế thừa facts/reviews/metrics.
New corrected snapshots chưa công bố metric readiness: không tự rebind metrics/
basis/reviews từ ancestors. SourceReviews mới chỉ pin đúng hai EPS và năm corrected
raw observations; page-level uncertain anchors và M2 quality vẫn giữ nguyên.
Baseline981 exact retrieval, accepted graph/15 lineages và catalog readiness
baseline15/15, recovery3/3 được so với persisted D-04 evidence. Execution eligible0.
Projection2022 mới chọn parent D-01 tường minh, giữ known B03 position issue của
parent; accepted recovery D-04 vẫn là alternative riêng để chọn cho B03. Không
ngầm gộp hai snapshots hoặc tuyên bố corrected projections đều preparation-ready.

Ignored artifacts `artifacts/evidence/D-05-review/`: original recovery response,
request metadata/usage, full source inventory/coverage before-after, per-year
normalized snapshots + canonical/document-evidence repositories, removed slots/
count details, raw overlays/SourceReviews, catalog/descriptors, root-cause records,
source renders và hashes. Không commit PDF/OCR/data/images/keys.

## Validation và giới hạn

Lượt chuẩn bị independent review: **243 PASS** sau khi sửa hai generic cases
phát hiện trước commit: label-only inventory không còn đòi code cell; label có
“giám đốc” cùng financial value slots không bị keyword chữ ký loại nhầm.
Cached projections thực tế giữ nguyên; không tạo snapshot cùng ID khác payload.

Local **243 PASS**: 16 generic scenarios + extraction/quality/arithmetic và
contracts/canonical/document-evidence/graph/metric/lineage/retrieval/D-02/D-04
regressions. Sau khi giới hạn catalog chỉ basic/code70 có nguồn, chạy lại đúng
16 D-05 controls; không rerun toàn bộ nhóm PASS. Ruff toàn repository PASS,
335 files formatted; planning98 và diff check PASS. Các nhóm tests vừa chạy lại
theo yêu cầu Owner; không thay kết quả local bằng CI hoặc financial accuracy.
Real evaluation: 981 original +196 accepted recovery = **1.177 exact lookups**,
15/15 baseline metrics và 3/3 D-04 recovery giữ exact catalog, graph và 15 baseline
lineages exact; corrected repositories restart exact. **2.457 input hashes trước
= sau**, gồm accepted artifacts và web local. Một Gateway attempt/5.966 tokens;
không extraction toàn PDF hoặc dataset benchmark. Không suy financial accuracy
từ synthetic tests. Lượt runner đầu gặp Windows transient replace lock khi persist; reuse
existing bounded local persist helper, không sửa repository hoặc gọi Gemini lại.

```powershell
.venv/Scripts/python.exe scripts/evaluate_d05_corrections.py --output artifacts/evidence/D-05-new --prepare
# Đọc/đối chiếu source renders trước recovery/evaluation.
.venv/Scripts/python.exe scripts/evaluate_d05_corrections.py --output artifacts/evidence/D-05-new --recover-live
.venv/Scripts/python.exe scripts/evaluate_d05_corrections.py --output artifacts/evidence/D-05-new
# Independent reconciliation từ persisted outputs, không gọi Gemini.
.venv/Scripts/python.exe scripts/evaluate_d05_corrections.py --review-output artifacts/evidence/D-05-review-prep
```

Chạy live chỉ cho target page nếu chưa có cache; runner từ chối gọi lại khi response
đã tồn tại, không retry provider vô hạn. Source readings ở runner chỉ dành cho BBS;
runtime không chứa company/year/page/snapshot hoặc malformed-token đặc thù này.
PDF mới dùng contracts/inventory/overlays riêng và explicit snapshot selection.

## Reconciliation để independent review

Kết quả review cached evidence: **981 − 73 + 2 = 910**, giảm ròng **71**.
Không có danh sách “71 observations bị loại”: thực tế loại **73**, bổ sung hai
EPS. Bảng dưới liệt kê đủ 73 identities của projection cũ; không ghép hai EPS
mới vào tập bị loại. Financial gồm cả subtotal và null financial slots; structural
gồm section_header/signature_or_footer/unknown. Header riêng đếm0 vì header gây
lỗi là header của note column, còn 25 observations lỗi thuộc note-reference slots.
Raw header/note/section/signature vẫn truy xuất trong table evidence.

| Filing | Financial | Structural | Header | Note | Total | Removed | Added |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | 182 -> 182 | 16 -> 0 | 0 -> 0 | 25 -> 0 | 223 -> 182 | 41 | 0 |
| 2022 | 188 -> 188 | 8 -> 0 | 0 -> 0 | 0 -> 0 | 196 -> 188 | 8 | 0 |
| 2023 | 190 -> 190 | 8 -> 0 | 0 -> 0 | 0 -> 0 | 198 -> 190 | 8 | 0 |
| 2024 | 178 -> 180 | 8 -> 0 | 0 -> 0 | 0 -> 0 | 186 -> 180 | 8 | 2 |
| 2025 | 170 -> 170 | 8 -> 0 | 0 -> 0 | 0 -> 0 | 178 -> 170 | 8 | 0 |
| TOTAL | 908 -> 910 | 48 -> 0 | 0 -> 0 | 25 -> 0 | 981 -> 910 | 73 | 2 |

Danh sách dưới dùng locator `filing/page/N/link/M`; full local ID bằng document
content identity của filing trong D-01/inventory.json cộng `/page/N/link/M`.
Tất cả thuộc snapshot **D-01/normalized-v2**. Corrected snapshot là
**D-05/corrected-v1**, không reuse identity cũ để overwrite payload. Bản máy đọc
đủ full document/snapshot/local identity, label, code, raw value/header và source
selectors ở ignored `D-05-review-prep/removed-observations.json`;908 kept bindings
cũ→mới ở `retained-bindings.json`. Bảng này chỉ công bố locators và reasons,
không commit dataset/financial payload hoặc tên người ký.

Reason **N**: note-reference column, không phải financial period/value slot.
**S**: section header, không code/value tài chính. **F**: signature/footer với
role text, không giá trị tài chính. **U0**: blank null slot. **UT**: text tên người
ký trong value position, không mã/số liệu tài chính. Mọi raw evidence giữ nguyên.

| # | Filing | Original locator | Table/row/column | Role | Reason |
| ---: | ---: | --- | --- | --- | --- |
| 1 | 2021 | page/6/link/0 | 0/1/2 | note_reference | N |
| 2 | 2021 | page/6/link/3 | 0/2/2 | note_reference | N |
| 3 | 2021 | page/6/link/6 | 0/3/2 | note_reference | N |
| 4 | 2021 | page/6/link/9 | 0/4/2 | note_reference | N |
| 5 | 2021 | page/6/link/12 | 0/5/2 | note_reference | N |
| 6 | 2021 | page/6/link/15 | 0/6/2 | note_reference | N |
| 7 | 2021 | page/6/link/18 | 0/7/2 | note_reference | N |
| 8 | 2021 | page/6/link/21 | 0/8/2 | note_reference | N |
| 9 | 2021 | page/6/link/24 | 0/9/2 | note_reference | N |
| 10 | 2021 | page/6/link/27 | 0/10/2 | note_reference | N |
| 11 | 2021 | page/6/link/30 | 0/11/2 | note_reference | N |
| 12 | 2021 | page/6/link/33 | 0/12/2 | note_reference | N |
| 13 | 2021 | page/6/link/36 | 0/13/2 | note_reference | N |
| 14 | 2021 | page/6/link/39 | 0/14/2 | note_reference | N |
| 15 | 2021 | page/6/link/42 | 0/15/2 | note_reference | N |
| 16 | 2021 | page/6/link/45 | 0/16/2 | note_reference | N |
| 17 | 2021 | page/6/link/48 | 0/17/2 | note_reference | N |
| 18 | 2021 | page/6/link/51 | 0/18/2 | note_reference | N |
| 19 | 2021 | page/6/link/54 | 0/19/2 | note_reference | N |
| 20 | 2021 | page/6/link/57 | 0/20/2 | note_reference | N |
| 21 | 2021 | page/6/link/60 | 0/21/2 | note_reference | N |
| 22 | 2021 | page/6/link/63 | 0/22/2 | note_reference | N |
| 23 | 2021 | page/6/link/66 | 0/23/2 | note_reference | N |
| 24 | 2021 | page/6/link/69 | 0/24/2 | note_reference | N |
| 25 | 2021 | page/6/link/72 | 0/25/2 | note_reference | N |
| 26 | 2021 | page/9/link/0 | 0/1/2 | section_header | S |
| 27 | 2021 | page/9/link/1 | 0/1/3 | section_header | S |
| 28 | 2021 | page/9/link/4 | 0/3/2 | section_header | S |
| 29 | 2021 | page/9/link/5 | 0/3/3 | section_header | S |
| 30 | 2021 | page/9/link/32 | 0/17/2 | section_header | S |
| 31 | 2021 | page/9/link/33 | 0/17/3 | section_header | S |
| 32 | 2021 | page/9/link/42 | 0/22/2 | section_header | S |
| 33 | 2021 | page/9/link/43 | 0/22/3 | section_header | S |
| 34 | 2021 | page/9/link/58 | 0/30/2 | signature_or_footer | F |
| 35 | 2021 | page/9/link/59 | 0/30/3 | signature_or_footer | F |
| 36 | 2021 | page/9/link/60 | 0/31/2 | unknown | U0 |
| 37 | 2021 | page/9/link/61 | 0/31/3 | unknown | U0 |
| 38 | 2021 | page/9/link/62 | 0/32/2 | unknown | U0 |
| 39 | 2021 | page/9/link/63 | 0/32/3 | unknown | U0 |
| 40 | 2021 | page/9/link/64 | 0/33/2 | unknown | UT |
| 41 | 2021 | page/9/link/65 | 0/33/3 | unknown | UT |
| 42 | 2022 | page/8/link/0 | 0/1/2 | section_header | S |
| 43 | 2022 | page/8/link/1 | 0/1/3 | section_header | S |
| 44 | 2022 | page/8/link/4 | 0/3/2 | section_header | S |
| 45 | 2022 | page/8/link/5 | 0/3/3 | section_header | S |
| 46 | 2022 | page/8/link/34 | 0/18/2 | section_header | S |
| 47 | 2022 | page/8/link/35 | 0/18/3 | section_header | S |
| 48 | 2022 | page/8/link/44 | 0/23/2 | section_header | S |
| 49 | 2022 | page/8/link/45 | 0/23/3 | section_header | S |
| 50 | 2023 | page/8/link/0 | 0/1/2 | section_header | S |
| 51 | 2023 | page/8/link/1 | 0/1/3 | section_header | S |
| 52 | 2023 | page/8/link/4 | 0/3/2 | section_header | S |
| 53 | 2023 | page/8/link/5 | 0/3/3 | section_header | S |
| 54 | 2023 | page/8/link/34 | 0/18/2 | section_header | S |
| 55 | 2023 | page/8/link/35 | 0/18/3 | section_header | S |
| 56 | 2023 | page/8/link/44 | 0/23/2 | section_header | S |
| 57 | 2023 | page/8/link/45 | 0/23/3 | section_header | S |
| 58 | 2024 | page/10/link/0 | 0/1/2 | section_header | S |
| 59 | 2024 | page/10/link/1 | 0/1/3 | section_header | S |
| 60 | 2024 | page/10/link/4 | 0/3/2 | section_header | S |
| 61 | 2024 | page/10/link/5 | 0/3/3 | section_header | S |
| 62 | 2024 | page/10/link/32 | 0/17/2 | section_header | S |
| 63 | 2024 | page/10/link/33 | 0/17/3 | section_header | S |
| 64 | 2024 | page/10/link/42 | 0/22/2 | section_header | S |
| 65 | 2024 | page/10/link/43 | 0/22/3 | section_header | S |
| 66 | 2025 | page/8/link/0 | 0/1/2 | section_header | S |
| 67 | 2025 | page/8/link/1 | 0/1/3 | section_header | S |
| 68 | 2025 | page/8/link/4 | 0/3/2 | section_header | S |
| 69 | 2025 | page/8/link/5 | 0/3/3 | section_header | S |
| 70 | 2025 | page/8/link/32 | 0/17/2 | section_header | S |
| 71 | 2025 | page/8/link/33 | 0/17/3 | section_header | S |
| 72 | 2025 | page/8/link/40 | 0/21/2 | section_header | S |
| 73 | 2025 | page/8/link/41 | 0/21/3 | section_header | S |

### Hai EPS và năm corrections: exact bindings

Hai EPS cùng PDF2024 page9, label **18. Lãi cơ bản trên cổ phiếu**, code **70**,
table0/row19. Raw unit context là VND; semantic unit VND/share, scale1 theo label/
code và note21 PDF page25 (profit VND chia ordinary shares). Đây là unit semantics
có căn cứ nguồn, không phải PDF in trực tiếp string “VND/share”.

| Period/header | Raw -> normalized | Unit | Value selector | Label selector | Header selector |
| --- | --- | --- | --- | --- | --- |
| 2024 / Năm 2024 | 1.032 -> 1032 | VND/share | /tables/0/cells/93 | /tables/0/cells/90 | /tables/0/headers/3 |
| 2023 / Năm 2023 | 917 -> 917 | VND/share | /tables/0/cells/94 | /tables/0/cells/90 | /tables/0/headers/4 |

PDF SHA-256: `f4e696a85c65f33cb1a1fa982dbfc6b3dccb5a227d14084d5f02b0d673f57c54`; reviewed render SHA-256: `8dd3495925d96fb4d0f8f9203b95df2e63b0811e02dfc61e2a997cd6344aae84`.

Năm raw overlays cùng PDF2023 page5, raw token gốc `-turc`, effective glyph `-`,
normalized **null → null**. Review đối chiếu lại ảnh nguồn, không chuyển dash
thành zero. Mỗi selector bên dưới nằm trong exact-bound SourceReview mới.

| Code | Period/header | Value selector | Label selector | Header selector | Normalized |
| --- | --- | --- | --- | --- | --- |
| 152 | 2023-01-01 / 01/01/2023 | /tables/0/cells/64 | /tables/0/cells/60 | /tables/0/headers/4 | null -> null |
| 227 | 2023-12-31 / 31/12/2023 | /tables/0/cells/98 | /tables/0/cells/95 | /tables/0/headers/3 | null -> null |
| 227 | 2023-01-01 / 01/01/2023 | /tables/0/cells/99 | /tables/0/cells/95 | /tables/0/headers/4 | null -> null |
| 260 | 2023-12-31 / 31/12/2023 | /tables/0/cells/123 | /tables/0/cells/120 | /tables/0/headers/3 | null -> null |
| 261 | 2023-12-31 / 31/12/2023 | /tables/0/cells/128 | /tables/0/cells/125 | /tables/0/headers/3 | null -> null |

PDF SHA-256: `81d8035271a11a7421141dd8a4ce82c8280add30a8f75db35584c30b57d55a9a`; request ID: `1dd2593c-98e8-4be0-9595-1af0a8968754`; reviewed render SHA-256: `9aa3ce578ad47db98183ec89a59ec32c7010a0f58f506e3487438af5e55aaf68`.

### Phạm vi kiểm tra và kết quả thực tế

Đã đọc/rà soát **16 files thuộc D-05**: `.github/workflows/ci.yml`, hai docs
`d03-system-blocker-audit.md`/`d05-extraction-corrections.md`, bốn planning files
`current-status.md`/`progress.md`/`tasks.md`/`tasks/D/D-05.md`, evaluator,
sáu accounting files `automated_extraction.py`/`financial_runtime.py`/`quality.py`/
`completeness.py`/`extraction_semantics.py`/`raw_corrections.py`, evidence adapter
và `tests/unit/test_d05_corrections.py`. Thay đổi `web/next-env.d.ts` là local có
trước, giữ nguyên ngoài stage. CI chỉ thêm D-05 focused tests, không tắt checks.

16 generic test functions bao phủ missing middle/terminal/optional/incomplete
inventory/ambiguous/unreadable; header/note/section/signature/alphanumeric codes;
malformed tokens/nulls/immutable overlays; basic EPS vs monetary/mixed/unknown
units; snapshot isolation, company/period khác và monetary operands. Bổ sung hai
cases phát hiện trong review vào đúng tests hiện có. Runtime không có literals
BBS/company/year/PDF/page/snapshot riêng; code70 là versioned accounting semantics
catalog, source-bound BBS fixtures chỉ ở evaluator. Không benchmark/live call mới.

Revalidation lần này: **20 cached pages** giữ exact extraction/quality projection;
908 retained slots giữ code/label/header/period/numeric value/source references;
910 corrected facts/document-evidence restart exact;7 SourceReviews exact. D-04
catalog và graph exact, **baseline15/15**, **recovery3/3**,15 baseline +3 recovery
lineages exact; explicit snapshot selection/ancestry giữ nguyên. **2.457 input
hashes** và **39 D-05 input files** unchanged; zero Gateway attempts ở lượt review.

Local focused243 PASS (8.98s); Ruff lint/format toàn repository335 PASS;
planning98 và diff checks được chạy trước commit. CI của implementation là evidence
engineering riêng, không thay source review hoặc chứng minh full-PDF accuracy.

Next action: Tech Lead review D-05 và source evidence; không tự DONE/D-06/M4.
