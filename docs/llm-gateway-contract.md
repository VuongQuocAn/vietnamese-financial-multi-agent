# LLM Gateway Contract — llm_gateway_v1

## Phạm vi và ownership

M1-05 thuộc `core`, triển khai tại `src/core/llm_contracts.py`. Public namespace:
`vietnamese_financial_multi_agent.core.llm_contracts`; exports qua `__all__`.
Module chỉ Pydantic/standard library, không imports nghiệp vụ hoặc SDK. Không
network, environment, đọc secrets, schema resolution, token estimation hoặc inference.
Các consumer tương lai document_processing/agents/verification/outputs import core;
core không import ngược. Pipeline Offline → Online → Output giữ nguyên.

## Request và messages

`LLMRequest`: contract_version bắt buộc `llm_gateway_v1`, request_id, model,
messages và generation bắt buộc; output_spec/constraints/correlation optional nullable.
`ModelIdentity` có provider và model riêng, opaque identifiers ASCII tối đa 200 ký tự
`[A-Za-z0-9][A-Za-z0-9._:/-]*`. Không parse model ID để suy provider. Requested model
khác effective model; không có credential/account/project key hoặc provider kwargs.

Messages giữ thứ tự, roles system/developer/user/assistant. Content chỉ string không
rỗng/whitespace-only. Giữ nguyên Unicode tiếng Việt, whitespace và text dài, không
truncate/tokenize. Không giới hạn độ dài prompt tại contract; runtime phải quản lý
kích thước/depth đầu vào theo policy sau này. Empty conversation bị từ chối.
Không có metadata tùy ý, file/image/audio/video hoặc tool/function messages.

`GenerationParameters` không đặt generation defaults: temperature >= 0 hữu hạn,
top_p trong [0,1], max_output_tokens int dương, stop_sequences list string không rỗng,
seed int; tất cả nullable/optional. Temperature không có upper bound toàn provider;
capability validation của adapter phải từ chối explicit unsupported parameters.
Không ngầm coi mọi provider có cùng miền temperature/seed/stop/null semantics.
Omitted khác null khác giá trị; adapter không được âm thầm bỏ null/unsupported values.
`RequestConstraints.timeout_seconds` dương/hữu hạn, chỉ representation, không timer.
`Correlation` chỉ trace_id/parent_request_id/caller opaque IDs, không arbitrary mapping.

## Structured outputs

`OutputSpec.format`: text hoặc json. Text không có schema/strictness. JSON có thể
cung cấp `SchemaReference(schema_id, name, version, dialect)` và strict bool/null;
strictness chỉ có nghĩa khi schema_ref được cung cấp. Dialect v1 nhận JSON Schema
Draft 2020-12; không tuyên bố provider hỗ trợ hoặc đã enforce dialect/schema/strictness.
Refs là identity, không URL fetch/file open. Không inline business schema trong gateway.

| Representation | Ý nghĩa |
| --- | --- |
| output absent/null | Không có output nhận được; response lỗi có thể dùng trạng thái này |
| TextOutput(format=text, text=...) | Text, kể cả trông giống JSON; không tự parse |
| JSONOutput/json_valid | JSON syntax hợp lệ, không schema reference; chưa schema-valid |
| JSONOutput/unverified | JSON syntax hợp lệ và có schema reference, chưa có attestation |
| JSONOutput/schema_valid | Caller khai validator đã kiểm tra schema, kèm attestation |
| JSONOutput/schema_invalid | Caller khai schema mismatch, kèm attestation |
| JSONOutput/invalid_json | Parse thất bại; payload bắt buộc null, không attestation |

`parse_json_output(raw_text, schema_ref=...)` chỉ tạo json_valid/unverified/invalid_json.
Không bao giờ tạo schema_valid. JSON null hợp lệ khác invalid JSON qua status.
Duplicate object keys, NaN/Infinity và trailing content không hợp lệ. Lone surrogate
bị từ chối toàn contract vì không thể serialize Unicode an toàn.

`JSONOutput` giữ raw_text và payload, kiểm tra chúng đồng nhất về biểu diễn JSON
(object key order không quan trọng; true/1 và 1/1.0 không bị coi tương đương). Không
chấp nhận payload khác raw hoặc tự nâng unverified. Schema checked statuses cần
`SchemaValidation(schema_ref, validator_id, status)` khớp identity/status. Attestation
là lời khai, không chứng minh schema validator đã thực thi. Không có schema validator
runtime trong M1-05. Parsing errors biểu diễn bằng invalid_json; schema mismatch bằng
schema_invalid, không lưu raw exception/validator diagnostic tùy ý.

## Response và provenance

`LLMResponse` bắt buộc version/request_id/status/provenance/usage/cost/finish_reason;
output/error/provider_response_id/correlation optional nullable. Output discriminated
union text/json ngăn mixed fields. Finish reason stop/length/safety/error/unknown là
vocabulary chuẩn hóa, không giữ raw provider body hoặc arbitrary metadata.

| Status | Điều kiện |
| --- | --- |
| success | Có output, không error/invalid JSON/schema mismatch; finish stop/unknown |
| error | Có GatewayError, không output; finish error |
| partial | Có output; finish length/error/unknown; có thể giữ JSON bị cắt và error |
| refused | Có safety error, finish safety, không generated output |
| malformed | Có invalid_json/schema_invalid và matching structured_output_invalid/schema_mismatch error |

Success chỉ nói generation hoàn tất: json_valid/unverified vẫn chưa schema-verified.
Partial không phải success, consumer phải kiểm tra output validation_status.
Không có pending response model; trước khi provider trả kết quả chưa tạo response.

`ResponseProvenance.requested_model` luôn giữ routing ban đầu. Effective model chỉ
có khi adapter_confirmed, adapter confirmation cần effective model. Provider-reported
model string riêng, có thể là alias và không chứng minh effective identity. metadata_source
unknown không được có claimed effective/reported model; provider_reported cần reported
model. Provider response ID là opaque ID; không có arbitrary provider response metadata.
Caller/gateway tương lai chịu trách nhiệm khớp request_id/requested_model/schema của
response với request; parser độc lập không giữ state để xác minh binding.
Provider provenance không thay business evidence/source provenance tài chính.

## Usage và cost

`Usage`: status unknown/not_available/available; source unknown/provider_reported/
calculated/estimated. Input/output/total/cached/reasoning tokens nullable, strict int
không âm, không bool/string. Available cần ít nhất một counter kể cả zero và source
đã biết. Unknown/not_available không được có counter/source claim. Không điền total
từ input+output, không buộc đẳng thức hoặc cached/reasoning subsets vì accounting
provider có thể khác. Không suy tokens từ số ký tự; M1-05 không tính estimates.

`Cost`: status và source tương tự, source estimated/provider_reported/calculated.
Money chỉ Decimal hoặc decimal string, không nhận binary float/int/bool. Không âm,
không NaN/Infinity. JSON money luôn string giữ precision/scale, unknown amount=null
khác zero. Available bắt buộc amount/currency/price_source; estimated/calculated cần
pricing_version. Optional pricing_timestamp phải UTC YYYY-MM-DDTHH:MM:SSZ hợp lệ.
Currency chỉ kiểm tra format ba chữ ASCII hoa; chưa xác minh membership registry ISO
hoặc khả năng provider hỗ trợ. price_source là opaque identity, không tự fetch pricing.
Unknown/not_available không được claim amount/currency/pricing provenance.
Không bảng giá, quota hoặc budget trong M1-05; unknown không biến thành zero.

## Error taxonomy và security

`GatewayError.category/code`: invalid_request, invalid_configuration, authentication,
authorization, rate_limit, quota_exceeded, provider_unavailable, timeout, network,
structured_output_invalid, schema_mismatch, safety, internal, unknown_provider.
V1 code dùng cùng vocabulary và phải khớp category; có thể version-review finer codes
sau này. Retryability unknown/retryable/not_retryable và origin caller/gateway/adapter/
provider được caller xác nhận; không tự suy từ HTTP 429. quota_exceeded không được
claim retryable transient. Retry hint không phải retry engine; adapter chịu trách nhiệm
chỉ cung cấp retry_after_seconds từ nguồn đáng tin cậy, hữu hạn/không âm.

`safe_message` chỉ nhận chuỗi cố định `LLM operation failed` (default); omitted default
không xuất trong export, code/category luôn có. Provider error code chỉ allowlist
http_400/401/403/408/429/500/502/503/504/other; unknown provider codes map other, không
chép raw code/body/exception. Không lưu credentials, account identifiers, headers,
raw exceptions hoặc arbitrary diagnostic metadata.

Public `parse_llm_request`/`parse_llm_response` ném `LLMContractError` chỉ chứa
ContractIssue code/path; không giữ payload/input/context/message/exception nguyên gốc.
Paths dùng schema-owned field names/index; unknown key/discriminator được che bằng
`<field>`. Chỉ public parser là safe error boundary. Pydantic direct model APIs có thể
có input trong `.errors()` dù hide_input_in_errors=True; không publish các lỗi đó.

Text/raw_text/JSON payload/opaque IDs vẫn là dữ liệu caller cung cấp. Contract không
phải secret detector/DLP; caller không gửi secrets, không log toàn prompt/response,
không đặt credential vào IDs. Không thể cam kết tự redact secret nằm trong text hợp lệ.
Credentials/runtime routing config phải nằm ngoài serialized contracts; multi-key,
rotation/account/quota aggregation không nằm trong contract.

## Serialization và versioning

Strict Pydantic 2, extra forbid, finite numbers, valid Unicode, non-executable JSON
types. Public parsers nhận decoded object hoặc JSON string; JSON string parser từ chối
duplicate keys trước khi model validation. Direct model_validate_json không thay parser
này vì JSON duplicate handling của Pydantic không thuộc public guarantees.
`export()` revalidate snapshot, mode=json/exclude_unset; `to_json()` sorted object keys,
compact separators, Unicode nguyên vẹn, no NaN. Arrays không sort, không normalize text.
Models có thể sửa trong bộ nhớ; public export revalidate trước serialization. Không dùng
model_construct/model_copy(update=...)/model_dump làm validation hoặc safe boundary.

Contract version bắt buộc, version lạ và fields lạ bị từ chối. Breaking changes/status/
capability additions cần review/version mới; future multimodal/tools sẽ version-review,
không dùng kwargs mở. Không cam kết migration/backward compatibility ngoài v1.
Không đổi Raw OCR/Document Understanding/Path Mapping v1.

Artifact [llm_gateway_v1.schema.json](../schemas/llm_gateway_v1.schema.json) sinh từ
public request/response models bằng `llm_gateway_json_schema()` ở serialization mode:

```powershell
python scripts/export_llm_gateway_schema.py
```

Schema Draft 2020-12 và $id urn cố định; unit tests so sánh artifact để phát hiện drift.
Schema mô tả serialized types/bounds/fields/discriminator; không thực thi cross-field
invariants, decimal parsing, duplicate key/Unicode rules hoặc chứng minh attestation.
Python validators mới kiểm tra các semantics đó; không suy schema-valid từ parse.

## Ví dụ synthetic

```python
from vietnamese_financial_multi_agent.core.llm_contracts import (
    parse_llm_request,
    parse_json_output,
)

request = parse_llm_request(
    {
        "contract_version": "llm_gateway_v1",
        "request_id": "example-1",
        "model": {"provider": "example-provider", "model": "example-model"},
        "messages": [{"role": "user", "content": "Trả JSON ví dụ tiếng Việt."}],
        "generation": {"max_output_tokens": 128, "temperature": None},
        "output_spec": {"format": "json"},
    }
)
serialized = request.to_json()
output = parse_json_output('{"text":"Ví dụ"}')
assert output.validation_status == "json_valid"  # chưa kiểm tra schema
```

Không phải live test, ground truth, benchmark hoặc chứng nhận chất lượng tài chính.

## Limitations và handoff

- M1-06: Gateway/correlation/capability policy, safe errors, resource/input limits,
  schema validator lựa chọn và response/request binding còn TBD; giữ states rõ ràng.
- M1-07: SDK, Gemini model, live API policy và provider-specific structured-output
  capabilities TBD; adapter map statuses/metadata và không serialize credentials.
- M1-08: budget/quota limits/pricing table/effective prices và chính sách retry TBD;
  unknown usage/cost không được coi là zero hoặc safe-to-retry.
- M1-09: cache backend/key/privacy policy TBD; canonical JSON không tự là cache policy.
- Không inline schema execution/resolution, no full provider metadata dump, no measured
  inference quality/cost. Schema attestations cần trusted caller và validator thực thi
  ở task sau; không thể chứng minh sự thật chỉ bằng validation contract.
