# Codex Handoff

## Active Task
M1-13b — Structured OCR Quality Improvement

## Status
REVIEW

## Last Verified State
Baseline main `97d8d7104074fa37121895dc53767320e3ea76cf` sạch; M1-13a DONE.
User cho implement/test/API/commit/push; dừng REVIEW, không M1-14.

## Completed Work
Text/cell/layout/geometry validation độc lập; provenance fail closed; v2 prompt/schema;
runner --structured-quality dùng lại Gateway/cache/quota và BED source-table crop.
Baseline replay API0 giữ45 texts/2 tables/32 cell texts; new55/0/41, cell layouts31.
Geometry unresolved96; không infer dimensions/rescale/đảo axes hoặc sửa tài chính.
BED10/10 số sample đúng ảnh (baseline6 ở cells,4 text); BCC header đúng, bỏ từ thừa.
Source/raw/images/baseline/manifest bất biến. Artifacts ignored M1-13b.

## Remaining Work
CI exact implementation SHA sau push; Tech Lead review limitations/implementation.
Không retry crop hoặc chạy thêm corpus/API để cải thiện kết quả.

## Modified Files
vision_ocr.py; runner hiện có; test_structured_components.py; registry/spec/dashboard/
current-status/handoff và evidence M1-13b. Không sửa shared Gateway/data contracts.

## Tests
8 focused mới +9 image integration cũ passed; Ruff changed files/planning/diff đạt.
Không hàng trăm regression local; CI sẵn có 3.11/3.12 kiểm tra sau push, không workflow mới.

## Blockers
3 attempts,2 successes +1 crop timeout; known2999 input/7060 output/10059 tokens;
usage timeout unknown1, actual aggregate chưa xác định, không retry/rotation.
Crops: BED bbox verified [345,547,2297,874] giữ pixels, nhưng không có model output;
BCC bbox cắt thiếu bảng nên skip. Layout tables mới0/4 valid, declared counts vẫn sai;
geometry model chưa đáng tin. accepted chỉ là cấu trúc, không visual/financial truth.
Không ground truth/accuracy toàn dataset. Quota owner-attested, money NOT_CONFIGURED.

## Git Checkpoint
Baseline `97d8d7104074fa37121895dc53767320e3ea76cf`; một implementation commit/push;
exact SHA/CI ghi trong bàn giao cuối, không publication commit.
[Spec](tasks/M1/M1-13b.md), [evidence](../docs/reviews/M1-13b-evidence.md).

## Exact Next Action
Tech Lead review implementation và limitations pilot; không tự DONE/M1-14.
