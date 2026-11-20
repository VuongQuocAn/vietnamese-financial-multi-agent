# AGENT-EFFICIENCY-01 — Specialist progress, lập kế hoạch và budget M6

**REVIEW**, 20/11/2026. Owner giao sau QWEN-E2E-05; main `ae215e737ae2d625c4288f4a0957281ece1f33c9`
+ local edits, chưa commit/push. Không đổi kết quả batch cũ hoặc dùng Gold để sửa.

Phạm vi: đọc đủ29 Specialist calls đã lưu, phân loại evidence/calculation/proposal/
lặp; sửa prompt phân rã theo nghĩa vụ bằng chứng; giữ Calculator history để Agent
tạo analysis; loop dùng budget tổng thay vì ép final theo số lượt mỗi task;
dự trữ calls/thời gian cho M6 trước execution và phân biệt budget với API failure.
LLM quyết định đủ dữ liệu/nội dung nhiệm vụ/claim; Python chỉ quản lý tiến trình,
budget, schema/DAG/provenance. Giữ nguyên mọi điều kiện M6/Ledger/M7 verification.

Criteria: audit29/29 có bằng chứng; tests offline trên tools/nguồn thật chứng minh
Agent final sớm được, vẫn thêm Tools khi thiếu và >3 calls khi còn budget; Calculator
history sống qua retrieval và tạo analysis đúng contract; M6 có calls/time reserve,
budget exhaustion khác provider failure. Không model/live QA/benchmark trong task.

Evidence và baseline incremental: `artifacts/evidence/AGENT-EFFICIENCY-01/`.

B?o c?o n?y ???c c?ng b? b?ng commit docs-only; runtime ???c m? t? v?n local,
ch?a commit/push. Raw traces/baseline ? local; b?ng audit ?? ??a v?o Git b?n d??i.

## Audit29 calls

Đã đọc29/29 raw request/response và tool results theo task của provider rerun,
không mở Gold để chọn sửa. Chi tiết từng call trong `specialist-calls.md/json`.

| Nhóm | Calls | Kết quả quan sát |
| --- | --- | --- |
| Thêm source handles | SH002/005, MH012/013, NR024 | 5 lượt; nguồn mới không đồng nghĩa đúng relevance |
| Calculator | NR025/028 | 2 lượt: percentage_of và ratio; có result, chưa có analysis claim |
| Tool không thêm source/phép tính | SH003/006/008/009; MH014/016/017/019/020; NR026/029/030/032 | 13 lượt; một số cache-only, một số tái thực thi ở task khác |
| Final | SH004/007/010; MH015/018/021; NR027/031/033 | 9 lượt;7 có raw proposals,2 rỗng; có proposals sai/lặp, không coi là9 claims mới |

SH Coordinator chọn bài toán định giá doanh nghiệp khác nghĩa vụ đọc giá trị
khoản đầu tư; trong code không có luật ép3 tasks, lỗi này là model planning.
MH lặp query với cùng document handles rồi đề xuất đoạn giới thiệu doanh nghiệp;
không có bằng chứng corpus thiếu dữ liệu. NR đã nhận2 facts và Calculator result,
nhưng các lượt lấy facts tiếp thay `tool_results`; final không thấy lịch sử ratio,
chỉ đề xuất operands. Có cả lỗi protocol `kind_or_meaning_mismatch`. Đây là mất
context ở implementation cộng với model chọn proposal chưa đáp ứng nhiệm vụ;
không tự suy rằng sửa context chắc chắn làm model trả đúng.

## Sửa chung

- Coordinator: prompt yêu cầu tách theo nghĩa vụ độc lập/phụ thuộc thực sự;
  một task có thể đọc nhiều số và dùng Calculator. Giữ goal/object/quan hệ của
  câu hỏi, không thay việc đọc số được báo cáo thành bài toán suy diễn. Python
  vẫn chỉ adapt/kiểm schema, references và lịch DAG; không luật SH/MH/QA/provider.
- Specialist: prompt ưu tiên final ngay khi đủ cho objective, dùng lại evidence/
  calculations/shared_tasks; chỉ yêu cầu Tool cho thiếu hụt cụ thể. Bỏ ép final
  ở turn4; chia budget M5 toàn request, không đặt cap2–3 calls/task. Giữ chốt
  sau cache-only/no-progress và khi chỉ còn1 generation call. Loop độc lập với
  RequestGateway dùng fallback16 lượt để vẫn hữu hạn, bằng default tổng request;
  production dùng max_calls đã cấu hình, không mở retry vô hạn.
- Calculator: task giữ `evidence_ids/operations/steps` qua mọi lượt và công bố
  lại ở `calculations`; shared_tasks nhận cả lịch sử trước khi có candidate.
  Agent tự viết `AnalysisProposal`/`derived_fact` theo schema hiện có. Python
  không tự tạo claim, đổi operator/operands, sửa final hoặc cho ACCEPT từ Tool.
- Budget: RequestGateway chia trước1/3 thời gian và `max(1,total_calls//3)`
  calls cho M6. Với cap12:1 Coordinator +7 Specialist dùng chung +4 M6 dự trữ.
  M5 HTTP timeout bị bound bởi generation deadline; M6 vẫn dùng deadline chung.
  Không bảo đảm mọi số lượng document candidates đều đủ4 calls; quá cap vẫn
  được từ chối có kiểm soát, không nới verification. Dự trữ có thể còn dư nếu
  không có candidates; đây là tradeoff cấu hình hiện tại, chưa tối ưu thực nghiệm.
- Diagnostics: gateway refusal trước HTTP dùng error `quota_exceeded` sẵn có,
  ghi `BUDGET_EXHAUSTED` riêng với actual calls count. Không tăng HTTP/unknown
  usage count từ request bị chặn. API không có released claims trả
  `budget_exhausted/BLOCKED/BUDGET_EXHAUSTED`, giữ nguyên provider failure thật.
  Có claims verified vẫn giữ partial output cùng diagnostics budget.

Không sửa cache xuyên task, source-selection replay, evidence mappings hoặc
các conditions M6/Ledger/M7. 13 lượt lặp là cơ hội cải thiện, không phải13 calls
đã tiết kiệm được. Chưa chạy model để đo savings/latency hoặc accuracy sau sửa.

## Quy mô và kiểm chứng

Incremental runtime **4 files,+96/−24 dòng**: `lite_orchestrator`+52/−22,
`request_gateway`+34/−2, API pipeline+9/−0, response contract+1/−0.
Không thêm runtime file/helper class/Agent/config flag. Abstraction mới duy nhất
là property đếm generation calls còn lại trong Gateway hiện có; dùng chung cho
enforcement và prompt, tránh thêm budget framework. Thêm nhánh reserve calls/time,
blocked diagnostic/status và ghi Calculator history; bỏ chốt turn4 và reserve1 call
cục bộ cũ. Giữ guards schema/provenance/số học/semantic/ledger như trước.

Ba hàm test mới (5 cases) dùng fake model responses, network bị chặn và Tools
trên persisted BKC_2024: allocation8 generation+4 verification/timeout reserve;
Agent final sau2 calls hoặc vẫn gọi Tools và final sau5 calls; Calculator history
sống qua2 lượt retrieval rồi Agent tạo ratio analysis; API budget khác provider
failure. Một expectation cũ cập nhật timeout→quota_exceeded cho gateway cap.
Lượt đầu fixture ratio chưa khai period_relation khác kỳ:1 FAIL/4 PASS; đã sửa
fixture, không đổi Calculator validator. Không dùng mocked verdict làm bằng
chứng chất lượng tài chính hoặc gọi đây là benchmark.

Kết quả:5 cases mới đều PASS qua các lượt; lượt validation sau sửa fixture
**13 PASS** (Calculator controls2 cases + controls giao thức hiện có + production
path nguồn thật→M6→Ledger→M7). Ba cases budget/API đã PASS ở lượt đầu, không chạy
lại. Smoke giữ2 facts supported và bác unsupported interpretation; không thay
quyền M6 bằng Python hoặc dùng benchmark Gold. Ruff lint/format và diff check
PASS; planning checker vẫn FAIL `CHAT-01/Status` có sẵn, không sửa task khác.
179 runtime files ngoài phạm vi, source/import JSON, benchmark inputs và frozen
QWEN-E2E-05 outputs giữ nguyên hashes; không stage/commit/push/model calls.

Giới hạn: prompt không bảo đảm LLM luôn đánh giá đúng sufficiency hoặc tạo plan
tối thiểu. Replay/controls không đo được số calls thực tế sau sửa; không công bố
savings/accuracy/latency hoặc benchmark-ready. Chưa thay cache xuyên task, chưa
sửa `selection_source_mismatch`; dự trữ M6 không vô hạn. Dừng ở REVIEW.

Next action: Tech Lead nghiệm thu thay đổi offline và quyết định có cấp phép live validation hay không.
