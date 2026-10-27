# Bounded classification pilot — M1-11b

CLI nhỏ, text-only, tái sử dụng M1-11 với evidence-aware gate M1-11b.
Không sửa taxonomy/contracts/OCR/crops/PDF; không scan dataset hoặc đánh giá accuracy.
Kết quả lịch sử M1-11a giữ nguyên ở evidence và artifacts riêng.

## Dry-run và selection

Trong môi trường `.[dev]`, cấu hình `FINANCIAL_REPORT_DIR`/`FINANCIAL_OCR_DIR`
theo [data config](dataset.md), rồi chạy:

```powershell
python scripts/run_classification_pilot.py
```

`--manifest` mặc định là frozen M1-04b manifest, `--limit` trong [10,19], default 19.
Một connectivity request được dành riêng nên không chọn 20 trang thật để vượt trần
20 requests. Coverage pages trước, rồi risk-focused theo exact identity; không thay
trang lỗi bằng trang thuận lợi hơn. Manifest gốc 23 pages/14 strata; không mở rộng pool.

`prepare_pilot` parse/digest/root-bind parent, reuse verify_bindings với approved
plan/index/ledger, đối chiếu selected OCR snapshots trước/sau loader. Chỉ đọc nội dung
19 selected OCR files, không hash/decode crop/image dataset. Metadata binding check
của parent có thể đối chiếu references ngoài subset; không đọc OCR pages ngoài subset.
Load bằng OCR Loader với identity/image anchor từ approved binding.

Source_ref `M1-01/page_manifest` của request cũ chỉ nhận diện inventory, không phải
document. Runner tạo external request copy dùng **exact original OCR artifact locator**
đã có trong manifest làm page source_ref; giữ parent digest, snapshots và original
request qua parent. Không tạo OCR run ID, không gộp document từ symbol/year. Run identity
gốc vẫn unverified. Không document aggregation trên subset thiếu completeness manifest.

Frozen subset/dry-run report dưới `artifacts/classification-pilot/M1-11b/` (ignored),
exclusive/idempotent writes; cùng inputs reuse, khác inputs conflict. Root tách source
bằng CheckpointStore containment và existing local filesystem checks. Trusted filesystem,
single writer, không phải security sandbox chống concurrent writers/TOCTOU.

## Live preconditions và credentials

Live explicit; không có fallback model hoặc tự chọn key khi lỗi:

```powershell
python scripts/run_classification_pilot.py --live --key-index 0 `
  --live-policy artifacts/classification-pilot/M1-11b/live-policy.json
```

`--key-file` mặc định local ignored credentials file do task chỉ định. Runtime chỉ nhận
key-only lines đúng định dạng, `--key-index` bắt buộc và zero-based trong các key hợp lệ.
Chỉ đọc một lần để cấu hình một client; không log/serialize/fingerprint keys. Không đưa
credentials vào unit tests. Model cố định `gemini-3.5-flash-lite`, không retry/rotation.

`live-policy.json` là private local configuration, gồm `project_policy` theo M1-08,
và bốn attestations true: `free_tier_confirmed`, `pricing_confirmed`,
`data_export_approved`, `exclusive_pilot_scope_confirmed`; `monetary_cap_usd` phải là
string `"0"`. Project policy phải free tier, một credential alias, mapping confirmed,
đúng model/provider, RPM <=5 và RPD <=20. Không hỗ trợ paid billing trong runner này.

Người dùng xác nhận ngày 27/10/2026: được gửi mọi trang báo cáo tài chính, tài khoản
free tier, quota 15 RPM/250000 TPM/500 RPD áp dụng selected key/model, không ứng dụng
khác dùng API. Chọn key index 0; local project/account aliases bind đúng credential
theo attestation này, không giả Google project ID. Active provider quota/billing vẫn
không được API xác minh độc lập. [Google pricing](https://ai.google.dev/gemini-api/docs/pricing)
liệt kê Standard input/output free cho model; [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
áp dụng theo project, không độc lập theo key. Tariff đối chiếu ngày 27/10/2026.

USD 0 là cap theo **user-confirmed free tier và tariff**, không phải provider billing
đã quan sát. Guard monetary accounting là `NOT_CONFIGURED` vì hạ tầng hiện hữu không
có free-tier billing attestation; runner chỉ cho free-only calls sau explicit confirmation.
Không gán provider cost=0 trong LLMResponse. Estimated free-tier cost 0 tách actual
billing unknown. Nếu không xác nhận được free tier/tariff thì dừng trước SDK/client.

## Giới hạn và stop policy

Client được đưa vào GeminiAdapter qua metered SDK boundary; tất cả generate calls
vẫn đi qua CachedLLMService → QuotaBudgetGuard → SharedLLMGateway → GeminiAdapter.
Guard scope mới chỉ cho pilot đã xác nhận exclusive; không chứng minh Google quota
remaining hoặc phục hồi lịch sử project. SDK/GeminiAdapter attempts=1.

- Tối đa 20 actual `generate_content` attempts, gồm smoke và failures.
- Ít nhất 12,1 giây giữa starts tại SDK boundary và pace trước guard admission;
  guard thêm RPM <=5, không từ chối call thứ sáu do đợi quá muộn sau admission.
- Không giới hạn tổng input tokens mặc định. `--input-token-budget N` là tùy chọn explicit,
  không bật chỉ vì pilot cũ dùng 20000. Mỗi request giữ upper bound input 100000 tokens
  (local resource bound), output 512; guard reserve 100512 total, đối chiếu TPM thực tế
  theo configured policy. SDK trước send kiểm UTF-8 JSON bytes contents/config +2048
  envelope <=100000; conservative caller-attested upper bound, không tokenizer.
  Không truncate OCR. Quota guard vẫn kiểm RPM/TPM/RPD và budget được cấu hình.
- Usage prompt tokens provider-reported reconcile bound. Thiếu usage hoặc actual vượt
  bound thì giữ charge bảo thủ và dừng; không unknown→zero.
- Output cap 512 (gồm giới hạn do provider áp dụng); không tools/grounding/image.
- Smoke synthetic đúng schema local phải đạt trước real pages. Failure đầu tiên
  (auth/quota/schema/provider/guard), mất source binding, budget limit hoặc unknown
  usage đều dừng; không retry hoặc key fallback. Safe HTTP status/category được giữ,
  không provider body. Policy bảo thủ có thể dừng trước 10 trang nếu source/quota/provider không an toàn.

`live.started.json` được tạo exclusive trước client; tồn tại marker thì không cho
live invocation mới để tránh reset counters sau crash/restart. Không xóa marker để retry.
Live resumption có network sau restart cần accounting/approval riêng, ngoài task này.

## Reuse và diagnostics

CheckpointStore root riêng; chỉ PageClassifier operational gate đã opt-in được
save_verified. Schema-valid prediction vẫn có thể unresolved theo OCR/evidence gate.
Sau completed page, runner probe cùng request: resolved reuse checkpoint, unresolved
schema-valid có thể reuse cache. Probe khóa network trước khi thử, nên cache expiry/
MISS không gây thêm API call; mismatch dừng. `run_pilot(..., smoke=False)` kiểm tra
resume với cùng service/guard/meter, không khởi tạo lại budget scope.

Public stdout/report chỉ aggregate counts, fixed statuses/issue codes và safe HTTP
code, không raw prompts/responses/OCR text/paths/per-file hashes. `successful_responses`
đếm SDK responses, schema errors tách riêng. `attempted_pages` đếm pipeline attempts;
`processed_pages` đếm completed classifier results, loại local pre-send/guard/provider
failures khỏi resolved/unresolved denominator. `real_api_requests` tách khỏi smoke.
Local pre-send limit được ghi budget_denials, không provider_errors.
Usage counters là **known provider-reported sums**, phải đọc cùng `unknown_usage`;
provider failures không có usage không được diễn giải là tokens thực tế bằng 0.
Checkpoint/cache probes nằm trong hit counts, không thêm page denominator.

Evidence/limitations và readiness trước M1-12 ở [M1-11a evidence](reviews/M1-11a-evidence.md).

## M1-11b policy và so sánh

19 pages giữ đúng selection/order/snapshots của M1-11a, 3 mã/14 strata.
Năm completed pages cũ là prefix 5 của selection; `page_outcomes` giữ status/issues/
anchor counts theo thứ tự, không OCR text/identity, phục vụ so sánh cùng mẫu.
`source_validation_failures` tách source lỗi đã fail closed trong classifier.
Không coi tăng resolved rate là tăng accuracy.

Gate/policy cache semantics ở [classification](page-document-classification.md).
Không đổi prompt/schema/model/cấu hình prediction M1-11a để tránh mất cache tương thích;
cache service revision giữ tên lịch sử theo binding không đổi. Policy revision riêng
chỉ invalidate verified checkpoints. Cache M1-11a chỉ ở RAM, quá trình đã kết thúc,
0 resolved checkpoint: không có prediction persisted đủ điều kiện reuse giữa hai phiên.
Không chuyển aggregate report thành cache giả. Reuse hiện có được probe với network khóa.
Quota/billing vẫn theo owner attestation; historical usage không đồng nghĩa quota remaining
được provider xác minh, quota error dừng ngay.
