# Codex Handoff

## Active Task
W-01 — Web Demo V1 Architecture, API Contracts & UI Design

## Status
REVIEW

## Last Verified State
Baseline sau fetch `5c8a80e4ceedb735dcbad12e267620b0b8046adb` trùng origin/main;
main chỉ docs/UI untracked, M2-09 DONE. Nhánh docs/w-01-web-demo-design.
Task đính kèm cho phép W-01 design và commit/push; không W-02/M3.

## Completed Work
Đã đọc required planning/architecture/contracts/M2-09 và backend M1–M2/tests;
đọc cả hai Stitch DESIGN/HTML, quan sát PNG. Ba tài liệu web-demo-v1 gồm
architecture/integration/session/security, REST/metadata/JSON, UI tokens/routes.
Checker mở rộng W IDs/spec/counts và links docs mới; ba regression tests PASS.
Sáu Stitch files nguyên bản, tổng 266161 bytes; không dataset hoặc secrets.

## Remaining Work
Tech Lead nghiệm thu độc lập W-01: kiến trúc, API/metadata, UI và giới hạn runtime.
Chưa xây app/metadata extractor; không tự DONE hoặc bắt đầu W-02/M3.

## Modified Files
Ba docs/web-demo-v1/*.md; planning/tasks/W/W-01.md; tasks/progress/current-status/
handoff/roadmap; scripts/check_planning.py; tests/unit/test_check_planning.py;
sáu docs/UI assets nguyên bản được thêm để bàn giao reference.

## Tests
Local checker regressions 3 PASS; Ruff lint/format hai file PASS;
planning checker 87 tasks PASS; 11 JSON examples parse PASS và value/context
example validate trực tiếp bằng models M2, Decimal zero/scale giữ wire strings.
git diff --check PASS; staged check phần W-01 tự viết PASS. Staged toàn bộ
báo bốn trailing spaces tại dòng 121/138 của hai DESIGN.md gốc; giữ nguyên theo
yêu cầu bảo toàn Stitch, không tắt checks. Sáu staged blobs khớp bytes gốc.
Không live Gemini/financial benchmark/full unit local/web E2E; M1–M2 không sửa.
Sau push, gh run list trên nhánh trả []; workflow chỉ push main hoặc pull_request,
chưa mở PR nên không kích hoạt CI. Không báo CI SUCCESS hoặc dùng CI M2-09 thay W-01.

## Blockers
Không blocker thiết kế. Metadata extractor mới; extraction không callback nên
adapter per-page và aggregate quality; cache/quota in-memory cần conservative
restart policy. Cần Tech Lead review internal symbol namespace và status policy.

## Git Checkpoint
Baseline ổn định `5c8a80e4ceedb735dcbad12e267620b0b8046adb`.
Design/checker/assets commit
`7a158f31e2feab0895d4ca5054bdbb56e78526be` đã push;
git ls-remote xác nhận nhánh docs/w-01-web-demo-design khớp exact SHA, tree sạch
sau push. Commit tiếp theo chỉ cập nhật planning evidence của checkpoint này,
không thay design/code/assets. Không tự merge main. CI không có run như Tests.
Không stage credentials/.env/raw/cache/PDF/reference hoặc dữ liệu private.
Stitch bytes đã hash đối chiếu, chỉ tài liệu thiết kế reference được commit.

## Exact Next Action
Tech Lead nghiệm thu độc lập W-01.
