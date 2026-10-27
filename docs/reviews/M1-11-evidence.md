# M1-11 — Engineering Evidence

Cập nhật 2026-10-27 (Asia/Bangkok); đang implementation, chưa Tech Lead nghiệm thu.

- Baseline HEAD/origin: `98abecb538a82fd6ffdf4db57b8dfff81899c278` đã fetch/đối chiếu.
- M1-04/07/08/09/10 DONE trong registry; M1-11 là implementation task duy nhất.
- PageClassifier, Prediction/local schema registry, aggregate_document; usage ở
  [page/document classification](../page-document-classification.md).
- Candidate labels B01/B02/B03/B09 opt-in; accounting taxonomy approval TBD.
- Gateway/Gemini Adapter/guard/cache/CheckpointStore tái sử dụng, không sửa shared code.
- Source text/cell anchors + separate provenance; raw/contracts bất biến.
- Checkpoint verified chỉ sau explicit opt-in và evidence gate; HIT revalidation,
  input/config/prompt/schema/taxonomy/processing invalidation.
- Local targeted classification tests: **35 passed**, gồm disabled/overlap/ancillary conflict.
- Related regression: **333 passed** (DU/checkpoints/Gemini/Gateway/cache/guard/OCR loader).
- Ruff lint/format toàn repository đạt (132 files), planning checker 75 tasks và diff check đạt.
- Secret file tồn tại, thư mục ignored, index rỗng; `git log --all -- src/api/api_key`
  rỗng. Không mở nội dung keys, không secret/dataset trong changes.
- Live Gemini **0 requests**, success/failure N/A; actual usage/cost/quota **chưa biết**.
  Không credential được chọn/project mapping/active quota/budget xác nhận; không API probe.
  Model code chỉ đối chiếu [Google model docs](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
  không chứng minh live access. [Quota theo project](https://ai.google.dev/gemini-api/docs/rate-limits).
- Không dataset thật/financial accuracy/benchmark; synthetic tests chỉ engineering integration.
- Implementation SHA/CI: chờ commit/push và exact-SHA verification.

Next action: Commit/push M1-11 và xác minh exact-SHA CI trước REVIEW.
