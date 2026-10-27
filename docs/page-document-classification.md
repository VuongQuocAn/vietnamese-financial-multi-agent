# Page and Document Classification — M1-11

Offline consumer: `LoadedOCRPage` → `PageClassifier` → DU v1 classification →
`aggregate_document`. Không thay serialized contracts hoặc source OCR.
Text-only; không mở images/crops, không sửa OCR/tables và không chuẩn hóa kế toán.

## Taxonomy và evidence gate

Repository chưa có accounting taxonomy approved. M1-01 discovery chỉ ghi ứng viên
B01/B02/B03/B09; DU v1 dùng vocabulary mở. Caller **phải opt-in** `enabled_labels`
và `taxonomy_version`. Tập candidates thử nghiệm trong `TITLES`:

| Label | Tiêu đề kiểm tra (case-insensitive, giữ nguyên OCR) |
| --- | --- |
| B01 | Bảng cân đối kế toán |
| B02 | Báo cáo kết quả hoạt động kinh doanh |
| B03 | Báo cáo lưu chuyển tiền tệ |
| B09 | Thuyết minh báo cáo tài chính |

Đây là operational policy bảo thủ để review, **không phê duyệt taxonomy kế toán**.
Approval đầy đủ, biến thể ngân hàng/bảo hiểm, tiêu đề khác, OCR mất dấu, continuation
và financial acceptance vẫn TBD. Không gán nhãn `other`/`unknown` cho appendix.

Model trả `Prediction(label, disposition, evidence)` qua structured JSON. Evidence là
indices trong catalog OCRText/cell text; không dùng table.name, không double-count
cell và lines. Code tạo anchors đúng ID/bbox nguồn, không cho model tự tạo evidence.
Local schema validation khác evidence gate và khác business acceptance.

`resolved` cần model `supported`, enabled label, mã Bxx theo word boundary và đúng
title ở hai regions có bbox không chồng nhau, cả hai được model cite. Kiểm tra toàn
catalog để không che loại báo cáo khác. Nhiều cặp code/title khác nhau hoặc model báo
conflicting → `unresolved/conflicting_evidence`; thiếu/single heading/appendix →
`unresolved/insufficient_evidence`. Citation sai → invalid_evidence. OCR quality issue
bất kỳ → ocr_quality_review; DU source-link issues → source_validation_failed.
Không confidence threshold hoặc suy label từ symbol/year. Chuỗi code/title trùng
trong hai vùng vẫn có thể là false positive; chưa có accuracy trên dữ liệu thật.

## Composition và API

Import từ `vietnamese_financial_multi_agent.document_processing.classification`.
`classification_schema_registry()` đăng ký schema prediction v1. Dùng **cùng registry**
cho GeminiAdapter, SharedLLMGateway và CachedLLMService. Wiring tiếp tục theo
[Gemini adapter](gemini-adapter.md), [guard](llm-quota-budget.md),
[cache](llm-response-cache.md). Business classifier chỉ gọi `CachedLLMService`, service
gọi guard rồi SharedLLMGateway/Gemini. Không retry/rotation/model fallback.

```python
config = ClassificationConfig(
    taxonomy_version="experimental-candidates-v1",
    enabled_labels=("B01", "B02", "B03", "B09"),
    configuration_revision="approved-application-binding-revision",
)
classifier = PageClassifier(service, config, checkpoints=store)
page = classifier.classify(
    loaded,
    source_ref=document_run_ref,
    credential_ref=selected_credential_alias,
    reservation=approved_reservation,
    cache_allowed=False,
    checkpoint_allowed=False,
)
document = aggregate_document(
    pages,
    source_ref=document_run_ref,
    expected_pages=complete_manifest,
    ancillary_pages=frozenset(),
)
```

`service/store/loaded` và verified bindings do application cung cấp. Reservation là
upper bound input + output + mọi tokens khác do caller attests; module không suy quota
từ độ dài text. Default model `gemini-3.5-flash-lite`, output cap 512, timeout 30s,
input JSON cap 100000 characters (không truncation). Vượt cap hoặc catalog rỗng không
gọi Gateway. Provider/schema/guard failures trả unresolved; xem safe issue code và
`llm_result.guard_result`/response usage thay vì log toàn response.

`PageClassificationResult.understanding` là DU v1; `provenance` và `source_mapping`
giữ nguyên snapshot nguồn; `prediction` tách LLM prediction. `text_regions/tables`
để rỗng vì task này chỉ phân loại; evidence text/table được dẫn qua classification
anchors về raw. Wrapper có fingerprints/checkpoint status/`llm_result` cho accounting,
không serialize thành contract mới. Không log wrapper fields/prompt/raw responses.

## Identity và aggregation

Caller xác minh source_ref bind đúng **một document + OCR run/artifact** và dùng cùng
ref trong OCR loader mapping và manifest. Không suy từ symbol/year; không tự tạo hoặc
resolve ref. Raw page identity giữ đủ symbol/year/page/image/source_ref. Mapping anchor
nếu có phải khớp identity. Chỉ nhận mapping resolved; raw được parse lại và quality check.
Không yêu cầu loader.identity_checked=True khi chưa có anchor; source binding vẫn là
trách nhiệm caller, không phải module chứng minh mapping giữa file và tài liệu.

`aggregate_document` cần caller-verified complete manifest. Pages khác source/run bị
reject, kể cả cùng symbol/year. Manifest phải cùng symbol/year; đủ exact identities,
không duplicate page number/identity; thiếu/thừa/duplicate hoặc mixed config → unresolved.
Không tự đoán completeness từ max page number. Document có thể chứa nhiều statement
types; trả tuple labels, không ép toàn tài liệu thành một Bxx. Candidate labels/anchors
có thể giữ khi document unresolved; không diễn giải chúng thành document accepted.

Ancillary pages được caller khai báo theo manifest; chỉ bỏ qua trang có đúng issue
insufficient_evidence. Không bỏ qua conflict/provider/schema/source/quality errors.
Không có supported label thì unresolved. Không có persisted document checkpoint hoặc
LLM document call: aggregation deterministic, runtime-only.

## Checkpoint/cache và acceptance

Mặc định cả cache/checkpoint đều opt-out. `checkpoint_allowed=True` là attestation
caller chấp nhận **operational evidence gate** này cho resume và cho phép lưu dữ liệu
trong root đã chọn. Chỉ prediction resolved qua gate/source validation được save_verified;
unresolved/error không lưu verified. Không coi schema-valid là accepted. Root phải nằm
ngoài data roots và chỉ dành cho authorized source/scope; không chia checkpoint root
cho tenants/permissions khác. Đổi binding/adapter/model permissions cần đổi config revision.

Input digest phủ full OCR export (gồm provenance/extras), logical source mapping và
identity_checked. Config digest phủ model/generation/limits/config revision/taxonomy/
processing version, prompt content, local schema content/identity và title rules.
Text-only không đọc ảnh nên không hash ảnh; muốn dùng image phải thêm verified content
digests và version mới. Không fingerprint API key. Source/page/stage khác tách slot.

HIT chỉ khi checkpoint opt-in, integrity/request match; parse prediction và chạy lại
evidence/source gate trên OCR hiện tại. Semantically invalid HIT thành INVALID rồi xử lý
lại. HIT hợp lệ không gọi service/guard/LLM. Cache key cũng nhận input/config digest để
không reuse text giống nhau với nguồn/config khác. Cache HIT revalidate evidence gate;
usage mới là calculated zero, usage gốc nằm historical_usage theo M1-09.

## Credentials và live verification

Secret directory `src/api/api_key/` được ignore toàn bộ, không tracked. Business code
không đọc file keys. Application dùng `GEMINI_API_KEY` của **một credential đã chọn** qua
`GeminiAdapter.from_environment`; không auto-select/rotate keys. File local được giữ nguyên.

Tra tài liệu Google ngày 2026-10-27: model code và structured outputs được liệt kê ở
[model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).
Đây không chứng minh selected credential truy cập API được. [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
áp dụng theo project; active limits xem AI Studio. Phiên này chưa có selected credential,
project mapping/quota hiện hành/budget đã xác nhận, nên **không gọi API** (kể cả models.get).
Live availability/access/usage vẫn chưa verified; không fallback model hoặc giả zero cost.
