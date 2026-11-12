# QWEN-GEN-01 — Kiểm thử tổng quát hóa với Qwen

Ngày 12/11/2026. **PAUSED — WAITING FOR OWNER**. Baseline
`cbc307733fc76a92f0def390fd4cee11e9b9b8eb`. Chưa hoàn thành evaluation.

## Cấu hình và preflight

Qwen3-8B-AWQ, alias `qwen3-8b-awq-t4`, qua SharedLLMGateway; pipeline dự kiến
M5 Lite → EF-EG/Financial Tools → M6 Lite → M7 Lite như QWEN-QA-01.
Dùng current config ignored đã có; không đổi URL/key/model. Working tree có
local edits/dependencies từ trước, không phải pristine baseline. Không sửa runtime.

Factory mặc định ban đầu báo `qwen_configuration_invalid` vì thiếu config mặc định,
chưa gửi request. Sau khi tìm đúng current config đã có, gửi đúng **một** request
`Reply OK.` lúc **18:29:26 Asia/Bangkok** qua Gateway. Temperature=0, top_p=1,
max_output_tokens=8, stop_sequences=[], timeout=30s, enable_thinking=false.
Đây là preflight, không phải case evaluation hoặc cấu hình inference đã freeze.

Kết quả: `error/provider_unavailable`, origin=`adapter`, HTTP status không có;
latency **0,094s**, token usage/cost **UNKNOWN**. Adapter chuẩn hóa lỗi nên chưa
phân biệt DNS/connection/TLS từ trace; không khẳng định Colab đã tắt.
Dừng ngay, không retry/request chẩn đoán/fallback/đổi endpoint hoặc model.

## Câu hỏi và reference

Dừng trước khi chuẩn bị/freeze bộ câu hỏi theo mục 3 của task. Các ID sau chỉ là
slots theo phân bổ đề xuất, chưa phải câu hỏi hoàn chỉnh. Question, company,
document, period, difficulty, expected answer/abstention, required points,
evidence refs, formulas/operands đều **TBD**. Không tạo reference giả.
Khi resume phải chọn câu từ PDF/evidence hiện có, không dùng lại hai câu QWEN-QA-01,
và cố định reference độc lập trước bất kỳ case inference nào.

## Kết quả từng case

| IDs | Nhóm | Số câu | Trạng thái từng case |
| --- | --- | ---: | --- |
| Q01, Q02, Q03, Q04, Q05 | Single-hop | 5 | NOT_RUN |
| Q06, Q07, Q08, Q09, Q10 | Multi-hop/cross-year | 5 | NOT_RUN |
| Q11, Q12, Q13, Q14, Q15 | Numerical | 5 | NOT_RUN |
| Q16, Q17, Q18, Q19, Q20 | Interpretation | 5 | NOT_RUN |
| Q21, Q22, Q23, Q24, Q25 | Unanswerable | 5 | NOT_RUN |

Case cuối thành công: **không có**. Hoàn thành **0/25**, chưa chạy **25/25**.
Final answer, agents, tools/results, claims, M6 verdicts, M7 status, citations:
**N/A**, pipeline chưa được gọi. Provider attempts: **1 preflight, 0 evaluation**.

## Metrics và nguyên nhân

Answer correctness/completeness, citation accuracy, unsupported claim rate,
abstention accuracy, schema compliance, M6 ACCEPT/ABSTAIN/INVESTIGATE và latency/
usage evaluation: **N/A**, không phải 0% hoặc PASS. Usage preflight UNKNOWN.
Lỗi quan sát: **Provider/API — provider_unavailable**. Chưa có bằng chứng quy lỗi
cho OCR, retrieval/EF-EG, Tools, M5/M6/M7 hoặc Qwen model/schema.
Chưa kết luận về tổng quát hóa, lỗi cũ tái xuất hiện hay độ sẵn sàng so sánh model.

## Evidence và bàn giao

Local ignored `artifacts/evidence/QWEN-GEN-01/`: `preflight.json` chứa request/
response Gateway không có URL/key; `results.json` chứa25NOT_RUN; `receipt.json`
chứa hashes. Có thể kiểm tra preflight offline; chưa có execution traces M5–M7
để replay vì chưa chạy case nào. Không commit dataset/secrets.
Registry dùng **BLOCKED**, tương ứng **PAUSED — WAITING FOR OWNER** theo task;
không REVIEW/DONE. Planning checker và diff check là validation nhẹ;
không unit/full CI/M8 hoặc evaluation live. Commit checkpoint chỉ task files/hunks.

Next action: **Owner kiểm tra/khởi động lại API và thông báo đã hoạt động**.
Sau thông báo mới preflight, chuẩn bị/freeze25references và chạy case chưa hoàn thành;
hiện chưa có case PASS nào cần bỏ qua.
