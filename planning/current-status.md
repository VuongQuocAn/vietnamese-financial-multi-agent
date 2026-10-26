# Trạng thái hiện tại

Cập nhật **2026-10-26** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- M1-03a/b/c, M1-03 và M1-03d DONE theo Tech Lead APPROVED.
- Acceptance M1-03d `1e7fe344c4991b99127448a5180bdcb4470c9a60`, remote khớp;
  CI 40340730395 success đúng SHA/mọi steps Python 3.11/3.12.
- M1-03e IN_PROGRESS: checkpoints A/B/C hoàn tất, đang chuẩn bị D/publication.
- Hai exact local mappings verified; rejected/ambiguous 0; 1.178 positive controls
  trên 14 nhóm mã/năm mỗi prefix, 4 negative controls; 193 local page bindings.
- Audit đúng 193/193 trang, 1.557 references: existing 985, missing 572,
  unique/contextual missing 572/572; unmapped/unsafe/ambiguous 0, baseline khớp.
- Eligible table.crop 199; 288 unsupported views, 85 non-table requires_review.
- Dry-run 12/12; recovered 12, conflicts/failures 0. Reopen/pixels/hash/provenance
  12/12 đạt; rerun 12 already_recovered, output hash/metadata không đổi, cap 12.
- 193 JSON và 193 raw images hash/metadata trước/sau khớp; không ghi raw/processed.
- Full local Windows Python 3.12: 614 passed/13 skipped; Ruff lint/format 71 files,
  planning 74 tasks/pip check đạt. Synthetic tests không phải đánh giá tài chính.
- Full artifacts/bindings chỉ local bị ignore; chưa xác minh original Drive/run
  identity hoặc equivalence với preprocessing gốc. Không bắt đầu M1-04a/b.
- Next action: Xuất sanitized evidence và xác minh commit/push/CI M1-03e.
