# Codex Handoff

## Active Task

M0-04 — Project Task Tracking & Codex Handoff System (task vừa hoàn tất).
Không có active implementation task mới.

## Status

DONE

## Last Verified State

2026-10-26 (Asia/Bangkok): M0-04 checkpoint `3c7d78c6855467262beca6064d657bb23a7a2e3e`
đã push lên `origin/main`; local/remote khớp, working tree sạch ở checkpoint.
[CI 40269619726](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40269619726) success trên Python 3.11 và 3.12,
gồm lint/format, tracking validation và unit tests. Bản ghi này được cập nhật
sau khi xác minh kết quả đó; không tự coi run này là CI của commit tương lai.
M0-01/02/03 và lịch sử/IDs đã đối chiếu, không có blocker cũ còn mở.

## Completed Work

Roadmap M0–M8, registry 72 task, dashboard, template, spec M0-04/M1-01 và thư mục
M0–M8 đã tạo. AGENTS/README hướng dẫn checkpoint/resume; có validator standard
library trong CI. Giữ lịch sử cũ, chia M1-02/03/04 bằng hậu tố, không đổi scope/ID.
M0-04 DONE, M1-01 READY; chưa có implementation M1 hoặc nghiệp vụ mới.

## Remaining Work

Không còn acceptance criteria mở của M0-04. Backlog tương lai ở registry,
không tự chuyển sang triển khai. Chỉ khi được giao mới bắt đầu task READY.

## Modified Files

- `.github/workflows/ci.yml`, `AGENTS.md`, `README.md`.
- `planning/roadmap.md`, `tasks.md`, `current-status.md`, `decisions.md`.
- `planning/progress.md`, `handoff.md`, `task-template.md`.
- `planning/tasks/M0/M0-04.md`, `planning/tasks/M1/M1-01.md`.
- `planning/tasks/M2/.gitkeep` đến `M8/.gitkeep` (chỗ giữ thư mục).
- `scripts/check_planning.py`.

Danh sách là phạm vi M0-04, không phải khẳng định working tree đang dirty.
Luôn kiểm tra `git status --short` khi resume; không commit thay đổi ngoài task.

## Tests

Local Python 3.12.0: Ruff 0.17.2 lint/format đạt; pytest 9.1.1, **11 passed**.
`python scripts/check_planning.py`: 72 task nhất quán. 10 bản sao tài liệu lỗi
(duplicate ID, dependency thiếu/vòng, status sai, thiếu evidence, dashboard,
link, READY chưa đủ gate, metadata spec, nhiều active task) bị từ chối đúng nguyên nhân.
Metadata đủ 9.127 file raw/OCR và hash file Git ngoài phạm vi không đổi.
CI checkpoint nêu trên kiểm tra độc lập Python 3.11/3.12. Không gọi Gemini,
đánh giá tài chính hoặc xử lý OCR trong M0-04.

## Blockers

Không có blocker M0-04. TBD về model, storage, contracts/ngưỡng và phạm vi pháp
lý nằm trong [decisions](decisions.md); task sau phải làm rõ theo phạm vi, không
được tự biến TBD thành quyết định đã duyệt.

## Git Checkpoint

Checkpoint đã push và có CI success: `3c7d78c6855467262beca6064d657bb23a7a2e3e`.
Bản ghi DONE có thể nằm ở commit tiếp theo cùng message theo yêu cầu; khi resume,
kiểm tra `git log -1`, `git status --short --branch`, `git fetch origin` và
`git rev-list --left-right --count HEAD...origin/main`. Không reset về checkpoint
hoặc làm lại phần đã kiểm tra chỉ vì SHA mới hơn bản ghi này.

## Exact Next Action

Chờ người dùng giao [M1-01](tasks/M1/M1-01.md), không tự bắt đầu task.
Khi được giao: đọc AGENTS → current-status → handoff → spec M1-01, kiểm tra Git
thực tế rồi chỉ đọc tài liệu/module liên quan và chuyển task sang IN_PROGRESS.
Ghi checkpoint sau phần độc lập đã kiểm thử; không giả định luôn kịp bàn giao
khi quota/IDE dừng đột ngột.
