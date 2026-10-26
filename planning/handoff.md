# Codex Handoff

## Active Task

M1-03f — Controlled Table Crop Recovery Expansion.

## Status

BLOCKED

## Last Verified State

M1-03e Tech Lead APPROVED/DONE; acceptance ca607debe2148ab2a52c25c78f142f181cf35674,
remote khớp, CI 40345846471 success mọi steps Python 3.11/3.12.
M1-03 giữ DONE; dependencies M1-03/M1-04 không đổi.

## Completed Work

Coordinator/CLI/review sheets. Default dry-run/cap 12; expansion cap 199,
batch tối đa 24; frozen plan/approval exact IDs/hashes, OS single-writer lock,
exclusive outputs, conflict/failed-batch stop và clean resume.
Re-audit 193 trang: 1.557 references, existing original 985/missing original 572,
eligible 199; reconstructed_available 12/missing_unrecovered 187; conflicts 0.
12 pilot PNG/sidecars/pixels/dimensions/hash/IDs đã kiểm tra. Source snapshots
193 JSON + 193 raw images giữ nguyên. Không thực thi expansion.
12 contact sheets, review manifest, pending approval template và recovery index local.

## Remaining Work

Human review 12 sheets và approval local còn thiếu.
Chỉ sau approval hợp lệ mới execute từng batch <=24, validate/reconcile,
cập nhật evidence và chuyển REVIEW. Không bắt đầu M1-04a/b.

## Modified Files

crop_recovery.py, crop_expansion.py, crop_review.py, crop_evidence.py;
scripts expand_table_crop_recovery/create_crop_review_sheet/export_crop_evidence;
unit tests, crop-recovery docs, evidence M1-03f và planning.
Local sheets: artifacts/crop-recovery/M1-03f/review/;
approval template: visual-review-approval.template.json trong thư mục task.
Toàn bộ artifacts/data bị ignore; không commit PNG/private manifests.

## Tests

Baseline acceptance: 614 passed/13 skipped; Ruff/planning/pip đạt.
M1-03f full local: 655 passed/14 skipped; Ruff lint/format 79 files,
planning 75 tasks/pip check đạt. Expansion 35 passed/1 skipped, publication 19 passed.
Native junction/process-lock/clean-resume đạt; synthetic tests không đánh giá tài chính.
CI implementation Python 3.11/3.12: mỗi job 658 passed/11 skipped, mọi steps success;
đã kiểm tra exact SHA, jobs/steps và test logs. Pip check là local.

## Blockers

Chưa có human visual approval. Không tự điền approved/reviewer.
TOCTOU/aliases/hardlinks/trusted filesystem còn giới hạn; OS lock chỉ phối hợp
các CLI dùng chung lock. Failed batch/incomplete PNG-sidecar cần review, không xóa.
Original Drive/run identity và preprocessing equivalence unverified.

## Git Checkpoint

Stable acceptance ca607debe2148ab2a52c25c78f142f181cf35674, push/remote đã khớp;
[CI 40345846471](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40345846471)
success đúng SHA/mọi steps Python 3.11/3.12.
Stable implementation M1-03f `a91492e17a0644c8f9d7e4e655ba73dda26c79f0`,
push/remote khớp;
[CI 40349513656](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40349513656)
success đúng SHA/mọi steps Python 3.11/3.12, mỗi job 658 passed/11 skipped.
Metadata publication đi sau code; kiểm tra Git HEAD/remote/CI riêng khi resume.
Checkpoint local: plan.json, execution-plan-*.json, final-integrity.json,
recovery-index.jsonl và review/review-manifest.json trong thư mục artifacts task.
Sau khi người dùng review thực sự, tạo visual-review-approval.json đúng template;
giữ plan_id/reviewed/IDs/hashes, điền reviewer/time/verdict thật theo docs/crop-recovery.md.
Tái kiểm tra approval/source plan/full checks rồi execute từng batch <=24,
validate giữa các batch; không tự reset conflicts hoặc đổi approved plan.

## Exact Next Action

Người dùng xem 12 local review sheets và ghi approval thật khớp template.
