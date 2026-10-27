# M1-07 — Evidence

- Scope: google-genai **2.33.0** adapter, jsonschema **4.26.0** Draft 2020-12 local
  registry và Gateway validation sau binding; llm_gateway_v1/schema không đổi.
  No retry/key rotation/quota/cache; key ngoài Git, chỉ process environment.
- Baseline main/origin sạch **f29baea90baf1cc5d4ed61dceb4faad29876d250** /
  [CI 40461193406](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40461193406)
  success. M1-05/M1-06 DONE; user giao triển khai và dừng REVIEW.
- Local targeted adapter/gateway **66 passed**, zero skips; Ruff/planning/diff kiểm tra trước publication.
  Full unit suite chỉ trên CI Python 3.11/3.12; không live API trong CI.
- Live smoke **PASS**: đúng **1 request, 1 key user chọn (thứ 1)**, model
  gemini-3.5-flash-lite; success, trusted local schema_valid; provider usage
  input=11/output=9/total=20; cost unknown; project identity unknown.
  Synthetic prompt, limit 256 output tokens, timeout 30s; không retry/fallback/raw output.
- Implementation SHA/CI exact kiểm tra sau push và ghi báo cáo cuối, không tự tham
  chiếu commit. Candidate REVIEW chỉ sẵn sàng sau CI exact SHA thành công.
- Limitations: text v1/leading system; developer/interleaved system/null params reject.
  Provider subset JSON Schema; local không external refs/$id hoặc format checker tùy biến.
  Pricing/quota/budget thuộc M1-08, cache thuộc M1-09.
- Next action: Tech Lead review M1-07 sau CI; không tự DONE.
