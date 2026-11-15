# ViFinBench-NR-FULL — 200 Numerical Reasoning QA mới

Ngày **15/11/2026** (Asia/Bangkok). Trạng thái **REVIEW**, chờ Tech Lead nghiệm thu. Baseline: `358318aa38dd1e1532390afe5150022be4e0c542`, Numerical Pilot đã được nghiệm thu theo brief Full.

[Dataset Full](../ViFinBench/benchmark/numerical/full.jsonl) có **200 QA mới**, ID `VFB-NR-0016`–`VFB-NR-0215`. [Pilot](../ViFinBench/benchmark/numerical/pilot.jsonl) giữ nguyên 15 QA/ID cũ; tổng hai file là **215 QA**. Không đưa Pilot vào Full. Chỉ tạo dataset Full và báo cáo này, giữ nguyên các subset khác, neutral, metadata, Schema v1, planning, pipeline và local edits ngoài task.

Implementation là commit chứa hai deliverables; tra SHA bằng `git log -1 --format=%H -- ViFinBench/benchmark/numerical/full.jsonl`. SHA cụ thể và xác minh remote ghi trong bàn giao, không gán SHA baseline thành SHA Full.

## Phân bố và cách biên soạn

| Độ khó | Explicit | Implicit | Advanced | Tổng |
| --- | ---: | ---: | ---: | ---: |
| Easy | 20 | 40 | 0 | **60** |
| Medium | 14 | 58 | 28 | **100** |
| Hard | 0 | 0 | 40 | **40** |
| **Tổng** | **34** | **98** | **68** | **200** |

Explicit nêu phép tính/cách đối chiếu trực tiếp; Implicit yêu cầu xác định công thức hoặc suy ngược từ chỉ tiêu/mục tiêu tài chính; Advanced yêu cầu chọn toán hạng dễ nhầm, kết hợp báo cáo/kỳ hoặc tổ chức các bước phân tích. Advanced có thể chứa giả định/cách tính để tránh mơ hồ; nhãn này không đồng nghĩa câu hỏi hoàn toàn không gợi ý. Kiểu yêu cầu không phải độ khó: chọn thuế hoãn lại đúng dấu có thể là Medium/Advanced, còn tổng hợp dòng tiền hai kỳ là Hard/Advanced.

Easy dùng 20 đại lượng tài chính khác nhau, mỗi đại lượng có ba mục tiêu: chênh lệch tiền, biến động phần trăm, hệ số so kỳ gốc. Medium gồm các chỉ số, tác động của việc dùng số dư cuối kỳ thay bình quân, và bài toán suy ngược nhu cầu vốn/chi phí/doanh thu. Hard gồm phân tích thay đổi, nguồn tiền tự tài trợ, thu hồi phải thu, phân rã tác động lợi nhuận và CAGR. Không dùng DuPont dài nhưng rút gọn được để tạo Hard.

Có **96 nhãn mục tiêu tính toán**, mỗi nhãn tối đa **4 QA**; đây là nhãn bài toán, không phải 96 công thức đại số độc lập. Đã thay các trường hợp hỏi lại cùng chỉ tiêu/doanh nghiệp/kỳ qua cột so sánh ở tài liệu khác; chuyển riêng các câu quá giống nhau sang khoảng thiếu hụt, suy ngược mục tiêu hoặc tác động của lựa chọn số dư. Một số chỉ số cơ bản vẫn lặp ở 2–3 tình huống nguồn để có coverage, không chỉ dựa vào thay cách diễn đạt.

Không tạo lại các bài Pilot bằng cách đổi doanh nghiệp/năm: chẳng hạn Full dùng ROE thay bài ROA Pilot; hệ số tiền mặt thay hiện hành/nhanh; DSO mục tiêu để tính vốn giải phóng thay tính CCC; tổng hợp khả năng tự tài trợ hai kỳ thay chênh lệch FCF Pilot. Các thành phần tài chính có thể giao nhau nhưng mục tiêu trả lời khác nhau.

## Nhóm phép tính chính

Các nhóm dưới đây không chồng lấn; mỗi nhóm bao gồm cả chỉ số và bài toán suy ngược/đối chiếu tương ứng.

| Nhóm | Số QA | Nội dung tiêu biểu |
| --- | ---: | --- |
| Số học hai kỳ | 60 | Giá vốn, lợi nhuận gộp, chi phí, công nợ, nợ vay, thuế tiền mặt, cổ tức, chi đầu tư, dự phòng |
| Sinh lời và hiệu quả sử dụng tài sản | 28 | ROE, vòng quay tổng tài sản/tồn kho/TSCĐ, DSO/DIO/DPO, số dư bình quân và sai lệch khi dùng cuối kỳ |
| Thanh khoản và cơ cấu tài trợ/tài sản | 32 | Tiền mặt/nợ ngắn hạn, nợ/vốn chủ sở hữu, vốn thường xuyên, nợ vay ròng, cơ cấu kỳ hạn, phải thu và hao mòn TSCĐ |
| Lãi vay, biên EBIT, thuế và chi phí | 16 | Bảo đảm lãi vay, thuế suất hiệu dụng, EBIT ước tính, chi phí vận hành trên lợi nhuận gộp và mục tiêu liên quan |
| Dòng tiền và phân bổ vốn | 24 | Biên CFO, trang trải lãi tiền mặt, CFO/nợ bình quân, cổ tức, chi đầu tư/tài sản và tiền sau đầu tư |
| Thay đổi biên và tác động đến lợi nhuận/doanh thu | 12 | Điểm phần trăm so với tăng trưởng tương đối, tác động quy mô/biên ròng, doanh thu bù chi phí |
| Phân tích nhiều bước về tiền và thời điểm ghi nhận | 24 | Đóng góp vốn lưu động vào CFO, tự tài trợ/thiếu hụt tiền, trả nợ, DSO mục tiêu, hai kỳ cổ tức và thuế dồn tích so thực nộp |
| CAGR nhiều tài liệu | 4 | Doanh thu hợp nhất qua 2 hoặc 3 khoảng tăng trưởng năm |
| **Tổng** | **200** | |

Các mục tiêu 10% ROE, 20% thuế đối chiếu, 30 ngày DSO, cơ cấu nợ 50/50… là **giả định phân tích được nêu trong câu hỏi**, không phải dữ kiện quan sát, chuẩn bắt buộc hay kết luận pháp lý. Toán hạng tài chính vẫn lấy từ neutral. Không suy giả định này thành hiệu quả kinh doanh thực tế.

## Bao phủ nguồn

- **15 doanh nghiệp / 40 tài liệu**. Năm báo cáo: **2021: 3; 2022: 3; 2023: 10; 2024: 10; 2025: 14**. Các cột so sánh còn cung cấp kỳ 2020. Mỗi tài liệu được dẫn trong 4–7 QA, tính cả nguồn ở hai đầu CAGR; không yêu cầu chia đều theo doanh nghiệp.
- Doanh nghiệp: ADC, ALT, AMC, AME, ARM, ATS, BBS, BCC, BED, BKC, BPC, BTS, BTW, C69, CAG. Không dùng BCC_2025 vì export chỉ có công văn, không có bộ báo cáo chính cần cho bài toán.
- **200/200 QA có toán hạng từ B01/B02/B03**. Đếm QA theo báo cáo có thể chồng: **B01: 103; B02: 108; B03: 57; B09: 0**. B09 không cung cấp toán hạng tài chính.
- **60 QA** có `unit_evidence` phụ; trong đó **28 QA** dùng đoạn chính sách đơn vị tiền tệ ở B09, các câu còn lại dẫn đơn vị tại báo cáo chính khác cùng tài liệu. Nếu tính cả nguồn đơn vị thì có **28 QA dẫn B09**, tách rõ khỏi số QA có toán hạng B09.
- **576 toán hạng/tham chiếu ô**, có **122 toán hạng âm** và **13 toán hạng ở cột ghi rõ điều chỉnh/trình bày lại**. Không đổi dấu tiền chi thành thu; chỉ dùng độ lớn khi công thức yêu cầu. Không coi ô trống/dấu gạch là số 0.
- Bốn câu CAGR nối hai tài liệu hợp nhất cùng doanh nghiệp, cùng scope đã xác minh. Các câu còn lại dùng một tài liệu, kể cả kỳ so sánh, để hạn chế ghép nhầm số liệu được điều chỉnh. Với scope `unknown`, câu hỏi không tự gọi là báo cáo riêng/hợp nhất.

## Một số ví dụ

| ID | Mức | Bài toán | Gold | Nguồn neutral |
| --- | --- | --- | --- | --- |
| 0016 | Easy | Chênh lệch giá vốn ADC 2021 so với 2020 | **-59.052.449.851 VND** | ADC_2021, trang 11 |
| 0077 | Medium | ROE Khoáng sản Á Châu 2025, dùng vốn bình quân | **11,93%** | AMC_2025, trang 8–9 |
| 0078 | Medium | Sai lệch ROE ARM 2024 khi dùng vốn cuối kỳ thay bình quân | **-0,19 điểm phần trăm** | ARM_2024, trang 8–9 |
| 0079 | Medium | LNST cần tăng thêm để BBS đạt ROE mục tiêu 10% | **3.588.955.557 VND** | BBS_2025, trang 6–7 |
| 0184 | Hard | Phần thay đổi tác động tiền của ba khoản vốn lưu động đóng góp vào biến động CFO ADC 2025 | **73,06%** | ADC_2025, trang 13 |
| 0194 | Hard | CFO sau giả định giải phóng phải thu về DSO 30 ngày, đối chiếu chi đầu tư tài sản | **274,13%** | ADC_2025, trang 10, 12–13 |
| 0198 | Hard | Tác động riêng của tăng doanh thu ADC 2023 đến LNST nếu giữ biên ròng 2022 | **1.389.515.130 VND** | ADC_2023, trang 11 |
| 0204 | Hard | Hai kỳ CFO sau chi đầu tư có bao phủ tổng cổ tức BCC 2022–2023 không, thể hiện bằng tỷ số có dấu | **-1,31 lần** | BCC_2023, trang 14 |
| 0212 | Hard | CAGR doanh thu hợp nhất ALT 2023–2025, đúng hai khoảng năm | **18,47%/năm** | ALT_2023 và ALT_2025, trang 10 |

Công thức, toán hạng chuẩn hóa, table ID, hàng, cột và quote đầy đủ nằm trong JSONL; báo cáo không chép lại 200 bản ghi. Ví dụ 0184 lấy các tác động tiền có dấu trên B03, không lấy chênh lệch số dư B01; 0198 giữ biên năm gốc và chỉ đo hiệu ứng quy mô; 0204 âm là thiếu dòng tiền sau đầu tư, không phải trả được “âm số lần” cổ tức.

## Schema và quy ước tính

Giữ nguyên cấu trúc Numerical Pilot: `answer` số chuẩn dạng string; Evidence chính là object, `supporting_evidence` là mảng; `E1` là nguồn chính, `E2` trở đi theo thứ tự bằng chứng hỗ trợ. Mỗi toán hạng lưu tên, giá trị, đơn vị và evidence reference. Giữ `formula.expression`, `formula.rounding`, `reasoning`, `tags`, `input_documents`; không thêm trường quản lý/review hay tolerance vào QA. Nhãn Explicit/Implicit/Advanced được thống kê theo việc review biên soạn, không thêm vào schema chung.

- Tính bằng **Decimal, precision 50**, không float và không làm tròn trung gian. `ROUND_HALF_UP` ở kết quả cuối; tiền làm tròn đến VND khi câu hỏi yêu cầu, tỷ lệ/hệ số/ngày dùng 2 chữ số thập phân. Các toán hạng tiền đều giữ **VND**, đúng đơn vị của vùng nguồn đã chọn.
- Giữ unit Pilot: `vnd`, `percent`, `ratio`, `day`, `percentage_point`. Không đổi phần trăm thành điểm phần trăm. `key_points: []`, không bắt mô hình viết giống reasoning/display.
- Biểu thức dùng các toán tử hiện có và thêm **`**`** cho CAGR, với số khoảng năm là hằng số xác định trong câu hỏi. Tính lũy thừa bằng Decimal; kiểm lại CAGR bằng logarithm/exponential Decimal. Không thêm parser hay evaluator.
- Tồn kho dùng giá trị thuần; DSO/DPO dùng công nợ thương mại ngắn hạn và các đại diện doanh thu/giá vốn đã nêu. Các chỉ số bình quân dùng đầu/cuối kỳ; không tự lấy trung bình nhiều mốc không được yêu cầu. Quy ước EBIT, tiền sau đầu tư và các mục tiêu giả định được ghi ngắn gọn ở câu hỏi để Gold xác định.

## Focused validation

**PASS local** cho bản bàn giao:

1. UTF-8 JSONL đúng 200 dòng không trống; ID duy nhất, liên tục 0016–0215; 60/100/40; 215 Numerical QA khi cộng Pilot. Schema, decimal string, đơn vị, dấu và E1…En hợp lệ; không float.
2. **576/576 toán hạng khớp ô neutral**. Đối chiếu table ID/trang, hàng/cột thật, giá trị, quote header/toàn hàng trong Markdown, table reference trong TXT và nguồn đơn vị phụ. Kiểm kỳ theo header hiện tại/so sánh, mốc đầu/cuối năm, cột điều chỉnh và scope metadata. Bỏ ứng viên không rõ hoặc mâu thuẫn, không sửa nguồn hay lấp ô trống.
3. **200/200 Gold tính lại đúng bằng Decimal** theo bài toán tương ứng, không làm tròn trung gian. Đối chiếu công thức với mục tiêu câu hỏi; kiểm dấu khoản chi, số dư bình quân, chênh lệch tương đối/điểm phần trăm và số khoảng CAGR. Các thay đổi câu chữ cuối không thay toán hạng, công thức hoặc đáp án.
4. Không trùng ID/câu hỏi với Pilot hoặc subset khác; không có cặp cùng mục tiêu/chỉ tiêu, doanh nghiệp và kỳ bị hỏi lại qua hai export. Rà mục tiêu so với Pilot và các nhóm lặp trong Full; đổi riêng trường hợp quá giống sang bài toán khác. Với đáp án tiền, kiểm tra không xuất hiện trực tiếp trong các hàng bảng Markdown của tài liệu tương ứng.
5. **131 file neutral/benchmark có trước task giữ nguyên SHA-256**, gồm Numerical Pilot, Single-hop/Multi-hop, metadata và Schema. Git chỉ stage/commit hai deliverables. `git diff --check` và staged diff không có lỗi whitespace; local edits ngoài task được giữ nguyên.

Các phép tính/kiểm tra dùng script tạm ngoài repository; không thêm framework, bộ test, parser hay evaluator vào dự án. Không chạy full CI, model benchmark, LLM Judge, Gemini/Qwen, OCR hoặc đối chiếu PDF/PNG. PASS ở đây xác nhận tính toán và provenance **trong neutral**, không chứng nhận độ đúng OCR/PDF hoặc chất lượng mô hình tài chính.

## Hạn chế và bước tiếp theo

- Gold được biên soạn và tự kiểm, chưa có người thứ hai đối chiếu PDF. Nhãn khó/kiểu yêu cầu chưa hiệu chuẩn bằng kết quả mô hình; một số dạng số học và chỉ số vẫn có mô thức lặp được giới hạn.
- Có tài liệu scope `unknown`; không suy thêm loại báo cáo. C69 partial thiếu trang 30; chỉ dùng những trang và bảng thực sự hiện diện, không suy dữ liệu trang thiếu hoặc chất lượng toàn tài liệu từ các vùng đã chọn.
- Các câu được chọn có đơn vị VND; chưa bao phủ chuyển đổi nghìn/triệu đồng. CAGR chỉ có hai doanh nghiệp hợp nhất ALT/BCC, dùng các cửa sổ 2–3 năm; không điều chỉnh tăng trưởng hữu cơ hay thay đổi phạm vi kinh tế ngoài thông tin nguồn.
- DSO/DPO và các tình huống giải phóng vốn là ước tính theo đại diện và giả định trong câu hỏi, không phải thời gian thu/trả hoặc dự báo dòng tiền đã được xác nhận. Những tỷ lệ tiền âm hoặc vượt 100% cần giữ đúng dấu, không diễn giải thành khả năng chi trả thực tế dương. Chưa triển khai tolerance/evaluator.

**Next action duy nhất:** Tech Lead review và nghiệm thu ViFinBench-NR-FULL; không tự bắt đầu subset tiếp theo.
