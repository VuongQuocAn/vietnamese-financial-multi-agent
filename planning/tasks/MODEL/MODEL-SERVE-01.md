# TASK MODEL-SERVE-01 — Colab T4 Qwen3-14B API Notebook

## Metadata

- Milestone: MODEL
- Status: REVIEW
- Priority: P1
- Dependencies: -
- Estimated Complexity: S
- Related Modules: notebook độc lập; không thay runtime DACNTT

## Objective

Mở Colab → Run all → chuẩn bị Qwen3-14B GGUF Q4_K_M → nhận API nếu môi trường cho phép.
Context mục tiêu 16384 trên T4; chưa xác nhận GPU/16K hoặc external API hoạt động thực tế.

## Context

Owner yêu cầu đơn giản hóa ngày 11/11/2026, cho phép commit/push main và bàn giao REVIEW.
Chỉ hỗ trợ Qwen3-14B, bỏ lựa chọn Qwen3.5 và full-file SHA-256 model mỗi lần chạy.
Yêu cầu mới thay phạm vi dual-model/local-only trước đây; giữ lịch sử implementation cũ.

## Inputs

Qwen/Qwen3-14B-GGUF, file Qwen3-14B-Q4_K_M.gguf, revision
530227a7d994db8eca5ab5ced2fb692b614357fd; size 9001752960 xác minh qua metadata.
llama.cpp pin cd959bae99ff4bed22bef2604f45241c09bbb8c8; cloudflared pin 2026.10.7.
Không tìm thấy qwen_vllm_api.ipynb trong thư mục dự án; tham chiếu docs chính thức
Cloudflare Quick Tunnel và Colab được liên kết trong notebook.

## Outputs

[Notebook](../../../notebooks/colab_qwen_t4_api.ipynb): chuẩn bị GPU/Drive, cache/build,
Start API, Test API và Stop thủ công. Colab tự tạo MyDrive/DACNTT/api_info.json
chứa BASE_URL/API_KEY/MODEL_NAME và status/timestamp; không commit file secret này.

## Allowed Changes

Notebook và ba tài liệu tracking liên quan; commit/push main đúng hunk thuộc task.
Tự chọn implementation phù hợp theo yêu cầu Owner; dùng lại pinned CUDA backend.

## Out of Scope

Không pipeline M5/M6/M7/EF-EG, Gateway adapter, benchmark M8, weights/GPU execution
trong Codex, FP16 downloads, lượng tử hóa lại hoặc cơ chế giữ Colab sống/vượt chặn.

## Implementation Steps

1. Giữ một model/cache nhẹ, giới hạn tùy chọn context và HTTPS.
2. Start server có key, thử tunnel HTTPS và kiểm tra public route trước khi lưu URL.
3. Hai smoke tests, static validation, commit/push và bàn giao Owner thử Colab.

## Acceptance Criteria

- [x] Notebook hợp lệ, code parse được, không có execution outputs/secrets hardcoded.
- [x] Một Qwen3-14B GGUF Q4_K_M; mặc định 16K, fallback 8K do Owner chọn khi OOM.
- [x] Ưu tiên Drive, copy local; chưa có thì tải HF; chỉ kiểm tra size/GGUF header của weights.
- [x] CUDA build pin/reuse, GPU offload, readiness/timeout/logs và dừng process sở hữu.
- [x] OpenAI-compatible non-thinking server có API key; thử Cloudflare HTTPS khi được bật.
- [x] Chỉ lưu URL HTTPS sau probe model alias và xác nhận thiếu key bị từ chối.
- [x] Tự lưu api_info.json trên Drive; không in key; LOCAL_ONLY có BASE_URL null.
- [x] Hai test tiếng Việt/JSON và latency/tokens/tốc độ/VRAM hoặc UNKNOWN.
- [x] Run all giữ API chạy; Stop riêng vô hiệu URL và dừng server/tunnel.
- [x] Không thay pipeline DACNTT hoặc chạy weights/build/tunnel/GPU trong Codex.

Các criteria trên xác nhận cấu trúc/logic tĩnh, không phải kết quả thực thi Colab.

## Required Tests

nbformat schema, AST/sequential names, Ruff lint/format; ba offline controls:
cache header/size không full hash, api_info READY/LOCAL_ONLY/STOPPED, final-content/JSON.
Đối chiếu HF metadata/backend/tunnel docs; planning checker và git diff --check.

## Risks and Blockers

T4/16K chưa GPU tested; Colab có thể kết thúc phiên/chặn tunnel. Quick Tunnel đổi URL,
không SLA/SSE; client phải stream=false. Public route chỉ probe từ Colab, chưa từ máy DACNTT.
Codex cần kết nối/quyền đọc Drive hoặc Drive sync để lấy api_info.json; mount Colab
không tự chia sẻ filesystem với Codex. File có thể stale nếu runtime bị ngắt đột ngột;
client cần kiểm tra models trước khi dùng. Cache size/header không chứng minh toàn vẹn hash.

## Implementation Evidence

Implementation sửa theo Owner: `0d556d2c23ecbdbeb732cec5740d78af324b668e`; static checks ở trên PASS local.
Implementation đầu `34beda90f98262107696bfe6cc958d5a8850b320` được giữ trong lịch sử.
Evidence offline ignored: artifacts/evidence/MODEL-SERVE-01/simplify/.
Không weights/model calls/build/Colab/GPU/tunnel execution hoặc full suite/CI run trong phiên này.
STATIC VALIDATED — NOT GPU TESTED.

## Handoff Notes

REVIEW, chờ Owner/Tech Lead nghiệm thu; không tự DONE.
Next action: Owner mở notebook trên Colab Free, chạy các cell và gửi log nếu lỗi.
