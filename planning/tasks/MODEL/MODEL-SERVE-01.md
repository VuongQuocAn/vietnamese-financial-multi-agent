# TASK MODEL-SERVE-01 — Google Colab T4 Notebook for Qwen3.5-9B / Qwen3-14B 4-bit

## Metadata

- Milestone: MODEL
- Status: REVIEW
- Priority: P1
- Dependencies: -
- Estimated Complexity: S
- Related Modules: notebook độc lập; không thay runtime DACNTT

## Objective

Notebook Colab Free chọn một GGUF Q4_K_M, cache Drive, start local API và test tương tác.
Chỉ tạo notebook; không triển khai/chạy model trong Codex.

## Context

Owner giao task ngày 11/11/2026, cho phép commit/push main đúng phạm vi.
STATIC VALIDATED — NOT GPU TESTED; chưa xác nhận GPU inference/context/API.

## Inputs

Owner spec; metadata Hugging Face của axteam/Qwen3.5-9B-GGUF và Qwen/Qwen3-14B-GGUF;
source llama.cpp v0.9.0 pin cd959bae99ff4bed22bef2604f45241c09bbb8c8.
Notebook chứa source links và model revision/size/SHA-256 xác minh từ LFS metadata.

## Outputs

[Notebook](../../../notebooks/colab_qwen_t4_api.ipynb), bốn phần tiếng Việt và Colab forms.

## Allowed Changes

Notebook, registry/current-status/dashboard/spec và checker nhận task ID MODEL-SERVE.
Stage riêng các hunk mới khi planning có local edits; không commit local edits ngoài task.

## Out of Scope

Không weights/GPU inference/Colab execution, Gateway adapter, M5/M6/M7/EF-EG,
benchmark M8, vision encoder, quantize lại, FP16 download hoặc public tunnel.

## Implementation Steps

1. Xác minh filenames/revisions/LFS hashes và backend source/arguments.
2. Tạo notebook: config/GPU, Drive/local cache, CUDA server và API tests.
3. Kiểm tra tĩnh, planning/diff; commit/push main và bàn giao REVIEW.

## Acceptance Criteria

- [x] Notebook hợp lệ, code cells parse được, không có execution outputs.
- [x] Dropdown hai model, mặc định Qwen3.5-9B; Q4_K_M và context 16K/8K.
- [x] GPU/runtime/disk checks; không âm thầm CPU-only.
- [x] Drive cache riêng từng model, header/size/hash và download fallback.
- [x] Pinned CUDA source build, SM75 trên T4, reuse binary khi hợp lệ.
- [x] Start/stop process sở hữu, timeout/readiness/logs, offload/API probes.
- [x] Local OpenAI-compatible API; non-thinking parameter và final-content checks.
- [x] Vietnamese QA, JSON numeric checks, financial 20%, optional tokenizer-counted long context.
- [x] Usage/latency/VRAM/timing báo UNKNOWN khi không được backend cung cấp.
- [x] Connection template phân biệt local/external; không giả public URL/key.
- [x] Không tải weights/chạy backend/inference, không đổi runtime DACNTT.

Các dấu trên xác nhận cấu trúc/logic tĩnh; Owner vẫn phải thử thực tế trên Colab.

## Required Tests

nbformat schema; AST parse tất cả code cells và sequential name analysis;
offline helper controls cho cache integrity, JSON/final content, long-context budget;
đối chiếu flags/API với pinned source và model IDs/files với HF metadata;
planning checker và git diff --check. Không full project suite/CI/GPU smoke.

## Risks and Blockers

GPU availability, Colab CUDA toolkit/build, architecture load, 16K VRAM và API inference
chưa chạy thực tế. Drive filesystem free-space không bảo đảm phản ánh account quota;
copy failure fallback sang local. Không có external endpoint để máy Codex gọi.

## Implementation Evidence

Implementation SHA: `34beda90f98262107696bfe6cc958d5a8850b320` (đã xác minh và push main).
Static validation PASS tại môi trường Codex; evidence local ignored tại
`artifacts/evidence/MODEL-SERVE-01/`. Không tải weights hoặc chạy GPU/API inference.
Static helpers không chứng minh financial accuracy hoặc GPU feasibility.

## Handoff Notes

REVIEW, chờ Project Owner/Tech Lead nghiệm thu; không tự DONE hoặc mở FIX task.
Next action: Project Owner mở notebook trên Colab Free, chọn model và chạy thử.
