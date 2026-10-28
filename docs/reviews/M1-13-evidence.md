# M1-13 — Evidence-Preserving OCR Correction

Ngày 28/10/2026; Research MVP Lean v3. Engineering review, không financial accuracy.

`OCRCorrector(service).correct(loaded, source_ref=..., credential_ref=...,
cache_allowed=True)` trả `CorrectionResult.view` và `llm_result` (Gateway usage/errors).
Compose service với `correction_schema_registry()` như runner. LoadedOCRPage cần
identity_checked + resolved mapping/anchor khớp đúng source_ref. Không đổi raw/DU v1.

Prediction chỉ có disposition và corrections(element_id, cell_id, original, proposed,
reason). Local strict schema + exact source gate; cell ID được scope trong table.
Không nhận model status/bbox/anchor. Original sai hoặc ID không tồn tại bị loại,
page unresolved; duplicate proposals giữ audit unresolved, không chọn winner.
Empty/unchanged replacements unresolved; clean page có thể có zero corrections.
SourceAnchor sao chép identity/bbox từ raw; source_digest phủ toàn export_source.

Mỗi correction giữ original/proposed/reason/source_anchor/status/issues. `proposed`
nghĩa là candidate đã bind nguồn, chưa kiểm chứng nội dung; `confirmed` dành cho
bằng chứng độc lập. MVP không có verifier độc lập nên **không phát sinh confirmed**.
Schema/provider/guard failures trả unresolved, không sinh correction giả.
Corrected View có mọi text/cell, original/effective_text/proposed/status; effective_text
luôn giữ raw ở MVP này. Consumer không được diễn giải proposed thành financial truth.
Không suy số liệu bằng cân đối, không dùng OCR lines cùng run hoặc Gemini làm xác nhận.

Runner: `python scripts/run_ocr_correction_pilot.py --live --key-index 0` sau khi cấu hình
hai input-root environment variables như `.env.example`. Default dry-run API0.
Hai trang cố định M1-04b indices 2/4; full-page OCR gồm cells/lines/geometry/provenance,
không truncate. Gemini `gemini-3.5-flash-lite`, structured JSON, một credential/project,
SDK attempts1, không retry/rotation. Cache chung được reuse đơn giản; không probes.
Pilot giới hạn hai requests bằng membership, không đặt aggregate input-token cap.
Quota guard 15 RPM/250000 TPM/500 RPD theo owner authorization M1-13; không chứng nhận
provider remaining quota/billing. MeteredModels nhận RPM cấu hình, defaults cũ giữ nguyên.
Per-request reservation tính từ toàn content/schema UTF-8; provider TPM vẫn được enforce,
không giảm evidence để vừa quota. Exclusive live marker không cho reset scope khi restart.

Pilot thật: **2 pages, 0 corrections (proposed0/confirmed0/unresolved0)**; cả hai page
assessed, không có provider/schema failures. **2 requests, 17450 input/40 output/
17490 total tokens**, unknown usage0; guard money NOT_CONFIGURED. OCR snapshots và
frozen manifest đối chiếu trước/sau bất biến; không claim actual billing bằng 0.
Đối chiếu trực quan ảnh BCC p14 cho thấy raw header `BÍM SƠN` thay vì `BỈM SƠN`, và
raw `vấn đề để môi trường` có thêm `để` so với ảnh. **Gemini bỏ sót các lỗi này**;
đây là ví dụ kiểm tra thủ công, không phải model correction hoặc auto-confirmation.
Không correction số nào được đề xuất/kiểm chứng ở pilot này. Zero proposals không
chứng minh văn bản đúng. Chưa ground truth; không tuyên bố correction accuracy.

11 focused tests +47 related regression passed (MeteredModels/table assistance);
final focused11 passed sau source-gate refinement. Ruff files thay đổi, planning
checker/diff check trước commit; CI full unit 3.11/3.12 trên exact implementation SHA
kiểm tra sau push, kết quả trong báo cáo bàn giao, không tạo publication commit.
Artifacts private ignored `artifacts/ocr-correction/M1-13/`; không commit dataset,
credentials, source paths hoặc ảnh. Trạng thái REVIEW, chờ Tech Lead.
