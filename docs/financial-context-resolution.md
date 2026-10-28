# Financial context resolver — M2-02

Import qua `vietnamese_financial_multi_agent.accounting`. Resolver deterministic,
không đọc file/gọi API, parse số tiền, áp dụng scale hoặc xác minh financial fact.
Không thay schema `financial_normalization_v1` hoặc contracts M1.

```python
from vietnamese_financial_multi_agent.accounting import (
    evidence_from_unified_page,
    resolve_financial_context,
)

# page: UnifiedPage M1; caller chọn phạm vi trang/region cần giải quyết.
result = resolve_financial_context(evidence_from_unified_page(page))
context = result.context  # FinancialContext v1; chỉ chứa fields resolved.
```

`resolve_financial_context(Iterable[ContextEvidence])` giữ toàn bộ evidence, kể cả
text không match. Mỗi input gồm `raw_text`, list `FinancialSourceReference` nguyên
nguồn và `status` text M1 (mặc định resolved khi caller xác nhận text usable).
Không truyền identity.year/file thành text evidence cho reporting period.

Output `ContextResolution` có `context`, `period`, `unit`, `reporting_scope`,
`evidence`, `financial_fact_verified=false`. Mỗi field resolution có status,
candidates và issues; mỗi candidate có FinancialContext, evidence gốc, status/issues.
Thiếu match → unresolved; candidate không đủ nguồn/text chưa resolved, format đã
nhận diện nhưng invalid, mention hoặc giá trị khác nhau → uncertain. Không chọn
candidate đầu tiên khi khác giá trị hoặc khác period_type. Duplicate support cùng
giá trị không gây conflict; uncertainty của một candidate vẫn được giữ.

Các quy tắc dùng Unicode casefold/whitespace trên từng dòng để match; raw text
trong evidence không thay đổi. Period/unit cần dòng đầy đủ theo mẫu; scope chỉ
resolved khi cả dòng là title `Báo cáo tài chính riêng` hoặc `... hợp nhất`.
Mention trong câu/thuyết minh giữ candidate uncertain. Caller phải khoanh vùng
evidence đúng tài liệu; regex không hiểu trích dẫn/title của tài liệu khác khi
title đứng riêng một dòng, hoặc liên kết heading nhiều regions.

| Bằng chứng | period_type | period |
| --- | --- | --- |
| Năm 2025 / Năm tài chính 2025 | fiscal_year | 2025 |
| Cho năm tài chính kết thúc ngày 31/12/2025 | fiscal_year_end | 2025-12-31 |
| Tại ngày 31 tháng 12 năm 2025 | as_of | 2025-12-31 |
| Quý III năm 2025 (I–IV hoặc 1–4) | quarter | 2025-Q3 |
| 9 tháng đầu năm 2025 (1–12) | year_to_month | 2025-M01/M09 |
| Kỳ kế toán từ 01/01/2025 đến 31/12/2025 | date_range | 2025-01-01/2025-12-31 |

`fiscal_year_end` chỉ chứng minh ngày kết thúc, không tự đặt ngày bắt đầu năm
tài chính. `fiscal_year` giữ nhãn năm, không biến thành ngày/khoảng thời gian.
Ngày dạng d/m/yyyy hoặc d tháng m năm yyyy được kiểm tra calendar; khoảng đảo
ngược và số tháng không hợp lệ giữ uncertain. Không coi các period_type tương đương.
Định dạng khác/bare year chưa hỗ trợ có thể không match → unresolved.

`Đơn vị tính:` hoặc `Đơn vị:` với đồng/VND, nghìn đồng, triệu đồng → currency VND,
scale lần lượt Decimal(1/1000/1000000); Decimal JSON string theo v1. Dòng khai báo
đơn vị khác giữ candidate uncertain, kể cả khi có thêm candidate VND. Raw unit text
nằm nguyên trong candidate.evidence.raw_text; không nhân/chia giá trị tài chính.

`evidence_from_unified_page(UnifiedPage)` duyệt text regions và table cells;
text chỉ usable khi status accepted và quality.text_accepted/downstream_usable/
usable_for=text_evidence cùng đạt. Layout chưa accepted không tự làm text mất giá
trị bằng chứng; nhưng không mapping context vào ô/cột. Native giữ page-level và
selector, không tạo IDs/bbox; existing giữ raw IDs nếu cấp provenance cho phép.
Anchor status uncertain, geometry chỉ dùng khi M1 xác nhận verified/accepted.
Không làm source verification, sửa M1 hoặc nâng page-level thành cell-level.

## Evidence — 2026-10-28

Baseline sạch local/origin: `1ca5091f5f33e2cf5dd082fdb068d08b116b34d0`, M2-01 DONE.
Synthetic: 10 focused cases M2-02 + 8 regression contracts M2-01 PASS local trong
`.[dev]`; period formats, Decimal, title/mention, missing/conflicts, raw/provenance,
metadata, invalid dates/ranges/units, unaccepted text và hai nhánh M1 adapter.
Ruff lint/format accounting + test, planning checker 82 tasks và diff check PASS.
Không full local suite, benchmark, Gemini hoặc API.

Pilot read-only **5 trang khác nhau**; kỳ vọng được đối chiếu thủ công với toàn
bộ text được đưa vào resolver, gồm table cells. Không dùng schema PASS làm đánh
giá đúng/sai. Không human second review hoặc đối chiếu PDF/ảnh; đây chỉ là đánh
giá theo văn bản OCR M1. Hai trang native có nhãn kỳ so sánh nên phải uncertain.

| Mẫu | Period | Unit | Scope |
| --- | --- | --- | --- |
| BBS2025 trang5, existing M1-16 | resolved: as_of 2025-12-31 | resolved: VND ×1 | unresolved: thiếu evidence |
| BBS2025 trang7, native M1-16 | uncertain: fiscal_year_end 2025-12-31 và Năm 2025/2024 | resolved: VND ×1 | unresolved |
| BBS2025 trang8, native M1-16 | uncertain: fiscal_year_end 2025-12-31 và Năm 2025/2024 | resolved: VND ×1 | unresolved |
| BCC2025 trang1, raw OCR M1 | unresolved: chỉ narrative, không dòng kỳ hỗ trợ | unresolved | uncertain: mention hợp nhất |
| BED2025 trang1, raw OCR M1 | resolved: fiscal_year_end 2025-12-31 | unresolved | unresolved |

5/5 mẫu khớp trạng thái/giá trị kỳ vọng sau khi đối chiếu đầy đủ cells. 15 trường:
**5 resolved đúng, 0 resolved sai, 3 uncertain, 7 unresolved**. Các uncertain/
unresolved là abstention phù hợp nguồn, không tính thành financial accuracy.
Ví dụ nguồn: `Tại ngày 31 tháng 12 năm 2025`, `Đơn vị tính: VND`,
`Cho năm tài chính kết thúc ngày 31/12/2025`; BCC là câu công bố về báo cáo hợp
nhất, không title của chính trang. Chưa có mẫu thực scale nghìn/triệu hoặc title
riêng/hợp nhất trong pilot; các dạng này chỉ được kiểm tra bằng synthetic tests.
Không suy độ chính xác toàn dataset từ 5 trang này.

Artifacts local ignored: `artifacts/context-resolution/M2-02/pilot.py`, `pilot.json`.
Receipt giữ full raw text/candidates/anchors, selector, expected/actual và SHA256;
4 files đầu vào không đổi hash trước/sau. Nguồn unified tại
`artifacts/document-understanding/M1-16/{existing,native}.json`; raw tại
`data/processed/Financial_Report_OCR/{BCC,BED}/2025/ocr_json/page_1.json`.
Chỉ tài liệu aggregate này vào Git; không dataset, OCR export hoặc locator cá nhân.

CI exact implementation SHA: đang chờ commit/push và xác minh; dừng REVIEW.
