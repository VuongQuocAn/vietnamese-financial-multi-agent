# Document Understanding thống nhất — M1-16

`document_processing.understanding_pipeline.run_document_understanding(source, options)`
trả `contracts.unified_document.UnifiedDocument`, version `unified_document_v1`.
Đây là export trung gian cho consumer M2; chưa có quy tắc normalization kế toán.
Không thay `raw_ocr_v1` hoặc `document_understanding_v1` đã DONE.

Existing OCR nhận `PathMappingRequest` category `ocr_page_json` và
`UnderstandingOptions(data_config=config)`, dùng nguyên loader/resolver read-only.
Không cần PDF gốc; mapping/reference, raw metadata/provenance và hash đúng bytes
loader đã parse được giữ trong output. Identity check của loader được giữ riêng.
Raw text/cells/lines/bbox/row/col còn nguyên trong `source_component`.
Raw row/col chưa được xác minh layout nên chưa đưa vào fields row/column được chấp nhận;
không chạy reconstruction/correction mặc định. Classification dùng gate M1-11
code/title ở các vùng độc lập không chồng nhau, không blocking quality issue.

PDF/PNG nhận `Path`, `symbol`, `year`, `pages` (số trang gốc, one-based), `dpi`.
Tái sử dụng ingestion M1-15: PDF render từng trang PNG, không gửi PDF vào request.
Mặc định bắt buộc `persisted_results={page_number: record_M1_15}`; thiếu một trang
thì fail closed trước API. Record đã có, kể cả provider failure, không được gọi lại.
Live chỉ khi `allow_live_ocr=True` cùng `service` Gateway và `credential_ref` được
inject tường minh. Không khởi tạo provider/client hoặc đọc credentials trong pipeline.
M1-16 không chạy live. Recovery chỉ đề xuất, chưa có executor/opt-in recovery trong MVP.

Replay không cần PDF gốc có thể dùng manifest và các rendered PNG đã lưu:

```python
import json
from pathlib import Path
from vietnamese_financial_multi_agent.document_processing.understanding_pipeline import (
    PersistedOCRInput,
    UnderstandingOptions,
    run_document_understanding,
)

base = Path("artifacts/gemini-ingestion/M1-15/pdf")
pages = (5, 7, 8)
result = run_document_understanding(
    PersistedOCRInput(json.loads((base / "manifest.json").read_text("utf-8")), base),
    UnderstandingOptions(
        symbol="BBS",
        year="2025",
        pages=pages,
        persisted_results={
            n: json.loads((base / f"page-{n}.json").read_text("utf-8")) for n in pages
        },
    ),
)
export = result.export_result()
```

Replay kiểm tra image hash/dimensions và exact provenance/identity giữa manifest,
PNG, record; chạy lại component validator từ response payload gốc. Status lưu sẵn
không là bằng chứng. PDF hash được bảo toàn theo manifest, chưa rehash PDF trong
chế độ này; `source_references.integrity_scope` ghi rõ giới hạn. Replay không API.

Mỗi page có identity/source type/hash/references, text regions, tables/cells,
classification, issues, processing history, recovery decisions. Các flags độc lập:

| Field | Phạm vi chứng minh |
| --- | --- |
| `schema_valid` | Input OCR đúng raw schema hoặc structured OCR schema; không là quality |
| `quality.text_accepted` | Raw text không rỗng hoặc component text observed qua M1-13b |
| `quality.layout_accepted` | Cell layout qua component validation; raw chưa verified giữ unresolved |
| `quality.geometry_verified` | Chỉ tọa độ xác minh với ảnh; adapter MVP luôn false |
| `quality.downstream_usable`, `usable_for` | Chỉ `text_evidence`, không là financial fact đã chuẩn hóa |

`status` ở region là text status; `layout_status`, `geometry_status` riêng.
Table status cần text/layout đạt; `layout_accepted` riêng không đòi text accepted.
Ô unknown/inferred vẫn giữ text và candidate layout/bbox; không bỏ bảng lỗi.
`bbox` chỉ cho geometry verified, hiện null. Bbox raw/model nằm ở `source_component`
với trạng thái unresolved; không swap/rescale hoặc tạo bbox.
`source_pointer` là selector tương đối payload structured OCR hoặc raw OCR JSON,
không phải raw ID. Chỉ nhánh existing có `raw_*_id` do nguồn cung cấp; native giữ
page-level provenance, không cell-level dù có selector. Cell IDs trùng vẫn còn
trong nguồn và issues, consumer không được coi là khóa duy nhất.

Native classification unresolved khi không có independent region anchors đạt
gate M1-11; không suy nhãn chỉ từ một heading hoặc đổi điều kiện để accept.
Router chỉ đề xuất table reconstruction khi layout unresolved và human review khi
text/classification thiếu evidence. Mọi decision có reason, selector, `executed=false`.
Chưa có executor cho OCR correction/vision crop; không đủ ảnh/evidence thì unresolved.

Consumer M2 parse cùng `UnifiedDocument.model_validate_json(...)`, duyệt
`text_regions` và `tables[].cells`, đọc quality/purpose trước sử dụng. Không cần
biết nhánh đầu vào. Consumer test kiểm tra round-trip và text evidence cho cả hai
nhánh; không coi schema test là đánh giá accuracy tài chính.
