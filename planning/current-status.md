# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-14 DONE** — Tech Lead APPROVED có điều kiện; M1-13b DONE, không task triển khai active.
- Baseline acceptance `7ed1b808239d5a1240f79a167d6c06ac8b677da8` đúng, tree sạch.
- Evaluator offline, private benchmark4 pages/46 labels/18 số; 36 vị trí/3 bảng.
- Common2 pages/26 labels: A/B24/26, C26/26; số6/6 cả ba.
- A/B same8 structure accepted1/8→2/8; C schema2/2 nhưng tables0/4 accepted.
- Hybrid là **provisional architecture recommendation**, không chứng minh accuracy vượt trội;
  benchmark chỉ4 trang, C chỉ2 trang, sample B09-only, thiếu human second review,
  full grid/merge/bbox truth và paired latency/cost; không accuracy toàn dataset.
- 0 API mới; source/images/raw/persisted outputs bất biến, private artifacts ignored.
- Implementation `176844cec032c792152c82326a7935a8c31045f8`; [CI 40615555237](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40615555237)
  completed/success đúng SHA, mọi steps Python3.11/3.12 success.
- Nghiệm thu chỉ planning, không chạy lại evaluation/API/tests, không yêu cầu CI mới.
- [Spec](tasks/M1/M1-14.md), [report](../docs/reviews/M1-14-evaluation.md).
- Next action: **Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2 hoặc web demo.**
