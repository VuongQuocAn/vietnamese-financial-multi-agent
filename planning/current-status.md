# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-12a REVIEW**, chờ Tech Lead; M1-12 DONE, M1-13 TODO.
- Assisted API tái sử dụng M1-12/DU v1/loader/Gateway/Adapter/guard/cache/checkpoints;
  full OCR evidence, structured JSON, source coverage/geometry gate; không raw mutation.
- Cùng 4 trang/8 bảng/310 cells: **deterministic1/7 →assisted2/6 resolved/unresolved**;
  318 source anchors checked, chỉ28 cells/30 anchors thuộc resolved tables.
- Live **7 requests**, 55620 input/17177 output/72797 total tokens, failures0/unknown0.
  Model gemini-3.5-flash-lite, text/layout mode; không retry/rotation, không total input cap.
- 4 invalid coverage (bỏ17 empty cells/lặp1 source ID), 1 unsupported merge, 1 gaps;
  giữ2265 original geometry conflicts unresolved. New resolved table có12 cells,
  8 bbox ngoài bbox table nhưng valid/trong page và local grid/layout đạt; warning giữ.
- Cache7/checkpoint1 probes; **offline checkpoint1/service0/API0**. 9 snapshots và
  manifest/raw provenance bất biến; không sửa M1-12 report hoặc mở rộng mẫu.
- **28 focused +233 regression =261 passed**; Ruff/planning/diff đạt.
  Không full local suite; full unit suite CI 3.11/3.12 đạt exact implementation SHA.
- Limitations: không ground truth/accuracy, source run caller-bound, text/layout only.
  Guard money NOT_CONFIGURED; billing/project ID/quota remaining chưa independently verified.
- Baseline HEAD/origin sạch `54d198e886fd41dcc8f9f84a26a40ed77b7a4088` trước triển khai;
  implementation `dbc1b0941cff2c863066eafffff6233912049017` đã push main;
  [CI 40607344930](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40607344930) success exact SHA, mọi steps 3.11/3.12 đạt.
  Checkpoint REVIEW chỉ docs/planning, SHA/CI kiểm tra riêng sau push.
- [Spec](tasks/M1/M1-12a.md), [usage](../docs/table-assistance.md),
  [evidence](../docs/reviews/M1-12a-evidence.md).
- Next action: **Tech Lead review M1-12a; không DONE/M1-13.**
