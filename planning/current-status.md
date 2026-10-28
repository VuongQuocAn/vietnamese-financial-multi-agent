# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-14 REVIEW**, được user giao triển khai/commit/push; M1-13b DONE, không M2.
- Baseline acceptance `7ed1b808239d5a1240f79a167d6c06ac8b677da8` đúng, tree sạch.
- Evaluator offline, private benchmark4 pages/46 labels/18 số; 36 vị trí/3 bảng.
- Common2 pages/26 labels: A/B24/26, C26/26; số6/6 cả ba.
- A/B same8 structure accepted1/8→2/8; C schema2/2 nhưng tables0/4 accepted.
- Khuyến nghị Hybrid có kiểm soát; sample B09-only, thiếu human second review,
  full grid/merge/bbox truth và paired latency/cost; không accuracy toàn dataset.
- 0 API mới; source/images/raw/persisted outputs bất biến, private artifacts ignored.
- 8 focused tests, Ruff/planning/diff; CI exact implementation SHA kiểm sau push,
  báo trong bàn giao cuối, không publication commit cập nhật SHA.
- [Spec](tasks/M1/M1-14.md), [report](../docs/reviews/M1-14-evaluation.md).
- Next action: **Tech Lead review nhãn, metrics và đề xuất Hybrid; giữ REVIEW.**
