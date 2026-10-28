# Statement type recognition — M2-03

Resolver deterministic trong accounting, nhận evidence nội dung từng trang.
Không suy loại từ filename/metadata hoặc từ khóa tài chính chung. Không gọi API,
sửa contracts M1 hoặc financial_normalization_v1. Schema-valid không chứng minh
financial fact đã verified.

```python
from vietnamese_financial_multi_agent.accounting import (
    evidence_from_unified_page,
    recognize_document_statements,
    resolve_statement_type,
)

# page: UnifiedPage M1; pages: các trang cùng tài liệu do caller chọn.
result = resolve_statement_type(evidence_from_unified_page(page))
inventory = recognize_document_statements(pages)
```

`resolve_statement_type(Iterable[ContextEvidence]) -> StatementTypeResolution`
trả statement_type B01/B02/B03/B09 hoặc null, status, candidates, evidence, issues
và financial_fact_verified=false. Candidate giữ value: FinancialContext,
signal title/form_code/mention, evidence gốc, status/issues. Candidate resolved
chỉ nói tín hiệu riêng đủ điều kiện; xung đột vẫn làm kết quả cuối uncertain.
Giữ toàn bộ evidence, kể cả text không match.

Tái sử dụng ContextEvidence và evidence_from_unified_page() M2-02. M1 text cần
accepted/text_accepted/downstream_usable/text_evidence. Giữ raw text, selector,
anchors và trạng thái M1; không nâng geometry chưa verified hoặc tạo IDs/bbox.
Caller truyền evidence trực tiếp chịu trách nhiệm khai báo đúng M1 status/provenance.

| Loại | Title hỗ trợ |
| --- | --- |
| B01 | Bảng cân đối kế toán; Báo cáo tình hình tài chính |
| B02 | Báo cáo kết quả hoạt động kinh doanh |
| B03 | Báo cáo lưu chuyển tiền tệ |
| B09 | Thuyết minh báo cáo tài chính; Bản thuyết minh báo cáo tài chính |

Match Unicode NFC/casefold/whitespace từng dòng, không sửa raw text. Title cần
nguyên dòng, có thể thêm riêng/hợp nhất và `(Tiếp theo)`. Mã
`Mẫu [số] B01/B02/B03/B09 [- DN]` cần title cùng loại trong cùng trang.
Form đơn lẻ, bare code hoặc tên báo cáo trong đoạn văn/danh sách/trích dẫn chỉ tạo
candidate yếu → uncertain. Không match → unresolved. Aliases B01/B09 nằm trong
phạm vi yêu cầu; pilot thực chỉ xác nhận các title xuất hiện dưới đây.

Title/form đủ điều kiện được ưu tiên hơn mention; mention vẫn giữ status/issues
trong candidates. Title B09 kèm câu `Chuẩn mực số 24 - Báo cáo lưu chuyển tiền tệ.`
→ B09 resolved, candidate mention B03 uncertain. Hai title khác loại, form khác
title, title/form thiếu provenance hoặc text M1 chưa accepted → uncertain/null.
Không chọn candidate đầu tiên; duplicate support cùng loại không gây conflict.

Phạm vi resolver là một trang. Evidence nhiều page identities bị chặn bằng
mixed_page_scope. `recognize_document_statements(Iterable[UnifiedPage])` trả
DocumentStatementTypes với kết quả độc lập trong pages theo thứ tự input,
statement_types là inventory các loại đã resolved, completeness_verified=false.
Không có nhãn duy nhất cho toàn PDF; inventory nhiều loại là hợp lệ. Không truyền
nhãn trang đầu sang trang sau. Trang tiếp nối chỉ resolved khi có title riêng đủ
căn cứ, như BBS trang6. Không kiểm chứng tính đầy đủ hoặc ranh giới các báo cáo.

Giới hạn: không segmentation/layout/reading-order, không ghép heading chia nhiều
regions, không hiểu mọi trích dẫn đứng riêng một dòng hoặc heading trong cell.
Caller cần khoanh đúng evidence; regex không chứng minh vai trò hình học của title.
Định dạng không hỗ trợ giữ uncertain/unresolved.

## Evidence — 2026-10-28

M2-02 DONE tại baseline sạch e1c84783fea5487c1f2b1e8ae77c1ccbfcaf65e1 đã push trước
implementation. Local .[dev]: **11 focused mới +18 regression M2-01/02 =29 PASS**.
Bao phủ bốn loại/aliases, form đúng/sai, mention/list/quotes, missing/conflicts,
raw/provenance/status M1 và round-trip, duplicate/mixed pages, continuation và
inventory. Ruff files liên quan, planning82 và diff check PASS. Không full local
suite, benchmark hoặc Gemini.

Pilot read-only **8 trang khác nhau**. Expected ghi từ đọc text nguồn trước khi
chạy resolver; không lấy prediction làm ground truth. Unified M1-16 cung cấp
BBS5/7/8, không đếm lại BBS5 native. Năm raw pages còn lại qua loader/pipeline M1
có sẵn; không OCR lại hoặc gọi API. Adapter đưa toàn bộ text regions và cells
vào resolver, giữ M1 quality. Đánh giá chỉ theo OCR text, chưa PDF/ảnh/second reviewer.

| Trang / nguồn | Expected từ text OCR | Kết quả | Source pointer chính |
| --- | --- | --- | --- |
| BBS2025/5, existing M1-16 | B01 title/form | resolved B01 đúng | /elements/1; /elements/3 |
| BBS2025/6, raw qua M1 | B01 title riêng có (Tiếp theo) | resolved B01 đúng | /elements/1; /elements/3 |
| BBS2025/7, native M1-16 | B02 title/form | resolved B02 đúng | /text_elements/1; /text_elements/3 |
| BBS2025/8, native M1-16 | B03 title/form | resolved B03 đúng | /text_elements/1; /text_elements/4 |
| BBS2025/9, raw qua M1 | B09 title/form | resolved B09 đúng | /elements/2; /elements/0 |
| BBS2025/10, raw qua M1 | B09 title; B03 narrative | resolved B09 đúng | /elements/1; /elements/2; mention /elements/17 |
| BCC2025/1, raw qua M1 | Công văn liệt kê nhiều báo cáo | uncertain phù hợp | /elements/17; /elements/19; /elements/20 |
| BED2025/1, raw qua M1 | Bìa chung, thiếu title bốn loại | unresolved phù hợp | /elements/6 |

Tổng: **6 resolved đúng /0 resolved sai /1 uncertain /1 unresolved**. Đủ mẫu thực
B01/B02/B03/B09, không loại nào thiếu kiểm chứng thực trong pilot. Chưa pilot thực
aliases Báo cáo tình hình tài chính/Bản thuyết minh, title có riêng/hợp nhất,
missing provenance hoặc continuation thiếu title; các dạng này chỉ synthetic.
Không suy độ chính xác toàn dataset; abstention phù hợp không là financial accuracy.

Receipt ignored `artifacts/statement-resolution/M2-03/pilot.json` giữ full raw
text/candidates/anchors, source refs, expected/actual/reason và SHA256. Pilot script
và inputs.json cùng thư mục giữ allowlist hữu hạn để reproduce. Hash **7 file
đầu vào không đổi**: unified M1-16 existing.json/native.json; raw OCR BBS2025
page6/9/10, BCC2025/page1 và BED2025/page1 dưới data/processed/Financial_Report_OCR.
Không commit artifacts/dataset, không sửa nguồn.

CI exact implementation SHA: chờ xác minh sau commit/push. Task REVIEW chờ Tech Lead.
