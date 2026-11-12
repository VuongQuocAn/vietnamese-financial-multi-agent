# TASK MODEL-SERVE-01 — Colab T4 Qwen3-8B API Notebook

## Metadata

- Milestone: MODEL
- Status: REVIEW
- Priority: P1
- Dependencies: -
- Estimated Complexity: S
- Related Modules: notebook độc lập; không thay pipeline DACNTT

## Objective

Mở Colab → load Qwen3-8B-AWQ 4-bit → Start API → HTTPS nếu khả dụng → Test.
Context mặc định24576, non-thinking/concurrency1; chưa xác nhận24K trên T4.

## Context

Owner yêu cầu chuyển từ14B sang8B/24K ngày12/11/2026; cho phép commit/push main.
Owner đã báo14B/8K chạy được; giới hạn KV8512 và lỗi shared memory trước thuộc14B.
Giữ lịch sử14B/GGUF trong Git; không gán kết quả đó cho model8B.

## Inputs

Qwen/Qwen3-8B-AWQ, revision4da05a8edb55c6046cce958586c33b61da07bb79;
manifest9 files,2 shards safetensors tổng6098581864 bytes, config AWQ4/group128.
max_position_embeddings40960; đây là config model, không chứng minh T4 đủ VRAM cho24K.
Giữ vLLM0.10.2/Python3.11/Transformers4.55.2/HFHub0.34.4 và V0/XFormers đã chọn.

## Outputs

[Notebook](../../../notebooks/colab_qwen_t4_api.ipynb), giữ path cũ theo Owner.
Cache MyDrive/DACNTT/models/Qwen3-8B-AWQ riêng, không xóa cache14B.
Connection MyDrive/DACNTT/api_info.json, MODEL_NAME=qwen3-8b-awq-t4.

## Allowed Changes

Notebook và registry/current-status/spec; chỉ stage hunks thuộc task, giữ local edits.

## Out of Scope

Không pipeline M5/M6/M7/EF-EG, Gateway adapter, benchmark M8, model download/inference
trên máy Codex; không FP16 checkpoint hoặc quantize lại; không giữ Colab sống/vượt chặn.

## Implementation Steps

1. Đổi repo/revision/alias/context và manifest8B theo HF metadata, không weights download.
2. Dùng lại vLLM/lifecycle/HTTPS/info/test, giữ workaround T4, không thêm framework.
3. Static checks, commit/push REVIEW; Owner chạy Colab thực tế.

## Acceptance Criteria

- [x] Một model Qwen/Qwen3-8B-AWQ 4-bit; bỏ apt/llama.cpp/GGUF/build CUDA.
- [x] Pin vLLM0.10.2, Python3.11 riêng; chỉ wheels, không thay torch của notebook kernel.
- [x] Engine V0/XFormers, dtype half, AWQ, eager; context24K/concurrency1, không retry OOM.
- [x] Ưu tiên cache Drive riêng AWQ, copy local; thiếu thì tải snapshot đã pin và lưu lại.
- [x] Kiểm tra file sizes và AWQ config; không hash toàn bộ weights, không dùng cache GGUF cũ.
- [x] Non-thinking cố định trong official template và request; kiểm tra final content.
- [x] Server start/stop/readiness/timeouts/logs, HTTPS khi khả dụng và auth probe.
- [x] Tự lưu BASE_URL/API_KEY/MODEL_NAME vào api_info.json; key không hiển thị.
- [x] Test tiếng Việt/JSON, tokens/latency/output tok/s E2E/VRAM hoặc UNKNOWN.
- [x] Run all giữ API chạy; Stop riêng dừng server/tunnel; không đổi pipeline DACNTT.

Các criteria xác nhận code và logic tĩnh; chưa xác nhận Colab/T4/16K/API hoạt động.

## Required Tests

nbformat, AST/sequential names, Ruff lint/format; 2 static controls cho repo/revision/manifest/cache/alias8B, official non-thinking
Jinja template và command budget24K. Giữ các server flags đã đối chiếu source vLLM. Planning/diff checks.
Không full suite, cài vLLM, weights, GPU, model API/tunnel execution hoặc benchmark trong Codex.

## Risks and Blockers

T4/24K và driver/wheels chưa thử thực tế; server dừng và báo log nếu VRAM/KV-cache không đủ.
Colab Free có thể chặn/kết thúc phiên; Quick Tunnel không SLA/SSE, client stream=false.
Public probe chỉ từ Colab, không chứng minh máy DACNTT truy cập được. Codex cần quyền
Drive/Drive sync để đọc connection; URL có thể stale sau runtime termination.
Cache size/config không xác minh cryptographic integrity. Không tự DONE hoặc thêm FIX loop.

## Implementation Evidence

8B/24K implementation `b8d3cc9072a333b52dea702093cd98b28b38dbaf`. nbformat/AST/sequential names, Ruff và2 static controls PASS local.
Planning/diff checks PASS; không model download/install vLLM/GPU/API/tunnel execution trong Codex.
Metadata HF-only xác minh files/config/tokenizer. Evidence ignored: artifacts/evidence/MODEL-SERVE-01/8b/.
14B lịch sử:20be7ca/66f16ef/7eb7ee5; Owner báo8K chạy được, không suy8B/24K PASS.
STATIC VALIDATED — NOT GPU TESTED.

## Handoff Notes

REVIEW, chờ Owner/Tech Lead nghiệm thu.
Next action: Owner chạy notebook mới từ cấu hình đến Test API trên Colab T4 và gửi kết quả/log8B/24K.
