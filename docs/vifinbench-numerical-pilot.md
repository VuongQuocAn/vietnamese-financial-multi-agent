# ViFinBench-NR-PILOT-Refine — Cải thiện 15 Numerical Reasoning QA

Ngày **15/11/2026** (Asia/Bangkok). Trạng thái **REVIEW**, chờ Tech Lead nghiệm thu. Baseline được review: `344776c9cbca9459cbf0496b1583989e8c6323ec` ([Pilot cũ](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/blob/344776c9cbca9459cbf0496b1583989e8c6323ec/ViFinBench/benchmark/numerical/pilot.jsonl)). Dataset sau Refine: [pilot.jsonl](../ViFinBench/benchmark/numerical/pilot.jsonl).

**7 KEEP / 6 REWRITE / 2 REPLACE; 5 Easy / 7 Medium / 3 Hard; 4 Explicit / 7 Implicit / 4 Advanced.** Giữ 15 ID, 15 doanh nghiệp/15 tài liệu. Hai bài thay thế là ROA trên tài sản bình quân (0011) và chu kỳ chuyển đổi tiền mặt CCC (0014); loại bỏ DuPont dài nhưng rút gọn đơn giản. Không triển khai Numerical Full hoặc sửa subset khác.

Chỉ cập nhật hai deliverables, giữ các local edits ngoài task, neutral, metadata, Schema v1, planning và pipeline. Implementation là commit chứa hai file này, lấy SHA bằng `git log -1 --format=%H -- ViFinBench/benchmark/numerical/pilot.jsonl`; SHA cụ thể và xác minh remote ghi trong bàn giao. Không lấy SHA baseline làm SHA Refine.

## Review từng QA

KEEP giữ toàn bộ item, không chỉ ý tưởng. REWRITE giữ bài toán nhưng cải thiện câu hỏi/Gold; REPLACE đổi bài toán. Không thêm trường review hay nhãn suy luận vào JSONL; bảng này là nguồn phân loại.

| ID cuối | Quyết định | Độ khó | Kiểu yêu cầu | Đáp án sau Refine | Lý do |
| --- | --- | --- | --- | --- | --- |
| 0001 | KEEP | Easy | Implicit | 10,56 % | Tăng trưởng từ hai giá trị, không cho sẵn phép chia; phù hợp Easy. |
| 0002 | KEEP | Easy | Explicit | -249.512.955 VND | Phép trừ LNST có hướng và dấu rõ, giữ làm mẫu thực thi Explicit. |
| 0003 | KEEP | Easy | Explicit | -379.046.514 VND | Phân biệt số dư đầu/cuối năm; phép trừ tiền rõ và chưa có đáp án ghi sẵn. |
| 0004 | KEEP | Easy | Implicit | -4,01 % | Tự xác định mẫu số đầu năm cho tỷ lệ biến động; số học vẫn ở mức Easy. |
| 0005 | KEEP | Easy | Explicit | -5.602.449.814 VND | Phép trừ CFO hai kỳ có dấu, là mẫu Explicit cơ bản. |
| 0006 | REWRITE | Medium | Implicit | 11,99 % | Bỏ gợi ý mẫu số doanh thu; yêu cầu nhớ định nghĩa biên gộp. |
| 0007 | REWRITE | Medium | Advanced | 0,815 % | Bỏ công thức/mã 60 khỏi câu hỏi; chọn LNST toàn tập đoàn giữa các chỉ tiêu gần giống. Dùng 3 chữ số để không chấp nhận nhầm phần thuộc công ty mẹ. |
| 0008 | KEEP | Medium | Implicit | 59,06 % | Thuật ngữ và tỷ trọng tài chính tự nhiên, chưa nêu chuỗi thao tác; phù hợp Implicit. |
| 0009 | REWRITE | Medium | Implicit | 0,42 lần | Bỏ công thức chia cho sẵn; mô hình phải biết hệ số thanh toán hiện hành. |
| 0010 | REWRITE | Medium | Implicit | 0,78 lần | Giữ quy ước cần thiết cho chỉ số có nhiều định nghĩa; bỏ công thức đầy đủ. |
| 0011 | REPLACE | Medium | Implicit | 0,83 % | Đổi CFO/LNST trùng dạng 0015 thành ROA dùng tài sản bình quân, tăng đa dạng chỉ số. |
| 0012 | KEEP | Medium | Explicit | 128,72 % | Tỷ lệ trang trải đầu tư với dấu âm là một mẫu Explicit hữu ích. |
| 0013 | REWRITE | Hard | Advanced | 157.588.095.957 VND | Giữ FCF hai kỳ nhưng dùng tình huống tự tài trợ đầu tư; mô hình tự tổ chức các phép tính và xử lý âm. |
| 0014 | REPLACE | Hard | Advanced | -26,82 ngày | Bỏ DuPont rút gọn được; CCC cần 8 toán hạng, chọn công nợ thương mại, ba số dư bình quân và ba số ngày. |
| 0015 | REWRITE | Hard | Advanced | -979,33 điểm phần trăm | Bỏ chuỗi công thức cho sẵn; giữ bài toán hai kỳ, hai báo cáo, CFO đổi dấu và chênh lệch điểm phần trăm. |

## Suy luận, độ khó và nguồn

Explicit cung cấp phép tính hoặc cách xử lý trực tiếp; Implicit dùng thuật ngữ/quan hệ tài chính và để mô hình xác định công thức; Advanced yêu cầu chọn giữa các chỉ tiêu dễ nhầm hoặc tổ chức tính qua nhiều kỳ/báo cáo. Đây là kiểu yêu cầu, **không đồng nhất với độ khó**: 0007 là Advanced về chọn phạm vi lợi nhuận nhưng chỉ Medium về tính toán. Các câu cần quy ước thanh toán nhanh/CCC vẫn nêu quy ước để có Gold duy nhất.

- **Explicit 4:** 0002, 0003, 0005, 0012. **Implicit 7:** 0001, 0004, 0006, 0008, 0009, 0010, 0011. **Advanced 4:** 0007, 0013, 0014, 0015.
- **Easy 5:** số học hai giá trị, dữ kiện rõ. **Medium 7:** công thức tài chính hoặc chọn chỉ tiêu/số dư bình quân. **Hard 3:** FCF qua hai kỳ, CCC với ba giai đoạn vận hành và số dư bình quân, thay đổi CFO/LNST qua hai kỳ và hai báo cáo. Không tăng nhãn độ khó vì biểu thức dài.
- **15/15 câu khai thác báo cáo chính**; đếm QA theo nguồn toán hạng, có chồng: **B01 7 / B02 7 / B03 4 / B09 0**. Các câu ghép báo cáo: 0011 (B01+B02), 0014 (B01+B02), 0015 (B02+B03). B09 chỉ xác nhận đơn vị VND cho **3 câu** 0003/0006/0010 qua `unit_evidence`; nếu tính cả nguồn đơn vị phụ thì có 3 QA dẫn B09, không có toán hạng tài chính từ B09.
- **15 doanh nghiệp / 15 tài liệu**: ADC_2023, ARM_2023, BKC_2023; AMC_2024, ATS_2024, BED_2024, ALT_2024, BCC_2024; AME_2025, BBS_2025, BPC_2025, CAG_2025, BTS_2025, BTW_2025, C69_2025. Các cột so sánh còn cung cấp năm 2022; không ghép chéo scope tài liệu.
- Các dạng tính: tăng trưởng, chênh lệch, biên gộp/ròng, nợ trên tài sản, thanh toán hiện hành/nhanh, ROA bình quân, trang trải đầu tư, thay đổi tiền sau đầu tư, CCC và thay đổi khả năng chuyển lợi nhuận thành tiền.

## Ví dụ cải thiện đáng kể

- **0007:** trước cho sẵn mã 60 và công thức; sau hỏi biên ròng toàn tập đoàn. Gold chọn tổng LNST, không nhầm phần công ty mẹ. Với 2 chữ số, cả hai lựa chọn đều ra 0,81%; vì vậy câu mới yêu cầu **3 chữ số**: đúng **0,815%**, nhầm công ty mẹ ra **0,808%**. Evidence giữ cả tổng và hai phần phân bổ để thấy rõ lựa chọn.
- **0011:** trước tiếp tục hỏi CFO/LNST; sau hỏi ROA, buộc dùng tài sản bình quân đầu/cuối kỳ và ghép B01 với B02. Chỉ dùng tài sản cuối kỳ sẽ cho một đáp án khác.
- **0014:** trước nhân DuPont rồi triệt tiêu các thành phần; sau tính CCC với tồn kho, phải thu khách hàng và phải trả người bán bình quân. Phải chọn công nợ thương mại, áp dụng ba mẫu số đúng và trừ thời gian trả người bán; kết quả âm có ý nghĩa tài trợ vốn lưu động, không bị đổi thành trị tuyệt đối.

## Schema và quy ước Gold

Giữ cấu trúc Numerical hiện có: `task: numerical_reasoning`; `evidence` là object Evidence v1, `supporting_evidence` là mảng bổ sung. `E1` trỏ evidence chính, `E2` là phần tử đầu tiên của supporting evidence; mỗi toán hạng có `name`, `value` decimal string, `unit`, `evidence_ref`. Giữ `formula.expression`, `formula.rounding`, `reasoning`, `input_documents`; không thêm company/industry/split/review hoặc tolerance. Các quote gồm header và toàn hàng thật, giữ số trang neutral, không gán thành trang PDF.

`formula.expression` dùng tên toán hạng, hằng số nguyên, `+ - * /`, ngoặc và `abs`. Tính bằng **Decimal precision 50**, không float/không làm tròn trung gian; `ROUND_HALF_UP` tại kết quả cuối. Tỷ lệ/hệ số/ngày mặc định 2 chữ số; **0007 dùng 3 chữ số theo câu hỏi**. Tiền giữ nguyên đơn vị VND, dấu ngoặc âm chuyển sang `-`; các chênh lệch tiền giữ số nguyên. `answer.type: number`, `answer.value` decimal string, `key_points: []`; chấm số không phụ thuộc văn phong reasoning/display.

Các unit giữ nguyên: `vnd`, `percent`, `ratio`, `percentage_point`; bổ sung duy nhất **`day` (ngày)** cho CCC. Không sửa Schema v1 của Single-hop/Multi-hop. Quy ước chỉ số có nhiều biến thể được đặt trong câu hỏi: thanh toán nhanh chỉ loại tồn kho; ROA dùng LNST và bình quân đầu/cuối năm; CCC dùng 365 ngày, doanh thu thuần/giá vốn làm đại diện cho bán chịu/mua hàng, phải thu khách hàng ngắn hạn trước dự phòng và phải trả người bán ngắn hạn. Phần tiền sau đầu tư ở 0013 chỉ xét CFO và chi mua sắm/xây dựng TSCĐ, tài sản dài hạn khác, không gọi đó là FCFF chuẩn hóa.

## Câu hỏi, công thức, toán hạng và nguồn

### VFB-NR-0001

Theo báo cáo tài chính năm 2023 của Công ty Cổ phần Mĩ thuật và Truyền thông (ADC), doanh thu thuần năm 2023 tăng bao nhiêu phần trăm so với năm 2022? Làm tròn đến 2 chữ số thập phân.

Gold: **10,56 %**. Công thức: `(revenue_2023 - revenue_2022) / revenue_2022 * 100`.

- `revenue_2023=431661958216` VND ← ADC_2023, trang 11, `ADC_2023_p011_t001`, hàng **3. Doanh thu thuần về bán hàng & cc dịch vụ**, cột **Năm 2023 VND** (E1).
- `revenue_2022=390415031494` VND ← ADC_2023, trang 11, `ADC_2023_p011_t001`, hàng **3. Doanh thu thuần về bán hàng & cc dịch vụ**, cột **Năm 2022 VND** (E2).

### VFB-NR-0002

Theo báo cáo tài chính năm 2024 của Công ty Cổ phần Khoáng sản Á Châu (AMC), lợi nhuận sau thuế năm 2024 chênh lệch bao nhiêu VND so với năm 2023? Tính năm 2024 trừ năm 2023, giữ dấu của kết quả.

Gold: **-249.512.955 VND**. Công thức: `pat_2024 - pat_2023`.

- `pat_2024=6186953400` VND ← AMC_2024, trang 9, `AMC_2024_p009_t001`, hàng **15. Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm nay** (E1).
- `pat_2023=6436466355` VND ← AMC_2024, trang 9, `AMC_2024_p009_t001`, hàng **15. Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm trước** (E2).

### VFB-NR-0003

Theo bảng cân đối kế toán năm 2023 của Công ty Cổ phần Xuất nhập khẩu Hàng không (ARM), tiền và các khoản tương đương tiền cuối năm chênh lệch bao nhiêu VND so với đầu năm? Tính số dư ngày 31/12/2023 trừ số dư ngày 01/01/2023.

Gold: **-379.046.514 VND**. Công thức: `cash_end - cash_begin`.

- `cash_end=7556416481` VND ← ARM_2023, trang 7, `ARM_2023_p007_t001`, hàng **I. Tiền và các khoản tương đương tiền**, cột **Tại ngày 31/12/2023** (E1).
- `cash_begin=7935462995` VND ← ARM_2023, trang 7, `ARM_2023_p007_t001`, hàng **I. Tiền và các khoản tương đương tiền**, cột **Tại ngày 01/01/2023** (E2).

### VFB-NR-0004

Theo báo cáo tài chính năm 2024 của Công ty Cổ phần Tập đoàn Đầu tư ATS, tổng tài sản ngày 31/12/2024 biến động bao nhiêu phần trăm so với ngày 01/01/2024? Giữ dấu tăng/giảm và làm tròn đến 2 chữ số thập phân.

Gold: **-4,01 %**. Công thức: `(assets_end - assets_begin) / assets_begin * 100`.

- `assets_end=48375125736` VND ← ATS_2024, trang 9, `ATS_2024_p009_t001`, hàng **TỔNG CỘNG TÀI SẢN**, cột **31/12/2024 (VND)** (E1).
- `assets_begin=50396277286` VND ← ATS_2024, trang 9, `ATS_2024_p009_t001`, hàng **TỔNG CỘNG TÀI SẢN**, cột **01/01/2024 (VND)** (E2).

### VFB-NR-0005

Theo báo cáo lưu chuyển tiền tệ năm 2024 của Công ty Cổ phần Sách và Thiết bị Trường học Đà Nẵng (BED), lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2024 chênh lệch bao nhiêu VND so với năm 2023? Tính năm 2024 trừ năm 2023.

Gold: **-5.602.449.814 VND**. Công thức: `cfo_2024 - cfo_2023`.

- `cfo_2024=5627994268` VND ← BED_2024, trang 11, `BED_2024_p011_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm 2024** (E1).
- `cfo_2023=11230444082` VND ← BED_2024, trang 11, `BED_2024_p011_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm 2023** (E2).

### VFB-NR-0006

Theo báo cáo hợp nhất năm 2024 của Công ty Cổ phần Văn hóa Tân Bình (ALT), biên lợi nhuận gộp năm 2024 là bao nhiêu phần trăm? Làm tròn đến 2 chữ số thập phân.

Gold: **11,99 %**. Công thức: `gross_profit / revenue * 100`.

- `gross_profit=49720776690` VND ← ALT_2024, trang 9, `ALT_2024_p009_t001`, hàng **5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ**, cột **Năm 2024** (E1).
- `revenue=414815832540` VND ← ALT_2024, trang 9, `ALT_2024_p009_t001`, hàng **3. Doanh thu thuần bán hàng và cung cấp dịch vụ**, cột **Năm 2024** (E2).

### VFB-NR-0007

Theo báo cáo hợp nhất năm 2025 của Công ty Cổ phần Alphanam E&C (AME), biên lợi nhuận ròng của toàn bộ tập đoàn năm 2025 là bao nhiêu phần trăm? Làm tròn đến 3 chữ số thập phân.

Gold: **0,815 %**. Công thức: `pat / revenue * 100`.

- `pat=40676793541` VND ← AME_2025, trang 9, `AME_2025_p009_t001`, hàng **16. Lợi nhuận sau thuế thu nhập doanh nghiệp (60=50 - 51)**, cột **Năm 2025** (E1).
- `revenue=4993200475924` VND ← AME_2025, trang 9, `AME_2025_p009_t001`, hàng **3. Doanh thu thuần về bán hàng và cung cấp dịch vụ (10= 01-02)**, cột **Năm 2025** (E2).

### VFB-NR-0008

Theo báo cáo tài chính năm 2025 của Công ty Cổ phần Vicem Bao bì Bút Sơn (BBS), nợ phải trả chiếm bao nhiêu phần trăm tổng tài sản tại ngày 31/12/2025? Làm tròn đến 2 chữ số thập phân.

Gold: **59,06 %**. Công thức: `liabilities / assets * 100`.

- `liabilities=157146559558` VND ← BBS_2025, trang 6, `BBS_2025_p006_t001`, hàng **C - NỢ PHẢI TRẢ**, cột **31/12/2025** (E1).
- `assets=266086680765` VND ← BBS_2025, trang 5, `BBS_2025_p005_t001`, hàng **TỔNG CỘNG TÀI SẢN**, cột **31/12/2025** (E2).

### VFB-NR-0009

Theo báo cáo hợp nhất năm 2024 của Công ty Cổ phần Xi măng Bỉm Sơn (BCC), hệ số thanh toán hiện hành tại ngày 31/12/2024 là bao nhiêu lần? Làm tròn đến 2 chữ số thập phân.

Gold: **0,42 lần**. Công thức: `current_assets / current_liabilities`.

- `current_assets=672229543798` VND ← BCC_2024, trang 9, `BCC_2024_p009_t001`, hàng **A. TÀI SẢN NGẮN HẠN**, cột **Số cuối năm** (E1).
- `current_liabilities=1611658282496` VND ← BCC_2024, trang 10, `BCC_2024_p010_t001`, hàng **I. Nợ ngắn hạn**, cột **Số cuối năm** (E2).

### VFB-NR-0010

Theo báo cáo tài chính riêng năm 2023 của Công ty Cổ phần Khoáng sản Bắc Kạn (BKC), hệ số thanh toán nhanh tại ngày 31/12/2023 là bao nhiêu lần? Áp dụng quy ước chỉ loại hàng tồn kho khỏi tài sản ngắn hạn; làm tròn đến 2 chữ số thập phân.

Gold: **0,78 lần**. Công thức: `(current_assets - inventory) / current_liabilities`.

- `current_assets=266334866645` VND ← BKC_2023, trang 10, `BKC_2023_p010_t001`, hàng **TÀI SẢN NGẮN HẠN (100 = 110+130+140+150)**, cột **31/12/2023** (E1).
- `inventory=146117484978` VND ← BKC_2023, trang 10, `BKC_2023_p010_t001`, hàng **IV. Hàng tồn kho**, cột **31/12/2023** (E2).
- `current_liabilities=155008443033` VND ← BKC_2023, trang 11, `BKC_2023_p011_t001`, hàng **I. Nợ ngắn hạn**, cột **31/12/2023** (E3).

### VFB-NR-0011

Theo báo cáo tài chính năm 2025 của Công ty Cổ phần Vicem Bao bì Bỉm Sơn (BPC), tỷ suất sinh lời sau thuế trên tổng tài sản bình quân (ROA) năm 2025 là bao nhiêu phần trăm? Dùng bình quân số dư đầu và cuối năm; làm tròn đến 2 chữ số thập phân.

Gold: **0,83 %**. Công thức: `pat / ((assets_begin + assets_end) / 2) * 100`.

- `pat=1447331727` VND ← BPC_2025, trang 7, `BPC_2025_p007_t001`, hàng **Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm 2025** (E1).
- `assets_begin=178138045193` VND ← BPC_2025, trang 5, `BPC_2025_p005_t001`, hàng **TỔNG CỘNG TÀI SẢN**, cột **01/01/2025** (E2).
- `assets_end=169985696177` VND ← BPC_2025, trang 5, `BPC_2025_p005_t001`, hàng **TỔNG CỘNG TÀI SẢN**, cột **31/12/2025** (E3).

### VFB-NR-0012

Theo báo cáo tài chính năm 2025 của Công ty Cổ phần Cảng An Giang (CAG), dòng tiền thuần từ hoạt động kinh doanh trang trải bao nhiêu phần trăm tiền chi mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác trong năm 2025? Lấy giá trị tuyệt đối của dòng tiền chi làm mẫu số và làm tròn đến 2 chữ số thập phân.

Gold: **128,72 %**. Công thức: `cfo / abs(capex_cash_flow) * 100`.

- `cfo=2945594773` VND ← CAG_2025, trang 11, `CAG_2025_p011_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm nay** (E1).
- `capex_cash_flow=-2288380037` VND ← CAG_2025, trang 11, `CAG_2025_p011_t002`, hàng **1. Tiền chi để mua sắm, xây dựng tài sản cố định và các tài sản dài hạn khác**, cột **Năm nay** (E2).

### VFB-NR-0013

Theo báo cáo tài chính riêng năm 2025 của Công ty Cổ phần Xi măng Vicem Bút Sơn (BTS), lượng tiền còn lại từ hoạt động kinh doanh sau khi tự tài trợ chi mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác đã cải thiện bao nhiêu VND trong năm 2025 so với năm 2024? Chỉ xét khoản chi này, không tính các dòng đầu tư khác; báo mức thay đổi có dấu.

Gold: **157.588.095.957 VND**. Công thức: `(cfo_2025 - abs(capex_2025)) - (cfo_2024 - abs(capex_2024))`.

- `cfo_2025=196111084304` VND ← BTS_2025, trang 13, `BTS_2025_p013_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm nay** (E1).
- `capex_2025=-64286120236` VND ← BTS_2025, trang 13, `BTS_2025_p013_t001`, hàng **1. Tiền chi mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác**, cột **Năm nay** (E2).
- `cfo_2024=145726718525` VND ← BTS_2025, trang 13, `BTS_2025_p013_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm trước** (E3).
- `capex_2024=-171489850414` VND ← BTS_2025, trang 13, `BTS_2025_p013_t001`, hàng **1. Tiền chi mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác**, cột **Năm trước** (E4).

### VFB-NR-0014

Theo báo cáo tài chính riêng năm 2025 của Công ty Cổ phần Cấp nước Bến Thành (BTW), chu kỳ chuyển đổi tiền mặt ước tính năm 2025 là bao nhiêu ngày? Quy ước năm có 365 ngày, dùng số dư bình quân đầu và cuối năm; lấy doanh thu thuần thay doanh thu bán chịu, giá vốn hàng bán thay giá trị mua hàng. Với công nợ, chỉ xét phải thu khách hàng ngắn hạn trước dự phòng và phải trả người bán ngắn hạn. Giữ dấu kết quả và làm tròn đến 2 chữ số thập phân.

Gold: **-26,82 ngày**. Công thức: `((inventory_begin + inventory_end) / 2 / cogs + (trade_receivables_begin + trade_receivables_end) / 2 / revenue - (trade_payables_begin + trade_payables_end) / 2 / cogs) * 365`.

- `inventory_begin=25064720944` VND ← BTW_2025, trang 10, `BTW_2025_p010_t001`, hàng **Hàng tồn kho**, cột **Tại 01/01/2025 VND** (E1).
- `inventory_end=32638507469` VND ← BTW_2025, trang 10, `BTW_2025_p010_t001`, hàng **Hàng tồn kho**, cột **Tại 31/12/2025 VND** (E2).
- `trade_receivables_begin=11460895440` VND ← BTW_2025, trang 10, `BTW_2025_p010_t001`, hàng **Phải thu ngắn hạn của khách hàng**, cột **Tại 01/01/2025 VND** (E3).
- `trade_receivables_end=11681731821` VND ← BTW_2025, trang 10, `BTW_2025_p010_t001`, hàng **Phải thu ngắn hạn của khách hàng**, cột **Tại 31/12/2025 VND** (E4).
- `trade_payables_begin=66528204283` VND ← BTW_2025, trang 11, `BTW_2025_p011_t001`, hàng **Phải trả người bán ngắn hạn**, cột **Tại 01/01/2025 VND** (E5).
- `trade_payables_end=54085809693` VND ← BTW_2025, trang 11, `BTW_2025_p011_t001`, hàng **Phải trả người bán ngắn hạn**, cột **Tại 31/12/2025 VND** (E6).
- `revenue=550869711512` VND ← BTW_2025, trang 12, `BTW_2025_p012_t001`, hàng **Doanh thu thuần về bán hàng và cung cấp dịch vụ**, cột **Năm 2025 VND** (E7).
- `cogs=332918140913` VND ← BTW_2025, trang 12, `BTW_2025_p012_t001`, hàng **Giá vốn hàng bán**, cột **Năm 2025 VND** (E8).

### VFB-NR-0015

Theo báo cáo hợp nhất năm 2025 của Công ty Cổ phần Xây dựng 1369 (C69), mức chuyển đổi lợi nhuận sau thuế thành dòng tiền kinh doanh của toàn tập đoàn đã thay đổi bao nhiêu điểm phần trăm trong năm 2025 so với năm 2024? Xét dòng tiền thuần từ hoạt động kinh doanh so với lợi nhuận sau thuế của từng năm, báo thay đổi có dấu và làm tròn kết quả cuối đến 2 chữ số thập phân.

Gold: **-979,33 điểm phần trăm**. Công thức: `(cfo_2025 / pat_2025 - cfo_2024 / pat_2024) * 100`.

- `cfo_2025=-150018916317` VND ← C69_2025, trang 18, `C69_2025_p018_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm nay** (E1).
- `pat_2025=43284958984` VND ← C69_2025, trang 17, `C69_2025_p017_t001`, hàng **Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm nay** (E2).
- `cfo_2024=138308866178` VND ← C69_2025, trang 18, `C69_2025_p018_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm trước** (E3).
- `pat_2024=21858531665` VND ← C69_2025, trang 17, `C69_2025_p017_t001`, hàng **Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm trước** (E4).

## Focused validation

**PASS local**, chỉ trên phạm vi Pilot; script tính/kiểm tra tạm ngoài repo, không thêm parser/evaluator/framework:

- Parse UTF-8 JSONL, 15 ID cũ duy nhất và 5/7/3; schema hiện có, E1…En, decimal strings/unit, không float. Đối chiếu baseline: **7 item KEEP bằng nguyên object**, 6 REWRITE, 2 REPLACE. Không trùng ID/câu hỏi trong subset khác.
- **42/42 toán hạng** khớp giá trị bảng/hàng/cột trong neutral; từng quote header/hàng khớp Markdown cùng trang, table reference khớp TXT; kiểm tra unit_evidence, năm và scope. Với nhãn tồn kho lặp, quote toàn hàng chứa mã số 140 để phân biệt hàng 141.
- **15/15 Gold tính lại độc lập bằng Decimal từ ô nguồn**, theo công thức tài chính riêng từng câu; kiểm tra ROUND_HALF_UP và không làm tròn trung gian. Kiểm tra riêng FCF hai kỳ, số dư bình quân ROA/CCC, các thành phần DIO/DSO/DPO, CFO âm và chênh lệch điểm phần trăm. 0006 cho 11,986229258789…%, cao hơn ngưỡng 11,985%, nên làm tròn thành 11,99%; kiểm tra thêm hai trường hợp đúng điểm giữa với dấu dương/âm cho ROUND_HALF_UP.
- Đối chiếu lựa chọn dễ nhầm: 0007 dùng LNST toàn tập đoàn ra 0,815%, phần công ty mẹ ra 0,808%; 0011 dùng tài sản bình quân thay số dư cuối kỳ; 0014 dùng công nợ thương mại thay tổng phải thu/nợ ngắn hạn.
- SHA-256 **130 file** neutral/benchmark ngoài Numerical giữ nguyên so với snapshot đầu task. `git diff --check` và staged diff PASS; chỉ hai deliverables được stage/commit. Không chạy lại full CI, benchmark mô hình, OCR, PDF/PNG hoặc API Gemini/Qwen.

## Hạn chế và bước tiếp theo

Gold được tự kiểm trên neutral, chưa có review độc lập từ PDF. C69 partial thiếu trang 30; câu 0015 chỉ dùng trang 17–18 hiện có. Các scope `unknown` giữ nguyên cách gọi “theo báo cáo tài chính”; không tự coi là báo cáo riêng/hợp nhất. CCC là ước tính theo các đại diện và số dư bình quân đã nêu, không phải số ngày thu/trả thực tế; ba kiểu Explicit/Implicit/Advanced và nhãn khó là đánh giá biên soạn, chưa có kết quả mô hình để hiệu chuẩn. Ba câu còn dùng nguồn đơn vị phụ B09; chưa có tolerance/evaluator. Validation xác nhận tính toán và provenance trong neutral, không chứng nhận độ đúng tài chính từ PDF hoặc chất lượng Multi-Agent.

**Next action duy nhất:** Tech Lead nghiệm thu ViFinBench-NR-PILOT-Refine trước khi quyết định mở rộng.
