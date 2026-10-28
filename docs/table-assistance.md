# Gemini-Assisted Table Reconstruction — M1-12a

`document_processing.table_assistance.TableReconstructor` nhận CachedLLMService
đã compose với `table_schema_registry()` và Shared Gateway/Gemini Adapter/quota guard.
Consumer tái sử dụng `reconstruct_table`; deterministic resolved trả ngay, API0.

```python
from vietnamese_financial_multi_agent.document_processing.table_assistance import (
    TableReconstructor,
)

engine = TableReconstructor(service, checkpoints=store)
result = engine.reconstruct(
    loaded,
    table_id,
    source_ref=loaded.mapping_result.reference.source_ref,
    credential_ref=credential_ref,
    reservation=reservation,
    cache_allowed=True,
    checkpoint_allowed=True,
)
table = result.table  # UnderstoodTable, DU v1
```

Loader phải identity_checked, mapping resolved và có page anchor khớp source_ref.
Internal `GridPrediction` chỉ có disposition/dimensions và source IDs/row/col/spans/
placeholder IDs; không có field text/value. Local JSON Schema + strict Pydantic validation;
mọi raw ID xuất hiện đúng một lần. Output ID/text/bbox lấy từ raw, không từ model.
Text/whitespace/số liệu/provenance không chỉnh sửa; bbox nằm trong observed_bbox anchors.

Geometry policy `layout-evidence-v1`:

- Duplicate/empty IDs, invalid bbox, bbox vượt trang, invalid table identity, unreviewed
  raw structural extras vẫn blocking; không gọi Gemini khi source preflight thất bại.
- Logical grid phải có positive spans, zero-based positions, complete coverage,
  không collision/out-of-bounds. Không sinh cell để điền gaps.
- Bbox text vượt nhẹ bbox table và edge overlap không tự là lỗi grid. Giữ aggregate
  issues với prefix `reviewed_`; vẫn kiểm tra thứ tự tâm X khi logical row ranges
  giao nhau, tâm Y khi column ranges giao nhau và dải Y cùng hàng phải giao nhau.
  Bbox content trùng hoàn toàn giữa hai ô vẫn unresolved.
- Ô rỗng không lines/line_count và bbox đúng bằng toàn bảng có geometry không thông
  tin: chỉ giữ observed empty tại raw position, không tự coi là merged placeholder.
- Merge cần bbox owner phủ tâm các ô độc lập trong **mọi** covered row/column band.
  Chỉ lời khẳng định của Gemini hoặc bbox rộng chưa đủ. Placeholder chỉ được gộp
  khi text đúng rỗng, không lines, raw position nằm trong span; anchors vẫn giữ đủ.

DU source validation chạy sau evidence gate; chỉ `empty_text` là quality warning
được phép. Fail thì giữ deterministic candidate unresolved và issue code, prediction
riêng để audit; không đánh verified. `resolved` là acceptance cấu trúc theo policy,
không chứng nhận semantics tài chính/accuracy hoặc độc lập xác minh OCR run identity.

Input fingerprint phủ toàn page/provenance/mapping/identity_checked; config fingerprint
phủ model/config, prompt text/revision, schema/ref và policy/processing version.
Checkpoint stage riêng từng table; HIT phải revalidate. Chỉ accepted prediction lưu
save_verified; schema-valid cache prediction (kể cả unresolved) luôn qua gate hiện tại.
Thay code gate phải bump policy version. Cache RAM scope một project, TTL pilot 3600s.

Pilot dùng đúng frozen M1-12 report và 8 tables/4 pages, không đọc lại corpus.
Text/layout mode, không ảnh: Gateway v1 hiện text-only; không claim crop/image binding.
Full raw table cells/lines/metadata + OCR provenance được gửi, không truncate; bỏ crop
locator vì không phải evidence nội dung. Model cố định gemini-3.5-flash-lite.

```powershell
python scripts/run_table_assistance_pilot.py
python scripts/run_table_assistance_pilot.py --live --key-index 0
python scripts/run_table_assistance_pilot.py --resume
```

Cần hai biến dataset của loader. Live chọn một key index/project theo owner-attested
policy đã có; không in key. SDK retries1 attempt, max15 attempts tính cả failures,
RPM5, TPM250000, per-request input bound100000/output cap16384; **không tổng input cap**.
Giới hạn per-request từ chối nguyên request, không cắt evidence. MeteredModels cũ thêm
optional caps để dùng chung, defaults classification giữ nguyên.
Exclusive `live.started.json` chặn restart reset budget; không xóa marker để rerun.
Offline resume không đọc credentials/khởi tạo client, chỉ kiểm tra accepted checkpoints.
Không reset hoặc tự retry khi provider/quota/model/schema lỗi.

Artifacts riêng ignored `artifacts/table-reconstruction/M1-12a/`; M1-12 report read-only.
Billing/project ID/quota remaining chưa independently verified, guard money status
NOT_CONFIGURED; không suy API thực tế cost0 từ free-only attestation.
Xem [spec](../planning/tasks/M1/M1-12a.md) và [evidence](reviews/M1-12a-evidence.md).
