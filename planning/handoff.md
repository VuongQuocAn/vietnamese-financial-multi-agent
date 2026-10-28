# Codex Handoff

## Active Task
M1-13a — Vision-Grounded OCR Correction & Structured OCR Pilot

## Status
REVIEW

## Last Verified State
Baseline main `10b626f` sạch; M1-13 DONE. User cho code/API/commit/push; dừng REVIEW.

## Completed Work
Optional inline PNG Gateway/adapter; verified image mapping/hash/dimensions;
vision correction dùng source gates cũ, effective_text giữ raw, không confirmed.
Structured OCR schema nhỏ, image-only prompt, nullable geometry/readings phân biệt;
full responses giữ riêng. Runner cũ thêm --vision, reuse guard/cache/meter.
Live2 pages/4 requests,22531 input/5975 output/28506 total tokens; failures0/unknown0.
Correction0; structured unresolved2 do columns/index mismatch. SDK nhận đúng PNG
bytes/hash; frozen raw/image/manifest bất biến. Không API rerun/retry/rotation.

## Remaining Work
CI exact implementation SHA sau push; Tech Lead nghiệm thu limitations và implementation.
Không sửa kết quả model cho đẹp, không tự DONE/M1-14.

## Modified Files
Gateway contracts/adapter/schema; correction/meter/vision module; runner/tests;
Gateway/adapter docs và evidence M1-13a; registry/spec/dashboard/current-status/handoff.

## Tests
219 focused/related tests passed, gồm9 mới +11 correction cũ; final focused9 sau cleanup.
Ruff lint/format, planning checker, diff check; runner dry-run cả hai modes đạt.
Không full suite local. CI hiện có Python3.11/3.12, không workflow mới.

## Blockers
Không independent verifier/ground truth; vision bỏ sót hai lỗi chữ đã biết.
Structured có text/tables/cells nhưng invalid indices cả hai trang, bbox sai scale/axes;
không coi output là raw OCR hợp lệ hoặc số tài chính được xác nhận.
Quota owner-attested15/250000/500, money NOT_CONFIGURED, không chứng nhận billing.

## Git Checkpoint
Baseline `10b626f`; một implementation commit/push; exact SHA và CI kết quả bàn giao
cuối phiên. Không publication commit. Artifacts ignored `artifacts/ocr-correction/M1-13a/`.
[Spec](tasks/M1/M1-13a.md), [evidence](../docs/reviews/M1-13a-evidence.md).

## Exact Next Action
Tech Lead nghiệm thu implementation và limitations pilot; không tự DONE/M1-14.
