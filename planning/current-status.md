# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-13b REVIEW**; M1-13a DONE, M1-14 TODO. Baseline main `97d8d71` sạch.
- Component accepted = structure only; provenance mismatch rejected toàn bộ;
  text/cells giữ riêng khi layout/geometry lỗi, không sửa số/dimensions/bbox ngầm.
- Persisted replay API0:45 texts/2 tables/32 cell texts retained thay vì0/0/0.
  Hai bảng accepted cũ chỉ headers. OCR mới55/0/41; cell layouts31, geometry unresolved96.
- BED10/10 số mẫu khớp ảnh; baseline đã đúng nhưng4 số ở text rời. BCC giữ header đúng,
  bỏ từ thừa trước môi trường. Không accuracy toàn trang/dataset, không auto-confirm.
- Pilot3 attempts:full-page2 success, crop BED timeout1;10059 known tokens,
  usage crop unknown, tổng thực tế chưa xác định. Không retry/API rerun.
- Source/images/raw/baseline/manifest bất biến; private ignored artifacts M1-13b.
- 8 focused mới +9 image integration cũ passed; Ruff/planning/diff đạt. Một implementation
  commit/push; CI exact SHA kiểm tra sau push, không publication commit.
- [Spec](tasks/M1/M1-13b.md), [evidence](../docs/reviews/M1-13b-evidence.md).
- Next action: **Tech Lead review implementation và limitations pilot; không tự DONE/M1-14.**
