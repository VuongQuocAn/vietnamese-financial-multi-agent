# M4-05 — Question Answering Baseline

Baseline QA tiếng Việt từ câu hỏi tự nhiên, chạy trên persisted BBS 2021–2025 và
snapshot recovery 2022. Đây là đối chứng nghiên cứu `single_agent_tool_baseline`,
không phải Claim Verifier/Multi-Agent M5. `financial_fact_verified=False` xuyên suốt.

## API và cách chạy

Public exports từ `vietnamese_financial_multi_agent.tools`:
`FinancialQABaseline`, `QAContext`, `QADocument`, `QAUnderstanding`, `QAResponse`.
Caller hydrate `SnapshotCatalog` bằng repositories/approved policies hiện có;
`QADocument` bind document ID, company ID/aliases và filing year từ inventory đã biết.
Không suy filing year từ tên file hoặc lấy năm lớn nhất của facts.

```python
from vietnamese_financial_multi_agent.tools import FinancialQABaseline, QAContext


def ask(catalog, documents):
    baseline = FinancialQABaseline(catalog, documents)
    return baseline.answer("Tổng tài sản BBS năm 2025 là bao nhiêu?", QAContext())
```

Local CLI nhận câu hỏi bất kỳ, không đọc danh sách benchmark để trả lời:

```powershell
python scripts/ask_financial_qa.py "Biên lợi nhuận gộp BBS năm 2025?"
python scripts/ask_financial_qa.py "Tổng nợ BBS năm 2022 bản gốc?"
python scripts/ask_financial_qa.py "Tăng trưởng doanh thu BBS năm 2022 bản recovery?" --json
```

CLI dùng lại loader accepted BBS artifacts trong scripts; đây là local research
demo, cần các persisted inputs có sẵn. Public API độc lập loader/filesystem này.
Context nhận document/company/snapshot ID, year/period, reporting scope và target
cho câu hỏi tiếp nối. Có thể truyền `formula_id`/`canonical_item_id` của response
trước cùng document/snapshot/kỳ; không có conversation memory ngầm.

`QAResponse.version=financial_qa_v1` giữ original question, parsed intent,
resolved document/snapshot/period, numerical string/unit và Vietnamese answer.
`facts` giữ nguyên raw/normalized value, unit, scale, statement, quality và identities.
`calculation` giữ formula policy/approval/digest, exact original operands, Decimal
trace và M4-02 evidence; không ghi đè DerivedMetric. `citations` là original
EvidenceCitation/anchors, không tạo geometry hoặc đổi page-level thành cell-level.
`retrieval`, `calculation`, `evidence`, `llm` và ordered `tool_trace` tách riêng trạng
thái các lớp; presence/grounding/calculation không trở thành financial verification.

## Question understanding và tool dispatch

Rules normalize tiếng Việt có/không dấu, longest non-overlapping aliases từ toàn
bộ `ITEM_CATALOG`, cộng cách nói thông dụng như tổng nợ/doanh thu/biên lợi nhuận gộp.
Các nhãn trùng nghĩa chưa phân biệt như “Hàng tồn kho” yêu cầu làm rõ; không chọn
candidate đầu tiên. Chỉ ba formula IDs đã duyệt được dispatch. Năm đơn lẻ dùng
closing date cho B01 và fiscal year cho B02/B03; hỗ trợ đầu năm/ngày cụ thể. Câu
quý/tháng, nhiều mục tiêu và công thức chưa duyệt không được đổi thành annual fact.

- Direct: `find_financial_facts` → `get_evidence_sources` → deterministic rendering.
- Analytical: `list_financial_metrics`, bind kỳ của current operand →
  `calculate_financial_metric` → `get_metric_evidence_lineage` → rendering.
- Evidence: cùng target và tools; thêm công thức/operands/trang và giải thích mức
  đối chiếu nguồn. Không coi `value_row_verified` là financial fact verified.

Original/recovery ambiguity yêu cầu exact selection. Chấp nhận snapshot ID từ
context hoặc ID thực có trong câu hỏi, cũng như “bản gốc/recovery” nếu chỉ có duy
nhất descriptor phù hợp; không tự chọn latest hoặc kế thừa facts/reviews từ parent.
Context/year/period/scope/snapshot mâu thuẫn được trả rõ. Explicit scope chỉ được
dùng khi source-backed scope resolution phù hợp: original 2024 separate, các
filings còn lại unresolved. Direct/approved same-filing metrics vẫn được dùng;
cross-document comparisons giữ chặn D03-B10. Revenue YoY chỉ dùng hai kỳ đã bind
trong cùng filing/snapshot.

## Gateway

Optional inject `SharedLLMGateway`; `QAContext(allow_gateway=True)` chỉ cho tối đa
một call khi rules chưa xác định được target. Model mặc định lấy
`DEFAULT_GEMINI_MODEL=gemini-3.5-flash-lite`; caller có thể đổi model.
Request dùng JSON output mode, schema Pydantic trong instruction và local
Pydantic validation sau Gateway. Chưa đăng ký provider-enforced JSON Schema
riêng. Backend kiểm allowlist/intent-target/year/scope/period/company; model không
được xuất document/snapshot ID, số liệu hoặc citations. Không retry/chain/reflection.
Rendering luôn deterministic từ typed tools, gồm multiplier phần trăm của policy.

CLI chỉ bật Gateway qua `--allow-live` và process `GEMINI_API_KEY`, giữ giới hạn một
request/600 output tokens/30 giây; không tự lấy key khác, không OCR/đọc lại PDF.
Không có process credentials/live configuration trong phiên này: live Gemini
**NOT RUN**, zero requests, token usage **N/A**. Mock Gateway tests kiểm contract và
gates; không coi đó là đánh giá NLP Gemini thực tế.

## Real-data benchmark

36 câu ở `evaluation/m4-05-questions.json`: 14 direct, 9 analytical, 5 evidence,
8 negative. BBS 2021–2025 thật, có original và recovery selection explicit; E05 là
câu tiếp nối có context. Không hardcode expected numbers vào parser/composer.

References tạo từ exact persisted facts và accepted
`M4-03-final/executions.json` trước khi gọi baseline. Chấm exact values, units,
fact payloads/identities, calculation traces, original source anchors/citations,
intent, ordered tool selection và refusal/clarification dispositions. Reference
không lấy đáp án của chính baseline. Đây là reference theo accepted artifacts,
chưa phải independent human financial gold hoặc accuracy trên toàn PDF.

| Chỉ số | Kết quả |
| --- | ---: |
| Total | 36 |
| Answered / correct trong answered | 28 / 28 |
| Incorrect / partial | 0 / 0 |
| Abstained hoặc unsupported | 6 |
| Cần làm rõ | 2 |
| Đúng disposition toàn tập | 36/36 |
| Grounded citations trong answered | 28/28 |
| Wrong/missing citations | 0 |
| Intent parsing / tool selection | 36/36 / 36/36 |
| Gemini calls / tokens | 0 / N/A |

Final run local: latency median **520,46 ms**, max **9.944,39 ms** mỗi `answer()`;
không tính hydrate/catalog initialization. Có cả cold/warm selections trong run,
không phải thống kê latency live Gemini hoặc benchmark hiệu năng nhiều máy.

Các negative controls có nguyên nhân thực: 2022 có hai snapshots; ROE chưa duyệt;
cross-document compatibility chưa xác nhận; scope consolidated 2025 unresolved;
canonical nợ ngắn hạn chưa sẵn trong selected persisted catalog; B03 2022 original
`insufficient`; chỉ tiêu không tồn tại; câu “Nguồn ở đâu?” thiếu target.
Không dùng đáp án đoán để tăng answer rate.

Chạy lại với output folder mới, không ghi đè evidence đã có:

```powershell
python scripts/evaluate_m4_05_qa.py --output artifacts/evidence/M4-05-review
```

Artifacts ignored: `M4-05-final/{references,responses,scores,summary,metric-regression,hashes-before,hashes-after}.json`.
Responses chứa đầy đủ câu trả lời tiếng Việt và structured citations/operands.

## Ví dụ câu trả lời thật

**D01 — Tổng tài sản của BBS năm 2025 là bao nhiêu?**

> TỔNG CỘNG TÀI SẢN của BBS kỳ 2025-12-31 là 266.086.680.765 VND. Báo cáo B01; Nguồn PDF, trang 5. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Phạm vi báo cáo chưa được xác nhận. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

Document `sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`, snapshot `D-01/normalized-v2`.

**D03 — Doanh thu thuần BBS năm 2024?**

> 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ của BBS kỳ 2024 là 355.507.372.286 VND. Báo cáo B02; Nguồn PDF, trang 9. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

Document `sha256:f4e696a85c65f33cb1a1fa982dbfc6b3dccb5a227d14084d5f02b0d673f57c54`, snapshot `D-01/normalized-v2`.

**A01 — Biên lợi nhuận gộp của BBS năm 2025?**

> Biên lợi nhuận gộp của BBS kỳ 2025 là 7,21%. Công thức: (lợi nhuận gộp / doanh thu thuần) × 100. Số liệu gốc: lợi nhuận gộp: 32.482.519.668 VND, kỳ 2025; doanh thu thuần: 450.474.531.227 VND, kỳ 2025. Nguồn PDF, trang 7. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Phạm vi báo cáo chưa được xác nhận. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

Document `sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`, snapshot `D-01/normalized-v2`.

**A02 — Tỷ lệ nợ trên tổng tài sản BBS năm 2025 là bao nhiêu?**

> Tỷ lệ nợ phải trả trên tổng tài sản của BBS kỳ 2025-12-31 là 59,06%. Công thức: (nợ phải trả / tổng tài sản) × 100. Số liệu gốc: nợ phải trả: 157.146.559.558 VND, kỳ 2025-12-31; tổng tài sản: 266.086.680.765 VND, kỳ 2025-12-31. Nguồn PDF, trang 5, 6. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Phạm vi báo cáo chưa được xác nhận. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

Document `sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`, snapshot `D-01/normalized-v2`.

**A03 — Tăng trưởng doanh thu của BBS năm 2025?**

> Tăng trưởng doanh thu của BBS kỳ 2025 là 26,71%. Công thức: ((doanh thu thuần kỳ hiện tại - doanh thu thuần kỳ trước) / doanh thu thuần kỳ trước) × 100. Số liệu gốc: doanh thu thuần kỳ hiện tại: 450.474.531.227 VND, kỳ 2025; doanh thu thuần kỳ trước: 355.507.372.286 VND, kỳ 2024. Nguồn PDF, trang 7. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Phạm vi báo cáo chưa được xác nhận. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

Document `sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`, snapshot `D-01/normalized-v2`.

**E04 — Tăng trưởng doanh thu BBS năm 2022 dùng công thức và lấy số liệu nào?**

> Tăng trưởng doanh thu của BBS kỳ 2022 là -14,32%. Công thức: ((doanh thu thuần kỳ hiện tại - doanh thu thuần kỳ trước) / doanh thu thuần kỳ trước) × 100. Số liệu gốc: doanh thu thuần kỳ hiện tại: 448.420.784.262 VND, kỳ 2022; doanh thu thuần kỳ trước: 523.353.809.694 VND, kỳ 2021. Nguồn PDF, trang 7. Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. Phạm vi báo cáo chưa được xác nhận. Trạng thái nguồn: đã đối chiếu giá trị/dòng với PDF. Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính.

Document `sha256:480854b56c27737c9327e3f7650f8f6fde84fbcaab552b83dbbe72431c9da0ee`, snapshot `D-02/recovery-2022-v1`.

## Validation, corrections và giới hạn

193 targeted tests PASS: 25 QA + M4 execution/retrieval/calculator/evidence tools.
Warning Pydantic duy nhất từ existing invalid-Decimal negative test; không lỗi runtime.
Sau thay đổi rendering/cache, 25 QA PASS. Ruff toàn repository 372 files, planning
checker 100 tasks và diff checks được kiểm trước bàn giao; không chạy full suite.
CLI smoke câu “Biên lợi nhuận gộp BBS năm 2025?” PASS từ process mới: 7,21%,
operands 32.482.519.668/450.474.531.227 VND, PDF trang7, zero Gateway.

Regression bounded đọc accepted artifacts: 18/18 executions và independent
arithmetic exact (15 original + 3 recovery), 29 accepted queries, partial-scope
correction, 36 cross-document pairs vẫn undetermined, năm D-07 scopes, D-06
QA09/QA15 exact. Inventory giữ 139 text/24 tables/2.973 anchors/18 lineages;
không replay toàn bộ 2.973 anchor queries vì M3/M4 accepted runtime không đổi.
2.670 protected hashes unchanged, fresh façade/JSON response replay exact;
không sửa facts/metrics/policies/reviews/lineage, PDF/raw hoặc web local.

Trong phát triển, targeted tests phát hiện calculator operands dùng RetrievalMatch
thay vì FinancialFactMatch: composer được sửa để bind review/scope từ actual metric
evidence, không dựng metadata. Review thêm chặn nhầm “nguồn vốn” thành Evidence QA,
nhầm unsupported ratio thành direct fact, lệch kỳ đầu năm/ngày cụ thể, unknown
snapshot và stale follow-up target cho câu hỏi không liên quan. Selection cache
chỉ lưu catalog bất biến, trả deep copies; không thay gates hoặc chọn snapshot mới.

Giới hạn cho M5: baseline đơn mục tiêu/annual, thiếu free-form reasoning và
conversation resolution tự động, phụ thuộc coverage/mapping và metadata đã bind.
Rules không đảm bảo hiểu mọi câu tiếng Việt; chưa có live Gemini NLP benchmark.
Các nguồn thật vẫn chủ yếu page-level/uncertain; unresolved scope và dữ liệu thiếu
không được tự sửa bởi QA. Không specialist agents, planner, verifier hoặc ledger.

## Git và review

Status **DONE**, Tech Lead APPROVED ngày02/11/2026,cho phép đồng bộ planning,
không cần sửa thêm; implementation
`359babb9dcfbf40275ef693399c5bdf204aea150` đã push main, origin khớp.
[CI41384217552](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41384217552)
completed/SUCCESS đúng implementation SHA: Python3.12 lint/format/planning/focused
tests và Web smoke/typecheck/lint/build/browser/proxy SUCCESS. Full unit regression
SKIPPED theo workflow. Checkpoint sau chỉ docs/planning [skip ci]; không gán CI
implementation cho SHA checkpoint.
M4 hoàn tất trong phạm vi phê duyệt;D03-B10 vẫn BLOCKED với cross-document.
Phiên nghiệm thu chỉ docs/planning và planning/diff checks;không chạy lại tests,
benchmark hoặc Gemini/OCR/extraction,không sửa runtime/accepted artifacts/web local.

Next action: chờ Tech Lead gửi brief M5-01 — Evidence Plan and Planner Contracts.
