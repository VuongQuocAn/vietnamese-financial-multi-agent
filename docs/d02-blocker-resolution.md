# D-02 — Blocker audit và analytical readiness

Baseline từ accepted D-01 `0f2ca61`, kiểm tra trực tiếp artifacts ngày 30/10/2026.
Audit này lập trước khi sửa implementation; artifacts riêng `artifacts/evidence/D-02/`.

| ID / source | Root cause / loại | Records / metrics | Mức | Existing evidence | Fix / acceptance | Status baseline |
| --- | --- | --- | --- | --- | --- | --- |
| A / D-01 | Không có scope explicit; thiếu metadata thật, không phải mất binding | 981 facts; 15 metrics; 36 pairs | P1 | normalized-result context, PDF headers chưa thấy riêng/hợp nhất | Đọc 20 primary pages; chỉ bind khi có nguồn; profile same-document phải chờ Tech Lead | OPEN |
| B / M3-01,D-01 | Anchor page uncertain; chưa có bản ghi visual verification riêng | 30 operand occurrences / 15 metrics | P1 | sources/source_pointer, D-01 48 spot checks | Verification riêng có observation/snapshot/PDF hash/page/selector/label/header/value; không sửa anchor | OPEN |
| C / M3-01,D-01 | Mọi 30 operand occurrences chỉ có resolution issue missing_reporting_scope; generic unresolved_operand_context gộp lý do | 15 metrics | P1 | Audit facts_from_persisted_result: period/type/statement/VND/scale=1/unit đã đủ | Trả exact context blockers; giữ global engine và original issues; không bịa context | OPEN |
| D / D-01 Q07 | Extractor khai columns=3 nhưng header/body có column=3 (zero-based); validator đúng | B03/2022 page 8, cả bảng; 1 query | P1 | Original payload table dimensions và out-of-bounds 27 cells/header | Một full-table Gateway recovery attempt mới; M2 tự đánh giá, giữ original; so alignment/headers/values/periods | OPEN |
| E / M3-05 | Formula policy reference_example, chưa approved | 15 metrics | P1 | FormulaDefinition.policy_status | Không executor/không approve; Tech Lead quyết định policy và M4 tiếp nhận | OPEN / decision required |
| F / D-01 | Unknown scope giữa các filings; numeric equality không chứng minh consistency | 36 pairs | P1 | cross-year.json: 36 equal,36 undetermined | Giữ undetermined nếu không đủ evidence; Tech Lead quyết định scope evidence | OPEN |
| G / D-01 | Catalog thiếu short-term liabilities; header slots không có period/numeric; outside target metrics | 816 unmapped; 5 mapped header slots; Q25 | P2 | Summary, fixed queries, quality blocked header observations | Giữ mapping gap/blocked, không mở rộng taxonomy | DEFERRED trong scope D-02 |
| H / D-01 | Chưa independent human gold/full-PDF accuracy; accounting basis chưa kiểm chứng | 981 observations | research limitation | D-01 chỉ 48 controlled visual cells | Không gọi Gemini self-check là independent; unknown accounting basis chặn eligibility | OPEN |

Không tự coi experimental profile là approved. P1 chưa đóng cần quyết định Tech Lead;
REVIEW implementation không đồng nghĩa analytical readiness hay nghiệm thu DONE.

## Disposition sau implementation

D-02 dừng REVIEW, chưa commit tại thời điểm lập báo cáo. Tech Lead quyết định
nghiệm thu/risk acceptance; Owner quyết định thay đổi phạm vi, agent không tự duyệt.

| ID | Sau D-02 | Quyết định còn cần |
| --- | --- | --- |
| A | Đọc 20 primary headers + thuyết minh; scope vẫn unknown, zero bindings. Profile riêng `D-02/document-statement-v1`, experimental | Tech Lead duyệt/bác exception cùng statement/document/snapshot; không cho cross-statement/document |
| B | Đóng trong selected operands: 25 value-row reviews/30 occurrences; thêm 2 OCF recovery reviews, original page/uncertain giữ nguyên | Review evidence; không áp dụng cho 956 baseline observations còn lại |
| C | 30 occurrences chỉ thiếu reporting_scope; không có adapter binding bug. Trả exact issues, giữ original issues | Liên kết A, còn mở; không khai đã bổ sung scope |
| D | Đóng target table-position blocker qua attempt mới, Q07 available có caveat | Recovery còn lỗi năm ở ngày ký, chưa verified toàn bảng |
| E | Formula vẫn reference_example; eligibility false | Tech Lead duyệt formula/execution policy |
| F | Đúng 36 pairs vẫn undetermined vì scope, dù numeric equal | Scope evidence mạnh hơn/approved decision; không suy từ ticker/equality |
| G | Q25 thiếu mapping, giữ 816 unmapped và header slots | Outside target metrics, không mở taxonomy |
| H | Chưa independent human gold/full-PDF accuracy/verified claim | Giữ research limitations; accounting basis cho selected B01/B02 đã tìm được |

Blocker P0: 0 trước/sau. P1: 6 (A–F) trước, B/D đóng trong selected scope,
A/C/E/F còn mở (C chung root cause A). Chưa có quyết định chấp nhận P1 của Tech Lead;
chưa đạt strict success/analytical readiness được phê duyệt.

## Source-backed findings và verification

Ảnh local ignored D-02: `headers-{year}.png`, `{year}-{page}.png` và
`basis-{year}-{page}.png`. Thuyết minh 2021:10, 2022:9, 2023:9, 2024:11, 2025:9
ghi VAS/TT200, dồn tích (ngoại trừ một số cash flow), giá gốc và hoạt động liên tục
tại mục 3/4.1. Filing 2025 nhắc thay đổi chế độ kế toán áp dụng từ 2026, không áp
hồi tố cho operands 2025. Ảnh thuyết minh 2025 xoay 180° chỉ để đọc. Accounting
basis records chỉ hỗ trợ B01/B02, không tự áp cho B03; không suy scope từ basis.

SourceReview riêng giữ observation/snapshot, anchors gốc, PDF SHA-256/page,
review render hash/reference/method, exact value/label/header/period và selectors.
Evaluator re-render PDF, kiểm tra cached image binding, resolve ba selectors cùng
bảng/row/column, unique positions và raw-normalized value. Source missing,
inconsistent, unverified, page_resolved và value_row_verified được phân biệt;
không cho cell_verified vì chưa có evidence geometry. Không sửa uncertainty gốc.

25 unique operands gồm current/prior revenue, current gross profit, assets và
liabilities mỗi filing. Tám B01 readings 2021–2024 reuse controlled D-01 source-bound
spot checks; 17 readings còn lại và hai OCF recovery readings đọc trực tiếp PDF ảnh.
Đây là controlled visual read của implementation agent, **không independent human
gold**, không dùng Gemini tự xác nhận output Gemini. Không lan spot-check sang 981 facts.

## Cùng 15 metrics trước/sau

API `evidence.analytical_readiness.assess_analytical_readiness()` giữ nguyên global
`approved_compatibility` và trả candidate riêng. Profile chỉ xem xét unknown scope
exception trong cùng statement/document/snapshot, mọi operand có value-row review.
Không tự điền separate. Khác scope/period/item/role, unit/scale mismatch, source
mismatch, quality insufficient/conflicted, unknown accounting basis hoặc extra
unresolved issues vẫn chặn. Không có tham số tự approve profile/formula.

| Cùng sample D-01 | Trước | Sau |
| --- | ---: | ---: |
| Complete metrics / operand occurrences | 15 / 30 | 15 / 30 |
| Period/type/statement/currency/scale/unit complete occurrences | 30 | 30 |
| Scope complete occurrences | 0 | 0 |
| Separate source review records cho metric operands | 0 | 25 |
| Value-row reviewed occurrences | 0 | 30 |
| Source-backed accounting-basis records | 0 | 5 |
| Approved compatible / undetermined / incompatible | 0 / 15 / 0 | 0 / 15 / 0 |
| Experimental candidate compatible / undetermined / incompatible | Chưa có profile | 15 / 0 / 0 |
| Calculation eligible / computed / verified claims | 0 / 0 / 0 | 0 / 0 / 0 |

Mỗi năm giữ cùng gross_margin, debt_to_assets, revenue_yoy: ba candidate compatible,
ba approved undetermined. Candidate source readiness không cấp phép thực thi.
Per-metric evidence trong `metrics-readiness.json`, `metric-source-links.json`,
`source-reviews.json`, `accounting-basis-reviews.json`. Eligibility blockers:
`compatibility_profile_not_approved`, `formula_policy_not_approved`; global scope/
source uncertainty/resolution issues vẫn giữ nguyên.

## B03/2022 và fixed regressions

Đúng một full-table page-8 recovery qua existing Gateway Free Tier,
`gemini-3.5-flash-lite`: **1 attempt, 7,312 provider-reported tokens** (1,299 input,
6,013 output), zero provider errors. Không discovery/full-PDF/multi-year live reruns.
Response đã lưu trước khi helper cleanup gặp AttributeError do sai thuộc tính pool;
process kết thúc, không mất response/không gọi lại API. Evaluator chính dùng pool.close().

Attempt mới `D-02/recovery-2022-v1`, parent `D-01/normalized-v2`, original giữ nguyên.
32 rows giữ nguyên, columns 3 → 4; headers 4 → 4, body cells 116 → 120.
60/60 code/label/period keys match; numeric values không đổi. Một placeholder
`- N/A` → `-`, normalized vẫn null, không thành zero. Hai OCF values/headers
current/comparative khớp PDF. M2 tự đánh giá 60 B03 observations:
60 insufficient → 8 usable / 43 usable_with_caveat / 9 insufficient, không override.

**Recovery limitation:** ngày ký mới bị đọc năm 2022 trong khi ảnh in 2023.
Giữ nguyên lỗi này trong extraction/context comparison; không dùng ngày ký làm kỳ
tài chính, period operands lấy từ headers 2022/2021. Chỉ hai OCF rows được review,
không gọi toàn bảng verified. Nếu downstream cần ngày ký, corrective action nhỏ nhất
là review/binding đúng dòng này; không cần API call nữa trong target hiện tại.

29 fixed queries: **22 → 23 available**, **1 → 0 quality blocked**; 4 ambiguous,
1 missing mapping, 1 absent snapshot giữ nguyên. Q07 là category thay đổi duy nhất.
Các queries khác giữ values; get_sources vẫn resolve citations.
981 observations trước/sau, exact retrieval 981/981, recovery repository restart
exact, graph structural valid. 15 original metric lineages exact với D-01.
36 original/comparative pair keys đánh giá cả trước/sau recovery: numeric equal,
36 undetermined vì reporting_scope; không chọn lại pairs/deduplicate.

## Validation, integrity và cách chạy

120 focused/core PASS: 18 D-02 cases + 102 compatibility/evidence/lineage regressions.
Controls gồm khác scope/document/statement/snapshot/period/unit/scale, wrong raw/
normalized value/row, ambiguous position, missing source, quality blocked/conflicted,
unknown accounting basis, extra unresolved context, unsupported cell upgrade,
overwrite attempt. CI thêm đúng D-02 test file; không full regression/frontend local.

```powershell
.venv/Scripts/python.exe scripts/evaluate_d02_blockers.py
.venv/Scripts/python.exe -m pytest tests/unit/test_d02_readiness.py tests/unit/test_evidence_contracts.py tests/unit/test_canonical_facts.py tests/unit/test_document_evidence.py tests/unit/test_evidence_graph.py tests/unit/test_derived_metrics.py tests/unit/test_metric_lineage.py tests/unit/test_evidence_retrieval.py -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe scripts/check_planning.py
git diff --check
```

Prepared visual inputs/review images phải có local. `--recover-live` chỉ opt-in một
trang khi chưa có cache; không tự tạo visual gold. Evaluator từ chối thay existing
output khác nội dung. SourceReview không mở filesystem; caller evaluator resolve
PDF/image/selector từ local sources đã chọn. Không sửa global compatibility.

**2,352 input SHA-256 trước = sau**, gồm accepted D-01 artifacts, PDFs/OCR và unrelated
web/next-env.d.ts. Năm PDF hashes giữ đúng bảng D-01; full manifest ignored
`D-02/hashes-before.json`. Không commit readings/dataset/PDF/OCR/ảnh/payload/secrets.
Ruff toàn repo/planning/diff và exact SHA/CI ghi trong spec khi hoàn tất Git workflow.

Next action: Tech Lead review D-02 và quyết định scope/profile/formula policy;
không tự DONE hoặc bắt đầu M4-01.
