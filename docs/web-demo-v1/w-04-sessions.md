# W-04 — Processing Sessions

Từ trang chi tiết tài liệu có metadata accepted, bấm **Phân tích báo cáo**.
Không cần ticker, project ID hoặc chọn trang. Một worker/queue dùng chung với
preflight; discovery/extraction qua cùng CachedLLMService, Gateway và Free Tier
key pool W-03, đăng ký thêm hai schema M1–M2. Không đổi model hoặc tier.

Discovery kiểm tra mọi trang, dùng Vision khi text layer không đủ; giữ uncertain
để extraction thử đọc, B09 chỉ inventory. Adapter gọi runtime hiện có theo từng
trang được chọn, rồi đánh giá lại quality trên toàn bộ evidence để giữ conflict
đa trang. Không đổi raw values, Decimal strings hoặc kỳ của từng cell theo năm
metadata. Completed chỉ là hoàn tất kỹ thuật, không phải verified financial facts.

POST `/api/documents/{id}/process` nhận `{operation:"extract",metadata_revision:N}`
và header Idempotency-Key UUIDv4. Một tài liệu chỉ có một job active; cùng key và
operation/revision trả attempt cũ, key mới retry terminal. Metadata accepted cần
tên doanh nghiệp và năm hợp lệ, ticker nullable. Status có phase discovery,
extraction, finalizing và số trang thực đã persist; không phần trăm/ETA.

Kết quả nằm trong storage root W-03 tại
`documents/<id>/attempts/<attempt-id>/result.json`, ghi atomic sau mỗi trang.
Snapshot chứa inventory, records/payload M1–M2, quality, evidence DTO, metadata
revision/config/model. Job/status/history vẫn trong document.json W-03.
PDF gốc giữ nguyên. API inventory/evidence đọc snapshot theo attempt_id bắt buộc,
không ghép attempts; evidence hỗ trợ statement B01/B02/B03, offset/limit 1..500.
Giữ mọi provenance refs, bbox=null khi chưa có tọa độ trusted; raw payload riêng
server, không đưa paths/ảnh/credentials vào HTTP.

Retry thủ công cùng metadata revision/config/model dùng lại kết quả thành công
trong 24 giờ; discovery kiểm PDF hash/image hash/model, extraction revalidate
image/page binding qua runtime M1–M2. Trang lỗi hoặc uncertain được thử lại theo
caps. Không sửa snapshot attempt cũ. Không tự gửi lại sau restart: queued và
processing thành interrupted, vẫn đọc được kết quả cũ. Trang đang gọi lúc crash
có thể chưa được lưu và có thể tốn request khi retry thủ công.

Giữ upload/pages, RPM/TPM/RPD/key rotation và request cap W-03. Extraction dùng
chung `WEB_PREFLIGHT_REQUEST_LIMIT` (mặc định 50) cho cả discovery và extraction;
không tạo quota framework khác. Khi cap/provider ngăn hoàn tất, session giữ
snapshot và trả partial nếu còn numeric evidence usable, failed khi chưa có;
notes-only inventory là partial. Với PDF dài, người dùng có thể cần chờ hạn mức
rồi retry thủ công. Không tự gọi lại để đạt đủ coverage.

Engineering tests ở `test_extraction_sessions.py` dùng raster PDF synthetic và
Gateway mock, không chứng minh accuracy tài chính. Live BBS_2025 và giới hạn
nghiên cứu được ghi ngắn tại [spec/evidence W-04](../../planning/tasks/W/W-04.md).
UI chỉ hiển thị tiến độ/summary; bảng evidence/viewer thuộc task sau.
