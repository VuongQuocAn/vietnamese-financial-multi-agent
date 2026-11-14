# ViFinBench-P1B-Refine — Cải thiện 15 Multi-hop QA Pilot

Ngày thực hiện: **14/11/2026** (Asia/Bangkok). Trạng thái: **REVIEW** — chờ Tech Lead nghiệm thu. Baseline đã review: `de399ab9f2a1f6de39ae598ca6f94b369cdd73b0` ([Pilot cũ](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/blob/de399ab9f2a1f6de39ae598ca6f94b369cdd73b0/ViFinBench/benchmark/multi_hop/pilot.jsonl)). Gold dựa trên neutral và tự kiểm biên soạn, chưa phải human gold độc lập từ PDF.

## 1. Kết quả Refine

**15 QA: 3 KEEP / 5 REWRITE / 7 REPLACE; 5 Easy / 7 Medium / 3 Hard.** Giữ ID `VFB-MH-0001`–`VFB-MH-0015`. Có **8 QA suy luận phụ thuộc**, **3 QA bảng–văn bản**, **2 QA cross-document**; còn **2 câu hỏi nhị phân** (0003, 0008). 0014 là câu chọn năm với đáp án tập rỗng đã chứng minh, không gộp vào nhãn Có/Không hoặc Unanswerable. Hai câu nhị phân giữ vì đo hai kết hợp tài chính có ý nghĩa; không chỉ đổi cách diễn đạt để làm đẹp thống kê.

**11 doanh nghiệp / 13 tài liệu, 35 Evidence chính.** 10/15 QA dẫn B01/B02/B03 (0001–0004, 0006–0009, 0012, 0014); 3 trong số đó nối B01 với B09 (0001, 0002, 0009). Năm mẫu còn lại dùng các vùng thuyết minh để xây cầu nối thực thể/điều khoản. Tỷ lệ báo cáo chính giảm so với Pilot cũ vì ưu tiên chuỗi suy luận thực, không vì né OCR; brief Refine không đặt quota cứng. 3 mẫu kết hợp bảng–văn bản là 0005, 0009, 0015; nguồn đơn vị phụ không được tính là hop văn bản.

Chỉ cập nhật [pilot.jsonl](../ViFinBench/benchmark/multi_hop/pilot.jsonl) và báo cáo này. Giữ nguyên Single-hop, corpus, metadata, Schema v1, planning và local edits ngoài task. Không mở Full Multi-hop/Numerical, không API/OCR/model benchmark/full CI. Lịch sử Pilot trước Refine được giữ tại commit baseline, không tạo bản sao dataset thứ ba.

Implementation Refine là commit chứa hai file này; tra bằng `git log -1 --format=%H -- ViFinBench/benchmark/multi_hop/pilot.jsonl`. SHA cụ thể và remote verification ghi trong bàn giao, không gán SHA baseline thành SHA implementation.

## 2. Đối chiếu từng QA cũ và mới

KEEP nghĩa là giữ nguyên các trường nội dung QA cũ; chỉ thêm hai trường yêu cầu nguồn cho nhất quán. REWRITE giữ ý tưởng cốt lõi, đổi mục tiêu trả lời/reasoning; REPLACE đổi bài toán. Không đặt quota hành động trước khi review.

| ID cuối | Quyết định | Nội dung cũ | Nội dung sau Refine | Lý do |
| --- | --- | --- | --- | --- |
| 0001 | REPLACE | Doanh thu năm lớn hơn tổng tài sản cuối năm? | Khoản mục vốn lưu động → khách hàng lớn nhất | Bỏ phép so dòng phát sinh với số dư; chuyển sang xác định vùng chiếm dụng vốn rồi tìm đối tượng trong thuyết minh. |
| 0002 | REPLACE | Tồn kho cuối năm có vượt giá vốn cả năm? | Dự phòng lớn hơn → cổ phiếu chịu dự phòng | Bỏ so tồn kho với giá vốn; truy từ khoản dự phòng lớn hơn đến chứng khoán liên quan. |
| 0003 | KEEP | Dấu lợi nhuận sau thuế và CFO | Lãi kế toán dương nhưng CFO âm | Đối chiếu lợi nhuận với dòng tiền có ý nghĩa thực tế, không yêu cầu phép tính; giữ một câu nhị phân cơ bản. |
| 0004 | REWRITE | Tiền thu bán hàng có lớn hơn doanh thu thuần? | Đối chiếu doanh thu ghi nhận và khoản thực thu | Giữ phép đối chiếu có ý nghĩa; yêu cầu mô tả hai cơ sở đo và số liệu thay vì trả lời Có/Không. |
| 0005 | REPLACE | Tiền vay nhận trong năm so với dư nợ cuối năm | Ngân hàng dư nợ lớn nhất → hạn mức và thời hạn | Bỏ so số phát sinh với số dư; dùng dư nợ để chọn hợp đồng cần đọc. |
| 0006 | REWRITE | Doanh thu và tài sản có cùng chiều biến động? | Tổng hợp hai chiều biến động doanh thu và tài sản | Giữ nội dung so sánh quy mô, bỏ phép trừ và kết quả chênh lệch không cần thiết; mô tả quan hệ hai biến động. |
| 0007 | REWRITE | Chi phí thuế và thực nộp có bằng nhau; chênh bao nhiêu? | Phân biệt thuế ghi nhận và tiền thuế đã nộp | Bỏ yêu cầu tính chênh lệch; trọng tâm là phân biệt chỉ tiêu dồn tích và dòng tiền. |
| 0008 | KEEP | Phải thu khách hàng tăng và CFO dương | Điều kiện đồng thời về phải thu và CFO | Câu nhị phân này kiểm tra kết hợp biến động số dư và dấu CFO; cả hai điều kiện đều đúng nên mỗi nguồn đều cần. |
| 0009 | REPLACE | So tiền gửi đầu tư với tiền và tương đương tiền | Nhóm tiền lớn hơn → ký hiệu (*) → điều khoản tiền gửi | Chuyển sang chuỗi phân loại thanh khoản và tra chú thích thực tế, không chỉ so hai số tiền. |
| 0010 | REPLACE | Giao dịch DINCO có vượt ngưỡng tự đặt 5%? | Bên liên quan bán hàng lớn nhất → công nợ tương ứng | Bỏ ngưỡng chủ quan và tỷ lệ; chọn đối tác từ giao dịch rồi tìm số dư phải thu cùng đối tượng. |
| 0011 | REWRITE | Ngân hàng dư nợ lớn nhất và ngưỡng một nửa nợ ngắn hạn | Ngân hàng lớn nhất → quyền đòi nợ dùng bảo đảm | Giữ bước chọn ngân hàng, thay ngưỡng tỷ lệ bằng tra điều kiện bảo đảm của hợp đồng tương ứng. |
| 0012 | REWRITE | Tính mức giảm tổng nợ giữa 2021 và 2024 | Đối chiếu cơ cấu tài trợ cùng phạm vi qua hai năm | Giữ hai tài liệu hợp nhất, chuyển từ tính chênh lệch nợ sang nhận diện nguồn tài trợ chiếm phần lớn ở từng mốc. |
| 0013 | REPLACE | Tính và đối chiếu hai chênh lệch cổ tức | Ngân hàng tiền gửi lớn nhất → công ty con vay → quyền biểu quyết | Lời giải cũ chủ yếu là phép trừ; thay bằng chuỗi chuyển thực thể ngân hàng → đơn vị vay → cấu trúc tập đoàn. |
| 0014 | KEEP | Không năm nào có doanh thu và CFO trái chiều | Đối chiếu điều kiện qua hai báo cáo và cột trình bày lại | Cả bốn nguồn đều cần để chứng minh kết quả rỗng trong tập {2022, 2024}; trọng tâm là ghép chỉ tiêu và kỳ so sánh, không phải tính tăng trưởng. |
| 0015 | REPLACE | CFO so với thiếu hụt vốn lưu động ròng | Ngân hàng thứ hai về vay ngắn hạn → khoản vay dài hạn và mục đích/bảo đảm | Bỏ công thức thiếu hụt vốn lưu động; lần theo cùng ngân hàng qua cấu trúc kỳ hạn và hợp đồng dự án. |

## 3. Phân bố suy luận và ranh giới Numerical

| Dạng chính, không đếm chồng | Số QA | ID cuối |
| --- | ---: | --- |
| Bridge qua bảng | 5 | 0001, 0002, 0010, 0011, 0013 |
| Bridge bảng–văn bản | 3 | 0005, 0009, 0015 |
| Đối chiếu/tổng hợp báo cáo trong cùng tài liệu | 5 | 0003, 0004, 0006, 0007, 0008 |
| Đối chiếu liên kỳ qua nhiều tài liệu | 2 | 0012, 0014 |

Tổng 8 bridge có phụ thuộc nguồn thật: kết quả chọn khoản mục/thực thể/ký hiệu từ bước trước xác định bảng hoặc đoạn cần đọc tiếp. Không tính câu 0006/0012/0014 thành bridge chỉ vì có nhiều lần tra cứu. Các bridge vẫn có phép so giá trị để chọn đối tượng, nhưng đáp án cuối yêu cầu thông tin không có ở bảng tuyển chọn.

| Mẫu giao thoa được review | Quyết định về ranh giới |
| --- | --- |
| 0001, 0002, 0005 | Bỏ các so sánh stock–flow; thay bằng chọn đối tượng rồi tra nội dung phụ thuộc |
| 0006 | Bỏ hai phép trừ; giữ đối chiếu chiều doanh thu và tài sản |
| 0007 | Bỏ tính chênh lệch thuế; giữ phân biệt chi phí hiện hành và tiền thực nộp |
| 0008 | Giữ phép trừ phụ trợ để kiểm phải thu tăng; trọng tâm là ghép với dấu CFO |
| 0009 | Phép so chỉ chọn nhóm; đáp án nằm ở liên kết ký hiệu (*) với chú thích |
| 0010, 0011 | Bỏ ngưỡng 5%/một nửa do người biên soạn đặt; dùng liên kết đối tác/hợp đồng |
| 0012 | Bỏ mức giảm tổng nợ; đối chiếu nguồn tài trợ chiếm phần lớn ở hai mốc cùng phạm vi |
| 0013, 0015 | Thay hẳn hai bài toán chênh lệch bằng chuỗi ngân hàng → công ty con/quyền biểu quyết, ngân hàng → kỳ hạn/mục đích/bảo đảm |
| 0014 | Giữ: so chiều từng chỉ tiêu và kết hợp điều kiện theo từng kỳ so sánh; không yêu cầu tỷ lệ tăng trưởng |

Không có QA đòi tính tỷ lệ, tăng trưởng, vòng quay hoặc đối chiếu hai công thức làm năng lực chính. Phép so/xét dấu, xếp hạng và phép trừ phụ trợ ở 0008 vẫn thuộc lời giải Multi-hop. Không chuyển dữ liệu sang Numerical hoặc thêm evaluator.

## 4. Nguồn và schema riêng Multi-hop

Giữ mở rộng P1B: `task: multi_hop`, `evidence` là mảng Evidence v1, thêm `reasoning`. Refine bổ sung đúng hai key cấp item:

- `input_documents`: danh sách document ID duy nhất, theo lần xuất hiện đầu trong Evidence; gồm toàn bộ tài liệu thực sự cần cho lời giải.
- `setting`: `single_doc` nếu một document ID, `multi_doc` nếu nhiều ID.

Đây là yêu cầu nguồn của bài toán, không cam kết cung cấp nguyên tài liệu cho mô hình khi đánh giá. Chỉ áp dụng subset Multi-hop; không đổi Schema v1 chung/Single-hop. Không thêm evidence_id, role, operands, operation, result hoặc annotator_note. Ghi vai trò chứng cứ trong báo cáo để review, không mở rộng JSON thành framework.

Mỗi Evidence giữ tám key v1; văn bản dùng null cho table_id/row_label/column_header/row_path. Quote bảng giữ header và hàng nguyên văn; có thể trích chọn các hàng theo thứ tự. `row_path` chỉ theo nhóm thật. Số trang là trang neutral. Answer giữ v1: các mẫu hiện là text, số tiền/ngày/tỷ lệ nằm trong string, `unit: null`, có key_points đầy đủ. Không tạo số float hoặc mã đơn vị mới.

Đơn vị ưu tiên trong header/trang bảng. ARM 0005 có VND trong header; BTS 0015 dùng tuyên bố đơn vị **trình bày** tại trang 15; AME 0013 E2 dùng đơn vị VND của mục V bắt đầu tại trang 22 và tiếp tục đến thuyết minh vay 18 tại trang 29 (trước mục VI). Không dùng câu về tiền tệ ghi sổ để tự xác nhận đơn vị trình bày. E3 của 0013 là tỷ lệ quyền biểu quyết có dấu % ngay ô nguồn.

Tài liệu: `ADC_2025`, `AMC_2025`, `AME_2025`, `ARM_2025`, `BBS_2025`, `BCC_2021`, `BCC_2022`, `BCC_2024`, `BED_2025`, `BPC_2025`, `BTS_2025`, `BTW_2025`, `CAG_2025`.

Doanh nghiệp: ADC, AMC, AME, ARM, BBS, BCC, BED, BPC, BTS, BTW, CAG. Năm tài chính tài liệu: 2021, 2022, 2024, 2025; năm 2023 xuất hiện như kỳ so sánh. Hai mẫu multi_doc 0012/0014 chỉ nối BCC hợp nhất với BCC hợp nhất; không ghép phạm vi unknown với riêng/hợp nhất thành chuỗi liên kỳ.

## 5. Mẫu tiêu biểu cho Tech Lead

- **0013:** chọn Đông Nam Á – Long Biên từ bảng tiền gửi → tìm Alpec trong nhóm vay cùng chi nhánh → tra quyền biểu quyết 99,532% trong danh sách công ty con. Ba nguồn có ba chức năng và khóa nối thay đổi qua từng bước; không thể chỉ lấy số lớn nhất làm đáp án.
- **0009:** chọn nhóm tài sản trên B01 → tìm dòng có (*) trong thuyết minh tiền → đọc chú thích kỳ hạn gốc 03 tháng/lãi suất 4,2%. Dấu (*) phải được gắn đúng bảng, không dùng chú thích (*) của mục đầu tư kế tiếp.
- **0015:** chọn ngân hàng thứ hai về vay ngắn hạn → tra khoản vay dài hạn cùng ngân hàng và phần đến hạn → lấy mục đích tài trợ, tài sản bảo đảm trong diễn giải. Phải phân biệt tổng khoản vay với phần sau 12 tháng.
- **0014:** không có năm thỏa điều kiện là kết quả có căn cứ trong tập đóng {2022, 2024}; giữ đúng cột so sánh trình bày lại năm 2021 trong báo cáo 2022.

## 6. QA sau Refine: Gold, Evidence, reasoning

E1/E2… tương ứng thứ tự mảng Evidence trong JSONL. Mỗi mục ghi rõ vai trò và phép thử bỏ nguồn. Gold chấm theo toàn bộ key_points; chỉ nêu tên thực thể hoặc đáp Có/Không không đủ khi câu hỏi yêu cầu đặc điểm/quan hệ kèm theo.

### VFB-MH-0001 — easy — REPLACE

**Câu hỏi:** Cuối năm 2025 của Vicem Bao bì Bút Sơn, khoản phải thu ngắn hạn của khách hàng hay hàng tồn kho có số dư lớn hơn? Trong thuyết minh của khoản mục lớn hơn đó, đối tượng được nêu tên riêng có số dư lớn nhất là ai?

**Gold:** Phải thu ngắn hạn của khách hàng lớn hơn: 164.464.383.310 VND so với hàng tồn kho 50.788.605.600 VND. Trong các khách hàng được nêu tên riêng, Công ty TNHH MTV Xi măng Vicem Tam Điệp có số dư lớn nhất, 34.110.286.767 VND.

**Nguồn yêu cầu:** `single_doc`; `BBS_2025`.

**E1 — `BBS_2025_p005_t001`, trang 5; hàng “1. Phải thu ngắn hạn của khách hàng”, cột “31/12/2025”.** Chọn khoản mục để biết cần mở thuyết minh khách hàng thay vì tồn kho.

> Tại ngày 31 tháng 12 năm 2025
> Đơn vị tính: VND
> ### BẢNG CÂN ĐỐI KẾ TOÁN
> | CHỈ TIÊU | Mã số | Thuyết minh | 31/12/2025 | 01/01/2025 |
> | --- | --- | --- | --- | --- |
> | 1. Phải thu ngắn hạn của khách hàng | 131 | 6 | 164.464.383.310 | 192.724.114.055 |
> | III. Hàng tồn kho | 140 |  | 50.788.605.600 | 44.422.418.035 |

**E2 — `BBS_2025_p014_t002`, trang 14; hàng “Công ty TNHH MTV Xi măng Vicem Tam Điệp”, cột “31/12/2025 / VND”.** Chọn khách hàng định danh lớn nhất trong khoản mục đã xác định.

> | Chỉ tiêu | 31/12/2025 VND | 01/01/2025 VND |
> | --- | --- | --- |
> | Công ty Cổ phần Xi măng Vicem Bút Sơn | 32.822.068.156 | 46.824.574.989 |
> | Công ty Cổ phần Xi măng Hạ Long | 22.675.923.587 | 23.339.609.861 |
> | Công ty TNHH MTV Xi măng Vicem Tam Điệp | 34.110.286.767 | 27.645.137.090 |
> | Công ty Cổ phần Đầu tư Thành Thắng Group | 12.116.167.102 | 30.566.724.840 |
> | Công ty TNHH NĐ Minh Dương | 5.653.479.254 | 7.052.129.254 |
> | Công ty Cổ phần Thương mại NCL | 9.688.427.064 | 18.572.406.560 |
> | Công ty Cổ phần Xi măng Bỉm Sơn | 9.204.566.598 | 12.931.549.067 |
> | Các khách hàng khác | 38.193.464.782 | 25.791.982.394 |

**Reasoning tham chiếu:**

1. E1: 164.464.383.310 > 50.788.605.600 VND, nên chọn khoản phải thu khách hàng và lần theo thuyết minh 6.
2. E2: trong bảng phải thu khách hàng tại 31/12/2025, so các đối tượng được nêu tên riêng; Tam Điệp 34.110.286.767 VND lớn hơn Bút Sơn 32.822.068.156 VND và các khách hàng định danh còn lại.
3. Kết luận khoản mục là phải thu khách hàng, đối tượng là Xi măng Vicem Tam Điệp; loại nhóm gộp Các khách hàng khác khỏi tập khách hàng định danh.

**Bỏ nguồn:** Thiếu E1 không chứng minh khoản mục nào lớn hơn và vì sao chọn bảng khách hàng; thiếu E2 không biết đối tượng cuối cùng.

### VFB-MH-0002 — easy — REPLACE

**Câu hỏi:** Trong hai khoản dự phòng giảm giá chứng khoán kinh doanh và dự phòng phải thu ngắn hạn khó đòi cuối năm 2025 của Vicem Bao bì Bỉm Sơn, khoản có độ lớn cao hơn gắn với cổ phiếu của doanh nghiệp nào?

**Gold:** Khoản lớn hơn là dự phòng giảm giá chứng khoán kinh doanh, 2.016.000.000 VND, so với dự phòng phải thu khó đòi 765.440.000 VND. Khoản dự phòng chứng khoán gắn với cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai.

**Nguồn yêu cầu:** `single_doc`; `BPC_2025`.

**E1 — `BPC_2025_p005_t001`, trang 5; hàng “2. Dự phòng giảm giá chứng khoán kinh doanh”, cột “31/12/2025”.** So độ lớn hai khoản dự phòng để chọn đối tượng cần giải thích.

> Tại ngày 31 tháng 12 năm 2025
> Đơn vị tính: VND
> ### BẢNG CÂN ĐỐI KẾ TOÁN
> | CHỈ TIÊU | Mã số | Thuyết minh | 31/12/2025 | 01/01/2025 |
> | --- | --- | --- | --- | --- |
> | 2. Dự phòng giảm giá chứng khoán kinh doanh | 122 |  | (2.016.000.000) | (2.259.360.000) |
> | 3. Dự phòng phải thu ngắn hạn khó đòi | 137 | 7 | (765.440.000) | - |

**E2 — `BPC_2025_p014_t002`, trang 14; hàng “Cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai”, cột “Dự phòng (VND)”.** Nối khoản dự phòng được chọn với tên cổ phiếu.

> | Chỉ tiêu | Giá gốc (VND) | Giá trị hợp lý (VND) | Dự phòng (VND) |
> | --- | --- | --- | --- |
> | Cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai | 2.952.000.000 | 936.000.000 | (2.016.000.000) |

**Reasoning tham chiếu:**

1. E1: hai khoản đều ghi âm do là khoản điều chỉnh tài sản; so độ lớn 2.016.000.000 với 765.440.000 VND để chọn dự phòng chứng khoán.
2. E2: tra bảng chứng khoán kinh doanh tại 31/12/2025, dòng có dự phòng (2.016.000.000) VND gắn với cổ phiếu Xi măng Vicem Hoàng Mai.
3. Kết luận khoản dự phòng được chọn thuộc cổ phiếu Hoàng Mai, không phải một khoản nợ khách hàng.

**Bỏ nguồn:** E1 có cả hai loại dự phòng nhưng không có tên cổ phiếu; E2 có cổ phiếu nhưng không có khoản dự phòng phải thu để xác định khoản nào lớn hơn.

### VFB-MH-0003 — easy — KEEP

**Câu hỏi:** Năm 2025, lợi nhuận sau thuế và dòng tiền thuần từ hoạt động kinh doanh của Mĩ thuật và Truyền thông có cùng dấu không?

**Gold:** Không. Báo cáo riêng ghi lợi nhuận sau thuế năm 2025 dương 11.069.694.145 VND, nhưng dòng tiền thuần từ hoạt động kinh doanh âm 1.823.580.740 VND.

**Nguồn yêu cầu:** `single_doc`; `ADC_2025`.

**E1 — `ADC_2025_p012_t001`, trang 12; hàng “17. Lợi nhuận sau thuế thu nhập doanh nghiệp”, cột “Năm 2025 / VND”.** Xác định lợi nhuận sau thuế, không thay bằng lợi nhuận trước thuế.

> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH Năm 2025
> | Mã số | CHỈ TIÊU | Thuyết minh | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- | --- |
> | 60 | 17. Lợi nhuận sau thuế thu nhập doanh nghiệp |  | 11.069.694.145 | 13.961.942.478 |

**E2 — `ADC_2025_p013_t001`, trang 13; hàng “Lưu chuyển tiền thuần từ hoạt động kinh doanh”, cột “Năm 2025 / VND”.** Xác định dấu CFO.

> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ Năm 2025 (Theo phương pháp gián tiếp)
> | Mã số | CHỈ TIÊU | Thuyết minh | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- | --- |
> | 20 | Lưu chuyển tiền thuần từ hoạt động kinh doanh |  | (1.823.580.740) | 29.461.119.372 |

**Reasoning tham chiếu:**

1. E1: lấy lợi nhuận sau thuế năm 2025 từ B02: 11.069.694.145 VND > 0.
2. E2: B03 cùng năm trình bày CFO là (1.823.580.740) VND; ngoặc đơn biểu thị số âm.
3. Đối chiếu dấu: lợi nhuận sau thuế dương, CFO âm. Không kết luận doanh nghiệp thua lỗ từ CFO âm và không dùng lợi nhuận trước thuế trên B03 thay cho lợi nhuận sau thuế.

**Bỏ nguồn:** B02 không có CFO, B03 không có lợi nhuận sau thuế; cần cả hai để xác định quan hệ dấu.

### VFB-MH-0004 — easy — REWRITE

**Câu hỏi:** Đối chiếu doanh thu thuần với tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác của Khoáng sản Á Châu năm 2025: hai chỉ tiêu phản ánh những khoản nào và số thực thu nằm ở phía nào so với doanh thu thuần?

**Gold:** Doanh thu thuần bán hàng và cung cấp dịch vụ được ghi nhận là 169.865.621.961 VND; khoản tiền thực thu từ bán hàng, cung cấp dịch vụ và doanh thu khác là 177.385.494.652 VND, cao hơn doanh thu thuần. Khoản thu tiền có phạm vi tên chỉ tiêu bao gồm cả doanh thu khác.

**Nguồn yêu cầu:** `single_doc`; `AMC_2025`.

**E1 — `AMC_2025_p010_t001`, trang 10; hàng “1. Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác”, cột “Năm nay”.** Cho khoản thu tiền thực tế và tên phạm vi khoản thu.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
> Đơn vị: VND
> ### Báo cáo lưu chuyển tiền tệ
> | Chỉ tiêu | Mã số | Năm nay | Năm trước |
> | --- | --- | --- | --- |
> | 1. Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác | 01 | 177.385.494.652 | 164.337.752.205 |

**E2 — `AMC_2025_p009_t001`, trang 9; hàng “2. Doanh thu thuần về bán hàng và cung cấp dịch vụ”, cột “Năm nay”.** Cho doanh thu thuần ghi nhận trên kết quả kinh doanh.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
> | Mã số | CHỈ TIÊU | Thuyết minh | Năm nay | Năm trước |
> | --- | --- | --- | --- | --- |
> | 10 | 2. Doanh thu thuần về bán hàng và cung cấp dịch vụ | VI.1 | 169.865.621.961 | 159.789.927.069 |

Nguồn đơn vị cùng tài liệu, trang 12:

> Báo cáo tài chính kèm theo được trình bày bằng Đồng Việt Nam (VND), theo nguyên tắc giá gốc và phù hợp với Chuẩn mực kế toán, Chế độ kế toán doanh nghiệp Việt Nam và các quy định pháp lý có liên quan đến việc lập và trình bày Báo cáo tài chính. Báo cáo tài chính kèm theo không nhằm phản ánh tình hình tài chính, kết quả hoạt động kinh doanh và tình hình lưu chuyển tiền tệ theo các nguyên tắc và thông lệ kế toán được chấp nhận chung tại các nước khác ngoài Việt Nam.

**Reasoning tham chiếu:**

1. E1: B03 trực tiếp ghi khoản tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác năm 2025 là 177.385.494.652 VND.
2. E2: B02 ghi doanh thu thuần bán hàng và cung cấp dịch vụ năm 2025 là 169.865.621.961 VND.
3. Đối chiếu cho thấy khoản tiền thu cao hơn doanh thu thuần; giữ đầy đủ tên chỉ tiêu để phân biệt tiền thực thu với doanh thu ghi nhận.

**Bỏ nguồn:** Thiếu một nguồn không thể xác định quan hệ giữa tiền thực thu và doanh thu thuần.

### VFB-MH-0005 — easy — REPLACE

**Câu hỏi:** Khoản vay ngân hàng có dư nợ lớn nhất cuối năm 2025 của Xuất nhập khẩu Hàng không được cấp theo loại hạn mức nào và duy trì đến ngày nào?

**Gold:** Đó là khoản vay tại Ngân hàng TMCP Công thương Việt Nam – CN Tây Hà Nội, dư nợ 13.847.937.668 VND. Hợp đồng (1) cấp hạn mức thấu chi 30 tỷ VND, duy trì 12 tháng từ 31/7/2025 đến 31/7/2026.

**Nguồn yêu cầu:** `single_doc`; `ARM_2025`.

**E1 — `ARM_2025_p026_t001`, trang 26; hàng “Ngân hàng TMCP Công thương Việt Nam - CN Tây Hà Nội (1)”, cột “31/12/2025 (VND) Giá trị”.** Chọn ngân hàng theo dư nợ cuối năm và lấy ký hiệu hợp đồng (1).

> Cho năm tài chính kết thúc ngày 31/12/2025
> | Chỉ tiêu | 31/12/2025 (VND) Giá trị | 31/12/2025 (VND) Số có khả năng trả nợ | Trong năm (VND) Tăng | Trong năm (VND) Giảm | 01/01/2025 (VND) Giá trị | 01/01/2025 (VND) Số có khả năng trả nợ |
> | --- | --- | --- | --- | --- | --- | --- |
> | Ngân hàng TMCP Công thương Việt Nam - CN Tây Hà Nội (1) | 13.847.937.668 | 13.847.937.668 | 6.453.558.128 | 4.810.752.000 | 12.205.131.540 | 12.205.131.540 |
> | Ngân hàng TMCP Ngoại thương Việt Nam - CN Chương Dương | - | - | 1.150.837.200 | 18.874.170.063 | 17.723.332.863 | 17.723.332.863 |
> | Ngân hàng Nông nghiệp và Phát triển Nông thôn Việt Nam - CN Đống Đa (2) | 7.238.700.000 | 7.238.700.000 | 22.753.850.125 | 17.744.150.125 | 2.229.000.000 | 2.229.000.000 |

**E2 — `ARM_2025`, trang 26, văn bản.** Giải nghĩa hợp đồng đã chọn: loại hạn mức và thời gian duy trì.

> - (1) Hợp đồng cho vay số 01/2025-HDCVHMTC/NHCT146-AIRIMEX ngày 31/7/2025 giữa Ngân hàng TMCP Công thương Việt Nam - CN Tây Hà Nội và Công ty Cổ phần Xuất nhập khẩu Hàng không. Hạn mức thấu chi 30 tỷ VND. Mục đích sử dụng: Bổ sung vốn lưu động phục vụ hoạt động kinh doanh và ủy thác. Thời hạn duy trì hạn mức thấu chi: 12 tháng (từ ngày 31/7/2025 đến ngày 31/7/2026). Lãi suất: Được xác định theo thông báo tại ngày 25 hàng tháng. Lãi thấu chi trong ngày 6%/365 ngày đối với các khoản nợ phát sinh và được hoàn trả ngay trong ngày làm việc. Tài sản đảm bảo: Không có.

**Reasoning tham chiếu:**

1. E1: so dư nợ cuối năm tại các ngân hàng: Công thương Tây Hà Nội 13.847.937.668 VND lớn hơn Nông nghiệp Đống Đa 7.238.700.000 VND; dòng này mang ký hiệu (1).
2. Dùng ký hiệu (1) và tên chi nhánh để tìm đúng đoạn hợp đồng ở E2.
3. E2 ghi hạn mức thấu chi 30 tỷ VND, thời hạn duy trì 12 tháng, kết thúc 31/7/2026; đây là hạn mức, không phải dư nợ đã sử dụng.

**Bỏ nguồn:** Bảng dư nợ không có điều khoản; đoạn hợp đồng không cho biết ngân hàng nào có dư nợ cuối năm lớn nhất.

### VFB-MH-0006 — medium — REWRITE

**Câu hỏi:** Báo cáo riêng năm 2025 của Cấp nước Bến Thành cho thấy doanh thu thuần và tổng tài sản diễn biến như thế nào khi lần lượt đối chiếu với năm 2024 và thời điểm đầu năm 2025?

**Gold:** Doanh thu thuần giảm từ 561.464.712.365 VND năm 2024 xuống 550.869.711.512 VND năm 2025; tổng tài sản tăng từ 380.695.090.023 VND đầu năm lên 384.095.301.328 VND cuối năm 2025. Doanh thu giảm trong khi quy mô tài sản tăng.

**Nguồn yêu cầu:** `single_doc`; `BTW_2025`.

**E1 — `BTW_2025_p012_t001`, trang 12; hàng “Doanh thu thuần về bán hàng và cung cấp dịch vụ”, cột “Năm 2025 / VND”.** Xác định chiều doanh thu giữa hai năm.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Cho năm tài chính kết thúc ngày 31/12/2025
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
> | Chỉ tiêu | Mã số | Thuyết minh | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- | --- |
> | Doanh thu thuần về bán hàng và cung cấp dịch vụ | 10 |  | 550.869.711.512 | 561.464.712.365 |

**E2 — `BTW_2025_p010_t001`, trang 10; hàng “TỔNG TÀI SẢN”, cột “Tại 31/12/2025 VND”.** Xác định chiều số dư tài sản trong năm 2025.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Tại ngày 31 tháng 12 năm 2025
> ### BẢNG CÂN ĐỐI KẾ TOÁN
> | TÀI SẢN | Mã số | Thuyết minh | Tại 31/12/2025 VND | Tại 01/01/2025 VND |
> | --- | --- | --- | --- | --- |
> | TỔNG TÀI SẢN | 270 |  | 384.095.301.328 | 380.695.090.023 |

**Reasoning tham chiếu:**

1. E1: đối chiếu hai cột năm 2025 và 2024 trên B02: doanh thu thuần năm 2025 thấp hơn.
2. E2: đối chiếu hai cột 31/12/2025 và 01/01/2025 trên B01: tổng tài sản cuối năm cao hơn.
3. Tổng hợp: doanh thu giảm trong khi số dư tổng tài sản tăng.

**Bỏ nguồn:** Mỗi nguồn chỉ cho một chiều biến động; thiếu một nguồn không thể kết luận quan hệ hai chiều.

### VFB-MH-0007 — medium — REWRITE

**Câu hỏi:** Khi đối chiếu chi phí thuế TNDN hiện hành với thuế TNDN đã nộp năm 2025 của Cấp nước Bến Thành trong báo cáo riêng, khoản nào ghi nhận vào kết quả kinh doanh, khoản nào là tiền chi và quan hệ độ lớn của chúng ra sao?

**Gold:** Chi phí thuế TNDN hiện hành ghi nhận vào kết quả kinh doanh là 12.238.256.455 VND. Thuế TNDN đã nộp là dòng tiền ra 8.839.086.235 VND. Chi phí thuế hiện hành lớn hơn số tiền thuế đã nộp trong năm.

**Nguồn yêu cầu:** `single_doc`; `BTW_2025`.

**E1 — `BTW_2025_p012_t001`, trang 12; hàng “Chi phí thuế TNDN hiện hành”, cột “Năm 2025 / VND”.** Xác định đúng chi phí thuế hiện hành trên kết quả kinh doanh.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Cho năm tài chính kết thúc ngày 31/12/2025
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
> | Chỉ tiêu | Mã số | Thuyết minh | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- | --- |
> | Chi phí thuế TNDN hiện hành | 51 | 30 | 12.238.256.455 | 11.959.143.488 |

**E2 — `BTW_2025_p013_t001`, trang 13; hàng “Thuế thu nhập doanh nghiệp đã nộp”, cột “Năm 2025 / VND”.** Xác định đúng tiền chi nộp thuế, giữ dấu dòng tiền ra.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Cho năm tài chính kết thúc ngày 31/12/2025
> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ
> | Chỉ tiêu | Mã số | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- |
> | Thuế thu nhập doanh nghiệp đã nộp | 15 | (8.839.086.235) | (14.134.867.462) |

**Reasoning tham chiếu:**

1. E1: B02, mã 51, ghi chi phí thuế TNDN hiện hành năm 2025 là 12.238.256.455 VND.
2. E2: B03 ghi (8.839.086.235) VND ở dòng Thuế thu nhập doanh nghiệp đã nộp, tức tiền chi 8.839.086.235 VND.
3. Đối chiếu độ lớn tiền chi với chi phí: chi phí hiện hành cao hơn; hai khoản thuộc kết quả kinh doanh và lưu chuyển tiền khác nhau.

**Bỏ nguồn:** Không nguồn nào đơn lẻ có đủ cả chi phí hiện hành và tiền thực nộp để xác định quan hệ.

### VFB-MH-0008 — medium — KEEP

**Câu hỏi:** Trong năm 2025, Cảng An Giang có đồng thời ghi nhận phải thu ngắn hạn của khách hàng tăng từ đầu đến cuối năm và dòng tiền thuần từ hoạt động kinh doanh dương không?

**Gold:** Có. Phải thu ngắn hạn của khách hàng tăng từ 10.495.861.227 VND lên 14.029.472.134 VND, đồng thời CFO năm 2025 dương 2.945.594.773 VND.

**Nguồn yêu cầu:** `single_doc`; `CAG_2025`.

**E1 — `CAG_2025_p006_t001`, trang 6; hàng “1. Phải thu ngắn hạn của khách hàng”, cột “Số cuối năm”.** Kiểm biến động đúng khoản phải thu khách hàng.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
> Tại ngày 31 tháng 12 năm 2025
> Đơn vị tính: VND
> ### Bảng cân đối kế toán
> | CHỈ TIÊU | Mã số | Thuyết minh | Số cuối năm | Số đầu năm |
> | --- | --- | --- | --- | --- |
> | 1. Phải thu ngắn hạn của khách hàng | 131 | V.3 | 14.029.472.134 | 10.495.861.227 |

**E2 — `CAG_2025_p011_t001`, trang 11; hàng “Lưu chuyển tiền thuần từ hoạt động kinh doanh”, cột “Năm nay”.** Kiểm dấu CFO cả năm.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
> Đơn vị tính: VND
> ### Lưu chuyển tiền tệ từ hoạt động kinh doanh
> | CHỈ TIÊU | Mã số | Thuyết minh | Năm nay | Năm trước |
> | --- | --- | --- | --- | --- |
> | Lưu chuyển tiền thuần từ hoạt động kinh doanh | 20 |  | 2.945.594.773 | (726.857.705) |

**Reasoning tham chiếu:**

1. E1: phải thu ngắn hạn của khách hàng cuối năm 2025 là 14.029.472.134 VND, đầu năm là 10.495.861.227 VND. Tính 14.029.472.134 - 10.495.861.227 = 3.533.610.907 VND > 0.
2. E2: lấy CFO năm nay (2025) trên B03 là 2.945.594.773 VND > 0.
3. Điều kiện phải thu khách hàng tăng và CFO dương cùng được thỏa mãn. Không đồng nhất riêng khoản phải thu khách hàng với toàn bộ các khoản phải thu điều chỉnh trong CFO và không suy quan hệ nhân quả.

**Bỏ nguồn:** Thiếu nguồn nào cũng không xác nhận được cả hai điều kiện đồng thời; B03 không thay thế số dư riêng phải thu khách hàng.

### VFB-MH-0009 — medium — REPLACE

**Câu hỏi:** Cuối năm 2025, hãy chọn nhóm có số dư lớn hơn giữa tiền và các khoản tương đương tiền với đầu tư nắm giữ đến ngày đáo hạn ngắn hạn của Cấp nước Bến Thành. Khoản tiền gửi được đánh dấu (*) trong nhóm đó có kỳ hạn gốc và lãi suất thế nào?

**Gold:** Nhóm lớn hơn là tiền và các khoản tương đương tiền, 60.718.713.521 VND, so với đầu tư nắm giữ đến ngày đáo hạn ngắn hạn 51.100.000.000 VND. Dòng được đánh dấu (*) là các khoản tương đương tiền 5.000.000.000 VND; đó là tiền gửi có kỳ hạn gốc 03 tháng, lãi suất 4,2%/năm.

**Nguồn yêu cầu:** `single_doc`; `BTW_2025`.

**E1 — `BTW_2025_p010_t001`, trang 10; hàng “Tiền và các khoản tương đương tiền”, cột “Tại 31/12/2025 VND”.** Chọn nhóm tài sản và số thuyết minh cần tra.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Tại ngày 31 tháng 12 năm 2025
> ### BẢNG CÂN ĐỐI KẾ TOÁN
> | TÀI SẢN | Mã số | Thuyết minh | Tại 31/12/2025 VND | Tại 01/01/2025 VND |
> | --- | --- | --- | --- | --- |
> | Tiền và các khoản tương đương tiền | 110 | 5 | 60.718.713.521 | 85.407.192.689 |
> | Đầu tư nắm giữ đến ngày đáo hạn | 123 |  | 51.100.000.000 | 46.100.000.000 |

**E2 — `BTW_2025_p022_t001`, trang 22; hàng “Các khoản tương đương tiền (*)”, cột “Tại 31/12/2025 / VND”.** Nối nhóm đã chọn với khoản mang ký hiệu (*).

> Cho năm tài chính kết thúc ngày 31/12/2025
> ### 5. TIỀN VÀ CÁC KHOẢN TƯƠNG ĐƯƠNG TIỀN
> |  | Tại 31/12/2025 VND | Tại 01/01/2025 VND |
> | --- | --- | --- |
> | Các khoản tương đương tiền (*) | 5.000.000.000 | 5.000.000.000 |

**E3 — `BTW_2025`, trang 22, văn bản.** Giải thích kỳ hạn gốc và lãi suất của ký hiệu (*).

> (*) Là khoản tiền gửi có kỳ hạn gốc 03 tháng tại Ngân hàng Thương mại Cổ phần với lãi suất là 4,2%/năm.

**Reasoning tham chiếu:**

1. E1: 60.718.713.521 > 51.100.000.000 VND, nên chọn nhóm tiền và các khoản tương đương tiền và mở thuyết minh 5.
2. E2: trong nhóm đã chọn, dòng Các khoản tương đương tiền (*) có số dư 5.000.000.000 VND; dùng dấu (*) để nối sang chú thích.
3. E3: chú thích định nghĩa đúng khoản này là tiền gửi kỳ hạn gốc 03 tháng, lãi suất 4,2%/năm.

**Bỏ nguồn:** E1 xác định nhóm lớn hơn; E2 xác định (*) thuộc khoản nào và số dư; E3 mới có kỳ hạn/lãi suất. Không nguồn riêng lẻ có đủ cả ba phần.

### VFB-MH-0010 — medium — REPLACE

**Câu hỏi:** Bên liên quan có giá trị giao dịch bán hàng và cung cấp dịch vụ lớn nhất năm 2025 của Sách và Thiết bị trường học Đà Nẵng là bên nào, và khoản phải thu khách hàng tương ứng còn bao nhiêu tại 31/12/2025?

**Gold:** Đó là Công ty CP Kỹ thuật Xây dựng DINCO, với giá trị bán hàng và cung cấp dịch vụ 1.471.601.409 VND, lớn hơn Go-Working 62.157.518 VND. Khoản phải thu ngắn hạn của khách hàng đối với DINCO tại 31/12/2025 là 45.206.064 VND.

**Nguồn yêu cầu:** `single_doc`; `BED_2025`.

**E1 — `BED_2025_p038_t003`, trang 38; hàng “Công ty CP Kỹ thuật Xây dựng DINCO”, cột “Năm 2025 (VND)”.** Chọn đúng đối tác theo giao dịch bán hàng, không theo giao dịch mua hàng.

> ### Giao dịch với các bên liên quan
> | Chỉ tiêu | Năm 2025 (VND) | Năm 2024 (VND) |
> | --- | --- | --- |
> | Bán hàng và cung cấp dịch vụ |  |  |
> | Công ty CP Kỹ thuật Xây dựng DINCO | 1.471.601.409 | 1.534.648.691 |
> | Công ty TNHH Go-Working | 62.157.518 | 869.233.475 |

**E2 — `BED_2025_p038_t002`, trang 38; hàng “Công ty CP Kỹ thuật Xây dựng DINCO”, cột “Tại ngày 31/12/2025 (VND)”.** Tra số dư phải thu cuối năm của đối tác vừa chọn.

> ### Số dư phải thu (phải trả) với các bên liên quan
> | Chỉ tiêu | Tại ngày 31/12/2025 (VND) | Tại ngày 01/01/2025 (VND) |
> | --- | --- | --- |
> | Phải thu ngắn hạn của khách hàng |  |  |
> | Công ty CP Kỹ thuật Xây dựng DINCO | 45.206.064 | 2.222.657.408 |

**Reasoning tham chiếu:**

1. E1: chỉ xét nhóm Bán hàng và cung cấp dịch vụ với bên liên quan: DINCO 1.471.601.409 VND lớn hơn Go-Working 62.157.518 VND.
2. Dùng tên DINCO để tra cùng đối tượng trong bảng số dư, chọn nhóm Phải thu ngắn hạn của khách hàng ở E2.
3. E2: số dư DINCO tại 31/12/2025 là 45.206.064 VND. Kết luận ghép giao dịch cả năm với số dư cuối năm của đúng đối tác.

**Bỏ nguồn:** E1 không cho công nợ cuối năm; E2 không cho xếp hạng giao dịch bán hàng. Không suy số tiền đã thu bằng cách lấy doanh thu trừ công nợ.

### VFB-MH-0011 — medium — REWRITE

**Câu hỏi:** Với ngân hàng có dư nợ lớn nhất cuối năm 2025 của Vicem Bao bì Bút Sơn, hợp đồng cấp tín dụng tương ứng nhận bảo đảm bằng quyền đòi nợ phát sinh từ các hợp đồng mua bán với doanh nghiệp nào?

**Gold:** Ngân hàng có dư nợ lớn nhất là Ngân hàng TMCP Ngoại thương Việt Nam – Chi nhánh Nam Định, 42.405.101.215 VND. Hợp đồng số 01/2025/VCB.NDI/7189524/CTD ngày 16/06/2025 nhận bảo đảm, trong đó có quyền đòi nợ phát sinh từ hợp đồng với Công ty Cổ phần Xi măng Vicem Hoàng Mai về mua bán vỏ bao xi măng, bao Sling Jumbo.

**Nguồn yêu cầu:** `single_doc`; `BBS_2025`.

**E1 — `BBS_2025_p018_t001`, trang 18; hàng “Ngân hàng TMCP Ngoại thương Việt Nam”, cột “31/12/2025 - Giá trị (VND)”.** Chọn ngân hàng theo dư nợ thực tế và ký hiệu chi nhánh.

> ### 13. VAY VÀ NỢ THUÊ TÀI CHÍNH
> | Chỉ tiêu | 01/01/2025 - Giá trị (VND) | 01/01/2025 - Số có khả năng trả nợ (VND) | Trong năm - Tăng (VND) | Trong năm - Giảm (VND) | 31/12/2025 - Giá trị (VND) | 31/12/2025 - Số có khả năng trả nợ (VND) |
> | --- | --- | --- | --- | --- | --- | --- |
> | Ngân hàng TNHH MTV Shinhan Việt Nam | 5.000.000.000 | 5.000.000.000 | - | 5.000.000.000 | - | - |
> | Ngân hàng TMCP Đầu tư và Phát triển Việt Nam | 19.605.091.014 | 19.605.091.014 | 84.123.721.290 | 73.765.951.362 | 29.962.860.942 | 29.962.860.942 |
> | - Chi nhánh Nam Định (1) |  |  |  |  |  |  |
> | Ngân hàng TMCP Ngoại thương Việt Nam | 30.256.123.298 | 30.256.123.298 | 138.900.855.155 | 126.751.877.238 | 42.405.101.215 | 42.405.101.215 |
> | - Chi nhánh Nam Định (2) |  |  |  |  |  |  |
> | Ngân hàng TMCP Công thương Việt Nam | 52.474.409.144 | 52.474.409.144 | 189.565.588.735 | 206.511.204.752 | 35.528.793.127 | 35.528.793.127 |
> | - Chi nhánh Nam Định (3) |  |  |  |  |  |  |

**E2 — `BBS_2025_p019_t001`, trang 19; hàng “(2) Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Nam Định”, cột “Tài sản đảm bảo”.** Lấy đúng quyền đòi nợ trong danh sách bảo đảm của ngân hàng đã chọn.

> ### Chi tiết các khoản vay ngắn hạn của Công ty tại ngày 31/12/2025
> | Ngân hàng | Hợp đồng | Hạn mức (VND) | Thời hạn và mục đích vay | Tài sản đảm bảo |
> | --- | --- | --- | --- | --- |
> | (2) Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Nam Định | Hợp đồng cấp tín dụng số 01/2025/VCB.NDI/7189524/CTD, ngày 16/06/2025 | 50.000.000.000 | Thời gian cấp hạn mức tín dụng 13 tháng kể từ ngày 30/05/2025 nhưng không quá 12 tháng kể từ ngày 16/06/2025; Mục đích: bổ sung vốn lưu động, bảo lãnh, mở L/C | Tài sản đảm bảo bao gồm: 01 máy tráng màng PP hiệu Starlinger xuất xứ Châu Âu; Toàn bộ máy móc thiết bị hình thành từ vốn vay và vốn tự có theo hợp đồng MMTB số 03/2017/TSĐB/7189524 ngày 15/09/2017; Quyền sở hữu tài sản gắn liền với đất sổ CB 224471; 01 máy dán đáy Starlinger xuất xứ Châu Âu; Dây chuyền thiết bị sản xuất bao dán đáy thương hiệu Starlinger xuất xứ Châu Âu; 08 máy dệt tròn RX 6.0 hiệu Starlinger; Quyền đòi nợ phát sinh từ các hợp đồng kinh tế ký kết với Công ty Cổ phần Xi măng Vicem Hoàng Mai về việc mua bán vỏ bao xi măng, bao Sling Jumbo; Hàng hóa luân chuyển có giá trị tối thiểu bằng số dư cấp tín dụng ngắn hạn tại VietcomBank Nam Định. |

**Reasoning tham chiếu:**

1. E1: so dư nợ tại 31/12/2025, Ngoại thương 42.405.101.215 VND lớn hơn Công thương 35.528.793.127 VND và Đầu tư và Phát triển 29.962.860.942 VND; nối với dòng Chi nhánh Nam Định (2).
2. Dùng ngân hàng và ký hiệu (2) để chọn hợp đồng tương ứng trong E2.
3. E2: đọc cột Tài sản đảm bảo của hợp đồng 01/2025/VCB.NDI/7189524/CTD; quyền đòi nợ được nêu gắn với Xi măng Vicem Hoàng Mai, mua bán vỏ bao xi măng và bao Sling Jumbo.

**Bỏ nguồn:** Bảng dư nợ không có thông tin bảo đảm; bảng hợp đồng có hạn mức và bảo đảm nhưng không có dư nợ để chọn ngân hàng lớn nhất.

### VFB-MH-0012 — medium — REWRITE

**Câu hỏi:** Theo hai báo cáo hợp nhất năm 2021 và năm 2024 của Xi măng Bỉm Sơn, ở từng thời điểm cuối năm, nợ phải trả hay vốn chủ sở hữu chiếm phần lớn hơn trong tổng nguồn vốn? Vị trí chiếm phần lớn này thay đổi thế nào giữa hai mốc?

**Gold:** Vốn chủ sở hữu chiếm phần lớn hơn ở cả hai mốc. Cuối năm 2021, vốn chủ sở hữu 2.118.650.183.625 VND lớn hơn nợ phải trả 1.757.744.055.173 VND; cuối năm 2024, vốn chủ sở hữu 1.776.788.715.715 VND vẫn lớn hơn nợ phải trả 1.635.582.933.110 VND. Không có sự đổi vị trí giữa hai mốc này.

**Nguồn yêu cầu:** `multi_doc`; `BCC_2021`, `BCC_2024`.

**E1 — `BCC_2021_p009_t001`, trang 9; hàng “C. NỢ PHẢI TRẢ”, cột “Số cuối năm”.** Xác định nguồn tài trợ chiếm phần lớn tại cuối 2021.

> Tại ngày 31 tháng 12 năm 2021
> Đơn vị: VND
> ### BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT (Tiếp theo)
> | NGUỒN VỐN | Mã số | Thuyết minh | Số cuối năm | Số đầu năm |
> | --- | --- | --- | --- | --- |
> | C. NỢ PHẢI TRẢ | 300 |  | 1.757.744.055.173 | 2.012.132.904.102 |
> | D. VỐN CHỦ SỞ HỮU | 400 |  | 2.118.650.183.625 | 2.115.712.203.695 |

**E2 — `BCC_2024_p010_t001`, trang 10; hàng “C. NỢ PHẢI TRẢ”, cột “Số cuối năm”.** Xác định nguồn tài trợ chiếm phần lớn tại cuối 2024.

> Tại ngày 31 tháng 12 năm 2024
> ### Đơn vị: VND
> ### BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT
> | NGUỒN VỐN | Mã số | Thuyết minh | Số cuối năm | Số đầu năm |
> | --- | --- | --- | --- | --- |
> | C. NỢ PHẢI TRẢ | 300 |  | 1.635.582.933.110 | 1.871.791.299.592 |
> | D. VỐN CHỦ SỞ HỮU | 400 |  | 1.776.788.715.715 | 1.784.922.141.815 |

**Reasoning tham chiếu:**

1. E1: tại cuối năm 2021, so hai nhóm nguồn vốn trong B01 hợp nhất: vốn chủ sở hữu 2.118.650.183.625 VND > nợ phải trả 1.757.744.055.173 VND.
2. E2: tại cuối năm 2024, vẫn chọn cột cuối năm của B01 hợp nhất: vốn chủ sở hữu 1.776.788.715.715 VND > nợ phải trả 1.635.582.933.110 VND.
3. Nối hai kết quả theo cùng doanh nghiệp và phạm vi hợp nhất: vốn chủ sở hữu giữ vị trí phần lớn hơn ở cả hai mốc.

**Bỏ nguồn:** Một báo cáo riêng lẻ không có cả hai mốc 2021 và 2024; phải ghép hai kết quả theo cùng phạm vi hợp nhất.

### VFB-MH-0013 — hard — REPLACE

**Câu hỏi:** Trong báo cáo hợp nhất Alphanam E&C năm 2025, hãy lần theo ngân hàng nhận tiền gửi có kỳ hạn lớn nhất tại 31/12/2025 để xác định công ty con vay ngắn hạn tại cùng chi nhánh đó, số dư vay của công ty con và tỷ lệ quyền biểu quyết của Công ty mẹ tại công ty con này.

**Gold:** Ngân hàng TMCP Đông Nam Á – Chi nhánh Long Biên nhận khoản tiền gửi có kỳ hạn lớn nhất, 38.000.000.000 VND. Cùng chi nhánh đó cho Alpec vay ngắn hạn 38.880.784.513 VND. Alpec là Công ty Cổ phần Liên doanh Alpec, công ty con cấp 1, với tỷ lệ quyền biểu quyết của Công ty mẹ là 99,532%.

**Nguồn yêu cầu:** `single_doc`; `AME_2025`.

**E1 — `AME_2025_p022_t003`, trang 22; hàng “Ngân hàng TMCP Đông Nam Á - Chi nhánh Long Biên”, cột “31/12/2025 - Giá trị ghi sổ”.** Chọn ngân hàng và chi nhánh từ khoản tiền gửi lớn nhất.

> Đơn vị tính: VND
> ### 2.2. Đầu tư nắm giữ đến ngày đáo hạn
> | Chỉ tiêu | 31/12/2025 - Giá gốc | 31/12/2025 - Giá trị ghi sổ | 01/01/2025 - Giá gốc | 01/01/2025 - Giá trị ghi sổ |
> | --- | --- | --- | --- | --- |
> | Ngắn hạn |  |  |  |  |
> | Tiền gửi có kỳ hạn | 45.560.000.000 | 45.560.000.000 | 42.385.109.769 | 42.385.109.769 |
> | Ngân hàng TMCP Quân đội - Chi nhánh Hoàn Kiếm | 1.960.000.000 | 1.960.000.000 | 1.960.000.000 | 1.960.000.000 |
> | Ngân hàng TMCP Đông Nam Á - Chi nhánh Long Biên | 38.000.000.000 | 38.000.000.000 | 40.000.000.000 | 40.000.000.000 |
> | Ngân hàng TMCP Việt Nam Thịnh Vượng | 2.000.000.000 | 2.000.000.000 | - | - |
> | Ngân hàng First Commercial Bank - CN Hà Nội | 3.600.000.000 | 3.600.000.000 | - | - |
> | Ngân hàng TMCP Đầu tư và Phát triển Việt Nam - Chi nhánh Thái Hà | - | - | 425.109.769 | 425.109.769 |

**E2 — `AME_2025_p029_t001`, trang 29; hàng “Ngân hàng TMCP Đông Nam Á - CN Long Biên”, cột “31/12/2025”.** Đổi khóa nối từ ngân hàng sang công ty con có khoản vay tại chi nhánh đó.

> ### 18. Vay và nợ thuê tài chính
> | Khoản mục | 31/12/2025 | 01/01/2025 |
> | --- | --- | --- |
> | 18.1. Vay và nợ thuê tài chính ngắn hạn |  |  |
> | Khoản vay ngắn hạn tại Alpec |  |  |
> | Ngân hàng |  |  |
> | Ngân hàng TMCP Đông Nam Á - CN Long Biên | 38.880.784.513 | - |

Nguồn đơn vị cùng tài liệu, trang 22:

> Đơn vị tính: VND

**E3 — `AME_2025_p013_t001`, trang 13; hàng “Công ty Cổ phần Liên doanh Alpec”, cột “Tỷ lệ quyền biểu quyết”.** Đổi tên rút gọn Alpec sang tên đầy đủ, cấp công ty con và quyền biểu quyết.

> ### Danh sách các công ty con được hợp nhất
> | Tên công ty con | Tỷ lệ phần sở hữu | Tỷ lệ quyền biểu quyết | Địa chỉ - Hoạt động kinh doanh chính |
> | --- | --- | --- | --- |
> | Công ty con cấp 1 |  |  |  |
> | Công ty Cổ phần Liên doanh Alpec | 99,532% | 99,532% | Hưng Yên - Sản xuất các thiết bị nâng, hạ và bốc xếp, cung cấp dịch vụ sửa chữa, bảo trì thang máy |

**Reasoning tham chiếu:**

1. E1: trong các ngân hàng nhận tiền gửi kỳ hạn tại 31/12/2025, Đông Nam Á – Chi nhánh Long Biên có giá trị ghi sổ 38.000.000.000 VND, lớn nhất; lấy tên ngân hàng/chi nhánh làm khóa nối.
2. E2: tra cùng Đông Nam Á – CN Long Biên trong nhóm Khoản vay ngắn hạn tại Alpec, được số dư 38.880.784.513 VND; kết quả trung gian chuyển từ ngân hàng sang đơn vị Alpec.
3. E3: dùng Alpec để tìm tên đầy đủ trong danh sách công ty con được hợp nhất; đó là Công ty Cổ phần Liên doanh Alpec, thuộc nhóm công ty con cấp 1, tỷ lệ quyền biểu quyết 99,532%.

**Bỏ nguồn:** Thiếu E1 không biết ngân hàng cần truy; thiếu E2 không nối được ngân hàng với công ty con; thiếu E3 không có tên đầy đủ/cấp công ty con/quyền biểu quyết. Không bù trừ tiền gửi và khoản vay của hai chủ thể khác nhau.

### VFB-MH-0014 — hard — KEEP

**Câu hỏi:** Xét hai năm 2022 và 2024 của Xi măng Bỉm Sơn theo báo cáo hợp nhất từng năm, năm nào có doanh thu thuần và dòng tiền thuần từ hoạt động kinh doanh biến động trái chiều, khi mỗi chỉ tiêu được so với kỳ so sánh trong chính báo cáo năm đó?

**Gold:** Không năm nào trong hai năm này có biến động trái chiều. Năm 2022, doanh thu thuần giảm từ 4.330.051.249.712 VND xuống 4.218.317.356.885 VND và CFO giảm từ 424.221.921.072 VND xuống 178.149.035.829 VND theo cột so sánh trình bày lại. Năm 2024, doanh thu thuần tăng từ 3.081.365.372.469 VND lên 3.487.978.470.438 VND và CFO tăng từ 28.673.341.455 VND lên 202.642.595.052 VND.

**Nguồn yêu cầu:** `multi_doc`; `BCC_2022`, `BCC_2024`.

**E1 — `BCC_2022_p009_t001`, trang 9; hàng “3. Doanh thu thuần về bán hàng (10=01-02)”, cột “Năm nay”.** Kiểm chiều doanh thu 2022 theo cột trình bày lại.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2022
> Đơn vị: VND
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT
> | CHỈ TIÊU | Mã số | Thuyết minh | Năm nay | Năm trước (Trình bày lại) |
> | --- | --- | --- | --- | --- |
> | 3. Doanh thu thuần về bán hàng (10=01-02) | 10 | 24 | 4.218.317.356.885 | 4.330.051.249.712 |

**E2 — `BCC_2022_p010_t001`, trang 10; hàng “Lưu chuyển tiền thuần từ hoạt động kinh doanh”, cột “Năm nay”.** Kiểm chiều CFO 2022 theo cột trình bày lại.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2022
> Đơn vị: VND
> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ HỢP NHẤT
> | CHỈ TIÊU | Mã số | Năm nay | Năm trước (Trình bày lại) |
> | --- | --- | --- | --- |
> | Lưu chuyển tiền thuần từ hoạt động kinh doanh | 20 | 178.149.035.829 | 424.221.921.072 |

**E3 — `BCC_2024_p011_t001`, trang 11; hàng “3. Doanh thu thuần về bán hàng (10=01)”, cột “Năm nay”.** Kiểm chiều doanh thu 2024.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024
> Đơn vị: VND
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT
> | CHỈ TIÊU | Mã số | Thuyết minh | Năm nay | Năm trước |
> | --- | --- | --- | --- | --- |
> | 3. Doanh thu thuần về bán hàng (10=01) | 10 | 24 | 3.487.978.470.438 | 3.081.365.372.469 |

**E4 — `BCC_2024_p012_t001`, trang 12; hàng “Lưu chuyển tiền thuần từ hoạt động kinh doanh”, cột “Năm nay”.** Kiểm chiều CFO 2024.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024
> Đơn vị: VND
> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ HỢP NHẤT
> | CHỈ TIÊU | Mã số | Năm nay | Năm trước |
> | --- | --- | --- | --- |
> | Lưu chuyển tiền thuần từ hoạt động kinh doanh | 20 | 202.642.595.052 | 28.673.341.455 |

**Reasoning tham chiếu:**

1. E1: B02 hợp nhất 2022 ghi doanh thu thuần năm nay 4.218.317.356.885 VND và năm trước (Trình bày lại) 4.330.051.249.712 VND: năm 2022 giảm.
2. E2: B03 hợp nhất 2022 ghi CFO năm nay 178.149.035.829 VND và năm trước (Trình bày lại) 424.221.921.072 VND: năm 2022 giảm. Hai chỉ tiêu cùng giảm nên năm 2022 không có biến động trái chiều.
3. E3: B02 hợp nhất 2024 ghi doanh thu thuần năm nay 3.487.978.470.438 VND > năm trước 3.081.365.372.469 VND: năm 2024 tăng.
4. E4: B03 hợp nhất 2024 ghi CFO năm nay 202.642.595.052 VND > năm trước 28.673.341.455 VND: năm 2024 tăng.
5. Đối chiếu hai chiều biến động trong từng năm: 2022 cùng giảm, 2024 cùng tăng. Không năm nào trong tập {2022, 2024} có hai chỉ tiêu trái chiều. Giữ nguyên kỳ so sánh trình bày lại của báo cáo 2022; không thay bằng số gốc của báo cáo 2021 hoặc suy kết quả cho năm khác.

**Bỏ nguồn:** Thiếu bất kỳ nguồn nào sẽ không xác định được một chiều biến động trong một năm, nên không chứng minh được không năm nào trái chiều. Đây là đáp án xác định, không phải Unanswerable.

### VFB-MH-0015 — hard — REPLACE

**Câu hỏi:** Với ngân hàng đứng thứ hai về dư nợ vay ngắn hạn được nêu riêng tại cuối năm 2025 của Xi măng Vicem Bút Sơn, khoản vay dài hạn tại ngân hàng đó tài trợ dự án gì, được bảo đảm bằng gì và gồm những phần phải trả trong và sau 12 tháng nào?

**Gold:** Ngân hàng được chọn là Ngân hàng TMCP Ngoại thương Việt Nam – Chi nhánh Hà Nam, dư nợ vay ngắn hạn 284.602.002.053 VND, đứng sau BIDV Hà Nam 620.782.125.617 VND. Khoản vay dài hạn tài trợ công trình tận dụng nhiệt thừa khí thải dây chuyền 1 và 2 để phát điện, được bảo đảm bằng một số tài sản thuộc dây chuyền 1 và Dự án nhiệt thừa khí thải. Trong tổng dư nợ khoản vay dài hạn 163.889.101.366 VND, 43.744.176.000 VND phải trả trong vòng 12 tháng và 120.144.925.366 VND phải trả sau 12 tháng.

**Nguồn yêu cầu:** `single_doc`; `BTS_2025`.

**E1 — `BTS_2025_p027_t001`, trang 27; hàng “Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Hà Nam (ii)”, cột “Số cuối năm - Giá trị”.** Chọn ngân hàng theo thứ hạng dư nợ vay ngắn hạn cuối năm.

> ### 18. VAY NGẮN HẠN
> | Chỉ tiêu | Số đầu năm - Giá trị | Số đầu năm - Số có khả năng trả nợ | Trong năm - Tăng | Trong năm - Giảm | Số cuối năm - Giá trị | Số cuối năm - Số có khả năng trả nợ |
> | --- | --- | --- | --- | --- | --- | --- |
> | Vay ngắn hạn | 931.970.693.824 | 931.970.693.824 | 2.219.561.875.902 | 2.246.148.442.056 | 905.384.127.670 | 905.384.127.670 |
> | Ngân hàng TMCP Đầu tư và Phát triển Việt Nam - Chi nhánh Hà Nam (i) | 698.650.824.544 | 698.650.824.544 | 1.523.654.925.727 | 1.601.523.624.654 | 620.782.125.617 | 620.782.125.617 |
> | Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Hà Nam (ii) | 233.319.869.280 | 233.319.869.280 | 695.906.950.175 | 644.624.817.402 | 284.602.002.053 | 284.602.002.053 |

Nguồn đơn vị cùng tài liệu, trang 15:

> Báo cáo tài chính kèm theo được trình bày bằng Đồng Việt Nam (VND), theo nguyên tắc giá gốc và phù hợp với chuẩn mực kế toán, chế độ kế toán doanh nghiệp Việt Nam và các quy định pháp lý có liên quan đến việc lập và trình bày báo cáo tài chính.

**E2 — `BTS_2025_p028_t001`, trang 28; hàng “Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Hà Nam”, cột “Số cuối năm - Giá trị”.** Tra dư nợ khoản vay dài hạn cùng ngân hàng và hai phần kỳ hạn.

> ### Vay dài hạn
> | Chỉ tiêu | Số đầu năm - Giá trị | Số đầu năm - Số có khả năng trả nợ | Trong năm - Tăng | Trong năm - Giảm | Số cuối năm - Giá trị | Số cuối năm - Số có khả năng trả nợ |
> | --- | --- | --- | --- | --- | --- | --- |
> | Vay dài hạn |  |  |  |  |  |  |
> | Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Hà Nam | 207.633.277.366 | 207.633.277.366 | - | 43.744.176.000 | 163.889.101.366 | 163.889.101.366 |
> | Trong đó: |  |  |  |  |  |  |
> | - Số phải trả trong vòng 12 tháng | 43.744.176.000 | 43.744.176.000 |  |  | 43.744.176.000 | 43.744.176.000 |
> | - Số phải trả sau 12 tháng | 163.889.101.366 | 163.889.101.366 |  |  | 120.144.925.366 | 120.144.925.366 |

Nguồn đơn vị cùng tài liệu, trang 15:

> Báo cáo tài chính kèm theo được trình bày bằng Đồng Việt Nam (VND), theo nguyên tắc giá gốc và phù hợp với chuẩn mực kế toán, chế độ kế toán doanh nghiệp Việt Nam và các quy định pháp lý có liên quan đến việc lập và trình bày báo cáo tài chính.

**E3 — `BTS_2025`, trang 28, văn bản.** Tra mục đích tài trợ và tài sản bảo đảm của hợp đồng vay dài hạn.

> Số dư vay dài hạn ngân hàng tại ngày 31 tháng 12 năm 2025 thể hiện khoản vay từ Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Hà Nam theo hợp đồng số 101/22/HĐTD/9DY ngày 05 tháng 4 năm 2022 và hợp đồng sửa đổi bổ sung số 02.101/22/HĐCTD/9DY ngày 10 tháng 01 năm 2024 được sử dụng để tài trợ cho các nhu cầu tín dụng hợp pháp, hợp lý, hợp lệ liên quan đến việc đầu tư thực hiện phương án Đầu tư xây dựng công trình tận dụng nhiệt thừa khí thải dây chuyền 1 và dây chuyền 2 để phát điện theo quy định của pháp luật. Khoản vay được thực hiện từng lần với số tiền vay tối đa là 249.000.000.000 VND nhưng tối đa không vượt quá 60% tổng mức đầu tư (chưa bao gồm thuế giá trị gia tăng) của dự án. Thời hạn cho vay là 83 tháng kể từ ngày giải ngân. Lãi suất cho vay được xác định theo từng lần giải ngân. Khoản vay được ân hạn 16 tháng kể từ ngày giải ngân đầu tiên nhưng không quá 03 tháng kể từ ngày dự án đi vào hoạt động. Lãi suất sẽ được trả vào ngày 26 hàng tháng. Khoản vay được đảm bảo bằng một số tài sản thuộc dây chuyền 1 và Dự án nhiệt thừa khí thải (Thuyết minh số 11).

**Reasoning tham chiếu:**

1. E1: trong các ngân hàng được nêu riêng, BIDV Hà Nam có dư nợ vay ngắn hạn 620.782.125.617 VND và Ngoại thương Hà Nam 284.602.002.053 VND; chọn ngân hàng thứ hai là Ngoại thương Hà Nam.
2. E2: dùng tên ngân hàng đã chọn để tìm khoản vay dài hạn; bảng cho tổng dư nợ khoản vay 163.889.101.366 VND, trong đó 43.744.176.000 VND trả trong vòng 12 tháng và 120.144.925.366 VND trả sau 12 tháng.
3. E3: tra đoạn hợp đồng vay dài hạn của cùng ngân hàng: vốn tài trợ công trình tận dụng nhiệt thừa khí thải dây chuyền 1 và 2 để phát điện; tài sản bảo đảm là một số tài sản dây chuyền 1 và Dự án nhiệt thừa khí thải.
4. Ghép hồ sơ khoản vay đúng ngân hàng; giữ phần đến hạn trong 12 tháng tách khỏi phần phải trả sau 12 tháng, không lấy tổng khoản vay làm toàn bộ nợ dài hạn trình bày.

**Bỏ nguồn:** E1 mới xác định thứ hạng; E2 mới có cơ cấu dư nợ theo kỳ hạn; E3 mới có mục đích và bảo đảm. Không cộng lại phần đến hạn trả đã nằm trong vay ngắn hạn.

## 7. Validation và giới hạn

Focused checks local bằng Python trên hai artifact, không thêm runner/framework vào repository:

| Kiểm tra | Kết quả / giới hạn |
| --- | --- |
| JSONL/schema/ID | PASS: 15 dòng UTF-8, ID liên tục duy nhất, 5/7/3, Evidence ≥2, Answer/Evidence v1 và hai key nguồn đúng kiểu |
| Hành động review | PASS: 3 KEEP giữ nguyên nội dung baseline; 5 REWRITE/7 REPLACE đã đối chiếu đủ 15 ID; KEEP chỉ thêm metadata yêu cầu nguồn |
| Nguồn | PASS: 35 Evidence định vị đúng trang/tài liệu; header, toàn bộ hàng được trích và đoạn văn khớp neutral; row_path chỉ dùng nhóm thật |
| Đáp án | PASS: đọc lại 15/15, kiểm lại thứ hạng/khóa nối/ô số dư/điều khoản, dấu tiền chi, kỳ và phạm vi; các số/tên/ngày/tỷ lệ của Gold có trong nguồn |
| Metadata nguồn | PASS: input_documents đúng tập tài liệu cần thiết, không trùng; 13 single_doc/2 multi_doc; cả hai multi_doc giữ cùng phạm vi hợp nhất |
| Multi-hop/Numerical | Đã đọc lại 15/15 theo vai trò và phép thử bỏ nguồn; 8 bridge có kết quả trung gian quyết định tra cứu tiếp; không có nguồn đơn lẻ đủ Gold đầy đủ |
| Trùng ý | 0 câu trùng chính xác; không thấy hai mẫu cùng đối tượng/kỳ và cùng bài toán. Các bridge ngân hàng khác nhau về mục tiêu: hạn mức, quyền đòi nợ, công ty con, tài trợ dự án/kỳ hạn |
| Bảo toàn | PASS: hash các file tracked/untracked hiện có ngoài hai deliverables không đổi; neutral, Single-hop, metadata, schema và local edits ngoài task được giữ |
| Diff | PASS: git diff --check và kiểm diff được stage chỉ thuộc hai deliverables |

Đây là tự kiểm biên soạn trên neutral, không phải independent human review, PDF verification hoặc kết quả evaluation mô hình. Không suy tính đúng tài chính toàn hệ thống từ PASS cấu trúc.

**Giới hạn/điểm cần Tech Lead quyết định:**

- 8 bridge vẫn chủ yếu khởi đầu bằng so/xếp hạng số rồi nối thực thể/khoản mục; chưa đại diện mọi kiểu suy luận chuỗi. 0001/0002 là bridge Easy có lựa chọn hữu hạn, chưa phải tình huống tìm kiếm mở.
- Chỉ 2 QA cross-document, cùng BCC hợp nhất và không có chuỗi văn bản xuyên tài liệu. 10 QA dùng báo cáo chính, 5 chỉ dùng các vùng thuyết minh; đây là đánh đổi với mức đa dạng reasoning, không đặt thành quota cho Full.
- Cả 15 answer là text để giữ nội dung nhiều điều kiện; cần chấm đủ key_points, không chấm bằng từ đầu Có/Không hay chỉ một con số. Hai câu nhị phân còn lại có chủ đích; câu 0014 tập rỗng cần giữ là answerable.
- 0013 nối “Chi nhánh” với “CN” của cùng Đông Nam Á – Long Biên và “Alpec” với tên đầy đủ trong danh sách công ty con; không bù trừ tiền gửi cấp hợp nhất với khoản vay của công ty con. Đơn vị vay không được nhầm sang Công ty mẹ.
- 0015 phần trả trong vòng 12 tháng đã được phân loại sang ngắn hạn; không cộng trùng hoặc gọi 163.889.101.366 VND là toàn bộ khoản vay dài hạn sau 12 tháng. Không dùng diễn giải hạn mức ngắn hạn có ngày năm 2026 để mô tả khoản vay dài hạn năm 2025.
- 0004 có khoản tiền thu bao gồm cả “doanh thu khác”; 0007 không biến chênh chi phí–tiền nộp thành thuế phải trả; 0010 không lấy doanh thu trừ phải thu để suy tiền đã thu; 0012 chỉ so hai mốc, không khẳng định cơ cấu giữ nguyên mọi năm giữa hai mốc.
- Độ khó chưa hiệu chỉnh bằng model/human evaluation; Hard dựa trên 3–4 nguồn thiết yếu, liên kết nhiều thực thể/điều kiện và phân loại kỳ hạn/kỳ so sánh, không dựa trên độ dài câu hỏi.

**Next action duy nhất:** Tech Lead review 15 QA Refine và quyết định nghiệm thu Pilot tại REVIEW trước khi giao mở rộng Multi-hop.
