# Financial item mapping — M2-04

API public qua `vietnamese_financial_multi_agent.accounting`:

```python
from vietnamese_financial_multi_agent.accounting import map_financial_items

results = map_financial_items(page)  # UnifiedPage M1; từng trang độc lập.
```

`map_item_label(ContextEvidence, statement_type)` cho caller đã khoanh đúng loại
báo cáo. `map_financial_items(UnifiedPage)` dùng resolver M2-03 và adapter M2-02;
trả list `ItemMapping` cho cells chữ có khả năng là nhãn. Không nhận diện đầy đủ
mọi hàng, không nối nhãn bị tách dòng/cells hoặc kế thừa loại sang trang khác.

Mỗi output giữ raw_item_label, canonical_item_id nullable, statement_type,
statement_resolution (ở page API), status, candidates (rule_id/alias_id và
catalog_evidence), evidence gốc và issues. `source_item_code` cùng
`source_code_evidence` chỉ có khi code header/row/cell đủ accepted. Không tự điền
mã nguồn từ catalog. Thiếu bằng chứng → uncertain/unresolved; xung đột mã với nhãn
→ uncertain và không link số. Mã không dùng một mình để suy chỉ tiêu hoặc ép chọn
ambiguous. Không đổi M1/schema financial_normalization_v1 hoặc quality status.

`ITEM_CATALOG` gồm **14 internal canonical IDs**, quy ước hệ thống theo các dòng
đã đối chiếu trực tiếp ảnh BBS2025 trang5/7/8; đây không phải taxonomy/mã kế toán
chính thức. Bảng sau ghi **mã in trên ảnh**, không phải source code tự gán vào output.

| Internal IDs (tiền tố theo báo cáo) | Mã in trên mẫu | Nguồn |
| --- | --- | --- |
| b01.cash_equivalents, short_term_receivables | 110, 130 | BBS2025/5 |
| b01.inventory_total, inventory_gross, total_assets | 140, 141, 270 | BBS2025/5 |
| b02.net_revenue, cost_of_sales, gross_profit | 10, 11, 20 | BBS2025/7 |
| b02.profit_before_tax, profit_after_tax | 50, 60 | BBS2025/7 |
| b03.operating_cash_flow, investing_cash_flow, financing_cash_flow | 20, 30, 40 | BBS2025/8 |
| b03.closing_cash | 70 | BBS2025/8 |

Exact match sau NFC/casefold/whitespace; giữ nguyên dấu và raw text. Aliases trong
module liệt kê toàn bộ, có nhãn bỏ ordinal như quy ước nội bộ cùng nghĩa. Không
strip ordinal chung hoặc fuzzy match. `III. Hàng tồn kho` và `1. Hàng tồn kho`
khác ID; bare `Hàng tồn kho` giữ hai candidates → uncertain. Các tên ngắn hơn chưa
xác nhận như `Doanh thu`, `Lợi nhuận trước thuế`, `Tiền cuối kỳ` không tự match.
B09 chưa có mục được xác nhận trong mẫu: unresolved, không map narrative.

`value_link_status/issues` và `value_links` tách khỏi label status. Chỉ liên kết
khi bảng status accepted/layout_accepted, mọi cell có row/column không âm, không
trùng và layout accepted/quality.layout_accepted. MVP dùng label column0/header
row0; đây là phạm vi hỗ trợ có kiểm tra, không tái dựng bảng. Duplicate source
pointer chặn binding. Không dùng bbox hoặc vị trí trong list để nối nhãn–số.

Từng header kỳ phải được resolver M2-02 giải quyết độc lập; giữ tất cả cột kỳ hỗ
trợ, không chọn cột đầu làm hiện tại. Không hiểu header sẽ không tạo link cho cột
đó. Unit/scale phải resolved từ evidence trang (xung đột thì abstain); thiếu hoặc
text cell số chưa accepted thì không link. Liên kết trả FinancialNormalizationResult
với context của cột, raw_value, nguồn label/value/header/unit/code; không nhân scale,
parse số hoặc diễn giải dấu `_` thành zero. `normalized_value=null`, value.status
unresolved (`numeric_normalization_deferred`) và financial_fact_verified=false
luôn giữ nguyên. Link resolved chỉ xác nhận liên kết cấu trúc raw cells.

## Evidence — 2026-10-28

M2-03 DONE; baseline sạch local/origin `34829b60daaa3b004e838e8568f25d54c2392ed5`.
Local .[dev]: **12 focused +29 regression M2-01/02/03 =41 PASS**;
Ruff modified Python, planning82 và diff check PASS. Positive structural linking
hai kỳ, missing layout/unit/period, code conflict, duplicate positions/pointers,
raw/provenance/roundtrip, ambiguous/unknown/cross-statement được kiểm tra synthetic.
Không full local suite, OCR lại, Gemini hoặc benchmark.

Pilot read-only chọn trước **3 trang, 20 nhãn**, từ M1-16 existing page5 và native
page7/8, không đếm lại native page5. Expected ID/mã in trên nguồn được ghi độc lập
trước mapper, từ đọc OCR và đối chiếu trực tiếp PNG local BBS2025 trang5/7/8.
Một reviewer; không second review. Hai mã tồn kho 140/141 đã được phân biệt trên ảnh.

| Trang | Labels xét | Đúng | Sai | Uncertain | Unresolved | Numeric slots accepted/rejected/chưa xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| B01 trang5 | 7 | 5 | 0 | 0 | 2 | 0/10/4 |
| B02 trang7 | 7 | 5 | 0 | 0 | 2 | 0/10/4 |
| B03 trang8 | 6 | 4 | 0 | 0 | 2 | 0/8/4 |
| Tổng | 20 | 14 | 0 | 0 | 6 | 0/28/12 |

6 unresolved là nhãn ngoài catalog: tài sản ngắn hạn, tiền, doanh thu bán hàng,
doanh thu tài chính, lưu chuyển tiền thuần trong năm, tiền đầu năm. Không tính
abstention là mapping đúng. Mỗi nhãn có hai ô giá trị trên ảnh: 28 slots của 14
nhãn mapped bị từ chối vì bảng M1 status unresolved (B02 có layout_accepted nhưng
status vẫn unresolved). 12 slots còn lại chưa xét vì label unsupported.
Không dùng OCR adjacency để xác nhận mã/số; source_item_code trong pilot vẫn null.
Tất cả numerical values/period links của pilot vẫn unresolved, **0 accepted**.
Chưa có bằng chứng positive numeric linking trên dữ liệu thực hoặc accuracy toàn
dataset; schema PASS không thay thế kiểm chứng tài chính.

Artifacts local ignored: `artifacts/item-mapping/M2-04/{pilot.py,expected.json,pilot.json}`.
Receipt giữ expected IDs/printed codes, output đầy đủ/provenance, SHA256;
hash **5 nguồn không đổi** (2 unified exports và 3 PNG). Chỉ aggregate docs vào Git,
không OCR/dataset/ảnh hoặc đường dẫn cá nhân. Không sửa dữ liệu nguồn.

CI exact implementation SHA sẽ được ghi sau commit/push. Task REVIEW chờ Tech Lead.
