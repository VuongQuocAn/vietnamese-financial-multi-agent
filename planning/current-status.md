# Trạng thái hiện tại

Cập nhật **2026-10-27** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-11b IN_PROGRESS**, người dùng cho phép code/tests/bounded API/commit/push;
  dừng REVIEW chờ Tech Lead. M1-11/M1-11a DONE, M1-12 TODO.
- Baseline HEAD/origin `e14be8b9fd7dbaf269e9d78cb5a80b697297f33f` sạch sau fetch.
- Evidence-aware gate, policy fingerprint riêng với prediction cache; bỏ total token
  cap mặc định, giữ optional budget, per-request/quota/max20 requests/RPM5 gates.
- 319 targeted/regression passed; Ruff/planning/diff đạt, không full local suite.
- Dry-run 19 trang/3 mã/14 strata/API0; frozen order/snapshots khớp M1-11a, prefix5
  là 5 completed pages cũ. Pilot thật đang chạy một lượt, không khởi động lại.
- Prior cache RAM không persisted, 0 resolved checkpoints; không prediction cũ để reuse.
  Không sửa original M1-11a artifacts/credentials/source/contracts.
- M1-11a lịch sử: 6 requests/5 pages/0 resolved/5 unresolved, 12307 input/176 output;
  4 quality/1 insufficient. [Evidence](../docs/reviews/M1-11a-evidence.md) giữ nguyên.
- Taxonomy provisional/no ground truth; quota remaining/billing/project ID chưa
  independently verified, free-only owner attestation/guard money NOT_CONFIGURED.
- [Spec](tasks/M1/M1-11b.md), [usage](../docs/classification-pilot.md).
- Next action: **Đợi pilot đang chạy kết thúc, đối chiếu evidence và publish REVIEW sau CI.**
