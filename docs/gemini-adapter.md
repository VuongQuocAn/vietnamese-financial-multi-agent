# Gemini Adapter — M1-07

`core.gemini_adapter.GeminiAdapter` implement callable LLMTransport, dùng Google
Gen AI Python SDK **2.33.0** (pin pyproject), provider `gemini`, model mặc định
`gemini-3.5-flash-lite`. Request chọn model tường minh, không phân tích prompt.
Nguồn: [SDK](https://googleapis.github.io/python-genai/),
[model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[structured output](https://ai.google.dev/gemini-api/docs/structured-output).

## Credentials và API

File key giữ ngoài repository trong thư mục secrets riêng của tài khoản local.
Chỉ đưa key đã chọn vào `GEMINI_API_KEY` của process, không tự thử credential khác.
`from_environment()` truyền key tường minh cho Gemini Developer API; GOOGLE_API_KEY
không ghi đè lựa chọn. Không commit `.env` thật hoặc log SDK exceptions/prompt/response.
`.env.example` chỉ là mẫu; không tự load dotenv. Project identity unknown khi chưa mapping.

`GeminiAdapter(client, schema_registry=registry)` nhận mocked SDK client;
`GeminiAdapter.from_environment(schema_registry=registry)` tạo live client tường minh.
Không API call khi import. Caller đóng client bằng `adapter.close()`.

Đăng ký `LocalSchemaRegistry([(schema_ref, schema)])` với SchemaReference v1 và dict
JSON Schema ứng dụng duyệt. Inject cùng registry vào adapter và
`SharedLLMGateway({"gemini": adapter}, schema_registry=registry)` rồi gọi generate.
Ví dụ runnable đầy đủ: `scripts/smoke_gemini.py`; mặc định NOT_RUN, không tạo client.

## Mapping và trusted validation

- User/assistant → Gemini user/model, giữ ordered text parts. Leading system messages
  → system_instruction. Developer role, system xen giữa hoặc conversation chỉ system
  bị reject trước SDK để tránh đổi precedence.
- temperature (0..2), top_p, max_output_tokens, stop_sequences, seed map cùng tên SDK.
  Explicit null generation/timeout bị reject, omitted giữ omitted. Provider có thể
  reject capability của model khác. Timeout giây → millisecond, làm tròn lên.
- JSON dùng response_mime_type application/json và response_json_schema khi có ref.
  Registry dùng toàn identity/version/dialect, snapshot/copy schema; Draft 2020-12
  check_schema lúc đăng ký. Không external refs/$id đổi base URI, chỉ refs nội bộ #.
  Không fetch schema; unresolved refs trả safe schema error. Provider chỉ hỗ trợ subset
  JSON Schema, local valid không bảo đảm provider chấp nhận.
- Adapter parse raw JSON bằng contract parser, chỉ trả json_valid/unverified/invalid_json;
  không dùng SDK parsed hoặc tạo schema attestation. Gateway vẫn reject attestation
  từ transport, kiểm tra binding rồi tự chạy Draft202012Validator trên đúng payload/schema.
- Sau local validation mới tạo schema_valid/schema_invalid và SchemaValidation.
  Invalid JSON không chạy schema validator. Schema mismatch → malformed hoặc giữ
  partial, kèm schema_mismatch. Không repair JSON hoặc biến partial thành success.
  Gateway thiếu registry thì giữ unverified. Không trust dựa vào provider/validator ID.

## Usage, errors và giới hạn

Map prompt/candidates/total/cached/thoughts counters khi provider báo, không tự cộng
hoặc ước lượng. Giữ requested_model riêng provider-reported model_version. Cost unknown
khi chưa pricing. Metadata không hợp lệ bị từ chối.

STOP → success/malformed; MAX_TOKENS → partial; safety/blocklist/prohibited/SPII/
recitation hoặc prompt block → refused. Finish reason khác hoặc candidate/text không
hợp lệ → safe internal error; không xuất raw SDK object/diagnostics.

400 → invalid_request, 401 → authentication, 403 → authorization, 429 → rate_limit,
408/504 hoặc timeout exception → timeout, 5xx → provider_unavailable. Chỉ structured
reason QUOTA_EXCEEDED/DAILY_LIMIT_EXCEEDED trong error.details mới tách quota_exceeded;
không suy từ message/HTTP 429. GatewayError chỉ safe taxonomy/HTTP allowlist.
Retry attempts=1 cả client và request; SDK mặc định có retry. Không retry/key rotation/
fallback/cache; M1-08 xử lý pricing/budget/quota policies.

## Bounded smoke

Sau khi user xác nhận môi trường và chọn key, cấu hình process environment và chạy
`python scripts/smoke_gemini.py --allow-live`. Không flag/key thì NOT_RUN. Một request
synthetic, default model trên, timeout 30s, tối đa 256 output tokens. Runner gọi qua
Gateway, chỉ in status/category/validation/usage/cost; không raw text/key/project secret.
Không chạy runner trong CI hoặc tự retry. Đây không phải đánh giá chất lượng tài chính.
