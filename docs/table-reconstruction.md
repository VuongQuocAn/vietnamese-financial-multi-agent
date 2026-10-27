# Table Structure Reconstruction — M1-12

API thuần bộ nhớ trong `document_processing.table_reconstruction`:

```python
from vietnamese_financial_multi_agent.document_processing.ocr_loader import load_ocr_page
from vietnamese_financial_multi_agent.document_processing.table_reconstruction import (
    reconstruct_table,
)

loaded = load_ocr_page(request, config)
table = reconstruct_table(
    loaded.page,
    table_id,
    source_ref=request.reference.source_ref,
)
```

Caller cung cấp request/mapping/table ID đã chọn, bind source_ref vào đúng artifact;
module không tự khẳng định OCR run identity. Output là `UnderstoodTable` DU v1,
có thể đặt vào `DocumentUnderstandingResult.tables` cùng classification hiện có.
Không thay classification/contracts. Không có pipeline orchestration tự động.

Row/col zero-based, cells sắp theo row/col/ID; ID/text/whitespace/số liệu giữ nguyên.
Bbox nằm trong `anchors[].observed_bbox`, dùng pixel ảnh gốc. Mọi raw cell giữ
link ID trong đúng table/page; không tìm theo vị trí hoặc chọn match đầu khi ID mơ hồ.
Object output và anchors tách khỏi raw, không sửa inputs.

Default extent là max row/col + 1. Grid đầy đủ, không collision và hình học nhất
quán thì chốt spans 1×1. `shape=(rows, columns)` là kích thước do caller đã review,
hữu ích để phát hiện trailing missing cells không thể thấy từ metadata hiện hữu.
Không có shape/ground truth thì không chứng minh thiếu hàng/cột ngoài extent quan sát.
Không tạo empty cells cho gaps. Text rỗng quan sát được giữ thành cell và issue
`observed_empty_cell`; khác `missing_grid_positions`.

Ô gộp cần `spans=(SpanEvidence(...), ...)`: caller cung cấp exact `SourceAnchor`
(page gồm source_ref, element_id/table_id/cell_id, observed_bbox, status resolved),
rowspan/colspan nguyên dương và optional `placeholder_ids` đã chú giải. Đây là
runtime input đã review, không phải Gemini prediction hoặc schema raw mới.
Nếu merge vượt extent raw, caller phải truyền shape đủ lớn đã review.

Placeholder chỉ hợp lệ khi ID duy nhất, không phải span owner khác, text đúng `""`,
không lines/line_count, vị trí khác owner và nằm trong span, bbox nằm trong owner.
Placeholder không thành ô dữ liệu riêng; anchor/bbox của nó nằm trên merged cell.
Không có annotation: giữ raw record làm candidate, không tự đoán placeholder từ
bbox trùng hoặc text rỗng. Không suy colspan từ bbox rộng. Extra raw keys
rowspan/colspan/is_placeholder/merged_with hiện trả `unreviewed_structure_metadata`;
semantics producer chưa được duyệt, chưa tự diễn giải.

Issues blocking gồm source/ID không hợp lệ, duplicate positions, `grid_collision`,
`invalid_span`, `span_out_of_bounds`, `invalid_placeholder`, `span_source_mismatch`,
`missing_grid_positions`, bbox invalid/out-of-bounds và `metadata_bbox_conflict`.
Geometry dùng exact ordering của các khoảng logical rời nhau, không tolerance hoặc
clustering: phù hợp gate bảo thủ; grid cong/lệch/không đều có thể unresolved.
So sánh theo cặp O(n²), không materialize grid theo max coordinate.

Có issue blocking thì cả table/cells/anchors unresolved và spans output null.
Source records vẫn được giữ; missing/ambiguous table reference trả table unresolved
không chọn nguồn tùy tiện. `resolved` chỉ là nhất quán cấu trúc theo checks hiện có,
không phải verified financial data. DU validator vẫn có thể báo `empty_text` cho
empty cell hợp lệ; issue đó không tự chứng minh cấu trúc sai.

Không persistence/checkpoint vì pure core nhỏ và chưa tích hợp stage runner; không
có cache hoặc checkpoint verified cho kết quả unresolved. Gemini-assisted là phần
deferred, cần task được giao tiếp theo và evidence-validation protocol; khi làm phải
qua Gateway/Gemini Adapter hiện có với `gemini-3.5-flash-lite`. M1-12 không gọi API.

Validation bounded từ frozen M1-04b, tối đa bốn manifest indices:

```powershell
python scripts/validate_table_reconstruction.py --page-indices 0 2 4 5
```

Cần cấu hình hai biến môi trường dataset như loader; không đọc credential/.env.
Script kiểm tra frozen manifest/bindings/evidence và selected JSON snapshots trước/sau,
gọi loader với identity đầy đủ, đối chiếu DU anchors và fingerprint raw trong RAM.
Kết quả write-once ở ignored `artifacts/table-reconstruction/M1-12/validation.json`;
không scan corpus hoặc đọc crops/ảnh. Không công bố raw locators/content/hashes.
Xem [evidence](reviews/M1-12-evidence.md) và [spec](../planning/tasks/M1/M1-12.md).
