# D-07 — Reporting scope source resolution

Ngày02/11/2026 (Asia/Bangkok). Status **IN_PROGRESS**, chuẩn bị implementation
commit/CI trước REVIEW. Baseline main `f0b4328e68597b0ff37760ffe2507203c4c19e51`.
Chỉ giải quyết reporting scope; không mở cross-document execution/M4-02.

## Kết luận từ nguồn

Đã tìm trong **133 cached OCR pages**, kiểm cached extraction/context và đọc
trực tiếp **38 original PDF pages**: cover, audit opinion, basis và các keyword
candidates. Không Gemini/OCR/re-extraction. Không suy scope từ tên công ty,
ticker, absence of consolidation wording hoặc các đoạn mô tả bên liên quan.

Selected snapshot của cả5 original filings: **`D-01/normalized-v2`**. Document ID
bằng `sha256:` cộng exact PDF hash ở bảng. Recovery2022 không tự kế thừa review.

| Filing | Exact PDF SHA256 | Scope / evidence status | PDF pages đã đọc trực tiếp | Root cause |
| --- | --- | --- | --- | --- |
| 2021 | `bcf81efa8b41b7dc5221ce6cd12b7a62bdbf97ae52983c1e7ae58789e2740353` | unknown / insufficient | 1–5,10,13–14 | Chưa tìm được explicit filing-scope declaration trong phạm vi kiểm tra |
| 2022 | `480854b56c27737c9327e3f7650f8f6fde84fbcaab552b83dbbe72431c9da0ee` | unknown / insufficient | 1–4,9,12 | Nguồn chưa đủ xác nhận; audit/basis không xác định perimeter |
| 2023 | `81d8035271a11a7421141dd8a4ce82c8280add30a8f75db35584c30b57d55a9a` | unknown / insufficient | 1–4,9–10,12–13 | Nguồn chưa đủ xác nhận, không lấy wording về bên liên quan làm scope |
| 2024 | `f4e696a85c65f33cb1a1fa982dbfc6b3dccb5a227d14084d5f02b0d673f57c54` | **separate / confirmed** | 1–6,11,14–15 | Filing declaration checkbox đã có trong PDF/OCR nhưng chưa đưa vào context; resolver thiếu selected-option semantics |
| 2025 | `6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1` | unknown / insufficient | 1–4,9,12–13 | Nguồn chưa đủ xác nhận; basis/TT200 không đồng nghĩa separate |

**2024 PDF page1:** dấu X nằm tại option:
“BCTC riêng (TCNY không có công ty con và đơn vị kế toán cấp trên có đơn vị trực thuộc);”.
“BCTC hợp nhất” và “BCTC tổng hợp” đều unchecked. OCR source selectors lần lượt
`/elements/40`, `/elements/41`, `/elements/42` (checkbox_001/002/003). PDF page2
ghi tài liệu đính kèm là BCTC2024 đã kiểm toán; audit opinion thật ở PDF page6,
basis ở page11. Đây là phạm vi chính bộ báo cáo này, không phải subsidiary example.

Các basis sources của trường hợp insufficient:2021p10 `/elements/33/text`
“4.1. Cơ sở lập báo cáo”;2022p9 và2023p9 `/elements/36/text` “Cơ sở lập báo cáo”;
2025p9 `/elements/7/text` “4.1. Cơ sở lập báo cáo”. Đã đọc cả nội dung dồn tích/
giá gốc/going concern ở các trang này; không có scope declaration đủ rõ tại đó.
Các keyword “riêng” ở policy borrowing costs/other income không nói reporting scope.
Đây là kết luận insufficient sau kiểm tra có hệ thống, **không phải** chứng nhận
mọi OCR token/toàn PDF chính xác hoặc bằng chứng scope chắc chắn không tồn tại.

## Root cause và production fix

Before: cả981 original facts có scope=None; cover2024 không nằm trong financial
statement pages/context đã dùng cho canonical operands. Raw OCR đã giữ đúng ba
checkbox labels/checked/choice. Không có lỗi detector cần OCR lại. M2 context
adapter chỉ nhận text/table regions, còn scope parser chỉ nhận full title
“báo cáo tài chính riêng/hợp nhất”; không thể dùng selected “BCTC riêng (...)”.

`src/accounting/context_resolution.py` thêm `evidence_from_ocr_scope_choices`:
read-only Raw OCR adapter, explicit PDF page identity, giữ selectors/element IDs,
không sửa raw Colab paths. `ContextEvidence.scope_selection` mang selected/
unselected/unknown; checked/choice bất đồng giữ unknown. Raw candidates vẫn
unresolved cho tới controlled original-PDF verification. Resolver hiểu selected
filing-scope option, bỏ unchecked options khỏi scope inference nhưng giữ trong
evidence, unknown/unsupported/multiple conflicting choices fail closed. Title và
narrative behavior cũ được giữ; không suy separate từ “không có công ty con”.

`src/evidence/reporting_scope.py` thêm versioned `ReportingScopeReview` và
`ReportingScopeResolution`. Review chứa document/snapshot/PDF hash/page, exact
quote, scope, role của evidence, original source references, render hash và
verification/inspection references. Chỉ role `filing_scope` được resolve;
`other_entity`/`inspected_context` giữ provenance nhưng không xác định filing scope.
Runtime revalidate quote/value/source binding, giữ cả nguồn khi conflict.
Selected reviews được deep-copy trước khi dựng context result;negative control
đã tái hiện và chặn việc caller sửa object trả về làm thay đổi review nội bộ.

`SnapshotCatalog.get_reporting_scope(document_id, snapshot_id)` trả overlay riêng,
không latest/parent fallback/merge. JSON restart qua existing model contracts,
không thêm database/repository engine. New PDF dùng cùng API, không company/year/
PDF hash trong production code. Original SourceFact/FinancialContext và global
M3 assessments giữ nguyên; overlay có scope không tự là execution authority.

After:2024 exact-bound scope overlay **resolved/separate**, restart exact; bốn
filings còn lại **unresolved/None**, reason `reporting_scope_source_insufficient`.
Không bind review sang D-04 recovery hoặc D-05/D-06 snapshot khác.

## Validation và artifacts

**273 focused PASS**, gồm17 generic scope cases/hai independent synthetic
documents,10 existing context tests và246 M3/M4/D-02/D-04/D-06 regressions.
Controls: separate/consolidated, mixed/conflicting sources, unknown/unverified
selection, missing/source/document/snapshot/hash/selector/quote/value/verification,
insufficient, unsupported tổng hợp, subsidiary description, parent isolation,
restart/immutability và scope không tự cấp formula execution.
JUnit cuối ignored `artifacts/evidence/D-07/final-focused-tests.xml`, SHA256
`ebbbef45df3cbedf29b26d3e50a25e613284971a60104758daff7a7ea4e5305c`.

Real regression với scope reviews đã nạp vào production catalog: **15/15 original
+3/3 recovery eligible**,18 closure outputs và18 reviewed lineages exact với
accepted M4-01;**36 cross-document pairs vẫn undetermined**,29 retrieval queries
exact. Original facts/snapshots/lineage/source references và D-02/M4 policies
không ghi đè;**2.573 protected input hashes before=after**,computed0,zero Gateway.
Sau fix read-only cuối,5 scope views trên persisted real reviews được kiểm lại
exact và hash inputs không đổi (`final-scope-regression.json`);giữ bằng chứng
regression15+3/36 đã PASS vì metric compatibility/policies không thay đổi.

Ignored `artifacts/evidence/D-07/`: cache-inventory/candidates,38 original renders
(renders+extra-renders),source-inspections,reporting-scope-reviews,scope-results
(before/after,exact bindings,source quotes/reasons),metric-closures,cross-document,
hashes và summary. Runtime không phụ thuộc các evaluation paths này.

Tái hiện ở **directory mới**, đọc original renders trước khi evaluate:

```powershell
.venv/Scripts/python.exe scripts/evaluate_d07_scope.py --output artifacts/evidence/D-07-reproduce --prepare
.venv/Scripts/python.exe scripts/evaluate_d07_scope.py --output artifacts/evidence/D-07-reproduce
```

## Disposition và Git

D03-B10 **chỉ giải quyết một phần**: root cause2024 được sửa, bốn scopes còn
UNKNOWN vì insufficient source. Giữ blocker cho cross-document comparisons;
dependency tiếp theo là source-backed filing declarations cho2021/2022/2023/2025
hoặc policy comparison riêng được Tech Lead phê duyệt trong task tương lai.
Không liên tục audit lại cùng nguồn như một implementation bug; không tự cấp
document-pair exception hoặc lan scope2024 sang các năm khác.

Implementation chưa commit; CI chưa chạy. Dừng REVIEW sau validation/Git/CI,
chờ Tech Lead nghiệm thu; không bắt đầu M4-02 hoặc cross-document execution.
Next action duy nhất sau bàn giao: Tech Lead independent review D-07.
