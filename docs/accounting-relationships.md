# Quan hệ kế toán — M2-06

## API và quy tắc

Public APIs trong `vietnamese_financial_multi_agent.accounting`:

- `evaluate_accounting_relationships(values, rules=RELATIONSHIP_RULES, *, tolerance_policy=None)`.
- `evaluate_automated_relationships(records, rules=RELATIONSHIP_RULES, *, tolerance_policy=None)`.
- `RelationshipValue`, `RelationshipItem`, `RelationshipRule`, `RelationshipCheck`,
  `RELATIONSHIP_RULES`; tái sử dụng `TolerancePolicy` từ M2-05.

```python
from vietnamese_financial_multi_agent.accounting import evaluate_automated_relationships

# records đã render/revalidate PDF-bound cache qua run_automated_pdf.
checks = evaluate_automated_relationships(records)
```

`RelationshipValue` bọc FinancialNormalizationResult, PDF SHA-256 có bằng chứng,
optional AutomatedLink, period_end_evidence (ContextEvidence) và source_metadata.
Provenance extraction phải trỏ `source_ref=sha256:<PDF hash>`; adapter đối chiếu thêm
trang và image hash với metadata do run_automated_pdf cung cấp. Adapter không tự
xác minh PDF trên đĩa; caller phải dùng run_automated_pdf trước, không truyền cache
chưa bind. Input gốc, link, source/PDF/image/model/request và selectors được snapshot
riêng cho từng toán hạng. Không sửa SourceAnchor hoặc tạo bbox/cell ID.

Registry gồm **1 active rule** `b01_b03.closing_cash`: B01 tiền và tương đương tiền
mã110 = B03 tiền cuối kỳ mã70, tại cùng ngày, scope, currency, unit và scale.
Căn cứ là quan hệ C được giao trong M2-06 và đối chiếu mẫu thực BBS2025 trang5/8;
không khẳng định applicability cho mọi cách trình bày báo cáo. Không hardcode mã
chứng khoán hoặc giá trị BBS vào production module.

Ưu tiên canonical ID. API trực tiếp cũng nhận source code trong mapped_item_code
(hoặc raw code của AutomatedLink có result) **kèm exact approved label và statement**.
Chỉ có cặp B01/110/`I. Tiền và các khoản tương đương tiền` và
B03/70/`Tiền và tương đương tiền cuối năm` được đăng ký. Không fuzzy matching;
canonical khác đã xác định không bị source-code fallback ghi đè. Adapter M2-04b
chỉ dùng accepted links có result; không tự nâng unresolved/raw rows thành accepted.
Giữ original records/payload và các nhãn ngoài catalog cho downstream QA.

Group theo PDF SHA/source_ref, **ngày kết thúc thực**, scope, currency, unit, scale;
statement được xác định riêng theo operand, page không là khóa grouping.
B01 chỉ dùng `as_of`; B03 dùng `fiscal_year_end` hoặc `fiscal_year` có evidence
ngày kết thúc tài chính rõ ràng và năm khớp. Bare year không được tự đổi thành 31/12.
Scope cả hai null được so sánh cùng PDF, giữ null và caveat `scope_unconfirmed`;
scope đã biết khác nhau hoặc một bên null được giữ thành các nhóm riêng.
Không chuyển 01/01 sang 31/12 năm trước; không đổi đơn vị/scale/currency.

Các trạng thái: `consistent`, `inconsistent`, `insufficient_data`, `not_applicable`.
Thiếu toán hạng, duplicate (kể cả cùng giá trị), unresolved hoặc metadata conflict
không tạo inconsistency. Khác context tạo các nhóm thiếu toán hạng riêng.
Không có statement liên quan là not_applicable; record có statement nhưng không có
accepted extraction là insufficient_data. Binding metadata sai ở adapter ném ValueError.

Mọi phép tính dùng Decimal với precision đủ chữ số; JSON Decimal là chuỗi.
`difference = computed_value - reported_value`; tolerance mặc định0.
Tolerance tùy chọn phải có basis và tính theo đơn vị hiển thị. Các công thức active
chỉ là đẳng thức tổng các operands, không có engine biểu thức động.
Output giữ description/statements/PDF/period/scope/currency/unit/scale, values,
difference/tolerance/basis, missing_inputs, issues, caveats và lineage từng operand.

Kết quả là annotation độc lập. Extraction vẫn dùng cho QA dù relationship thiếu
dữ liệu hoặc inconsistent; `financial_fact_verified=false`. Không kết luận báo cáo
đã đúng, vi phạm kế toán hoặc pháp luật.

## Pilot BBS2025 — 2026-10-28

Replay cache M2-04b retry/page5, retry/page7, live/page8 qua run_automated_pdf200DPI,
không lấy persisted extraction decisions làm sự thật. PDF SHA-256 trước/sau:
`6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`.
28 accepted extraction giữ nguyên; **0 Gemini calls, 0 trang bổ sung**.

```powershell
python scripts/run_relationship_pilot.py data/raw/Financial_Report_pdf/BBS/2025/BBS_2025.pdf --cache-root artifacts/item-mapping/M2-04b --output artifacts/relationships/M2-06/new-run
```

Đích phải chưa tồn tại. Artifact local ignored:
`artifacts/relationships/M2-06/final/relationships.json`; hash ghi trong spec/handoff.
Expected values/manual review không tham gia runtime. Sau runtime đã xem ảnh nguồn
trang5/8, đối chiếu mã110/70, kỳ, VND và số tiền:
3.711.595.064 − 3.711.595.064 =0. Một reviewer kỹ thuật, chưa là financial verification.

| Relationship | Period/context | Status | Difference | Source pages |
| --- | --- | --- | --- | --- |
| B01 ↔ B03 tiền cuối kỳ | 31/12/2025 | consistent | 0 VND | 5, 8 |
| B01 ↔ B03 tiền cuối kỳ | 01/01/2025 | insufficient_data | null | 5; thiếu B03 cùng ngày |
| B01 ↔ B03 tiền cuối kỳ | Năm2024, ngày cuối kỳ chưa xác nhận | insufficient_data | null | 8; thiếu B01 cùng ngày |
| B01 cân đối | 31/12/2025, 01/01/2025 | 2 insufficient_data | null | 5; chưa lấy nguồn vốn |
| B01 ↔ B02 lợi nhuận giữ lại | 31/12/2025, 01/01/2025, năm2024 chưa xác nhận ngày | 3 insufficient_data | null | 7 hoặc không toán hạng; thiếu B01/điều chỉnh |
| B03 reconciliation | 31/12/2025, năm2024 chưa xác nhận ngày | 2 insufficient_data | null | 8; thiếu mapping/FX |

Tổng **1 consistent / 0 inconsistent / 9 insufficient_data / 0 not_applicable**,
đếm rule × document/date/context, không phải số lỗi tài chính. Active rule riêng:
1 consistent và2 insufficient. Ba candidates unavailable tạo7 insufficient.
Không có bằng chứng mâu thuẫn từ phép kiểm tra thực duy nhất này.

| Unavailable candidate | Lý do |
| --- | --- |
| b01.balance_identity | Chưa xác nhận mã/nhãn tổng nguồn vốn; trang nguồn vốn ngoài pilot5/7/8 |
| b01_b02.retained_earnings | Thiếu số dư và phân phối/điều chỉnh; không dùng đẳng thức trực tiếp |
| b03.cash_reconciliation | Mã50/60 có raw values nhưng chưa map; ảnh không có dòng tỷ giá, không suy zero |

Không cần thêm trang để đạt check liên báo cáo thực. Giới hạn catalog/nguồn và lý do
giữ candidate unavailable ở [issue](../planning/tasks/M2/issues/M2-06-relationships.md).
Không chạy thêm PDF, toàn bộ24 trang, benchmark hoặc API thật.

## Engineering evidence

38 focused tests PASS; 72 regression trực tiếp arithmetic/automated extraction/contracts
PASS. Có integration từ mocked run_automated_pdf → revalidation → relationship và
kiểm tra nhãn ngoài catalog vẫn còn cho QA. Fixtures synthetic không là đo quality.
Ruff/planning/diff và exact SHA CI ghi tại [spec](../planning/tasks/M2/M2-06.md).
