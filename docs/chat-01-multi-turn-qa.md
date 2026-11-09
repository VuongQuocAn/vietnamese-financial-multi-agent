# CHAT-01 — Multi-turn Conversational QA

Owner giao09/11/2026; baseline `423514b`. REC-01 giữ DONE có giới hạn:
không tiếp tục OCR Recovery. CHAT-01 dừng ở REVIEW, chờ Tech Lead nghiệm thu.

## Thiết kế và sử dụng

`ConversationService` lưu các sessions riêng trong bộ nhớ tiến trình, serialize turns
bằng một lock cho local single-user prototype. Session **không tồn tại sau restart**,
không chia sẻ giữa workers. Mỗi session giữ tối đa40 lượt gần nhất; turn_id tăng liên tục.
`create()` luôn tạo session độc lập, cũng là thao tác bắt đầu lại.

Luồng: message → deterministic resolver → `FinancialQARequest` →
`FinancialQAPipeline.run()` hiện hữu → M5/M6/Ledger/M7/Firewall → cập nhật state.
Không nối lịch sử vào prompt, không đưa answer cũ vào evidence, không tạo claim mới
ngoài pipeline. Mỗi lượt vẫn kiểm tra ledger và source policy hiện hành. Resolver
không gọi Gemini, kể cả create/history; request mới có thể chọn Gateway qua contract cũ.

State tách `selected_context` (ý định chọn của người dùng) và `resolved_context`
(binding đã có answer verified), topics/referent, summary ngắn, claim/citation IDs.
History giữ response và execution trace để hiển thị; resolver chỉ đọc context/topics.
Kết quả thất bại không được biến thành topic đã xác minh; partial nhiều targets
không trở thành một referent duy nhất. Explicit company/year/document ghi đè phần
context tương ứng và xóa source pins cũ; reporting scope không tự đổi. Năm/công ty
chưa chọn thì hỏi lại. Nhiều topics, nhiều công ty, xung đột kỳ/scope hoặc ticker
chưa biết đều cần làm rõ. Tham chiếu phức tạp ngoài các quy tắc deterministic cần
người dùng nêu lại chủ đề; không thêm LLM fallback hoặc calls phụ.

So với năm trước của doanh thu dùng `revenue_yoy` đã duyệt, giữ năm gốc và hai
operands trong cùng evidence binding. Chỉ hỏi giá trị năm trước thì giảm năm đúng
một lần. Các phép so sánh khác giữ giới hạn QA hiện hữu, không tự thêm công thức.

Các file chính:

- `src/api/conversations.py`: contracts, in-memory store, resolver và service.
- `src/api/conversation_routes.py`, `src/api/main.py`: HTTP adapter có dependency injection.
- `tests/unit/test_conversations.py`: ba focused tests.
- `scripts/evaluate_conversations.py`: bảy hội thoại dùng sources thật và audit độc lập.
- `.github/workflows/ci.yml`: smoke API/core QA/conversation; full regression manual.
- `scripts/check_planning.py`: nhận task prefix CHAT; planning/spec/report cập nhật.

Python composition cho WEB-02: tạo `ConversationService(approved_financial_qa_pipeline)`
rồi truyền `create_app(conversation_service=service)`. `ConversationMessage(question=...)`
mặc định deterministic, không bật Gateway. Có thể dùng trực tiếp
`service.create()`, `service.send(conversation_id, message)`, `service.history(conversation_id)`.
Backend mặc định chưa có QA catalog composition chung; không inject service thì các
routes conversation trả503 `conversation_service_not_configured`, không dùng dữ liệu giả.
Đây là service/API cho WEB-02; task này không thay Web UI hoặc tự chọn dataset.

| Method | Route | Kết quả |
| --- | --- | --- |
| POST | `/api/conversations` | 201; session mới, ID độc lập |
| POST | `/api/conversations/{id}/messages` | turn với original/resolved question, context, inherited/changed, timing và response QA đầy đủ |
| GET | `/api/conversations/{id}` | state và lịch sử giới hạn40 lượt |

ID không tồn tại trả404; body theo Pydantic validation hiện hữu. `response` chứa
status/answer/citations/used_verified_claim_ids và `trace` agents/tools/Gemini/M6/M7/Firewall.
Không tự retry provider; session storage có thể thay sau này, không Redis/vector DB.

## Kiểm chứng trên dữ liệu thật

Evidence cuối: `artifacts/evidence/CHAT-01/run4/`, thay riêng S3 bằng
`artifacts/evidence/CHAT-01/document-fix/` sau bản sửa cuối. `final-summary.json`
tổng hợp20 lượt của bảy scenarios; không chạy lại sáu scenarios không bị ảnh hưởng.
Ledger mới trong artifacts CHAT-01, seed bằng bản sao ledger từ những lượt thử
CHAT-01 trước đó. Vì vậy12 lượt cuối là cache-hit: pipeline vẫn kiểm tra proof,
binding, current policy và M7/Firewall; không dùng một answer đã lưu thay cho request.
Một lượt fresh và một lượt partial reuse/refresh thực thi M5/M6 trong tập cuối.

Audit độc lập đối chiếu claim với accepted original fact values, tính lại công thức
bằng Decimal, kiểm tra quotations với original evidence records, company/document,
mọi source citation và trang gốc, cũng như citation-to-verified-claim binding.
**142 citation occurrences, sáu unique verified claims, không phát hiện mismatch hoặc
leakage**. Cả hai runs giữ nguyên hash396 JSON nguồn EXT-01/GEN-01 release.
Không thay raw/processed, source policy, approved input hoặc ledger cũ.

| Scenario | Lượt | Kết quả và đối chiếu |
| --- | ---: | --- |
| S1 | 5 | BBS2025: doanh thu450.474.531.227VND → YoY26,71% → gross margin7,21% → công thức; lượt5 sau các sessions khác vẫn BBS2025/gross margin. Năm trước trong YoY là operand2024, không đổi năm gốc. Cả năm lượt verified/citations PDF7. |
| S2 | 3 | BBS2025 → BCC2024: doanh thu3.487.978.470.438VND, đúng document BCC/PDF11. Hỏi công thức của direct fact trả partial có value đã verified, không bịa công thức. Đây là giới hạn QA hiện hữu, không lẫn company/topic. |
| S3 | 2 | Thuyết minh nhân viên quản lý chủ chốt BBS2025 → hỏi trang; hai lượt exact quotations từ PDF14, selectors4/5/6; follow-up sau fix completed_with_caveats. |
| S4 | 3 | Doanh thu thiếu công ty/năm → hỏi lại; chọn BCC2025 trả3.696.241.245.507VND/PDF7 → “Còn năm2024?” trả đúng3.487.978.470.438VND/PDF11, không dùng nhầm năm2025. |
| S5 | 3 | ROE BBS2025 chưa resolve thành topic verified → hỏi công thức tiếp tục cần làm rõ; hỏi doanh thu năm đó kế thừa **lựa chọn người dùng** BBS2025 và trả verified value, không có claim ROE. |
| S6 | 2 | Mixed revenue + thuyết minh BBS2025: hai claims, PDF7+14; “chỉ số này” không có referent duy nhất nên hỏi lại. |
| S7 | 2 | Gross margin BCC2024 bị pipeline chặn bởi accounting_basis_missing và snapshot_closure_not_closed; không có claim/citation. Follow-up formula cần làm rõ, không nâng target thất bại thành context verified. Đây là negative source-readiness case, không đánh dấu answerable/PASS tài chính. |

Tổng: **13 completed_with_caveats / 1 partial_verified_coverage / 5 clarification_required /
1 verification_blocked**. Các hành vi conversation được kiểm tra đạt; không tuyên bố
20/20 câu trả lời đầy đủ. S2 direct-fact formula và S7 accounting basis vẫn là giới hạn
pipeline/source, không sửa accounting hoặc làm nguồn “sạch” giả tạo trong CHAT-01.

### Ví dụ bốn lượt thật

Các số citation là số hiển thị riêng trong từng response, không phải số trang.

| Người dùng | Answer đã verified, rút gọn | Citations |
| --- | --- | --- |
| Doanh thu BBS năm2025 là bao nhiêu? | Doanh thu thuần450.474.531.227VND. | `[1]…[10]`, PDF7 |
| So với năm trước thì sao? | Tăng trưởng doanh thu2025 đạt26,71%. | `[1]…[12]`, PDF7, operands2025/2024 |
| Tỷ suất lợi nhuận gộp năm đó thế nào? | Biên lợi nhuận gộp2025 đạt7,21%. | `[1]…[13]`, PDF7 |
| Công thức tính chỉ số này là gì? | (Lợi nhuận gộp / Doanh thu thuần) ×100%; giữ metric BBS2025. | `[1]…[13]`, PDF7 |

Actual responses còn giữ caveats: reporting scope chưa được xác nhận, nguồn cấp trang,
source_reference_uncertain và source-bound verification không phải financial audit
độc lập. Không nâng provenance thành cell-level. Artifact từng lượt chứa answer đầy
đủ, claim IDs, exact source pointers và M6/M7/Firewall trace.

### Calls và độ trễ

Resolver/create/history **0 Gemini calls**; toàn tập cuối provider_calls=0,
known tokens=0. Trace ghi hai lần thực thi specialist `profitability`, bốn tool calls:
`find_financial_facts`2 và `get_evidence_sources`2. Cache-hit không chạy lại M5;
ledger checks/M7/Firewall vẫn chạy. Không OCR hoặc benchmark M8.

| Lượt | Resolver ms | Tổng service s |
| --- | ---: | ---: |
| S1-T1 | 24,484 | 12,915 |
| S1-T2 | 2,871 | 3,331 |
| S1-T3 | 10,900 | 8,093 |
| S1-T4 | 5,797 | 6,513 |
| S1-T5 | 3,771 | 6,632 |
| S2-T1 | 6,719 | 7,636 |
| S2-T2 | 5,877 | 3,517 |
| S2-T3 | 7,107 | 79,562 |
| S3-T1 | 22,939 | 8,630 |
| S3-T2 | 12,954 | 5,383 |
| S4-T1 | 2,873 | 0,003 |
| S4-T2 | 3,501 | 88,014 |
| S4-T3 | 3,789 | 2,947 |
| S5-T1 | 1,202 | 0,001 |
| S5-T2 | 5,663 | 0,006 |
| S5-T3 | 7,803 | 8,889 |
| S6-T1 | 15,747 | 18,644 |
| S6-T2 | 3,636 | 0,004 |
| S7-T1 | 4,262 | 30,929 |
| S7-T2 | 4,063 | 0,004 |

Resolver median5,730ms/max24,484ms; service median6,572s. Số đo một sample/lượt,
không benchmark so sánh; không gồm startup/catalog loading, audit script hoặc HTTP
serialization. Bảng có cả clarify/cache/fresh, không coi latency thấp của clarify
là tốc độ financial QA. Pipeline latency79,562–88,014s còn tồn tại ngoài resolver.

### Lỗi đã sửa và engineering validation

Bốn lỗi Conversation Layer đã sửa: composition document rò sang financial-only
request; expansion tạo conjunct “Còn BCC2024” thừa; dấu hỏi trước context suffix
tạo requirement riêng; “ở đâu năm” bị parser hiểu thành “đầu năm”. Bản sửa cuối
ghép “cho năm” và focused test chứng minh không tạo opening-date period.
Không sửa M5/M6/M7, công thức kế toán hoặc OCR.

Hai lần thử trước dừng vì audit script dùng sai contract (financial claim không có
references; SelectedRepositories chỉ có list_by_document); đã sửa, không tính là
PASS. S3 trước fix bị clarification không đúng; không che kết quả này trong run4.
Chỉ chạy lại S3 sau fix; các scenarios khác giữ year/company/topic cùng nghĩa.

Local:23 supporting smoke/planning tests PASS và3 conversation tests PASS sau fix
cuối; Ruff lint/format các file sửa, staged tree lint/format594files, planning119
tasks và diff check PASS. Local working planning120tasks gồm pending GEN-01a;
index/remote119tasks giữ phần đó ngoài commit. Không full regression/Web build local;
Web build/smoke dùng CI hiện hữu.

## Giới hạn và bàn giao

Đánh giá này kiểm tra hội thoại trên accepted saved financial facts/document selectors;
không phải benchmark M8 hoặc đánh giá OCR độc lập toàn PDF. Source caveats, các
claims bị policy chặn và giới hạn QA có sẵn vẫn giữ nguyên. Session chỉ trong một
process, lịch sử có giới hạn; cần inject approved pipeline khi Web tích hợp.

Implementation cuối `21eec27791a8ea06ef7770803cc693bb72727fea` đã push main,
sau implementation ban đầu `d50497c496e05b9d13fc883460d1c1eafb497c5b`.
[CI implementation cuối](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42582799192)
SUCCESS đúng21eec27: Python3.12 lint/format/planning và18smoke tests PASS;
Web typecheck/lint/build và9browser smoke PASS. Full unit regression manual SKIPPED.
Không gán CI của d50497c cho bản sửa21eec27.
Checkpoint tiếp theo chỉ docs/planning, không thay runtime hoặc chạy thêm CI lớn.
Giữ pending GEN-01a và Web ngoài commit CHAT-01.
Next action: Tech Lead review CHAT-01.
