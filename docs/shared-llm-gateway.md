# Shared LLM Gateway — Research MVP

Gateway thuộc `core`, dùng nguyên [llm_gateway_v1](llm-gateway-contract.md).
Caller → SharedLLMGateway → transport inject theo provider → revalidate/bind response.
Core không import nghiệp vụ. Không SDK, environment, network hoặc ghi log tự động.

## API và ví dụ chạy offline

`LLMTransport` là callable Protocol: `(LLMRequest) -> LLMResponse`.
`SharedLLMGateway(transports: Mapping[str, LLMTransport]).generate(request)` trả
`LLMResponse`. Mapping được sao chép khi khởi tạo; chọn provider/model tường minh
trong `request.model`, không phân tích tên model. Thay mapping bằng instance gateway
mới khi đổi provider configuration. Không global state hoặc default model ẩn.

Ví dụ sau chạy trong môi trường đã cài package, không cần key:

```python
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_contracts import parse_llm_request
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway

gateway = SharedLLMGateway({"synthetic": FakeLLMTransport()})
request = parse_llm_request(
    {
        "contract_version": "llm_gateway_v1",
        "request_id": "example-1",
        "model": {"provider": "synthetic", "model": "example-v1"},
        "messages": [{"role": "user", "content": "Ví dụ synthetic"}],
        "generation": {},
        "output_spec": {"format": "json"},
    }
)
response = gateway.generate(request)
assert response.status == "success"
assert response.output.validation_status == "json_valid"
assert response.usage.total_tokens is None
```

Fake chỉ dành cho tests/examples: `text`/`json_text` cấu hình output synthetic;
`handler` tùy chọn nhận request để mô phỏng provider errors, timeout, mismatches,
usage/cost. Handler có cùng signature transport. Fake mặc định ghi usage/cost unknown.
JSON lỗi syntax trả malformed + structured_output_invalid; không sửa raw text.

## Binding và structured output

Gateway revalidate mutable models bằng parser của contract. Snapshot request riêng
được giữ để đối chiếu, transport nhận deep copy; response cũng được sao chép.
Transport tự chịu trách nhiệm thread safety nếu dùng state; gateway không cache
response hoặc giữ request đang xử lý. Shared fake mặc định không có per-request state.

Response phải khớp request_id, requested_model (cả provider/model) và correlation.
Correlation so sánh toàn bộ giá trị, kể cả trường hợp một bên thiếu; không bỏ qua
mismatch. Output khi có phải khớp format được yêu cầu và schema_ref chính xác.
Không có output_spec thì nhận text hoặc JSON không schema. Error/refused có thể
không có output, vẫn phải khớp identity/correlation. effective_model là metadata
riêng theo contract; không bị ghi đè thành requested_model.

Contract-valid chỉ nói response hợp lệ độc lập; request-bound cần các kiểm tra
trên. Schema-validated cần validator thực sự đáng tin cậy, chưa có trong M1-06.
Vì vậy gateway reject cả schema_valid/schema_invalid do transport khai bằng safe
schema_mismatch, kể cả attestation hợp lệ về cấu trúc. Không có allowlist validator
ID hoặc cờ trust để biến lời khai thành bằng chứng. Không nâng unverified thành
schema_valid, không giả định strict=True được provider enforce. Success/unverified
chỉ là generation hoàn tất; caller không được coi đó là schema validation thành công.

JSON syntax được parser contract kiểm tra với raw_text/payload. Giữ json_valid,
unverified, invalid_json; giữ malformed/partial và lỗi tương ứng. Response tự nhận
success nhưng chứa JSON sai bị từ chối khi revalidate. Không repair JSON, fetch schema
hoặc chạy general schema engine. Status/finish_reason/error dùng nguyên invariants v1.

## Usage, cost và errors

Response được chấp nhận giữ usage/cost và provenance provider nguyên giá trị,
kể cả Decimal precision/scale, counters zero hoặc unknown/null. Không ước lượng
token từ text, cộng counters, tải pricing hoặc tính chi phí. Response bị từ chối
không đáng tin cậy: safe response mới có usage/cost unknown, không dùng billing claim
từ response đó; thông tin này không khẳng định provider chưa tiêu tốn chi phí.

| Trường hợp | Kết quả |
| --- | --- |
| Invalid request | Ném safe LLMContractError trước transport; thiếu valid identity không thể tạo response v1 |
| Provider chưa đăng ký | error / invalid_configuration |
| Transport báo TimeoutError | error / timeout |
| Transport exception khác | error / provider_unavailable |
| Invalid response hoặc identity/correlation mismatch | error / internal |
| Output format mismatch | error / structured_output_invalid |
| Schema mismatch hoặc untrusted schema attestation | error / schema_mismatch |
| Provider-declared error/refusal hợp lệ và bound | Giữ error taxonomy/retry hints/status gốc |

Safe responses bind với snapshot request, không output/raw exception, message cố định
`LLM operation failed`, retryability unknown. Gateway không log prompt/response hoặc
exception. Request text/opaque IDs vẫn do caller kiểm soát, contract không phải DLP.

M1-06 chỉ gateway và fake tests. M1-07 quyết định SDK/model/provider capabilities,
schema validation thực tế và adapter mapping; adapter thực thi timeout từ constraints
và xử lý unsupported/null generation values tường minh. Gateway hiện không ngắt một
transport bị treo. M1-08 xử lý quota/budget/pricing/retry; M1-09 cache. Không task nào
trong số này được triển khai ở đây; không live inference/đánh giá tài chính.
