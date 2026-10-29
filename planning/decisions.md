# Quyết định và điểm cần làm rõ

## 2026-10-29 — M3 Preflight: Research Alignment

- Theo chỉ đạo Tech Lead, định hướng M3 là **Typed Executable Financial Evidence
  Graph with Semantic Compatibility and Evidence-Quality Propagation**. Đây là
  hướng nghiên cứu, chưa chứng minh novelty/SOTA hoặc hiệu quả thực nghiệm.
- Giữ Offline → Online → Output và `SourceFact → DerivedMetric → Claim → VerificationRecord`.
  M3 biểu diễn SourceFact/CanonicalFinancialFact, EvidenceAnchor, TextEvidence/TableEvidence,
  typed relations, DerivedMetric, lineage và retrieval. Claim thuộc M5/M6;
  không triển khai Claim/VerificationRecord/Verified Claim Ledger tại M3.
- M3-01 thiết kế compatibility của financial item, reporting period, reporting scope,
  unit/scale, document/source identity và formula operand roles theo quy tắc được duyệt.
  Không tự suy quy tắc kế toán; chi tiết types/rules TBD.
- M3-06 thiết kế quality propagation contract, giữ bốn task-aware decisions của M2,
  unresolved provenance, missing operands và reasons có nguồn. Không thêm enum hay
  đặt confidence score, thresholds, propagation algorithm trước thiết kế/thực nghiệm.
  Source grounding và numerical calculation validity không thay claim verification.
- M4 sở hữu deterministic execution tools và baseline đã đăng ký; M5 planner/specialists;
  M6 verification/ledger; M7 grounded QA/report; M8 controlled evaluation/ablation.
  M3 retrieval chuẩn bị evidence cho đánh giá, không tự chạy benchmark.
- Giữ nguyên M3-01–M3-07, IDs/dependencies/TODO, chưa bắt đầu M3-01; không task mới.
  Không chọn graph/vector database, không thêm agents/frontend hoặc đổi runtime/schema.
  Caveats và evidence M1/M2/W-07 giữ nguyên; không chứng nhận financial accuracy mới.
- Phạm vi/criteria dự kiến tại [roadmap](roadmap.md#m3); semantics tại
  [architecture](../docs/architecture.md#định-hướng-m3--typed-executable-financial-evidence-graph).
  Preflight dừng REVIEW, chờ Tech Lead nghiệm thu PR.

## 2026-10-27 — M1-11a Final Acceptance

- Tech Lead APPROVED sau review implementation `063bd2935a47832d928a6869ea35a2bd0cf6f9f2`,
  source/tests/evidence và [CI 40505711042](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40505711042);
  cho phép REVIEW → DONE. Python 3.11/3.12 mỗi job 1130 passed/11 skipped.
- Trước acceptance, HEAD/origin khớp `ad2a1664faa33f54ccc90e4a0cbace41ab48fbc7`,
  working tree sạch; [CI 40506143468](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40506143468)
  success exact SHA 3.11/3.12 được đối chiếu lại.
- Giữ nguyên live: 6 requests, 5 real pages, 0 resolved/5 unresolved,
  12307 input/176 output/12483 total tokens, cache HIT 5/checkpoint HIT 0.
  Không chạy lại Gemini; không biến nghiệm thu engineering thành financial accuracy.
- Hai follow-up chỉ ghi nhận, chờ Tech Lead giao việc riêng:
  đánh giá lại OCR quality gate; loại bỏ giới hạn 20.000 input tokens tùy ý ở pilot tiếp theo.
  Không sửa gate/token cap hiện tại trong acceptance hoặc tự tạo/bắt đầu task mới.
- Chỉ 7 docs/planning files; code/tests/contracts/API keys/runtime artifacts bất biến.
  Local Ruff/planning/diff; không full local unit suite/API. Acceptance SHA/CI kiểm tra
  riêng sau push và báo cuối. [Evidence](../docs/reviews/M1-11a-evidence.md).
- M1-12 TODO; chờ Tech Lead giao việc, không tự bắt đầu M1-12 hoặc task khác.

## 2026-10-27 — M1-11a bounded classification pilot

- User giao M1-11a, cho phép code/tests/live/commit/push, dừng REVIEW; M1-11 DONE,
  không bắt đầu M1-12. User xác nhận data export/free tier/quota applicability/no other apps.
- Chọn duy nhất first key; một client và opaque project/account aliases bind selected
  credential theo owner attestation, không suy Google project ID hoặc quota remaining.
  Không rotation/retry; Google Standard free tariff đối chiếu, cap USD 0 conditional
  user-confirmed free tier; actual billing unknown, guard money NOT_CONFIGURED công khai.
- Freeze 19 pages từ verified M1-04b pool, exact artifact locators + source snapshots;
  không tạo OCR run identity, không sửa raw/contracts/classifier M1-11.
- Live 6 requests (smoke +5 real pages), 12307 input/176 output/12483 total tokens;
  0 resolved/5 unresolved, 5 cache probes HIT, 0 checkpoint HIT. Dừng pre-send local token
  reservation, không dùng hết cap bằng cách truncate hoặc nới policy. No provider/schema errors.
- Sửa riêng runner metrics: local token denial tách provider failure/completed pages;
  original private live report giữ nguyên + interpretation riêng, regression test,
  không gọi lại API. [Evidence](../docs/reviews/M1-11a-evidence.md).
- Taxonomy provisional, text-only gate bảo thủ; live actual subset 1 symbol/5 years,
  không ground truth/accuracy/financial readiness; Tech Lead quyết định trước M1-12.
- Implementation `063bd2935a47832d928a6869ea35a2bd0cf6f9f2` /
  [CI 40505711042](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40505711042)
  success exact SHA, 1130 passed/11 skipped mỗi Python 3.11/3.12. Dừng REVIEW,
  Tech Lead nghiệm thu độc lập; không tự chuyển DONE/M1-12.

## 2026-10-27 — M1-11 Final Acceptance

- Tech Lead APPROVED ngày 27/10/2026 sau review implementation
  `e8e757fe7b9f2d1cd1af75f3eb4c026e8fca86c5`, tests và
  [CI 40500929151](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40500929151);
  không blocking issues trong engineering scope. Cho phép REVIEW → DONE.
- Review checkpoint `7a3614559e2542414166d78e300507d533b84217` /
  [CI 40501298126](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40501298126)
  success exact SHA; jobs và mọi steps Python 3.11/3.12 kiểm tra lại trước acceptance.
  Giữ evidence 35 focused + 333 related regression passed; CI mỗi job 1113 passed/11 skipped.
- Nghiệm thu engineering không phê duyệt taxonomy kế toán: B01/B02/B03/B09 vẫn là
  candidates opt-in, taxonomy chính thức TBD. Text-only evidence gate bảo thủ;
  không financial accuracy/acceptance. Live Gemini chưa verified, **0 requests**;
  selected credential/project mapping/active quota/budget vẫn chưa xác nhận.
- Chỉ 7 docs/planning files; production code/tests/contracts/API keys bất biến,
  không full local unit suite hoặc live API. [Evidence](../docs/reviews/M1-11-evidence.md).
- Acceptance SHA/CI kiểm tra riêng sau push và báo cuối. M1-12 TODO;
  chờ Tech Lead giao việc, không tự bắt đầu task mới.

## 2026-10-27 — M1-10 Final Acceptance

- Tech Lead APPROVED ngày 27/10/2026 sau review source/tests/evidence và CI 40497588383
  trên implementation 796e4664e6faf1d32354f7db62770bb7e4e1304e; không blocking issues.
- Cho phép REVIEW → DONE và commit/push acceptance; chỉ 7 docs/planning files,
  không thay production code/tests/contracts/dữ liệu, không rerun full local suite/API.
- Review checkpoint 21f1834a4d765da7fab2293f42abba8b4d0ca7c3 /
  [CI 40497942861](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40497942861)
  success exact SHA; mọi steps Python 3.11/3.12 verified. Giữ bằng chứng 38 checkpoint
  + 246 regression passed; implementation CI mỗi job 1078 passed/11 skipped.
- Giữ nguyên limitations trusted filesystem/single writer, một revision/slot, không
  distributed locking/eviction/history/size cap/absolute crash durability. Caller chịu
  source binding/content fingerprints/semantic validation; checksum không chứng nhận
  OCR/financial correctness. [Evidence](../docs/reviews/M1-10-evidence.md).
- Acceptance SHA/CI xác minh riêng sau push và báo cuối, không tự tham chiếu hoặc suy CI cũ.
  M1-11 TODO; chờ Tech Lead giao task tiếp theo, không tự bắt đầu implementation.

## 2026-10-27 — M1-10 checkpoint design

- User giao M1-10, cho phép code/tests/docs/commit/push, dừng REVIEW; không DONE/M1-11.
- Runtime API trong document_processing, tái sử dụng RawPageIdentity và DataConfig;
  không đổi serialized contracts, pipeline hoặc Gateway/cache/quota.
- Một JSON artifact/slot unit+stage, source_ref bind document/run do caller xác minh;
  page-level giữ đầy đủ identity/source_ref. Không dùng symbol/year/page làm global ID.
- Stable JSON SHA-256 cho input/config, processing version tường minh; checksum cả
  payload và metadata. Chỉ caller-confirmed verified output được publish.
- Temp cùng directory, flush/fsync/close rồi atomic replace; trusted filesystem,
  single writer/process. Root tách khỏi configured data/raw/processed/recovered sources.
- Không dataset thật/API/LLM; checksum/JSON structure không chứng nhận OCR/tài chính.
  Caller chịu đầy đủ input content digests, source binding và semantic validation.
  [Usage và giới hạn](../docs/document-processing-checkpoints.md).

## 2026-10-27 — Tech Lead Final Acceptance M1-05

- **Tech Lead APPROVED ngày 27/10/2026**, M1-05 REVIEW → DONE theo giao việc
  Finalize Acceptance; dependencies M1-02/M1-04 DONE.
- Nghiệm thu provider-neutral contracts và pure validation trong core, structured
  states/schema attestations, usage/cost, error taxonomy và serialization/schema v1.
- Implementation f6de33cb5855847985069ab78e2ada8596cc8cd2 / CI 40458339034 success;
  review checkpoint 7a54715369016a29ac886cf16b7480fd57ebc2f9 / CI 40458603189 success
  exact SHA, từng step Python 3.11/3.12 verified trước finalization.
- Giữ bằng chứng targeted 142 passed/zero skips, full local 910 passed/2 platform
  skips; CI mỗi job 901 passed/11 platform skips. Không coi skips là passed.
- Chỉ 7 docs/planning files trong phiên acceptance; không đổi code/tests/schema,
  không rerun local unit suite, không API/dataset/secrets hoặc task mới.
- Giữ limitations: attestation không chứng minh validator thực thi; secret safety
  không phải DLP; SDK/model/live policy/pricing/quota/budget/capabilities/cache TBD.
- Acceptance SHA/CI kiểm tra sau push, ghi báo cáo cuối để tránh tự tham chiếu.
  M1-06..09 TODO; chờ Tech Lead giao task tiếp theo, không tự bắt đầu M1-06.

## 2026-10-27 — M1-05 contract design

- Implementation f6de33cb5855847985069ab78e2ada8596cc8cd2 đã push, CI 40458339034
  success exact SHA/mọi steps Python 3.11/3.12; 901 passed/11 skipped mỗi job.
  Local 910 passed/2 skipped, targeted 142 passed/zero skips/warnings. Chuyển REVIEW,
  chờ Tech Lead nghiệm thu; final docs checkpoint chỉ tham chiếu implementation đã biết.

- User giao M1-05, cho phép commit/push và dừng REVIEW, không tự DONE.
- Core sở hữu module llm_contracts độc lập; giữ pipeline và contracts cũ.
- Provider/model IDs riêng; text-only messages, strict types/extra forbid; metadata
  có fields cố định. Không kwargs/SDK/credentials/account identities.
- Chỉ schema reference Draft 2020-12; parser JSON không nâng schema status.
  SchemaValidation là attestation có validator identity, không runtime validator.
- Unknown usage/cost khác zero; không suy total, money Decimal serialized string.
- Errors code/category cố định, provider error code allowlist; public parser
  bỏ raw input/context và che dynamic paths. Không tự redact secrets trong text.
- Version llm_gateway_v1, deterministic JSON/exclude_unset, schema drift test.
- Temperature upper bound và null/capabilities do adapter kiểm tra sau; không
  âm thầm bỏ parameter. SDK/model/live API/pricing/quota/budget/cache vẫn TBD.
- [Thiết kế và giới hạn](../docs/llm-gateway-contract.md),
  [task spec](tasks/M1/M1-05.md). M1-06..09 giữ TODO.

## 2026-10-27 — Tech Lead Final Acceptance M1-04

- **M1-04 chính thức APPROVED**, REVIEW → DONE; M1-04a/M1-04b và M1-03 đã DONE.
- Validators đáp ứng contracts và giữ provenance; bounded pilot có frozen manifest
  và hai lượt deterministic, 472 selected snapshots unchanged theo local evidence.
- Final approval chỉ engineering scope; không chứng nhận OCR accuracy, financial
  correctness, table completeness hoặc dataset-wide readiness.
- Giữ 23 pages/398 refs (coverage 14/risk 9), 316 original/14 reconstructed/
  68 unrecovered. Năm human bbox issues vẫn requires_review, thiếu BCC/2025,
  original equivalence/run identity chưa xác minh; không ground truth/quality thresholds.
- Baseline ad39a946546b4ffc6bc73c7044caa55f6a357d7d / CI 40439654103 success
  exact SHA, mọi steps Python 3.11/3.12 verified. CI acceptance commit mới kiểm tra
  sau push, không tự tham chiếu SHA/CI hoặc suy run cũ cho commit mới.
- Finalization chỉ 7 docs/planning files, không code/tests/manifest/statistics/data,
  không rerun pilot/hash dataset/LLM/recovery. Không còn work của M1-04; chờ giao task.

## 2026-10-27 — M1-04 Aggregate Review, chờ Tech Lead xác nhận cuối

- Sau M1-04b DONE tại a0ffaaff317c046bebd023c9305b1303ddcf8451 / CI 40439127716
  success exact SHA, Software Engineer đối chiếu riêng 10 aggregate checks theo roadmap.
- M1-03/M1-04a/M1-04b DONE; source/tests/evidence/Git diff/CI cho thấy đủ bằng chứng
  engineering của parent trong phạm vi đã duyệt. [Aggregate report](../docs/reviews/M1-04-aggregate-evidence.md).
- Parent TODO → READY → IN_PROGRESS → REVIEW theo giao việc aggregate; không DONE,
  không tự suy approval của parent từ approvals hai task con. Tech Lead phải xác nhận cuối.
- Giữ mọi giới hạn: 5 bbox issues mở, thiếu BCC/2025, original equivalence/run identity
  unverified, không ground truth/OCR accuracy/financial correctness/table completeness.
- Chỉ docs/planning, không rerun/đọc/hash dataset hoặc đổi manifest/statistics/code;
  không M1-05/task khác. CI parent commit xác minh riêng sau push, không self-reference.

## 2026-10-27 — Tech Lead Final Acceptance M1-04b

- **M1-04b APPROVED**, REVIEW → DONE theo giao việc finalization mới.
- Nghiệm thu engineering protocol, provenance, implementation và repeatability;
  không chứng nhận OCR accuracy, financial correctness hoặc table completeness.
- Implementation 4a2a4ed4ae09924e073448029e884b030f61bc27 / CI 40437144971;
  checkpoint 7b0bc52dd44cded9bfb5cc0a668433c4ff9b9576 / CI 40437415893 success
  exact SHA; từng step Python 3.11/3.12 verified, mỗi job 759 passed/11 skipped.
- Giữ 23 pages/398 refs, 316 original/14 alternatives/68 unrecovered, hai lượt
  deterministic và 472 selected snapshots unchanged theo evidence đã được duyệt.
  Không rerun pilot hoặc sửa manifest/statistics/data/validators/contracts.
- Năm human bbox issues vẫn requires_review; thiếu BCC/2025, original equivalence/
  run identity chưa xác minh, không ground truth hoặc đánh giá accuracy tài chính/OCR.
- M1-04 giữ TODO ở checkpoint 1. Sau CI finalization success mới aggregate review;
  nếu đạt chỉ chuyển parent REVIEW, chờ Tech Lead xác nhận cuối; không M1-05.

## 2026-10-27 — Tech Lead Final Acceptance M1-04a

- **APPROVED — engineering scope, 2026-10-27** theo task M1-04b do user giao.
- REVIEW → DONE; implementation 32a3d23 / CI 40432840930 và checkpoint
  d782320 / CI 40433101346 success exact SHA, mọi steps Python 3.11/3.12 verified.
- Finalization riêng chỉ planning, không đổi code/tests/artifacts hoặc đóng 5 bbox issues.
- M1-04b đã được giao; chỉ bắt đầu sau finalization commit/push/exact-SHA CI.
  M1-04 cha vẫn TODO; M1-05 ngoài scope.

## 2026-10-27 — Tech Lead Final Acceptance M1-03f

- Tech Lead chính thức APPROVED: chuyển M1-03f REVIEW → DONE, nghiệm thu
  engineering cho 199 reconstructed table crops (12 pilot + 187 mới, 8 batches).
- Scope chỉ controlled bbox-faithful reconstruction; không chứng nhận OCR accuracy,
  table completeness hoặc original crop preprocessing/equivalence/Drive-run identity.
- 5 bbox issues sheets 02/03/08/11/12 vẫn unresolved, bàn giao M1-04a cùng index
  reconstructed_available. 85 non-table crops/288 views ngoài recovery; original
  OCR JSON và crop references giữ nguyên. Không sửa code/data/artifacts hoặc recovery thêm.
- Baseline 4902b1e28b00bdfead1839a71be96e35c0ca2980 / CI 40428602056 success đã đối chiếu;
  [evidence](../docs/reviews/M1-03f-evidence.md) giữ lịch sử và giới hạn. CI commit nghiệm thu
  được kiểm tra riêng sau push, không thêm commit chỉ để nhúng SHA/CI tự tham chiếu.
- Không đổi dependencies M1-03/M1-04. M1-04a/b vẫn TODO; chờ Tech Lead giao M1-04a.

## 2026-10-26 — Controlled table recovery expansion (M1-03f)

- M1-03e Tech Lead APPROVED/DONE, acceptance ca607debe2148ab2a52c25c78f142f181cf35674,
  CI 40345846471 success đúng SHA. M1-03 và dependencies M1-04 giữ nguyên.
- Expansion riêng table.crop, tổng <=199 và mỗi invocation <=24 PNG mới;
  default recover_crop cap 12 không đổi. Canonical recovery ID/sidecars giữ nguyên.
- Frozen plan bind inventory/mappings/snapshots/audit/candidates; human approval
  bind đúng 12 pilot IDs/hashes + plan_id. Không suy human approval từ pixel tests.
- Shared OS lock cho pilot/expansion; no-overwrite, failed batch stop và explicit
  clean-interruption resume. Source/output conflicts cần review, không tự xóa/sửa.
- Reconstructed index là alternative ngoài OCR JSON; chưa tích hợp M1-04a.
  Chỉ publish aggregate allowlists. Human review chưa có: dừng checkpoint A/B/C,
  không thực thi expansion và không chuyển REVIEW trước khi hoàn tất criteria.

## 2026-10-26 — Verified local pilot và public evidence (M1-03e)

- Tech Lead APPROVED M1-03d engineering/synthetic/zero-output; chuyển DONE, giữ
  M1-03 DONE, không thêm recovery tasks vào dependency task cha đã nghiệm thu.
- Người dùng cho phép kiểm chứng mapping local từ bản sao dataset Drive; không
  yêu cầu truy cập Drive hoặc tuyệt đối hóa OCR run identity. Exact source roots,
  suffix mã/năm/page, inventory độc lập với page metadata, containment, dimensions
  và positive/negative controls đủ cho bounded local pilot; fail closed từng trường
  hợp chưa đủ evidence. Không khẳng định original Drive byte identity.
- Reuse engine M1-03d, tối đa 12 table.crop, source roots read-only; mapping/image
  evidence và per-file provenance chỉ local. Không sửa versioned contracts.
- Từ M1-03e, task có kết quả local quan trọng cần báo cáo nghiệm thu đã loại bỏ
  dữ liệu nhạy cảm được commit lên GitHub. Chỉ aggregate/method/issues/tests;
  không source paths, Drive IDs, OCR/cell text, per-file hashes hoặc ảnh thật.
  Public exporter dùng allowlist numeric/boolean/enum, unknown values fail closed.
- Full real run xác minh 2 mappings/193 page bindings; 572 missing khớp baseline,
  199 table candidates; dry-run/recovered/rerun 12/12/12, nguồn không đổi. Không
  suy ra OCR/tài chính chính xác hoặc preprocessing equivalence; dừng REVIEW.

## 2026-10-26 — Missing Crop Audit & Bounded Recovery (M1-03d)

- M1-03c Tech Lead APPROVED, task cha M1-03 DONE; M1-03d độc lập dependency M1-03.
  Acceptance `5937b815135478ace1d0958ff7c2f31f2ae4cc51`, CI 40314189759 success.
- Audit manifest chọn đúng 193 trang; không full inventory. Source Colab roots/run
  còn TBD theo contract: không tự duyệt mapping. Tất cả 1.557 references unmapped,
  zero eligible/recovered; không biến unmapped thành missing hoặc ép bằng 572.
- Chỉ table.crop với approved image identity binding, matching dimensions/bbox;
  không suy đoán detection_view hoặc transformations. Color views unsupported.
- Pillow >=11,<13 cho PNG lossless; không dependency AI. Runtime audit records
  và manifests phụ trợ, không thêm public/versioned contract hoặc core whitelist.
- Default dry-run, output chỉ data/recovered_crops, exclusive PNG + hash sidecar,
  cap 12; trusted filesystem một writer, TOCTOU/aliases còn giới hạn. Chi tiết và
  kết quả thực tế ở [crop recovery](../docs/crop-recovery.md).

## 2026-10-26 — Read-Only OCR Data Loader (M1-03c)

- M1-03b Tech Lead APPROVED/DONE; acceptance `10eb4e9`, CI 40310998984 success.
- LoadedOCRPage frozen dataclass và OCRLoadError/code là runtime wrappers nội bộ,
  không đổi serialized contracts. Structural issues giữ paths/cause, quality riêng.
- Reuse resolver mới trước/sau read; bind root key, bounded O_RDONLY, fstat/lstat,
  O_NOFOLLOW/O_NONBLOCK khi có. Còn TOCTOU; không secure descriptor framework.
- Fingerprint dev/inode/size/mtime, POSIX thêm ctime; Windows ctime có semantics
  khác giữa lstat/fstat nên không dùng để so chéo.
- 32 MiB default hữu hạn chưa đo phù hợp corpus; đọc tối đa limit + 1 sentinel.
- UTF-8/BOM, reject duplicate JSON keys và NaN/Infinity constants; không sửa nguồn.
- Anchor kiểm tra exact symbol/year/page/image; không suy ra run identity.
- Đọc đúng 3 mẫu theo manifest, hash/metadata khớp; không scan hoặc benchmark.
  Chi tiết API/security/errors/verification ở [ocr-loader](../docs/ocr-loader.md).

## Các lựa chọn cho M0-01

| Nội dung | Quyết định | Cơ sở |
| --- | --- | --- |
| Phạm vi | Chỉ skeleton, môi trường và tài liệu | Yêu cầu M0-01 |
| Ngôn ngữ | Python 3.11+ | Yêu cầu M0-01 |
| Kiến trúc | Modular monolith, Offline → Online → Output | Yêu cầu M0-01 và báo cáo Chương 4–6 |
| LLM | Gateway dùng chung; hỗ trợ đổi model, structured outputs và chi phí | Yêu cầu M0-01; chưa triển khai |
| Đầu ra | QA và báo cáo chỉ dùng nhận định trong Verified Claim Ledger | Báo cáo Chương 4.5, 5.7 |
| Đóng gói | setuptools; distribution `vietnamese-financial-multi-agent`, namespace `vietnamese_financial_multi_agent` ánh xạ vào `src/` | Lựa chọn thiết lập M0-01, giữ cây thư mục yêu cầu và tránh import tên chung |
| Kiểm tra | Ruff cho lint/format; pytest cho smoke tests cài đặt/import | Lựa chọn thiết lập tối thiểu M0-01 |
| Dependencies | Không có runtime dependency; dev chỉ có Ruff và pytest | Không cài thư viện AI khi chưa cần |
| CI | Kiểm tra package thường, lint/format và unit tests trên Python 3.11/3.12 | Xác minh mức Python tối thiểu và bản có tại máy |
| Tài liệu | Tiếng Việt; identifiers/tên code bằng tiếng Anh | Quy tắc nhất quán trong M0-01 |
| Git | Nhánh `main`, repository private; dữ liệu hiện có và tài liệu gốc nằm ngoài tập commit | Yêu cầu M0-01 |

Các khoảng phiên bản dev nằm trong `pyproject.toml`; chưa có lockfile. Phiên bản
đã kiểm tra sẽ được ghi trong trạng thái task. Chính sách khóa dependency cho
thực nghiệm tái lập là `TBD` trước khi triển khai benchmark.

Đã kiểm tra GitHub của `VuongQuocAn`: chưa có repository đúng tên
`vietnamese-financial-multi-agent` tại thời điểm khởi tạo. Repository sẵn có
`Mutil_Agent_Financial_Report` là public, đã có triển khai theo kiến trúc C1–C5;
không phù hợp với yêu cầu skeleton private và pipeline mới của M0-01. Giữ nguyên
repository đó, tạo repository private theo đúng tên được yêu cầu.

## Các vấn đề TBD

- Schema dữ liệu, provenance, facts, EF-EG, claim, ledger và versioning contracts.
- Backend lưu trữ, engine đồ thị, framework API, công cụ OCR và thư viện điều phối.
- SDK Gateway, Gemini model, nhà cung cấp bổ sung, hạn mức và cấu hình chi phí.
- Quy tắc kế toán, bảng ánh xạ, dung sai số học và điều kiện kiểm chứng chi tiết.
- Dataset chính thức, quyền sử dụng, manifest, chia tập và quy trình chú giải.
- Ngưỡng đánh giá, ngân sách thực nghiệm và baseline chốt triển khai.
- Phạm vi tuân thủ quy định: tên đề tài trong M0-01 có nội dung này, trong khi
  Chương 1 của báo cáo giữa kỳ nói kiểm tra tuân thủ pháp lý không thuộc phạm vi
  nghiên cứu chính. Giữ tên đề tài theo yêu cầu mới nhất; chưa tự chọn văn bản
  pháp luật, luật kiểm tra hay module tuân thủ cho đến khi phạm vi được làm rõ.

Không dùng danh sách công nghệ được đề xuất trong báo cáo như quyết định đã
được duyệt. Không tự mở rộng phạm vi trong task khởi tạo.

## 2026-10-26 — Tracking và handoff (M0-04)

- Master Task Registry là nguồn trạng thái chính; chỉ dùng sáu states đã quy
  định. Dashboard và metadata trong spec/handoff phải đồng bộ với registry.
- Task IDs bất biến. Giữ scope/ID M1-01..04 từ M0-03; M1-02/03/04 làm task cha
  nghiệm thu, chia phần nhỏ bằng hậu tố thay vì đánh số lại. Task mới khác dùng
  số tiếp theo, không tái sử dụng IDs.
- Có 72 task đã đăng ký, gồm ba task cha. Số đếm không phải ước lượng khối lượng
  hoặc phần trăm nghiên cứu; implementation/benchmark chưa có số đo thì N/A.
- Chỉ tạo spec đầy đủ cho M0-04 và task M1-01 có inputs/criteria rõ. Backlog xa
  dùng mô tả ngắn trong roadmap; trước READY cần spec riêng và xem xét chia M/L.
- Validator Python standard library kiểm tra IDs, dependency cycles, states,
  DONE evidence, dashboard, spec metadata và links; CI chạy cùng lint/unit tests.
  Script không đọc dataset, gọi API hoặc chọn công nghệ nghiệp vụ.
- Resume đọc bốn tài liệu nhỏ (AGENTS/current-status/handoff/active spec), xác
  minh Git rồi chỉ mở tài liệu liên quan. Ghi checkpoint sau phần độc lập đã
  kiểm thử; không suy đoán luôn kịp bàn giao khi quota hết.
- DONE/publication được ghi sau nghiệm thu với SHA đã biết; bản ghi status có
  thể đi ở commit tiếp theo để tránh ghi SHA tự tham chiếu hoặc claim push trước
  khi thực tế push. Run CI luôn gắn với commit cụ thể, không suy ra cho commit mới.

Đây là quyết định quản lý công việc, không đổi Modular Monolith, pipeline,
module boundaries, contracts hoặc đóng góp nghiên cứu. Framework/model/storage,
schema kế toán và phạm vi pháp lý vẫn TBD như phần trên.

## 2026-10-26 — Document Understanding v1 (M1-02b)

- Output ứng dụng sở hữu dùng strict/extra forbid; unknown fields gây structural
  error giữ payload, khác chính sách bảo toàn raw extra allow.
- Page-level result; anchors mang identity và ngữ cảnh element/table/cell/line.
  source_ref caller cung cấp nếu biết run/artifact; không giả định global uniqueness.
- Bbox observed/proposed riêng, pixel ảnh gốc; image-only anchor còn chưa xác minh.
- Optional spans không default 1; export exclude_unset phân biệt missing/null/value.
- Classification vocabulary mở, null = chưa biết; không thêm taxonomy/logic kế toán.
- Quality validation riêng, raw comparison tường minh trong bộ nhớ; không sửa dữ liệu.
- Global run binding, taxonomy, migration và header relationships còn TBD.
Chi tiết fields, status semantics và giới hạn ở [data contracts](../docs/data-contracts.md).

## 2026-10-26 — Path Mapping v1 (M1-02c)

- Root config là explicit approved source root + path style + category + logical
  destination root key. Runtime M1-03a/b bind key, không hardcode local paths.
- So root theo components, exact case, giữ source string nguyên văn. Suffix dùng
  `/` để biểu diễn components độc lập host. Không marker search/basename fallback.
- Nhiều rules cùng category khớp đều ambiguous, kể cả nested roots hoặc cùng đích;
  không ưu tiên theo thứ tự. Config lỗi/duplicate IDs làm request unsafe.
- Policy portable fail closed cho traversal, separator lẫn, encoding, stream/device
  syntax. Lexical checks không chứng minh containment qua symlink/junction.
- Helper chỉ sinh not_checked/unsafe/unmapped/ambiguous. Runtime resolved/missing
  cần evidence tường minh và quality/status validation; không xác minh file content.
- Strict structural parsing tách quality validation; giữ payload lỗi và missing/null.
  PathReference tái sử dụng SourceAnchor, không sửa Raw OCR/Understanding models.
- Runtime policy, root/run identity, migration và recovery vẫn TBD. Không đăng ký
  M1-03d hoặc triển khai runtime ở task contracts.

## 2026-10-26 — Central Data Configuration (M1-03a)

- M1-02c Tech Lead APPROVED; task cha M1-02 DONE sau đối chiếu ba contracts,
  không chỉ dựa vào dependencies. Phase 1 355bec4/CI 40304977048 đã xác minh.
- Dùng bốn environment keys hiện hữu, không suy ra từ các biến thư mục cha.
  FINANCIAL_REPORT_DIR/FINANCIAL_OCR_DIR bắt buộc; NORMALIZED_DATA_DIR và
  CANONICAL_DATA_DIR optional vì chưa triển khai output stages. Key cung cấp rỗng
  luôn lỗi; lookup unconfigured không fallback. Chưa cần samples key.
- Source checkout default base từ module/markers; wheel cần base tuyệt đối
  tường minh. Không lấy CWD, đọc .env hoặc expand environment/home trong path.
- Chỉ native runtime paths, foreign styles bị từ chối; metadata vẫn ở Path Mapping.
  Root lookup trả Path, không nối suffix hoặc filesystem I/O. Core không import contracts.
- Frozen strict Pydantic, whitelist cố định; lexical overlap guard tách outputs
  khỏi inputs/outputs khác. Không stat dataset, không mkdir hoặc giải quyết symlink.
  Runtime containment/existence/access/race, source identity vẫn TBD cho M1-03b/c.

## 2026-10-26 — Read-Only Path Resolver (M1-03b)

- M1-03a Tech Lead APPROVED/DONE; acceptance 3d700a5, CI 40306938717 success.
- document_processing.resolve_path dùng lexical helper + get_root và result v1;
  không đổi contracts/core, local path không thêm field vào output.
- Chặn mọi symlink/reparse point qua lstat, kể cả root ancestors và link trong root;
  resolve component containment vẫn thực hiện. Không secure-open API.
- Roots overlap không làm đổi binding; shared_root_identity là issue thông tin
  khi samefile trùng, không chứng minh source/run identity.
- Missing chỉ khi selected root tồn tại, containment verified; filesystem errors
  unsafe/permission_denied hoặc filesystem_error, không che thành missing.
- Regular file + PNG/JSON structural extension + os.access metadata; không mở nội
  dung. Loader sau xử lý lỗi đọc/content và kiểm tra lại tại thời điểm dùng.
- TOCTOU, ACL/aliases/mounts/short names còn giới hạn; chi tiết ở
  [runtime policy](../docs/path-resolver.md). Không recovery, API/OCR/dataset scan.

## 2026-10-27 — M1-08 Acceptance

- User nghiệm thu M1-08 REVIEW → DONE, cho phép commit/push finalization.
- Implementation f895d74ca4267abc6b3c740419890d800437dd76 /
  [CI 40466483190](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40466483190)
  success exact SHA, mọi steps Python 3.11/3.12 verified; mỗi job 1006 passed/11 skipped.
- Giữ limitations của guard đã nghiệm thu; chỉ docs/planning, không production code
  hoặc live Gemini tests. CI acceptance xác minh riêng sau push và báo cuối.
- M1-09 vẫn TODO, chờ giao việc; không tự triển khai.

## 2026-10-27 — M1-09 Acceptance

- Tech Lead APPROVED M1-09, cho phép chuyển REVIEW → DONE và commit/push acceptance.
- Implementation afb866f760fea63cb3a960d3056a6909139b6294 /
  [CI 40468254692](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40468254692) success exact SHA;
  mọi steps Python 3.11/3.12 đạt, mỗi job 1040 passed/11 skipped.
- Review checkpoint 389e4c86bef7cf176cc7a34fd3a425b5e82b4e77 /
  [CI 40468492757](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40468492757) success exact SHA, mọi steps 3.11/3.12 đạt.
- Chỉ cập nhật 7 docs/planning files; không sửa production code hoặc bổ sung tests,
  không chạy lại live Gemini API. Giữ nguyên limitations cache đã nghiệm thu.
- CI acceptance xác minh riêng exact SHA sau push và báo cuối.
- M1-10/M1-11 vẫn TODO; chờ Tech Lead giao task tiếp theo.

## 2026-10-27 — M1-11b Quality Gate và Pilot REVIEW

- Evidence-aware quality scope gồm selected và code/title candidates toàn trang;
  identity/reference/unknown giữ fail closed. Không sửa raw/provenance/contracts.
- Policy fingerprint riêng làm verified checkpoints STALE; compatible prediction cache
  revalidate current gate. Không giả persisted cache từ báo cáo M1-11a.
- Total token budget optional/off mặc định; giữ per-request100000+output512,
  quota guard và max20 requests/RPM5, không retry/rotation/truncate.
- 19 pages/20 requests, 9 resolved/10 insufficient; cùng5 trang cũ 0/5 →4/1.
  Chỉ operational improvement, không financial accuracy; [evidence](../docs/reviews/M1-11b-evidence.md).
- Dừng REVIEW chờ Tech Lead; không tự DONE hoặc bắt đầu M1-12.

## 2026-10-27 — M1-11b Final Acceptance

- Tech Lead APPROVED M1-11b, cho phép REVIEW → DONE; đồng bộ 7 docs/planning files.
- Review checkpoint `07b6a311b7d2183794a7ec0dbbd9c645b665a325` sạch/khớp origin sau fetch;
  [CI 40510853544](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40510853544) success exact SHA đã xác minh.
- Giữ nguyên pilot 19 trang/20 requests/9 resolved/10 unresolved/48847 input tokens.
  10 insufficient, taxonomy provisional, chưa ground truth/accuracy vẫn là limitations.
- Không đổi code/tests/contracts, credentials hoặc runtime artifacts; không Gemini API
  hoặc full local test rerun. Local acceptance: Ruff lint/format/planning/diff.
- Acceptance SHA/CI xác minh riêng sau push và báo cuối.
- Next action: Chờ Tech Lead giao task; không tự bắt đầu M1-12.
