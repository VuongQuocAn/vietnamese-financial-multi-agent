# M1-11 — Engineering Evidence

Cập nhật 2026-10-27 (Asia/Bangkok); **DONE — Tech Lead APPROVED** engineering scope.
Tech Lead review implementation/tests/CI, không blocking issues; cho phép REVIEW → DONE.

- Baseline HEAD/origin: `98abecb538a82fd6ffdf4db57b8dfff81899c278` đã fetch/đối chiếu.
- M1-04/07/08/09/10 DONE; M1-11 đã nghiệm thu, không implementation task active.
- PageClassifier, Prediction/local schema registry, aggregate_document; usage ở
  [page/document classification](../page-document-classification.md).
- Candidate labels B01/B02/B03/B09 opt-in; taxonomy chưa được duyệt chính thức.
  Text-only evidence gate bảo thủ; engineering approval không financial acceptance.
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
- Implementation **e8e757fe7b9f2d1cd1af75f3eb4c026e8fca86c5**, đã push origin/main.
- [CI 40500929151](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40500929151)
  success exact implementation SHA; đã kiểm tra headSha, cả hai jobs và **mọi steps**
  Python 3.11/3.12 success. Logs mỗi job **1113 passed/11 skipped**.
- Review checkpoint **7a3614559e2542414166d78e300507d533b84217** /
  [CI 40501298126](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40501298126)
  success exact SHA; jobs và mọi steps Python 3.11/3.12 kiểm tra lại trước acceptance.
- Acceptance chỉ 7 docs/planning files; local Ruff lint/format, planning/diff check;
  không rerun unit suite/live API, không thay code/tests/contracts/API keys.
- Acceptance SHA/CI kiểm tra riêng sau push và báo cuối; không suy CI cũ hoặc
  ghi commit tự tham chiếu. Các số liệu tests bên trên là evidence implementation.

Next action: Chờ Tech Lead giao việc; không tự bắt đầu M1-12.
