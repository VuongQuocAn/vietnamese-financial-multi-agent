# Trạng thái hiện tại

Cập nhật **2026-10-27** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- M1-04a **DONE**, Tech Lead APPROVED engineering; finalization
  6bfd43209d47ada1f236f8619ebc876c47c60f28 đã push/main khớp origin.
  [CI 40435213198](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40435213198)
  success exact SHA, mọi steps Python 3.11/3.12 verified.
- M1-04b **IN_PROGRESS**, user giao implementation/pilot/commit/push, dừng REVIEW.
  [Spec/protocol](tasks/M1/M1-04b.md) Checkpoint A chốt trước đọc thêm dữ liệu thật;
  TODO → READY → IN_PROGRESS, duy nhất một active task.
- Hai nhóm coverage/risk không trùng, deterministic approved pool, <=30 pages/500 refs.
  Default preflight, immutable freeze trước execute; không sửa validators/data/ledger.
- M1-04 cha TODO, M1-05 ngoài scope; 5 bbox issues không đóng.
- Checkpoint C: frozen manifest 23 pages/398 crop references, không vượt trần;
  targeted cuối 40 passed, full cuối 768 passed/2 skipped; Ruff/planning/pip/diff đạt.
- Checkpoint F: hai reports/digests/membership khớp; 472 selected input snapshots
  không đổi (390 files/82 absence), chỉ 28 selected recovered files hash.
  316 original/14 reconstructed/68 unrecovered; 5 human issues giữ requires_review.
- [Evidence draft](../docs/reviews/M1-04b-evidence.md) và sanitized statistics đã có.
- Exact next action: **allowlist commit/push implementation và kiểm tra exact-SHA CI**.
