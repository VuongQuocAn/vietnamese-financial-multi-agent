# M1-06 — Evidence

- Scope: core synchronous gateway + injected callable transport, synthetic fake,
  binding snapshots, safe error mapping, giữ usage/cost/structured semantics v1.
  Không đổi contract/schema, không SDK/network/credentials/dataset.
- Baseline: b689cf47f67c7bc763e3dd566c08f1699bb01463, main/origin sạch;
  [CI M1-05 acceptance](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40459277293)
  success exact SHA và tất cả steps Python 3.11/3.12 verified trước triển khai.
- Local: targeted `tests/unit/test_llm_gateway.py`: **28 passed**, zero skips;
  Ruff lint/format, planning và diff check xác minh trước publication.
  Không chạy full local suite hoặc benchmark. CI giữ full tests/unit 3.11/3.12.
- Git/CI implementation: exact SHA, URL và kết quả được kiểm tra sau push và ghi
  báo cáo bàn giao cuối; không dùng CI baseline thay bằng chứng implementation,
  không tạo commit để nhúng SHA của chính nó. Checkpoint chứa file này là candidate
  REVIEW, chỉ sẵn sàng nghiệm thu khi CI exact SHA thành công.
- Limitations: no trusted schema engine (reject schema attestations), no Gemini/live
  provider, timer/retry/quota/budget/cache. Timeout do transport báo; fake chỉ synthetic.
  Contract-valid/request-bound khác schema-validated. Không đo chất lượng tài chính.
- Next action: Tech Lead review M1-06 sau CI; không tự DONE hoặc bắt đầu M1-07.
