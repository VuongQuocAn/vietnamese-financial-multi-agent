# M5-COORD-01 — Adaptive Coordinator & Task DAG

Ngày17/11/2026 (Asia/Bangkok). **REVIEW**, chờ Tech Lead; chưa nghiệm thu DONE.

Mở rộng `FinancialLiteOrchestrator` V2 dưới cờ request
`integration_v2=true, adaptive_coordinator=true` (default false).
Pipeline tự bật profile Lite như V2 hiện có; legacy/document/fusion routing,
M6 Verification và M7 Generation giữ nguyên. Không thêm framework/agent/Python,
feedback, repair, expansion hoặc selection/join records của task tiếp theo.

## Thay đổi

- Qwen chỉ sinh `goals:[{text,mode}]` và
  `tasks:[{goal_indexes,role,objective,input_handles,after}]`. Schema nhỏ và ví dụ
  nằm trong prompt; transport JSON mode qua Gateway, adapter Pydantic kiểm local.
  Không tuyên bố endpoint enforced schema hoặc constrained decoding đã được probe.
- Backend cấp G1…/T1… theo index gốc; giữ goal text và metadata chưa resolve.
  Tái dùng resolver/aliases trên trusted inventory. Period chỉ bind khi một kỳ
  nguồn phù hợp được xác định duy nhất; không tạo unit/formula từ tên file.
- Kahn scheduling ổn định theo goal/task; forward dependencies hợp lệ.
  Task sai/cycle/unknown ref và dependents bị chặn; không sửa index theo phỏng đoán.
  Envelope/goals sai không tạo kế hoạch thay thế; goal thiếu owner vẫn là gap.
- Retrieve và execute khi task ready; workspace giữ evidence dùng chung,
  result handle revision1, digest nội dung/nguồn/proof, dependency version refs,
  candidate IDs và tool-step IDs. Dependency phải có outputs thực tế, không chỉ
  status generated/partial. Kết quả rỗng/lỗi không xóa nhánh độc lập.
- Specialist sau nhận dependency result refs, statements/proofs và evidence IDs
  ổn định. Backend giữ source/citation/proof closure đầy đủ; prompt dùng projection
  hữu hạn. Calculator replay từ facts; candidates chưa có thẩm quyền verified.
  M6 vẫn tự quyết truth/goal support; M7 chỉ phát hành ledger có binding.
  Coverage kỹ thuật theo goal trong nhánh adaptive, giữ hành vi opt-out.

## Live Test có giới hạn

Ba câu mới do task tạo, không đọc benchmark/Gold; corpus thật đã import tại
`VFB-IMPORT-03/full-final`, nguồn refined JSON BBS2025/ADC2021. Không OCR/Gemini,
không chỉnh corpus, không sử dụng dữ liệu giả. Runner:
`scripts/run_m5_coordinator_live.py prepare|run`.
API/model/key lấy từ biến môi trường; không lưu key hoặc endpoint vào artifacts.

| Câu | Lượt | Kết quả | Calls / tokens | Ghi nhận |
| --- | --- | --- | --- | --- |
| SH01: doanh thu thuần BBS2025 | v1 | completed_with_caveats | 1 /3243 | 450.474.531.227 VND,6citations; planning Qwen, scalar specialists/verification deterministic |
| MH01: CFO trừ LNST BBS2025 | v1 | internal_error | 1 /3467 | Self-dependencies, tất cả closure bị chặn trước execution |
| MH02: CFO/doanh thu ADC2021 | v1 | internal_error | 2 /11053 | Hai task cycle bị chặn; task độc lập vẫn chạy nhưng chọn sai mẫu số,3ACCEPT toán học không có goal binding,0citation phát hành |
| MH01 giữ nguyên câu hỏi | v2 | completed_with_caveats | 3 /11696 | DAG hợp lệ,2specialist phối hợp,3ACCEPT với G1/G2/G3,12citations |

Tổng **7provider calls,29.459known tokens,0unknown usage**,153,964giây cộng wall
của bốn executions. Lượt đầu cap18, retest cap6; không retry model/benchmark rộng.
V1 có8graph responses found (SH6/ADC2); retest dùng evidence từ dependencies,
không truy xuất lại hoặc gọi graph. Đây là capability probe, không accuracy score.

Nguyên nhân tổng quát v1: prompt nói indexes nhưng thiếu mô tả field và ví dụ
multi-task; Qwen dùng `after:[1]` ở task index1 và `[2]` ở index2, tạo self-cycle;
gom nhiều scalar vào một goal và gán phép tính mode analysis. Sửa một lần bằng
field descriptions, ví dụ hai roots `after:[]` và consumer `after:[0,1]`, quy tắc
mỗi goal một output/phép tính dùng value. Không sửa DAG theo ý backend, không
hardcode doanh nghiệp/câu hỏi. Chỉ retest MH01 rồi dừng calls.

## Trace phối hợp đã quan sát ở v2

1. Qwen `provider/001.json`: ba value goals; T1 profitability nguồn S35,
   T2 cash_flow_and_earnings_quality nguồn S37, T3 cash_flow_and_earnings_quality
   `input_handles:[]`, `after:[0,1]`. Execution order T1→T2→T3.
2. T1 dùng `get_financial_fact` và `get_evidence_sources`, trả LNST
   7.249.557.946 VND, `E-0d41ed5660d39b71c2a5`, nguồn JSON trang7.
   `result:T1:v1`, digest
   `357ed4455c4d232e2dbff5b9428c93d2aced15ec9550124684c8951a370e1252`.
3. T2 gọi hai tools đó cho CFO14.319.681.754 VND,
   `E-6764d600e2efe8005216`, JSON trang8. Workspace của T2 đã nhận cả evidence T1.
   `result:T2:v1`, digest
   `5fe65ee269854cf657a569ab07982a14201550b09dd03612230c89fa1c8461f6`.
4. T3 không có tool-step mới; input_results pin cả hai handles/revision/digest.
   Request Qwen `provider/002-request.json` có `shared_tasks` chứa hai kết quả và
   `dependency_results` trỏ đúng phiên bản; response002 dùng đúng hai evidence IDs
   từ parents, operation `subtract(CFO,LNST)`, Calculator trả **7.070.123.808 VND**.
   Đây là consumption từ evidence do parents cung cấp, không chỉ khai dependency
   rồi mỗi specialist tự truy xuất cùng số. Model không ghi result handle vào
   prose goal; input/result lineage do backend lưu và proof/source IDs đối chiếu.
5. M6 deterministic replay và semantic call `provider/003.json` trả SUPPORTED
   cho calculation candidate `candidate:d26cf181245d6b0c90b5fd74`, support G3.
   Tổng3ACCEPT và binding G1/G2/G3 được admit vào ledger hiện có.
6. M7 render hai số liệu và chênh lệch cùng12source citations, coverage ba goals
   satisfied. Không gọi M7 model và không đổi logic Verification/Generation.

Full request/response, tasks/results/proofs, tools, M6 decisions, ledger và M7
ở local `artifacts/evidence/M5-COORD-01/live-v1/`, `live-v2/`; không commit raw
evidence/dataset. `implementation.json` pin mọi file runtime và questions manifest.
57source JSON hashes lượt đầu và24BBS hashes retest giữ nguyên. Runtime cuối
khớp toàn bộ receipt v2; initial SH/ADC dùng bản trước sửa prompt, không gán
kết quả của chúng thành retest bản cuối.

## Validation và hạn chế

`test_adaptive_coordinator.py`3controls + V2 compatibility18 = **21PASS** trên
worktree implementation cuối. Bao gồm forward dependency chạy trước retrieval
của consumer, cycle/unknown refs, nhánh exception, partial rỗng chặn consumer,
source/result closure, pipeline M6/M7 và opt-out. Ruff lint/format, planning
checker và diff check chạy local; không full CI/regression. Smoke synthetic
chỉ chứng minh engineering, không chất lượng tài chính.

Còn lại: chỉ một multi-hop retest thành công, chưa đo độ ổn định plan; Qwen v1
chọn sai source handles, ADC chưa retest. Một goal analysis không được thay bằng
phép tính đã ACCEPT. `complete` là coverage theo inventory model, không bảo đảm
không bỏ sót ý. Provenance vẫn JSON/page-level, chưa PDF-verified; citations có
thể lặp. T3 có output hợp lệ nhưng status partial vì graph không có starting node
trong retrieval bundle riêng; không làm mất output/M6/M7. Result chỉ revision1,
chưa invalidation/patch/demand retrieval hoặc reuse interpretation đã ACCEPT.
Những phần này giữ ngoài scope, không mở task kế tiếp.

Git: implementation trên worktree riêng sau merge histories đã commit
`f3c326b`, bảo toàn toàn bộ local edits ngoài task; không đưa freeze VFB-E2E-05
vào commit mới. SHA implementation được ghi trong spec sau commit và được
đối chiếu receipt trước push main.

**Next action:** Tech Lead review M5-COORD-01 và bằng chứng phối hợp v2.
