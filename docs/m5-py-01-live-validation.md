# M5-PY-01 — Python Agent

Trạng thái **DONE — Owner xác nhận hoàn thành ngày17/11/2026**.
Baseline local `9a3adba`, đã tích hợp
remote main `83c21dc` trước release; giữ local edits ngoài task trong worktree gốc.
Implementation `7992105dcbf8718222d6fc7e2220224256451830` đã push main, xác minh
remote cùng SHA; không thay M6/M7. Bàn giao REVIEW tại `461afd4` trước nghiệm thu.
Giữ các giới hạn đã báo; phiên đóng chỉ tài liệu/tracking và planning/diff/Git,
không sửa runtime hoặc chạy lại tests/API/benchmark.

Coordinator dùng optional `python_requirement` cho primitive ngoài Calculator;
backend đối chiếu cả câu hỏi gốc và objective. Gate bảo thủ theo tên capability,
chưa phải bộ chứng minh tính biểu đạt của mọi công thức. Các phép tính thông
thường tiếp tục dùng Calculator. Consumer computational dùng operands đã truy
xuất của dependencies, không cần model đoán lại source handles.

`PythonAgent` gọi Gateway chung, nhận `{code,outputs,computation,constants}`.
Backend pin toàn bộ tool-returned observations: identity/digest, raw/normalized
value, scale, context/kỳ/unit, selectors/citations, quality/issues. `data[handle]`
là Decimal đơn vị cơ sở, scale áp đúng một lần; không nhận operands do model tạo.
Literals bị AST precheck giới hạn và constants phải khai purpose; ý nghĩa công
thức/constants/unit vẫn cần M6 kiểm, không được coi là authority.

`tasks[task_id].python_candidate` và result record cùng giữ
`python_execution_proof_v1`: code/hash, input manifest/digest, proposed units,
constants/computation, versions/status/results/traceback, worker identity và Gateway
responses/usage. Lineage là toàn bộ manifest, không giả lập tracing từng biến.
Record giữ `candidate`, `financial_fact_verified=false`, `requires_M6-PY-01`;
không chuyển thành v1 CandidateClaim, không ghi Python result vào verified ledger.
Code error được sửa tối đa một lần, dùng cùng inputs; tiêu thụ repair budget
chung của Workspace. Timeout/OOM/output-limit/provider/schema lỗi không retry.

Worker Docker Linux/WSL2: image bất biến, user65534, network none, không host
mounts/socket/credentials, read-only, cap-drop ALL, no-new-privileges, seccomp;
1CPU/256MiB/swap0/32PIDs,10s execution,12KiB code/256KiB input/64KiB output.
Preflight chạy trusted probe kiểm UID/caps/seccomp/interfaces/cgroup; inspect
kiểm mounts/network/read-only. Cleanup xóa container kể cả timeout; lỗi cleanup
không trả success. Không có host fallback hoặc pull/package install trong request.

Live dùng JSON/EF-EG BBS2025 đã import, không Gold/PDF/OCR/Gemini. Tổng
**14 actual Qwen calls,73562 tokens,0unknown,0transport retry**; không gọi tiếp.

| Câu/probe | Kết quả thực tế |
| --- | --- |
| RMS doanh thu2024/2025 | Qwen tự lập DAG, hai root retrieve nguồn → consumer chọn sqrt → code chạy Docker thành công: `405778754393.2543044639216769104146 VND`. Hai operands `355507372286` và `450474531227`, nguồn trang7, `/blocks/3/table/rows/2/5` và `/blocks/3/table/rows/2/4`. |
| Giá vốn/doanh thu2025 theo% | Live model chọn power sai; backend giữ Calculator. Completion dùng lại nguyên saved plan, chỉ thêm1call cho specialist chưa chạy: divide ra `0.9278926611466262138573953017875971 ratio`, không Python. Model thêm multiply với literal handle `100` không hợp lệ, nhánh đó bị loại; chưa đáp ứng đầy đủ yêu cầu%. Control Calculator `percentage_of` trên cùng source operands ra `92.78926611466262138573953017875971 percent`. Không gọi kết quả control là live model PASS. |
| Độ lệch chuẩn tổng thể hai doanh thu | Lượt đầu code có import bị chặn → gửi traceback → Qwen sửa1lần vẫn import → dừng đúng2executions, cùng input digest. Retest chạy đúng `47483579470.5 VND` nhưng model gán `diagnostic_missing=1`, không tạo NameError yêu cầu; không tuyên bố live repair thành công. |

Lượt đầu7calls: hai consumer vướng demand dùng task handle thay source handle;
diagnostic hai executions đều lỗi import. Sau prompt/data-shape/gate fix, retest
6calls: RMS và dispersion chạy được; Calculator vẫn vướng redundant demand.
Final dependency-operand reuse sửa đường này; completion1call dùng nguyên plan
đã lưu, không chạy lại toàn câu. `live-v1` chỉ lỗi cấu hình timeout trước API:0calls.

Evidence local ở `artifacts/evidence/M5-PY-01/`: `live-v2/` (7calls),
`live-final/` (6calls), `calculator-completion/` (1call),
`validation-summary.json`. Final completion receipt khớp **183 runtime files**;
RMS code được chạy lại trong cùng worker trên final runtime và khớp results.
Arithmetic controls khớp công thức câu hỏi,24JSON nguồn giữ nguyên qua mọi run.
Đây là engineering/capability evidence, không phải M6 independent verification
hoặc chứng nhận financial/PDF accuracy. Provenance giữ JSON-only/page-level limits.

Targeted final: **11PASS,1deselected** trong Python/Coordinator/evidence/feedback
controls; đúng3tests mới, gồm Docker execution/timeout/cleanup/unavailable,
repair bound/input digest và candidate boundary/shared repair budget.
Smoke cũ `test_pipeline_flag_keeps_existing_m6_m7_and_opt_out` fail do thiếu
goal binding; đã tái hiện cùng failure trên baseline `83c21dc`, không sửa ngoài
scope. Ruff/planning/diff check đạt; không full suite/CI thủ công/frontend build.

Thiết lập local, không cần credentials trong worker:

```powershell
docker build -f configs/python-worker.Dockerfile -t financial-python-worker:m5-py-01 .
$env:PYTHON_WORKER_IMAGE = docker image inspect financial-python-worker:m5-py-01 --format '{{.Id}}'
```

Đặt biến này trong process chạy API và bật `integration_v2`/`adaptive_coordinator`
hiện có. Image base pin digest trong Dockerfile; image thực nghiệm
`sha256:73c636a1fd573b2ef90b57d98de19e7b7c9cad5e248d52791dc38688086b4687`.
Chưa có image/config/preflight hợp lệ trả `python_unavailable`, Calculator vẫn dùng được.

Next action: chờ Owner giao nhiệm vụ tiếp theo; không tự bắt đầu M6-PY-01.
