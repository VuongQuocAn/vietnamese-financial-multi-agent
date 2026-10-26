# Trạng thái hiện tại

Cập nhật **2026-10-26** (Asia/Bangkok). Nguồn trạng thái chính:
[Master Task Registry](tasks.md); tiếp tục phiên từ [Codex Handoff](handoff.md).

- Active task: **M0-04 — Project Task Tracking & Codex Handoff System**.
- Status: **REVIEW**. Registry/roadmap/dashboard/template/spec và checks local
  đã đạt; còn commit/push, đối chiếu CI và ghi evidence hoàn thành.
- M0-01 đến M0-03: DONE, đã đối chiếu commits trên `origin/main` và CI success.
- Git baseline trước task: `main`, working tree sạch, local/origin cùng
  `c86b86eb95ef91251a53b3768ae5c52c2ed73514` (ahead/behind 0/0).
  [CI 40208843162](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40208843162)
  success cho baseline; chưa phải CI của M0-04.
- Blocker: không có blocker được xác nhận. Model/storage/schema/ngưỡng/phạm vi
  tuân thủ còn TBD tại [decisions](decisions.md), không cản M0-04.
- Next action: publication M0-04 bằng commit đúng message, push bình thường và
  xác minh GitHub/CI; không bắt đầu M1-01.

## Implementation thực tế

M0 đã có skeleton, cấu hình phát triển, CI, smoke tests và dataset local được
tổ chức. Các package nghiệp vụ vẫn chỉ có docstring; chưa có Gateway, OCR loader/
resolver, normalization, EF-EG, tools, agents, verification, QA/report hoặc API.
Xem [dashboard](progress.md) để đối chiếu module và số task; không dùng phần trăm
cảm tính hoặc coi dữ liệu OCR có sẵn là implementation của repository.

## Kiểm tra của phiên

Local M0-04: Ruff lint/format đạt, 11 unit tests passed; tracking validator đạt
cho 72 task và phát hiện đúng 10 trường hợp lỗi cố ý trên bản sao tài liệu.
Metadata 9.127 file raw/OCR, lịch sử M0 và file ngoài phạm vi giữ nguyên.
CI M0-04 chưa được xác minh; kết quả chi tiết ở [spec](tasks/M0/M0-04.md) và handoff.
