# M1-13a — Vision-Grounded OCR Correction & Structured OCR Pilot

Ngày 28/10/2026 (Asia/Bangkok). Trạng thái REVIEW; chờ Tech Lead, không M1-14.
Baseline `10b626f`; một implementation commit/push, CI xác minh sau push.

Usage: `python scripts/run_ocr_correction_pilot.py --vision --live --key-index 0`.
Bỏ `--live` để dry-run API0. Cấu hình hai input roots theo `.env.example`.
Live marker write-exclusive chặn chạy lại scope; không retry/rotation/cache probes.
Giữ default text-only M1-13 cho compatibility; `--vision` bắt buộc verified PNG,
không có fallback. Kết quả task này dùng `--vision`, không phải text-only.

`load_verified_image` kiểm tra loaded identity/anchor, approved image binding,
resolver read policy, frozen SHA-256 và dimensions khớp OCR. Bytes PNG gốc được gửi
qua `Message.images` → Gemini `Part.from_bytes`; không resize hoặc thay ảnh.
Local SDK boundary ghi MIME, số bytes và SHA-256 ngay trước generate_content.
Bốn requests đều chứa một inline PNG: BCC 4.431.609 bytes (hai lần), BED 3.075.848
bytes (hai lần); hashes khớp đúng ảnh frozen và corrected view/source envelope.
Đây là bằng chứng request thực chứa ảnh; không chứng minh model đối chiếu thành công.

Correction giữ source-ID/original gate M1-13; source anchor/bbox từ raw và image hash
ở view. `effective_text` luôn giữ raw; không tự confirmed, kể cả lời model nói nhìn
thấy hoặc suy cân đối tài chính. Structured schema nhỏ riêng vì raw contract đòi
provenance detector/coordinates không thể suy ra an toàn. Envelope page identity,
image hash và dimensions do local gắn; readings observed/inferred/unknown do model
khai, bbox/row/column nullable. `observed` không là xác nhận độc lập.

| Chỉ số | BCC 2021 trang ảnh 14 | BED 2023 trang ảnh 39 |
| --- | --- | --- |
| Vision correction | 0 proposals, 0 confirmed | 0 proposals, 0 confirmed |
| Đúng/sai proposals | N/A: không có proposal | N/A: không có proposal |
| Structured OCR model trả | 20 text elements, 1 bảng, 12 cells, 32 bbox | 25 text elements, 3 bảng, 20 cells, 45 bbox |
| Local validation | unresolved: columns=3 nhưng có column=3 | unresolved: bảng đầu columns=3 nhưng có column=3 |
| Source linkage | page identity + image hash + frozen mapping | page identity + image hash + frozen mapping |
| Vision tokens input/output | 7.708 / 20 | 12.042 / 20 |
| Structured tokens input/output | 1.390 / 2.818 | 1.391 / 3.117 |

Tổng **4 requests; 22.531 input + 5.975 output = 28.506 tokens** provider-reported;
unknown usage0/provider failures0. Correction pages assessed2; **structured pages
unresolved2**, không được hiểu `unresolved_pages=0` ở summary cũ là structured PASS.
Không gọi lại để cải thiện kết quả. Guard quota owner-attested15 RPM/250000 TPM/500 RPD,
money NOT_CONFIGURED; không khẳng định chi phí0 hoặc remaining quota. Image token
reservation là caller-attested tile bound, không phải actual provider token count;
không có aggregate input cap. Raw snapshots/images/manifest đối chiếu trước/sau bất biến.

Đối chiếu trực quan chính ảnh đầy đủ đã gửi: header BCC là `BỈM SƠN`; đoạn CRC là
`vấn đề môi trường`, không có từ `để`. **Vision correction bỏ sót cả hai** (như pilot
text-only trước). Structured OCR đọc đúng header `BỈM SƠN`, nhưng vẫn thêm `đê` trong
`vấn đề đê môi trường`: chưa giải quyết lỗi thứ hai. Không claim correction accuracy.

Đối chiếu tám giá trị BED với ảnh: lương hai năm của Nguyễn Văn Cần và Lê Mạnh,
doanh thu cho thuê và khoản thuê tối thiểu. Structured text khớp các số được xem;
chi tiết giá trị giữ trong private manual-comparison. Cặp doanh thu/khoản thuê được
model đặt ở text_elements, không gắn thành data cells trong hai bảng tương ứng.
Không tự xác nhận hoặc áp dụng số.
Không đánh giá toàn bộ ô/trang/dataset, chưa có ground truth.

Bbox model không đáng tin: BCC trả tọa độ cỡ0–1000 thay vì pixels2481×3510; BED có
biểu hiện đảo x/y và tọa độ cỡ0–1000. Bounds-only validation không chứng minh vị trí
đúng. Không tự rescale/đổi thứ tự hoặc sửa columns để làm PASS. Raw model responses
được lưu nguyên để so sánh, validated output=null cho cả hai. Không ingestion thay thế.

Private ignored artifacts: `artifacts/ocr-correction/M1-13a/` gồm live marker/policy,
manifest snapshots, page-2/page-4 corrected view và full structured response, live-result,
manual-comparison. Không commit ảnh/OCR/paths/keys hoặc dữ liệu tài chính nguồn.
219 focused + related tests passed (9 mới, 11 correction cũ, contracts/adapter/meter
regression); Ruff lint/format, planning checker, diff check. Runner đã gộp lại vào
runner cũ với --vision; dry-run cả hai modes đạt, không live rerun. CI exact SHA kiểm
tra sau push; chỉ đọc conclusion nếu PASS, không tải logs.

Next action: Tech Lead nghiệm thu implementation và limitations pilot; không tự DONE/M1-14.
