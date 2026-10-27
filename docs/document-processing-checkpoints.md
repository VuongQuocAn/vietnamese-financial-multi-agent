# Document Processing Checkpoints — M1-10

Checkpoint nội bộ giúp resume kết quả đã được caller xác minh, không xử lý lại unit
khi input/config/version còn khớp. Không thay DU v1 hoặc raw contracts.

## Lưu trữ và identity

`document_processing.checkpoints.CheckpointStore` nhận output root và `DataConfig`.
Root tương đối tính theo CWD tại khởi tạo; nên truyền `project_root / "checkpoints"`.
Root resolved phải tách khỏi configured data roots, data/raw, data/processed,
data/recovered_crops (kể cả ancestor/descendant). Không mkdir khi lookup.
`checkpoints/` đã được .gitignore; root tùy biến cần được ignore riêng.
Caller chọn root chỉ dành cho checkpoint, không chứa source/crops khác ngoài cấu hình.

`ProcessingUnit.source_ref` bắt buộc là locator bind đúng document/artifact/run do caller
xác minh; không tự suy từ symbol/year hoặc đường dẫn. Page-level bổ sung `RawPageIdentity`
đầy đủ gồm source_ref; document-level bỏ page. Không suy đoán OCR run identity.
Identity lưu nguyên văn Unicode/case/whitespace. Giữ cách cung cấp omitted/null nhất quán
giữa các lần gọi; không normalize identity hoặc provenance.

Một file `<SHA256(unit+stage)>.json` chứa format version, request (unit/stage/input/config
fingerprints/processing version), verified bool, result JSON, result digest và artifact digest.
Artifact digest phủ cả metadata lẫn result để phát hiện metadata bị sửa vô tình.
Đây là checksum, không chữ ký chống attacker trên filesystem không tin cậy.
Mỗi unit/stage chỉ giữ revision gần nhất; save mới thay slot cũ, không giữ lịch sử.

## API và tích hợp M1-11

```python
from vietnamese_financial_multi_agent.document_processing.checkpoints import (
    CheckpointRequest,
    CheckpointStore,
    ProcessingUnit,
    fingerprint_json,
)

# config là DataConfig đã load; source_ref/page_identity do application xác minh.
store = CheckpointStore(config.project_root / "checkpoints", data_config=config)
request = CheckpointRequest(
    unit=ProcessingUnit(source_ref=document_source_ref, page=page_identity),
    stage="classification",
    input_fingerprint=fingerprint_json(input_snapshot),
    config_fingerprint=fingerprint_json(effective_config),
    processing_version="classification-v1",
)
lookup = store.lookup(request)
if lookup.status == "HIT":
    result = lookup.result  # Có thể là null/false/empty JSON; kiểm tra status.
else:
    result = process_unit(input_snapshot)
    validate_completed_result(result)  # Caller áp dụng criteria đã được duyệt.
    store.save_verified(request, result, verified=True)
```

Các tên application trong ví dụ là điểm tích hợp, chưa triển khai classification.
Với DU v1 dùng `parse_document_understanding`, `validate_understanding_quality` và
`export_result()` hiện hữu trước save; khi HIT parse lại nếu cần typed model.
Quality issues phải được caller giải quyết theo policy; structural JSON hợp lệ tự nó
không đủ để xác nhận semantic validation. `verified=True` là attestation của caller,
không phải kết luận OCR/tài chính chính xác hoặc Verified Claim Ledger.

## Fingerprint và invalidation

`fingerprint_json` dùng UTF-8, sort keys, compact JSON, SHA-256; không hash(), mtime/size/path.
Chấp nhận dict keys string, list, string/int/finite float/bool/null; từ chối tuple,
non-string keys, NaN/Infinity và objects khác. Không normalize Unicode hoặc số dạng text.
Omitted khác explicit null; order arrays ảnh hưởng digest, order object keys không ảnh hưởng.

Caller hash snapshot chứa **mọi nội dung ảnh hưởng kết quả**, gồm raw export, provenance,
manifest/revision và image/crop content digests nếu stage sử dụng chúng. Hash chỉ path,
filename hoặc raw JSON có image path không chứng minh image content bất biến. Không dùng
metadata fingerprint nội bộ của OCR loader làm content fingerprint. Store không scan dataset.
Config phải chứa effective options/model/prompt/schema revisions khi liên quan, không secrets;
processing_version thay khi implementation đổi. Thiếu fingerprint/source_ref gây
`ValidationError` trước I/O; store không tự HIT khi thiếu evidence.

| Status | Điều kiện |
| --- | --- |
| MISS | Không có published artifact cho unit/stage |
| HIT | Đủ metadata/verified/integrity và request khớp hoàn toàn; trả result mới decode |
| STALE | Artifact hợp lệ nhưng request revision khác; result không trả |
| INVALID | JSON/metadata/format/verified/digest hỏng hoặc thiếu; result không trả |

Stage/unit khác trả MISS ở slot riêng. Format không tương thích trả INVALID. Lookup
không sửa/xóa artifact stale/invalid. `lookup` cũng là verified load, không cần API thứ hai.
I/O errors khác FileNotFoundError được raise, không che lỗi permission thành MISS.
Save sai JSON/attestation trả ValueError, request sai trả ValidationError, I/O trả OSError.
Exceptions không cố ý đưa payload/provenance vào thông báo; không log source hoặc secrets.

## Atomic write, resume và giới hạn

Serialize toàn bộ trước ghi; tạo temp cùng directory, write/flush/fsync/close rồi
`os.replace`. Temp được dọn khi failure có thể xử lý; crash có thể để orphan `.tmp`,
lookup chỉ đọc tên `.json` xác định nên bỏ qua. Không có published partial success.
Save thất bại trước replace giữ checkpoint cũ nguyên trạng hoặc vẫn MISS. Restart
Python dùng root/request cũ sẽ đọc và xác minh lại artifact, không dựa RAM.

Single writer/process trên trusted local filesystem; không hỗ trợ concurrent writers,
distributed locks/scheduler, filesystem attacker/TOCTOU hoặc durable directory fsync trên
mọi nền tảng/power loss. Output root không được rebind trong lúc chạy. Không size cap,
eviction hoặc history; caller giới hạn kích thước JSON và dọn checkpoint khi thích hợp.
Không pickle, sửa OCR/bbox/số liệu, LLM calls, financial validation hoặc evaluation.
