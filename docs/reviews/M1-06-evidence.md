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
- Git/CI implementation: **21d667c96fd8c9fe2ec593f0e486368df42018a5** /
  [CI 40460425395](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40460425395)
  success exact SHA; mọi steps Python 3.11/3.12 verified, mỗi job **929 passed,
  11 skipped**. User cho phép nghiệm thu theo CI ngày 27/10/2026: REVIEW → DONE,
  không cần review lại source hoặc lặp full local suite. Acceptance chỉ docs/planning.
- Limitations: no trusted schema engine (reject schema attestations), no Gemini/live
  provider, timer/retry/quota/budget/cache. Timeout do transport báo; fake chỉ synthetic.
  Contract-valid/request-bound khác schema-validated. Không đo chất lượng tài chính.
- Next action: Tech Lead chốt inputs và giao triển khai M1-07 (spec đã chuẩn bị, TODO).
