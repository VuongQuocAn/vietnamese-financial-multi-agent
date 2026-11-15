# ViFinBench-NR-PILOT — 15 Numerical Reasoning QA

Ngày: **15/11/2026** (Asia/Bangkok). Trạng thái: **REVIEW**, chờ Tech Lead nghiệm thu; chưa mở rộng lên 200 câu.

Dataset: [pilot.jsonl](../ViFinBench/benchmark/numerical/pilot.jsonl). Chỉ thay đổi dataset này và báo cáo này; giữ nguyên Single-hop, Multi-hop, neutral, metadata, schema chung, planning và pipeline DACNTT. Các local edits có trước task được giữ nguyên.

Implementation là commit chứa hai deliverables; lấy SHA bằng `git log -1 --format=%H -- ViFinBench/benchmark/numerical/pilot.jsonl`. SHA cụ thể được ghi trong bàn giao sau commit, không dùng SHA baseline làm implementation.

## Quy ước mở rộng tối thiểu cho Numerical

Áp dụng theo phạm vi task cho phép lưu `formula` và `operands`, giữ các trường chung Schema v1: `task: numerical_reasoning`; `evidence` vẫn là **object Evidence v1**. `supporting_evidence` là mảng Evidence v1 bổ sung; `E1` trỏ tới `evidence`, `E2` tới phần tử đầu tiên của `supporting_evidence`, tiếp tục theo thứ tự. Mỗi toán hạng có `name`, `value` (decimal string), `unit`, `evidence_ref`; mỗi bằng chứng xác định document, trang neutral, table ID, nhãn hàng và header cột thật. `input_documents` liệt kê tài liệu đầu vào; `reasoning` lưu các bước tính ngắn gọn như Multi-hop. Không tạo evaluator hay sửa Schema v1 của các subset đã nghiệm thu.

`formula.expression` chỉ dùng tên toán hạng, hằng số nguyên, `+ - * /`, ngoặc và `abs`; `formula.rounding` quy định `decimal_places` và `mode: ROUND_HALF_UP`. Các số tiền toán hạng giữ nguyên **VND** theo đơn vị nguồn; dấu ngoặc âm được chuẩn hóa thành dấu `-`. `answer.type: number`, `answer.value` là decimal string để chấm số độc lập với `display`/lời giải; `key_points: []`, không áp đặt văn phong trả lời hay tolerance. Các unit bổ sung thực sự cần cho Numerical: `percent` (%), `ratio` (lần), `percentage_point` (điểm phần trăm); giữ `vnd` cho chênh lệch tiền. Phần trăm, điểm phần trăm và hệ số làm tròn 2 chữ số thập phân ở **kết quả cuối**; chênh lệch tiền giữ số nguyên chính xác. Tính bằng `Decimal`, precision 50, không dùng float hoặc làm tròn trung gian.

## Tổng hợp 15 câu hỏi và đáp án

| ID | Độ khó | Câu hỏi | Đáp án |
| --- | --- | --- | --- |
| VFB-NR-0001 | Easy | Theo báo cáo tài chính năm 2023 của Công ty Cổ phần Mĩ thuật và Truyền thông (ADC), doanh thu thuần năm 2023 tăng bao nhiêu phần trăm so với năm 2022? Làm tròn đến 2 chữ số thập phân. | **10,56 %** |
| VFB-NR-0002 | Easy | Theo báo cáo tài chính năm 2024 của Công ty Cổ phần Khoáng sản Á Châu (AMC), lợi nhuận sau thuế năm 2024 chênh lệch bao nhiêu VND so với năm 2023? Tính năm 2024 trừ năm 2023, giữ dấu của kết quả. | **-249.512.955 VND** |
| VFB-NR-0003 | Easy | Theo bảng cân đối kế toán năm 2023 của Công ty Cổ phần Xuất nhập khẩu Hàng không (ARM), tiền và các khoản tương đương tiền cuối năm chênh lệch bao nhiêu VND so với đầu năm? Tính số dư ngày 31/12/2023 trừ số dư ngày 01/01/2023. | **-379.046.514 VND** |
| VFB-NR-0004 | Easy | Theo báo cáo tài chính năm 2024 của Công ty Cổ phần Tập đoàn Đầu tư ATS, tổng tài sản ngày 31/12/2024 biến động bao nhiêu phần trăm so với ngày 01/01/2024? Giữ dấu tăng/giảm và làm tròn đến 2 chữ số thập phân. | **-4,01 %** |
| VFB-NR-0005 | Easy | Theo báo cáo lưu chuyển tiền tệ năm 2024 của Công ty Cổ phần Sách và Thiết bị Trường học Đà Nẵng (BED), lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2024 chênh lệch bao nhiêu VND so với năm 2023? Tính năm 2024 trừ năm 2023. | **-5.602.449.814 VND** |
| VFB-NR-0006 | Medium | Theo báo cáo hợp nhất năm 2024 của Công ty Cổ phần Văn hóa Tân Bình (ALT), biên lợi nhuận gộp năm 2024 bằng bao nhiêu phần trăm doanh thu thuần? Làm tròn đến 2 chữ số thập phân. | **11,99 %** |
| VFB-NR-0007 | Medium | Theo báo cáo hợp nhất năm 2025 của Công ty Cổ phần Alphanam E&C (AME), biên lợi nhuận ròng năm 2025 bằng bao nhiêu phần trăm? Dùng lợi nhuận sau thuế toàn tập đoàn (mã số 60) chia doanh thu thuần và làm tròn đến 2 chữ số thập phân. | **0,81 %** |
| VFB-NR-0008 | Medium | Theo báo cáo tài chính năm 2025 của Công ty Cổ phần Vicem Bao bì Bút Sơn (BBS), nợ phải trả chiếm bao nhiêu phần trăm tổng tài sản tại ngày 31/12/2025? Làm tròn đến 2 chữ số thập phân. | **59,06 %** |
| VFB-NR-0009 | Medium | Theo báo cáo hợp nhất năm 2024 của Công ty Cổ phần Xi măng Bỉm Sơn (BCC), hệ số thanh toán hiện hành tại ngày 31/12/2024 bằng bao nhiêu lần? Tính tài sản ngắn hạn chia nợ ngắn hạn và làm tròn đến 2 chữ số thập phân. | **0,42 lần** |
| VFB-NR-0010 | Medium | Theo báo cáo tài chính riêng năm 2023 của Công ty Cổ phần Khoáng sản Bắc Kạn (BKC), hệ số thanh toán nhanh tại ngày 31/12/2023 bằng bao nhiêu lần nếu tính bằng (tài sản ngắn hạn − hàng tồn kho) / nợ ngắn hạn? Làm tròn đến 2 chữ số thập phân. | **0,78 lần** |
| VFB-NR-0011 | Medium | Theo báo cáo tài chính năm 2025 của Công ty Cổ phần Vicem Bao bì Bỉm Sơn (BPC), lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2025 bằng bao nhiêu phần trăm lợi nhuận sau thuế cùng năm? Làm tròn đến 2 chữ số thập phân. | **414,38 %** |
| VFB-NR-0012 | Medium | Theo báo cáo tài chính năm 2025 của Công ty Cổ phần Cảng An Giang (CAG), dòng tiền thuần từ hoạt động kinh doanh trang trải bao nhiêu phần trăm tiền chi mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác trong năm 2025? Lấy giá trị tuyệt đối của dòng tiền chi làm mẫu số và làm tròn đến 2 chữ số thập phân. | **128,72 %** |
| VFB-NR-0013 | Hard | Theo báo cáo tài chính riêng năm 2025 của Công ty Cổ phần Xi măng Vicem Bút Sơn (BTS), dòng tiền tự do theo định nghĩa CFO trừ tiền chi mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác đã cải thiện bao nhiêu VND từ năm 2024 sang năm 2025? Tính dòng tiền tự do từng năm rồi lấy năm 2025 trừ năm 2024; tiền chi được trừ theo giá trị tuyệt đối. | **157.588.095.957 VND** |
| VFB-NR-0014 | Hard | Theo báo cáo tài chính riêng năm 2025 của Công ty Cổ phần Cấp nước Bến Thành (BTW), ROE năm 2025 tính theo phân rã DuPont ba thành phần bằng bao nhiêu phần trăm? Dùng (LNST / doanh thu thuần) × (doanh thu thuần / tổng tài sản bình quân) × (tổng tài sản bình quân / vốn chủ sở hữu bình quân); mỗi số bình quân lấy trung bình số dư ngày 01/01/2025 và 31/12/2025. Không làm tròn trung gian; làm tròn ROE đến 2 chữ số thập phân. | **18,24 %** |
| VFB-NR-0015 | Hard | Theo báo cáo hợp nhất năm 2025 của Công ty Cổ phần Xây dựng 1369 (C69), tỷ lệ chuyển đổi lợi nhuận thành tiền (CFO / LNST toàn tập đoàn × 100) năm 2025 thay đổi bao nhiêu điểm phần trăm so với năm 2024? Tính tỷ lệ từng năm bằng số liệu của chính năm đó, lấy năm 2025 trừ năm 2024, giữ dấu âm của CFO và chỉ làm tròn kết quả cuối đến 2 chữ số thập phân. | **-979,33 điểm phần trăm** |

## Phân bố và nguồn

- **15 QA = 5 Easy / 7 Medium / 3 Hard**; ID liên tục `VFB-NR-0001`–`VFB-NR-0015`, không trùng ID Single-hop/Multi-hop.
- **15 doanh nghiệp / 15 tài liệu**; năm tài liệu: 2023 (ADC, ARM, BKC), 2024 (AMC, ATS, BED, ALT, BCC), 2025 (AME, BBS, BPC, CAG, BTS, BTW, C69). Toán hạng có cả kỳ so sánh 2022; không ghép hai tài liệu có phạm vi khác nhau.
- **15/15 QA khai thác B01/B02/B03**. Đếm QA theo nguồn toán hạng (có thể chồng): **B01: 6; B02: 7; B03: 5; B09: 0**. Ba câu ghép B01/B02 hoặc B02/B03: 0011, 0014, 0015.
- Nguồn xác nhận đơn vị phụ từ B09 cho **3 QA**: ARM trang 13, ALT trang 13, BKC trang 15; chỉ trích chính sách trình bày VND, **không lấy toán hạng tài chính từ B09**. Nguồn đơn vị này vẫn được ghi trong `unit_evidence`, không tính thành báo cáo chính hoặc bước suy luận số học. Các đơn vị còn lại có ở header/báo cáo chính.
- Easy dùng hai giá trị cho phép trừ hoặc tỷ lệ biến động; Medium áp dụng công thức tài chính; Hard gồm FCF qua hai kỳ (0013), phân rã DuPont kết hợp hai báo cáo và số dư bình quân (0014), thay đổi CFO/LNST qua hai kỳ và hai báo cáo (0015). DuPont là công thức tài chính chuẩn; có kiểm tra rút gọn ROE, không coi số phép toán riêng lẻ là thước đo độ khó.

## Công thức, toán hạng và nguồn từng câu

Các cột so sánh `Năm nay/Năm trước` được gắn với năm báo cáo/năm liền trước theo tiêu đề trang. Cột `Số cuối năm/Số đầu năm` dùng đúng mốc cuối/đầu kỳ; phạm vi hợp nhất/riêng chỉ ghi khi metadata đã xác minh. Những tài liệu `unknown` được gọi là “theo báo cáo tài chính”, không tự suy thành báo cáo riêng. Quote nguyên văn header và toàn hàng được giữ trong JSONL, không chép lại toàn bảng ở báo cáo.

### VFB-NR-0001

Công thức: `(revenue_2023 - revenue_2022) / revenue_2022 * 100` → **10,56 %**.

- `revenue_2023=431661958216` VND ← ADC_2023, trang 11, `ADC_2023_p011_t001`, hàng **3. Doanh thu thuần về bán hàng & cc dịch vụ**, cột **Năm 2023 VND** (E1)
- `revenue_2022=390415031494` VND ← ADC_2023, trang 11, `ADC_2023_p011_t001`, hàng **3. Doanh thu thuần về bán hàng & cc dịch vụ**, cột **Năm 2022 VND** (E2)

Lấy doanh thu thuần năm 2022 làm mẫu số của tỷ lệ tăng trưởng.

### VFB-NR-0002

Công thức: `pat_2024 - pat_2023` → **-249.512.955 VND**.

- `pat_2024=6186953400` VND ← AMC_2024, trang 9, `AMC_2024_p009_t001`, hàng **15. Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm nay** (E1)
- `pat_2023=6436466355` VND ← AMC_2024, trang 9, `AMC_2024_p009_t001`, hàng **15. Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm trước** (E2)

Cột Năm nay là 2024, Năm trước là 2023 theo tiêu đề báo cáo; kết quả âm biểu thị mức giảm.

### VFB-NR-0003

Công thức: `cash_end - cash_begin` → **-379.046.514 VND**.

- `cash_end=7556416481` VND ← ARM_2023, trang 7, `ARM_2023_p007_t001`, hàng **I. Tiền và các khoản tương đương tiền**, cột **Tại ngày 31/12/2023** (E1)
- `cash_begin=7935462995` VND ← ARM_2023, trang 7, `ARM_2023_p007_t001`, hàng **I. Tiền và các khoản tương đương tiền**, cột **Tại ngày 01/01/2023** (E2)

So sánh hai số dư cùng khoản mục; giữ dấu âm nếu tiền giảm.

### VFB-NR-0004

Công thức: `(assets_end - assets_begin) / assets_begin * 100` → **-4,01 %**.

- `assets_end=48375125736` VND ← ATS_2024, trang 9, `ATS_2024_p009_t001`, hàng **TỔNG CỘNG TÀI SẢN**, cột **31/12/2024 (VND)** (E1)
- `assets_begin=50396277286` VND ← ATS_2024, trang 9, `ATS_2024_p009_t001`, hàng **TỔNG CỘNG TÀI SẢN**, cột **01/01/2024 (VND)** (E2)

Lấy tổng tài sản đầu năm làm mẫu số; kết quả âm là giảm.

### VFB-NR-0005

Công thức: `cfo_2024 - cfo_2023` → **-5.602.449.814 VND**.

- `cfo_2024=5627994268` VND ← BED_2024, trang 11, `BED_2024_p011_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm 2024** (E1)
- `cfo_2023=11230444082` VND ← BED_2024, trang 11, `BED_2024_p011_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm 2023** (E2)

Dùng dòng tiền thuần từ hoạt động kinh doanh, không dùng lưu chuyển tiền thuần trong năm.

### VFB-NR-0006

Công thức: `gross_profit / revenue * 100` → **11,99 %**.

- `gross_profit=49720776690` VND ← ALT_2024, trang 9, `ALT_2024_p009_t001`, hàng **5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ**, cột **Năm 2024** (E1)
- `revenue=414815832540` VND ← ALT_2024, trang 9, `ALT_2024_p009_t001`, hàng **3. Doanh thu thuần bán hàng và cung cấp dịch vụ**, cột **Năm 2024** (E2)

Biên lợi nhuận gộp bằng lợi nhuận gộp chia doanh thu thuần, nhân 100.

### VFB-NR-0007

Công thức: `pat / revenue * 100` → **0,81 %**.

- `pat=40676793541` VND ← AME_2025, trang 9, `AME_2025_p009_t001`, hàng **16. Lợi nhuận sau thuế thu nhập doanh nghiệp (60=50 - 51)**, cột **Năm 2025** (E1)
- `revenue=4993200475924` VND ← AME_2025, trang 9, `AME_2025_p009_t001`, hàng **3. Doanh thu thuần về bán hàng và cung cấp dịch vụ (10= 01-02)**, cột **Năm 2025** (E2)

Chọn LNST toàn tập đoàn, không thay bằng LNST thuộc cổ đông công ty mẹ.

### VFB-NR-0008

Công thức: `liabilities / assets * 100` → **59,06 %**.

- `liabilities=157146559558` VND ← BBS_2025, trang 6, `BBS_2025_p006_t001`, hàng **C - NỢ PHẢI TRẢ**, cột **31/12/2025** (E1)
- `assets=266086680765` VND ← BBS_2025, trang 5, `BBS_2025_p005_t001`, hàng **TỔNG CỘNG TÀI SẢN**, cột **31/12/2025** (E2)

Ghép nợ phải trả và tổng tài sản cùng ngày cuối năm; dùng tổng nợ, không chỉ nợ vay.

### VFB-NR-0009

Công thức: `current_assets / current_liabilities` → **0,42 lần**.

- `current_assets=672229543798` VND ← BCC_2024, trang 9, `BCC_2024_p009_t001`, hàng **A. TÀI SẢN NGẮN HẠN**, cột **Số cuối năm** (E1)
- `current_liabilities=1611658282496` VND ← BCC_2024, trang 10, `BCC_2024_p010_t001`, hàng **I. Nợ ngắn hạn**, cột **Số cuối năm** (E2)

Số cuối năm trong hai phần bảng cân đối hợp nhất đều là tại 31/12/2024.

### VFB-NR-0010

Công thức: `(current_assets - inventory) / current_liabilities` → **0,78 lần**.

- `current_assets=266334866645` VND ← BKC_2023, trang 10, `BKC_2023_p010_t001`, hàng **TÀI SẢN NGẮN HẠN (100 = 110+130+140+150)**, cột **31/12/2023** (E1)
- `inventory=146117484978` VND ← BKC_2023, trang 10, `BKC_2023_p010_t001`, hàng **IV. Hàng tồn kho**, cột **31/12/2023** (E2)
- `current_liabilities=155008443033` VND ← BKC_2023, trang 11, `BKC_2023_p011_t001`, hàng **I. Nợ ngắn hạn**, cột **31/12/2023** (E3)

Trừ hàng tồn kho khỏi tài sản ngắn hạn rồi chia nợ ngắn hạn cùng ngày; dùng đúng định nghĩa đã nêu trong câu hỏi.

### VFB-NR-0011

Công thức: `cfo / pat * 100` → **414,38 %**.

- `cfo=5997429314` VND ← BPC_2025, trang 8, `BPC_2025_p008_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm 2025** (E1)
- `pat=1447331727` VND ← BPC_2025, trang 7, `BPC_2025_p007_t001`, hàng **Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm 2025** (E2)

Ghép CFO trên B03 với LNST trên B02 cùng năm 2025.

### VFB-NR-0012

Công thức: `cfo / abs(capex_cash_flow) * 100` → **128,72 %**.

- `cfo=2945594773` VND ← CAG_2025, trang 11, `CAG_2025_p011_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm nay** (E1)
- `capex_cash_flow=-2288380037` VND ← CAG_2025, trang 11, `CAG_2025_p011_t002`, hàng **1. Tiền chi để mua sắm, xây dựng tài sản cố định và các tài sản dài hạn khác**, cột **Năm nay** (E2)

Dòng tiền chi ghi âm trong bảng; dùng độ lớn khoản chi khi tính tỷ lệ trang trải.

### VFB-NR-0013

Công thức: `(cfo_2025 - abs(capex_2025)) - (cfo_2024 - abs(capex_2024))` → **157.588.095.957 VND**.

- `cfo_2025=196111084304` VND ← BTS_2025, trang 13, `BTS_2025_p013_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm nay** (E1)
- `capex_2025=-64286120236` VND ← BTS_2025, trang 13, `BTS_2025_p013_t001`, hàng **1. Tiền chi mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác**, cột **Năm nay** (E2)
- `cfo_2024=145726718525` VND ← BTS_2025, trang 13, `BTS_2025_p013_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm trước** (E3)
- `capex_2024=-171489850414` VND ← BTS_2025, trang 13, `BTS_2025_p013_t001`, hàng **1. Tiền chi mua sắm, xây dựng TSCĐ và các tài sản dài hạn khác**, cột **Năm trước** (E4)

FCF 2025 = 196111084304 − 64286120236 = 131824964068 VND. FCF 2024 = 145726718525 − 171489850414 = −25763131889 VND; lấy FCF 2025 trừ FCF 2024.

### VFB-NR-0014

Công thức: `(pat / revenue) * (revenue / ((assets_begin + assets_end) / 2)) * (((assets_begin + assets_end) / 2) / ((equity_begin + equity_end) / 2)) * 100` → **18,24 %**.

- `pat=48292022418` VND ← BTW_2025, trang 12, `BTW_2025_p012_t001`, hàng **Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm 2025 VND** (E1)
- `revenue=550869711512` VND ← BTW_2025, trang 12, `BTW_2025_p012_t001`, hàng **Doanh thu thuần về bán hàng và cung cấp dịch vụ**, cột **Năm 2025 VND** (E2)
- `assets_begin=380695090023` VND ← BTW_2025, trang 10, `BTW_2025_p010_t001`, hàng **TỔNG TÀI SẢN**, cột **Tại 01/01/2025 VND** (E3)
- `assets_end=384095301328` VND ← BTW_2025, trang 10, `BTW_2025_p010_t001`, hàng **TỔNG TÀI SẢN**, cột **Tại 31/12/2025 VND** (E4)
- `equity_begin=261296524351` VND ← BTW_2025, trang 11, `BTW_2025_p011_t001`, hàng **Vốn chủ sở hữu**, cột **Tại 01/01/2025 VND** (E5)
- `equity_end=268214288536` VND ← BTW_2025, trang 11, `BTW_2025_p011_t001`, hàng **Vốn chủ sở hữu**, cột **Tại 31/12/2025 VND** (E6)

Tổng tài sản bình quân = 382395195675,5 VND; vốn chủ sở hữu bình quân = 264755406443,5 VND. Tính ba thành phần DuPont từ B01 và B02 rồi nhân; kiểm tra tương đương LNST / vốn chủ sở hữu bình quân × 100.

### VFB-NR-0015

Công thức: `(cfo_2025 / pat_2025 - cfo_2024 / pat_2024) * 100` → **-979,33 điểm phần trăm**.

- `cfo_2025=-150018916317` VND ← C69_2025, trang 18, `C69_2025_p018_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm nay** (E1)
- `pat_2025=43284958984` VND ← C69_2025, trang 17, `C69_2025_p017_t001`, hàng **Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm nay** (E2)
- `cfo_2024=138308866178` VND ← C69_2025, trang 18, `C69_2025_p018_t001`, hàng **Lưu chuyển tiền thuần từ hoạt động kinh doanh**, cột **Năm trước** (E3)
- `pat_2024=21858531665` VND ← C69_2025, trang 17, `C69_2025_p017_t001`, hàng **Lợi nhuận sau thuế thu nhập doanh nghiệp**, cột **Năm trước** (E4)

Tính riêng CFO/LNST năm 2025 và năm 2024; CFO 2025 âm, hai LNST đều dương. Lấy chênh lệch hai tỷ lệ theo điểm phần trăm, không chia tiếp cho tỷ lệ năm 2024.

## Focused validation

**PASS local** cho dữ liệu bàn giao (script tạm ngoài repository; không thêm framework/pipeline):

- Parse UTF-8 JSONL, đúng 15 record/ID, 5/7/3, các trường chung và mở rộng, decimal strings, đơn vị, không có float; không trùng ID/câu hỏi trong benchmark hiện có.
- Tính lại độc lập **15/15 đáp án** từ ô neutral bằng `Decimal` theo công thức tài chính tương ứng; so giá trị cuối và quy tắc làm tròn. Kiểm tra FCF từng kỳ, dấu dòng tiền, điểm phần trăm và đẳng thức DuPont/ROE rút gọn.
- Đối chiếu **39/39 toán hạng/tham chiếu ô** với giá trị tại bảng/hàng/cột được dẫn, exact header/row trong Markdown, table reference trong TXT cùng trang; xác nhận quote và nguồn đơn vị phụ. Kiểm tra kỳ, phạm vi và số QA từng loại báo cáo bằng tay trên các nguồn đã chọn. Bốn đáp án chênh lệch tiền không xuất hiện trực tiếp trong Markdown của tài liệu tương ứng.
- SHA-256 của **130 file** neutral và benchmark có trước task giữ nguyên so với snapshot trước khi ghi; Git chỉ stage hai deliverables. `git diff --check` và kiểm tra staged diff không whitespace error.

Không chạy full CI, evaluator, OCR, PDF/PNG, Gemini/Qwen hoặc API trả phí; không benchmark mô hình. Các kiểm tra trên xác nhận tính toán và dẫn nguồn **trong neutral**, không chứng nhận accuracy từ PDF hay hiệu năng hệ thống Multi-Agent.

## Hạn chế và bước tiếp theo

Gold do biên soạn và tự kiểm trên neutral, chưa có người thứ hai đối chiếu PDF. C69 là export `partial` (thiếu trang 30); chỉ dùng trang 17–18 hiện có, không suy dữ liệu trang thiếu. Một số tài liệu có scope `unknown`; không tự gắn nhãn riêng/hợp nhất. B09 chỉ bổ sung đơn vị cho ba câu, không là nguồn toán hạng. Các chỉ số FCF và thanh toán nhanh có nhiều cách định nghĩa; câu hỏi đã nêu rõ công thức áp dụng. Chưa đánh giá mức khó bằng thực nghiệm mô hình, chưa định nghĩa tolerance/evaluator.

**Next action duy nhất:** Tech Lead review 15 QA và nghiệm thu ViFinBench-NR-PILOT trước khi quyết định mở rộng.
