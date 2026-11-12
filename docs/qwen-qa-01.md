# QWEN-QA-01 — Claim Calculator độc lập và M7 trình bày ACCEPT

Ngày12/11/2026; **REVIEW**, chưa commit. Baseline HEAD `82781f9` và working-tree
edits đã có; chỉ sửa phạm vi Owner duyệt sau QWEN-DIAG-01.

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
**0 model API calls**, không full CI/M8/frontend, không sửa evidence/ledger gốc,
không stage/commit/push runtime. Các thay đổi local ngoài task được giữ.

Giới hạn: phần trình bày sẽ sát nguyên mệnh đề ACCEPT hơn paraphrase tự do; đây
là lựa chọn triển khai boundary được duyệt. Semantic chất lượng vẫn do M6 chịu
trách nhiệm; chưa đo lại model, tốc độ hay chất lượng prose bằng live API.

**Next action duy nhất:** Tech Lead review code và evidence theo ba tiêu chí đã duyệt.
