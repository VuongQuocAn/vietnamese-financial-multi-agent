# Trạng thái hiện tại

Cập nhật **2026-10-27** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- M1-03a/b/c, M1-03, M1-03d/e giữ DONE; không đổi dependencies/task cha.
- **M1-03f REVIEW**, chờ Tech Lead nghiệm thu; không có active implementation task.
- User/Tech Lead approval thực tế đã ghi local từ template: chỉ bbox-faithful
  reconstruction, giữ nguyên 12 recovery IDs/hashes và approved plan.
- Sheets 02/03/08/11/12 có bbox chưa bao trọn bảng: 5 quality issues giữ riêng
  cho M1-04a, không sửa bbox hoặc coi crop là bảng hoàn chỉnh.
- 8 batch **7 × 24 + 19 = 187 PNG mới**, tổng **199 PNG + 199 sidecars**;
  **0 pending eligible**, conflicts/failures **0/0**.
- 193 OCR JSON + 193 raw images giữ nguyên hash/size/mtime/inode trước/sau từng
  batch và final reconciliation; mọi output cũ bất biến. 12 pilot IDs/hashes giữ nguyên.
- Fresh CLI verify: **199 already_recovered**, new_outputs 0, conflicts 0.
- Original existing/missing references vẫn **985/572**; original table.crop missing
  vẫn 199. Không xử lý 85 non-table crops và 288 processed/color views.
- Full pre-execution local checks: **655 passed/14 skipped**, Ruff **79 files**,
  planning **75 tasks**, pip check đạt. Không đổi production code.
- [Sanitized evidence](../docs/reviews/M1-03f-evidence.md) và fixed-allowlist
  statistics đã có; ảnh/approval/hashes/private manifests giữ local, Git ignore.
- Implementation ổn định `a91492e17a0644c8f9d7e4e655ba73dda26c79f0`;
  baseline publication `e6403a0a4601470f5f46c6d74eb3c9323e4eba62` fetch/remote khớp.
  Publication continuation đang chờ commit/push và exact-SHA CI.
- Original Drive/run identity, preprocessing equivalence và trusted filesystem
  limitations giữ nguyên; không gọi OCR/LLM/API dữ liệu hoặc benchmark tài chính.
- Exact next action: Tech Lead nghiệm thu M1-03f; không bắt đầu M1-04a/b.
