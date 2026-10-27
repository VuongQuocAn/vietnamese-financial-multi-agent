# Codex Handoff

## Active Task

M1-03f — Controlled Table Crop Recovery Expansion (chờ nghiệm thu).

## Status

REVIEW

## Last Verified State

2026-10-27: user/Tech Lead conditional approval đã ghi thật từ chat, validate gate
khớp template/plan/12 IDs-hashes. Full checks đạt trước expansion.
8 batches đã verify và final reconciliation đạt: 187 PNG mới, tổng 199 PNG/sidecars,
conflicts/failures 0/0. Fresh CLI verify trả 199 already_recovered, không tạo PNG mới.

## Completed Work

- Giữ nguyên template/reviewed IDs/hashes; approval chỉ bbox-faithful reconstruction.
- Ghi 5 source_bbox_incomplete_table issues cho sheets 02/03/08/11/12,
  requires_review tại M1-04a; không sửa bbox hoặc coi crop là bảng hoàn chỉnh.
- 7 × 24 + 19 ảnh mới, mỗi batch được kiểm tra source integrity và outputs;
  nguồn 193 JSON + 193 raw images hash/size/mtime/inode khớp frozen plan.
- Mọi output trước từng batch bất biến; 12 pilot PNG/sidecars/IDs/hashes giữ nguyên.
- 8 engine + 8 continuation receipts khớp, 187 IDs mới distinct đúng approved set.
- Final index 199 validated reconstructed_available, 0 pending eligible;
  original references vẫn existing 985/missing 572; non-table 85/views 288 ngoài scope.
- Sanitized evidence và allowlisted numeric/boolean statistics, không publish dữ liệu riêng.
- Dùng engine/coordinator đã có; không đổi production code, contracts hoặc task cha.

## Remaining Work

Commit/push publication và xác minh exact-SHA CI, ghi lại bằng chứng sau push.
Tech Lead nghiệm thu M1-03f. M1-04a/b chưa bắt đầu; 5 quality issues là input tương lai,
không phải bbox corrections đã thực hiện hoặc blocker engineering bị bỏ qua.

## Modified Files

docs/crop-recovery.md, docs/reviews/M1-03f-evidence.md, M1-03f-statistics.json;
planning/tasks/M1/M1-03f.md; planning/tasks.md, progress.md, current-status.md, handoff.md.
Artifacts/data đều ignore: visual-review-approval.json, visual-review-quality-issues.json,
approved-preflight-verification.json, continuation-*.started/finished.json,
engine batch checkpoints, recovery-index.jsonl, approved-expansion-final-integrity.json,
approved-final-summary.json và local helper scripts. Không stage chúng hoặc PNG/sidecars.
Không overwrite final-integrity.json checkpoint trước approval.

## Tests

Full local trước batch đầu: 655 passed/14 skipped, Ruff lint/format 79 files,
planning 75 tasks và pip check đạt. Native junction/process-lock tests đạt.
Mỗi batch: source snapshots/callbacks + frozen-plan re-audit, full output engine
inspection, independent rerun và prior-output snapshot comparison đều đạt.
Fresh final CLI verify đạt; private proof đối chiếu 199 index entries/PNG-sidecar
pairs, 8 checkpoint chains, 12 pilot IDs/hashes và 5 quality issues.
Synthetic tests không đánh giá chất lượng tài chính. Publication CI chờ push.

## Blockers

Không có execution conflict/failure. REVIEW chờ Tech Lead nghiệm thu cuối,
không phải human approval trước expansion còn thiếu.
Bbox coverage issues sheets 02/03/08/11/12 còn mở cho M1-04a.
Original Drive/run/preprocessing equivalence unverified. Trusted local FS,
TOCTOU/aliases/hardlinks và writers không dùng lock vẫn là giới hạn.

## Git Checkpoint

Stable implementation `a91492e17a0644c8f9d7e4e655ba73dda26c79f0`,
[CI 40349513656](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40349513656)
success đúng SHA Python 3.11/3.12 ở checkpoint trước approval.
Baseline publication `e6403a0a4601470f5f46c6d74eb3c9323e4eba62` fetch/remote khớp
trước commit continuation; không suy CI cũ cho publication mới.
Checkpoint local ổn định: approved-expansion-final-integrity.json; đủ 8 completed
batch/continuation receipts, không còn pending eligible. Không rerun execute;
nếu cần kiểm tra dùng --verify, không reset plan/conflicts hoặc overwrite nguồn.

## Exact Next Action

Tech Lead nghiệm thu M1-03f; không bắt đầu M1-04a/b.
