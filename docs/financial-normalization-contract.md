# Financial Normalization Contract v1

M2-01 chỉ định nghĩa biểu diễn trung gian của `accounting`, sau `unified_document_v1`
và trước canonical evidence. Import qua `vietnamese_financial_multi_agent.accounting`.
Không đọc file nguồn, parse raw number, suy luận kỳ, mapping chỉ tiêu hay chạy quy tắc kế toán.

| Public API | Ý nghĩa |
| --- | --- |
| `FinancialValue` | raw_value nguyên văn; normalized_value Decimal/null; unit nullable; status resolved/uncertain/unresolved; issues list string |
| `FinancialContext` | period/period_type/currency/raw_item_label/mapped_item_code string/null; scale Decimal/null; reporting_scope separate/consolidated/null; statement_type B01/B02/B03/B09/null |
| `FinancialSourceReference` | SourceAnchor M1, source_pointer nullable và provenance_level page/element/cell (mặc định page) |
| `FinancialNormalizationResult` | contract_version bắt buộc financial_normalization_v1, value/context/provenance bắt buộc; financial_fact_verified luôn false |
| `financial_normalization_json_schema()` | Draft 2020-12 sinh trực tiếp từ models |
| `validate_financial_quality(result)` | Trả list UnderstandingIssue M1 code/path/message, không sửa model hay làm quality gate |

Structural validation dùng `FinancialNormalizationResult.model_validate(payload)` hoặc
`model_validate_json(text)`, ném `pydantic.ValidationError` khi sai kiểu/version/extras.
Python chỉ nhận Decimal cho normalized_value/scale; JSON chỉ nhận chuỗi Decimal hữu hạn
hoặc null. `model_dump_json()` và `export_result()` serialize Decimal thành chuỗi, giữ
độ chính xác và trailing zeros, không qua float. Raw `1.234.567`, `(1.234)`, `-` chỉ là
chuỗi nguyên văn; không được lấy làm normalized_value bằng contract này.

Context có thể là `{}` (mọi field null); không suy luận ngữ cảnh từ identity.year,
raw label hay unit. Period/period_type/currency/unit là metadata do caller cung cấp,
chưa có vocabulary/rules chuẩn hóa; scale là hệ số biểu diễn do caller cung cấp,
không tự nhân/chia normalized_value. Quy tắc áp dụng/đối chiếu còn TBD ở M2-02.
Status mô tả độ xác định của giá trị, không phải trạng thái xác minh tài chính.

Provenance tái sử dụng nguyên `SourceAnchor`/`RawPageIdentity` M1 (symbol/year/page/image,
source_ref optional), giữ status uncertain/unresolved và các raw IDs/bbox nếu có bằng chứng.
Document locator có thể ở source_ref; source_pointer là selector nguyên văn tới component
trong unified export, không phải raw ID. Native M1 chỉ page-level thì truyền anchor trang
và provenance_level=page; không lấy đường dẫn cells hoặc row/column làm cell ID.
Không tự tạo identity, bbox, IDs, resolve paths hay đối chiếu reference với tài liệu nguồn.

Quality signals gồm missing_raw_value, missing_normalized_value, value_not_resolved,
missing_unit, missing_context, missing_provenance, provenance_unverified,
page_level_provenance và inconsistent_provenance. Đây là tín hiệu review, không phải
accounting checks hay cổng xác minh. Không có issue vẫn không chứng nhận nguồn/financial fact.
Caller cần giữ giới hạn M1; validator không thể phát hiện ID giả nếu không có nguồn đối chiếu.

Schema tại `schemas/financial_normalization_v1.schema.json`; sinh lại bằng
`python scripts/export_financial_normalization_schema.py`. Schema mô tả wire types;
finite Decimal strings được Python kiểm tra thêm. Không có verification engine trong v1;
`financial_fact_verified=true` bị từ chối ngay cả khi value.status=resolved.

## Evidence M2-01 — 2026-10-28

- Baseline sạch: `8c351bee80b81f609074c94c502299ff94b83315`; M1-16 DONE.
- Local: 8 focused tests PASS (synthetic), gồm JSON round-trip/Decimal/raw, null context,
  page-level M1 consumer, invalid types/version, unverified facts, schema parity.
- Ruff lint/format 5 Python files PASS; planning checker 82 tasks PASS; diff check PASS.
- Implementation `471ea80a35f9968ba43b712d4806b54353136373` đã push;
  [CI40636728310](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40636728310)
  completed/SUCCESS đúng SHA: Python3.11/3.12 và mọi steps success.
- Không sửa M1/raw/dataset, không gọi API, không full local suite/benchmark.
- Chưa triển khai M2-02–07; không chứng minh financial extraction accuracy.
- Status REVIEW; next action: Chờ Tech Lead review.
