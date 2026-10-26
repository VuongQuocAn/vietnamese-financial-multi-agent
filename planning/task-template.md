# TASK <TASK-ID> — <Task Name>

## Metadata

- Milestone: <M0..M8>
- Status: TODO
- Priority: <P0/P1/P2>
- Dependencies: <Task IDs tồn tại, phân cách bằng dấu phẩy; hoặc ->
- Estimated Complexity: <XS/S/M/L>
- Related Modules: <module/tài liệu liên quan>

## Objective

Một mục tiêu cụ thể, có thể nghiệm thu độc lập.

## Context

Chỉ liệt kê tài liệu và quyết định cần đọc, không đọc lại toàn repository.

## Inputs

Đầu vào, quyền truy cập, giới hạn mẫu; ghi `TBD` nếu chưa xác định.

## Outputs

Artifacts cụ thể; dữ liệu/kết quả lớn ở vị trí local bị Git bỏ qua.

## Allowed Changes

Liệt kê file/module được sửa, không gộp nhiều module lớn.

## Out of Scope

Nêu giới hạn nghiệp vụ, API/ngân sách và dữ liệu read-only.

## Implementation Steps

1. Đọc current status, handoff và spec; kiểm tra Git/checkpoint thực tế.
2. Xác minh dependencies/inputs; xem xét chia M/L trước khi triển khai.
3. Thực hiện phần độc lập, kiểm thử và ghi checkpoint ổn định khi phù hợp.
4. Đồng bộ registry/dashboard/spec/handoff, nghiệm thu, commit/push nếu được giao.

## Acceptance Criteria

- [ ] Đầu ra đáp ứng mục tiêu/contracts đã duyệt.
- [ ] Kiểm thử liên quan đạt; bằng chứng và giới hạn được ghi rõ.
- [ ] Raw/OCR giữ nguyên; không có dataset/secrets trong tập commit.
- [ ] Tiêu chí riêng được làm rõ trước READY.

## Required Tests

Nêu lệnh, phạm vi và kết quả cần đạt. Kiểm tra cơ bản: Ruff lint/format,
unit tests liên quan và `python scripts/check_planning.py`. Không dùng smoke
tests làm benchmark; không chạy lại công việc đã xác minh khi không có lý do.

## Risks and Blockers

BLOCKED: ghi lý do, dependency thiếu và hành động gỡ chặn. REVIEW: ghi phần cần
nghiệm thu. Không tự chọn công nghệ/schema chưa được duyệt.

## Implementation Evidence

- Commit SHA: TBD (SHA đã xác minh, không phải commit tương lai).
- Test Results: Chưa chạy.
- Review Notes: Chưa nghiệm thu, chỉ DONE khi mọi acceptance criteria đạt.

## Handoff Notes

Ghi completed/remaining work, modified files, checkpoint và đúng một next action.
Cập nhật handoff sau phần độc lập quan trọng, không đợi quota hết. Task ID bất
biến; không tự chuyển task. Chi tiết resume tại `planning/handoff.md`.
