# TASK MODEL-CTX-01 — LLM Context Profiling & Token Budget for Colab T4

## Metadata

- Milestone: MODEL
- Status: REVIEW
- Priority: P1
- Dependencies: CORE-PERIOD-01
- Estimated Complexity: S
- Related Modules: offline profiling, Gateway adapter inventory; không runtime changes

## Objective

Đo từng provider-facing request và chọn context/output budgets để thử model 4-bit
trên Colab T4, dựa trên traces thực tế; phân biệt token-fit với GPU feasibility.

## Context

Owner giao spec MODEL-CTX-01 ngày 11/11/2026. CORE-PERIOD-01 được nghiệm thu DONE
có giới hạn. Hệ thống Gemini M5/M6/M7 và EF-EG giữ nguyên.

## Inputs

Owner spec lưu tại ignored `artifacts/evidence/MODEL-CTX-01/owner-task.md`.
Traces CORE-PERIOD-01, EF-CORE-03/02 và CORE-FLOW-01; tokenizer/config chính thức
Qwen3-14B, Qwen3-8B, Llama-3.1-8B-Instruct; không model weights.

## Outputs

[Báo cáo](../../../docs/model-ctx-01-llm-context-profiling.md), script reproducible,
tests và artifacts ignored: inventory/payload hashes, per-call/per-component token
counts, sample percentiles, fit matrix 8K/16K/32K, VRAM estimates và budgets.

## Allowed Changes

Profiling script/tests, report và planning/checker để nhận task MODEL-CTX-01;
thêm targeted tests vào CI hiện có. Ghi nhận nghiệm thu CORE-PERIOD-01.
Commit/push main đúng phạm vi theo Owner spec; giữ local edits khác.

## Out of Scope

Không M5/M6/M7/EF-EG changes, sửa prompts, model serving/API, weights, Gemini live,
OCR/extraction, dataset writes hoặc M8. Không tự DONE task này.

## Implementation Steps

1. Inventory trực tiếp call sites, execution modes và adapter wrappers.
2. Tái dựng provider payload từ captured requests; hash và giữ nguồn read-only.
3. Đếm tokenizer/chat template theo model; output reserve theo stage, margin 10%.
4. Phân tích Graph ON/OFF, components, context overflow và VRAM theo architecture.
5. Targeted checks, commit/push và xác minh CI đúng implementation SHA; bàn giao REVIEW.

## Acceptance Criteria

- [x] Inventory M5/M6/M7 và legacy modes; có provider-facing reconstructed samples.
- [x] Per-agent/model token counts, output reserve, P95/max và fit matrix riêng từng call.
- [x] Graph/component analysis và giới hạn causal attribution được ghi rõ.
- [x] VRAM đúng architecture, stage budgets và đề xuất 8B/16K để thử GPU thật.
- [x] Llama tokenizer gated ghi unavailable, không bịa counts/tokenizer thay thế.
- [x] Không runtime/model API/weights/data changes; source hash unchanged.
- [x] CI SUCCESS đúng implementation SHA.
- [ ] Tech Lead review các limitations.

## Required Tests

Ba targeted tests cho template/adapter, per-call budget/missing counts và KV/components;
actual local Qwen deterministic/template smoke; Ruff/planning/diff. Không full regression.

## Risks and Blockers

Llama gated là limitation được spec cho phép, không chặn Qwen. Provider SDK wire
capture gốc không có; adapter reconstruction exact text, hidden Gemini overhead unknown.
Historical samples không đại diện mọi workload; chưa GPU/financial-quality evaluation.

## Implementation Evidence

Implementation SHA: [8b78f34](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/8b78f342433d639c09425e0cf513b6e14b82b3c5); [CI 42995134599](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42995134599) SUCCESS đúng implementation SHA; 234 Python PASS, Web/full regression SKIPPED. 20 scenarios/61 logical calls; Qwen 14B/8B cùng
tokenizer hash, 17 overflow/2 near tại 8K; 61 FIT tại 16K và 32K non-thinking.
M7 multi-specialist input lớn nhất 8.886, reserve 4.096. Llama UNKNOWN toàn bộ.
Ba targeted tests + bốn actual tokenizer checks PASS; Ruff/planning/diff PASS.
Local và CI tách riêng; không GPU/financial-quality claim.

## Handoff Notes

Next action: Tech Lead review MODEL-CTX-01 và quyết định task Colab serving.
