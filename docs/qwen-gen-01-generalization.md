# QWEN-GEN-01 — Khả năng tổng quát hóa Multi-Agent với Qwen

Ngày 12/11/2026 (Asia/Bangkok). **REVIEW — chờ Tech Lead nghiệm thu báo cáo**.
Một lượt 25 attempts đã kết thúc; **21 case có thể đánh giá, 4 case UNCERTAIN do harness**.
Không phải benchmark M8 hoặc bằng chứng pipeline đã ổn định. Không có thay đổi runtime trong task.

## Kết quả chính

Hệ thống có thể thực hiện một số so sánh và phép trừ mới đúng trên BBS/BCC, nhưng chưa tổng quát hóa ổn định. Trong 16 câu có đáp án nguồn và request hợp lệ, 4 câu trả lời đủ; 3 câu trả lời một phần. Bốn trong năm câu thiếu bằng chứng có hành vi từ chối phù hợp, nhưng thiếu giải thích cụ thể. Có hai claim được phát hành thiếu hỗ trợ, gồm một định nghĩa/phép tính sai về giảm trừ doanh thu. M6 ACCEPT không được dùng làm ground truth.

**Hạn chế phương pháp:** tôi đã dùng harness kế thừa từ hai câu financial-only và bind snapshot tài chính cho cả câu thuyết minh. Q16/Q17 bị chặn ngay bởi `document_snapshot_not_in_composition`; Q19/Q20 tìm kiếm trong snapshot tài chính, không chứa đoạn note thuộc unified snapshot đã pin trong reference. Đây là lỗi binding của harness, không phải bằng chứng Qwen/BM25 không đọc được thuyết minh. Bốn case được giữ `UNCERTAIN`, loại khỏi denominator hợp lệ; không sửa reference/request giữa lượt hoặc chạy lại để cải thiện kết quả. Nhóm interpretation vì vậy chưa được đánh giá đầy đủ.

## Cấu hình, thời điểm và tính bất biến

- Baseline Git: `837975adf2f56dcb02441691e7dfaf405365f207` trên main. Runtime là baseline cộng các local dependencies/edits đã có, gồm adapter Qwen chưa commit từ task trước; không phải pristine commit. Hash từng file Python và bản sao source local lưu cùng freeze.
- Qwen3-8B-AWQ, alias yêu cầu và provider báo `qwen3-8b-awq-t4`, API OpenAI-compatible qua SharedLLMGateway. URL/key ở config owner-supplied được Git ignore, không ghi vào report/traces. Không xác minh độc lập revision weights từ alias.
- `M5 Lite → EF-EG/Financial Tools → M6 Lite → M7 Lite`, graph bật; document intent vẫn đi DocumentPlanner/BM25 theo routing hiện có. Không ép mọi câu đi đủ mọi stage nếu pipeline dừng sớm.
- Mỗi case ledger mới, `force_refresh=true`, mode auto, max6provider calls/case, deadline300s/case. Không retry provider, không fallback model, không Gemini/Vision/OCR, không đổi prompt theo từng case, không full CI/M8.
- Temperature0 và `enable_thinking=false`; inference defaults theo từng agent giữ nguyên trong cả lượt. Các tham số không được request truyền, như top_p, dùng default endpoint; không tự gán giá trị đã pin.

| Stage | max_output_tokens | Timeout/request |
| --- | ---: | ---: |
| Supervisor Lite | 900 | 60s |
| Financial Specialist / M6 semantic | 2500 | 60s |
| M7 Lite | 4096 | 60s |
| DocumentPlanner | 3000 | 45s |

Preflight ban đầu đã dừng task với provider_unavailable, không chạy case. Sau Owner cung cấp config mới, đúng một preflight mới phản hồi inference: 15input+8output=23tokens,1,373s, status partial do cap8tokens. Đây là kiểm tra kết nối, không phải một case hoặc một lần chạy lại evaluation. Lượt evaluation hiện tại có61calls/133709tokens; tính cả preflight mới là62calls/133732known tokens. Attempt mất kết nối của checkpoint trước không có usage, giữ UNKNOWN, không ghi thành0tokens.

- Freeze references: `2026-11-12T11:40:20.846572+00:00` (UTC).
- Bắt đầu runner: `2026-11-12T11:41:15.693222+00:00` (UTC).
- Kết thúc runner: `2026-11-12T11:56:19.253160+00:00` (UTC).

Runtime hashes và frozen input files **unchanged** sau lượt chạy. Reference được tạo trước case inference đầu tiên, dựa trên catalog/evidence và đọc trực tiếp13trang PDF: BBS2025:p5,7,8,12,14; BCC2025:p5,6,7,8,13; BCC2024:p11,16,17. PDF SHA khớp manifest. Phép tính Decimal độc lập, không lấy answer Qwen/verdict M6 để sửa reference. Đây là source-first review của Codex, chưa phải independent human gold hay audit toàn PDF.

## 25 câu hỏi và reference đã cố định

Ba tài liệu: BBS_2025.pdf; BCC_2025.pdf (riêng); BCC_2024.pdf (hợp nhất). Các kỳ2023/2024/2025 được dùng trong cùng filing tương ứng; không trộn cột2024 của báo cáo riêng2025 với báo cáo hợp nhất2024. Không dùng lại hai câu QWEN-QA-01. Một số chủ đề note đã xuất hiện trong nghiên cứu GEN-02 trước đây; đây là tập mới so với hai câu Qwen đã dùng sửa lỗi, không tuyên bố globally blind holdout. Không thêm doanh nghiệp khác chỉ có ảnh/OCR nhưng chưa có EF-EG/composition sẵn để dùng.

Reference đầy đủ gồm company/document/snapshot/period, difficulty, required points, fact/record IDs, source pointers, formulas/operands nằm trong `references.json`, SHA-256 `709e6a3e048a87707bf3e7bfa5720af26ebd58ff6c1fcf7418fef7dbdf829c40`. Snapshot nguồn và metadata không bị suy đoán hoặc sửa. Bảng dưới là bản tóm tắt; các ý ngăn bởi dấu chấm phẩy đều là yêu cầu reference.

| ID | Nhóm / độ khó | Company/document và kỳ | Câu hỏi | Expected answer / các ý bắt buộc | Evidence PDF / selectors | Công thức và operands độc lập |
| --- | --- | --- | --- | --- | --- | --- |
| Q01 | single_hop/easy | BBS_2025; 2025-12-31 | Hàng tồn kho của BBS tại ngày 31/12/2025 là bao nhiêu VND? | 50.788.605.600 VND, đúng ngày 31/12/2025 | p5 | b01.inventory_total@2025-12-31=50788605600 VND |
| Q02 | single_hop/easy | BCC_2025; 2025-12-31 | Tài sản ngắn hạn BCC tại ngày 31/12/2025 là bao nhiêu? | 767.374.839.317 VND | p5 | b01.current_assets@2025-12-31=767374839317 VND |
| Q03 | single_hop/easy | BCC_2024; 2024 | Báo cáo hợp nhất BCC năm 2024 ghi nhận lãi hay lỗ sau thuế và số tiền bao nhiêu? | Lỗ sau thuế 8.133.426.100 VND; không nhầm với cột so sánh riêng trong báo cáo2025 | p11 | b02.profit_after_tax@2024=-8133426100 VND |
| Q04 | single_hop/easy | BBS_2025; 2025 | Lưu chuyển tiền thuần từ hoạt động đầu tư BBS năm 2025 là bao nhiêu, mang dấu dương hay âm? | Âm 7.672.311.772 VND | p8 | b03.investing_cash_flow@2025=-7672311772 VND |
| Q05 | single_hop/easy | BCC_2025; 2025 | Các khoản giảm trừ doanh thu của BCC năm 2025 là bao nhiêu? | 173.405.357.408 VND | p7 | b02.revenue_deductions@2025=173405357408 VND |
| Q06 | multi_hop/hard | BBS_2025; 2024,2025 | Doanh thu thuần và lợi nhuận gộp BBS năm 2025 so với 2024 có cùng chiều biến động không? Nêu số liệu hai năm cho cả hai chỉ tiêu. | Doanh thu tăng:450474531227 so với355507372286; Lợi nhuận gộp giảm:32482519668 so với36432410381; Hai chỉ tiêu ngược chiều; không suy nguyên nhân | p7 | b02.net_revenue@2025=450474531227 VND; b02.net_revenue@2024=355507372286 VND; b02.gross_profit@2025=32482519668 VND; b02.gross_profit@2024=36432410381 VND |
| Q07 | multi_hop/medium | BCC_2025; 2024,2025 | Dòng tiền kinh doanh BCC năm 2025 tăng hay giảm so với 2024 và chênh lệch bao nhiêu VND theo cùng báo cáo năm 2025? | 2025:314097335438;2024:201870668494; Tăng112226666944 VND | p8 | b03.operating_cash_flow@2025=314097335438 VND; b03.operating_cash_flow@2024=201870668494 VND; a-b, a=314097335438, b=201870668494 ⇒ 112226666944 |
| Q08 | multi_hop/hard | BCC_2024; 2023,2024 | Theo báo cáo hợp nhất BCC 2024, doanh thu thuần và kết quả sau thuế thay đổi thế nào từ 2023 sang 2024? Doanh nghiệp đã hết lỗ chưa? | Doanh thu tăng3487978470438 từ3081365372469; Lỗ giảm từ233536479368 còn8133426100; Vẫn lỗ, không kết luận chuyển lãi | p11 | b02.net_revenue@2024=3487978470438 VND; b02.net_revenue@2023=3081365372469 VND; b02.profit_after_tax@2024=-8133426100 VND; b02.profit_after_tax@2023=-233536479368 VND |
| Q09 | multi_hop/hard | BCC_2025; 2024,2025 | Từ báo cáo BCC năm 2025, lợi nhuận gộp tăng bao nhiêu phần trăm và tốc độ đó cao hay thấp hơn tăng trưởng doanh thu thuần so với cột 2024? | Tính đủ hai tốc độ từ cùng báo cáo riêng2025; Tốc độ tăng lợi nhuận gộp cao hơn doanh thu | p7 | b02.gross_profit@2025=369838783346 VND; b02.gross_profit@2024=306759698803 VND; b02.net_revenue@2025=3696241245507 VND; b02.net_revenue@2024=3487978470438 VND; (a/b-1)*100, a=369838783346, b=306759698803 ⇒ 20.56302858202673041043525700; (a/b-1)*100, a=3696241245507, b=3487978470438 ⇒ 5.970873296211819075895621400 |
| Q10 | multi_hop/medium | BBS_2025; 2024,2025,2025-12-31 | Tiền cuối năm 2025 trên báo cáo lưu chuyển tiền tệ BBS có khớp tiền và tương đương tiền trên bảng cân đối kế toán không? So với tiền cuối năm 2024 tăng hay giảm? | Hai bảng đều3711595064 VND; So với2503093254 VND năm2024 là tăng; dẫn cả B01 và B03 | p5,8 | b03.closing_cash@2025=3711595064 VND; b01.cash_equivalents@2025-12-31=3711595064 VND; b03.closing_cash@2024=2503093254 VND |
| Q11 | numerical/medium | BBS_2025; 2025 | Tính biên lợi nhuận gộp BBS năm 2025, nêu công thức và hai số đầu vào. | Lợi nhuận gộp/doanh thu thuần*100; Cả hai operands đúng kỳ, kết quả làm tròn2chữ số | p7 | b02.gross_profit@2025=32482519668 VND; b02.net_revenue@2025=450474531227 VND; a/b*100, a=32482519668, b=450474531227 ⇒ 7.210733885337378614260469821 |
| Q12 | numerical/medium | BCC_2025; 2025-12-31 | Nợ phải trả chiếm bao nhiêu phần trăm tổng tài sản BCC tại ngày 31/12/2025? Nêu phép tính. | Nợ/tài sản*100, operands đúng ngày; Kết quả% đúng trong0,01điểm% | p5,6 | b01.total_liabilities@2025-12-31=1377855526955 VND; b01.total_assets@2025-12-31=3275086920922 VND; a/b*100, a=1377855526955, b=3275086920922 ⇒ 42.07080789682086212207496622 |
| Q13 | numerical/medium | BBS_2025; 2024,2025 | Lợi nhuận sau thuế BBS năm 2025 cao hơn năm 2024 bao nhiêu VND? Nêu phép trừ. | 7249557946-6189585588=1059972358 VND; Tăng, không nhầm tỷ lệ phần trăm | p7 | b02.profit_after_tax@2025=7249557946 VND; b02.profit_after_tax@2024=6189585588 VND; a-b, a=7249557946, b=6189585588 ⇒ 1059972358 |
| Q14 | numerical/medium | BCC_2025; 2025-12-31 | Hệ số thanh toán hiện hành BCC ngày 31/12/2025 bằng bao nhiêu lần? Dùng tài sản ngắn hạn và nợ ngắn hạn. | 767374839317/1368031294449; Đơn vị lần; dưới1 không phải% | p5,6 | b01.current_assets@2025-12-31=767374839317 VND; b01.short_term_liabilities@2025-12-31=1368031294449 VND; a/b, a=767374839317, b=1368031294449 ⇒ 0.5609336880163070115270902215 |
| Q15 | numerical/medium | BCC_2024; 2023,2024 | Doanh thu thuần trong báo cáo hợp nhất BCC năm 2024 tăng bao nhiêu phần trăm so với 2023? Nêu công thức và số liệu. | (3487978470438/3081365372469-1)*100; Đúng cột2024/2023 trong cùng báo cáo hợp nhất | p11 | b02.net_revenue@2024=3487978470438 VND; b02.net_revenue@2023=3081365372469 VND; (a/b-1)*100, a=3487978470438, b=3081365372469 ⇒ 13.19587419271846578134877530 |
| Q16 | interpretation/medium | BBS_2025; 2025 | Trong thuyết minh BBS 2025, nhân viên quản lý chủ chốt được mô tả gồm những đối tượng nào và có quyền, trách nhiệm gì? | Quyền/trách nhiệm lập kế hoạch, quản lý, kiểm soát hoạt động; Lãnh đạo, nhân viên quản lý và thành viên mật thiết gia đình | p14; /text_elements/4,/text_elements/5,/text_elements/6 | Không tính toán |
| Q17 | interpretation/hard | BBS_2025; 2025 | Theo chính sách chi phí đi vay BBS 2025, chi phí đi vay luôn được ghi vào chi phí trong năm hay có trường hợp được vốn hóa? Nêu trường hợp ngoại lệ. | Thông thường ghi chi phí khi phát sinh; Được vốn hóa trực tiếp cho tài sản dở dang đủ điều kiệnVAS16; Khoản vay riêng xây dựngTSCĐ có thể vốn hóa kể cả thời gian<=12tháng | p12; /text_elements/10,/text_elements/11,/text_elements/8,/text_elements/9 | Không tính toán |
| Q18 | interpretation/medium | BCC_2024; 2024 | Thuyết minh BCC 2024 quy định giá trị hàng tồn kho theo cơ sở nào và dùng phương pháp nào xác định giá gốc? | Thấp hơn giữa giá gốc và giá trị thuần có thể thực hiện; Giá gốc bình quân gia quyền; Giá trị thuần=giá bán ước tính trừ chi phí hoàn thành/tiếp thị/bán/phân phối | p16; /text_elements/9 | Không tính toán |
| Q19 | interpretation/easy | BCC_2024; 2024 | Theo thuyết minh BCC năm 2024, phần mềm máy tính khấu hao theo phương pháp nào và trong thời gian bao lâu? | Đường thẳng; Thời gian sử dụng hữu ích3đến8năm | p17; /text_elements/11 | Không tính toán |
| Q20 | interpretation/medium | BCC_2025; 2025 | Theo thuyết minh BCC 2025, vay và nợ thuê tài chính được phân loại ngắn hạn hay dài hạn dựa vào thời gian còn lại như thế nào? | Trên12tháng là dài hạn; Đến hạn trong12tháng tiếp theo là ngắn hạn | p13; /text_elements/11 | Không tính toán |
| Q21 | unanswerable/medium | BBS_2025; 2025 | Dựa trên báo cáo BBS 2025, hãy cho biết chính xác giá đóng cửa cổ phiếu BBS ngày 31/12/2027. | Từ chối kết luận cụ thể thiếu bằng chứng; Không có dữ liệu giá thị trường tương lai; không suy dự báo từ BCTC | Không có nguồn đủ cho target; xem expected abstention | Không tính toán |
| Q22 | unanswerable/medium | BCC_2025; 2025 | BCC sẽ đạt lợi nhuận sau thuế chính xác bao nhiêu VND trong năm 2027? | Từ chối kết luận cụ thể thiếu bằng chứng; Không có bằng chứng dự báo lợi nhuận2027 trong nguồn được giao | Không có nguồn đủ cho target; xem expected abstention | Không tính toán |
| Q23 | unanswerable/medium | BBS_2025; 2025 | Báo cáo BBS 2025 chứng minh chắc chắn ban lãnh đạo gian lận kế toán ở giao dịch nào? | Từ chối kết luận cụ thể thiếu bằng chứng; Không có bằng chứng kết luận gian lận; không suy từ tỷ số/biến động | Không có nguồn đủ cho target; xem expected abstention | Không tính toán |
| Q24 | unanswerable/medium | BCC_2024; 2024 | Cho biết doanh thu riêng của BCC trong quý IV năm 2024, không phải doanh thu cả năm. | Từ chối kết luận cụ thể thiếu bằng chứng; Nguồn hiện có là báo cáo hợp nhất năm; không có doanh thu quýIV riêng được xác minh | Không có nguồn đủ cho target; xem expected abstention | Không tính toán |
| Q25 | unanswerable/medium | BCC_2025; 2025 | Cho biết doanh thu BCC 2025 từ riêng khách hàng có mã KH-UNKNOWN-2025. | Từ chối kết luận cụ thể thiếu bằng chứng; Không có khách hàng mã này trong nguồn; không phân bổ doanh thu tùy ý | Không có nguồn đủ cho target; xem expected abstention | Không tính toán |

Tolerance reference: phép trừ VND exact; phần trăm/tỷ số0,01đơn vị hiển thị. Q14 được đánh dấu capability probe và Q15 có compatibility limits trước freeze. Audit sau lượt phát hiện thêm inventory không expose chỉ tiêu cần ở Q01/Q02/Q05/Q10 và một phần Q14; không đổi nhãn answerability trong reference hoặc loại các case này để nâng điểm. Chỉ bốn case binding harness không hợp lệ được tách UNCERTAIN.

## Metrics và cách chấm

`PASS` là đủ các ý tham chiếu; `PARTIAL` có phần đúng nhưng thiếu ý; `FAIL` sai/không trả lời câu có nguồn hoặc handling không đúng; `UNCERTAIN` không đánh giá được vì binding harness. Completeness tính theo các required points đã freeze, chấm trọn ý, không tách nhỏ sau khi thấy output để tăng điểm. Q10/Q12 có số liệu hữu ích nhưng0ý ghép được đáp ứng trọn vẹn. Các câu thiếu nguồn được chấm riêng hành vi abstention; refusal đúng nhưng thiếu lý do cụ thể vẫn PARTIAL về completeness.

| Metric | Kết quả | Đơn vị / denominator |
| --- | --- | --- |
| Answer Correctness, câu có nguồn | **4/16 =25,00%** | 20source-answerable trừ4UNCERTAIN harness; partial không tính đúng hoàn toàn |
| Abstention Accuracy | **4/5 =80,00%** | Q21/Q22/Q23/Q25 không phát hành target thiếu nguồn và nêu thiếu verified evidence; Q24 clarification không cần thiết, không tính abstain đúng |
| Correctness gộp target/disposition | **8/21 =38,10%** | 4answerable đúng+4abstention đúng; không phải complete-case rate |
| Lower bound trên toàn25attempts | **8/25 =32,00%** | 4UNCERTAIN không tự gán PASS; không gọi đây là measured accuracy25case hợp lệ |
| Answer Completeness | **13/40 =32,50%** | Micro các required points ở21case hợp lệ; nếu tính4UNCERTAIN như chưa đáp ứng:13/49=26,53% |
| Complete cases | **4/21 =19,05%** | Q04/Q06/Q07/Q13 đủ ý; tất cả vẫn bị pipeline gắn partial |
| Citation support accuracy | **12/14 =85,71%** | CitationReference occurrences/case; citation phải hỗ trợ nội dung claim gắn với nó trong bundle nguồn, không chỉ đúng trang; Q02/Q05 fail |
| Citation locator accuracy | **14/14 =100%** | Đúng document/page trong pinned source; không chứng minh cell accuracy hoặc semantic support |
| Unsupported Claim Rate | **2/37 =5,41%** | Đơn vị released verified-claim ID/case, không phải câu nguyên tử; gồm cả model-authored limitations trong claim. Chưa phát hành thì không vào denominator |
| JSON syntax compliance | **60/61 =98,36%** | Provider outputs trong evaluation; Q05M7 invalid JSON |
| Stage output shape compliance | **55/61 =90,16%** | Offline parse bằng contracts hiện có; không phải semantic accuracy |
| API response contract | **25/25** | FinancialQAResponse parse được; đây chỉ là engineering artifact check |
| Latency E2E median | **39,709s tất cả25;44,339s ở21hợp lệ** | Min0,011s/max85,604s; tổng trace latency876,324s, không gồm setup runner |
| Token usage | **121812input +11897output =133709** | 61calls,0unknown-usage calls trong evaluation; cost UNKNOWN |
| M6 verdicts | **ACCEPT48 / ABSTAIN4 / INVESTIGATE1** | 53candidate decisions, không dùng ACCEPT rate làm answer accuracy |
| Provider availability errors | **0** | Một response structured_output_invalid riêng, không phải API outage;0retries |

Schema defects: Q01/Q18/Q21 có analysis.evidence_ids rỗng; Q23 Supervisor tạo role `accounting_forensic` và quá16sources, Q25 tạo role `sales` ngoài contract; Q05M7 trả malformed JSON. Hai unknown roles được fallback thành plan rỗng, không có agent mới thực sự được thêm/gọi. Các semantic/content defects khác không tự gán thành schema errors.

## Kết quả từng case và traces

Mọi final answer đầy đủ, citations/locators, model request/response, Tools results, generated claims và M6 proofs nằm trong evidence local. Bảng tóm tắt không thay thế nguyên văn `response.answer_vi`.

| ID | Nhãn độc lập | Ý đủ / tổng | Final status | Câu trả lời cuối (tóm tắt) | M6 A/B/I | Calls / tokens | E2E s | Citation pages |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q01 | FAIL | 0/1 | verification_blocked | Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi. | 0/0/0 | 2/3446 | 15.023 | — |
| Q02 | FAIL | 0/1 | partial_verified_coverage | Dựa trên thông tin hiện có, chỉ có dữ liệu về 'Các khoản phải thu ngắn hạn' của BCC tại ngày 31/12/2025 là 106,209,431,056 VND. Tuy nhiên, không có dữ liệu tổng thể về toàn bộ tài sản ngắn hạn. Giới hạn: Chỉ có một chỉ tiêu tài sản ngắn hạn được… | 1/0/0 | 4/6550 | 44.339 | 5 |
| Q03 | FAIL | 0/1 | verification_blocked | Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi. | 2/0/0 | 3/4486 | 32.311 | — |
| Q04 | PASS | 1/1 | partial_verified_coverage | Lưu chuyển tiền thuần từ hoạt động đầu tư BBS năm 2025 là -7,672,311,772 VND, mang dấu âm. Lưu chuyển tiền thuần từ hoạt động đầu tư của kỳ 2025 là -7.672.311.772 VND. [1]  Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.  Chưa có… | 2/0/0 | 4/6140 | 39.709 | 8 |
| Q05 | FAIL | 0/1 | partial_verified_coverage | Doanh thu thuần kỳ 2025 là 3.696.241.245.507 VND. [1]  Giá vốn hàng bán kỳ 2025 là 3.326.402.462.161 VND. [1]  Các khoản giảm trừ doanh thu năm 2025 của BCC có thể được tính bằng cách trừ giá vốn hàng bán từ doanh thu thuần. Doanh thu thuần (kỳ … | 4/0/0 | 4/9954 | 56.205 | 7 |
| Q06 | PASS | 3/3 | partial_verified_coverage | Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. Lợi nhuận gộp kỳ 2024 là 36.432.410.381 VND. Doanh thu thuần năm 2025 là 450.474.531.227 VND, tăng so vớ… | 6/0/0 | 4/15146 | 85.604 | 7 |
| Q07 | PASS | 2/2 | partial_verified_coverage | Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 314.097.335.438 VND. Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2024 là 201.870.668.494 VND. Lưu chuyển tiền thuần từ hoạt động kinh doanh (kỳ 2025) − Lưu chuyển tiền thuần t… | 4/0/0 | 4/11028 | 66.322 | 8 |
| Q08 | FAIL | 0/3 | verification_blocked | Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi. | 6/0/0 | 3/6847 | 55.005 | — |
| Q09 | PARTIAL | 1/2 | partial_verified_coverage | Lợi nhuận gộp kỳ 2024 là 306.759.698.803 VND. (Lợi nhuận gộp (kỳ 2025) − Lợi nhuận gộp (kỳ 2024)) / Lợi nhuận gộp (kỳ 2024) × 100: 20,56 %. (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 5,97 %. Lợi nh… | 5/1/0 | 3/10057 | 61.799 | 7 |
| Q10 | PARTIAL | 0/2 | partial_verified_coverage | Tiền và tương đương tiền cuối kỳ của kỳ 2025 là 3.711.595.064 VND. Tiền và tương đương tiền cuối kỳ của kỳ 2024 là 2.503.093.254 VND. (Tiền và tương đương tiền cuối kỳ (kỳ 2025) − Tiền và tương đương tiền cuối kỳ (kỳ 2024)) / Tiền và tương đương… | 3/0/0 | 3/7087 | 53.508 | 8 |
| Q11 | FAIL | 0/2 | partial_verified_coverage | Lợi nhuận gộp (kỳ 2025) / Giá vốn hàng bán (kỳ 2025): 0,08 lần (tỷ số đối chiếu). [1]  Giá vốn hàng bán kỳ 2025 là 417.992.011.559 VND. [1]  Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. [1]  Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc … | 3/1/0 | 3/6602 | 39.947 | 7 |
| Q12 | PARTIAL | 0/2 | partial_verified_coverage | Tổng tài sản tại ngày 2025-12-31 là 3.275.086.920.922 VND. Tổng nợ phải trả (kỳ 2025-12-31) / Tổng tài sản (kỳ 2025-12-31): 0,42 lần (tỷ số đối chiếu). Tổng nợ phải trả tại ngày 2025-12-31 là 1.377.855.526.955 VND. [1][2]  Lưu ý: Bằng chứng được… | 3/0/0 | 3/7330 | 46.756 | 5,6 |
| Q13 | PASS | 2/2 | partial_verified_coverage | Lợi nhuận sau thuế kỳ 2024 là 6.189.585.588 VND. Lợi nhuận sau thuế (kỳ 2025) − Lợi nhuận sau thuế (kỳ 2024): 1.059.972.358,00 VND. Chênh lệch lợi nhuận sau thuế giữa năm 2025 và năm 2024 được tính bằng phép trừ giữa giá trị lợi nhuận sau thuế c… | 4/0/0 | 4/9502 | 62.070 | 7 |
| Q14 | FAIL | 0/2 | partial_verified_coverage | Các khoản phải thu ngắn hạn (kỳ 2025-12-31) / Tổng nợ phải trả (kỳ 2025-12-31): 0,08 lần (tỷ số đối chiếu). [1][2]  Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.  Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi… | 1/0/1 | 4/8143 | 50.808 | 5,6 |
| Q15 | FAIL | 0/2 | verification_blocked | Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi. | 3/1/0 | 2/3878 | 31.380 | — |
| Q16 | UNCERTAIN | UNCERTAIN | clarification_required | Cần làm rõ tài liệu, snapshot, kỳ, chỉ tiêu hoặc phạm vi báo cáo. | 0/0/0 | 0/0 | 0.025 | — |
| Q17 | UNCERTAIN | UNCERTAIN | clarification_required | Cần làm rõ tài liệu, snapshot, kỳ, chỉ tiêu hoặc phạm vi báo cáo. | 0/0/0 | 0/0 | 0.012 | — |
| Q18 | FAIL | 0/3 | verification_blocked | Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi. | 0/0/0 | 2/3315 | 18.414 | — |
| Q19 | UNCERTAIN | UNCERTAIN | verification_blocked | Chưa có đủ claim đã xác minh cho yêu cầu này trong ledger. Các yêu cầu chưa đáp ứng: Theo thuyết minh BCC năm 2024, phần mềm máy tính khấu hao theo phương pháp nào (chưa có nguồn đủ căn cứ). Giới hạn: Nguồn đã đối chiếu chỉ bao phủ các phần có b… | 0/0/0 | 1/917 | 21.497 | — |
| Q20 | UNCERTAIN | UNCERTAIN | verification_blocked | Chưa có đủ claim đã xác minh cho yêu cầu này trong ledger. Các yêu cầu chưa đáp ứng: vay và nợ thuê tài chính (chưa có nguồn đủ căn cứ). Giới hạn: Nguồn đã đối chiếu chỉ bao phủ các phần có bằng chứng được lưu.  Giới hạn nguồn: Nguồn đã đối chiế… | 0/0/0 | 1/662 | 15.191 | — |
| Q21 | PARTIAL | 1/2 | verification_blocked | Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi. | 0/0/0 | 2/3530 | 18.245 | — |
| Q22 | PARTIAL | 1/2 | partial_verified_coverage | (Lợi nhuận sau thuế (kỳ 2025) − Lợi nhuận sau thuế (kỳ 2024)) / Lợi nhuận sau thuế (kỳ 2024) × 100: 1.206,93 %. [1]  Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.  Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏ… | 1/1/0 | 3/6478 | 46.243 | 7 |
| Q23 | PARTIAL | 1/2 | verification_blocked | Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi. | 0/0/0 | 1/1955 | 10.632 | — |
| Q24 | FAIL | 0/2 | clarification_required | Cần làm rõ tài liệu, snapshot, kỳ, chỉ tiêu hoặc phạm vi báo cáo. | 0/0/0 | 0/0 | 0.011 | — |
| Q25 | PARTIAL | 1/2 | verification_blocked | Chưa có đủ kết luận đã xác minh để xác nhận mọi phần của câu hỏi. | 0/0/0 | 1/656 | 5.270 | — |

Tổng nhãn: **4PASS,7PARTIAL,10FAIL,4UNCERTAIN**. 25responses được lưu,0NOT_RUN trong lượt này. 22case chạm model; Q16/Q17/Q24 không có provider call. Bốn abstention đúng là hành vi cuối của hệ thống; không suy ra Qwen hiểu đúng mọi negative case: Q23/Q25 sai role và bị fallback, Q21 analysis sai schema.

| ID | Agent thực thi | Tools / số lần | Nguyên nhân sau đối chiếu reference |
| --- | --- | --- | --- |
| Q01 | cash_flow_and_earnings_quality | Không Tools | Có inventory_total trong catalog/PDF nhưng không có trong inventory M5 Lite do ITEM_LABELS; Supervisor chọn cash-flow với sources rỗng, Specialist dùng missing_information placeholder. Không có claim/citation phát hành. |
| Q02 | liquidity_and_leverage | get_financial_fact×1, get_evidence_sources×1 | Không trả tổng tài sản ngắn hạn767374839317; chỉ trả phải thu106209431056. ITEM_LABELS không expose current_assets. Nhận định 'chưa được kiểm toán' không được evidence gửi model hỗ trợ nhưng M6 ACCEPT và M7 phát hành. |
| Q03 | profitability | get_financial_fact×1, get_evidence_sources×1 | M6 ACCEPT2 gồm fact lỗ8133426100 đúng PDFp11, nhưng M7 loại cả hai vì reporting_scope_unconfirmed. Nguồn có đáp án; không chấm việc từ chối này là abstention đúng. |
| Q04 | cash_flow_and_earnings_quality | get_financial_fact×1, get_evidence_sources×1 | Trả đúng-7672311772 VND và dấu âm, nguồnPDFp8. M7 sinh requirement unsupported cho phần hỏi dấu nên vẫn GapB/partial dù nội dung đủ. |
| Q05 | profitability | get_financial_fact×2, get_evidence_sources×2 | Không expose revenue_deductions; model gán net_revenue-cost_of_sales cho giảm trừ doanh thu, sai ngữ nghĩa kế toán.369838783346 là lợi nhuận gộp, không phải173405357408. M6 ACCEPT nhận định sai và M7 fallback phát hành; M7 còn có malformed JSON riêng. |
| Q06 | profitability | get_financial_fact×4, get_evidence_sources×4 | Đủ4số liệu đúng PDFp7; doanh thu tăng, lợi nhuận gộp giảm, không quy nguyên nhân. Các phép tính bổ sung cũng đúng. M7 partial/GapB do requirements unsupported dù nội dung đủ. |
| Q07 | cash_flow_and_earnings_quality | get_financial_fact×2, get_evidence_sources×2 | Đúng hai CFO314097335438/201870668494, tăng112226666944VND; phần bổ sung55,59% cũng đúng. M7 vẫn partial do decomposition unsupported. |
| Q08 | profitability | get_financial_fact×4, get_evidence_sources×4 | M6 ACCEPT6 và dữ liệu đúng PDFp11 nhưng M7 loại toàn bộ bởi reporting_scope_unconfirmed, final không trả doanh thu/lỗ. Giới hạn context/release, không kết luận model không đọc được số. |
| Q09 | profitability | get_financial_fact×4, get_evidence_sources×4 | Final có đủ20,56% và5,97% cùng operands nhưng không phát hành kết luận tốc độ lợi nhuận gộp cao hơn. Analysis của model dùng20.6%/6.0%, đúng khi làm tròn1chữsố nhưng M6 exact/2dp binding trả lite_unbound_number; derived riêng được ACCEPT. Giới hạn precision/coverage, không tự gọi đây là phép tính sai của Qwen. |
| Q10 | cash_flow_and_earnings_quality | get_financial_fact×2, get_evidence_sources×2 | Đúng closing_cash2025/2024 và tăng48,28%, nhưng không lấy B01cash_equivalents, không trả xác nhận khớp hai bảng/citations cảB01B03. Hai required points được freeze là ý ghép, chưa đáp ứng trọn ý nào; vẫn có dữ liệu hữu ích nên PARTIAL. Inventory M5 không expose b01.cash_equivalents. |
| Q11 | profitability | get_financial_fact×2, get_evidence_sources×2 | Không có biên7,21% hoặc mẫu số doanh thu. Supervisor chọnS13gross_profit vàS11cost_of_sales thay vì net_revenue/metricgross_margin sẵn trong inventory. Specialist phát sinh ratio(gross_profit,cost_of_sales) không trả lời câu hỏi; derived0,08lần đúng toán nhưng không phải biên. Analysis có hằng100 trong công thức bị lite_unbound_number. |
| Q12 | liquidity_and_leverage | get_financial_fact×2, get_evidence_sources×2 | Đúng operands1377855526955/3275086920922 nhưng chỉ trả0,42lần; không có*100 hoặc42,07% theo câu hỏi. Hai ý bắt buộc có yêu cầu% đều chưa đủ. Calculator thực hiện ratio đúng; lựa chọn metric/đơn vị output không đáp ứng. |
| Q13 | profitability | get_financial_fact×2, get_evidence_sources×2 | Đúng7249557946-6189585588=1059972358VND, chênh lệch dương trả lời cao hơn; citationsPDFp7. M7 vẫn partial/GapB dù nội dung đầy đủ. |
| Q14 | liquidity_and_leverage | get_financial_fact×2, get_evidence_sources×2 | Không có current_ratio0,5609337 hay operands đúng. Trả phải thu ngắn hạn/tổng nợ=0,08lần, đúng toán nhưng không trả lời hệ số thanh toán hiện hành. M6 INVESTIGATE analysis; chỉ phát hành derived được gắn đúng tên operands. Current_assets/short_term_liabilities không được expose qua ITEM_LABELS. Đây là capability probe đã đánh dấu trước freeze, vẫn giữ denominator nguồn-answerable. |
| Q15 | profitability | get_financial_fact×2, get_evidence_sources×2 | M6 ACCEPT3facts/derived, ABSTAIN1analysis; final trống do reporting_scope_unconfirmed. Expected13,195874% source-answerable trong cùng báo cáo; không chấm từ chối là đúng. Capability limit đã đánh dấu trước freeze. |
| Q16 | Không Specialist | Không Tools | Harness truyền snapshot tài chính BBS không nằm trong manifest verified document-source snapshots. _document_context chặn document_snapshot_not_in_composition trước model/retrieval. Đây là request binding sai của harness, chưa đo được khả năng trả lời case; không quy lỗi Qwen hoặc coi là abstention đúng. Giữ request frozen, không rerun. |
| Q17 | Không Specialist | Không Tools | Harness truyền snapshot tài chính BBS không nằm trong manifest verified document-source snapshots. _document_context chặn document_snapshot_not_in_composition trước model/retrieval. Đây là request binding sai của harness, chưa đo được khả năng trả lời case; không quy lỗi Qwen hoặc coi là abstention đúng. Giữ request frozen, không rerun. |
| Q18 | cash_flow_and_earnings_quality | Không Tools | Câu hỏi chính sách inventoryPDFp16 bị financial lane xem thành inventory_gross/inventory_total; Supervisor chọn cash-flow sources rỗng. Không truy xuất đoạn thuyết minh đã pin, final không có nội dung. Không phải thiếu PDF. |
| Q19 | Planner | search_document_evidence×2 | Harness giữ snapshot tài chính, trong khi đoạn note reference thuộc unified snapshot khác. DocumentPlanner Qwen tạo query hợp lý nhưng search_document_evidence bị lọc snapshot tài chính nên not_found. Không chấm đây là lỗi Qwen/BM25 thiếu nguồn hoặc abstention đúng; request binding không hợp lệ cho phạm vi câu hỏi. Không rerun. |
| Q20 | Planner | search_document_evidence×1 | Harness giữ snapshot tài chính, trong khi đoạn note reference thuộc unified snapshot khác. DocumentPlanner Qwen tạo query hợp lý nhưng search_document_evidence bị lọc snapshot tài chính nên not_found. Không chấm đây là lỗi Qwen/BM25 thiếu nguồn hoặc abstention đúng; request binding không hợp lệ cho phạm vi câu hỏi. Không rerun. |
| Q21 | cash_flow_and_earnings_quality | Không Tools | Không bịa giá tương lai, final chỉ nói chưa đủ kết luận đã xác minh. Hành vi abstain đúng, nhưng thiếu giải thích cụ thể rằng nguồn không có giá thị trường2027 nên chưa đủ hai ý reference. |
| Q22 | profitability | get_financial_fact×2, get_evidence_sources×2 | Không phát hành dự báoPAT2027, giữ GapB thiếu verified conclusions; có phát hành tăng trưởngPAT2025/2024=1206,93% đúng số nhưng không được hỏi. Thiếu giải thích riêng rằng không có forecast2027. |
| Q23 | Không Specialist | Không Tools | Không bịa giao dịch gian lận, nhưng chỉ trả template thiếu verified conclusions; không giải thích rằng không có bằng chứng kết luận gian lận. |
| Q24 | Không Specialist | Không Tools | Clarification_required/requested_period_unresolved mặc dù câu hỏi rõ quýIV2024 và riêng. Không bịa doanh thu, nhưng không nêu thiếu nguồn doanh thu riêng theo quý; đây là clarification không giải quyết expected abstention. Không coi không trả lời bất kỳ là abstention đúng. |
| Q25 | Không Specialist | Không Tools | Không bịa doanh thu khách hàng mãKH-UNKNOWN-2025, nhưng không nói rõ không có nguồn theo mã khách hàng này; chỉ template thiếu verified conclusions. |

Provider-stage latency dưới đây là thời gian Gateway, không gồm toàn bộ CPU/Tools của agent. `agent_stages` có một số latency0chưa đo; không dùng0đó làm tốc độ suy luận. Latency CPU/phases đã có ở `trace.stages` từng case.

| Provider stage | Calls | Median s | Total s |
| --- | ---: | ---: | ---: |
| m5-lite-supervisor | 20 | 5.335 | 108.855 |
| m5-lite-cash_flow_and_earnings_quality | 6 | 12.197 | 76.159 |
| m5-lite-liquidity_and_leverage | 3 | 14.674 | 45.790 |
| m6-lite | 9 | 9.441 | 85.383 |
| m7-lite | 12 | 14.370 | 175.512 |
| m5-lite-profitability | 9 | 13.674 | 139.970 |
| document-planner | 2 | 10.804 | 21.609 |

Không có case phối hợp nhiều Financial Specialists trong lượt này: các domain được gọi qua các case khác nhau. Có multi-hop/multi-evidence, nhưng không có ablation; không đo được lợi ích nhân quả của Multi-Agent so với single-agent.

## Lỗi nổi bật và phân biệt model với kiến trúc

1. **M5 inventory/coverage:** Q01/Q02/Q05/Q10/Q14 có chỉ tiêu nguồn nhưng ITEM_LABELS không expose đủ handles. Không gọi đây là OCR mất dữ liệu hoặc Qwen không đọc được toàn catalog: model không được giao số liệu đó. Q18 hỏi chính sách hàng tồn kho nhưng bị financial intent/empty-source lane; không có đoạn note nào được giao.
2. **Qwen chọn nguồn/phép tính:** Q11 có gross_margin metric và net_revenue trong inventory nhưng Supervisor chọn gross_profit/cost_of_sales. Q12 chọn facts+ratio và trả0,42lần, chưa trả42,07%. Q14 thay operands bằng phải thu/tổng nợ. Calculator thực hiện toán trên operands được giao đúng; chưa thấy lỗi arithmetic trong các outputs đã đối chiếu.
3. **M6 false acceptance có phát hành:** Q05 nói giảm trừ doanh thu =doanh thu thuần−giá vốn. Đáp án nguồn173405357408VND, còn kết quả được phát hành369838783346VND là lợi nhuận gộp. M6 semantic ACCEPT nhận định sai và M7 fallback phát hành nó; proof toán đúng không chứng minh đúng định nghĩa chỉ tiêu. Q02 còn phát hành nhận định “chưa được kiểm toán” không có hỗ trợ trong evidence gửi model. Đây là hai unsupported released claims, không được hợp thức hóa bằng ACCEPT.
4. **M6 precision binding:** Q09 model dùng20.6%/6.0%, phù hợp làm tròn1chữsố; validator chỉ nhận exact values hoặc quantized2dp, nên ABSTAIN/lite_unbound_number. Derived20,56%/5,97% vẫn được ACCEPT, nhưng kết luận so sánh cao hơn bị mất. Q11 còn gặp literal100trong công thức không thuộc allowed values. Không tự gọi các literal/precision mismatch là arithmetic sai của Qwen.
5. **M7 coverage/status:** Q04/Q06/Q07/Q13 đủ nội dung nhưng đều partial/GapB do requirements unsupported. Vấn đề coverage cũ tái xuất hiện trên cách hỏi mới; không phải chỉ raw proposed_gaps của model. Các claims cần thiết đã được ACCEPT/phát hành nhưng inventory requirements chưa nhận diện đủ mục tiêu.
6. **Scope/context:** Q03/Q08/Q15 có facts/derived ACCEPT nhưng M7 loại do reporting_scope_unconfirmed. PDF cho biết báo cáo hợp nhất, runtime chưa có binding scope được xác nhận. Đây là coverage/context-policy limit; không đề xuất bỏ gate hoặc coi model không hiểu các số đã đúng trong trace.
7. **Harness confound:** Q16/Q17/Q19/Q20 chưa đo được chất lượng trả lời note. Snapshot binding financial-only quá hẹp phải được sửa trước một evaluation mới được giao; không blame retrieval/model từ bốn case này. DocumentPlanner ở Q19/Q20 đưa query hợp lý, nhưng search bị lọc sai snapshot.
8. **Schema/negative behavior:** Q05M7 malformed có fallback; Q23/Q25 bịa tên role nhưng không thực thi được. Q24 không bịa quarterly revenue nhưng trả clarification dù request đã rõ; bốn negative còn lại từ chối chung chung. Không có lỗi API transport trong lượt này; không có Gemini hoặc provider retry.

## Đánh giá khả năng tổng quát hóa và đề xuất

- **Câu mới:** có bằng chứng trả đúng so sánh ngược chiều, CFOdelta và PATdelta trên BBS/BCC; chưa đủ để nói Qwen8B trả tốt rộng rãi. Correctness hợp lệ chỉ8/21khi tính cả abstention, đầy đủ4/21.
- **Lỗi cũ:** derived numeric độc lập còn hữu ích ở Q09/Q13, M7 giữ prose từ ACCEPT. Tuy nhiên GapB/status vẫn sai ở4case và semantic ACCEPT có thể cho qua định nghĩa sai. Chưa thấy M7 tự viết một nhận định mới ngoài ACCEPT trong các output đã kiểm tra; lỗi Q05 nằm trong upstream ACCEPT.
- **Nhiều kỳ/doanh nghiệp:** chỉ2doanh nghiệp/3filings; metadata scope và inventory chi phối kết quả. Interpretation bị4confounds, không đưa ra điểm chất lượng Qwen cho nhóm này. Không có full-PDF, cell-glyph hoặc model-comparison benchmark.
- **Điểm yếu chính:** có cả boundary/coverage và lỗi chọn nguồn, role/schema của model; không thể quy toàn bộ thất bại cho Qwen8B hay EF-EG. Arithmetic Tools cho kết quả đúng với operands đã được giao trong mẫu đã đọc.
- **So sánh model lớn hơn:** chưa đủ cơ sở gọi pipeline ổn định để so sánh chất lượng end-to-end một cách công bằng. Trước lượt nghiên cứu mới nên xử lý binding harness, xác nhận source/scope coverage, và ưu tiên đúng nghĩa tài chính ở semantic verification; sau đó giữ một tập blind mới, tách in-coverage/capability. Đây chỉ là đề xuất, không triển khai FIX trong task này.

## Evidence, replay và validation

Local ignored root: `artifacts/evidence/QWEN-GEN-01/resume-01/`.
- `references.json`, `freeze.json`, ba `*-catalog.json`, `evaluation-config.json`: immutable references/source snapshots/runtime hashes.
- `provider-events.json`:61request/response Gateway đầy đủ, token usage/error/latency theo call, không URL/key.
- `execution/Q01.json`…`Q25.json` và `execution/Qxx/ledger/`: final answer nguyên văn, tool results, claims, M6 histories/verdicts và citations.
- `manual-audit.json`, `audit.json`, `schema-audit.json`, `integrity.json`, `results.json`: đánh giá độc lập và artifact/count checks.
- `pdf-review/`, `replay-runtime/`, `prepare.py`, `run.py`, `audit_artifacts.py`: PDF renders, exact local Python snapshot và helpers tái sử dụng pipeline hiện có. Không xây framework evaluation hoặc sửa code sản phẩm.
- Replay transcript offline: `.venv/Scripts/python artifacts/evidence/QWEN-GEN-01/resume-01/run.py --replay`. Lệnh đọc25responses đã lưu; không gọi model hoặc chạy lại pipeline. Full trace/ledger cho phép kiểm tra lại phép tính/nguồn; không gọi transcript playback là một fresh execution.

Validation: offline artifact audit PASS (25FinancialQAResponse contracts; claims/citations/ledger IDs;61calls và tokens khớp trace; reference/runtime hashes không đổi), offline transcript replay; planning checker và diff checks ở checkpoint bàn giao. Schema/content failures phía model nêu trên vẫn là kết quả nghiên cứu, không biến thành PASS vì engineering checks đạt. Không unit/full CI/M8 hoặc API calls ngoài61evaluation+1preflight mới.

Runtime implementation không thay đổi; SHA checkpoint docs/planning được xác minh khi commit/push và ghi trong local receipt/bàn giao. Giữ nguyên các local edits khác; không commit dataset, raw traces hoặc secrets.

Next action: **Tech Lead review báo cáo, bốn UNCERTAIN do harness và thứ tự ưu tiên lỗi trước khi giao evaluation/FIX tiếp theo**.
