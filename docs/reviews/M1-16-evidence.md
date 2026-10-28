# M1-16 — Unified Document Understanding evidence

2026-10-28 (Asia/Bangkok), **REVIEW**, chờ Tech Lead. Baseline
`e80319975b1eeef79efc68fac5007980cb20a2a7`, main/tree sạch trước sửa.
Một implementation commit gồm report này; SHA lấy bằng
`git log -1 --format=%H -- src/document_processing/understanding_pipeline.py`.
CI hiện có chạy sau push; kiểm tra exact SHA/jobs/steps và báo cuối phiên,
private receipt lưu local; không publication commit chỉ để ghi CI.
Implementation `7486a6140ac075b90d2c2454f6703b6a56186b1a` đã push;
CI40620767512 dừng format Python code fence trong Markdown. Có thêm đúng một
commit sửa định dạng tài liệu; code/tests/replay không đổi, không rewrite lịch sử.

Entrypoint `run_document_understanding(source, UnderstandingOptions(...))` dùng
read-only loader cho Existing OCR, M1-15 cho PDF/PNG. Export `unified_document_v1`
giữ text/tables/cells, selectors riêng raw IDs, source identity/hashes/references,
quality flags, issues/history và recovery decisions. [API/contract](../unified-document-understanding.md).

Replay thật từ dataset/artifacts local, không synthetic evidence:

| Nguồn | Trang | Text giữ/accepted | Tables giữ/unresolved | Cells giữ | Cell text accepted/unresolved | Cell layout accepted |
| --- | --- | --- | --- | ---: | --- | ---: |
| Existing OCR BBS2025 | 5 | 6/6 | 1/1 | 97 | 97/0 | 0 |
| M1-15 native BBS2025 | 5 | 6/6 | 1/1 | 112 | 97/15 | 64 |
| M1-15 native BBS2025 | 7 | 13/13 | 1/1 | 100 | 87/13 | 100 |
| M1-15 native BBS2025 | 8 | 14/14 | 1/1 | 123 | 105/18 | 121 |

Native tổng33 text/3 tables/335 cells;289 cell texts accepted/46 unresolved,
285 cell layouts accepted. 3/3 tables unresolved do text hoặc layout; geometry0
verified. So sánh chính xác từng text và danh sách cell texts với persisted M1-15;
không mất text/cells. Raw table cell texts cũng bằng nguồn từng ô, giữ lines/IDs.
Existing raw row/col là candidates, không tự chạy lại reconstruction để accept.
Schema valid4/4 input pages không đồng nghĩa layout/geometry hoặc financial accuracy.

Native replay dùng persisted manifest + PNG + response payload, kiểm tra exact
provenance/identity và image hash/dimensions; chạy lại component validation, không
tin status đã lưu. Giữ PDF/page/image identity và PDF hash từ manifest, **không
rehash PDF gốc** trong replay này. Existing source metadata/provenance và anchor
identity checked được giữ; không yêu cầu PDF. 9 source files đọc (OCR JSON,
linked raw PNG, manifest và 3 pairs PNG/JSON) hash trước/sau khớp.

Không có bbox mới/IDs giả; candidate bbox nằm ở source_component, top-level bbox
null. Native provenance chỉ page-level, selector không thành raw cell ID.
Classification native unresolved vì thiếu region anchors qua gate M1-11.
Recovery chỉ đề xuất/reason, executed=false, không executor/API tự động.
Downstream focused consumer round-trip cùng contract cho hai nhánh, chọn
usable_for=text_evidence; không triển khai M2/accounting normalization.

Local:10 focused tests passed;77 loader regression passed vì thêm snapshot hash;
Ruff changed files, planning checker, diff check đạt. PDF nhiều trang/PNG được
kiểm thử synthetic offline, không gọi đó là replay tài chính thật. Không full
local suite; CI full unit Python3.11/3.12. **0 Gemini API requests mới**.
Private outputs/receipt dưới artifacts/document-understanding/M1-16/, ignored;
không stage dữ liệu, OCR/PDF/PNG, artifacts, credentials hoặc đường dẫn cá nhân.

Next action: Tech Lead review implementation, CI exact SHA và giới hạn quality.
