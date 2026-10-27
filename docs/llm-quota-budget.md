# Quota & Budget Guard — M1-08

Application chọn project/credential → QuotaBudgetGuard → SharedLLMGateway → transport.
Một Guard dùng chung trong process giữ registry/buckets/budget dưới Lock; chỉ admission
và reconciliation giữ lock, không giữ qua network. Không đổi contract v1/Gateway/adapter.

## API và cấu hình

`ProjectRegistry(list[ProjectPolicy])` kiểm tra project/account/budget nhất quán,
credential alias không thuộc hai projects, không duplicate policy cho project/provider/model.
Policy chứa account_ref/project_ref/credential_refs/provider/model/tier/quota_limits/
verification_source/mapping_confirmed và optional BudgetLimit(amount=Decimal, currency).
Aliases không email/key. Hai credentials cùng project/model dùng chung bucket;
quota khác model tách bucket nhưng monetary budget của project dùng chung.

[Config mẫu](../configs/llm-projects.example.json) chỉ synthetic aliases, chưa xác nhận
mapping, limits 15 RPM/250000 TPM/500 RPD. Parse từng project bằng
`ProjectPolicy.model_validate_json(...)` khi đọc JSON. Mapping thật/secrets nằm ngoài Git.
Task báo một project có ảnh AI Studio xác nhận; phần còn lại user_reported. Phiên này
không kiểm tra ảnh/từng project độc lập, không tự coi giới hạn đó là chung cho mọi project.
`verification_source` giữ provenance được ứng dụng cung cấp, không phải bằng chứng API.

`GatewayBinding` liên kết project/account/credential/provider/model với Gateway được
khởi tạo cho credential đó. Guard không đọc key hoặc tự tạo client. Application có thể
dùng local resolver(credential_ref) → key khi dựng Gemini client/adapter; chỉ resolve
credential đã chọn, không ghi value vào registry/accounting. Không dò project từ key.
GatewayBinding là attestation của composition layer, không chứng minh key thuộc project.
Mapping chưa confirmed/thiếu/sai account/model/credential thì block trước Gateway.

Ví dụ offline hoàn chỉnh:

```python
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
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
    tier="free",
    quota_limits=QuotaLimits(rpm=15, tpm=250000, rpd=500),
    verification_source="synthetic_example",
    mapping_confirmed=True,
)
gateway = SharedLLMGateway({"gemini": FakeLLMTransport()})
binding = GatewayBinding(
    policy.account_ref,
    policy.project_ref,
    "synthetic_credential",
    policy.provider,
    policy.model,
    gateway,
)
guard = QuotaBudgetGuard(ProjectRegistry([policy]), [binding])
# Chỉ scope synthetic mới; live cần external accounting/mapping xác nhận trước.
guard.initialize(confirmed_fresh_scope=True)
request = parse_llm_request(
    {
        "contract_version": "llm_gateway_v1",
        "request_id": "synthetic-1",
        "model": {"provider": policy.provider, "model": policy.model},
        "messages": [{"role": "user", "content": "Synthetic example"}],
        "generation": {"max_output_tokens": 32},
    }
)
result = guard.generate(
    request,
    project_ref=policy.project_ref,
    credential_ref="synthetic_credential",
    reservation=Reservation(token_upper_bound=100, token_basis="caller_attested_upper_bound"),
)
assert result.admitted and result.response.status == "success"
assert result.response.usage.total_tokens is None
assert guard.snapshot(policy.project_ref, policy.provider, policy.model)["tpm_charged"] == 100
```

GuardResult có admitted/reason/response/error/retry_at; denied không tạo response v1 giả.
Admitted chỉ nói đã reserve và gọi Gateway, consumer vẫn kiểm tra response.status.
Invalid request/Reservation ném validation error trước admission. Không log input/errors.
Snapshots là copies của số liệu accounting, không chứa response bodies/credential values.

## Quota và thời gian

[Google rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) áp dụng theo
project, RPD reset midnight Pacific; limits phụ thuộc model/tier và capacity thực tế.
Guard dùng ZoneInfo America/Los_Angeles, có tzdata để Windows xử lý DST đúng.

RPM là sliding 60 giây từ admission, tính cả requests thất bại. TPM dùng upper bound
**total tokens** do application xác nhận (bảo thủ hơn TPM input của provider), không
suy từ text length. Bắt buộc max_output_tokens và bound >= output cap; application phải
tính/đảm bảo phần input và mọi token khác nằm trong bound. Đây không phải tokenizer.
Thiếu bound hợp lệ thì block, không gọi thêm API để count tokens.

Pending requests giữ quota qua window rollover; TPM giữ charge đến 60 giây sau completion.
RPD carry pending sang ngày Pacific mới để không bỏ sót requests băng qua midnight.
Chỉ provider-reported total_tokens mới reconcile token charge; thiếu total/estimated
usage giữ bound, ghi unknown_usage_count. Actual vượt bound khóa bucket để xử lý ngoài.
Policy bảo thủ có thể block lâu hơn provider. Provider usage trong response giữ nguyên.
Local RPM/RPD reset có retry_at khi tính được; không đoán khi pending/unknown provider hint.

## Budget và retry

Optional per-project budget và overall_budget dùng cùng currency, Decimal, không conversion.
Khi bật budget, mỗi call phải có spending_upper_bound/currency/spending_basis=
approved_upper_bound do application cung cấp theo policy đã duyệt; không có pricing engine.
Admission reserve đồng thời quota, project money và overall money. Currency sai/bound
thiếu hoặc vượt available budget thì block. Khi không bật: money status NOT_CONFIGURED,
used/reserved/remaining=None, không cam kết kiểm soát chi phí.

Snapshot used_known là phần chi phí provider báo; reserved gồm pending và unknown ceilings;
remaining = limit - used_known - reserved. Unknown cost giữ reserved vô thời hạn trong scope,
unknown_cost_count tăng, không đổi thành zero. Estimated/calculated cost không được coi
là actual; provider-reported zero phân biệt rõ. Sai currency/vượt ceiling đánh dấu budget
UNAVAILABLE; used thực tế vẫn ghi nhận, remaining có thể âm khi caller bound sai.
Actual cost không bao giờ được sửa trong LLMResponse. Limits là kiểm soát theo bounds
được tin cậy, không phải cam kết billing khi bounds khai sai hoặc có usage ngoài app.

Zero automatic retries, không key/project rotation. `manual_retry_eligible(error)` chỉ
true cho transient allowlist + retryability=retryable; caller vẫn cần admission mới.
Provider rate_limit/quota_exceeded khóa bucket; có retry_after thì dùng hint, thiếu thì
retry_at=None và chờ `clear_provider_unavailable(..., confirmed_available=True)` sau
xác nhận bên ngoài. Không khóa vĩnh viễn do đoán quota ngày, không reset counters khi clear.

## In-memory limitations

Chỉ một Guard dùng chung có tác dụng trong process. Không persistence, multiprocess,
distributed quota, phục hồi lịch sử hoặc authoritative Google accounting. Không dùng
hai guard độc lập cho cùng live scope. Sau restart không tự assume fresh quota:
Guard mặc định block đến explicit initialize. Chỉ xác nhận fresh_scope khi đã biết
scope exclusive không prior usage; nếu state mất/không kiểm chứng được thì giữ block,
chờ scope mới hoặc accounting policy được duyệt. initialize không cho reset guard đang dùng.
Không live API/keys thật trong M1-08; không pricing/batch/cache/production monitoring.
