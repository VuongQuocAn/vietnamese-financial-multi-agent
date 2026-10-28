# Codex Handoff

## Active Task

W-02 — Frontend/Backend Skeleton & Local Development

## Status

REVIEW

## Last Verified State

Ngày 28/10/2026, W-01 DONE, PR #1 OPEN/chưa merge. Baseline local/origin
docs/w-01-web-demo-design `31ca5704c388b31ac102b19577b030fcb1026628`, đã fetch,
working tree sạch. Không CI runs trên acceptance vì [skip ci]; không có run để
rerun và không workflow_dispatch. Không merge hoặc sửa dependency.

## Completed Work

Next.js 16.4.3/React 19.3.1/TS strict/Tailwind 4/Lucide, font Be Vietnam Pro
local, bốn routes, sidebar navigation/collapse, dashboard/empty documents,
Explorer split slider keyboard/mobile pane toggle, statement tabs, source details,
FinancialTable raw strings/dynamic periods/selection/status và AI Coming Soon.
FastAPI health, proxy environment, Windows docs; CI thêm web job, giữ Python gates.
Không upload/provider/API tài chính, không sửa M1–M2 hoặc sáu Stitch assets.

## Remaining Work

Chờ Tech Lead nghiệm thu W-02. Full unit suite bổ sung đang chạy; publication/
CI evidence được bổ sung sau xác minh. Không tự triển khai W-03 hoặc M3.

## Modified Files

web/, src/api/, tests/unit/test_api.py, pyproject.toml, .gitignore,
.github/workflows/ci.yml, README.md, docs/web-demo-v1/local-development.md,
planning/tasks/W/W-02.md và registry/dashboard/status/handoff/roadmap.

## Tests

Local typecheck/ESLint/build PASS; targeted API/package/planning 16 PASS;
Ruff check . PASS, format src/tests/scripts 130 files PASS; planning 88 tasks
PASS. Chromium routes/navigation/font/keyboard/responsive 1440/1280/390,
synthetic table và FastAPI proxy: 5 PASS. Screenshots đã xem, không pixel-perfect.
Full-tree Ruff 0.17.2 format FAIL: architecture W-01 tồn tại ngay trên baseline;
bốn docs cũ khác có CRLF local. Không sửa assets/docs để che checks.

## Blockers

Global formatting gate có lỗi baseline ngoài W-02; chưa có CI SUCCESS.
PR #1 chưa merge; dùng stacked development, chưa thể coi W-02 sẵn merge main.
Upload/PDF viewer/evidence API/AI chưa triển khai đúng scope skeleton.

## Git Checkpoint

Baseline ổn định đã push W-01: `31ca5704c388b31ac102b19577b030fcb1026628`.
Nhánh W-02 feat/w-02-web-skeleton, base PR docs/w-01-web-demo-design.
Implementation đã chạy/kiểm chứng local; commit/remote/CI ghi sau publication,
không ghi SHA tương lai. Không stage datasets/secrets/node_modules/.next/screenshots.

## Exact Next Action

Tech Lead nghiệm thu độc lập W-02 và quyết định xử lý lỗi format baseline.
