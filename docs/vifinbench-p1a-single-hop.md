# ViFinBench-P1A-Refine — Single-hop QA Pilot

Ngày thực hiện: **13/11/2026** (Asia/Bangkok). Trạng thái: **REVIEW**.
Dataset: [pilot.jsonl](../ViFinBench/benchmark/single_hop/pilot.jsonl).
Bản P1A trước refinement được giữ trong [commit 5f2531f](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/5f2531f8dfaaa4f999a4b90739d9ced6237fae97); mapping bên dưới so với bản đó.

## 1. Kết quả và quy tắc biên soạn

Đọc lại toàn bộ 15 mẫu cũ, báo cáo P1A và các trang neutral được dùng; đánh giá câu hỏi, thông tin đích, độ khó và khả năng đoán bằng kiến thức chung trước khi chuyển schema. Kết quả: **15 QA, 5 Easy / 7 Medium / 3 Hard; 10 natural / 5 formal; 1 KEEP / 11 REWRITE / 3 REPLACE**. Dùng **12 doanh nghiệp / 12 tài liệu / 15 trang**, tối đa hai câu mỗi tài liệu; năm 2021: 2, 2023: 4, 2024: 2, 2025: 7. Có B01/B02/B03/B09, **10 bằng chứng bảng / 5 bằng chứng văn bản**, đáp án 10 number / 3 text / 1 date / 1 entity.

KEEP giữ câu hỏi và thông tin đích; vẫn chuyển schema và bổ sung ngữ cảnh bằng chứng. REWRITE giữ thông tin đích nhưng viết lại câu và bằng chứng. REPLACE thay thông tin cần hỏi. ID được giữ để dễ đối chiếu, không hàm ý nội dung cũ bất biến.

Mỗi mẫu lấy đáp án từ một hàng/ô hoặc một đoạn của cùng hợp đồng/thuyết minh. Không có phép tính mới hay kết hợp nhiều bằng chứng độc lập. Với bảng, quote là **trích chọn các dòng nguyên văn theo thứ tự nguồn**: ngữ cảnh cần thiết, header đầy đủ, dòng phân cách, hàng phân nhóm nếu có và toàn bộ hàng chứa đáp án. Các hàng không liên quan được lược bỏ, không nối thành một trích dẫn liên tục giả định, không dùng dấu ba chấm. `row_label`/`column_header` giữ nhãn JSON; xuống dòng trong header JSON tương ứng dấu cách ở Markdown.

Không gán ngành nghề/phạm vi bằng suy đoán. Nguồn BCC_2024 và ALT_2023 ghi rõ hợp nhất. Đơn vị VND được đọc từ trang/bảng hoặc chính sách tiền tệ trong báo cáo: AMC_2021 trang 11, ALT_2023 trang 14, CAG_2025 trang 13. Đây là ngữ cảnh đơn vị, không ghép dữ kiện để tạo đáp án. Số trang là trang neutral, không thêm page_printed.

## 2. Tổng hợp bộ QA mới

| ID | Doanh nghiệp | Năm | Độ khó | Style | Chủ đề |
| --- | --- | --- | --- | --- | --- |
| VFB-SH-0001 | Vicem Bao bì Bút Sơn | 2025 | easy | natural | Tổng tài sản (B01) |
| VFB-SH-0002 | Khoáng sản Á Châu | 2021 | easy | formal | Doanh thu thuần (B02) |
| VFB-SH-0003 | Mĩ thuật và Truyền thông | 2021 | easy | natural | Đơn vị kiểm toán |
| VFB-SH-0004 | Xi măng Bỉm Sơn | 2024 | easy | formal | Dòng tiền kinh doanh hợp nhất (B03) |
| VFB-SH-0005 | Cảng An Giang | 2025 | easy | natural | Nhân sự cuối năm (B09) |
| VFB-SH-0006 | Sách và Thiết bị trường học Đà Nẵng | 2025 | medium | natural | Thời gian khấu hao máy móc (B09) |
| VFB-SH-0007 | Cấp nước Bến Thành | 2025 | medium | natural | Tài sản và mục đích thuê thực tế (B09) |
| VFB-SH-0008 | Vicem Bao bì Bỉm Sơn | 2025 | medium | formal | Giá trị hợp lý chứng khoán (B09) |
| VFB-SH-0009 | Xuất nhập khẩu Hàng không | 2023 | medium | natural | Công nợ ủy thác với ROHR (B09) |
| VFB-SH-0010 | Văn hóa Tân Bình | 2023 | medium | formal | Thuế hiện hành tại công ty mẹ (B09) |
| VFB-SH-0011 | Tập đoàn Đầu tư ATS | 2024 | medium | natural | Ngày hết hạn phụ lục thuê văn phòng (B09) |
| VFB-SH-0012 | Cảng An Giang | 2025 | medium | natural | Tiền cho thuê sẽ thu trên 5 năm (B09) |
| VFB-SH-0013 | Vicem Bao bì Bút Sơn | 2025 | hard | natural | Hai giới hạn thời gian cấp hạn mức (B09) |
| VFB-SH-0014 | Khoáng sản Bắc Kạn | 2023 | hard | natural | Hạn mức tín dụng sau sửa đổi (B09) |
| VFB-SH-0015 | Văn hóa Tân Bình | 2023 | hard | formal | Hao mòn lũy kế theo nhóm tài sản (B09) |

## 3. Đối chiếu 15 mẫu cũ và mới

| ID cũ → mới | Xử lý | Nội dung cũ | Thay đổi / căn cứ |
| --- | --- | --- | --- |
| VFB-SH-0001 → cùng ID | REWRITE | Tổng tài sản | Rút gọn câu hỏi; giữ chỉ tiêu có hai giá trị kỳ khác nhau; đưa header/đơn vị vào quote. |
| VFB-SH-0002 → cùng ID | REWRITE | Doanh thu thuần | Giữ thuật ngữ chính thức, bỏ cấu trúc câu dài; quote gắn Năm nay với năm 2021. |
| VFB-SH-0003 → cùng ID | KEEP | Tên kiểm toán | Câu hỏi sẵn rõ, tên kiểm toán đặc thù; giữ nguyên câu và thông tin đích, chuyển schema bắt buộc. |
| VFB-SH-0004 → cùng ID | REWRITE | Dòng tiền kinh doanh hợp nhất | Giữ phạm vi hợp nhất và tên chỉ tiêu; bổ sung header cùng ngữ cảnh năm/đơn vị. |
| VFB-SH-0005 → cùng ID | REPLACE | Cổ phiếu lưu hành, hai kỳ bằng nhau | Thay cổ phiếu 13.800.000 ở cả hai kỳ bằng nhân sự 120 cuối năm / 119 đầu năm trong một câu nguồn. |
| VFB-SH-0006 → cùng ID | REPLACE | Bình quân gia quyền / kê khai thường xuyên | Thay chính sách tồn kho phổ biến bằng khoảng khấu hao cụ thể doanh nghiệp công bố; giữ đủ hai đầu khoảng. |
| VFB-SH-0007 → cùng ID | REPLACE | Quy tắc ghi nhận doanh thu dịch vụ | Thay quy tắc ghi nhận doanh thu phổ biến bằng hợp đồng thuê mạng lưới cấp nước riêng của doanh nghiệp. |
| VFB-SH-0008 → cùng ID | REWRITE | Giá trị hợp lý cổ phiếu | Viết gọn nhưng giữ cơ sở giá trị hợp lý; quote có tiêu đề ngày để phân biệt hai bảng cùng header. |
| VFB-SH-0009 → cùng ID | REWRITE | Phải trả ROHR về ủy thác | Bỏ việc chép đường dẫn thuyết minh vào câu hỏi; giữ nhóm Ngắn hạn / Phải trả bên thứ ba / ủy thác trong quote. |
| VFB-SH-0010 → cùng ID | REWRITE | Thuế hiện hành công ty mẹ | Rút gọn câu hỏi, giữ phần công ty mẹ trong BCTC hợp nhất; thêm header và phạm vi vào quote. |
| VFB-SH-0011 → cùng ID | REWRITE | Ngày hết gia hạn thuê văn phòng | Hỏi trực tiếp ngày hết gia hạn; chuẩn hóa ISO và giữ ngày ký/ngày bắt đầu trong nguồn để tránh nhầm. |
| VFB-SH-0012 → cùng ID | REWRITE | Tiền thuê sẽ thu trên 5 năm | Làm rõ dòng tiền sẽ thu và phần thời hạn, tránh hiểu thành tiền phải trả hoặc tổng mọi kỳ của hợp đồng trên 5 năm. |
| VFB-SH-0013 → cùng ID | REWRITE | Thời gian cấp hạn mức Vietcombank | Bỏ mã hợp đồng dài khỏi câu hỏi, vẫn định danh được theo ngân hàng/ngày; key_points bắt buộc đủ hai điều kiện. |
| VFB-SH-0014 → cùng ID | REWRITE | Hạn mức sau sửa đổi VietinBank | Hỏi hạn mức sau sửa đổi bằng ngôn ngữ nhu cầu vay vốn; giữ số gốc và số sửa đổi trong cùng đoạn trích. |
| VFB-SH-0015 → cùng ID | REWRITE | Hao mòn lũy kế phương tiện vận tải | Bỏ phần dẫn dài, giữ phạm vi hợp nhất; quote đủ header, hàng phân nhóm hao mòn và hàng cuối năm. |

## 4. Câu hỏi, đáp án và bằng chứng

### VFB-SH-0001 — easy / natural

**Câu hỏi:** Cuối năm 2025, tổng tài sản của Vicem Bao bì Bút Sơn là bao nhiêu?

**Đáp án:** 266.086.680.765 VND

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "266086680765", "unit": "VND", "display": "266.086.680.765 VND", "key_points": []}
```

**Nguồn:** [BBS_2025, trang 5](../ViFinBench/neutral/BBS_2025/document.md); bảng `BBS_2025_p005_t001`; hàng `TỔNG CỘNG TÀI SẢN`; cột `31/12/2025`.

```text
Đơn vị tính: VND
| CHỈ TIÊU | Mã số | Thuyết minh | 31/12/2025 | 01/01/2025 |
| --- | --- | --- | --- | --- |
| TỔNG CỘNG TÀI SẢN | 270 |  | 266.086.680.765 | 291.306.659.104 |
```

**Single-hop / độ khó:** Easy: một chỉ tiêu tổng rõ ràng, không cộng các phần tài sản.

### VFB-SH-0002 — easy / formal

**Câu hỏi:** Doanh thu thuần về bán hàng và cung cấp dịch vụ của Khoáng sản Á Châu năm 2021 là bao nhiêu?

**Đáp án:** 157.803.608.857 VND

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "157803608857", "unit": "VND", "display": "157.803.608.857 VND", "key_points": []}
```

**Nguồn:** [AMC_2021, trang 9](../ViFinBench/neutral/AMC_2021/document.md); bảng `AMC_2021_p009_t001`; hàng `2. Doanh thu thuần về bán hàng và cung cấp dịch vụ`; cột `Năm nay`.

```text
### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2021
| CHỈ TIÊU | Mã số | Thuyết minh | Năm nay | Năm trước |
| --- | --- | --- | --- | --- |
| 2. Doanh thu thuần về bán hàng và cung cấp dịch vụ | 10 | VI.1 | 157.803.608.857 | 153.539.180.123 |
```

**Single-hop / độ khó:** Easy: tra trực tiếp mã 10 ở cột năm báo cáo, không tự tính doanh thu thuần.

### VFB-SH-0003 — easy / natural

**Câu hỏi:** Đơn vị nào kiểm toán báo cáo tài chính năm 2021 của Công ty Cổ phần Mĩ thuật và Truyền thông?

**Đáp án:** Công ty TNHH Kiểm toán và Kế toán AAC

**Đáp án chuẩn để chấm:**

```json
{"type": "entity", "value": "Công ty TNHH Kiểm toán và Kế toán AAC", "unit": null, "display": "Công ty TNHH Kiểm toán và Kế toán AAC", "key_points": []}
```

**Nguồn:** [ADC_2021, trang 7](../ViFinBench/neutral/ADC_2021/document.md); văn bản, `table_id`, `row_label`, `column_header` đều null.

```text
### CÔNG TY CỔ PHẦN MĨ THUẬT VÀ TRUYỀN THÔNG
Cho năm tài chính kết thúc ngày 31/12/2021
### Kiểm toán độc lập
Báo cáo tài chính này được kiểm toán bởi Công ty TNHH Kiểm toán và Kế toán AAC
```

**Single-hop / độ khó:** Easy: tên đơn vị được nêu trực tiếp; không thể xác định chỉ bằng chuẩn mực kế toán.

### VFB-SH-0004 — easy / formal

**Câu hỏi:** Theo báo cáo lưu chuyển tiền tệ hợp nhất năm 2024 của Xi măng Bỉm Sơn, lưu chuyển tiền thuần từ hoạt động kinh doanh là bao nhiêu?

**Đáp án:** 202.642.595.052 VND

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "202642595052", "unit": "VND", "display": "202.642.595.052 VND", "key_points": []}
```

**Nguồn:** [BCC_2024, trang 12](../ViFinBench/neutral/BCC_2024/document.md); bảng `BCC_2024_p012_t001`; hàng `Lưu chuyển tiền thuần từ hoạt động kinh doanh`; cột `Năm nay`.

```text
### BÁO CÁO LƯU CHUYỂN TIỀN TỆ HỢP NHẤT
Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024
Đơn vị: VND
| CHỈ TIÊU | Mã số | Năm nay | Năm trước |
| --- | --- | --- | --- |
| Lưu chuyển tiền thuần từ hoạt động kinh doanh | 20 | 202.642.595.052 | 28.673.341.455 |
```

**Single-hop / độ khó:** Easy: lấy tổng dòng tiền đã công bố, không cộng các dòng điều chỉnh.

### VFB-SH-0005 — easy / natural

**Câu hỏi:** Cuối năm 2025, Cảng An Giang có bao nhiêu nhân viên đang làm việc?

**Đáp án:** 120 nhân viên

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "120", "unit": "employees", "display": "120 nhân viên", "key_points": []}
```

**Nguồn:** [CAG_2025, trang 13](../ViFinBench/neutral/CAG_2025/document.md); văn bản, `table_id`, `row_label`, `column_header` đều null.

```text
### CÔNG TY CỔ PHẦN CẢNG AN GIANG
Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
- 6. Nhân viên
Tại ngày kết thúc năm tài chính Công ty có 120 nhân viên đang làm việc (số đầu năm là 119 nhân viên).
```

**Single-hop / độ khó:** Easy: số nhân sự cuối năm được nói rõ, có số đầu năm khác để kiểm tra đúng kỳ.

### VFB-SH-0006 — medium / natural

**Câu hỏi:** Theo báo cáo tài chính năm 2025, Sách và Thiết bị trường học Đà Nẵng ước tính thời gian khấu hao máy móc thiết bị trong khoảng bao nhiêu năm?

**Đáp án:** Từ 2 đến 7 năm

**Đáp án chuẩn để chấm:**

```json
{"type": "text", "value": "Từ 2 đến 7 năm", "unit": "years", "display": "Từ 2 đến 7 năm", "key_points": ["Thời gian tối thiểu 2 năm", "Thời gian tối đa 7 năm"]}
```

**Nguồn:** [BED_2025, trang 15](../ViFinBench/neutral/BED_2025/document.md); bảng `BED_2025_p015_t001`; hàng `Máy móc thiết bị`; cột `Năm 2025`.

```text
### 3.6. Tài sản cố định hữu hình
### Thời gian khấu hao ước tính
| Nhóm tài sản | Năm 2025 |
| --- | --- |
| Máy móc thiết bị | 02 – 07 năm |
```

**Single-hop / độ khó:** Medium: xác định ước tính của đúng nhóm máy móc trong chính sách tài sản hữu hình, phân biệt với nhà cửa, vận tải và dụng cụ quản lý.

### VFB-SH-0007 — medium / natural

**Câu hỏi:** Năm 2025, Cấp nước Bến Thành thuê tài sản gì của Tổng Công ty Cấp nước Sài Gòn theo hợp đồng 2703/HĐ-TCT-KTTC, và dùng vào mục đích nào?

**Đáp án:** Mạng lưới cấp nước do Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư, để cung cấp nước sạch trên địa bàn của Công ty.

**Đáp án chuẩn để chấm:**

```json
{"type": "text", "value": "Mạng lưới cấp nước do Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư, để cung cấp nước sạch trên địa bàn của Công ty.", "unit": null, "display": "Mạng lưới cấp nước do Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư, để cung cấp nước sạch trên địa bàn của Công ty.", "key_points": ["Mạng lưới cấp nước do Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư", "Sử dụng để cung cấp nước sạch trên địa bàn của Công ty"]}
```

**Nguồn:** [BTW_2025, trang 43](../ViFinBench/neutral/BTW_2025/document.md); văn bản, `table_id`, `row_label`, `column_header` đều null.

```text
### CÔNG TY CỔ PHẦN CẤP NƯỚC BẾN THÀNH
Cho năm tài chính kết thúc ngày 31/12/2025
### 35.2 CAM KẾT THUÊ HOẠT ĐỘNG
Theo hợp đồng thuê tài sản hoạt động số 2703/HĐ-TCT-KTTC ngày 09/05/2025, Công ty thuê tài sản là mạng lưới cấp nước của Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư để sử dụng cho mục đích cung cấp nước sạch trên địa bàn của Công ty, với tổng nguyên giá tài sản thuê là 10.010.334.699 đồng, thời hạn thuê từ ngày 01/01/2025 đến ngày 31/12/2025.
```

**Single-hop / độ khó:** Medium: chọn hợp đồng thuê mạng lưới và mục đích sử dụng giữa các cam kết thuê tài sản/đất; cả hai ý cùng một câu nguồn.

### VFB-SH-0008 — medium / formal

**Câu hỏi:** Tại ngày 31/12/2025, giá trị hợp lý của khoản đầu tư cổ phiếu Xi măng Vicem Hoàng Mai tại Vicem Bao bì Bỉm Sơn là bao nhiêu?

**Đáp án:** 936.000.000 VND

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "936000000", "unit": "VND", "display": "936.000.000 VND", "key_points": []}
```

**Nguồn:** [BPC_2025, trang 14](../ViFinBench/neutral/BPC_2025/document.md); bảng `BPC_2025_p014_t002`; hàng `Cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai`; cột `Giá trị hợp lý (VND)`.

```text
### 6. ĐẦU TƯ TÀI CHÍNH NGẮN HẠN - Chứng khoán kinh doanh (Tại ngày 31/12/2025)
| Chỉ tiêu | Giá gốc (VND) | Giá trị hợp lý (VND) | Dự phòng (VND) |
| --- | --- | --- | --- |
| Cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai | 2.952.000.000 | 936.000.000 | (2.016.000.000) |
```

**Single-hop / độ khó:** Medium: chọn bảng cuối năm và cột giá trị hợp lý, phân biệt giá gốc/dự phòng và bảng đầu năm.

### VFB-SH-0009 — medium / natural

**Câu hỏi:** Cuối năm 2023, Xuất nhập khẩu Hàng không (ARM) còn phải trả Công ty ROHR bao nhiêu tiền liên quan đến hoạt động ủy thác?

**Đáp án:** 5.135.627.375 VND

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "5135627375", "unit": "VND", "display": "5.135.627.375 VND", "key_points": []}
```

**Nguồn:** [ARM_2023, trang 25](../ViFinBench/neutral/ARM_2023/document.md); bảng `ARM_2023_p025_t001`; hàng `Công ty ROHR`; cột `Tại ngày 31/12/2023 VND`.

```text
Cho năm tài chính kết thúc ngày 31/12/2023
### 4.13 Phải trả khác
| Chỉ tiêu | Tại ngày 31/12/2023 VND | Tại ngày 01/01/2023 VND |
| --- | --- | --- |
| Ngắn hạn |  |  |
| Phải trả bên thứ ba | 44.122.707.707 | 57.314.586.627 |
| Các khoản phải trả, phải nộp về ủy thác | 42.262.619.187 | 55.566.028.559 |
| Công ty ROHR | 5.135.627.375 | 3.438.628.614 |
```

**Single-hop / độ khó:** Medium: đúng đối tác, phân nhóm công nợ ủy thác và kỳ cuối năm.

### VFB-SH-0010 — medium / formal

**Câu hỏi:** Theo báo cáo tài chính hợp nhất năm 2023 của Văn hóa Tân Bình, chi phí thuế thu nhập doanh nghiệp hiện hành tại Công ty mẹ là bao nhiêu?

**Đáp án:** 1.314.130.355 VND

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "1314130355", "unit": "VND", "display": "1.314.130.355 VND", "key_points": []}
```

**Nguồn:** [ALT_2023, trang 42](../ViFinBench/neutral/ALT_2023/document.md); bảng `ALT_2023_p042_t001`; hàng `Chi phí thuế TNDN hiện hành tại Công ty mẹ`; cột `Năm 2023`.

```text
Báo cáo tài chính hợp nhất Cho năm tài chính kết thúc ngày 31/12/2023
### 32. CHI PHÍ THUẾ THU NHẬP DOANH NGHIỆP HIỆN HÀNH
| Chỉ tiêu | Năm 2023 | Năm 2022 |
| --- | --- | --- |
| Chi phí thuế TNDN hiện hành tại Công ty mẹ | 1.314.130.355 | 2.456.916.173 |
```

**Single-hop / độ khó:** Medium: phân biệt phần công ty mẹ với công ty con, tổng chi phí thuế và số thuế phải nộp.

### VFB-SH-0011 — medium / natural

**Câu hỏi:** Trong báo cáo tài chính năm 2024, ATS cho biết hợp đồng thuê văn phòng TAC 20-F6/11 được gia hạn theo phụ lục số 06 đến ngày nào?

**Đáp án:** 30/06/2025

**Đáp án chuẩn để chấm:**

```json
{"type": "date", "value": "2025-06-30", "unit": null, "display": "30/06/2025", "key_points": []}
```

**Nguồn:** [ATS_2024, trang 22](../ViFinBench/neutral/ATS_2024/document.md); văn bản, `table_id`, `row_label`, `column_header` đều null.

```text
### CÔNG TY CỔ PHẦN TẬP ĐOÀN ĐẦU TƯ ATS
Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024
5.4. Phải thu khác ngắn hạn
(*) Là khoản tiền đặt cọc để thuê văn phòng theo Hợp đồng thuê văn phòng và dịch vụ văn phòng số TAC 20-F6/11 ký ngày 01/07/2020 (kèm theo phụ lục gia hạn hợp đồng số 06 ký ngày 30/05/2024 với thời hạn từ 01/07/2024 đến ngày 30/06/2025) để làm văn phòng giao dịch tại Phòng 608, Tầng 6, Toà nhà Sky City Tower A số 88 Láng Hạ, Quận Đống Đa, Hà Nội.
```

**Single-hop / độ khó:** Medium: tách ngày hết gia hạn khỏi ngày ký hợp đồng gốc, ngày ký phụ lục và ngày bắt đầu.

### VFB-SH-0012 — medium / natural

**Câu hỏi:** Cuối năm 2025, Cảng An Giang công bố sẽ thu tối thiểu bao nhiêu tiền từ các hợp đồng cho thuê hoạt động không thể hủy ngang cho phần thời hạn trên 5 năm?

**Đáp án:** 5.879.280.000 VND

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "5879280000", "unit": "VND", "display": "5.879.280.000 VND", "key_points": []}
```

**Nguồn:** [CAG_2025, trang 30](../ViFinBench/neutral/CAG_2025/document.md); bảng `CAG_2025_p030_t004`; hàng `Trên 05 năm`; cột `Số cuối năm`.

```text
Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
### VII. NHỮNG THÔNG TIN KHÁC
1. Tài sản cho thuê hoạt động
Tại ngày kết thúc năm tài chính, các khoản thanh toán tiền thuê tối thiểu trong tương lai thu được từ các hợp đồng thuê hoạt động không thể hủy ngang như sau:
| Chỉ tiêu | Số cuối năm | Số đầu năm |
| --- | --- | --- |
| Trên 05 năm | 5.879.280.000 | 6.767.280.000 |
```

**Single-hop / độ khó:** Medium: phân biệt bên cho thuê với bên đi thuê, đúng nhóm trên 5 năm và cột cuối năm.

### VFB-SH-0013 — hard / natural

**Câu hỏi:** Trong báo cáo tài chính năm 2025, Vicem Bao bì Bút Sơn cho biết Vietcombank Nam Định giới hạn thời gian cấp hạn mức của hợp đồng ngày 16/06/2025 như thế nào?

**Đáp án:** 13 tháng kể từ ngày 30/05/2025 nhưng không quá 12 tháng kể từ ngày 16/06/2025.

**Đáp án chuẩn để chấm:**

```json
{"type": "text", "value": "13 tháng kể từ ngày 30/05/2025 nhưng không quá 12 tháng kể từ ngày 16/06/2025.", "unit": null, "display": "13 tháng kể từ ngày 30/05/2025 nhưng không quá 12 tháng kể từ ngày 16/06/2025.", "key_points": ["13 tháng kể từ ngày 30/05/2025", "Không quá 12 tháng kể từ ngày 16/06/2025"]}
```

**Nguồn:** [BBS_2025, trang 19](../ViFinBench/neutral/BBS_2025/document.md); bảng `BBS_2025_p019_t001`; hàng `(2) Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Nam Định`; cột `Thời hạn và mục đích vay`.

```text
### Chi tiết các khoản vay ngắn hạn của Công ty tại ngày 31/12/2025
| Ngân hàng | Hợp đồng | Hạn mức (VND) | Thời hạn và mục đích vay | Tài sản đảm bảo |
| --- | --- | --- | --- | --- |
| (2) Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Nam Định | Hợp đồng cấp tín dụng số 01/2025/VCB.NDI/7189524/CTD, ngày 16/06/2025 | 50.000.000.000 | Thời gian cấp hạn mức tín dụng 13 tháng kể từ ngày 30/05/2025 nhưng không quá 12 tháng kể từ ngày 16/06/2025; Mục đích: bổ sung vốn lưu động, bảo lãnh, mở L/C | Tài sản đảm bảo bao gồm: 01 máy tráng màng PP hiệu Starlinger xuất xứ Châu Âu; Toàn bộ máy móc thiết bị hình thành từ vốn vay và vốn tự có theo hợp đồng MMTB số 03/2017/TSĐB/7189524 ngày 15/09/2017; Quyền sở hữu tài sản gắn liền với đất sổ CB 224471; 01 máy dán đáy Starlinger xuất xứ Châu Âu; Dây chuyền thiết bị sản xuất bao dán đáy thương hiệu Starlinger xuất xứ Châu Âu; 08 máy dệt tròn RX 6.0 hiệu Starlinger; Quyền đòi nợ phát sinh từ các hợp đồng kinh tế ký kết với Công ty Cổ phần Xi măng Vicem Hoàng Mai về việc mua bán vỏ bao xi măng, bao Sling Jumbo; Hàng hóa luân chuyển có giá trị tối thiểu bằng số dư cấp tín dụng ngắn hạn tại VietcomBank Nam Định. |
```

**Single-hop / độ khó:** Hard: một ô của bảng hợp đồng rộng chứa hai mốc bắt đầu và hai giới hạn lồng nhau, cạnh các thời hạn ngân hàng khác; không tính ngày hết hạn.

### VFB-SH-0014 — hard / natural

**Câu hỏi:** Theo báo cáo tài chính năm 2023, VietinBank Bắc Kạn đã nâng hạn mức cho Khoáng sản Bắc Kạn lên bao nhiêu sau khi sửa đổi hợp đồng ngày 28/02/2023?

**Đáp án:** 27.000.000.000 VND

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "27000000000", "unit": "VND", "display": "27.000.000.000 VND", "key_points": []}
```

**Nguồn:** [BKC_2023, trang 30](../ViFinBench/neutral/BKC_2023/document.md); văn bản, `table_id`, `row_label`, `column_header` đều null.

```text
Cho năm tài chính kết thúc ngày 31/12/2023
5.18 Vay và nợ thuê tài chính (Tiếp theo)
Hợp đồng cho vay hạn mức số 05/2023-HĐCVHM/NHCT172-KHOANG SAN ngày 28/02/2023 giữa Ngân hàng TMCP Công thương Việt Nam - Chi nhánh Bắc Kạn (Bên cho vay) và Công ty Cổ phần Khoáng sản Bắc Kạn. Hạn mức cho vay 25.000.000.000 VND (Bằng chữ: Hai mươi lăm tỷ đồng Việt Nam) kèm theo văn bản sửa đổi, bổ sung hợp đồng cho vay hạn mức số 05/2023-HĐCVTL-SĐBS1/NHCT172-KHOANG SAN sửa đổi nâng hạn mức thành 27.000.000.000 VND (Bằng chữ: Hai mươi bảy tỷ đồng Việt Nam).
```

**Single-hop / độ khó:** Hard: định vị hợp đồng và văn bản sửa đổi trong danh sách dài nhiều hợp đồng/mã gần giống; phân biệt hạn mức ban đầu 25 tỷ, sau sửa đổi 27 tỷ và dư nợ. Đáp án nằm trong một đoạn, không ghép trang bảng dư nợ.

### VFB-SH-0015 — hard / formal

**Câu hỏi:** Trên báo cáo tài chính hợp nhất năm 2023 của Văn hóa Tân Bình, hao mòn lũy kế cuối năm của nhóm phương tiện vận tải, truyền dẫn là bao nhiêu?

**Đáp án:** 11.137.916.671 VND

**Đáp án chuẩn để chấm:**

```json
{"type": "number", "value": "11137916671", "unit": "VND", "display": "11.137.916.671 VND", "key_points": []}
```

**Nguồn:** [ALT_2023, trang 29](../ViFinBench/neutral/ALT_2023/document.md); bảng `ALT_2023_p029_t001`; hàng `Số dư cuối năm`; cột `Phương tiện vận tải, truyền dẫn VND`.

```text
Báo cáo tài chính hợp nhất
Cho năm tài chính kết thúc ngày 31/12/2023
### 11. TÀI SẢN CỐ ĐỊNH HỮU HÌNH
| Chỉ tiêu | Nhà cửa, vật kiến trúc VND | Máy móc, thiết bị VND | Phương tiện vận tải, truyền dẫn VND | Thiết bị, dụng cụ quản lý VND | Tài sản cố định khác VND | Cộng VND |
| --- | --- | --- | --- | --- | --- | --- |
| Giá trị hao mòn lũy kế |  |  |  |  |  |  |
| Số dư cuối năm | 34.237.017.840 | 94.734.412.454 | 11.137.916.671 | 6.125.564.417 | 231.129.596 | 146.466.040.978 |
```

**Single-hop / độ khó:** Hard: bảng bảy cột, ba phần và nhãn Số dư cuối năm lặp lại; chọn đồng thời phần hao mòn, nhóm tài sản và cuối kỳ, không tính từ biến động.

## 5. Vấn đề đã khắc phục và giới hạn

- Thay 0005 bằng nhân sự cuối năm 120 người, khác số đầu năm 119; không còn thử phân biệt kỳ bằng hai ô cổ phiếu bằng nhau. Các mẫu bảng có hai kỳ được hỏi theo kỳ đều có giá trị so sánh khác nhau: 0001/0002/0004/0009/0010/0012. Mẫu 0008 có hai bảng cùng header nhưng khác ngày và giá trị hợp lý (936.000.000 cuối năm / 692.640.000 đầu năm); quote đã kèm tiêu đề ngày. Mẫu 0015 có nhiều phần/loại giá trị khác nhau. Mẫu 0006 chỉ có một cột năm, kiểm tra nhóm tài sản; không gán độ khó do phân biệt hai kỳ không tồn tại.
- Thay 0006/0007 vì câu cũ quá gần kiến thức chuẩn mực phổ biến. Khoảng khấu hao 2–7 năm của BED và hợp đồng thuê mạng lưới cấp nước của BTW phải tra tài liệu doanh nghiệp. Các mẫu còn lại hỏi số, đơn vị kiểm toán, đối tác, điều khoản hoặc kỳ hạn cụ thể; không dùng câu trả lời theo chuẩn mực làm bằng chứng áp dụng thực tế. Không chạy closed-book test.
- Header, hàng đáp án và phân nhóm cần thiết nằm ngay trong `evidence.quote` của cả 10 mẫu bảng. Mẫu 0009 có phân nhóm ủy thác bên thứ ba; 0015 có hàng hao mòn lũy kế. Mẫu 0012 ghi rõ tiền cho thuê sẽ thu, không dùng bảng tiền thuê phải trả. Mẫu 0013 giữ đủ năm cột của hàng hợp đồng, kể cả danh sách bảo đảm, để không tạo hàng trích bị thiếu ô.
- Chuẩn hóa answer object cho tất cả mẫu: số là string số nguyên không dấu phân cách, ngày đầy đủ dùng ISO; unit tách khỏi value. Text 0006 có hai đầu khoảng, 0007 có tài sản và mục đích, 0013 có hai điều kiện thời gian; key_points đủ các ý này. Không viết evaluator.
- Viết lại 11 câu theo nhu cầu tra cứu; giữ thuật ngữ trong 5 câu formal khi cần đảm bảo ý nghĩa. Natural không có nghĩa bỏ kỳ/phạm vi/đối tác. Không có cặp chỉ thay tên doanh nghiệp hoặc năm; các câu về thuê hỏi lần lượt tài sản/mục đích, ngày hết gia hạn và khoản thu tương lai.
- Tiếp tục tránh các ô/vùng audit có vấn đề: dữ liệu thiếu, bảng ragged/sai ánh xạ, số mâu thuẫn và BCC_2025 không phải bộ BCTC. Không sửa neutral/audit hay lấy số tự tính làm Gold.

Độ khó là đánh giá biên soạn, chưa hiệu chuẩn trên người dùng/mô hình. 0006 ở mức Medium do chọn đúng nhóm/ước tính, không do toán học; 0014 ở mức Hard do truy xuất đoạn hợp đồng dài và thông tin gốc/sửa đổi gần giống, cần Tech Lead xem xét khi hiệu chuẩn. Các trích đoạn cùng xuất phát từ neutral; đối ứng MD/JSON/TXT không phải kiểm chứng nguồn độc lập. Không đối chiếu PNG/PDF mới, không suy độ chính xác toàn corpus từ 15 mẫu. Cơ cấu 7/15 câu năm 2025 và 10/15 bằng chứng bảng vẫn là giới hạn của pilot; không ép cân bằng bằng cách thêm câu kém chất lượng.

## 6. Validation và bàn giao

Focused Python validation local: 15 dòng JSONL parse được, schema đúng; ID tuần tự/duy nhất; difficulty 5/7/3 và style 10/5; số/date chuẩn hóa; 15 document/page và 10 table references tồn tại, khớp JSON/TXT/Markdown; quote bảng đủ header và hàng đáp án; dòng trích nguyên văn theo đúng thứ tự trang, ô đáp án và giá trị so sánh đã đối chiếu. Đáp án text/key_points được đọc lại để kiểm tra đầy đủ ý. Không trùng câu hỏi rõ ràng; kiểm thủ công 15 mẫu về ý nghĩa, kỳ/đơn vị/phạm vi, khả năng đoán bằng kiến thức chung, Single-hop và không tính toán mới. Script không chứng nhận chất lượng ngữ nghĩa hoặc độ khó.

123 file neutral và audit giữ nguyên hash; local changes ngoài task được giữ riêng. Planning checker, Ruff cho checker đã sửa và `git diff --check` được chạy local. Không gọi Gemini/API, không chạy full CI, mô hình thử nghiệm hoặc pipeline DACNTT. Không thêm metadata ngoài schema brief.

Implementation SHA được ghi trong registry sau khi commit hai deliverables. Trạng thái **ViFinBench-P1A-Refine — REVIEW**; lịch sử P1A vẫn giữ trong Git, không tự đổi P1A thành DONE.

**Next action:** Tech Lead review bộ 15 QA đã refine và nghiệm thu P1A-Refine.
