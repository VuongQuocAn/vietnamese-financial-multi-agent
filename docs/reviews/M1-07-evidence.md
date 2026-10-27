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
- Implementation **e66fd7efa886b69d38f6fc10840173cdb13166c1** /
  [CI 40462740086](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40462740086)
  success exact SHA, mọi steps Python 3.11/3.12 verified; mỗi job **967 passed/11 skipped**.
  User nghiệm thu REVIEW → DONE ngày 27/10/2026. Chỉ cập nhật docs/planning,
  không lặp local unit suite/live smoke. CI acceptance xác minh riêng sau push và báo cuối.
- Limitations: text v1/leading system; developer/interleaved system/null params reject.
  Provider subset JSON Schema; local không external refs/$id hoặc format checker tùy biến.
  Pricing/quota/budget thuộc M1-08, cache thuộc M1-09.
- Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M1-08.
