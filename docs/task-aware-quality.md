# Đánh giá chất lượng theo tác vụ — M2-07

## API và cách sử dụng

Public APIs trong `vietnamese_financial_multi_agent.accounting`:

- `evidence_from_automated_records(records)` tạo snapshots cho cả accepted links và raw rows.
- `assess_evidence_for_task(evidence, task_type="direct_qa", *, required_evidence_ids=(), arithmetic_checks=(), relationship_checks=(), require_check=False)`.
- `assess_automated_records(records, task_type="direct_qa", **kwargs)` là adapter tiện dụng.
- Contracts: `AssessableEvidence`, `QualityIssue`, `EvidenceAssessment`, `QualityAssessment`.

```python
from vietnamese_financial_multi_agent.accounting import (
    assess_automated_records,
    assess_evidence_for_task,
    evidence_from_automated_records,
)

# records được run_automated_pdf render/revalidate và bind với PDF trước đó.
direct = assess_automated_records(records)
evidence = evidence_from_automated_records(records)
# Caller chọn operands và khai báo IDs cần thiết, không truyền toàn PDF cho một comparison.
selected = [e for e in evidence if e.canonical_item_id == "b02.gross_profit"]
comparison = assess_evidence_for_task(
    selected, "analytical_qa", required_evidence_ids=expected_ids,
)
```

`expected_ids` do caller cung cấp theo tác vụ; API không hiểu câu hỏi tự nhiên,
không tự biết comparison cần hai kỳ nếu caller không khai báo operands.
Arithmetic adapter M2-05 trả các record chứa `checks`: chuyển từng check bằng
`ArithmeticCheck.model_validate_json(json.dumps(check))` trước khi truyền.
Relationship adapter M2-06 trả `RelationshipCheck` trực tiếp.

`items[].decision` luôn mô tả khả năng truy xuất giá trị riêng lẻ. `decision` cấp
assessment mô tả tác vụ được yêu cầu. `summary_counts` đếm item decisions;
`reason_counts` đếm occurrences, có thể nhiều reasons trên một item.
Giữ nguyên `arithmetic_annotations`/`relationship_annotations` đã truyền, kể cả
unavailable/insufficient; annotations không thay thế extraction.

| Task type | Quyết định tác vụ |
| --- | --- |
| direct_qa | Label hoặc source code, số đọc được, kỳ và nguồn trang; thiếu unit/scale cho raw retrieval có caveat |
| analytical_qa | Tất cả operands yêu cầu có mặt, unit/currency/scale và loại kỳ tương thích; scope khác nhau không được trộn |
| accounting_analysis | Thêm scope và cùng kỳ hoặc có check liên quan xác nhận endpoint; require_check yêu cầu check thực chạy được |
| report_generation | Giữ từng mục usable, partial report có caveat khi mục khác thiếu/conflict |

Không có available item thì assessment insufficient hoặc conflicted nếu có mâu thuẫn.
Một Direct QA batch hoặc report
có cả item conflicted và usable trả usable_with_caveat, còn item conflict giữ conflicted.
Analytical/accounting gặp conflict trong operands trả conflicted. Bốn decisions:
`usable`, `usable_with_caveat`, `insufficient`, `conflicted`.

Caller chịu trách nhiệm chọn đúng item identity và operands cho tác vụ. Conflict tự động
chỉ so các normalized values khác nhau trong cùng document, statement, canonical ID
hoặc source code/label, kỳ/type, scope, currency/unit/scale. Missing value không là zero
hoặc conflict. Không fuzzy matching, không tự hợp nhất các identity khác nhau.

Check mismatch liên quan có caveat, cho phép truy xuất raw values hoặc báo kết quả
đối chiếu mismatch; không tự biến thành vi phạm pháp luật. Check không đủ dữ liệu
không chặn giá trị gốc. Check chỉ thỏa `require_check` nếu có inputs, mọi input xuất hiện
trong evidence được chọn và status passed/failed/consistent/inconsistent.
Không có check phù hợp trả unsupported_rule, giữ items đã có.

## Raw fallback và provenance

Adapter nhận records **đã được `run_automated_pdf` revalidate**, không phải payload tùy ý
hoặc persisted decisions chưa bind ảnh. Dùng links chứa association row/column đã kiểm
tra; chỉ bỏ mapping-only restriction và cho phép thiếu unit. Dùng lại parser Decimal,
context resolver M2-02; không gán canonical ID mới hoặc suy năm từ filename.
Reading uncertain, duplicate/conflicting bindings, statement/code conflicts và lỗi
layout vẫn insufficient. Dấu gạch/null/không parse được vẫn missing_source_data.

Giữ raw label/code/value/header/statement, unit/scale, page SourceAnchor, selectors
context/header/label/code/value, PDF/render/model/request metadata. Bbox không bắt buộc;
selector cell trong payload vẫn là provenance cấp trang, không xác minh glyph/cell.
Không có document/image identity kèm page thì provenance_missing. Input trực tiếp dùng
FinancialNormalizationResult do caller cung cấp; không xác minh nguồn trên đĩa tại API này.

Output là snapshot riêng, không sửa source records, normalization hay accepted status.
`financial_fact_verified` luôn false. Không thay contracts M1/M2-01 hoặc catalog.

## Pilot BBS2025 — 2026-10-28

Replay cache M2-04b retry/page5, retry/page7, live/page8; render PDF 200DPI,
không thêm trang và **0 Gemini calls**. SHA-256 PDF trước/sau:
`6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`.
Hash cả ba cache trước/sau khớp; records trước/sau bằng nhau.

```powershell
python scripts/run_quality_pilot.py data/raw/Financial_Report_pdf/BBS/2025/BBS_2025.pdf --cache-root artifacts/item-mapping/M2-04b --output artifacts/quality/M2-07/review
```

Thư mục output phải chưa tồn tại. Artifact ignored phiên này:
`artifacts/quality/M2-07/review/quality.json`; không đưa raw/normalized/cache/PDF lên Git.

| Metric | Số lượng |
| --- | ---: |
| Raw value slots (row × period column, gồm dấu gạch/thiếu) | 136 |
| Raw numeric items parse được | 121 |
| Numeric items có canonical ID | 28 |
| Numeric items ngoài catalog | 93 |
| Direct QA usable | 20 |
| Direct QA usable_with_caveat | 101 |
| Direct QA insufficient | 15 |
| Direct QA conflicted thực | 0 |
| Tổng Direct QA có thể sử dụng | 121 |
| Analytical/accounting scenarios đầy đủ có thể sử dụng | 3 |

28 accepted extraction giữ nguyên. 93 numeric items ngoài catalog đều dùng được
kèm caveat, chứng minh Direct QA không bị giới hạn ở catalog14 IDs/28 links.
101 caveat items gồm93 ngoài catalog và8 canonical items nhận scope_unconfirmed từ
relationship annotations. Các slot thiếu số không được tăng usability.

Reason counts toàn Direct QA: missing_canonical_mapping108 (93 numeric +15 không có
số đọc được), missing_source_data15, extraction_error8. Tám extraction_error là
uncertain_reading trên slot không có số; không có
numeric item bị chặn bởi lỗi này. Trong15 insufficient: missing_source_data15,
missing_canonical_mapping15, extraction_error8. Các reason chồng lấp, không cộng
thành số item. Missing mapping không phải lý do chặn riêng lẻ.

| Scenario | Expected behavior | Actual decision | Nguồn / lý do |
| --- | --- | --- | --- |
| Doanh thu thuần2025 | Dùng giá trị có nguồn | usable | B02 trang7 mã10:450.474.531.227 VND |
| Lưu chuyển tiền thuần trong năm2025 | Ngoài catalog vẫn dùng được | usable_with_caveat | B03 trang8 mã50:1.208.501.810 VND; missing_canonical_mapping |
| Gross profit comparison | Hai kỳ dùng được | usable_with_caveat | B02 trang7 mã20:2025=32.482.519.668;2024=36.432.410.381 VND; scope_unconfirmed |
| Gross profit arithmetic2025 | Check liên quan đủ | usable_with_caveat | M2-05 passed:450.474.531.227−417.992.011.559=32.482.519.668; scope_unconfirmed |
| B01 ↔ B03 cash | Endpoint được check xác định | usable_with_caveat | Trang5 mã110/trang8 mã70 cùng3.711.595.064 VND; M2-06 consistent; scope_unconfirmed |
| Missing prior-period operand | Giữ phần có thể truy xuất | operation insufficient, item usable | Chỉ chọn gross profit2025; khai báo thiếu kỳ trước, không sửa cache thật |
| Synthetic conflict | Chỉ hai phiên bản item bị conflict | report usable_with_caveat | Bản sao gross profit tăng1 (synthetic), hai items conflicted; doanh thu usable |

Partial scenario cố ý chọn subset của cache; không tuyên bố PDF thiếu kỳ2024.
Synthetic conflict là engineering fixture riêng trong report, không phải mâu thuẫn
trong báo cáo BBS. M2-07 chỉ đánh giá answerability, không tính growth hoặc sinh
câu trả lời tự nhiên. Con số thực đọc từ cache đã bind nguồn; pilot một PDF/ba trang,
không có đánh giá accuracy độc lập mới, không phải verified financial facts.

## Engineering evidence

20 focused tests M2-07, regression114 tests M2-04b/05/06 và normalization contracts;
tổng134 targeted PASS. Ruff lint/format, planning checker và diff check là checks local.
CI giữ nguyên full unit suite Python3.11/3.12, không dùng PDF riêng hoặc gọi Gemini thật.
SHA/CI exact và artifact hash ghi trong [spec](../planning/tasks/M2/M2-07.md) và
[handoff](../planning/handoff.md). Không tạo issue mới vì catalog restriction đã xử lý
trong phạm vi task, không còn blocker engineering. Dừng REVIEW chờ Tech Lead.
