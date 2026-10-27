# M1-05 — Engineering evidence

## Phạm vi

User giao M1-05 ngày 2026-10-27, cho phép commit/push, dừng REVIEW.
Dependencies M1-02/M1-04 DONE. Baseline sạch e75413cf63302cbeaf8a4407e811f55f16e4d8b2
khớp origin/main, CI 40440918230 success exact SHA/từng step Python 3.11/3.12.
Chỉ provider-neutral contracts/validation, không live provider hoặc dữ liệu tài chính.

## Acceptance matrix

| Yêu cầu | Bằng chứng |
| --- | --- |
| Ownership và provider neutrality | core/llm_contracts.py, không business/SDK imports; ModelIdentity tách provider/model |
| Request/messages | Ordered roles/text, nonblank, explicit generation; missing/null/value, Unicode/long text tests |
| Structured semantics | TextOutput/JSONOutput; syntax parser không nâng schema_valid; explicit schema attestation và identity matching |
| Response/provenance | Status invariants, requested/effective/reported model riêng, nguồn metadata tường minh |
| Usage/cost | Unknown/not_available khác available-zero; không suy total; Decimal string và pricing provenance |
| Error/secrets | Fixed taxonomy/message, retryability/origin, provider-code allowlist, safe public parser không giữ input |
| Serialization/versioning | Strict/extra forbid, finite/Unicode/duplicate-key checks; snapshot revalidation, deterministic JSON |
| Schema | llm_gateway_v1.schema.json; export script và drift test; schema chỉ cấu trúc |
| Boundaries | Không sửa OCR/Understanding/Path Mapping hoặc runtime validators/recovery; không dataset/secrets/network |
| Task workflow | TODO → READY → IN_PROGRESS theo user giao; REVIEW sau gates/CI, không tự DONE/M1-06 |

## Local verification

- Targeted contracts: **142 passed, zero skips/warnings**, `pytest ... -q -W error`.
- Ruff check và format check: đạt, 99 files (bao gồm code examples trong Markdown).
- Planning checker: đạt, 75 tasks. Pip check: không broken requirements.
- Full unit suite final source: **910 passed, 2 skipped** trong 316,52 giây trên
  Python 3.12/Windows. Skips: filesystem không phân biệt case và FIFO không hỗ trợ.
  Không dùng lượt chạy cũ bị dừng trước khi snapshot serialization được chốt làm
  bằng chứng cho final source. Không warnings trong kết quả cuối.
- Git diff/staged allowlist/privacy: đạt, đúng 12 files, không credential patterns,
  private paths hoặc data artifacts; ignore rules cho data/raw, data/processed, .env đạt.
- Exact-SHA publication/CI: chờ push implementation; chưa chuyển REVIEW.

## Evidence artifacts

- [Contract documentation](../llm-gateway-contract.md)
- [Task specification](../../planning/tasks/M1/M1-05.md)
- [JSON Schema](../../schemas/llm_gateway_v1.schema.json)
- src/core/llm_contracts.py, scripts/export_llm_gateway_schema.py,
  tests/unit/test_llm_contracts.py.

## Giới hạn và review

Không schema validator thực thi, resolver refs, SDK, live inference, quota/cache hoặc
financial quality evaluation. Schema attestation là caller assertion có identity;
syntax-valid/unverified chưa schema-valid. Public parser mới là safe error boundary,
direct Pydantic error APIs không dùng để publish. Text/payload/opaque IDs vẫn cần caller
kiểm soát secrets; contract không phải DLP. Currency kiểm tra format, chưa ISO membership.
Provider SDK/model/live policy/pricing/quota/budget/capabilities/cache backend TBD.
M1-06..09 vẫn TODO; Tech Lead nghiệm thu M1-05 trước quyết định task tiếp theo.
