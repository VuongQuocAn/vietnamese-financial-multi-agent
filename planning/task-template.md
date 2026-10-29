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

1. Đọc current status, handoff nếu cần và spec; kiểm tra Git/checkpoint thực tế.
2. Xác minh dependencies/inputs; xem xét chia M/L trước khi triển khai.
3. Thực hiện phần độc lập, kiểm thử và ghi checkpoint ổn định khi phù hợp.
4. Ghi status/evidence ngắn tại registry; chỉ đồng bộ tài liệu có thông tin thay
   đổi. Dừng REVIEW, commit/push nếu được giao; không tự nghiệm thu/sang task khác.

## Acceptance Criteria

- [ ] Đầu ra đáp ứng mục tiêu/contracts đã duyệt.
- [ ] Chức năng đúng + bằng chứng phù hợp + targeted validation đạt: đủ REVIEW.
- [ ] Phân biệt engineering smoke với research evaluation; không coi synthetic
      PASS là bằng chứng độ chính xác tài chính.
- [ ] Raw/OCR giữ nguyên; không có dataset/secrets trong tập commit.
- [ ] Tiêu chí riêng được làm rõ trước READY.

## Required Tests

Nêu lệnh và phạm vi thực sự cần theo [Research MVP Lean](../AGENTS.md): 1–3 targeted
tests nếu cần, một integration smoke khi đổi chức năng, lint/format file đã sửa;
frontend build khi ảnh hưởng build. Docs-only chỉ cần planning checker nếu sửa
planning và diff check; không chạy lại smoke/benchmark cũ.

Full regression chỉ khi module chung có rủi ro lan rộng, nghiệm thu milestone
quan trọng hoặc Tech Lead yêu cầu. Không xóa tests hiện có. CI Python 3.12 chạy
nhóm tests trọng tâm; ghi kết quả local/CI riêng, không suy diễn chưa chạy.
Research evaluation dùng PDF scan thực tế, độ đúng số liệu/provenance/QA và so sánh
Multi-Agent khi thuộc mục tiêu, trong ngân sách đã được giao.

## Risks and Blockers

BLOCKED: ghi lý do, dependency thiếu và hành động gỡ chặn. REVIEW: ghi phần cần
nghiệm thu. Không tự chọn công nghệ/schema chưa được duyệt.

## Implementation Evidence

- Implementation SHA: TBD (SHA đã xác minh; ghi chưa commit nếu chưa có).
- Main Changes: Tóm tắt ngắn.
- Test Results: Chưa chạy.
- Review Notes: Chưa nghiệm thu, chỉ DONE khi mọi acceptance criteria đạt.

## Handoff Notes

Chỉ cần status, implementation SHA, thay đổi chính, tests thực sự đã chạy và đúng
một next action; có thể ghi tại registry, không lặp lại ở mọi tài liệu. Handoff
ngắn khi cần resume; dashboard chỉ cập nhật khi số đếm/trạng thái thay đổi. Không
bắt validation report riêng cho thay đổi nhỏ. Task ID bất biến; Tech Lead review
trước DONE; không tự chuyển task. Giữ các headings để tương thích checker.
