# TASK MODEL-SERVE-01 — Colab T4 Qwen3-14B API Notebook

## Metadata

- Milestone: MODEL
- Status: REVIEW
- Priority: P1
- Dependencies: -
- Estimated Complexity: S
- Related Modules: notebook độc lập; không thay pipeline DACNTT

## Objective

Mở Colab → load Qwen3-14B-AWQ 4-bit → Start API → nhận HTTPS nếu khả dụng → Test.
Context mục tiêu 16384 trên T4, non-thinking và concurrency1. Chỉ static validation trong Codex.

## Context

Owner yêu cầu chuyển GGUF/llama.cpp sang vLLM, bỏ toàn bộ apt/build CUDA/backend cũ.
Cho phép commit/push main, bàn giao REVIEW để Owner chạy thử; không mở benchmark.
Lịch sử dual-model/GGUF và apt fix được giữ trong Git, không áp dụng cho bản AWQ này.

## Inputs

Qwen/Qwen3-14B-AWQ, revision 31c69efc29464b6bb0aee1398b5a7b50a99340c3;
metadata xác nhận Qwen3ForCausalLM/AWQ4/group128/float16, hai shard safetensors.
vLLM 0.10.2 (source AWQ min SM75), Python3.11 riêng qua uv0.9.5,
Transformers4.55.2/HFHub0.34.4; torch2.8/xformers theo dependency của vLLM.
Không tìm thấy qwen_vllm_api.ipynb trong repo; dùng source/docs vLLM và model chính thức.

## Outputs

[Notebook](../../../notebooks/colab_qwen_t4_api.ipynb), giữ path cũ theo yêu cầu Owner.
Cache: MyDrive/DACNTT/models/Qwen3-14B-AWQ; connection: MyDrive/DACNTT/api_info.json.

## Allowed Changes

Notebook và registry/current-status/spec; chỉ stage hunks thuộc task, giữ local edits.

## Out of Scope

Không pipeline M5/M6/M7/EF-EG, Gateway adapter, benchmark M8, model download/inference
trên máy Codex; không FP16 checkpoint hoặc quantize lại; không giữ Colab sống/vượt chặn.

## Implementation Steps

1. Thay GGUF/build bằng cài wheels vLLM vào Python riêng, cache snapshot AWQ nhiều files.
2. Start V0/XFormers/AWQ/half/eager, non-thinking template, readiness và lỗi VRAM rõ ràng.
3. Giữ HTTPS/auth/Drive connection và hai API tests; static check, commit/push REVIEW.

## Acceptance Criteria

- [x] Một model Qwen/Qwen3-14B-AWQ 4-bit; bỏ apt/llama.cpp/GGUF/build CUDA.
- [x] Pin vLLM0.10.2, Python3.11 riêng; chỉ wheels, không thay torch của notebook kernel.
- [x] Engine V0/XFormers, dtype half, AWQ, eager; context16K/concurrency1, không retry OOM.
- [x] Ưu tiên cache Drive riêng AWQ, copy local; thiếu thì tải snapshot đã pin và lưu lại.
- [x] Kiểm tra file sizes và AWQ config; không hash toàn bộ weights, không dùng cache GGUF cũ.
- [x] Non-thinking cố định trong official template và request; kiểm tra final content.
- [x] Server start/stop/readiness/timeouts/logs, HTTPS khi khả dụng và auth probe.
- [x] Tự lưu BASE_URL/API_KEY/MODEL_NAME vào api_info.json; key không hiển thị.
- [x] Test tiếng Việt/JSON, tokens/latency/output tok/s E2E/VRAM hoặc UNKNOWN.
- [x] Run all giữ API chạy; Stop riêng dừng server/tunnel; không đổi pipeline DACNTT.

Các criteria xác nhận code và logic tĩnh; chưa xác nhận Colab/T4/16K/API hoạt động.

## Required Tests

nbformat, AST/sequential names, Ruff lint/format; 3 static controls cho cache AWQ nhiều
files, official non-thinking Jinja template và flags theo pinned source. Planning/diff checks.
Không full suite, cài vLLM, weights, GPU, model API/tunnel execution hoặc benchmark trong Codex.

## Risks and Blockers

T4/16K và driver/wheels chưa thử thực tế; server dừng và báo log nếu VRAM/KV-cache không đủ.
Colab Free có thể chặn/kết thúc phiên; Quick Tunnel không SLA/SSE, client stream=false.
Public probe chỉ từ Colab, không chứng minh máy DACNTT truy cập được. Codex cần quyền
Drive/Drive sync để đọc connection; URL có thể stale sau runtime termination.
Cache size/config không xác minh cryptographic integrity. Không tự DONE hoặc thêm FIX loop.

## Implementation Evidence

AWQ implementation `20be7ca731cd1cc9cbc5ac2fdcd3a2244bc7f496`. nbformat/AST, Ruff và 3 static controls PASS local.
Metadata/source-only verification; chưa install vLLM hoặc tải weights/chạy model/GPU/tunnel.
Evidence ignored: artifacts/evidence/MODEL-SERVE-01/awq/.
GGUF lịch sử: 0d556d2/3f15270; không gán validation GGUF cho backend AWQ.
STATIC VALIDATED — NOT GPU TESTED.

## Handoff Notes

REVIEW, chờ Owner/Tech Lead nghiệm thu.
Next action: Owner mở notebook mới, chạy từ đầu trên Colab T4 và gửi log nếu lỗi.
