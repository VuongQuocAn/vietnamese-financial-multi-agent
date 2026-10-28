# Kiểm tra số học — M2-05

## API và giới hạn

Public API trong `vietnamese_financial_multi_agent.accounting`:

- `evaluate_arithmetic_rules(values, rules=ARITHMETIC_RULES, *, tolerance_policy=None)`
  nhận `FinancialNormalizationResult` hoặc `AutomatedLink`, trả `ArithmeticCheck`.
- `evaluate_automated_records(records)` nhận records **đã revalidate** từ
  `run_automated_pdf`, trả annotations riêng kèm PDF/image/model/request provenance.
- `ArithmeticRule`, `ArithmeticCheck`, `TolerancePolicy`, `ARITHMETIC_RULES`.

```python
from vietnamese_financial_multi_agent.accounting import evaluate_automated_records

# records lấy từ run_automated_pdf(..., cached_records=cache); không cần service/key.
annotations = evaluate_automated_records(records)
```

Checker chỉ tính các đẳng thức cộng/trừ được chỉ định. Registry gồm **1 rule active**
và **4 ứng viên unavailable**, không có engine biểu thức hoặc LLM calculation.
Canonical IDs chưa có catalog trong các ứng viên chỉ là tên dành trước;
không tạo mappings hoặc nhận diện nhãn mới. B02 active: mã20 =10 −11, giá vốn in
dương trên ảnh BBS2025 trang7, kỳ `fiscal_year`, VND. Căn cứ là công thức ứng viên
người dùng giao và đối chiếu nhãn/mã/dấu/số trên mẫu báo cáo thực.

Nhóm tính theo statement/period/period_type/reporting_scope/**exact page identity**
(symbol/year/page/image/source_ref). Kể cả scope đã biết, bản MVP này chỉ tính
trong cùng trang nguồn; chưa hỗ trợ toán hạng nằm ở nhiều trang. Scope null giữ null,
không suy separate/consolidated. Provenance nhiều trang trong một giá trị báo
`source_page_context_ambiguous`; không trộn các tài liệu chỉ vì cùng mã/kỳ.

Unit phải có và giống nhau; scale phải có, dương và giống nhau. Currency nếu có
phải khớp unit. Không nhân/chia scale hoặc đổi đơn vị. Decimal toàn bộ, precision
cục bộ đủ cho mọi chữ số và carry, không phụ thuộc precision mặc định28 của caller.
Mặc định tolerance = Decimal0. Tùy chọn `TolerancePolicy(absolute=Decimal("0.5"),
basis="căn cứ làm tròn đã được xác nhận")` tính theo đơn vị hiển thị; không tự suy
tolerance từ scale. Pilot dùng exact0, không làm tròn.

`difference = computed_value - reported_value`, PASS khi abs(difference) <= tolerance.
`insufficient_data` cho missing/value unresolved/duplicates/unit-scale conflict hoặc
rule unavailable; không mặc định missing bằng zero, không chọn duplicate đầu tiên.
`not_applicable` khi không có statement tương ứng hoặc period_type ngoài rule;
adapter biết statement từ record nhưng không có accepted link trả insufficient_data.
`missing_inputs` liệt kê IDs thiếu; `issues` giữ lý do conflict/unavailable.
Mỗi check giữ source_pages, formula/tolerance basis, reported/computed/difference,
toán hạng có dấu và bản sao đầy đủ extraction/provenance/link gốc.
Decimal JSON là chuỗi, hỗ trợ model_dump_json/model_validate_json round-trip.

Extraction không bị sửa bởi checker. Arithmetic failure/thiếu dữ liệu không hạ trạng thái
accepted_extraction; tất cả financial_fact_verified vẫn false. Original records phải
được giữ cho downstream QA, gồm raw label/code/header/value và payload nhãn ngoài catalog.
Annotations không thay thế extraction output, không là cổng bắt buộc cho QA/report.

## Pilot BBS2025 — 2026-10-28

Replay cache M2-04b cuối: retry/page5, retry/page7, live/page8; render lại PDF200DPI
qua `run_automated_pdf`, xác minh image binding và validation, không tin extraction
quyết định lưu sẵn. **0 live calls**; 28 accepted extraction giữ nguyên.
PDF SHA-256 trước/sau:
`6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`.

```powershell
python scripts/run_arithmetic_pilot.py data/raw/Financial_Report_pdf/BBS/2025/BBS_2025.pdf --cache-root artifacts/item-mapping/M2-04b --output artifacts/arithmetic/M2-05/new-run
```

Thư mục đích phải chưa tồn tại. Kết quả local ignored:
`artifacts/arithmetic/M2-05/final/arithmetic.json`, SHA-256
`6784479f9a03a0c16802fe18a0a33adea0e8665917c28706ec4639e8e8c82ce9`.
Không đưa cache/normalized values/ảnh/PDF lên Git; chỉ công bố evidence ngắn này.

Đếm **rule × kỳ × source context**, chỉ các statement hiện diện trong pilot:

| Báo cáo | Passed | Failed | Insufficient | Not applicable |
| --- | ---: | ---: | ---: | ---: |
| B01 | 0 | 0 | 4 | 0 |
| B02 | 2 | 0 | 2 | 0 |
| B03 | 0 | 0 | 2 | 0 |
| Tổng | 2 | 0 | 8 | 0 |

Một rule đủ toán hạng, chạy **hai phép kiểm tra thực**. Đã đọc ảnh trang7 và đối chiếu
nhãn/mã10/11/20, hai cột năm, VND và chữ số; một reviewer kỹ thuật sau chạy:

- 2025: 450.474.531.227 −417.992.011.559 =32.482.519.668, khớp reported, difference0.
- 2024: 355.507.372.286 −319.074.961.905 =36.432.410.381, khớp reported, difference0.

Không có công thức chạy thực bị chênh lệch. FAILED/difference chỉ được kiểm thử bằng
fixtures synthetic, không coi là phát hiện lỗi tài chính BBS2025.

| Ứng viên chưa chạy | Thiếu gì / căn cứ nguồn |
| --- | --- |
| B01 tổng tài sản | current_assets/noncurrent_assets chưa có catalog; mã100/200 có trong ảnh/cache trang5 |
| B01 tổng nguồn vốn | total_funding/liabilities/equity chưa có catalog và không có trang nguồn vốn trong pilot5/7/8 |
| B02 doanh thu thuần | sales_revenue/revenue_deductions chưa map; mã02 là dấu gạch, không suy zero |
| B03 lưu chuyển thuần | net_cash_flow mã50 có trên ảnh/cache trang8, chưa có canonical mapping |

Không mở rộng catalog vì đã có rule thực có ý nghĩa; không tự bật các ứng viên dù
caller truyền đủ IDs, phải xác minh và bỏ unavailable_reason sau review.
Xem [issue giới hạn catalog](../planning/tasks/M2/issues/M2-05-arithmetic-checks.md).
Provenance giữ PDF SHA/renderer/DPI, page/image identity, model/request và selectors
context/header/label/code/value, không giả bbox/raw OCR IDs. Arithmetic PASS chỉ nói
đẳng thức khớp trên các extraction tham gia; chưa xác minh độc lập financial facts,
accuracy toàn dataset hay các quan hệ liên báo cáo M2-06.

## Kiểm tra engineering

28 focused tests M2-05 PASS; 84 targeted tổng cộng với automated extraction,
financial item mapping và normalization contracts PASS. Ruff changed files PASS.
Planning/diff checks và CI đúng SHA ghi trong [spec](../planning/tasks/M2/M2-05.md).
CI dùng synthetic fixtures, không đọc PDF riêng hoặc gọi Gemini thật.
