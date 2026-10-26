# Codex Handoff

## Active Task

M0-04 — Project Task Tracking & Codex Handoff System.

## Status

REVIEW

## Last Verified State

2026-10-26 (Asia/Bangkok): baseline trước task local/origin cùng
`c86b86eb95ef91251a53b3768ae5c52c2ed73514`, working tree sạch;
[CI 40208843162](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40208843162)
đã success. M0-01/02/03 được đối chiếu Git/CI, không dựa riêng vào nhãn tài liệu.

## Completed Work

Soạn roadmap M0–M8, registry 72 task, dashboard, template, spec M0-04/M1-01;
giữ lịch sử và ID cũ, chia M1-02/03/04 bằng hậu tố. Thêm validator standard
library và bước CI. Cập nhật AGENTS/README/quyết định quản lý; chỉ thay đổi tài
liệu và automation tracking. Chưa có implementation nghiệp vụ mới.

## Remaining Work

Local checks, phạm vi và metadata đã đạt. Còn commit/push, xác minh CI M0-04,
ghi SHA/evidence và đồng bộ DONE. Sau M0-04 DONE, chuyển M1-01 sang READY và
spec tương ứng, không triển khai M1-01.

## Modified Files

- `AGENTS.md`, `README.md`, `.github/workflows/ci.yml`.
- `planning/roadmap.md`, `tasks.md`, `current-status.md`, `decisions.md`.
- `planning/progress.md`, `handoff.md`, `task-template.md`.
- `planning/tasks/M0/M0-04.md`, `planning/tasks/M1/M1-01.md`.
- `planning/tasks/M2/.gitkeep` đến `M8/.gitkeep` (chỗ giữ thư mục, không phải spec).
- `scripts/check_planning.py`.

Đối chiếu `git status --short` khi resume, không giả định working tree giống bản ghi.

## Tests

Local M0-04: `python scripts/check_planning.py` đạt cho 72 task; 10 bản sao tài
liệu lỗi bị từ chối đúng nguyên nhân. Ruff lint/format đạt, 11 unit tests passed.
So sánh metadata đủ 9.127 file raw/OCR không đổi, lịch sử M0 bảo toàn; chỉ sửa
file được phép. CI baseline nêu trên chưa thay thế CI M0-04.

## Blockers

Không có blocker đã xác nhận. Nếu Git/CI/validation lỗi, ghi nguyên nhân và
remaining work, không DONE. TBD công nghệ/contracts của task tương lai xem
[decisions](decisions.md); không tự giải quyết trong M0-04.

## Git Checkpoint

Checkpoint ổn định trước task: `c86b86eb95ef91251a53b3768ae5c52c2ed73514`.
Chưa có checkpoint M0-04. File đang sửa/chưa commit phải được xác minh bằng
`git status`, `git log -1`, `git diff`; không reset hoặc làm lại phần đã kiểm tra.

## Exact Next Action

Đọc AGENTS → [current-status](current-status.md) → handoff →
[spec M0-04](tasks/M0/M0-04.md), kiểm tra Git rồi thực hiện publication M0-04:
đầu tiên rà soát staged bằng `git diff --cached --check` trước commit đúng message.
Sau mỗi phần độc lập đã kiểm thử, cập nhật handoff/checkpoint; không giả định có
cơ hội ghi lại khi quota/IDE dừng đột ngột. Không tự chuyển sang task M1.
