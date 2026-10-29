# Codex Handoff

## Active Task

W-03 — PDF Upload & Gemini Vision Metadata Preflight (housekeeping 2026-10-29)

## Status

REVIEW

## Last Verified State

PR#1/#2/#3 đã MERGED tuần tự vào main, không conflict/force/delete branch.
Merge commits167e8fa/cb9efeb/6dd0d1d, CI main sau từng merge SUCCESS.
PR#1 formatting fence5779d45 đã CI PASS trước merge. Quyền merge user cấp29/10
thay giới hạn draft cũ. W-03 REVIEW, không tự DONE/W-04/M3.

## Completed Work

Root dev.ps1 kiểm dependencies, đọc local key/env/.env, chạy backend+frontend
cùng console, URL và Ctrl+C cleanup process tree sở hữu. Proxy/Origin/ports tự
đồng bộ, không gửi key sang Next. Update README/local guide/W-03 usage/evidence.
Launcher startup, live upload scan→auto-ready và cleanup/error cases đã PASS.

## Remaining Work

Commit/push housekeeping main, xác minh CI và ghi publication SHA. Chờ chỉ đạo;
không bắt đầu W-04.

## Modified Files

dev.ps1, README, docs/web-demo-v1/{local-development,w-03-usage,w-03-validation},
planning/{current-status,handoff,progress,roadmap,tasks,tasks/W/W-03}.
Giữ next-env local byte-for-byte, không stage. Không sửa backend/Next logic/CI.

## Tests

PowerShell syntax/startup/health/proxy/Ctrl+C/port-busy/custom ports/failure cleanup
PASS trên Windows.1 live call synthetic2 trang, gemini-3.5-flash-lite,2794 tokens,
metadata đúng và ready/auto; không chạy benchmark hoặc gọi lại AI.
CI main từng merge SUCCESS; launcher publication CI chờ push. Ruff/targeted
checks/planning/diff/index kiểm trước commit, không full local suite.

## Blockers

Không blocker. Dependencies cài một lần theo guide; chỉ launcher nếu local key
file hợp lệ. Provider/tier/quota assumptions W-03 giữ nguyên, không tăng phạm vi.

## Git Checkpoint

Main baseline6dd0d1d7c3fd2d92e3fc62d091348eb832d3c28e. Launcher chưa commit tại
checkpoint này. Temporary worktree/stash và Next-generated AGENTS đã cleanup.
Chỉ user next-env có sẵn ngoài task; không key/PDF/cache/counters trong Git.

## Exact Next Action

Commit/push housekeeping và xác minh CI.
