# M4-05a — Gemini Live Integration & QA Validation

## Nguyên nhân và thay đổi

M4-05 chưa chạy live vì composition của `ask_financial_qa.py` chỉ gọi
`GeminiAdapter.from_environment()`,không đọc file key đã có từ trước. Không phải
Owner chưa cung cấp credentials. Kiểm tra local: file tồn tại,bốn unique key lines
đúng format và hai dòng khác;Git ignore/không tracked. Nội dung keys không in/log.

`api.qa_gateway` dùng lại regex/dedup/UTF-8 BOM handling của existing metadata
composition. Thứ tự: explicit `--key-file`,nếu không có thì `GEMINI_API_KEY`,rồi
`GEMINI_API_KEY_FILE`,cuối cùng local default `src/api/api_key/api_gemini.txt`.
Giữ env option,đọc code lỗi an toàn khi file/format/index không hợp lệ. Credential
có `repr=False`;không đưa key vào response,request metadata hoặc artifacts.
Mỗi runner chọn một key (index0),SDK attempts=1,không tự rotation/retry. Không cần
đưa metadata key-pool/cache/ledger của web vào một bounded QA smoke.

Gateway và GeminiAdapter không đổi. CLI/runner tạo adapter qua local composition,
rồi inject `SharedLLMGateway` vào `FinancialQABaseline`. Model mặc định và model
provider trả về đều `gemini-3.5-flash-lite`.

Hai sửa đổi QA có root cause:

- Rules trước đây trả ngay `unsupported_formula` hoặc chặn mọi “so sánh”,kể cả
  tỷ lệ được duyệt và kỳ so sánh trên cùng báo cáo. Bây giờ chỉ các soft rejection
  được thử Gateway một lần khi opt-in;ratio bắt buộc trả approved formula ID.
  Multi-year/cross-document,quality,scope,snapshot và calculator gates giữ nguyên.
- Live v1 hiểu hai câu analytical là unsupported. Prompt chỉ gửi formula labels,
  đồng thời câu “không trả IDs” mâu thuẫn với schema có canonical/formula IDs.
  Prompt sửa rõ IDs nào được phép,cung cấp exact semantics/expression/operand IDs
  từ approved policies,không thêm công thức hoặc tính toán bằng LLM. Hai câu lỗi
  được thử lại;giữ nguyên kết quả ban đầu để đánh giá trung thực.

`QALLMMetadata` thêm typed provenance/error để phân biệt requested/provider model,
quota/network với lỗi structured intent. JSON mode + `QAUnderstanding` local strict
validation,allowlists và backend tools vẫn là biên xử lý. Gemini không xuất số liệu,
citations hoặc snapshot IDs. Composer luôn bind số/nguồn từ M4 tools.

## Protocol live

Năm câu mới ở `evaluation/m4-05a-live-questions.json`,không trùng 36 câu M4-05.
Bốn positive và một negative implicit ROE. Trước live,từng câu được chạy qua
`understand()` và deterministic QA:đều unsupported/calls0. Context live chỉ có
`allow_gateway=True`,không gán document/year/canonical/formula ID trước.

Reference tạo trước từ exact persisted BBS facts và accepted M4-03 executions.
Chấm số/units/fact payloads,trace,source anchors/identities,intent và ordered tools;
không lấy Gemini output làm ground truth. Các kết quả cuối được chọn theo từng
câu sau targeted fixes;không phải một fresh five-question run của prompt cuối.

## Kết quả live

| Question | Parsed by | Intent | QA Status | Correct | Grounded | Calls |
|---|---|---|---|---|---|---|
| L01 v1: Năm 2025, BBS thu về bao nhiêu từ hoạt động bán hàng sau các khoản giảm trừ? | gateway | direct_fact | answered | True | Yes | 1 |
| L02 v1: BBS năm 2025, lấy tổng nợ chia toàn bộ tài sản thì ra khoảng bao nhiêu phần trăm? | gateway | unsupported | unsupported | False | N/A | 1 |
| L03 v1: Doanh thu bán hàng của BBS năm 2025 thay đổi bao nhiêu phần trăm so với kỳ so sánh trên cùng báo cáo? | gateway | unsupported | unsupported | False | N/A | 1 |
| L04 v1: BBS năm 2024 còn lại bao nhiêu lợi nhuận từ bán hàng sau khi trừ giá vốn? | gateway | direct_fact | answered | True | Yes | 1 |
| L05 v1: BBS năm 2025, mỗi đồng vốn của cổ đông tạo ra bao nhiêu đồng lãi sau thuế? | gateway | unsupported | unsupported | True | N/A | 1 |
| L02 v2: BBS năm 2025, lấy tổng nợ chia toàn bộ tài sản thì ra khoảng bao nhiêu phần trăm? | gateway | calculated_metric | answered | True | Yes | 1 |
| L03 v2: Doanh thu bán hàng của BBS năm 2025 thay đổi bao nhiêu phần trăm so với kỳ so sánh trên cùng báo cáo? | gateway | calculated_metric | answered | True | Yes | 1 |
| L05 v2: BBS năm 2025, mỗi đồng vốn của cổ đông tạo ra bao nhiêu đồng lãi sau thuế? | gateway | unsupported | unsupported | True | N/A | 1 |

**L01**

> 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ của BBS kỳ 2025 là 450.474.531.227 VND. Báo cáo B02; Nguồn PDF, trang 7. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Phạm vi báo cáo chưa được xác nhận. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

**L02**

> Tỷ lệ nợ phải trả trên tổng tài sản của BBS kỳ 2025-12-31 là 59,06%. Công thức: (nợ phải trả / tổng tài sản) × 100. Số liệu gốc: nợ phải trả: 157.146.559.558 VND, kỳ 2025-12-31; tổng tài sản: 266.086.680.765 VND, kỳ 2025-12-31. Nguồn PDF, trang 5, 6. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Phạm vi báo cáo chưa được xác nhận. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

**L03**

> Tăng trưởng doanh thu của BBS kỳ 2025 là 26,71%. Công thức: ((doanh thu thuần kỳ hiện tại - doanh thu thuần kỳ trước) / doanh thu thuần kỳ trước) × 100. Số liệu gốc: doanh thu thuần kỳ hiện tại: 450.474.531.227 VND, kỳ 2025; doanh thu thuần kỳ trước: 355.507.372.286 VND, kỳ 2024. Nguồn PDF, trang 7. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Phạm vi báo cáo chưa được xác nhận. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

**L04**

> 5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ của BBS kỳ 2024 là 36.432.410.381 VND. Báo cáo B02; Nguồn PDF, trang 9. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

## Lỗi runner và chi phí thực tế

Runner ban đầu dùng nhầm helper no-overwrite `save()` cho growing aggregates.
L01 đã ghi đầy đủ;ở request thứ hai,ghi Gateway aggregate lỗi rồi response
aggregate cũng lỗi. Provider outcome/tokens của response thứ hai không được lưu,
không suy đoán là success hoặc quota error. Đã sửa thành file riêng cho từng
request/case rồi ghi aggregate một lần. Không chạy lại L01 đã PASS.

Giữ evidence run bị dừng ở `artifacts/evidence/M4-05a-live`,gồm `interruption.json`.
Các run tiếp theo riêng `M4-05a-live-remaining`,`M4-05a-live-formula-fix` và
`M4-05a-live-negative-final`;không sửa/xóa evidence cũ.

Tổng **9 API attempts**,**8 typed responses đã lưu,8 success**,một response mất do
lỗi ghi evidence nên provider outcome chưa biết. Năm câu có evidence đầu tiên:
**3/5 đúng**;sau sửa prompt và chỉ retest hai câu lỗi/câu negative,kết quả được giữ
cuối cùng **5/5 đúng**,gồm **4 answers có số/citations đúng** và một unsupported đúng.
Trên cả tám attempts đã ghi,**6/8 đúng**,hai false abstentions ban đầu không bị xóa.
Đây là targeted retest,không tuyên bố một fresh five-question run của prompt v2.

Provider-reported tokens của tám responses: **10.267 input + 531 output = 10.798**.
Tổng tokens của cả chín attempts **N/A** vì một response chưa lưu;cost tiền tệ
provider không cung cấp,không ước lượng thành số tiền. Một key,index0,không rotation.
Không có quota/network errors trong tám typed responses;không suy status của
response chưa ghi. Gateway latency **719–1.228 ms**;toàn `answer()` **836–11.975 ms**,
không tính hydrate/catalog initialization. Summary/selected responses riêng ở
`artifacts/evidence/M4-05a-validation`;giữ đủ lịch sử từng run.

## Kiểm thử và regression

30 focused tests PASS:credential format/dedup/precedence/errors,SDK retry=1,
bounded Gateway fallback,approved-policy prompt binding và existing QA controls.
Mock tests chỉ kiểm engineering;live results phía trên dùng Gemini thật.

Bounded offline regression ở `artifacts/evidence/M4-05a-regression`:36/36 đúng
disposition,28 answered đúng/grounded,6 abstained/unsupported,2 clarification;
intent/tools36/36,zero Gateway. Đây là regression deterministic riêng,không phải
live evaluation.18/18 accepted executions và independent arithmetic exact,
29 retrieval queries,36 cross-document pairs vẫn undetermined,D-06 QA09/QA15 và
năm D-07 scopes exact. Inventory139 text/24 tables/2.973 anchors/18 lineages giữ
nguyên. JSON/fresh façade replay exact,2.670 protected hashes unchanged.
Live runs có2.665 protected inputs (gồm original M4-05 artifacts) unchanged qua
cả run bị dừng và ba run tiếp theo. Không sửa PDFs/raw/facts/snapshots/calculations.
Ruff toàn repository377 files,planning checker101 tasks và diff check PASS.

## Cách chạy

```powershell
python scripts/ask_financial_qa.py "Năm 2025, BBS thu về bao nhiêu từ hoạt động bán hàng sau các khoản giảm trừ?" --allow-live
python scripts/evaluate_m4_05a_live.py --allow-live --output artifacts/evidence/M4-05a-review
```

Local key mặc định không cần export env. `--key-file`/`--key-index` chỉ dành cho
caller chọn explicit credential;runner tối đa5requests/run và dừng khi có typed
provider error. Chỉ chọn key khác khi có căn cứ quota;phiên này không đổi key.
Không chạy lại full financial pipeline,OCR hoặc extraction.

## Giới hạn và bàn giao

Đây là smoke năm câu,không phải NLP benchmark đại diện. Prompt v1 false abstention
cho hai câu analytical cho thấy giới hạn của label-only intent prompting. Rules
xử lý rẻ và ổn định các aliases chuẩn;Gemini hỗ trợ paraphrases chưa được rules
nhận ra,nhưng vẫn cần schema/allowlists và backend compatibility/quality gates.
Provenance thật vẫn page-level/scope có unresolved;`financial_fact_verified=False`.
D03-B10 vẫn BLOCKED với cross-document. Giữ M4-05 APPROVED/DONE.

Status **REVIEW**;local/regressions hoàn tất,chưa commit/CI tại checkpoint này.
Giữ M4-05 DONE;không bắt đầu M5-01. Giữ unrelated web local byte-for-byte.

Next action: Tech Lead independent review M4-05a.
