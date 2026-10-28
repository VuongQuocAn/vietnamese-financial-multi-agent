# Codex Handoff

## Active Task
M1-13 — Evidence-Preserving OCR Correction; Research MVP Lean v3.

## Status
REVIEW

## Last Verified State
Baseline main `9e93606`, working tree sạch trước triển khai; M1-12a DONE.
User giao 28/10/2026, cho code/tests/Gemini/commit/push; dừng REVIEW, không M1-14.

## Completed Work
Full-page structured Gemini proposals, exact scoped source-ID/original validation,
DU v1 source anchors + source digest; output corrected view riêng, raw bất biến.
Các trạng thái proposed/confirmed/unresolved tách biệt. MVP không verifier độc lập,
không phát sinh confirmed; effective_text giữ raw, candidates chỉ ở proposed.
MeteredModels thêm configurable RPM, M1-13 dùng15; defaults cũ giữ nguyên.
Live2 pages/2 requests, 0 corrections/confirmed/unresolved; 17450 input/40 output/
17490 total tokens; failures0/unknown0, OCR snapshots và manifest bất biến.

## Remaining Work
Tech Lead nghiệm thu engineering scope và giới hạn hiệu quả pilot; không tự DONE.

## Modified Files
src/document_processing/ocr_correction.py; classification_pilot.py (RPM only);
scripts/run_ocr_correction_pilot.py; tests/unit/test_ocr_correction.py;
docs/reviews/M1-13-evidence.md; planning/tasks.md; tasks/M1/M1-13.md; handoff.md.
current-status.md/progress.md chỉ đồng bộ trạng thái/counts để planning checker đạt.

## Tests
11 focused +47 related regression passed; final focused11 passed sau source gate refinement.
Ruff changed files, planning checker, diff check trước commit. Không full local suite,
không cache/checkpoint/quota probes, không API rerun. CI pipeline hiện có chạy một lần
full unit Python3.11/3.12 trên exact implementation SHA sau push; conclusion/test summary
được báo trong bàn giao cuối, không full logs/publication commit cập nhật SHA.

## Blockers
Không independent verifier/ground truth; live model bỏ sót lỗi chữ BCC đã nhìn trên ảnh.
Không xác nhận correction nào hoặc accuracy. Owner-attested quota15/250000/500;
provider remaining/billing chưa independently verified, guard money NOT_CONFIGURED.
Đây là limitations để review, không tự mở rộng sang image verifier hoặc evaluation.

## Git Checkpoint
Implementation là commit chứa handoff/spec/evidence này; baseline `9e93606`.
Đọc `git log -1` và bàn giao cuối để lấy exact SHA/CI sau một commit/push.
Private artifacts ignored `artifacts/ocr-correction/M1-13/`; không commit dataset/keys.
[Spec](tasks/M1/M1-13.md), [evidence](../docs/reviews/M1-13-evidence.md).

## Exact Next Action
Tech Lead review M1-13 và CI exact implementation SHA trong bàn giao; không M1-14.
