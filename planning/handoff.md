# Codex Handoff

## Active Task

M1-03d — Missing Crop Audit & Bounded Recovery.

## Status

DONE

## Last Verified State

Stable Phase 1 `5937b815135478ace1d0958ff7c2f31f2ae4cc51`, remote khớp;
CI 40314189759 success đúng SHA/từng step Python 3.11/3.12. M1-03c/M1-03 DONE.
Full local 575 passed/13 skipped; crop/security 57 passed/1 skipped Windows,
native junction đạt. Ruff 64 files, planning 73 tasks/pip check đạt. Stable implementation `6e30ba67fa6b3cf7dd8f6e74021c0dbbad9343a6`,
CI 40315855062 success Python 3.11/3.12, mỗi job 578 passed/10 skipped.

## Completed Work

Đăng ký task độc lập, không sửa dependency task cha hoặc M1-04. A: manifest
selection đúng 193 trang, read-only loader/resolver, provenance/dedup/status/
eligibility; B: bounded read PNG, bbox/image identity binding, dry-run,
exclusive PNG/hash-sidecar, cap/rerun/security tests. C zero-output pilot vì không
có approved source mappings/image identity bindings: eligible/recovered/conflicts 0.
Audit 1.557 references, 1.553 source strings; 773 review/784 unsupported views,
all unmapped. Missing counts chưa xác định, không đổi baseline 572. Đúng 193 OCR
JSON hash/metadata trước/sau khớp; không đọc ảnh nguồn hoặc quét crops.
Selection rerun zero, audit hash khớp; real output hash/dimensions/rerun N/A.
Sửa encoding PowerShell trong các bản ghi planning Phase 1/2 trước publication.

## Remaining Work

Tech Lead đã APPROVED M1-03d engineering/synthetic/zero-output. Chờ checkpoint CI
rồi đăng ký M1-03e theo task được giao; không bắt đầu M1-04a/b.

## Modified Files

src/document_processing/{crop_audit.py,crop_recovery.py}; scripts/audit_missing_crops.py;
tests/unit/test_crop_recovery.py; pyproject.toml (Pillow); docs/{crop-recovery.md,
dataset.md,data-contracts.md,ocr-data-discovery.md}; planning/{tasks.md,progress.md,
current-status.md,handoff.md,decisions.md,tasks/M1/M1-03c.md,tasks/M1/M1-03d.md}.
Local ignored artifacts/crop-recovery/{audit.jsonl,audit-summary.json,recovery.jsonl,
page-failures.jsonl,source-verification.json,pilot-summary.json}; không PNG mới.

## Tests

Full Windows Python 3.12: 575 passed/13 skipped; crop 57 passed/1 skipped do thiếu
quyền symlink; native junction đạt. Ruff lint/format 64 files đạt. Các skips khác
của loader/resolver: 10 symlink, case-insensitive filesystem, FIFO không hỗ trợ.
Planning 73 tasks/pip check đạt sau sửa encoding; không chạy lại suite đã đạt khi chỉ sửa docs.
Synthetic pixels/hash/cap/rerun không phải bằng chứng chất lượng OCR/tài chính.

## Technical Decisions

Pillow >=11,<13, local 12.3.0; reuse bounded read nội bộ loader thay secure-open
framework. Approved image_bindings caller xác nhận độc lập, không suy filename.
Root chỉ project data/recovered_crops, không đổi whitelist. PNG exclusive + sidecar,
reopen/dimensions/pixels/hash, không overwrite/xóa. Cap 12 với một writer.

## Blockers

Chưa có approved Colab/Drive source mappings/run/image bindings; zero-output
pilot theo trường hợp task cho phép. Không tự suy mapping từ discovery markers.
TOCTOU, aliases/hardlinks, concurrency/mounts còn giới hạn; trusted filesystem.
Không có ảnh thật nên output hash/dimensions/contact sheet và real rerun N/A.

## Git Checkpoint

Stable acceptance `5937b815135478ace1d0958ff7c2f31f2ae4cc51`, CI 40314189759 success.
Acceptance đầu `a16b0aa` fail handoff section, correction stable trên đạt.
Stable implementation `6e30ba67fa6b3cf7dd8f6e74021c0dbbad9343a6`, push/remote khớp;
[CI 40315855062](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40315855062)
success đúng SHA/từng step Python 3.11/3.12, 578 passed/10 skipped mỗi job.
Linux symlink đạt, native junction skip theo platform; Windows native junction đạt.
Bản ghi REVIEW đi sau stable implementation; CI mỗi commit phải tra đúng SHA,
không suy ra từ CI commit trước.

## Exact Next Action

Xác minh CI checkpoint acceptance rồi đăng ký M1-03e theo task được giao.
