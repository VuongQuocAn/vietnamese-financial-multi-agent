# Trạng thái hiện tại

Cập nhật **2026-10-26** (Asia/Bangkok). Nguồn: [Registry](tasks.md),
resume tại [handoff](handoff.md).

- Active implementation task: **Không có**; task vừa hoàn tất **M1-02a (DONE)**.
- M0-01 đến M0-04 và M1-01 vẫn DONE, không đổi task IDs hoặc scope task khác.
- Baseline main/origin đã fetch khớp `ddeef06691fe619f6cde8f3ac09d83c9595b0386`.
- Checkpoint nội dung `08f3289a47f021a97608b7e8d2885bd3656bc9c5` đã push origin/main.
- [CI 40274687167](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40274687167)
  success Python 3.11/3.12, gồm install/lint/format/planning/tests. Không suy ra
  kết quả CI checkpoint cho commit cập nhật trạng thái sau đó.
- Checkpoints A/B: models Pydantic v2, 7 types, nested table/cell/line, provenance,
  strict structural validation, quality issues riêng và source preservation.
- Local .venv Python 3.12: **91 unit tests passed** (57 contracts), Ruff lint/format,
  pip check và planning validator **72 task** đạt; cài editable .[dev] thành công.
- Schema raw_ocr_v1 đã xuất từ code và có test đồng bộ; docs contract đã cập nhật.
- Ba JSON mẫu phủ đủ 7 types giữ nguyên cấu trúc/giá trị sau parse/export.
- Metadata raw/processed khớp snapshot M1-01:
  `c92a8dd93accb74c936118b40eafc481febf8ec85559094c6c0d98b6217a16bb`.
  Chỉ đối chiếu metadata, không inventory lại hoặc hash toàn nội dung.
- Inventory M1-01 giữ nguyên: 9.127 file / 2.327.680.425 byte, 500 JSON trang,
  534 bảng, 21.461 cells; 24 representative và 6 pilot local Git ignore.
- Không gọi API/OCR mới hoặc benchmark tài chính; không có blocker M1-02a.
- Next action: chờ người dùng giao task tiếp theo; không bắt đầu M1-02b.

## Implementation thực tế

Có skeleton, cấu hình/CI, tracking, script khảo sát và Raw OCR Contract v1.
Chưa có loader/resolver, Gateway/Gemini, normalization, EF-EG, agents,
verification, QA/report hoặc API. Dừng sau M1-02a, không bắt đầu M1-02b.
