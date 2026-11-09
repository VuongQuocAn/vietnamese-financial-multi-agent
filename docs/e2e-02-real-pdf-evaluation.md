# E2E-02 — Real PDF Pipeline Evaluation & Issue Discovery

Đánh giá ngày 09/11/2026 (Asia/Bangkok). **DISCOVERY ONLY; REVIEW**, chờ Tech Lead nghiệm thu.
Runtime được đánh giá: `39d796acba7c9eebc9ca74c6c6f564238910d3b5`.
Không sửa production, prompt, policy, dữ liệu nguồn hoặc ledger đã nghiệm thu.

## Phạm vi và phương pháp

QA trên evidence đã ingest của bốn PDF thật: BBS 2024/2025 và BCC 2024/2025.
Không ingestion/OCR mới. BCC 2024 là hợp nhất, BCC 2025 là riêng; không đồng nhất
hai scope này. BBS còn giới hạn reporting scope. Composition verified xác nhận
binding, không tự chứng minh mọi câu OCR đúng.

Codex đọc trực tiếp các trang PDF render để chuẩn bị reference trước QA: giá trị,
VND, kỳ, scope, trang vật lý PDF, luận điểm, công thức Decimal và điều kiện answerable.
Không lấy output pipeline làm reference. Hai manifests và hashes được khóa trong
`freeze.json`. Số trang PDF có thể khác số trang in.

Chế độ deterministic, `allow_gateway=False`, ledger riêng mới không seed.
Fresh execution không tái sử dụng claim QA cũ; reuse chỉ dùng claim tạo trong
đợt đánh giá này và vẫn qua current policy/M7/Firewall. L4 dùng ba sessions độc lập,
mỗi session bốn lượt. Không ép kích hoạt mọi agent/tool. Không có mẫu Gemini live.

Repo có code GEN-01a và planning local từ trước. Runner import snapshot
`git archive --format=zip HEAD src` để chạy code đã commit, giữ nguyên thay đổi local.
Loader và composition dùng accepted inputs hiện hữu. Không sửa nguồn để tăng điểm.

### Điều chỉnh runner và số lần chạy

Startup đầu gặp graph=None ở catalog chỉ có document evidence, chưa gọi QA.
Hai QA invocations smoke sau đó không hợp lệ vì runner ghép BBS 2024 dùng ticker ID
với BBS 2025 dùng registration ID, gây yêu cầu làm rõ giả. Giữ nguyên chúng tại
`runner-check-invalid/`; chỉ sửa metadata composition của runner bằng company ID
đã có trong accepted catalog và bỏ graph không tồn tại. Không sửa QA/reference.
Sau sửa, 40 lượt chính thức chạy mỗi lượt một lần; hai lượt smoke chính thức giữ
trong tập 40, rồi resume 38 lượt còn lại. Tổng 42 QA/service invocations, không chọn
đáp án tốt hơn. Audit runner có một lỗi ghép trùng trường id; chỉ chạy lại audit,
không chạy lại QA. Các điều chỉnh kỹ thuật được ghi trong `runner-adjustments.json`.

## Artifacts và tái hiện

Dữ liệu riêng tư được Git ignore tại `artifacts/evidence/E2E-02/`:
questions/reference/freeze; turns/results/traces; ledger; catalog-inputs;
judgments/audit; latency.csv; summary/issues; integrity; pdf-review.
Không commit PDF, OCR/normalized/canonical, keys hoặc full outputs/traces.

Chuẩn bị manifests với nguồn local cùng hashes trong một thư mục kết quả mới:

```powershell
.venv/Scripts/python.exe scripts/evaluate_real_pdf.py freeze
.venv/Scripts/python.exe -u scripts/evaluate_real_pdf.py run --limit 2
.venv/Scripts/python.exe -u scripts/evaluate_real_pdf.py run
.venv/Scripts/python.exe scripts/audit_real_pdf.py
```

Audit cần judgments riêng đối chiếu reference, không tự chấm từ status.
`turns/Qxx.json` là quan sát gốc; judgments/audit là phần chấm bổ sung.
Không ghi đè đợt đã đo. Cách tái hiện từng issue ở [Issue Log](e2e-02-issue-log.md).

## Tập PDF và source status

Trang dưới đây là trang vật lý PDF; đường dẫn tương đối và document hashes đầy đủ trong reference.json. BBS 2024 được đối chiếu doanh thu trực tiếp PDF 9, không thay bằng cột so sánh của BBS 2025.

| PDF | Scope | Trang tham chiếu | Giới hạn | SHA256 PDF |
| --- | --- | --- | --- | --- |
| BBS_2025 | scope chưa được runtime xác nhận | 5,6,7,8,12,14 | BBS scope unresolved; page-level source caveats | `6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1` |
| BBS_2024 | scope chưa được runtime xác nhận | 9,21 | document evidence only; financial facts chưa có | `f4e696a85c65f33cb1a1fa982dbfc6b3dccb5a227d14084d5f02b0d673f57c54` |
| BCC_2024 | hợp nhất | 11,16,30 | BCC 2024 accounting basis chưa approved; PDF 30 selector9 quarantine | `866d6c9e212079c47974bddb2bdf0305ecf40008950a23fa5af856d50ee4ab5b` |
| BCC_2025 | riêng | 5,6,7,13 | riêng; không so đồng nhất với BCC 2024 hợp nhất | `91acbf554b287dc81cdfe256d19249a8cd5484197fcd2a71dc1aa3088f1bb214` |



## Tập PDF và source status

Trang dưới đây là trang vật lý PDF; đường dẫn tương đối và document hashes đầy đủ trong reference.json. BBS 2024 được đối chiếu doanh thu trực tiếp PDF 9, không thay bằng cột so sánh của BBS 2025.

| PDF | Scope | Trang tham chiếu | Giới hạn | SHA256 PDF |
| --- | --- | --- | --- | --- |
| BBS_2025 | scope chưa được runtime xác nhận | 5,6,7,8,12,14 | BBS scope unresolved; page-level source caveats | `6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1` |
| BBS_2024 | scope chưa được runtime xác nhận | 9,21 | document evidence only; financial facts chưa có | `f4e696a85c65f33cb1a1fa982dbfc6b3dccb5a227d14084d5f02b0d673f57c54` |
| BCC_2024 | hợp nhất | 11,16,30 | BCC 2024 accounting basis chưa approved; PDF 30 selector9 quarantine | `866d6c9e212079c47974bddb2bdf0305ecf40008950a23fa5af856d50ee4ab5b` |
| BCC_2025 | riêng | 5,6,7,13 | riêng; không so đồng nhất với BCC 2024 hợp nhất | `91acbf554b287dc81cdfe256d19249a8cd5484197fcd2a71dc1aa3088f1bb214` |

## Kết quả chất lượng

**40 lượt chính thức:24 CORRECT, 3 PARTIAL, 1 INCORRECT, 4 JUSTIFIED_ABSTAIN, 7 UNJUSTIFIED_ABSTAIN, 1 CLARIFICATION hợp lý, 0 RUNTIME_FAILURE.** Hai QA invocations smoke không hợp lệ và một startup failure của runner giữ riêng; không nằm trong 40. Tổng QA/service invocations 42, không Gemini.

| Loại | Số | Tỷ lệ/40 | L1 | L2 | L3 | L4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CORRECT | 24 | 60.0% | 6 | 6 | 2 | 10 |
| PARTIAL | 3 | 7.5% | 1 | 0 | 2 | 0 |
| INCORRECT | 1 | 2.5% | 1 | 0 | 0 | 0 |
| JUSTIFIED_ABSTAIN | 4 | 10.0% | 0 | 2 | 2 | 0 |
| UNJUSTIFIED_ABSTAIN | 7 | 17.5% | 2 | 2 | 2 | 1 |
| CLARIFICATION | 1 | 2.5% | 0 | 0 | 0 | 1 |
| RUNTIME_FAILURE | 0 | 0.0% | 0 | 0 | 0 | 0 |

Số lượt từng nhóm: L1=10, L2=10, L3=8, L4=12 (C1:Q29–32,C2:Q33–36,C3:Q37–40). Negative controls: Q17/Q18/Q27/Q28 là bốn từ chối hợp lý; Q37 là một clarification hợp lý, không tính coverage error. Q05/Q10 là các nguồn có thông tin trên PDF nhưng luồng hiện hữu không trả được; giữ source coverage gaps riêng với negative controls.

Không suy ra correctness từ status: Q08 completed_with_caveats nhưng đảo nghĩa OCR; Q22 partial_verified_coverage nhưng đã đủ ratio/chính sách/caveat theo reference giới hạn, nên CORRECT. Q21 PARTIAL vì thiếu diễn giải mô tả đơn giản, không vì hệ thống từ chối kết luận chất lượng lợi nhuận cao/thấp thiếu chứng cứ. Q06/Q26 PARTIAL theo phần liên kết doanh nghiệp trong reference, không là số liệu sai.

## Citations, số liệu và ngữ cảnh

- **292/293 citation occurrences hỗ trợ nội dung ở cấp trang/claim =99,66%.** Một citation selector7/Q08 trích sai điều kiện dự phòng. Đây không phải accuracy nguồn/cell-level hay accuracy toàn bộ PDF. Cùng một claim/source được dùng lại có thể tạo nhiều occurrences.
- Automated binding/page audit:0 structural errors / 293. Sự khác biệt với semantic PDF audit chính là lỗiQ08; đúng document/page không đủ chứng minh trích dẫn đúng.
- 21/21 lượt có số liệu phát hành khớp values/VND/year và công thức độc lập;0 numeric/operand mismatches trong claim audit. Không coi các câu không trả lời là đúng số liệu.
- Context 39/40phù hợp; Q34 thất bại follow-up theo chủ đề dù identity company/year vẫn đúng. Hai lần chuyển doanh nghiệp và đổi kỳ trongC3 không lẫn nguồn.
- Explanation supported 27/28 lượt có nội dung phát hành; Q08 không được PDF hỗ trợ. Answer complete 29/40 bao gồm bốn từ chối và một clarification đúng. Các fields không áp dụng ghiNOT_APPLICABLE, không nâng thànhTrue.
- Không có nội dung được chấm đúng khi không xác minh được:NOT_VERIFIABLE = 0 trong assertions/citation pages đã sử dụng; geometry/cell localization không nằm trong phép đo này. Chi tiết từng assertion và rationale:judgments.json/audit.json.

## Hiệu năng

`perf_counter` đo mỗi request/service turn, loại startup/catalog loading (hai process:6,417s và8,396s), PDF rendering, audit và HTTP/Web. P90 dùng nearest rank. Một sample/câu; order/ledger tăng dần, không matched benchmark giữa fresh/reuse.

| Tập/chế độ | N | Median s | P90 s | Min s | Max s | >10s | >30s | >60s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 40 | 11.499 | 39.624 | 0.003 | 85.312 | 22 | 9 | 2 |
| answered_only | 28 | 13.801 | 47.002 | 1.454 | 85.312 | 18 | 9 | 2 |
| fresh_financial_only | 10 | 37.274 | 47.002 | 25.425 | 85.312 | 10 | 7 | 1 |
| FRESH_M5_M6_M7 | 14 | 29.527 | 47.002 | 9.460 | 85.312 | 13 | 7 | 1 |
| CACHE_HIT | 12 | 8.559 | 10.361 | 1.454 | 22.132 | 3 | 0 | 0 |
| PARTIAL_REUSE_AND_REFRESH | 2 | 56.145 | 74.486 | 37.804 | 74.486 | 2 | 2 | 1 |
| BLOCKED | 11 | 0.013 | 13.677 | 0.003 | 19.332 | 4 | 0 | 0 |
| CLARIFICATION_REQUIRED | 1 | 0.005 | 0.005 | 0.005 | 0.005 | 0 | 0 | 0 |
| L1 | 10 | 13.963 | 28.653 | 0.013 | 30.401 | 8 | 1 | 0 |
| L2 | 10 | 24.454 | 40.981 | 0.003 | 47.002 | 6 | 5 | 0 |
| L3 | 8 | 12.019 | 74.486 | 0.003 | 74.486 | 5 | 2 | 1 |
| L4 | 12 | 8.559 | 19.332 | 0.005 | 85.312 | 3 | 1 | 1 |

Median toàn tập 11,499s bị ảnh hưởng bởi blocked/clarify. **Fresh financial-only: median 37,274s / P90 47,002s; max 85,312s.** 12 cache-hit chỉ tái sử dụng claim được tạo trong tập này, không seed ledger cũ. Hai PARTIAL_REUSE_AND_REFRESH gồm Q21/Q22. Các ca blocked vẫn có thể thực thiM5/M6 trước khi không phát hành, không đồng nhất BLOCKED với không thực thi.

Resolver L4 riêng: median 4,821ms / P90 20,098ms / max 23,661ms. Không cộng resolver vào total lần nữa.

### Stage timing

Bảng chỉ các stage đã thực thi; parent/unit/tool có thể chứa nhau. **Không cộng bảng này thành total.** Missing timer là NOT_MEASURED, không là 0. latency.csv giữ từng lượt/resolver, native stages và các retrieval tool timers hiện có. Document retrieval riêng không có đầy đủ native timer; nằm trong m5, không tách giả bằng phép trừ. Provider latency không áp dụng vì 0 calls. Những đoạn chưa instrument không được phân bổ suy đoán.

| Stage (inclusive) | N | Median ms | P90 ms | Max ms |
| --- | ---: | ---: | ---: | ---: |
| context | 36 | 524.52 | 1907.02 | 2310.38 |
| composition | 10 | 2863.34 | 5757.67 | 7364.58 |
| financial_binding | 3 | 1413.30 | 1612.42 | 1612.42 |
| fusion_planning | 3 | 5.09 | 5.34 | 5.34 |
| graph_context | 2 | 12514.21 | 12729.07 | 12729.07 |
| m5 | 19 | 15502.34 | 21646.80 | 36545.37 |
| m6 | 16 | 1384.32 | 4023.84 | 5098.47 |
| m6_validators | 11 | 909.98 | 2154.68 | 2564.50 |
| m6_evidence | 11 | 1412.44 | 2385.26 | 2453.38 |
| m6_logic | 11 | 29.50 | 82.25 | 90.39 |
| m6_judge_revision | 11 | 58.35 | 147.77 | 156.56 |
| ledger_lookup | 29 | 38.17 | 4111.36 | 4565.01 |
| admission | 16 | 200.39 | 4442.16 | 9855.73 |
| ledger_reload | 11 | 1115.65 | 3805.37 | 7202.89 |
| composer | 31 | 218.82 | 1666.92 | 3140.63 |
| citations | 31 | 2.75 | 7.14 | 11.92 |
| firewall | 31 | 234.20 | 1440.02 | 1710.08 |
| U1 | 3 | 4634.07 | 23770.96 | 23770.96 |
| U2 | 3 | 2835.03 | 24167.73 | 24167.73 |
| U3 | 1 | 10439.44 | 10439.44 | 10439.44 |

Các ca chậm đáng chú ý:

| QID | Total s | Stage lớn đã ghi nhận (inclusive, s) |
| --- | ---: | --- |
| Q03 | 30.401 | m5=17.211; m6=1.787; context=1.008 |
| Q11 | 36.271 | m5=18.990; m6=2.647; admission=1.934 |
| Q12 | 38.276 | m5=18.691; m6=3.796; ledger_reload=2.689 |
| Q13 | 40.981 | m5=17.866; admission=3.252; m6=2.801 |
| Q14 | 39.624 | m5=20.231; admission=3.412; m6=3.264 |
| Q16 | 47.002 | m5=21.647; admission=4.442; m6=4.024 |
| Q21 | 37.804 | m5=15.504; ledger_reload=3.805; admission=2.534 |
| Q22 | 74.486 | U2=24.168; U1=23.771; graph_context=12.299 |
| Q38 | 85.312 | m5=36.545; admission=9.856; ledger_reload=7.203 |

## Agent, tools và Gemini

Selected và executed counts bên dưới là entries trong native trace; không ép specialist chạy trên document/cache/clarification. Thứ tự phối hợp, request/result/status của từng call được giữ trong traces.json và turns/.

| Agent/component | Selected | Executed |
| --- | ---: | ---: |
| profitability | 7 | 7 |
| liquidity_and_leverage | 4 | 4 |
| EvidenceAwareQueryPlanner | 8 | 8 |
| RiskAwareSupervisor | 8 | 8 |
| FinancialMultiAgentOrchestrator | 8 | 8 |
| cash_flow_and_earnings_quality | 1 | 1 |
| Tool | Calls |
| --- | ---: |
| find_financial_facts | 21 |
| get_evidence_sources | 20 |
| search_document_evidence | 10 |
| calculate_financial_metric | 7 |
| get_metric_evidence_lineage | 7 |
| get_graph_context | 2 |

Tổng 67 tool-call entries;2 get_graph_context và7 get_metric_evidence_lineage được ghi nhận. M5 specialists profitability/liquidity/cash-flow xuất hiện đúng các nhánh thực tế;12CACHE_HIT không chạy lại agents. Pipeline financial qua M5→M6→Ledger→M7; document qua evidence retrieval/document verification; mixed qua fusion/graph unit trace; L4 qua ConversationService.

**Gemini/provider calls 0; known tokens 0; unknown-token calls 0; provider errors 0.** Không có live Gemini sample, không kết luận về năng lực reasoning/cost/latency khi bật Gemini hoặc lợi ích so với deterministic.

## Danh sách40 lượt và đánh giá riêng

Reference đầy đủ đã đóng băng trong reference.json. Dưới đây giữ nguyên câu hỏi, nguồn, pages dự kiến, kết quả độc lập và timing; nội dung trả lời đầy đủ cùng claim/citation IDs ở turns/Qxx.json.


### L1

| ID | Câu hỏi | Nguồn / PDF pages | Control | Kết quả | s |
| --- | --- | --- | --- | --- | ---: |
| Q01 | Doanh thu thuần BBS năm 2025 là bao nhiêu? | BBS_2025 / 7 | - | CORRECT | 25.425 |
| Q02 | Lợi nhuận sau thuế BBS năm 2025 là bao nhiêu? | BBS_2025 / 7 | - | CORRECT | 26.457 |
| Q03 | Tổng tài sản BCC tại ngày 31/12/2025 trên báo cáo riêng là bao nhiêu? | BCC_2025 / 5 | - | CORRECT | 30.401 |
| Q04 | Doanh thu thuần BCC năm 2024 trên báo cáo hợp nhất là bao nhiêu? | BCC_2024 / 11 | - | CORRECT | 28.653 |
| Q05 | Ai là người lập, kế toán trưởng và giám đốc ký báo cáo BBS 2025? | BBS_2025 / 7 | - | UNJUSTIFIED_ABSTAIN | 13.253 |
| Q06 | Thuyết minh BBS 2025 nói gì về nhân viên quản lý chủ chốt? | BBS_2025 / 14 | - | PARTIAL | 12.929 |
| Q07 | BBS 2024 ghi “Chi tiết các khoản vay ngắn hạn” ở đâu trong báo cáo? | BBS_2024 / 21 | - | CORRECT | 9.460 |
| Q08 | Thuyết minh BCC 2024 nói gì về dự phòng phải thu khó đòi? | BCC_2024 / 16 | - | INCORRECT | 14.673 |
| Q09 | Thuyết minh BCC 2025 quy định thế nào về vay và nợ thuê tài chính? | BCC_2025 / 13 | - | CORRECT | 12.673 |
| Q10 | BBS 2024 có doanh thu thuần là bao nhiêu? | BBS_2024 / 9 | - | UNJUSTIFIED_ABSTAIN | 0.013 |

### L2

| ID | Câu hỏi | Nguồn / PDF pages | Control | Kết quả | s |
| --- | --- | --- | --- | --- | ---: |
| Q11 | Biên lợi nhuận gộp BBS 2025 là bao nhiêu? | BBS_2025 / 7 | - | CORRECT | 36.271 |
| Q12 | Tăng trưởng doanh thu BBS 2025 so với năm trước là bao nhiêu? | BBS_2025 / 7 | - | CORRECT | 38.276 |
| Q13 | Tỷ lệ nợ phải trả trên tổng tài sản BBS cuối năm 2025 là bao nhiêu? | BBS_2025 / 5,6 | - | CORRECT | 40.981 |
| Q14 | Biên lợi nhuận gộp BCC 2025 trên báo cáo riêng là bao nhiêu? | BCC_2025 / 7 | - | CORRECT | 39.624 |
| Q15 | Doanh thu BCC 2025 tăng trưởng bao nhiêu so với 2024 theo cột so sánh báo cáo riêng? | BCC_2025 / 7 | - | UNJUSTIFIED_ABSTAIN | 0.007 |
| Q16 | Tỷ lệ nợ trên tổng tài sản BCC cuối năm 2025 là bao nhiêu? | BCC_2025 / 5,6 | - | CORRECT | 47.002 |
| Q17 | Biên lợi nhuận gộp BCC 2024 là bao nhiêu? | BCC_2024 / 11 | NEGATIVE | JUSTIFIED_ABSTAIN | 12.637 |
| Q18 | Tính ROE của BCC năm 2025. | BCC_2025 / 6,7 | NEGATIVE | JUSTIFIED_ABSTAIN | 0.003 |
| Q19 | Giải thích công thức biên lợi nhuận gộp BBS 2025 và nêu các toán hạng. | BBS_2025 / 7 | - | CORRECT | 3.705 |
| Q20 | So sánh lợi nhuận sau thuế BBS 2025 với năm 2024 theo báo cáo năm 2025. | BBS_2025 / 7 | - | UNJUSTIFIED_ABSTAIN | 0.003 |

### L3

| ID | Câu hỏi | Nguồn / PDF pages | Control | Kết quả | s |
| --- | --- | --- | --- | --- | ---: |
| Q21 | Đánh giá chất lượng lợi nhuận BBS 2025 qua lợi nhuận sau thuế và dòng tiền thuần từ hoạt động kinh doanh; dẫn số liệu và giới hạn kết luận. | BBS_2025 / 7,8 | - | PARTIAL | 37.804 |
| Q22 | Phân tích khả năng thanh toán BBS 2025 qua tỷ lệ nợ trên tổng tài sản và thông tin phân loại các khoản vay trong thuyết minh. | BBS_2025 / 5,6,12 | - | CORRECT | 74.486 |
| Q23 | Doanh thu thuần BBS 2025 tăng nhưng lợi nhuận gộp giảm so với 2024: các số liệu cho thấy điều gì? Không suy đoán nguyên nhân. | BBS_2025 / 7 | - | UNJUSTIFIED_ABSTAIN | 0.019 |
| Q24 | So sánh cơ cấu tổng tài sản và nợ phải trả BBS cuối năm với đầu năm 2025, nêu giới hạn nhận định. | BBS_2025 / 5,6 | - | UNJUSTIFIED_ABSTAIN | 0.008 |
| Q25 | Tỷ lệ nợ trên tổng tài sản BCC 2025 là bao nhiêu và thuyết minh gì về vay và nợ thuê tài chính? | BCC_2025 / 5,6,13 | - | CORRECT | 22.132 |
| Q26 | Doanh thu thuần BBS 2025 là bao nhiêu và thuyết minh nói gì về nhân viên quản lý chủ chốt? | BBS_2025 / 7,14 | - | PARTIAL | 10.361 |
| Q27 | So sánh tăng trưởng BCC 2024 hợp nhất với BCC 2025 riêng như cùng một phạm vi kế toán. | BCC_2024 / 11 | NEGATIVE | JUSTIFIED_ABSTAIN | 0.003 |
| Q28 | BCC 2024 thuyết minh gì về tài sản đảm bảo khoản vay của Xi măng Miền Trung tại BIDV trên trang 30? | BCC_2024 / 30 | NEGATIVE | JUSTIFIED_ABSTAIN | 13.677 |

### L4

| ID | Câu hỏi | Nguồn / PDF pages | Control | Kết quả | s |
| --- | --- | --- | --- | --- | ---: |
| Q29 | Doanh thu BBS năm 2025 là bao nhiêu? | BBS_2025 / 7 | - | CORRECT | 3.869 |
| Q30 | So với năm trước thì sao? | BBS_2025 / 7 | - | CORRECT | 9.515 |
| Q31 | Biên lợi nhuận gộp năm đó thế nào? | BBS_2025 / 7 | - | CORRECT | 10.104 |
| Q32 | Công thức tính chỉ số này là gì? | BBS_2025 / 7 | - | CORRECT | 9.501 |
| Q33 | BBS 2024 ghi “Chi tiết các khoản vay ngắn hạn” ở đâu? | BBS_2024 / 21 | - | CORRECT | 1.454 |
| Q34 | Nội dung đó ở trang nào? | BBS_2024 / 21 | - | UNJUSTIFIED_ABSTAIN | 19.332 |
| Q35 | Chuyển sang BCC năm 2025: thuyết minh nói gì về vay và nợ thuê tài chính? | BCC_2025 / 13 | - | CORRECT | 6.042 |
| Q36 | Nguồn của nội dung đó ở đâu? | BCC_2025 / 13 | - | CORRECT | 7.617 |
| Q37 | Chỉ số này là bao nhiêu? | BCC_2025 /  | NEGATIVE | CLARIFICATION | 0.005 |
| Q38 | Doanh thu BCC năm 2025 là bao nhiêu? | BCC_2025 / 7 | - | CORRECT | 85.312 |
| Q39 | Còn năm 2024? | BCC_2024 / 11 | - | CORRECT | 2.291 |
| Q40 | Còn BBS năm 2025? | BBS_2025 / 7 | - | CORRECT | 9.502 |

### Rationale theo lượt

| ID | Đối chiếu độc lập |
| --- | --- |
| Q01 | Doanh thu 450474531227 VND khớp BBS 2025, B02 mã 10, PDF 7. |
| Q02 | Lợi nhuận sau thuế 7249557946 VND khớp B02 mã 60, PDF 7. |
| Q03 | Tổng tài sản 3275086920922 VND khớp BCC 2025 riêng, PDF 5. |
| Q04 | Doanh thu 3487978470438 VND khớp BCC 2024 hợp nhất, PDF 11. |
| Q05 | PDF 7 có đủ ba tên/vai trò người lập, kế toán trưởng, giám đốc; pipeline không phát hành claim. |
| Q06 | Định nghĩa nhân sự và người thân đúng; thiếu luận điểm doanh nghiệp liên quan trong reference. |
| Q07 | Trích đúng tiêu đề và vị trí PDF 21, tương ứng trang in 18. |
| Q08 | PDF 16 ghi “người nợ khó có khả năng thanh toán”; output bỏ “khó”, đảo nghĩa điều kiện dự phòng. |
| Q09 | Đủ đối tượng, khế ước, nguyên tệ và phân loại kỳ hạn 12 tháng, PDF 13. |
| Q10 | PDF 9 có doanh thu 355507372286 VND; financial catalog BBS 2024 trống, no_usable_context_evidence. |
| Q11 | Biên lợi nhuận gộp 7,21% khớp Decimal và PDF 7. |
| Q12 | Tăng trưởng 26,71% khớp hai cột doanh thu 2025/2024 trong cùng PDF 7. |
| Q13 | Tỷ lệ nợ/tài sản 59,06% khớp PDF 5/6; giữ caveat về giới hạn đánh giá thanh toán. |
| Q14 | Biên lợi nhuận gộp 10,01% khớp BCC 2025 riêng, PDF 7. |
| Q15 | Câu yoy trong cùng báo cáo riêng bị chặn cross_document_comparison_blocked_D03_B10; không agent/tool. |
| Q16 | Tỷ lệ nợ/tài sản 42,07% khớp BCC 2025 riêng, PDF 5/6. |
| Q17 | Negative control: accounting basis chưa được phê duyệt, closure chưa closed; không phát hành metric. |
| Q18 | Negative control: ROE chưa có công thức hỗ trợ; không tự tạo công thức. |
| Q19 | Hiển thị đúng công thức, hai toán hạng VND và kết quả 7,21%; reuse claim tạo ở Q11. |
| Q20 | Hai số lợi nhuận sau thuế cùng PDF 7 có sẵn nhưng bị chặn như cross-document trước execution. |
| Q21 | PAT/CFO đúng, giới hạn kết luận phù hợp; thiếu diễn giải mô tả CFO dương và lớn hơn PAT. |
| Q22 | Đủ 59,06%, chính sách 12 tháng và giới hạn đánh giá thanh toán; CORRECT dù runtime báo partial. |
| Q23 | Các cột doanh thu/lợi nhuận gộp cùng PDF 7 đủ mô tả biến động nhưng bị chặn cross-document. |
| Q24 | Số cuối/đầu năm B01 PDF 5/6 hiện hữu nhưng bị chặn cross-document trước agent/tool. |
| Q25 | Đủ 42,07% và chính sách vay 12 tháng; cùng BCC 2025 riêng, PDF 5/6/13. |
| Q26 | Doanh thu và định nghĩa nhân sự đúng; thiếu luận điểm doanh nghiệp liên quan đã nêu trong reference. |
| Q27 | Negative control: từ chối đồng nhất scope BCC 2024 hợp nhất với BCC 2025 riêng. |
| Q28 | Negative control nguồn PDF 30 quarantine: không có claim/citation phát hành; chưa kết luận cơ chế gây block. |
| Q29 | C1-T1: doanh thu BBS 2025 đúng 450474531227 VND, PDF 7. |
| Q30 | C1-T2: yoy 26,71%; năm gốc vẫn 2025, hai toán hạng thuộc 2025/2024. |
| Q31 | C1-T3: “năm đó” kế thừa BBS 2025; chuyển đúng sang gross_margin 7,21%. |
| Q32 | C1-T4: “chỉ số này” resolve gross_margin; công thức đúng, PDF 7. |
| Q33 | C2-T1: đúng heading khoản vay ngắn hạn BBS 2024, PDF 21. |
| Q34 | C2-T2: hỏi lại vị trí đoạn vừa trả Q33 nhưng bị chặn; identity đúng, follow-up chủ đề thất bại. |
| Q35 | C2-T3: chuyển đúng sang BCC 2025; chính sách vay PDF 13, không dùng nguồn BBS. |
| Q36 | C2-T4: kế thừa BCC 2025 và chủ đề vay; citations đúng PDF 13. |
| Q37 | C3-T1: session mới thiếu chỉ tiêu/công ty/năm; hỏi lại hợp lý, không tự chọn nguồn. |
| Q38 | C3-T2: đúng doanh thu BCC 2025 riêng 3696241245507 VND, PDF 7; fresh. |
| Q39 | C3-T3: chuyển đúng BCC 2024, doanh thu 3487978470438 VND, PDF 11; không lẫn 2025. |
| Q40 | C3-T4: chuyển đúng BBS 2025, giữ chủ đề doanh thu, 450474531227 VND, PDF 7. |

## Issue discovery và hướng bàn giao

** 9 issues: 1 Critical / 3 High / 4 Medium / 1 Low**, tất cả OPEN_FOR_FIX_02, root_cause = NOT_ANALYZED. [Issue Log](e2e-02-issue-log.md) và issues.json cóexpected/actual, PDF pages, trace/citation/claim, latency và reproduction. Chỉ phân nhóm triệu chứng; chưa xác minh module gây lỗi.

Nhóm cần Tech Lead xem xét cho FIX-02: tính trung thực của source/quotation và source-bound release; coverage truy vấn cơ bản/so sánh cùng PDF; completeness của phân tích giới hạn; follow-up theo chủ đề; độ trễfresh/mixed và phần trả lời dài. Không đề xuất patch theo từng câu hỏi, không mở FIX-02.

Những phần đang hoạt động tốt trong mẫu: direct values và approved metrics đã phát hành khớp PDF;formula/operand follow-up C1 đúng; mixed QA kết hợp hai loại evidence; negative controls không phát hành claim; chuyển company/year không lẫn nguồn. Giới hạn lớn nhất là quotation sai nghĩa vẫn có claim verified, một số câu cùng báo cáo bị chặn và fresh latency cao.

## Giới hạn và validation

Mẫu chẩn đoán có chủ đích, chỉ 4 PDF / 2 doanh nghiệp, không random/không benchmark M8; không full-PDF accuracy, không independent human gold. Chấm bởi Codex dựa trên PDF trước run; borderline completeness được ghi rõ (Q06/Q26). Reporting scope/cell provenance chưa hoàn thiện; BBS 2024 catalog thiếu facts và BCC 2024 basis hạn chế được giữ. Không OCR mới/Gemini/retry để chọn answer. Timing local một vòng, không HTTP/Web, không matched fresh-vs-reuse test; các timers còn thiếu được công bố.

Integrity: 572 protected files (EXT-01,GEN-01 accepted releases,source-quality,PDF và local runtime) giữ hash; questions/reference hashes không đổi. Code production local từ trước được giữ, runtime chạy từ Git snapshot. Không stage PDF/dataset/keys/full artifacts.

Checks bàn giao: smoke 2 lượt chính thức giữ trong 40; independent PDF/Decimal/binding audit 40 lượt; Ruff 2 scripts, planning checker và git diff --check. Không chạy unit M1–M7/full regression / full CI / live provider. Audit runner từng gặp lỗi duplicate id khi ghép annotation; chỉ sửa audit và chạy lại audit trên raw outputs, không chạy lại QA.

Freeze hashes: questions `2d754c51dd245fa7508b520a5a5c5bc4f971b8ffc40a18c3bf6f2905ffda8d01`; reference `bbe33a6f05e710636458804944c655790986895192f41e373011d4d5389a0018`.

Implementation SHA: `c61e15882b47e9dd8ed6852b0023ed3397aeb3c3`; evaluated runtime `39d796acba7c9eebc9ca74c6c6f564238910d3b5`.

**Status: REVIEW. Next action: Tech Lead nghiệm thu E2E-02 và quyết định phạm vi FIX-02.**
