# QWEN-QA-01 — Claim Calculator độc lập và M7 trình bày ACCEPT

Ngày12/11/2026; **REVIEW**. Implementation local
`019d85260b5fadf2d88c2bc4d605a1e7b3da9fee`, chưa push; baseline `82781f9` và
working-tree edits đã có. Chỉ sửa phạm vi Owner duyệt sau QWEN-DIAG-01.

## Thay đổi

- **M7:** LLM chọn thứ tự/nhóm claim IDs; backend trình bày content và proof của
  entries ACCEPT. JSON mới không cần `text`; output cũ có `text` vẫn đọc được
  nhưng không phát hành phần text do model viết. Không kiểm tra ngữ nghĩa mới,
  không keyword gate và không tăng từ chối. Findings được chọn nhưng model bỏ
  sót vẫn được hiển thị, giữ citations/caveats và các bước tính đã xác minh.
- **M5 Lite:** bật nhánh derived candidate sẵn có. Kết quả Calculator được render
  thành candidate thuần số độc lập, không kế thừa assumptions/limitations do
  model gắn cho interpretation; backend source caveats vẫn giữ. M6 kiểm chứng
  analysis và derived candidate riêng, kể cả analysis điều kiện hoặc sai số.
- **M5 contract:** phân tách các source caveat đã có trong backend khỏi trường
  limitations của analysis, không cắt caveats nguồn hoặc tăng cap. Interpretation
  chọn metric đã có dùng metric trực tiếp; không chạy recomputation thừa do model
  khai. Với phép tính mới, closure bổ sung fact operands mà operation tham chiếu
  trong evidence đã được Tools giao; unknown IDs/context/units/periods vẫn qua
  checks hiện có. Giữ nguyên statement model để M6 kiểm chứng, không sửa số model.
- Không đổi M6, schema accounting, Gateway/provider hoặc thêm agent/verifier.
  M7 dùng renderer hiện có; raw model output vẫn nằm trong trace để đối chiếu.

Files runtime: [qa_lite.py](../src/outputs/qa_lite.py),
[lite_orchestrator.py](../src/agents/lite_orchestrator.py),
[specialist_common.py](../src/agents/specialist_common.py).

## Ba điều kiện nghiệm thu

| Kiểm tra | Kết quả offline |
| --- | --- |
| BBS tỷ lệ nợ/tài sản | PASS: hiển thị59,06% cùng proof; không phát hành diễn giải đảo chiều trong output M7 cũ. M6 ACCEPT1 numeric, INVESTIGATE1 analysis do không có semantic provider trong replay. |
| BBS tăng trưởng doanh thu | PASS: giữ analysis26,8% để M6 ABSTAIN; derived26,71% được M6 ACCEPT, admitted vào ledger riêng và hiển thị dù output M7 cũ chỉ chọn hai facts. Tổng ACCEPT3/ABSTAIN1. |
| Control ngoài BBS | PASS: pipeline BCC2025 với tăng trưởng doanh thu và chênh lệch lợi nhuận gộp; mỗi câu ACCEPT3/ABSTAIN1, trả đúng derived proof, không phát hành nhận định thanh khoản do payload model chèn thêm. |

Hai BBS cases dùng captured Qwen Supervisor/Specialist/M7 payloads, chạy fresh
Tools/M5/M6/ledger/M7 ở code mới; chỉ rebind claim IDs sang ledger mới. **Không phải
fresh Qwen run**. Semantic request Q1 được trả unavailable offline, không tạo
SUPPORTED giả. Hai replay vẫn `partial_verified_coverage`: Q1 chưa có semantic
ACCEPT, Q2 giữ gap B từ output M7 lịch sử; phần trăm đã được trả đúng.

Hai BCC controls dùng catalog/composition thật đã lưu, source-bound Decimal oracle;
payload agent **synthetic fault injection** (số sai và nhận định không có claim),
không phải câu trả lời live của Qwen/Gemini. Cả hai `completed_with_caveats`; doanh
thu thay đổi5,97%, chênh lệch lợi nhuận gộp khớp phép trừ từ đúng operands.
Không đọc lại PDF hoặc tuyên bố accuracy độc lập của nguồn tài chính.

3 tests mới xác nhận presentation chỉ từ ACCEPT, ownership source caveats/metric,
và derived độc lập trên các phép tính/kỳ khác nhau, gồm conditional analysis.
Chạy targeted suite: **32 PASS** (3 mới +29 existing). Ba assertions/expectations
M7 cũ được cập nhật theo contract presentation đã duyệt; không xóa test hiện có.
Không thêm bất kỳ số liệu BBS/BCC hay quy tắc riêng theo câu hỏi vào runtime.

## Evidence và bàn giao

`artifacts/evidence/QWEN-QA-01/` (ignored): `before.json`/source copies ghi baseline;
`replay.py`, `replay-01/{Q1,Q2,summary}.json`; `non_bbs_controls.py`,
`non-bbs-controls/{C1,C2,summary}.json`, cùng ledger riêng. Input gốc read-only.
Ruff lint/format, planning checker và diff checks là validation bàn giao.
Giai đoạn offline: **0 model API calls**, không full CI/M8/frontend, không sửa
evidence/ledger gốc. Commit và fresh evidence được cập nhật bên dưới.
Các thay đổi local ngoài task được giữ.

Giới hạn: phần trình bày sẽ sát nguyên mệnh đề ACCEPT hơn paraphrase tự do; đây
là lựa chọn triển khai boundary được duyệt. Semantic chất lượng vẫn do M6 chịu
trách nhiệm; chưa đo lại model, tốc độ hay chất lượng prose bằng live API.

## Commit và kiểm tra trước live

Commit `019d852` chỉ chứa12 task files/hunks; hunk `with_assignment` có sẵn trong
specialist_common và các edits khác không được stage. Isolated tree
`bbdf3355af69a260e7cdeab7e1be32339c1d16a1`: **32 tests PASS**, planning134tasks,
Ruff và staged diff check PASS. Working-tree planning có138tasks do các local
tasks chưa commit khác; không đưa chúng vào implementation commit này.

Live dùng QA patch đã commit cùng Qwen adapter/composition và local dependencies
đã có từ trước, chưa commit trong task này. Source hashes ở receipt; không giả
là toàn bộ runtime được chạy từ pristine commit.

## Lần kết nối đầu — DNS không hoạt động

09:51:52–09:52:24 Asia/Bangkok ngày12/11/2026: đúng2câu,6provider attempts,
không replay/retry/Gemini. Cả6 `provider_unavailable`; không nhận HTTP status,
model output hoặc usage. Một GET `/v1/models` chẩn đoán kết nối xác nhận
`httpx.ConnectError → gaierror11001`, DNS thất bại, không proxy environment.
Không có successful Qwen inference; không coi kết quả fallback là live PASS.

Q1 fallback:20,119s, M6 ACCEPT3/ABSTAIN1(context_mismatch), chỉ số59,06% nhưng thiếu
ý nghĩa. Q2 fallback:11,015s, M6 ACCEPT2 facts, thiếu26,71%. Cả hai partial;
semantic_candidate_count=0. Provider errors ghi đủ3lỗi/câu dù trace.errors rỗng.
Evidence riêng: `artifacts/evidence/QWEN-ADAPTER-01/qwen-qa-01-live-01/`.
Owner sau đó cung cấp URL mới; key/model được giữ trong config ignored, không
sửa source. Lần chạy tiếp dùng output/ledger mới, không ghi đè evidence lỗi DNS.

## Lần kết nối hai — URL mới phản hồi, key cũ bị từ chối

10:03:24–10:03:55 Asia/Bangkok: chạy lại đúng2câu theo URL mới Owner cung cấp,
ledger mới. Hai HTTP attempts đều **401 authentication**, usage UNKNOWN;
không retry, không model output. Request Gateway dừng các bước model tiếp theo
sau lỗi auth, nên chỉ có1 HTTP attempt/câu. M6 vẫn xử lý fallback local.

| Câu | Agent thực thi | Tools | M6 verdict local | Latency E2E | Kết quả |
| --- | --- | --- | --- | ---: | --- |
| Tỷ lệ nợ/tài sản và ý nghĩa | liquidity_and_leverage | calculate_financial_metric, get_financial_fact, get_evidence_sources | ACCEPT3, ABSTAIN1(context_mismatch) | 21,876s | partial; có59,06%, thiếu diễn giải |
| Tăng trưởng doanh thu2025/2024 | profitability | get_financial_fact, get_evidence_sources | ACCEPT2 | 7,563s | partial; hai facts, thiếu26,71% |

Hai câu không dùng replay hoặc Gemini. Cả hai có semantic_candidate_count=0 và
semantic_calls=0, vì provider không trả analysis. Không dùng fallback để khẳng
định lỗi QA đã đạt live acceptance. Giữ REVIEW; chưa đủ điều kiện DONE.

Evidence riêng: `artifacts/evidence/QWEN-ADAPTER-01/qwen-qa-01-live-02/` có nguyên
request/answer/M6/agent/tool/provider traces và ledger. Owner đã được yêu cầu
API key hiện hành hoặc đường dẫn api_info.json mới; key/URL không ghi vào source.

**Next action duy nhất:** Owner cung cấp API key hiện hành hoặc api_info.json
mới để tiếp tục hai câu fresh còn chờ nghiệm thu.

### Final answers (fallback, HTTP 401)

#### Q1

> Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. [1]
>
> Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%.
> Công thức đã xác minh: (C - NỢ PHẢI TRẢ / TỔNG CỘNG TÀI SẢN) × 100.
> C - NỢ PHẢI TRẢ: 157146559558 VND; hệ số đơn vị 1; kỳ 2025-12-31.
> TỔNG CỘNG TÀI SẢN: 266086680765 VND; hệ số đơn vị 1; kỳ 2025-12-31. [2][1]
>
> Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. [2]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Một bước xử lý chưa hoàn tất; chỉ trình bày phần đã xác minh.
>
> Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [2] Tài liệu nguồn 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

#### Q2

> Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. [1]
>
> Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Một bước xử lý chưa hoàn tất; chỉ trình bày phần đã xác minh.
>
> Lỗi kỹ thuật khi tạo câu trả lời; các findings đã xác minh được giữ bên dưới.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
