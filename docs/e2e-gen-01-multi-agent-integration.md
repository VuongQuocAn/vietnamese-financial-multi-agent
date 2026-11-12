# E2E-GEN-01 — Kiểm thử tích hợp Multi-Agent trên dữ liệu tài chính thực tế

**REVIEW — chờ Tech Lead nghiệm thu**, ngày12/11/2026 (Asia/Bangkok).

Một lượt 12 case đã hoàn tất: 0 PASS / 5 PARTIAL / 7 FAIL. Completeness nghiêm ngặt 7/35 required points; grounded released claims 19/22. Hệ thống gọi được nhiều specialist nhưng chưa chứng minh tổng hợp đủ nhiều nhánh; chưa đủ cơ sở cho QA/report tự do trong CHAT-02/REPORT-01. Không sửa runtime hoặc tối ưu lại câu hỏi.

## 1. Phạm vi, cấu hình và reference

Đây là integration evaluation trên BBS 2025/BCC 2025; không phải benchmark M8, không rerun25case QWEN-GEN-01. Giữ phân bổ3coordination/3cross-statement/2financial+document/2multi-step/2negative. Không dùng BCC2024 vì hai báo cáo2025 đã đủ nguồn cho 12 tình huống; không loại câu khó sau khi thấy kết quả.

Baseline Git `73525f6e451bb85bc4965f8e3dec460e88a79334`; accepted runtime fix451d9fd. Working tree còn adapter Qwen và các local edits có sẵn; đánh giá **working tree frozen**, không gán kết quả cho riêng baseline hoặc CI. Toàn bộ `171` file Python runtime được hash và lưu `frozen-runtime.zip` local để giữ khả năng đối chiếu. Commit task chỉ chứa harness/tests/report/planning, không thu gom adapter/runtime có sẵn.

- Provider Qwen qua SharedLLMGateway, model alias `qwen3-8b-awq-t4`; alias do provider báo, chưa xác minh weights/revision độc lập.
- Giữ `enable_thinking=false`, temperature 0; M5/M6/M7 Lite và graph flag true; model tự chọn có dùng graph. Financial path dùng Lite composer; document path thực tế dùng source-bound verification và legacy document composer, không giả định flagLite khiến hai path giống nhau.
- Mỗi case tối đa6 provider calls, E2E budget300 s; timeout provider60 s. Output caps hiện có: supervisor900, specialists2500, M6semantic2500, M7Lite4096. Không thay timeout/prompt/model giữa các case.
- Preflight một request inference tối đa8 output tokens/30 s; partial do cap token vẫn có phản hồi. Không retry/fallback provider, không Gemini/OCR/extraction/Colab restart.
- Reference chọn từ PDF và evidence pin trước API; tính bằng Decimal độc lập, không dùng Qwen hoặc M6 làm gold.10 trang renderPDF được đọc trực tiếp: BBS5/6/7/8/12/14 và BCC5/6/7/8. Chưa independent human gold/full-PDF accuracy.
- Financial namespace: BBS `D-01/normalized-v2`; BCC `a49f826f-8e45-49c1-9e40-95f44e467e46`. Document sources dùng verified composition pins `EXT-01/BBS_2025/v1`; C07/C08 request snapshot=None, không truyền financial snapshot vào document search.
- Cột B01 so sánh giữ ngày01/01/2025 theo nguồn. BCC B03p8 có ảnh hưởng tỷ giá655.368VND: cần cộng khoản này khi đối chiếu thay đổi tiền, không coi là lỗi số học.

Freeze UTC `2026-11-12T13:00:53.597382+00:00`; reference SHA256 `8606b15bb05f614f5abac159a59c6abb49516d4feab3eeb00da27473fe2b161d`; config SHA256 `56b1c1d5fe697fef80fdb6d0fcd7a1b38c84a80bc219dfa9897537d23d115251`. URL/key chỉ ở config ignored; không ghi giá trị vào report/trace.

6 in-coverage: C01/C03/C04/C09/C11/C12.6 capability probes: C02 currentratio+tổng hợp, C05 CFO/LNST ratio, C06FX mapping, C07/C08 mixed financial-document, C10workingcapital/currentratio. “In-coverage” chỉ nói nguồn/mục tiêu có căn cứ, không hứa runtime chắc chắn trả được.

## 2. Metrics và cách chấm

PASS: mọi required point đúng/đủ; PARTIAL: có ít nhất một point đầy đủ nhưng còn thiếu; FAIL: không point đầy đủ hoặc có khẳng định trọng yếu sai. Point composite chỉ tính khi đủ nội dung; phần đạt một phần ghi riêng. Grounding đánh giá nội dung claim phát hành độc lập, không dùng ACCEPT làm gold.

Citation support được đối chiếu nội dung từng claim vớiPDF/nguồn, tách khỏi kiểm tra kỹ thuật document/snapshot/page identity. Câu từ chối không có claim phát hành không được cộng thành grounded numeric claim. Point “không suy/bịa” là ràng buộc hành vi; đạt khi không phát hành suy diễn đó, không cần bịa thêm claim để trả chỉ dẫn.

| Metric | Kết quả |
| --- | --- |
| Answer correctness/completeness toàn case | 0/12PASS; 5PARTIAL; 7FAIL |
| Required points đầy đủ | 7/35; các ý mới đạt một phần không làm tròn lên |
| Grounded claim phát hành / citation hỗ trợ đúng nội dung | 19/22;3absence claims C04 thiếu hỗ trợ ở phạm vi toàn nguồn |
| M6 native decisions | {'INVESTIGATE': 8, 'ACCEPT': 22, 'ABSTAIN': 4}; không coi ACCEPT là accuracy |
| M7 giữ ACCEPT | 22claims phát hành; accepted_not_released chi tiết trongaudit; fallback ở C01, C04 |
| Provider calls evaluation | 33; input84696, output10110, total94806tokens |
| Preflight + evaluation | 34calls; input84711, output10118; unknownusage0 |
| E2E latency/case | median51.82s; min0.05s/max140.49s; tổng707.01s, không gồm setup/preflight |

Provider latency đo ở boundary Gateway (không bao gồm CPU/tools). Đây là số đo call thực tế, không phải latency mỗi stage đầy đủ.

| Agent / stage | Calls | Tổng provider latency (s) | Input tokens | Output tokens |
| --- | ---: | ---: | ---: | ---: |
| preflight | 1 | 1.70 | 15 | 8 |
| m5-lite-supervisor | 9 | 84.85 | 22756 | 1395 |
| m5-lite-profitability | 4 | 73.34 | 9555 | 1523 |
| m6-lite | 4 | 71.26 | 13363 | 1253 |
| m7-lite | 6 | 91.56 | 19303 | 1514 |
| m5-lite-liquidity_and_leverage | 4 | 112.40 | 10217 | 2211 |
| m5-lite-cash_flow_and_earnings_quality | 4 | 76.01 | 8252 | 1503 |
| document-planner | 2 | 34.88 | 1250 | 711 |

Phối hợp đáp ứng đầy đủ: **0/3 case coordination**; C02/C03 gọi đủ ba specialist. Tool selection vẫn sai mục tiêu ở C02/C04/C08/C10 dù các fact trả về khớp nguồn. Semantic verifier được gọi thật 4 lần; 2 lần JSON fenced không đọc được. 5/33 response evaluation malformed; 0 lỗi endpoint/retry, không có case INTERRUPTED/NOT_RUN. Không có full answer đúng đủ dù một số phần có số liệu đúng.

## 3. Kết quả từng case và coordination traces

P=profitability, L=liquidity_and_leverage, C=cash_flow_and_earnings_quality. Selected/executed là trace thực tế sau validation/fallback; plan thô Qwen và effective plan được lưu riêng trong provider events/agent_stages. Đếm roles độc nhất không thay thế đánh giá phối hợp.

| Case | Company / coverage | Verdict / points | Selected → executed | M6 | Calls / latency |
| --- | --- | --- | --- | --- | --- |
| C01 | BBS_2025; in_coverage | PARTIAL; 1/3 | P → P | {'INVESTIGATE': 1, 'ACCEPT': 2} | 4 / 85.13s |
| C02 | BCC_2025; capability_probe | FAIL; 0/3 | P, L, C → P, L, C | {'ABSTAIN': 1, 'ACCEPT': 2, 'INVESTIGATE': 1} | 6 / 95.28s |
| C03 | BBS_2025; in_coverage | PARTIAL; 1/3 | P, L, C → P, L, C | {'INVESTIGATE': 2, 'ACCEPT': 4} | 6 / 115.22s |
| C04 | BBS_2025; in_coverage | FAIL; 0/3 | C, L → C, L | {'INVESTIGATE': 1, 'ACCEPT': 6} | 6 / 140.49s |
| C05 | BCC_2025; capability_probe | FAIL; 0/3 | — → — | {} | 0 / 0.05s |
| C06 | BCC_2025; capability_probe | FAIL; 0/3 | — → — | {} | 1 / 18.39s |
| C07 | BBS_2025; capability_probe | PARTIAL; 3/4 | DocPlanner, DocSupervisor, DocOrchestrator → Planner | {'ACCEPT': 1} | 1 / 29.95s |
| C08 | BBS_2025; capability_probe | FAIL; 0/3 | DocPlanner, DocSupervisor, DocOrchestrator → Planner | {} | 1 / 28.08s |
| C09 | BBS_2025; in_coverage | FAIL; 0/3 | P → P | {'ACCEPT': 5} | 3 / 73.68s |
| C10 | BCC_2025; capability_probe | FAIL; 0/3 | L → L | {'ABSTAIN': 3, 'INVESTIGATE': 3, 'ACCEPT': 2} | 3 / 106.78s |
| C11 | BCC_2025; in_coverage | PARTIAL; 1/2 | — → — | {} | 1 / 10.22s |
| C12 | BBS_2025; in_coverage | PARTIAL; 1/2 | — → — | {} | 1 / 3.74s |

### C01 — coordination

**Câu hỏi:** Lập nhận xét ngắn về BBS năm 2025 gồm ba phần: tăng trưởng doanh thu thuần so với 2024, tỷ trọng nợ trong tài sản cuối năm và dòng tiền kinh doanh. Nêu số liệu cho từng phần, không dùng một chỉ tiêu để kết luận toàn bộ sức khỏe tài chính.

**Reference độc lập:**

- Đạt: Doanh thu 450474531227/355507372286, tăng 26.71%.
- Chưa đủ: Nợ157146559558/tài sản266086680765=59.06%.
- Chưa đủ: CFO dương14319681754; tổng hợp ba nhánh có giới hạn.

**Gold lineage:** b02.net_revenue@2025 → 7/link/4; b02.net_revenue@2024 → 7/link/5; b01.total_liabilities@2025-12-31 → 6/link/0; b01.total_assets@2025-12-31 → 5/link/40; b03.operating_cash_flow@2025 → 8/link/30.
Công thức/operands chuẩn: revenue_growth=yoy(450474531227, 355507372286)=26.71313349434577638130414900; debt_share=percent(157146559558, 266086680765)=59.05840875093904477116866861.

**Coordination:** FAIL: đề xuất3roles nhưng thực thi1; thiếu debt/CFO từ M5, không phải M7 làm mất.

**Tools:** {'get_financial_fact': 4, 'get_evidence_sources': 2, 'calculate_financial_metric': 1}; semantic verifier gọi thật 1 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C01.json` và ledger tương ứng.

**Nhận định độc lập:** Thông tin phát hành đúng; thiếu hai nhánh.

**Nguyên nhân gốc:** Qwen supervisor đặt use_graph ở top-level trái LitePlan(extra=forbid), M5 fallback một profitability. M6 JSON fenced khiến analysis đúng INVESTIGATE.

**Tác động downstream:** M7 raw bỏ một ACCEPT; fallback omitted_verified_findings phục hồi đủ2/2ACCEPT.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. [1]
>
> Tăng trưởng doanh thu kỳ 2025 đạt 26,71%.
> Công thức đã xác minh: ((3. Doanh thu thuần về bán hàng và cung cấp dịch vụ - 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ) / 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ) × 100.
> 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ: 450474531227 VND; hệ số đơn vị 1; kỳ 2025.
> 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ: 355507372286 VND; hệ số đơn vị 1; kỳ 2024. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### C02 — coordination

**Câu hỏi:** Đánh giá đồng thời lợi nhuận sau thuế, khả năng thanh toán hiện hành và tiền tạo từ kinh doanh của BCC năm 2025. Cho biết số liệu và hệ số thanh toán; tách dấu hiệu rủi ro khỏi kết luận chắc chắn về mất khả năng thanh toán.

**Reference độc lập:**

- Chưa đủ: LNST47135931818 dương.
- Chưa đủ: 767374839317/1368031294449=0.56 lần, dưới1.
- Chưa đủ: CFO314097335438 dương; không suy chắc chắn mất khả năng thanh toán.

**Gold lineage:** b02.profit_after_tax@2025 → 7/link/34; b01.current_assets@2025-12-31 → 5/link/0; b01.short_term_liabilities@2025-12-31 → 6/link/2; b03.operating_cash_flow@2025 → 8/link/28.
Công thức/operands chuẩn: current_ratio=ratio(767374839317, 1368031294449)=0.5609336880163070115270902215.

**Coordination:** FAIL: cả3specialists được gọi; không tổng hợp đủ, từng specialist coi thiếu dữ liệu các nhánh khác là gap của mình.

**Tools:** {'get_financial_fact': 8, 'get_evidence_sources': 8}; semantic verifier gọi thật 1 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C02.json` và ledger tương ứng.

**Nhận định độc lập:** Hai tỷ số phát hành có toán học đúng nhưng không đáp ứng LNST/current ratio/CFO-value được hỏi. Cash/short-term debt0.21 không phải current ratio0.56.

**Nguyên nhân gốc:** M5/Qwen chọn sai operands cho thanh khoản; profitability output period_relation=same cho subtraction qua hai năm sai schema, claims=[] nên abstained.

**Tác động downstream:** M6 từ chối statement CFO đúng vì đòi đủ thông tin toàn câu hỏi, có false-negative semantic. M7 giữ2/2ACCEPT nhưng các claims không trả mục tiêu.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> (Lưu chuyển tiền thuần từ hoạt động kinh doanh (kỳ 2025) − Lưu chuyển tiền thuần từ hoạt động kinh doanh (kỳ 2024)) / Lưu chuyển tiền thuần từ hoạt động kinh doanh (kỳ 2024) × 100: 55,59 %.
> I. Tiền và các khoản tương đương tiền (kỳ 2025-12-31) / I. Nợ ngắn hạn (kỳ 2025-12-31): 0,21 lần (tỷ số đối chiếu). [1][2][3]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
>
> Nguồn tham chiếu
>
> [1] BCC 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [2] BCC 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [3] BCC 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### C03 — coordination

**Câu hỏi:** Với BBS 2025, doanh thu thuần, phải thu ngắn hạn cuối kỳ và lưu chuyển tiền kinh doanh cùng tăng hay không so với cột so sánh 2024? Dẫn số liệu cho cả ba và tránh gán nguyên nhân thu hồi nợ khi chưa đủ căn cứ.

**Reference độc lập:**

- Đạt: Doanh thu450474531227>355507372286.
- Chưa đủ: Phải thu148103395658<174725197150.
- Chưa đủ: CFO14319681754<27996254086; không cùng tăng và không suy nguyên nhân.

**Gold lineage:** b02.net_revenue@2025 → 7/link/4; b02.net_revenue@2024 → 7/link/5; b01.short_term_receivables@2025-12-31 → 5/link/6; b01.short_term_receivables@2025-01-01 → 5/link/7; b03.operating_cash_flow@2025 → 8/link/30; b03.operating_cash_flow@2024 → 8/link/31.

**Coordination:** FAIL: đủ3specialists nhưng nhánh phải thu không ra claim; không tích hợp cross-branch đúng.

**Tools:** {'get_financial_fact': 6, 'get_evidence_sources': 6}; semantic verifier gọi thật 1 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C03.json` và ledger tương ứng.

**Nhận định độc lập:** Doanh thu hai năm và26.71% đúng; CFO-48.85% đúng nhưng thiếu hai giá trị gốc; thiếu phải thu.

**Nguyên nhân gốc:** M5 liquidity abstained; profitability sinh kết luận sai rằng phải thu/CFO cùng tăng từ evidence doanh thu.

**Tác động downstream:** M6 JSON fenced lỗi ->2INVESTIGATE, chặn cả kết luận sai và CFO đúng/chuỗi số lỗi; không chứng minh semantic đã phân biệt đúng sai. M7 giữ4/4ACCEPT.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Doanh thu thuần kỳ 2024 là 355.507.372.286 VND.
> Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.
> (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. [1]
>
> (Lưu chuyển tiền thuần từ hoạt động kinh doanh (kỳ 2025) − Lưu chuyển tiền thuần từ hoạt động kinh doanh (kỳ 2024)) / Lưu chuyển tiền thuần từ hoạt động kinh doanh (kỳ 2024) × 100: -48,85 %. [2]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [2] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### C04 — cross_statement

**Câu hỏi:** CFO của BBS năm 2025 có bù được dòng tiền đầu tư âm không? Sau cả dòng tiền tài chính, tiền tăng bao nhiêu; tiền cuối kỳ trên B03 có trùng B01 không?

**Reference độc lập:**

- Chưa đủ: CFO14319681754 bù ICF-7672311772, dư6647369982.
- Chưa đủ: Trừ CFF5438868172 còn tăng1208501810.
- Chưa đủ: B03=B01=3711595064; kỳ trước2503093254.

**Gold lineage:** b03.operating_cash_flow@2025 → 8/link/30; b03.investing_cash_flow@2025 → 8/link/38; b03.financing_cash_flow@2025 → 8/link/48; b03.closing_cash@2025 → 8/link/54; b03.closing_cash@2024 → 8/link/55; b01.cash_equivalents@2025-12-31 → 5/link/2.
Công thức/operands chuẩn: after_investing=sum(14319681754, -7672311772)=6647369982; net_flows=sum(14319681754, -7672311772, -5438868172)=1208501810; cash_change=subtract(3711595064, 2503093254)=1208501810.

**Coordination:** FAIL:2unique roles/3tasks nhưng sai task và isolated evidence.

**Tools:** {'get_financial_fact': 5, 'get_evidence_sources': 5}; semantic verifier gọi thật 1 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C04.json` và ledger tương ứng.

**Nhận định độc lập:** Ba numeric/comparison claims đúng; ba câu thiếu thông tin mâu thuẫn nguồn đãpin và có mâu thuẫn nội bộ với ICF vừa phát hành.

**Nguyên nhân gốc:** M5 chuyển mục tiêu CFO bùICF thành CFF bùICF, chọn nguồn thiếu CFO; giaoB03 S31 cho liquidity bịunknown_or_foreign_source, không chia sẻ evidence giữa nhánh.

**Tác động downstream:** M6 semantic xác nhận thiếu thông tin từ riêng bundle liquidity thành claim toàn câu hỏi.3false ACCEPT. M7 giữ6/6ACCEPT và phát hành cả3unsupported absence assertions; fallback không giải quyết semantic.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Lưu chuyển tiền thuần từ hoạt động tài chính của kỳ 2025 là -5.438.868.172 VND.
> Lưu chuyển tiền thuần từ hoạt động đầu tư (kỳ 2025) > Lưu chuyển tiền thuần từ hoạt động tài chính (kỳ 2025): sai.
> Lưu chuyển tiền thuần từ hoạt động đầu tư của kỳ 2025 là -7.672.311.772 VND. [1]
>
> Không có đủ thông tin để xác định số dư tiền mặt cuối kỳ năm 2025 trên B03. Cần số dư cụ thể của B03 để so sánh với B01. [2]
>
> Không có đủ thông tin để xác định liệu CFO của BBS năm 2025 có bù được dòng tiền đầu tư âm hay không. Cần biết dòng tiền đầu tư cụ thể trong báo cáo tài chính. [2]
>
> Không có đủ thông tin để xác định số dư tiền mặt cuối kỳ năm 2025 trên B01 và B03. Cần số dư cụ thể của B01 và B03 để so sánh. [2]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [2] Tài liệu nguồn 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### C05 — cross_statement

**Câu hỏi:** Đối chiếu LNST và CFO năm 2025 của BCC: dòng tiền kinh doanh lớn hơn lợi nhuận bao nhiêu lần? Tiền cuối năm ở B01 và B03 có khớp nhau không? Không quy chênh lệch thành gian lận.

**Reference độc lập:**

- Chưa đủ: LNST47135931818/CFO314097335438; CFO/LNST=6.66 lần.
- Chưa đủ: B01=B03=285165801455.
- Chưa đủ: Không gán chênh lệch cho gian lận.

**Gold lineage:** b02.profit_after_tax@2025 → 7/link/34; b03.operating_cash_flow@2025 → 8/link/28; b01.cash_equivalents@2025-12-31 → 5/link/2; b03.closing_cash@2025 → 8/link/52.
Công thức/operands chuẩn: cfo_to_profit=ratio(314097335438, 47135931818)=6.663649647381200308575174798.

**Coordination:** NOT_EXECUTED do context gate.

**Tools:** {}; semantic verifier gọi thật 0 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C05.json` và ledger tương ứng.

**Nhận định độc lập:** Không trả lời dù binding và nguồn hợp lệ;0 APIcalls.

**Nguyên nhân gốc:** Runtime context parser hiểu từ quy trong “không quy chênh lệch thành gian lận” là quý kế toán ->non_annual_period_unsupported ->requested_period_unresolved. Offlineunderstand xác nhận, không rerunpipeline/API.

**Tác động downstream:** Chưa đếnM5/M6/M7; không quy lỗi cho composer/harness snapshot.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Cần làm rõ tài liệu, snapshot, kỳ, chỉ tiêu hoặc phạm vi báo cáo.

### C06 — cross_statement

**Câu hỏi:** Hãy đối chiếu biến động tiền BCC 2025: cộng CFO, dòng tiền đầu tư và tài chính rồi so với tiền cuối năm trừ đầu năm. Chênh lệch có bằng ảnh hưởng tỷ giá ở B03 không, và tiền cuối năm có khớp B01?

**Reference độc lập:**

- Chưa đủ: Tổng3luồng134756261025.
- Chưa đủ: Tiền cuối285165801455-đầu150408885062=134756916393.
- Chưa đủ: Chênh655368 là tỷ giá B03; cuối khớpB01.

**Gold lineage:** b03.operating_cash_flow@2025 → 8/link/28; b03.investing_cash_flow@2025 → 8/link/36; b03.financing_cash_flow@2025 → 8/link/44; b03.opening_cash@2025 → 8/link/48; b03.closing_cash@2025 → 8/link/52; b01.cash_equivalents@2025-12-31 → 5/link/2.
Công thức/operands chuẩn: net_flows=sum(314097335438, -172076818813, -7264255600)=134756261025; cash_change=subtract(285165801455, 150408885062)=134756916393.

**Coordination:** NOT_EXECUTED do invalid supervisor output.

**Tools:** {}; semantic verifier gọi thật 0 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C06.json` và ledger tương ứng.

**Nhận định độc lập:** Không có câu trả lời cho reconciliation tiền/FX; không hallucinate số.

**Nguyên nhân gốc:** Qwen supervisor malformed structured_output_invalid ->supervisor_provider_failure; lexicalfallback tasks=[] ->0candidates.

**Tác động downstream:** FX row còn thiếu canonical mapping nhưng chưa phải nguyên nhân thực nghiệm lượt này: pipeline dừng trước retrieval. M6 không chạy.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.

### C07 — financial_document

**Câu hỏi:** Nêu LNST BBS năm 2025 rồi đối chiếu chính sách chi phí đi vay trong thuyết minh: khoản nào ghi chi phí, khoản nào có thể vốn hóa? Không suy ra số lãi vay vốn hóa thực tế từ chính sách.

**Reference độc lập:**

- Chưa đủ: LNST7249557946.
- Đạt: Thông thường ghi chi phí khi phát sinh.
- Đạt: Vốn hóa tài sản dở dang đủ điều kiện VAS16; vay riêng xây dựngTSCĐ kể cả<=12tháng.
- Đạt: Không suy số vốn hóa thực tế.

**Gold lineage:** b02.profit_after_tax@2025 → 7/link/34.
Document gold: artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json::unified/page/12/text/text_elements/8; artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json::unified/page/12/text/text_elements/9; artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json::unified/page/12/text/text_elements/10; artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json::unified/page/12/text/text_elements/11.

**Coordination:** FAIL mixed evidence: Planner được gọi, financial branch không thực thi; không phải bindingconfound.

**Tools:** {'search_document_evidence': 5, 'get_evidence_sources': 5}; semantic verifier gọi thật 0 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C07.json` và ledger tương ứng.

**Nhận định độc lập:** Chính sách trích dẫn đúngPDFp12, không bịa số vốn hóa; thiếu LNST.

**Nguyên nhân gốc:** document_intent chuyển cả câu mixed sang document path; requirements bỏ nhánh tài chính LNST, fusion_bundle={} và không gọi financialspecialists.

**Tác động downstream:** M7 document legacy coi chỉ dẫn “không suy ra số vốn hóa” là requirement dữ liệu còn thiếu, sinhgap sai. M6 source excerpt ACCEPT đúng,0 semantic call.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Theo các nội dung đã được xác minh trong ledger:
> Tài liệu ghi «4.12. Chi phí đi vay Chi phí đi vay bao gồm lãi tiền vay và các chi phí khác liên quan trực tiếp đến các khoản vay. Chi phí đi vay được ghi nhận vào chi phí sản xuất, kinh doanh trong năm khi phát sinh, ngoại trừ chi phí đi vay liên quan trực tiếp đến việc đầu tư, xây dựng hoặc sản xuất tài sản dở dang cần có một thời gian đủ dài (trên 12 tháng), để có thể đưa vào sử dụng theo mục đích định trước hoặc bán, được tính vào giá trị của tài sản đó (được vốn hóa) khi có đủ các điều kiện quy định của Chuẩn mực kế toán Việt Nam số 16 - Chi phí đi vay. Đối với khoản vay riêng phục vụ việc xây dựng tài sản cố định, lãi vay được vốn hóa kể cả khi thời gian xây dựng từ 12 tháng trở xuống. Đối với các khoản vốn vay chung, trong đó có sử dụng cho mục đích đầu tư xây dựng hoặc sản xuất tài sản dở dang thì số chi phí đi vay được vốn hóa được xác định theo tỷ lệ vốn hóa đối với chi phí lũy kế bình quân gia quyền phát sinh cho việc đầu tư xây dựng hoặc sản xuất tài sản đó. Tỷ lệ vốn hóa được tính theo tỷ lệ lãi suất bình quân gia quyền của các khoản vay chưa trả trong năm, ngoại trừ các khoản vay riêng biệt phục vụ cho mục đích hình thành một tài sản cụ thể.» [1][2][3][4][5]
> Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.
> Các yêu cầu chưa đáp ứng: Không suy ra số lãi vay vốn hóa thực tế từ chính sách (chưa có nguồn đủ căn cứ).
> Lưu ý: Trích từ bản nhận dạng đã lưu, với vị trí chứng cứ ở cấp độ nguồn ghi nhận.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> Giới hạn: Nội dung phản ánh tài liệu đã lưu.; Trích đoạn liên quan; chưa bao phủ toàn bộ thuyết minh.; Nguồn đã đối chiếu chỉ bao phủ các phần có bằng chứng được lưu.
>
> Lưu ý nguồn: Trích từ bản nhận dạng đã lưu, với vị trí chứng cứ ở cấp độ nguồn ghi nhận.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Giới hạn nguồn: Nội dung phản ánh tài liệu đã lưu.; Trích đoạn liên quan; chưa bao phủ toàn bộ thuyết minh.; Nguồn đã đối chiếu chỉ bao phủ các phần có bằng chứng được lưu.; Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
>
> ## Nguồn tham chiếu
>
> [1] BBS 2025 — Trang PDF 12. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
>
> [2] BBS 2025 — Trang PDF 12. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
>
> [3] BBS 2025 — Trang PDF 12. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
>
> [4] BBS 2025 — Trang PDF 12. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
>
> [5] BBS 2025 — Trang PDF 12. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.

### C08 — financial_document

**Câu hỏi:** Đối chiếu khoản tiền cuối năm 2025 trên B01 của BBS với thuyết minh mục 5 Tiền: nêu tiền mặt, tiền gửi ngân hàng và tổng cộng. Cộng hai thành phần để xác nhận có khớp B01 hay không.

**Reference độc lập:**

- Chưa đủ: B01=3711595064.
- Chưa đủ: Thuyết minh tiền mặt414172099,tiền gửi3297422965.
- Chưa đủ: 414172099+3297422965=3711595064 khớp.

**Gold lineage:** b01.cash_equivalents@2025-12-31 → 5/link/2.
Document gold: artifacts/gemini-ingestion/M1-15/pdf/page-14.json::unified/page/14/table/tables/0.

**Coordination:** FAIL mixed evidence: không tài chính/tabletool/calculator; đúngdocumentbinding(snapshot=None).

**Tools:** {'search_document_evidence': 1}; semantic verifier gọi thật 0 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C08.json` và ledger tương ứng.

**Nhận định độc lập:** Không trả các thành phần tiền dù bảngp14 đãpin và số B01 sẵn có.

**Nguyên nhân gốc:** Mixed request chuyển documentpath; search_document_evidence(evidence_type=text) với query nguyên requirement tìmnot_found, bỏ table cần thiết.

**Tác động downstream:** Không có candidates/M6; M7 blocked đúng với ledger rỗng nhưng không chứng minh nguồn không có dữ liệu.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Chưa có đủ claim đã xác minh cho yêu cầu này trong ledger.
> Các yêu cầu chưa đáp ứng: Đối chiếu khoản tiền cuối năm 2025 trên B01 của BBS với thuyết minh mục 5 Tiền: nêu tiền mặt, tiền gửi ngân hàng (chưa có nguồn đủ căn cứ).
> Giới hạn: Nguồn đã đối chiếu chỉ bao phủ các phần có bằng chứng được lưu.
>
> Giới hạn nguồn: Nguồn đã đối chiếu chỉ bao phủ các phần có bằng chứng được lưu.

### C09 — multi_step

**Câu hỏi:** Tính biên lợi nhuận gộp BBS cho cả 2024 và 2025 rồi lấy biên 2025 trừ biên 2024, đơn vị điểm phần trăm. Đối chiếu với chiều tăng doanh thu, không tự suy nguyên nhân giảm biên.

**Reference độc lập:**

- Chưa đủ: Biên2025=7.21%.
- Chưa đủ: Biên2024=10.25%.
- Chưa đủ: Giảm3.04điểm%, trong khi doanh thu tăng; không suy nguyên nhân.

**Gold lineage:** b02.gross_profit@2025 → 7/link/8; b02.net_revenue@2025 → 7/link/4; b02.gross_profit@2024 → 7/link/9; b02.net_revenue@2024 → 7/link/5.
Công thức/operands chuẩn: margin_2025=percent(32482519668, 450474531227)=7.210733885337378614260469821; margin_2024=percent(36432410381, 355507372286)=10.24800418250980968068981262; margin_delta=margin_delta(32482519668, 450474531227, 36432410381, 355507372286)=-3.037270297172431066429342799.

**Coordination:** Một profitability phù hợp, không cần ép nhiềuagent; thất bại nằm ở operators/unit/completeness.

**Tools:** {'get_financial_fact': 4, 'get_evidence_sources': 4}; semantic verifier gọi thật 0 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C09.json` và ledger tương ứng.

**Nhận định độc lập:** Bốn facts đúng, ratio/ratio-delta đúng toán học nhưng trả0.07/0.10/-0.03 lần thay vì7.21%/10.25%/-3.04điểm%; không đạt định dạng/đơn vị yêu cầu.

**Nguyên nhân gốc:** M5/Qwen dùng operator ratio và subtract không chuyển*100/percentage-point; generated analysis mất do schema, chỉ derived_fact phát hành.

**Tác động downstream:** M6 deterministic kiểm toán học đúng trên phép được yêu cầu bởi model, không chứng minh đáp ứng mục tiêu người dùng; semantic_calls=0. M7 giữ5/5ACCEPT, không tự đổi đơn vị.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND.
> Doanh thu thuần kỳ 2024 là 355.507.372.286 VND.
> Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.
> Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. [1]
>
> Lợi nhuận gộp (kỳ 2025) / Doanh thu thuần (kỳ 2025): 0,07 lần (tỷ số đối chiếu). Lợi nhuận gộp (kỳ 2024) / Doanh thu thuần (kỳ 2024): 0,10 lần (tỷ số đối chiếu). kết quả phép tính thứ 1 − kết quả phép tính thứ 2: -0,03 lần (tỷ số đối chiếu). Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024): 94.967.158.941,00 VND. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Giới hạn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### C10 — multi_step

**Câu hỏi:** Tại 31/12/2025, BCC có vốn lưu động ròng (tài sản ngắn hạn trừ nợ ngắn hạn) bao nhiêu và hệ số thanh toán hiện hành mấy lần? Đặt hai kết quả bên cạnh CFO dương năm 2025 và nêu giới hạn khi đánh giá thanh khoản.

**Reference độc lập:**

- Chưa đủ: Vốn lưu động ròng-600656455132.
- Chưa đủ: Hệ số0.56 lần.
- Chưa đủ: CFO314097335438 dương không chứng minh chắc chắn thanh toán tương lai.

**Gold lineage:** b01.current_assets@2025-12-31 → 5/link/0; b01.short_term_liabilities@2025-12-31 → 6/link/2; b03.operating_cash_flow@2025 → 8/link/28.
Công thức/operands chuẩn: working_capital=subtract(767374839317, 1368031294449)=-600656455132; current_ratio=ratio(767374839317, 1368031294449)=0.5609336880163070115270902215.

**Coordination:** FAIL: mục tiêu cầnL+C nhưng chỉL; không lấyCFO.

**Tools:** {'get_financial_fact': 4, 'get_evidence_sources': 4, 'calculate_financial_metric': 1}; semantic verifier gọi thật 0 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C10.json` và ledger tương ứng.

**Nhận định độc lập:** M6 chặn đúng analysis có phép trừ sai-599656455132; nhưng cũngINVESTIGATE các derived results đúng-600656455132 và0.56 cùng factcurrentassets. Final chỉ nợ/totalassets42.07% và nợngắnhạn, không trả3ý.

**Nguyên nhân gốc:** M5 chọn source sai/thừa metricdebt_to_assets, chỉ giaoL nên thiếuCFO. M6 numeric binding/context từ chối cả3candidate đúng(content_period_unbound/numeric_assertion_not_unambiguously_bound), gâyfalse negatives.

**Tác động downstream:** Hai proof động có kết quả đúng đã sinh tạiM5; không gọi đây là calculator không hỗ trợ.3analysis bịlite_unbound_number,0 semantic call. M7 giữ2/2ACCEPT; thiếuanswer bắt đầu trướcM7.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 42,07%.
> Công thức đã xác minh: (C - NỢ PHẢI TRẢ / TỔNG CỘNG TÀI SẢN) × 100.
> C - NỢ PHẢI TRẢ: 1377855526955 VND; hệ số đơn vị 1; kỳ 2025-12-31.
> TỔNG CỘNG TÀI SẢN: 3275086920922 VND; hệ số đơn vị 1; kỳ 2025-12-31. [1][2]
>
> I. Nợ ngắn hạn tại ngày 2025-12-31 là 1.368.031.294.449 VND. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.
>
> Nguồn tham chiếu
>
> [1] BCC 2025 — Trang PDF 6. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [2] BCC 2025 — Trang PDF 5. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

### C11 — negative

**Câu hỏi:** Chỉ dựa vào BCTC BCC 2025, hãy khẳng định chắc chắn công ty sẽ không trả được nợ năm 2026. Nếu bằng chứng không cho phép khẳng định, hãy nói rõ thay vì suy từ nợ ngắn hạn.

**Reference độc lập:**

- Đạt: Không thể khẳng định chắc chắn mất khả năng thanh toán2026.
- Chưa đủ: Dữ liệu lịch sử không đủ dự báo nghĩa vụ/dòng tiền2026.

**Gold lineage:** b01.short_term_liabilities@2025-12-31 → 6/link/2.

**Coordination:** NOT_EXECUTED; không có lý do cần gọi nhiềuagent cho yêu cầu vượt nguồn.

**Tools:** {}; semantic verifier gọi thật 0 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C11.json` và ledger tương ứng.

**Nhận định độc lập:** Không khẳng định chắc chắn mất khả năng thanh toán; chỉ báo thiếu kết luận, chưa giải thích giới hạn dữ liệu lịch sử/tươnglai.

**Nguyên nhân gốc:** Supervisor structuredoutputinvalid ->fallback tasks=[]; dừng trước retrieval/M6.

**Tác động downstream:** Safe non-answer do lỗi model, không phải bằng chứng evidence-limit reasoning thành công; không dùng làmPASS financialquality.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.

### C12 — negative

**Câu hỏi:** Từ báo cáo BBS 2025 đang chọn, hãy cho số CFO thực tế năm 2026 cùng trang chứng minh. Nếu báo cáo không có số này, không thay bằng CFO 2025 hoặc dự báo.

**Reference độc lập:**

- Chưa đủ: Không có CFO thực tế2026 trong báo cáo2025.
- Đạt: Không bịa số/trang hoặc thay bằng năm2025.

**Gold lineage:** No actual 2026 cash flow in pinned2025 report.

**Coordination:** NOT_EXECUTED; từ chối không cần ép nhiềuspecialist.

**Tools:** {}; semantic verifier gọi thật 0 lần. Claims/citations, tool arguments/results, proof operands và source identities đầy đủ trong `execution/C12.json` và ledger tương ứng.

**Nhận định độc lập:** Không bịa CFO2026/sốtrang hay thay2025; thiếu giải thích rõ báo cáo2025 không có actual 2026.

**Nguyên nhân gốc:** Supervisor structuredoutputinvalid ->fallback tasks=[]; không tới truy xuất evidence hoặcM6.

**Tác động downstream:** Safe abstention do output hỏng; chưa chứng minh phát hiện thiếucoverage chủ động.

**Câu trả lời cuối nguyên văn (citations giữ số hiển thị của case):**

> Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi.

## 4. Tools, calculations, M6 và evidence lineage

Financial retrieval giữ source identity và chất lượng/caveat; provenance hiện còn page-level, không tuyên bố exact cell geometry. Toán học đúng trên operands model chọn không đồng nghĩa chọn đúng chỉ tiêu hoặc đơn vị người dùng hỏi (C02 cash ratio/current ratio; C09 ratio/percentage point). C04 thiếu chia sẻ evidence liên nhánh khiến assertion “thiếu thông tin” bị nâng thành kết luận toàn nguồn.

Audit kỹ thuật: `{'retrieved_fact_checked': 60, 'final_source_identity_checked': 133, 'citation_group_binding_checked': 133, 'released_ledger_membership_checked': 12, 'release_ids_checked': 12, 'calculation_operand_checked': 16, 'arithmetic_step_checked': 9, 'unrecomputed_operator_greater': 1}`. Failures: `[]`. 778 protected files unchanged=True; references/config unchanged=True. Đây là checks identity/proof/integrity, tách khỏi chấm nội dungPDF thủ công.

M6: C01/C03 JSON fenced khiến semantic verdict không đọc được, giữINVESTIGATE; không dùng việc chặn do lỗiJSON làm bằng chứng verifier hiểu đúng sai. C02 có false-negative với statementCFO đúng vì verifier đòi thông tin các nhánh khác. C04 có3 false-positive source-absence assertions từ bundle hẹp. C07exact-source excerpt đúng; không có semanticcritic call. Không thêm verifier hay vòngFIX.

Ledger/M7: đối chiếu used_verified_claim_ids với ledger và released IDs; document path dùng document_release requirement IDs, không ép schemaLite. M7 không tự tạo số liệu tài chính mới trong lượt này, nhưng có thể phát hành claim đãACCEPT sai phạm vi(C04). C01/C04 fallback omitted_verified_findings phục hồi nội dung rawM7 bỏ; không xem raw omission là mấtclaim sau finalrelease.

## 5. Kết luận theo mục tiêu task và giới hạn

DACNTT thực thi được nhiều specialist trong một câu, nhưng3 case coordination chưa có case trả đủ cả3 nhánh. EF-EG đưa được facts đãpin vào tools; chưa chứng minh phối hợp đủ vì M5 có thể chọn sai sources/role, làm rơi analysis do schema hoặc không chia sẻ evidence. Hai mixed probes chưa hợp nhất được financial+document: C07trích đúngB09 nhưng mấtLNST, C08chọntext thaytable.

Điểm nghẽn quan sát được nằm ở Qwen structured output + M5 task/operand routing, context parser, và kiểm ngữ nghĩa phạm vi tại M6; không đủ bằng chứng quy mọiFAIL cho OCR hay cho M7. FX canonical coverage là giới hạn có thật nhưngC06dừng trước retrieval, chưa đo được ảnh hưởng riêng. Không có baseline single-agent/ablation, vì vậy không kết luận Multi-Agent cải thiện accuracy/latency bao nhiêu.

Chưa chứng minh financial accuracy toàn báo cáo/dataset, multi-year/consolidated-versus-separate toàn diện, độ ổn định nhiều lần chạy, model weights/revision, hoặc prompt/context khác. C05blocked0 API không phải thành công tiết kiệmquota. Các negative được chấm nội dung riêng ở C11/C12, không suy khả năng dự báo thực tế.

Chưa có cơ sở GO cho CHAT-02/REPORT-01 với yêu cầu tự do: trước hết cần Tech Lead quyết định phạm vi sửa tổng quát cho schema/task/evidence aggregation và scope của absence claims; table-aware mixed routing và unit/coverage là các giới hạn cần cân nhắc. Không tự mở task FIX, không đổi pipeline trong evaluation.

## 6. Artifacts, validation và bàn giao

Local ignored `artifacts/evidence/E2E-GEN-01/` chứa references/catalogs/coverage/freeze/config; exact runtime zip; provider-events lưu ngay từng call;12 execution files+ledgers; results/integrity/audit/manual-audit/context-diagnostic; prepare/inspect/audit/report scripts. Các file tài chính, ảnh và cấu hình bí mật không được commit. `completion-receipt.json` ghi SHA task sau commit/push và hash artifacts để đối chiếu.

Engineering validation:3 targeted offline harness controls PASS; Ruff lint/format, planning checker và diffcheck. Không chạy full CI/M8/Gemini/OCR; local checks không được trình bày thànhCI hoặc financial accuracy. Transcript giữ lỗi fixture thiếu generation ban đầu và lần sửa đãPASS. Task chưa tự chuyển DONE.

**Next action:** Tech Lead nghiệm thu báo cáo và quyết định phạm vi xử lý các lỗi tổng quát trước CHAT-02/REPORT-01.
