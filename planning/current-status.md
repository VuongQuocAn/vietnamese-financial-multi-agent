# Trạng thái hiện tại

Cập nhật **2026-10-26** (Asia/Bangkok). Nguồn: [Registry](tasks.md),
resume tại [handoff](handoff.md).

- Active implementation task: **Không có**. Task vừa hoàn tất: **M1-01 (DONE)**.
- M0-01 đến M0-04 vẫn DONE; không thay đổi task IDs hoặc scope task khác.
- Checkpoint nội dung M1-01 `dbfbb760ec6c85391da47199edd52510fda216a8` đã push origin/main.
- [CI 40272513247](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40272513247) success Python 3.11/3.12, gồm lint/format,
  planning và unit tests. Run này gắn với checkpoint nội dung; không suy ra
  cho commit cập nhật trạng thái sau đó.
- Inventory: **9.127 file / 2.327.680.425 byte**, **500 JSON trang**, 534 bảng,
  21.461 cells; metadata raw/processed trước/sau và sau kiểm tra ảnh khớp nhau.
- Có [discovery report](../docs/ocr-data-discovery.md), 24 representative (8/mã,
  phủ 15 báo cáo) và 6 pilot; đã xem 8 ảnh raw local. Artifacts bị Git ignore.
- Cảnh báo: 572 crop references thiếu suffix local, 263 cell bbox bất thường,
  64 duplicate row/col vượt lần đầu; 19 ứng viên bảng ngầm chưa là ground truth.
  BCC/2025 chỉ có 2 trang local. Xem report để phân biệt cảnh báo và kết luận.
- Local .venv Python 3.12: Ruff lint/format đạt; **34 unit tests passed**;
  validator đạt **72 task**. Không gọi API, OCR mới hoặc benchmark tài chính.
- Blocker M1-01: không có. Schema/nguồn Drive/quyền corpus/ngưỡng và model
  còn TBD theo task sau, không được coi là đã duyệt.
- Next action: chờ người dùng giao task tiếp theo.

## Implementation thực tế

Có skeleton, cấu hình/CI, tracking và script khảo sát độc lập. Package nghiệp
vụ vẫn chỉ có docstring; chưa có OCR loader/resolver, Gateway/Gemini,
normalization, EF-EG, agents, verification, QA/report hoặc API. Dừng sau M1-01.
