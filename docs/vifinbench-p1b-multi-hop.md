# ViFinBench-P1B — 15 Multi-hop QA Pilot

Ngày thực hiện: **14/11/2026** (Asia/Bangkok). Trạng thái: **REVIEW** — chờ Tech Lead nghiệm thu. Gold là lời giải tham chiếu do tác nhân biên soạn và kiểm với corpus neutral, chưa phải xác nhận độc lập từ PDF.

## 1. Kết quả và phạm vi

**15 QA: 5 Easy / 7 Medium / 3 Hard; 10 natural / 5 formal; 11 doanh nghiệp / 13 tài liệu.** ID liên tục `VFB-MH-0001`–`VFB-MH-0015`. Có 34 bằng chứng chính, mỗi QA có 2–4 bằng chứng; cả 15 QA dùng B01/B02/B03. Bốn QA nối báo cáo chính với B09; hai QA liên kỳ qua nhiều tài liệu; một QA đối chiếu ba bảng B01+B03 để tính thiếu hụt vốn lưu động ròng rồi so với CFO.

Chỉ tạo [pilot.jsonl](../ViFinBench/benchmark/multi_hop/pilot.jsonl) và báo cáo này. Không sửa corpus neutral, Single-hop Pilot/Full/Backup, metadata, schema chung, pipeline hoặc local edits ngoài task. Không sửa planning vì brief yêu cầu đúng hai deliverables; trạng thái P1B được ghi tại đây, registry hiện có được giữ nguyên.

Implementation là commit chứa hai file trên; tra bằng `git log -1 --format=%H -- ViFinBench/benchmark/multi_hop/pilot.jsonl`. SHA và kết quả đối chiếu remote được ghi trong bàn giao sau commit/push; không dùng SHA nguồn làm SHA implementation.

## 2. Phần mở rộng Multi-hop được giao

Giữ các trường chung v1: `id`, `task`, `difficulty`, `question_style`, `question`, `answer`, `tags`; dùng `task: multi_hop`. Theo brief P1B, riêng subset này có `evidence` là **mảng ít nhất hai Evidence v1**, thay cho object của Single-hop, và thêm `reasoning` là mảng bước giải tham chiếu ngắn, kiểm chứng được. Đây là ngoại lệ được giao so với mục 5 của schema đang khóa; không sửa Schema v1 hoặc Single-hop.

Mỗi Evidence giữ đủ tám key v1. `row_label`/`column_header` giữ đúng JSON nguồn, kể cả xuống dòng; quote chép header và toàn bộ hàng từ Markdown, có thể chọn các hàng nguyên văn theo thứ tự. `row_path` chỉ dùng nhóm thật (0009, 0010, 0013). Trang là trang neutral, không phải số trang in/PDF. Một Evidence có thể trích nhiều hàng cùng bảng để xác định cực đại hoặc đủ nhóm/cột; không tách cùng hàng thành nhiều Evidence để tăng hop giả.

Cả 15 đáp án là `text` với `value`, `display`, `unit: null` và `key_points`; số tiền nằm trong chuỗi tiếng Việt có ghi VND. Không tạo trường number dạng float. Các phép tính trong reasoning ghi đủ toán hạng và kết quả; không thêm đơn vị mới, tolerance, bbox, confidence hoặc metadata kỹ thuật. `unit_evidence` chỉ xác nhận đơn vị, không tính thành hop tài chính.

## 3. Phân bố và bảng tổng hợp

| Độ khó | QA | Cơ sở biên soạn |
| --- | ---: | --- |
| Easy | 5 | Hai chỉ tiêu, so sánh trực tiếp hoặc so dấu |
| Medium | 7 | Phân biệt số dư/phát sinh, nhóm/cột, ngưỡng, cực đại hoặc phạm vi liên kỳ |
| Hard | 3 | 3–4 bằng chứng thiết yếu, đối chiếu chênh lệch hoặc điều kiện kết hợp |

| Kiểu kết hợp chính (không đếm chồng) | Mục tiêu | Thực tế | ID cuối |
| --- | ---: | ---: | --- |
| B01 + B02 | 3 | 3 | 0001, 0002, 0006 |
| B02 + B03 | 3 | 3 | 0003, 0004, 0007 |
| B01 + B03 | 2 | 3 | 0005, 0008, 0015 |
| B01/B02/B03 + B09 | 4 | 4 | 0009, 0010, 0011, 0013 |
| Liên kỳ hoặc kết hợp khác | 3 | 2 | 0012 (B01 liên kỳ), 0014 (B02+B03 liên kỳ) |

Điều chỉnh một câu từ nhóm “khác” sang B01+B03: 0015 dùng ba bằng chứng để tính thiếu hụt vốn lưu động ròng rồi so với CFO, có liên hệ tài chính rõ và mọi bằng chứng đều cần thiết. Nếu đếm chồng, 0014 cũng có B02+B03; không dùng cách đếm đó để cộng tổng 15.

| ID | Độ khó | Doanh nghiệp / tài liệu | Chủ đề | Bằng chứng |
| --- | --- | --- | --- | ---: |
| VFB-MH-0001 | easy | BBS_2025 | Doanh thu năm so với tài sản cuối năm | 2 |
| VFB-MH-0002 | easy | BPC_2025 | Tồn kho cuối năm so với giá vốn trong năm | 2 |
| VFB-MH-0003 | easy | ADC_2025 | Lãi kế toán và dấu dòng tiền kinh doanh | 2 |
| VFB-MH-0004 | easy | AMC_2025 | Doanh thu và tiền thu từ bán hàng | 2 |
| VFB-MH-0005 | easy | ARM_2025 | Tiền vay nhận trong năm và dư nợ cuối năm | 2 |
| VFB-MH-0006 | medium | BTW_2025 | Chiều biến động doanh thu và quy mô tài sản | 2 |
| VFB-MH-0007 | medium | BTW_2025 | Thuế ghi nhận và tiền thuế thực nộp | 2 |
| VFB-MH-0008 | medium | CAG_2025 | Phải thu khách hàng tăng và CFO dương | 2 |
| VFB-MH-0009 | medium | AME_2025 | Tiền gửi đầu tư và tiền tương đương tiền | 2 |
| VFB-MH-0010 | medium | BED_2025 | Mức tập trung giao dịch với bên liên quan | 2 |
| VFB-MH-0011 | medium | BBS_2025 | Khoản vay ngân hàng lớn nhất và nợ ngắn hạn | 2 |
| VFB-MH-0012 | medium | BCC_2021, BCC_2024 | Đối chiếu tổng nợ hai năm, cùng phạm vi | 2 |
| VFB-MH-0013 | hard | ARM_2025 | Đối chiếu cổ tức phân phối, thực trả và phải trả | 3 |
| VFB-MH-0014 | hard | BCC_2022, BCC_2024 | Chiều biến động trong hai báo cáo hợp nhất | 4 |
| VFB-MH-0015 | hard | BTS_2025 | CFO so với thiếu hụt vốn lưu động ròng | 3 |

Tài liệu khai thác: `ADC_2025`, `AMC_2025`, `AME_2025`, `ARM_2025`, `BBS_2025`, `BCC_2021`, `BCC_2022`, `BCC_2024`, `BED_2025`, `BPC_2025`, `BTS_2025`, `BTW_2025`, `CAG_2025`.

Doanh nghiệp: ADC, AMC, AME, ARM, BBS, BCC, BED, BPC, BTS, BTW, CAG. Năm tài chính tài liệu: 2021, 2022, 2024, 2025; kỳ so sánh 2023 xuất hiện ở 0014. Không gán scope cho tài liệu metadata còn `unknown`; các câu đó giới hạn trong cùng một tài liệu. Hai câu liên kỳ 0012/0014 chỉ dùng các báo cáo BCC cùng phạm vi hợp nhất.

## 4. Từng mẫu: câu hỏi, Gold, bằng chứng và reasoning

E1, E2… trong mỗi mẫu theo đúng thứ tự mảng `evidence`. Các trích dẫn dưới đây là nội dung neutral; dấu ngoặc đơn của tiền là số âm. Các bảng trích đủ cột nguồn, nhưng câu hỏi chỉ dùng kỳ/cột đã định vị. Cột khác trong quote không tự trở thành đầu vào cho lời giải.

### VFB-MH-0001 — easy — Doanh thu năm so với tài sản cuối năm

**Câu hỏi:** Doanh thu thuần năm 2025 của Vicem Bao bì Bút Sơn có lớn hơn tổng tài sản tại ngày 31/12/2025 không?

**Gold:** Có. Doanh thu thuần năm 2025 là 450.474.531.227 VND, lớn hơn tổng tài sản tại ngày 31/12/2025 là 266.086.680.765 VND.

**E1 — `BBS_2025_p007_t001`, trang neutral 7; hàng “Doanh thu thuần về bán hàng và cung cấp dịch vụ”; cột “Năm 2025”.** Cung cấp doanh thu thuần cả năm.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Đơn vị tính: VND
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
> | STT | CHỈ TIÊU | Mã số | Thuyết minh | Năm 2025 | Năm 2024 |
> | --- | --- | --- | --- | --- | --- |
> | 3. | Doanh thu thuần về bán hàng và cung cấp dịch vụ | 10 |  | 450.474.531.227 | 355.507.372.286 |

**E2 — `BBS_2025_p005_t001`, trang neutral 5; hàng “TỔNG CỘNG TÀI SẢN”; cột “31/12/2025”.** Cung cấp tổng tài sản tại thời điểm cuối năm.

> Tại ngày 31 tháng 12 năm 2025
> Đơn vị tính: VND
> ### BẢNG CÂN ĐỐI KẾ TOÁN
> | CHỈ TIÊU | Mã số | Thuyết minh | 31/12/2025 | 01/01/2025 |
> | --- | --- | --- | --- | --- |
> | TỔNG CỘNG TÀI SẢN | 270 |  | 266.086.680.765 | 291.306.659.104 |

**Reasoning tham chiếu:**

1. E1: đọc doanh thu thuần cả năm 2025 là 450.474.531.227 VND từ B02.
2. E2: đọc tổng tài sản tại 31/12/2025 là 266.086.680.765 VND từ B01 của cùng tài liệu.
3. So sánh 450.474.531.227 > 266.086.680.765. Đây là so sánh số phát sinh trong năm với số dư cuối năm; không phải tỷ suất sinh lời hoặc vòng quay tính trên tài sản bình quân.

**Kiểm tính cần thiết:** E1 cung cấp doanh thu thuần cả năm. E2 cung cấp tổng tài sản tại thời điểm cuối năm. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0002 — easy — Tồn kho cuối năm so với giá vốn trong năm

**Câu hỏi:** Ở Vicem Bao bì Bỉm Sơn, hàng tồn kho cuối năm 2025 có vượt giá vốn hàng bán ghi nhận trong cả năm 2025 không?

**Gold:** Không. Hàng tồn kho tại 31/12/2025 là 26.588.023.255 VND, thấp hơn giá vốn hàng bán năm 2025 là 237.846.985.781 VND.

**E1 — `BPC_2025_p005_t001`, trang neutral 5; hàng “IV. Hàng tồn kho”; cột “31/12/2025”.** Cung cấp số dư tồn kho cuối năm.

> Tại ngày 31 tháng 12 năm 2025
> Đơn vị tính: VND
> ### BẢNG CÂN ĐỐI KẾ TOÁN
> | CHỈ TIÊU | Mã số | Thuyết minh | 31/12/2025 | 01/01/2025 |
> | --- | --- | --- | --- | --- |
> | IV. Hàng tồn kho | 140 | 8 | 26.588.023.255 | 19.806.637.849 |

**E2 — `BPC_2025_p007_t001`, trang neutral 7; hàng “Giá vốn hàng bán”; cột “Năm 2025”.** Cung cấp giá vốn phát sinh cả năm.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Đơn vị tính: VND
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
> | STT | CHỈ TIÊU | Mã số | Thuyết minh | Năm 2025 | Năm 2024 |
> | --- | --- | --- | --- | --- | --- |
> | 4. | Giá vốn hàng bán | 11 | 18 | 237.846.985.781 | 244.369.939.617 |

**Reasoning tham chiếu:**

1. E1: B01 ghi số dư hàng tồn kho tại 31/12/2025 là 26.588.023.255 VND.
2. E2: B02 ghi giá vốn hàng bán phát sinh năm 2025 là 237.846.985.781 VND.
3. 26.588.023.255 < 237.846.985.781 nên tồn kho cuối năm không vượt giá vốn cả năm. Không coi số dư tồn kho là lượng hàng đã bán hoặc tự suy ra số ngày tồn kho.

**Kiểm tính cần thiết:** E1 cung cấp số dư tồn kho cuối năm. E2 cung cấp giá vốn phát sinh cả năm. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0003 — easy — Lãi kế toán và dấu dòng tiền kinh doanh

**Câu hỏi:** Năm 2025, lợi nhuận sau thuế và dòng tiền thuần từ hoạt động kinh doanh của Mĩ thuật và Truyền thông có cùng dấu không?

**Gold:** Không. Báo cáo riêng ghi lợi nhuận sau thuế năm 2025 dương 11.069.694.145 VND, nhưng dòng tiền thuần từ hoạt động kinh doanh âm 1.823.580.740 VND.

**E1 — `ADC_2025_p012_t001`, trang neutral 12; hàng “17. Lợi nhuận sau thuế thu nhập doanh nghiệp”; cột “Năm 2025 / VND”.** Xác định lợi nhuận sau thuế, không thay bằng lợi nhuận trước thuế.

> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH Năm 2025
> | Mã số | CHỈ TIÊU | Thuyết minh | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- | --- |
> | 60 | 17. Lợi nhuận sau thuế thu nhập doanh nghiệp |  | 11.069.694.145 | 13.961.942.478 |

**E2 — `ADC_2025_p013_t001`, trang neutral 13; hàng “Lưu chuyển tiền thuần từ hoạt động kinh doanh”; cột “Năm 2025 / VND”.** Xác định dấu CFO.

> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ Năm 2025 (Theo phương pháp gián tiếp)
> | Mã số | CHỈ TIÊU | Thuyết minh | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- | --- |
> | 20 | Lưu chuyển tiền thuần từ hoạt động kinh doanh |  | (1.823.580.740) | 29.461.119.372 |

**Reasoning tham chiếu:**

1. E1: lấy lợi nhuận sau thuế năm 2025 từ B02: 11.069.694.145 VND > 0.
2. E2: B03 cùng năm trình bày CFO là (1.823.580.740) VND; ngoặc đơn biểu thị số âm.
3. Đối chiếu dấu: lợi nhuận sau thuế dương, CFO âm. Không kết luận doanh nghiệp thua lỗ từ CFO âm và không dùng lợi nhuận trước thuế trên B03 thay cho lợi nhuận sau thuế.

**Kiểm tính cần thiết:** E1 xác định lợi nhuận sau thuế, không thay bằng lợi nhuận trước thuế. E2 xác định dấu CFO. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0004 — easy — Doanh thu và tiền thu từ bán hàng

**Câu hỏi:** Năm 2025, khoản tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác của Khoáng sản Á Châu có lớn hơn doanh thu thuần bán hàng và cung cấp dịch vụ không?

**Gold:** Có. Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác là 177.385.494.652 VND, lớn hơn doanh thu thuần bán hàng và cung cấp dịch vụ 169.865.621.961 VND.

**E1 — `AMC_2025_p010_t001`, trang neutral 10; hàng “1. Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác”; cột “Năm nay”.** Cung cấp khoản thực thu theo B03 trực tiếp.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
> Đơn vị: VND
> ### Báo cáo lưu chuyển tiền tệ
> | Chỉ tiêu | Mã số | Năm nay | Năm trước |
> | --- | --- | --- | --- |
> | 1. Tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác | 01 | 177.385.494.652 | 164.337.752.205 |

**E2 — `AMC_2025_p009_t001`, trang neutral 9; hàng “2. Doanh thu thuần về bán hàng và cung cấp dịch vụ”; cột “Năm nay”.** Cung cấp doanh thu thuần theo B02.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
> | Mã số | CHỈ TIÊU | Thuyết minh | Năm nay | Năm trước |
> | --- | --- | --- | --- | --- |
> | 10 | 2. Doanh thu thuần về bán hàng và cung cấp dịch vụ | VI.1 | 169.865.621.961 | 159.789.927.069 |

Nguồn đơn vị cùng `AMC_2025`, trang 12:

> Báo cáo tài chính kèm theo được trình bày bằng Đồng Việt Nam (VND), theo nguyên tắc giá gốc và phù hợp với Chuẩn mực kế toán, Chế độ kế toán doanh nghiệp Việt Nam và các quy định pháp lý có liên quan đến việc lập và trình bày Báo cáo tài chính. Báo cáo tài chính kèm theo không nhằm phản ánh tình hình tài chính, kết quả hoạt động kinh doanh và tình hình lưu chuyển tiền tệ theo các nguyên tắc và thông lệ kế toán được chấp nhận chung tại các nước khác ngoài Việt Nam.

**Reasoning tham chiếu:**

1. E1: B03 theo phương pháp trực tiếp ghi tiền thu từ bán hàng, cung cấp dịch vụ và doanh thu khác năm 2025 là 177.385.494.652 VND.
2. E2: B02 ghi doanh thu thuần bán hàng và cung cấp dịch vụ năm nay (2025) là 169.865.621.961 VND; đơn vị trình bày VND được xác nhận ở trang 12.
3. 177.385.494.652 > 169.865.621.961. Hai khoản khác bản chất và tên khoản tiền thu còn bao gồm doanh thu khác; không đồng nhất tiền thu với doanh thu hoặc suy nguyên nhân chênh lệch.

**Kiểm tính cần thiết:** E1 cung cấp khoản thực thu theo B03 trực tiếp. E2 cung cấp doanh thu thuần theo B02. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0005 — easy — Tiền vay nhận trong năm và dư nợ cuối năm

**Câu hỏi:** Theo báo cáo riêng năm 2025 của Xuất nhập khẩu Hàng không, tiền thu từ đi vay trong năm có lớn hơn số dư vay và nợ thuê tài chính ngắn hạn cuối năm không?

**Gold:** Có. Tiền thu từ đi vay trong năm là 30.358.245.453 VND, lớn hơn số dư vay và nợ thuê tài chính ngắn hạn tại 31/12/2025 là 21.086.637.668 VND.

**E1 — `ARM_2025_p012_t001`, trang neutral 12; hàng “3. Tiền thu từ đi vay”; cột “Năm 2025”.** Cung cấp tiền vay thực nhận cả năm.

> Cho năm tài chính kết thúc ngày 31/12/2025
> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ
> | CHỈ TIÊU | Mã số | Thuyết minh | Năm 2025 | Năm 2024 |
> | --- | --- | --- | --- | --- |
> | 3. Tiền thu từ đi vay | 33 |  | 30.358.245.453 | 50.472.159.623 |

Nguồn đơn vị cùng `ARM_2025`, trang 14:

> Báo cáo tài chính kèm theo được trình bày bằng Đồng Việt Nam (VND).

**E2 — `ARM_2025_p010_t001`, trang neutral 10; hàng “10. Vay và nợ thuê tài chính ngắn hạn”; cột “31/12/2025 (VND)”.** Cung cấp số dư nợ vay ngắn hạn cuối năm.

> Tại ngày 31 tháng 12 năm 2025
> ### BẢNG CÂN ĐỐI KẾ TOÁN (TIẾP THEO)
> | Mã số | Thuyết minh | NGUỒN VỐN | 31/12/2025 (VND) | 01/01/2025 (VND) |
> | --- | --- | --- | --- | --- |
> | 320 | 5.15 | 10. Vay và nợ thuê tài chính ngắn hạn | 21.086.637.668 | 32.157.464.403 |

**Reasoning tham chiếu:**

1. E1: lấy dòng tiền thu từ đi vay năm 2025 trên B03 là 30.358.245.453 VND; trang 14 xác nhận đơn vị trình bày VND.
2. E2: lấy số dư vay và nợ thuê tài chính ngắn hạn tại 31/12/2025 trên B01 là 21.086.637.668 VND.
3. 30.358.245.453 > 21.086.637.668. Khoản thứ nhất là tổng tiền nhận trong kỳ, khoản thứ hai là số dư ngắn hạn tại một thời điểm; chênh lệch này không phải mức tăng dư nợ.

**Kiểm tính cần thiết:** E1 cung cấp tiền vay thực nhận cả năm. E2 cung cấp số dư nợ vay ngắn hạn cuối năm. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0006 — medium — Chiều biến động doanh thu và quy mô tài sản

**Câu hỏi:** Trong báo cáo riêng năm 2025 của Cấp nước Bến Thành, biến động doanh thu thuần so với năm 2024 có cùng chiều với biến động tổng tài sản tại 31/12/2025 so với 01/01/2025 không?

**Gold:** Không cùng chiều. Doanh thu thuần giảm từ 561.464.712.365 VND xuống 550.869.711.512 VND, trong khi tổng tài sản tăng từ 380.695.090.023 VND lên 384.095.301.328 VND.

**E1 — `BTW_2025_p012_t001`, trang neutral 12; hàng “Doanh thu thuần về bán hàng và cung cấp dịch vụ”; cột “Năm 2025 / VND”.** Cho hai doanh thu phát sinh trong các năm 2024 và 2025.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Cho năm tài chính kết thúc ngày 31/12/2025
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
> | Chỉ tiêu | Mã số | Thuyết minh | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- | --- |
> | Doanh thu thuần về bán hàng và cung cấp dịch vụ | 10 |  | 550.869.711.512 | 561.464.712.365 |

**E2 — `BTW_2025_p010_t001`, trang neutral 10; hàng “TỔNG TÀI SẢN”; cột “Tại 31/12/2025 VND”.** Cho hai số dư tài sản đầu và cuối năm 2025.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Tại ngày 31 tháng 12 năm 2025
> ### BẢNG CÂN ĐỐI KẾ TOÁN
> | TÀI SẢN | Mã số | Thuyết minh | Tại 31/12/2025 VND | Tại 01/01/2025 VND |
> | --- | --- | --- | --- | --- |
> | TỔNG TÀI SẢN | 270 |  | 384.095.301.328 | 380.695.090.023 |

**Reasoning tham chiếu:**

1. E1: doanh thu thuần năm 2025 là 550.869.711.512 VND, năm 2024 là 561.464.712.365 VND. Tính 550.869.711.512 - 561.464.712.365 = -10.595.000.853 VND.
2. E2: tổng tài sản tại 31/12/2025 là 384.095.301.328 VND, tại 01/01/2025 là 380.695.090.023 VND. Tính 384.095.301.328 - 380.695.090.023 = 3.400.211.305 VND.
3. Doanh thu năm giảm nhưng số dư tổng tài sản tăng; hai chiều trái nhau. Không diễn giải đây là bằng chứng về nguyên nhân hoặc hiệu quả sử dụng tài sản.

**Kiểm tính cần thiết:** E1 cho hai doanh thu phát sinh trong các năm 2024 và 2025. E2 cho hai số dư tài sản đầu và cuối năm 2025. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0007 — medium — Thuế ghi nhận và tiền thuế thực nộp

**Câu hỏi:** Ở báo cáo riêng năm 2025 của Cấp nước Bến Thành, số thuế thu nhập doanh nghiệp thực nộp trên báo cáo lưu chuyển tiền tệ có bằng chi phí thuế TNDN hiện hành trên báo cáo kết quả kinh doanh không; khoản nào lớn hơn?

**Gold:** Không bằng nhau. Chi phí thuế TNDN hiện hành là 12.238.256.455 VND, lớn hơn số thuế TNDN thực nộp 8.839.086.235 VND một khoản 3.399.170.220 VND.

**E1 — `BTW_2025_p012_t001`, trang neutral 12; hàng “Chi phí thuế TNDN hiện hành”; cột “Năm 2025 / VND”.** Cung cấp chi phí thuế hiện hành, phân biệt với hoãn lại.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Cho năm tài chính kết thúc ngày 31/12/2025
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
> | Chỉ tiêu | Mã số | Thuyết minh | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- | --- |
> | Chi phí thuế TNDN hiện hành | 51 | 30 | 12.238.256.455 | 11.959.143.488 |

**E2 — `BTW_2025_p013_t001`, trang neutral 13; hàng “Thuế thu nhập doanh nghiệp đã nộp”; cột “Năm 2025 / VND”.** Cung cấp khoản tiền thuế đã thực nộp.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Cho năm tài chính kết thúc ngày 31/12/2025
> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ
> | Chỉ tiêu | Mã số | Năm 2025 VND | Năm 2024 VND |
> | --- | --- | --- | --- |
> | Thuế thu nhập doanh nghiệp đã nộp | 15 | (8.839.086.235) | (14.134.867.462) |

**Reasoning tham chiếu:**

1. E1: chọn chi phí thuế TNDN hiện hành (mã 51), năm 2025, trên B02: 12.238.256.455 VND; không chọn thuế hoãn lại.
2. E2: B03 ghi thuế TNDN đã nộp năm 2025 là (8.839.086.235) VND. Lấy độ lớn 8.839.086.235 VND để so khoản thực nộp với chi phí; giữ dấu âm khi mô tả dòng tiền ra.
3. 12.238.256.455 - 8.839.086.235 = 3.399.170.220 VND > 0. Chi phí hiện hành lớn hơn số tiền nộp; không tự quy chênh lệch thành số dư thuế phải nộp cuối năm.

**Kiểm tính cần thiết:** E1 cung cấp chi phí thuế hiện hành, phân biệt với hoãn lại. E2 cung cấp khoản tiền thuế đã thực nộp. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0008 — medium — Phải thu khách hàng tăng và CFO dương

**Câu hỏi:** Trong năm 2025, Cảng An Giang có đồng thời ghi nhận phải thu ngắn hạn của khách hàng tăng từ đầu đến cuối năm và dòng tiền thuần từ hoạt động kinh doanh dương không?

**Gold:** Có. Phải thu ngắn hạn của khách hàng tăng từ 10.495.861.227 VND lên 14.029.472.134 VND, đồng thời CFO năm 2025 dương 2.945.594.773 VND.

**E1 — `CAG_2025_p006_t001`, trang neutral 6; hàng “1. Phải thu ngắn hạn của khách hàng”; cột “Số cuối năm”.** Xác định biến động đúng khoản phải thu khách hàng.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
> Tại ngày 31 tháng 12 năm 2025
> Đơn vị tính: VND
> ### Bảng cân đối kế toán
> | CHỈ TIÊU | Mã số | Thuyết minh | Số cuối năm | Số đầu năm |
> | --- | --- | --- | --- | --- |
> | 1. Phải thu ngắn hạn của khách hàng | 131 | V.3 | 14.029.472.134 | 10.495.861.227 |

**E2 — `CAG_2025_p011_t001`, trang neutral 11; hàng “Lưu chuyển tiền thuần từ hoạt động kinh doanh”; cột “Năm nay”.** Xác định CFO của cả năm; không thay bằng biến động riêng phải thu trên B03.

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

**Kiểm tính cần thiết:** E1 xác định biến động đúng khoản phải thu khách hàng. E2 xác định CFO của cả năm; không thay bằng biến động riêng phải thu trên B03. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0009 — medium — Tiền gửi đầu tư và tiền tương đương tiền

**Câu hỏi:** Theo báo cáo hợp nhất Alphanam E&C tại 31/12/2025, giá trị ghi sổ tiền gửi có kỳ hạn được xếp vào đầu tư nắm giữ đến ngày đáo hạn ngắn hạn lớn hơn hay nhỏ hơn tiền và các khoản tương đương tiền trên bảng cân đối kế toán?

**Gold:** Lớn hơn. Tiền gửi có kỳ hạn trong đầu tư nắm giữ đến ngày đáo hạn ngắn hạn có giá trị ghi sổ 45.560.000.000 VND, còn tiền và các khoản tương đương tiền là 20.977.317.114 VND.

**E1 — `AME_2025_p022_t003`, trang neutral 22; hàng “Tiền gửi có kỳ hạn”; cột “31/12/2025 - Giá trị ghi sổ”.** Xác định đúng loại tiền gửi và giá trị ghi sổ ở B09.

> Đơn vị tính: VND
> ### 2.2. Đầu tư nắm giữ đến ngày đáo hạn
> | Chỉ tiêu | 31/12/2025 - Giá gốc | 31/12/2025 - Giá trị ghi sổ | 01/01/2025 - Giá gốc | 01/01/2025 - Giá trị ghi sổ |
> | --- | --- | --- | --- | --- |
> | Ngắn hạn |  |  |  |  |
> | Tiền gửi có kỳ hạn | 45.560.000.000 | 45.560.000.000 | 42.385.109.769 | 42.385.109.769 |

**E2 — `AME_2025_p007_t001`, trang neutral 7; hàng “I. Tiền và các khoản tương đương tiền”; cột “31/12/2025”.** Cung cấp tổng tiền và tương đương tiền ở B01.

> Tại ngày 31 tháng 12 năm 2025
> Đơn vị tính: VND
> ### Bảng cân đối kế toán hợp nhất
> | TÀI SẢN | MÃ SỐ | THUYẾT MINH | 31/12/2025 | 01/01/2025 |
> | --- | --- | --- | --- | --- |
> | I. Tiền và các khoản tương đương tiền | 110 | V.1 | 20.977.317.114 | 22.946.226.838 |

**Reasoning tham chiếu:**

1. E1: B09, mục đầu tư nắm giữ đến ngày đáo hạn, nhóm Ngắn hạn, ghi giá trị ghi sổ tiền gửi có kỳ hạn tại 31/12/2025 là 45.560.000.000 VND. Không lấy số đầu năm hoặc tự đổi sang nhóm tương đương tiền.
2. E2: B01 hợp nhất ghi tiền và các khoản tương đương tiền cùng ngày là 20.977.317.114 VND.
3. 45.560.000.000 > 20.977.317.114. So sánh hai nhóm trình bày riêng; không cộng khoản tiền gửi đầu tư vào chỉ tiêu tiền và tương đương tiền đã công bố.

**Kiểm tính cần thiết:** E1 xác định đúng loại tiền gửi và giá trị ghi sổ ở B09. E2 cung cấp tổng tiền và tương đương tiền ở B01. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0010 — medium — Mức tập trung giao dịch với bên liên quan

**Câu hỏi:** Trong năm 2025 của Sách và Thiết bị trường học Đà Nẵng, giá trị bán hàng và cung cấp dịch vụ cho bên liên quan DINCO có vượt 5% doanh thu bán hàng và cung cấp dịch vụ trước giảm trừ của toàn Công ty không?

**Gold:** Không. Giá trị bán hàng và cung cấp dịch vụ cho Công ty CP Kỹ thuật Xây dựng DINCO là 1.471.601.409 VND, không vượt 5% doanh thu trước giảm trừ của toàn Công ty là 73.649.215.707 VND.

**E1 — `BED_2025_p038_t003`, trang neutral 38; hàng “Công ty CP Kỹ thuật Xây dựng DINCO”; cột “Năm 2025 (VND)”.** Cung cấp đúng giao dịch doanh thu với DINCO, tách khỏi số dư công nợ.

> ### Giao dịch với các bên liên quan
> | Chỉ tiêu | Năm 2025 (VND) | Năm 2024 (VND) |
> | --- | --- | --- |
> | Bán hàng và cung cấp dịch vụ |  |  |
> | Công ty CP Kỹ thuật Xây dựng DINCO | 1.471.601.409 | 1.534.648.691 |

**E2 — `BED_2025_p010_t001`, trang neutral 10; hàng “1. Doanh thu bán hàng và cung cấp dịch vụ”; cột “Năm 2025”.** Cung cấp mẫu số doanh thu toàn Công ty trước giảm trừ.

> Cho năm tài chính kết thúc ngày 31/12/2025
> Đơn vị tính: VND
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
> | CHỈ TIÊU | Mã số | TM | Năm 2025 | Năm 2024 |
> | --- | --- | --- | --- | --- |
> | 1. Doanh thu bán hàng và cung cấp dịch vụ | 01 | 5.1 | 73.649.215.707 | 79.840.305.533 |

**Reasoning tham chiếu:**

1. E1: trong bảng giao dịch với các bên liên quan, chọn nhóm Bán hàng và cung cấp dịch vụ, dòng DINCO, cột Năm 2025: 1.471.601.409 VND; không lấy số dư phải thu của DINCO hoặc giao dịch mua hàng.
2. E2: B02 ghi doanh thu bán hàng và cung cấp dịch vụ trước giảm trừ năm 2025 là 73.649.215.707 VND; không chọn doanh thu thuần.
3. Kiểm tra ngưỡng không làm tròn: 1.471.601.409 × 100 = 147.160.140.900, nhỏ hơn 73.649.215.707 × 5 = 368.246.078.535. Vì vậy giá trị giao dịch với DINCO không vượt 5% doanh thu được hỏi. Chỉ so các giá trị công bố, không suy rủi ro bên liên quan.

**Kiểm tính cần thiết:** E1 cung cấp đúng giao dịch doanh thu với DINCO, tách khỏi số dư công nợ. E2 cung cấp mẫu số doanh thu toàn Công ty trước giảm trừ. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0011 — medium — Khoản vay ngân hàng lớn nhất và nợ ngắn hạn

**Câu hỏi:** Cuối năm 2025 của Vicem Bao bì Bút Sơn, ngân hàng nào có dư nợ cho vay lớn nhất trong thuyết minh và khoản này có vượt một nửa tổng nợ ngắn hạn trên bảng cân đối kế toán không?

**Gold:** Ngân hàng TMCP Ngoại thương Việt Nam – Chi nhánh Nam Định có dư nợ lớn nhất, 42.405.101.215 VND. Khoản này không vượt một nửa tổng nợ ngắn hạn 157.146.559.558 VND.

**E1 — `BBS_2025_p018_t001`, trang neutral 18; hàng “Ngân hàng TMCP Ngoại thương Việt Nam”; cột “31/12/2025 - Giá trị (VND)”.** Xếp hạng dư nợ và nối tên ngân hàng với dòng chi nhánh trong B09.

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

**E2 — `BBS_2025_p006_t001`, trang neutral 6; hàng “I. Nợ ngắn hạn”; cột “31/12/2025”.** Cung cấp tổng nợ ngắn hạn, mẫu số không có trong bảng vay B09.

> Đơn vị tính: VND
> Tại ngày 31 tháng 12 năm 2025
> ### BẢNG CÂN ĐỐI KẾ TOÁN (Tiếp theo)
> | CHỈ TIÊU | Mã số | Thuyết minh | 31/12/2025 | 01/01/2025 |
> | --- | --- | --- | --- | --- |
> | I. Nợ ngắn hạn | 310 |  | 157.146.559.558 | 183.476.510.255 |

**Reasoning tham chiếu:**

1. E1: đối chiếu các số dư tại 31/12/2025 trong B09: Ngoại thương 42.405.101.215 VND > Công thương 35.528.793.127 VND > Đầu tư và Phát triển 29.962.860.942 VND. Shinhan trình bày dấu gạch ngang; không chuyển dấu đó thành số Gold. Dòng ngay sau Ngoại thương định vị Chi nhánh Nam Định (2).
2. E2: B01 ghi tổng nợ ngắn hạn tại cùng ngày là 157.146.559.558 VND. Đây là tổng nợ ngắn hạn, không phải riêng tổng vay ngắn hạn.
3. 42.405.101.215 × 2 = 84.810.202.430 < 157.146.559.558 nên khoản vay lớn nhất không vượt một nửa tổng nợ ngắn hạn.

**Kiểm tính cần thiết:** E1 xếp hạng dư nợ và nối tên ngân hàng với dòng chi nhánh trong B09. E2 cung cấp tổng nợ ngắn hạn, mẫu số không có trong bảng vay B09. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0012 — medium — Đối chiếu tổng nợ hai năm, cùng phạm vi

**Câu hỏi:** Đối chiếu báo cáo tài chính hợp nhất năm 2021 và năm 2024 của Xi măng Bỉm Sơn, tổng nợ phải trả tại 31/12/2024 tăng hay giảm bao nhiêu so với tại 31/12/2021?

**Gold:** Tổng nợ phải trả giảm 122.161.122.063 VND, từ 1.757.744.055.173 VND tại 31/12/2021 xuống 1.635.582.933.110 VND tại 31/12/2024.

**E1 — `BCC_2021_p009_t001`, trang neutral 9; hàng “C. NỢ PHẢI TRẢ”; cột “Số cuối năm”.** Cung cấp mốc tổng nợ cuối năm 2021.

> Tại ngày 31 tháng 12 năm 2021
> Đơn vị: VND
> ### BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT (Tiếp theo)
> | NGUỒN VỐN | Mã số | Thuyết minh | Số cuối năm | Số đầu năm |
> | --- | --- | --- | --- | --- |
> | C. NỢ PHẢI TRẢ | 300 |  | 1.757.744.055.173 | 2.012.132.904.102 |

**E2 — `BCC_2024_p010_t001`, trang neutral 10; hàng “C. NỢ PHẢI TRẢ”; cột “Số cuối năm”.** Cung cấp mốc tổng nợ cuối năm 2024 của cùng phạm vi hợp nhất.

> Tại ngày 31 tháng 12 năm 2024
> ### Đơn vị: VND
> ### BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT
> | NGUỒN VỐN | Mã số | Thuyết minh | Số cuối năm | Số đầu năm |
> | --- | --- | --- | --- | --- |
> | C. NỢ PHẢI TRẢ | 300 |  | 1.635.582.933.110 | 1.871.791.299.592 |

**Reasoning tham chiếu:**

1. E1: trong B01 hợp nhất năm 2021, cột Số cuối năm là tại 31/12/2021, tổng nợ phải trả 1.757.744.055.173 VND.
2. E2: trong B01 hợp nhất năm 2024, cột Số cuối năm là tại 31/12/2024, tổng nợ phải trả 1.635.582.933.110 VND. Hai nguồn đều là hợp nhất và trình bày VND; không lấy cột đầu năm.
3. 1.635.582.933.110 - 1.757.744.055.173 = -122.161.122.063 VND, tức giảm 122.161.122.063 VND giữa hai mốc. Không suy xu hướng giảm liên tục trong các năm ở giữa hoặc nguyên nhân do vay/trả nợ.

**Kiểm tính cần thiết:** E1 cung cấp mốc tổng nợ cuối năm 2021. E2 cung cấp mốc tổng nợ cuối năm 2024 của cùng phạm vi hợp nhất. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0013 — hard — Đối chiếu cổ tức phân phối, thực trả và phải trả

**Câu hỏi:** Ở báo cáo riêng năm 2025 của Xuất nhập khẩu Hàng không, về mặt số học, phần chênh giữa cổ tức đã chia trong thuyết minh và cổ tức, lợi nhuận đã thực trả trên báo cáo lưu chuyển tiền tệ có khớp với mức tăng số dư cổ tức, lợi nhuận phải trả từ đầu đến cuối năm không?

**Gold:** Có, hai chênh lệch đều là 83.719.700 VND. Cổ tức đã chia 3.111.283.000 VND trừ tiền cổ tức, lợi nhuận đã trả 3.027.563.300 VND bằng mức tăng khoản phải trả từ 289.976.614 VND lên 373.696.314 VND.

**E1 — `ARM_2025_p028_t002`, trang neutral 28; hàng “Cổ tức đã chia”; cột “Năm 2025 (VND)”.** Cung cấp cổ tức đã chia trong năm.

> Cho năm tài chính kết thúc ngày 31/12/2025
> ### Các giao dịch về vốn với chủ sở hữu và phân phối cổ tức, chia lợi nhuận
> | Chỉ tiêu | Năm 2025 (VND) | Năm 2024 (VND) |
> | --- | --- | --- |
> | Cổ tức đã chia | 3.111.283.000 | 3.111.283.000 |

**E2 — `ARM_2025_p012_t001`, trang neutral 12; hàng “6. Cổ tức, lợi nhuận đã trả cho chủ sở hữu”; cột “Năm 2025”.** Cung cấp dòng tiền thực trả trong năm.

> Cho năm tài chính kết thúc ngày 31/12/2025
> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ
> | CHỈ TIÊU | Mã số | Thuyết minh | Năm 2025 | Năm 2024 |
> | --- | --- | --- | --- | --- |
> | 6. Cổ tức, lợi nhuận đã trả cho chủ sở hữu | 36 |  | (3.027.563.300) | (3.164.477.300) |

Nguồn đơn vị cùng `ARM_2025`, trang 14:

> Báo cáo tài chính kèm theo được trình bày bằng Đồng Việt Nam (VND).

**E3 — `ARM_2025_p025_t002`, trang neutral 25; hàng “- Cổ tức, lợi nhuận phải trả”; cột “Số cuối năm (31/12/2025)”.** Cung cấp hai số dư phải trả để kiểm chênh lệch độc lập.

> Cho năm tài chính kết thúc ngày 31/12/2025
> ### 5.14. Phải trả khác
> | Chỉ tiêu | Số cuối năm (31/12/2025) | Số đầu năm (01/01/2025) |
> | --- | --- | --- |
> | Ngắn hạn | 77.502.849.068 | 63.637.379.780 |
> | - Cổ tức, lợi nhuận phải trả | 373.696.314 | 289.976.614 |

Nguồn đơn vị cùng `ARM_2025`, trang 14:

> Báo cáo tài chính kèm theo được trình bày bằng Đồng Việt Nam (VND).

**Reasoning tham chiếu:**

1. E1: B09 ghi Cổ tức đã chia năm 2025 là 3.111.283.000 VND; đây là số phân phối, không tự coi là tiền đã ra.
2. E2: B03 ghi Cổ tức, lợi nhuận đã trả cho chủ sở hữu là (3.027.563.300) VND. Độ lớn tiền chi là 3.027.563.300 VND. Tính phần chưa bằng tiền: 3.111.283.000 - 3.027.563.300 = 83.719.700 VND.
3. E3: B09 nhóm phải trả ngắn hạn ghi Cổ tức, lợi nhuận phải trả cuối năm là 373.696.314 VND và đầu năm là 289.976.614 VND. Tính mức tăng: 373.696.314 - 289.976.614 = 83.719.700 VND.
4. Hai kết quả bằng nhau: 83.719.700 VND. Đây là đối chiếu số học giữa phân phối, tiền chi và số dư, không xác nhận lịch thanh toán hay nguyên nhân từng giao dịch.

**Kiểm tính cần thiết:** E1 cung cấp cổ tức đã chia trong năm. E2 cung cấp dòng tiền thực trả trong năm. E3 cung cấp hai số dư phải trả để kiểm chênh lệch độc lập. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0014 — hard — Chiều biến động trong hai báo cáo hợp nhất

**Câu hỏi:** Xét hai năm 2022 và 2024 của Xi măng Bỉm Sơn theo báo cáo hợp nhất từng năm, năm nào có doanh thu thuần và dòng tiền thuần từ hoạt động kinh doanh biến động trái chiều, khi mỗi chỉ tiêu được so với kỳ so sánh trong chính báo cáo năm đó?

**Gold:** Không năm nào trong hai năm này có biến động trái chiều. Năm 2022, doanh thu thuần giảm từ 4.330.051.249.712 VND xuống 4.218.317.356.885 VND và CFO giảm từ 424.221.921.072 VND xuống 178.149.035.829 VND theo cột so sánh trình bày lại. Năm 2024, doanh thu thuần tăng từ 3.081.365.372.469 VND lên 3.487.978.470.438 VND và CFO tăng từ 28.673.341.455 VND lên 202.642.595.052 VND.

**E1 — `BCC_2022_p009_t001`, trang neutral 9; hàng “3. Doanh thu thuần về bán hàng (10=01-02)”; cột “Năm nay”.** Kiểm chiều doanh thu năm 2022 theo kỳ so sánh trình bày lại.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2022
> Đơn vị: VND
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT
> | CHỈ TIÊU | Mã số | Thuyết minh | Năm nay | Năm trước (Trình bày lại) |
> | --- | --- | --- | --- | --- |
> | 3. Doanh thu thuần về bán hàng (10=01-02) | 10 | 24 | 4.218.317.356.885 | 4.330.051.249.712 |

**E2 — `BCC_2022_p010_t001`, trang neutral 10; hàng “Lưu chuyển tiền thuần từ hoạt động kinh doanh”; cột “Năm nay”.** Kiểm chiều CFO năm 2022 theo kỳ so sánh trình bày lại.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2022
> Đơn vị: VND
> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ HỢP NHẤT
> | CHỈ TIÊU | Mã số | Năm nay | Năm trước (Trình bày lại) |
> | --- | --- | --- | --- |
> | Lưu chuyển tiền thuần từ hoạt động kinh doanh | 20 | 178.149.035.829 | 424.221.921.072 |

**E3 — `BCC_2024_p011_t001`, trang neutral 11; hàng “3. Doanh thu thuần về bán hàng (10=01)”; cột “Năm nay”.** Kiểm chiều doanh thu năm 2024.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024
> Đơn vị: VND
> ### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH HỢP NHẤT
> | CHỈ TIÊU | Mã số | Thuyết minh | Năm nay | Năm trước |
> | --- | --- | --- | --- | --- |
> | 3. Doanh thu thuần về bán hàng (10=01) | 10 | 24 | 3.487.978.470.438 | 3.081.365.372.469 |

**E4 — `BCC_2024_p012_t001`, trang neutral 12; hàng “Lưu chuyển tiền thuần từ hoạt động kinh doanh”; cột “Năm nay”.** Kiểm chiều CFO năm 2024.

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

**Kiểm tính cần thiết:** E1 kiểm chiều doanh thu năm 2022 theo kỳ so sánh trình bày lại. E2 kiểm chiều CFO năm 2022 theo kỳ so sánh trình bày lại. E3 kiểm chiều doanh thu năm 2024. E4 kiểm chiều CFO năm 2024. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

### VFB-MH-0015 — hard — CFO so với thiếu hụt vốn lưu động ròng

**Câu hỏi:** Theo báo cáo riêng năm 2025 của Xi măng Vicem Bút Sơn, về độ lớn, dòng tiền thuần từ hoạt động kinh doanh cả năm có vượt phần nợ ngắn hạn lớn hơn tài sản ngắn hạn tại 31/12/2025 không?

**Gold:** Không. Nợ ngắn hạn cuối năm 1.817.395.016.125 VND vượt tài sản ngắn hạn 820.530.328.188 VND một khoản 996.864.687.937 VND. CFO cả năm dương 196.111.084.304 VND, nhỏ hơn khoản chênh này 800.753.603.633 VND.

**E1 — `BTS_2025_p010_t001`, trang neutral 10; hàng “A. TÀI SẢN NGẮN HẠN”; cột “Số cuối năm”.** Cung cấp tài sản ngắn hạn cuối năm.

> Tại ngày 31 tháng 12 năm 2025
> Đơn vị: VNĐ
> ### BẢNG CÂN ĐỐI KẾ TOÁN
> | TÀI SẢN | Mã số | Thuyết minh | Số cuối năm | Số đầu năm |
> | --- | --- | --- | --- | --- |
> | A. TÀI SẢN NGẮN HẠN | 100 |  | 820.530.328.188 | 689.906.675.242 |

**E2 — `BTS_2025_p011_t001`, trang neutral 11; hàng “I. Nợ ngắn hạn”; cột “Số cuối năm”.** Cung cấp nợ ngắn hạn cuối năm để tính phần vượt.

> Tại ngày 31 tháng 12 năm 2025
> Đơn vị: VND
> ### BẢNG CÂN ĐỐI KẾ TOÁN
> | NGUỒN VỐN | Mã số | Thuyết minh | Số cuối năm | Số đầu năm |
> | --- | --- | --- | --- | --- |
> | I. Nợ ngắn hạn | 310 |  | 1.817.395.016.125 | 1.851.433.035.964 |

**E3 — `BTS_2025_p013_t001`, trang neutral 13; hàng “Lưu chuyển tiền thuần từ hoạt động kinh doanh”; cột “Năm nay”.** Cung cấp CFO cả năm để so với phần vượt đã tính.

> Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
> Đơn vị: VND
> ### BÁO CÁO LƯU CHUYỂN TIỀN TỆ
> | CHỈ TIÊU | Mã số | Năm nay | Năm trước |
> | --- | --- | --- | --- |
> | Lưu chuyển tiền thuần từ hoạt động kinh doanh | 20 | 196.111.084.304 | 145.726.718.525 |

**Reasoning tham chiếu:**

1. E1 và E2: lấy đúng hai số dư cuối năm 2025, tài sản ngắn hạn 820.530.328.188 VND và nợ ngắn hạn 1.817.395.016.125 VND. Tính phần nợ ngắn hạn vượt tài sản ngắn hạn: 1.817.395.016.125 - 820.530.328.188 = 996.864.687.937 VND. Không thay tài sản ngắn hạn bằng tổng tài sản hoặc nợ ngắn hạn bằng tổng nợ.
2. E3: B03 riêng ghi CFO năm nay (2025) là 196.111.084.304 VND > 0.
3. So độ lớn: 196.111.084.304 < 996.864.687.937. Tính chênh: 996.864.687.937 - 196.111.084.304 = 800.753.603.633 VND. CFO không vượt phần thiếu hụt vốn lưu động ròng cuối năm.
4. Đây là so sánh dòng tiền tạo trong năm với chênh lệch số dư tại thời điểm cuối năm; không coi CFO là tiền còn sẵn để chi trả hoặc tự kết luận khả năng thanh toán.

**Kiểm tính cần thiết:** E1 cung cấp tài sản ngắn hạn cuối năm. E2 cung cấp nợ ngắn hạn cuối năm để tính phần vượt. E3 cung cấp CFO cả năm để so với phần vượt đã tính. Bỏ một Evidence sẽ thiếu ít nhất một giá trị hoặc một phần bắt buộc của Gold; không có một quote đơn lẻ chứa đủ đáp án.

## 5. Validation đã thực hiện

Chỉ chạy focused checks bằng Python local, không tạo runner/test framework trong repository:

| Kiểm tra | Kết quả / phạm vi |
| --- | --- |
| JSONL parse UTF-8, số dòng và ID | PASS: 15 dòng, 15 ID duy nhất và liên tục |
| Độ khó / kiểu câu | PASS: 5/7/3; natural/formal 10/5 |
| Schema Multi-hop và cấu trúc Answer/Evidence v1 | PASS: đúng tập key/kiểu; answer text có key_points; mỗi QA ≥2 Evidence và reasoning không rỗng |
| Định vị nguồn | PASS: 34/34 Evidence khớp document/page/table; header, nhãn và toàn bộ hàng khớp tables.json và document.md; các dòng quote là dòng nguồn theo thứ tự |
| Đơn vị / kỳ / phạm vi | PASS trong corpus: số tiền VND theo bảng/trang hoặc câu xác nhận đơn vị trình bày; bốn tham chiếu đơn vị phụ (0004 E2, 0005 E1, 0013 E2/E3); không dùng chính sách tiền tệ ghi sổ thay cho đơn vị trình bày |
| Phép tính và kết luận | PASS: tính lại từ ô nguồn; so dấu/độ lớn dòng tiền đúng; ngưỡng không làm tròn; chênh lệch cổ tức và vốn lưu động ròng khớp Gold |
| Logic Multi-hop | Đọc lại 15/15 mẫu: từng Evidence có vai trò thiết yếu đối với Gold đầy đủ; không tách hai câu độc lập hoặc lặp cùng fact để đủ hop |
| Trùng câu / ý | 0 câu trùng chính xác; đọc lại không thấy cặp trùng suy luận và cùng fact/kỳ. Cùng chủ đề tiền-vay/chiều biến động ở doanh nghiệp khác vẫn giữ khi khác chỉ tiêu, phạm vi hoặc thao tác liên kết |
| Giới hạn kết luận | Đọc lại 15/15: chỉ mô tả so sánh/điều kiện/khớp số học; không gán nhân quả, khả năng thanh toán hoặc sức khỏe tài chính tổng thể |
| Bảo toàn | PASS: đối chiếu hash các file ViFinBench có sẵn và file local đã sửa trước task; không đổi các nguồn/dataset/planning/runtime đó |
| Diff | PASS: `git diff --check`, gồm kiểm riêng hai deliverables được stage |

Không sửa planning nên không chạy planning checker. Không chạy full CI, benchmark, Gemini, Qwen, OCR hoặc API trả phí; không tải PDF/tìm PNG. Validation ở đây là cấu trúc, đối chiếu neutral và tự kiểm logic biên soạn, không phải điểm chất lượng tài chính của mô hình.

## 6. Hạn chế và điểm chờ review

- Độ khó là nhãn sơ bộ; 15 mẫu tập trung so sánh mô tả, điều kiện và đối chiếu số học. Cả 15 đáp án là text; chưa đại diện mọi dạng câu Multi-hop, chưa đo lợi ích Multi-Agent hoặc hiệu chỉnh bằng mô hình.
- 15/15 mẫu dùng báo cáo chính, 4/15 nối B09; chưa có mẫu bảng–văn bản làm hop tài chính chính. Nguồn đơn vị phụ không được tính là mẫu bảng–văn bản. Không ép thêm loại này khi brief không đặt quota riêng.
- 0001/0002/0005 cố ý so số phát sinh năm với số dư cuối năm và nói rõ hai loại. Tech Lead cần xem độ hữu ích của các so sánh Easy này cho benchmark; không diễn giải thành vòng quay, mức tăng nợ hoặc thước đo hiệu quả.
- 0009 giữ tiền gửi đầu tư tách khỏi tiền và tương đương tiền; 0010 dùng doanh thu trước giảm trừ và đúng giao dịch DINCO, không lấy số dư công nợ; 0011 dùng tổng nợ ngắn hạn, không dùng tổng vay ngắn hạn. Đây là các điểm phân loại cần giữ khi nghiệm thu.
- 0013 chỉ chứng minh hai chênh lệch bằng nhau về số học. Không khẳng định đã chứng minh đầy đủ diễn biến/nguồn gốc từng giao dịch cổ tức.
- 0014 dùng chính cột so sánh **trình bày lại** năm 2021 trong báo cáo 2022; không thay bằng số gốc năm 2021 ở tài liệu khác. 0012 là đối chiếu tổng nợ hai mốc cuối 2021/cuối 2024, không khẳng định xu hướng liên tục. Các ô được chọn không có mâu thuẫn trực tiếp giữa Markdown và JSON; lỗi OCR ở khoản mục khác không làm chứng cứ cho Gold.
- Chưa kiểm PDF scan độc lập, chưa có human review hoặc mô hình evaluation. Việc gắn nhãn Gold/validation PASS không nâng độ tin cậy vượt corpus neutral và lượt tự kiểm này.

**Next action duy nhất:** Tech Lead review và nghiệm thu 15 Multi-hop QA Pilot tại REVIEW trước khi giao mở rộng; không tự tạo Full Multi-hop hoặc Numerical.
