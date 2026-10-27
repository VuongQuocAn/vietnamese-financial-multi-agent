# Trạng thái hiện tại

Cập nhật **2026-10-27** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-04b DONE**, Tech Lead APPROVED engineering protocol/provenance/implementation/
  repeatability. M1-04a và M1-03 DONE; M1-04 cha TODO tại checkpoint finalization.
- Baseline sạch/local/origin khớp: 7b0bc52dd44cded9bfb5cc0a668433c4ff9b9576 /
  [CI 40437415893](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40437415893)
  success exact SHA, mọi steps Python 3.11/3.12 verified.
- Implementation 4a2a4ed4ae09924e073448029e884b030f61bc27 /
  [CI 40437144971](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40437144971)
  success; mỗi job 759 passed/11 skipped.
- Evidence được duyệt giữ 23 pages/398 refs; coverage 14/331, risk 9/67;
  316 original/14 reconstructed/68 unrecovered, hai lượt deterministic,
  472 selected snapshots unchanged. [Evidence](../docs/reviews/M1-04b-evidence.md).
- Năm human bbox issues vẫn requires_review; thiếu BCC/2025, original equivalence/
  run identity chưa xác minh, không ground truth/OCR accuracy/financial evaluation.
- Phiên chỉ finalization docs/planning; không rerun pilot, đổi manifest/statistics hoặc code.
- Required local checks mới: 768 passed/2 skipped (case-insensitive FS/FIFO Windows);
  Ruff/planning/pip/diff đạt. CI finalization kiểm tra riêng sau push.
- Exact next action: **commit/push/check CI finalization M1-04b trước aggregate review M1-04**.
