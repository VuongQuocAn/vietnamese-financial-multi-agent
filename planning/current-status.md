# Trạng thái hiện tại

Cập nhật **2026-10-27** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-04a IN_PROGRESS** theo task user giao, có quyền commit/push và dừng REVIEW.
  Dependencies M1-03/M1-03f DONE; M1-04/M1-04b TODO, không triển khai task khác.
- Baseline `895087deeb06801ff4c67f198f8b1392a7da59de`: working tree sạch,
  fetch/local/origin/main khớp; [CI 40430400703](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40430400703)
  success đúng SHA, mọi steps Python 3.11/3.12 đã kiểm tra.
- Checkpoints A–G hoàn tất theo [spec](tasks/M1/M1-04a.md): composition validators,
  JSON–ảnh/bounds, original/reconstructed availability, recovery index/sidecar/hash/
  pixels, human ledger preservation và reports có provenance an toàn.
- Full local: **728 passed/2 skipped**, targeted **61 passed**; Ruff lint/format
  **85 files**, planning **75 tasks**, pip check và git diff --check đạt.
  Skips: filesystem không phân biệt case và FIFO không hỗ trợ Windows.
- Bounded real smoke **5 pages/50 references**, 43 existing_original,
  7 reconstructed_available; 5 human bbox issues giữ requires_review, deterministic.
  Selected sources/output hashes+metadata và metadata 398 recovered files bất biến.
  [Evidence](../docs/reviews/M1-04a-evidence.md),
  [statistics](../docs/reviews/M1-04a-statistics.json),
  [API](../docs/extraction-validation.md).
- Không đổi contracts/schema, recovery engine hoặc source JSON/images/PNG/sidecars/
  ledger/index; không recovery execution/LLM/API. Private reports giữ ignored local.
- M1-03f DONE theo Tech Lead APPROVED: 199 reconstructed PNG/sidecars. 5 bbox
  issues sheets 02/03/08/11/12 chưa được sửa; original equivalence/run identity và
  table completeness chưa xác minh. Không ngoại suy smoke thành chất lượng tài chính.
- Exact next action: **Commit/push M1-04a, kiểm tra CI implementation exact SHA**.
