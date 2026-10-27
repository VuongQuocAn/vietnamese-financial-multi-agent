# M1-10 — Engineering evidence

Ngày 2026-10-27 (Asia/Bangkok). **REVIEW**, chưa Tech Lead nghiệm thu; không DONE/M1-11.

## Implementation

- Baseline a130e72f5271c4c9b6f016e039d5e609ad1d7546, main/origin sạch sau fetch;
  dependencies M1-03/M1-02b/M1-09 DONE, không implementation task khác active.
- Implementation **796e4664e6faf1d32354f7db62770bb7e4e1304e**, đã push main/origin khớp.
- `CheckpointStore.lookup/save_verified`, ProcessingUnit/CheckpointRequest/fingerprint_json;
  một JSON unit/stage, request revisions, verified flag, result + artifact SHA-256.
- Source/run/page identity tường minh, content/config/version mismatch không HIT;
  strict JSON/metadata/digests, temp/write/flush/fsync/close/replace, reopen/restart.
- Tái sử dụng DataConfig/RawPageIdentity và DU v1 serializer/validator; serialized contracts
  và các module Gateway/cache/quota bất biến. Không API/dataset thật hoặc source writes.

## Local verification

- 38 checkpoint tests passed; 246 regression DU v1/DataConfig/OCR loader passed.
  Lệnh focused: `python -m pytest tests/unit/test_checkpoints.py -q`.
  Regression: `python -m pytest tests/unit/test_document_understanding.py tests/unit/test_data_config.py tests/unit/test_ocr_loader.py -q`.
- Coverage chính: interpreter subprocess restart, Unicode/numeric text/JSON null,
  document/page/source/stage isolation, input/config/version stale, missing/invalid
  fingerprints, corrupt/incompatible/incomplete metadata/payload, orphan temp,
  write/fsync/replace failures giữ old artifact hoặc MISS, cleanup, read errors,
  protected source roots và synthetic source bytes/mtime bất biến.
- Synthetic integration DU v1: parse/quality validation/export/save/lookup/parse,
  giữ anchors/source_ref/bbox/text và omitted/null; không đánh giá OCR/tài chính.
- Ruff lint/format 126 files, planning checker 75 tasks, diff check PASS.
- Kiểm tra ignore/index/staged allowlist: checkpoints/ bị ignore; không raw/dataset/
  ảnh/PDF/.env/secrets trong tập commit. Không chạy full local suite hoặc benchmark.

## CI exact implementation SHA

[Run 40497588383](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40497588383)
completed/success, headSha **796e4664e6faf1d32354f7db62770bb7e4e1304e**.

| Job | Job ID | Steps | Unit suite |
| --- | --- | --- | --- |
| Python 3.11 | 122166848656 | Mọi steps success | 1078 passed, 11 skipped |
| Python 3.12 | 122166848360 | Mọi steps success | 1078 passed, 11 skipped |

Đã xem jobs/steps thực tế và unit log summary bằng gh run view/watch; không suy từ
commit status. Checkout/setup/install/lint/format/planning/tests/post steps đều success.
Review publication chỉ docs/planning; exact SHA/CI mới kiểm tra sau push và báo cuối,
không dùng CI cũ để chứng nhận HEAD mới hoặc tạo commit tự tham chiếu.

## Limitations và handoff

Trusted local filesystem/single writer, một revision/slot; không distributed locking,
eviction/history/size cap hoặc absolute crash durability. Caller xác minh source/run,
hash đủ input/image/crop contents, effective config và implementation version, xác nhận
semantic validation trước `verified=True`. JSON/checksum không chứng minh OCR/financial
correctness và không thay Verified Claim Ledger. [Usage](../document-processing-checkpoints.md).

Không blocker engineering. Next action: **Chờ Tech Lead review M1-10.**
