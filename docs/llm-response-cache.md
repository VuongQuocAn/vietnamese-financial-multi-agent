# LLM Response Cache — M1-09

Application → `CachedLLMService` → cache lookup; miss/bypass/expired →
`QuotaBudgetGuard.generate` → `SharedLLMGateway` → adapter. Hit không gọi Guard,
không reserve RPM/RPD/TPM/budget. Guard rejection giữ nguyên trong `guard_result`,
không dựng response giả hoặc ghi cache. Contract v1/Gateway/Guard/adapter không đổi.

## Cấu hình và key

`CachedLLMService(guard, tenant_ref=..., project_ref=..., credential_refs=frozenset(...),
configuration_revision=..., scope_confirmed=False, schema_registry=None,
ttl_seconds=60, max_entries=128, clock=monotonic)` tạo store riêng cho mỗi instance.
Application phải xác nhận tenant/project và allowlist credential aliases đã được map
đúng với Guard, cùng quyền chia sẻ response; chỉ đặt `scope_confirmed=True` khi biết rõ.
Aliases không phải key values/fingerprints/email. Không suy project từ API key.
Đổi scope/binding/credential permissions/config thì tạo instance mới và hủy instance cũ.

Key là SHA-256 của canonical JSON: sorted object keys, compact separators, giữ ordered
arrays/messages/roles/content/system instructions và Unicode/whitespace. Gồm toàn
request export trừ request_id/correlation: contract `llm_gateway_v1`, provider/model,
generation (omitted/null/value khác nhau), output format/schema identity/version/dialect/
strictness, constraints. Thêm `llm_response_cache_v1`, tenant/project scope và
`configuration_revision` do application xác nhận (adapter, config, model revision).
Schema fingerprint là SHA-256 của schema content từ LocalSchemaRegistry, cùng đầy đủ
identity; không fetch URL/file. Thiếu local schema thì bypass cache. Không có credential
values/fingerprints trong key/entry; không xuất key digest hoặc raw prompts vào logs/evidence.

Model alias có thể đổi: dùng TTL hữu hạn ngắn (mặc định 60 giây), revision mới hoặc
explicit invalidation khi thay đổi; không cam kết deterministic replay. Chỉ adapters
tuân thủ contract, không dùng request_id/correlation làm input sinh output mới tương thích.

## Eligibility và validation

`generate(request, credential_ref=..., reservation=..., cache_allowed=False)` mặc định
bypass cả đọc và ghi. Caller chỉ bật True sau quyết định request **và response** được phép
lưu trong memory theo policy ứng dụng. Unknown/financial data chưa có policy: giữ False.
Không secret scanner/DLP: caller không gửi keys/secrets vào content hoặc IDs và không
approve output có secrets. Module không đọc environment, credentials, dataset hoặc ghi disk.

Chỉ lưu success, error=None, đúng request_id/correlation/requested_model/output format/schema.
Text phải không rỗng; JSON không schema cần json_valid. JSON có schema cần schema_valid
từ Gateway, đồng thời cache kiểm chứng payload trên đúng schema local; không tin raw
provider attestation/SDK objects. Error/partial/refused/malformed/invalid_json/schema_invalid/
unverified structured output không được lưu. Schema-valid không chứng minh nội dung tài chính đúng.

## TTL, eviction và concurrency

TTL bắt đầu khi lưu response hoàn tất; expired entry không được trả. Store dùng LRU,
max_entries dương; expired entries khác được dọn khi ghi. Không giới hạn bytes trong MVP,
nên caller phải giới hạn kích thước request/output theo policy. `invalidate(request)` xóa
key hiện tại, `clear()` xóa toàn scope. Invalidation tăng epoch để chặn writes từ calls
đang chạy trước invalidation; hits đã trả không bị thu hồi. Version/config mới dùng instance mới.
Clock inject trả monotonic seconds, không lùi hoặc non-finite; production mặc định monotonic.
Cache operations giữ Lock, không lock qua Guard/network. Không single-flight: concurrent
misses có thể sinh nhiều calls, từng call vẫn được shared M1-08 Guard kiểm soát.
Không cross-process sharing, distributed quota hoặc persistence/restart recovery.

## Result và accounting

`CachedResult` có response, cache_status (`hit/miss/expired/bypassed`), cache_hit,
provider_called, guard_result, historical_usage/cost, age_seconds/ttl_remaining_seconds,
key_version. Không có raw content/digest trong repr hoặc metrics/logs tự động.
Response chứa output riêng; caller không log/serialize toàn response vào diagnostics.

Hit tạo deep copy, bind request_id/correlation/requested_model theo request mới; giữ
effective/provider-reported model và provider_response_id gốc để provenance trung thực.
Usage gốc/cost gốc nằm trong historical_usage/historical_cost và **không** cộng như phát sinh
mới. Response hit usage = calculated zero input/output/total tokens, không giả là
provider_reported. Cost hit = not_available (không có currency/pricing để gán provider
cost); wrapper cache_hit/provider_called=False xác nhận không phát sinh provider billing
mới. Không biến historical unknown thành provider-reported zero.

Miss giữ nguyên response usage/cost và GuardResult. provider_called=False cho hit hoặc
Guard rejection; None cho admitted miss vì Guard chỉ xác nhận gọi Gateway, không biết
adapter có thực sự gửi API hay reject capability trước đó. Không khai sai live provider call.
Guard vẫn giữ accounting/unknown reservation của lần sinh gốc; cache không refund/reset quota.

## Ví dụ offline chạy được

Trong môi trường đã cài `.[dev]`, không API key:

```python
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_cache import CachedLLMService
from vietnamese_financial_multi_agent.core.llm_contracts import parse_llm_request
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_quota_budget import (
    GatewayBinding,
    ProjectPolicy,
    ProjectRegistry,
    QuotaBudgetGuard,
    QuotaLimits,
    Reservation,
)

policy = ProjectPolicy(
    account_ref="synthetic_account",
    project_ref="synthetic_project",
    credential_refs=("synthetic_credential",),
    provider="gemini",
    model="gemini-3.5-flash-lite",
    tier="synthetic",
    quota_limits=QuotaLimits(rpm=15, tpm=250000, rpd=500),
    verification_source="synthetic_example",
    mapping_confirmed=True,
)
gateway = SharedLLMGateway({"gemini": FakeLLMTransport()})
guard = QuotaBudgetGuard(
    ProjectRegistry([policy]),
    [
        GatewayBinding(
            policy.account_ref,
            policy.project_ref,
            "synthetic_credential",
            policy.provider,
            policy.model,
            gateway,
        )
    ],
)
guard.initialize(confirmed_fresh_scope=True)  # chỉ scope synthetic mới
service = CachedLLMService(
    guard,
    tenant_ref="synthetic_tenant",
    project_ref=policy.project_ref,
    credential_refs=frozenset({"synthetic_credential"}),
    scope_confirmed=True,
    configuration_revision="synthetic-adapter1-config1-model-unknown",
    ttl_seconds=30,
)
request = parse_llm_request(
    {
        "contract_version": "llm_gateway_v1",
        "request_id": "synthetic-1",
        "model": {"provider": policy.provider, "model": policy.model},
        "messages": [{"role": "user", "content": "Synthetic example"}],
        "generation": {"max_output_tokens": 32},
    }
)
args = dict(
    credential_ref="synthetic_credential",
    cache_allowed=True,
    reservation=Reservation(token_upper_bound=100, token_basis="caller_attested_upper_bound"),
)
first = service.generate(request, **args)
second_request = request.model_copy(deep=True)
second_request.request_id = "synthetic-2"
second = service.generate(second_request, **args)
assert first.cache_status == "miss" and second.cache_hit
assert second.provider_called is False
assert second.response.request_id == "synthetic-2"
assert second.response.usage.total_tokens == 0
assert guard.snapshot(policy.project_ref, policy.provider, policy.model)["rpd_used"] == 1
```
