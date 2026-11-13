# ViFinBench-P1A-Finalize — Gold QA Normalization & Schema v1 Freeze

Ngày thực hiện: **13/11/2026** (Asia/Bangkok). Trạng thái: **REVIEW**, chờ Tech Lead nghiệm thu phần chuẩn hóa/schema.
Chất lượng nội dung P1A đã được Tech Lead phê duyệt theo brief Finalize; baseline [d7a5b97](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/d7a5b97f75d0fcd7e1ed08b5d7c7968b539b4a77).

## 1. Kết quả

**15 QA giữ nguyên ID, nội dung cần hỏi, đáp án thực tế và độ khó: 5 Easy / 7 Medium / 3 Hard; 10 natural / 5 formal; 12 doanh nghiệp / 12 tài liệu.** Không tạo lại QA. Chỉ câu 0011 được mở rộng cách gọi ATS thành Công ty Cổ phần Tập đoàn Đầu tư ATS; các tên ARM, BCC/BPC, BBS/BTS còn lại đã tự phân biệt được.

Bổ sung **3 unit_evidence** (0002, 0010, 0012), **2 row_path** (0009, 0015). Chuyển 0006 thành range với min="2", max="7", unit="year", không có value, key_points rỗng; khoảng thực tế và display không đổi. Unit chuẩn: VND→vnd, employees→person, years→year. Các đáp án text 0007/0013 giữ đủ key_points. Phân bố answer mới: **10 number / 1 range / 2 text / 1 date / 1 entity**.

Tạo metadata cho **41/41 tài liệu**, gồm 15 ticker (ATS có hai tên theo thời kỳ); không có company_name/fiscal_year chưa xác minh. Schema v1 được khóa ở mức quy ước dữ liệu; chỉ thay đổi đúng bốn file được giao, không sửa planning, neutral, audit hoặc runtime.

- [Dataset](../ViFinBench/benchmark/single_hop/pilot.jsonl)
- [Document metadata](../ViFinBench/benchmark/document_metadata.json)
- [Schema v1](../ViFinBench/benchmark/SCHEMA.md)

## 2. Bằng chứng đơn vị và đường dẫn hàng

Chín đáp án tiền đều là vnd. Sáu mẫu 0001/0004/0008/0009/0014/0015 đã có VND trong quote chính. Ba mẫu dưới dùng chính sách tiền tệ của cùng tài liệu; kiểm tra header/ngữ cảnh bảng không có chỉ dẫn trình bày triệu/nghìn hoặc đơn vị khác. Unit evidence chỉ xác nhận đơn vị, không bổ sung số liệu để suy ra đáp án.

| QA | Nguồn đơn vị | Nội dung trích nguyên văn |
| --- | --- | --- |
| VFB-SH-0002 | AMC_2021, trang 11 | Báo cáo tài chính kèm theo được trình bày bằng Đồng Việt Nam (VND), theo nguyên tắc giá gốc và phù hợp với Chuẩn mực kế toán, Chế độ kế toán doanh nghiệp Việt Nam và các quy định pháp lý có liên quan đến việc lập và trình bày Báo cáo tài chính. |
| VFB-SH-0010 | ALT_2023, trang 14 | Đơn vị tiền tệ sử dụng trong ghi chép kế toán là đồng Việt Nam (VND). |
| VFB-SH-0012 | CAG_2025, trang 13 | Đơn vị tiền tệ sử dụng trong kế toán là Đồng Việt Nam (VND) do phần lớn các nghiệp vụ được thực hiện bằng đơn vị tiền tệ VND. |

| QA | row_path |
| --- | --- |
| VFB-SH-0009 | Ngắn hạn → Phải trả bên thứ ba → Các khoản phải trả, phải nộp về ủy thác → Công ty ROHR |
| VFB-SH-0015 | Giá trị hao mòn lũy kế → Số dư cuối năm |

Các cấp trên có nhãn thật, theo thứ tự cha–con trong bảng; 0009 giữ cả cấp Ngắn hạn vì nguồn phân biệt ngắn/dài hạn. Các bảng còn lại đã định vị bằng table_id/row_label/column_header; không thêm cấp từ tiêu đề thuyết minh hoặc cấp giả. Hai trường mới hiện diện ở mọi mẫu, dùng null khi không áp dụng. Quote chính, row_label và column_header của cả 15 mẫu không đổi so với baseline.

## 3. Document metadata và căn cứ corpus

Tên được đối chiếu từng tài liệu, chuẩn hóa hoa/thường và khoảng trắng, không đổi chữ trong tên. Alias gồm tên bỏ tiền tố pháp lý và ticker; ticker giữ namespace document_id của corpus, không xác minh lại với sàn chứng khoán. Năm lấy từ kỳ báo cáo trong nội dung, không lấy ngày ký hoặc chỉ dựa tên thư mục. Không tự mang tên/scope ở năm này sang năm khác.

Scope chỉ ghi separate/consolidated khi có tiêu đề BCTC, dòng công bố rõ phạm vi hoặc ô lựa chọn được đánh dấu. Ô không đánh dấu, tiêu đề BCTC chung và câu chuẩn mực nói về hợp nhất không đủ để gán phạm vi. unknown là chưa xác nhận rõ phạm vi, không phải dữ liệu tài chính sai. Cột nguồn ghi trang neutral; các dòng scope được dẫn đủ để kiểm quyết định.

| Document ID | Tên đầy đủ | Trang tên / kỳ | Scope | Căn cứ scope |
| --- | --- | --- | --- | --- |
| ADC_2021 | Công ty Cổ phần Mĩ thuật và Truyền thông | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| ADC_2022 | Công ty Cổ phần Mĩ thuật và Truyền thông | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| ADC_2023 | Công ty Cổ phần Mĩ thuật và Truyền thông | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| ADC_2024 | Công ty Cổ phần Mĩ thuật và Truyền thông | 2 / 2 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| ADC_2025 | Công ty Cổ phần Mĩ thuật và Truyền thông | 1 / 4 | separate | Trang 1: - [X] BCTC riêng (TCNY không có công ty con và đơn vị kế toán cấp trên có đơn vị trực thuộc); |
| ALT_2023 | Công ty Cổ phần Văn hóa Tân Bình | 1 / 1 | consolidated | Trang 1: ### BÁO CÁO TÀI CHÍNH HỢP NHẤT |
| ALT_2024 | Công ty Cổ phần Văn hóa Tân Bình | 1 / 1 | consolidated | Trang 1: ### BÁO CÁO TÀI CHÍNH HỢP NHẤT |
| ALT_2025 | Công ty Cổ phần Văn hóa Tân Bình | 1 / 1 | consolidated | Trang 1: ### BÁO CÁO TÀI CHÍNH HỢP NHẤT |
| AMC_2021 | Công ty Cổ phần Khoáng sản Á Châu | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| AMC_2022 | Công ty Cổ phần Khoáng sản Á Châu | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| AMC_2023 | Công ty Cổ phần Khoáng sản Á Châu | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| AMC_2024 | Công ty Cổ phần Khoáng sản Á Châu | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| AMC_2025 | Công ty Cổ phần Khoáng sản Á Châu | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| AME_2023 | Công ty Cổ phần Alphanam E&C | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| AME_2024 | Công ty Cổ phần Alphanam E&C | 1 / 1 | consolidated | Trang 1: Báo cáo tài chính hợp nhất đã được kiểm toán cho năm tài chính kết thúc vào ngày 31 tháng 12 năm 2024 |
| AME_2025 | Công ty Cổ phần Alphanam E&C | 1 / 1 | consolidated | Trang 1: ### BÁO CÁO TÀI CHÍNH HỢP NHẤT |
| ARM_2023 | Công ty Cổ phần Xuất nhập khẩu Hàng không | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| ARM_2024 | Công ty Cổ phần Xuất nhập khẩu Hàng không | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| ARM_2025 | Công ty Cổ phần Xuất nhập khẩu Hàng không | 1 / 3 | separate | Trang 1: [x] BCTC riêng (TCNY không có công ty con và đơn vị kế toán cấp trên có đơn vị trực thuộc); |
| ATS_2023 | Công ty Cổ phần Tập đoàn Dược phẩm ATESCO | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| ATS_2024 | Công ty Cổ phần Tập đoàn Đầu tư ATS | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| ATS_2025 | Công ty Cổ phần Tập đoàn Đầu tư ATS | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| BBS_2023 | Công ty Cổ phần Vicem Bao bì Bút Sơn | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| BBS_2024 | Công ty Cổ phần Vicem Bao bì Bút Sơn | 1 / 3 | separate | Trang 1: [X] BCTC riêng (TCNY không có công ty con và đơn vị kế toán cấp trên có đơn vị trực thuộc); |
| BBS_2025 | Công ty Cổ phần Vicem Bao bì Bút Sơn | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| BCC_2021 | Công ty Cổ phần Xi măng Bỉm Sơn | 1 / 2 | consolidated | Trang 2: ### BÁO CÁO TÀI CHÍNH HỢP NHẤT ĐÃ ĐƯỢC KIỂM TOÁN |
| BCC_2022 | Công ty Cổ phần Xi măng Bỉm Sơn | 1 / 1 | consolidated | Trang 1: ### BÁO CÁO TÀI CHÍNH HỢP NHẤT ĐÃ ĐƯỢC KIỂM TOÁN |
| BCC_2023 | Công ty Cổ phần Xi măng Bỉm Sơn | 1 / 5 | consolidated | Trang 1: [X] BCTC hợp nhất (TCNY có Công ty con); |
| BCC_2024 | Công ty Cổ phần Xi măng Bỉm Sơn | 3 / 3 | consolidated | Trang 3: ### BÁO CÁO TÀI CHÍNH HỢP NHẤT |
| BCC_2025 | Công ty Cổ phần Xi măng Bỉm Sơn | 1 / 1 | consolidated | Trang 1: 6.1. Báo cáo tài chính hợp nhất sau kiểm toán năm 2025 của Công ty Cổ phần Xi măng Bỉm Sơn được lập ngày 10 tháng 03 năm 2026, bao gồm: |
| BED_2023 | Công ty Cổ phần Sách và Thiết bị trường học Đà Nẵng | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| BED_2024 | Công ty Cổ phần Sách và Thiết bị trường học Đà Nẵng | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| BED_2025 | Công ty Cổ phần Sách và Thiết bị trường học Đà Nẵng | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| BKC_2023 | Công ty Cổ phần Khoáng sản Bắc Kạn | 1 / 3 | separate | Trang 1: ☑ BCTC riêng (TCNY không có công ty con và đơn vị kế toán cấp trên có đơn vị trực thuộc); |
| BKC_2024 | Công ty Cổ phần Khoáng sản Bắc Kạn | 1 / 3 | separate | Trang 1: [x] BCTC riêng (TCNY không có công ty con và đơn vị kế toán cấp trên có đơn vị trực thuộc); |
| BKC_2025 | Công ty Cổ phần Khoáng sản Bắc Kạn | 1 / 3 | consolidated | Trang 1: (Báo cáo tài chính hợp nhất) |
| BPC_2025 | Công ty Cổ phần Vicem Bao bì Bỉm Sơn | 3 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |
| BTS_2025 | Công ty Cổ phần Xi măng Vicem Bút Sơn | 1 / 4 | separate | Trang 1: [x] BCTC riêng (TCNY không có công ty con và đơn vị kế toán cấp trên có đơn vị trực thuộc); |
| BTW_2025 | Công ty Cổ phần Cấp nước Bến Thành | 1 / 3 | separate | Trang 1: [X] BCTC riêng (TCNY không có công ty con và đơn vị kế toán cấp trên có đơn vị trực thuộc) |
| C69_2025 | Công ty Cổ phần Xây dựng 1369 | 1 / 7 | consolidated | Trang 2: - BCTC hợp nhất 2025 / Consolidated financial statements 2025 |
| CAG_2025 | Công ty Cổ phần Cảng An Giang | 1 / 1 | unknown | Chưa có chỉ dẫn phạm vi rõ trong lượt kiểm mục tiêu; giữ unknown. |

Scope: **7 separate / 12 consolidated / 22 unknown**. Danh sách unknown: `ADC_2021`, `ADC_2022`, `ADC_2023`, `ADC_2024`, `AMC_2021`, `AMC_2022`, `AMC_2023`, `AMC_2024`, `AMC_2025`, `AME_2023`, `ARM_2023`, `ARM_2024`, `ATS_2023`, `ATS_2024`, `ATS_2025`, `BBS_2023`, `BBS_2025`, `BED_2023`, `BED_2024`, `BED_2025`, `BPC_2025`, `CAG_2025`.

ATS_2023 giữ tên **Công ty Cổ phần Tập đoàn Dược phẩm ATESCO**, ATS_2024/2025 là **Công ty Cổ phần Tập đoàn Đầu tư ATS**; metadata theo document_id bảo toàn khác biệt. BPC dùng tên Bỉm Sơn đúng trong thân báo cáo (trang 3/4), không lấy lỗi chữ Bìm ở bìa. BBS/BTS và BCC/BPC có ticker và tên đầy đủ riêng, không dùng alias chung “Bút Sơn” hoặc “Bỉm Sơn”.

**BCC_2025:** scope consolidated lấy đúng dòng công bố trang 1 về báo cáo được nhắc đến; export vẫn chỉ hai trang công bố/giải trình, không chứa bộ BCTC. Metadata không khẳng định tính đầy đủ, không bind PDF khác cùng key và không dùng tài liệu này để sinh QA. Đây là cùng nghĩa phạm vi báo cáo được công bố trong SCHEMA.md, không phải nhãn loại file hoặc chứng nhận nguồn đầy đủ.

## 4. Bộ QA sau chuẩn hóa

Trích dẫn bảng giữ các dòng nguyên văn đã chọn theo thứ tự trang, gồm header và hàng/nhóm cần thiết; không yêu cầu các dòng đó liền nhau trong bảng đầy đủ. Mỗi QA vẫn lấy thông tin đích từ một hàng/ô hoặc đoạn. Phần unit_evidence là ngữ cảnh đơn vị của cùng tài liệu.

### VFB-SH-0001 — easy / natural

**Câu hỏi:** Cuối năm 2025, tổng tài sản của Vicem Bao bì Bút Sơn là bao nhiêu?

**Đáp án:** 266.086.680.765 VND

```json
{"type": "number", "value": "266086680765", "unit": "vnd", "display": "266.086.680.765 VND", "key_points": []}
```

**Nguồn:** [BBS_2025, trang 5](../ViFinBench/neutral/BBS_2025/document.md); bảng `BBS_2025_p005_t001`; hàng `TỔNG CỘNG TÀI SẢN`; cột `31/12/2025`.

```text
Đơn vị tính: VND
| CHỈ TIÊU | Mã số | Thuyết minh | 31/12/2025 | 01/01/2025 |
| --- | --- | --- | --- | --- |
| TỔNG CỘNG TÀI SẢN | 270 |  | 266.086.680.765 | 291.306.659.104 |
```

### VFB-SH-0002 — easy / formal

**Câu hỏi:** Doanh thu thuần về bán hàng và cung cấp dịch vụ của Khoáng sản Á Châu năm 2021 là bao nhiêu?

**Đáp án:** 157.803.608.857 VND

```json
{"type": "number", "value": "157803608857", "unit": "vnd", "display": "157.803.608.857 VND", "key_points": []}
```

**Nguồn:** [AMC_2021, trang 9](../ViFinBench/neutral/AMC_2021/document.md); bảng `AMC_2021_p009_t001`; hàng `2. Doanh thu thuần về bán hàng và cung cấp dịch vụ`; cột `Năm nay`.

```text
### BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH
Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2021
| CHỈ TIÊU | Mã số | Thuyết minh | Năm nay | Năm trước |
| --- | --- | --- | --- | --- |
| 2. Doanh thu thuần về bán hàng và cung cấp dịch vụ | 10 | VI.1 | 157.803.608.857 | 153.539.180.123 |
```

**unit_evidence — trang 11:**

```text
Báo cáo tài chính kèm theo được trình bày bằng Đồng Việt Nam (VND), theo nguyên tắc giá gốc và phù hợp với Chuẩn mực kế toán, Chế độ kế toán doanh nghiệp Việt Nam và các quy định pháp lý có liên quan đến việc lập và trình bày Báo cáo tài chính.
```

### VFB-SH-0003 — easy / natural

**Câu hỏi:** Đơn vị nào kiểm toán báo cáo tài chính năm 2021 của Công ty Cổ phần Mĩ thuật và Truyền thông?

**Đáp án:** Công ty TNHH Kiểm toán và Kế toán AAC

```json
{"type": "entity", "value": "Công ty TNHH Kiểm toán và Kế toán AAC", "unit": null, "display": "Công ty TNHH Kiểm toán và Kế toán AAC", "key_points": []}
```

**Nguồn:** [ADC_2021, trang 7](../ViFinBench/neutral/ADC_2021/document.md); văn bản, các nhãn bảng null.

```text
### CÔNG TY CỔ PHẦN MĨ THUẬT VÀ TRUYỀN THÔNG
Cho năm tài chính kết thúc ngày 31/12/2021
### Kiểm toán độc lập
Báo cáo tài chính này được kiểm toán bởi Công ty TNHH Kiểm toán và Kế toán AAC
```

### VFB-SH-0004 — easy / formal

**Câu hỏi:** Theo báo cáo lưu chuyển tiền tệ hợp nhất năm 2024 của Xi măng Bỉm Sơn, lưu chuyển tiền thuần từ hoạt động kinh doanh là bao nhiêu?

**Đáp án:** 202.642.595.052 VND

```json
{"type": "number", "value": "202642595052", "unit": "vnd", "display": "202.642.595.052 VND", "key_points": []}
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

### VFB-SH-0005 — easy / natural

**Câu hỏi:** Cuối năm 2025, Cảng An Giang có bao nhiêu nhân viên đang làm việc?

**Đáp án:** 120 nhân viên

```json
{"type": "number", "value": "120", "unit": "person", "display": "120 nhân viên", "key_points": []}
```

**Nguồn:** [CAG_2025, trang 13](../ViFinBench/neutral/CAG_2025/document.md); văn bản, các nhãn bảng null.

```text
### CÔNG TY CỔ PHẦN CẢNG AN GIANG
Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025
- 6. Nhân viên
Tại ngày kết thúc năm tài chính Công ty có 120 nhân viên đang làm việc (số đầu năm là 119 nhân viên).
```

### VFB-SH-0006 — medium / natural

**Câu hỏi:** Theo báo cáo tài chính năm 2025, Sách và Thiết bị trường học Đà Nẵng ước tính thời gian khấu hao máy móc thiết bị trong khoảng bao nhiêu năm?

**Đáp án:** Từ 2 đến 7 năm

```json
{"type": "range", "min": "2", "max": "7", "unit": "year", "display": "Từ 2 đến 7 năm", "key_points": []}
```

**Nguồn:** [BED_2025, trang 15](../ViFinBench/neutral/BED_2025/document.md); bảng `BED_2025_p015_t001`; hàng `Máy móc thiết bị`; cột `Năm 2025`.

```text
### 3.6. Tài sản cố định hữu hình
### Thời gian khấu hao ước tính
| Nhóm tài sản | Năm 2025 |
| --- | --- |
| Máy móc thiết bị | 02 – 07 năm |
```

### VFB-SH-0007 — medium / natural

**Câu hỏi:** Năm 2025, Cấp nước Bến Thành thuê tài sản gì của Tổng Công ty Cấp nước Sài Gòn theo hợp đồng 2703/HĐ-TCT-KTTC, và dùng vào mục đích nào?

**Đáp án:** Mạng lưới cấp nước do Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư, để cung cấp nước sạch trên địa bàn của Công ty.

```json
{"type": "text", "value": "Mạng lưới cấp nước do Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư, để cung cấp nước sạch trên địa bàn của Công ty.", "unit": null, "display": "Mạng lưới cấp nước do Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư, để cung cấp nước sạch trên địa bàn của Công ty.", "key_points": ["Mạng lưới cấp nước do Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư", "Sử dụng để cung cấp nước sạch trên địa bàn của Công ty"]}
```

**Nguồn:** [BTW_2025, trang 43](../ViFinBench/neutral/BTW_2025/document.md); văn bản, các nhãn bảng null.

```text
### CÔNG TY CỔ PHẦN CẤP NƯỚC BẾN THÀNH
Cho năm tài chính kết thúc ngày 31/12/2025
### 35.2 CAM KẾT THUÊ HOẠT ĐỘNG
Theo hợp đồng thuê tài sản hoạt động số 2703/HĐ-TCT-KTTC ngày 09/05/2025, Công ty thuê tài sản là mạng lưới cấp nước của Tổng Công ty Cấp nước Sài Gòn TNHH MTV đầu tư để sử dụng cho mục đích cung cấp nước sạch trên địa bàn của Công ty, với tổng nguyên giá tài sản thuê là 10.010.334.699 đồng, thời hạn thuê từ ngày 01/01/2025 đến ngày 31/12/2025.
```

### VFB-SH-0008 — medium / formal

**Câu hỏi:** Tại ngày 31/12/2025, giá trị hợp lý của khoản đầu tư cổ phiếu Xi măng Vicem Hoàng Mai tại Vicem Bao bì Bỉm Sơn là bao nhiêu?

**Đáp án:** 936.000.000 VND

```json
{"type": "number", "value": "936000000", "unit": "vnd", "display": "936.000.000 VND", "key_points": []}
```

**Nguồn:** [BPC_2025, trang 14](../ViFinBench/neutral/BPC_2025/document.md); bảng `BPC_2025_p014_t002`; hàng `Cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai`; cột `Giá trị hợp lý (VND)`.

```text
### 6. ĐẦU TƯ TÀI CHÍNH NGẮN HẠN - Chứng khoán kinh doanh (Tại ngày 31/12/2025)
| Chỉ tiêu | Giá gốc (VND) | Giá trị hợp lý (VND) | Dự phòng (VND) |
| --- | --- | --- | --- |
| Cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai | 2.952.000.000 | 936.000.000 | (2.016.000.000) |
```

### VFB-SH-0009 — medium / natural

**Câu hỏi:** Cuối năm 2023, Xuất nhập khẩu Hàng không (ARM) còn phải trả Công ty ROHR bao nhiêu tiền liên quan đến hoạt động ủy thác?

**Đáp án:** 5.135.627.375 VND

```json
{"type": "number", "value": "5135627375", "unit": "vnd", "display": "5.135.627.375 VND", "key_points": []}
```

**Nguồn:** [ARM_2023, trang 25](../ViFinBench/neutral/ARM_2023/document.md); bảng `ARM_2023_p025_t001`; hàng `Công ty ROHR`; cột `Tại ngày 31/12/2023 VND`.

**row_path:** Ngắn hạn → Phải trả bên thứ ba → Các khoản phải trả, phải nộp về ủy thác → Công ty ROHR.

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

### VFB-SH-0010 — medium / formal

**Câu hỏi:** Theo báo cáo tài chính hợp nhất năm 2023 của Văn hóa Tân Bình, chi phí thuế thu nhập doanh nghiệp hiện hành tại Công ty mẹ là bao nhiêu?

**Đáp án:** 1.314.130.355 VND

```json
{"type": "number", "value": "1314130355", "unit": "vnd", "display": "1.314.130.355 VND", "key_points": []}
```

**Nguồn:** [ALT_2023, trang 42](../ViFinBench/neutral/ALT_2023/document.md); bảng `ALT_2023_p042_t001`; hàng `Chi phí thuế TNDN hiện hành tại Công ty mẹ`; cột `Năm 2023`.

```text
Báo cáo tài chính hợp nhất Cho năm tài chính kết thúc ngày 31/12/2023
### 32. CHI PHÍ THUẾ THU NHẬP DOANH NGHIỆP HIỆN HÀNH
| Chỉ tiêu | Năm 2023 | Năm 2022 |
| --- | --- | --- |
| Chi phí thuế TNDN hiện hành tại Công ty mẹ | 1.314.130.355 | 2.456.916.173 |
```

**unit_evidence — trang 14:**

```text
Đơn vị tiền tệ sử dụng trong ghi chép kế toán là đồng Việt Nam (VND).
```

### VFB-SH-0011 — medium / natural

**Câu hỏi:** Trong báo cáo tài chính năm 2024, Công ty Cổ phần Tập đoàn Đầu tư ATS cho biết hợp đồng thuê văn phòng TAC 20-F6/11 được gia hạn theo phụ lục số 06 đến ngày nào?

**Đáp án:** 30/06/2025

```json
{"type": "date", "value": "2025-06-30", "unit": null, "display": "30/06/2025", "key_points": []}
```

**Nguồn:** [ATS_2024, trang 22](../ViFinBench/neutral/ATS_2024/document.md); văn bản, các nhãn bảng null.

```text
### CÔNG TY CỔ PHẦN TẬP ĐOÀN ĐẦU TƯ ATS
Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024
5.4. Phải thu khác ngắn hạn
(*) Là khoản tiền đặt cọc để thuê văn phòng theo Hợp đồng thuê văn phòng và dịch vụ văn phòng số TAC 20-F6/11 ký ngày 01/07/2020 (kèm theo phụ lục gia hạn hợp đồng số 06 ký ngày 30/05/2024 với thời hạn từ 01/07/2024 đến ngày 30/06/2025) để làm văn phòng giao dịch tại Phòng 608, Tầng 6, Toà nhà Sky City Tower A số 88 Láng Hạ, Quận Đống Đa, Hà Nội.
```

### VFB-SH-0012 — medium / natural

**Câu hỏi:** Cuối năm 2025, Cảng An Giang công bố sẽ thu tối thiểu bao nhiêu tiền từ các hợp đồng cho thuê hoạt động không thể hủy ngang cho phần thời hạn trên 5 năm?

**Đáp án:** 5.879.280.000 VND

```json
{"type": "number", "value": "5879280000", "unit": "vnd", "display": "5.879.280.000 VND", "key_points": []}
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

**unit_evidence — trang 13:**

```text
Đơn vị tiền tệ sử dụng trong kế toán là Đồng Việt Nam (VND) do phần lớn các nghiệp vụ được thực hiện bằng đơn vị tiền tệ VND.
```

### VFB-SH-0013 — hard / natural

**Câu hỏi:** Trong báo cáo tài chính năm 2025, Vicem Bao bì Bút Sơn cho biết Vietcombank Nam Định giới hạn thời gian cấp hạn mức của hợp đồng ngày 16/06/2025 như thế nào?

**Đáp án:** 13 tháng kể từ ngày 30/05/2025 nhưng không quá 12 tháng kể từ ngày 16/06/2025.

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

### VFB-SH-0014 — hard / natural

**Câu hỏi:** Theo báo cáo tài chính năm 2023, VietinBank Bắc Kạn đã nâng hạn mức cho Khoáng sản Bắc Kạn lên bao nhiêu sau khi sửa đổi hợp đồng ngày 28/02/2023?

**Đáp án:** 27.000.000.000 VND

```json
{"type": "number", "value": "27000000000", "unit": "vnd", "display": "27.000.000.000 VND", "key_points": []}
```

**Nguồn:** [BKC_2023, trang 30](../ViFinBench/neutral/BKC_2023/document.md); văn bản, các nhãn bảng null.

```text
Cho năm tài chính kết thúc ngày 31/12/2023
5.18 Vay và nợ thuê tài chính (Tiếp theo)
Hợp đồng cho vay hạn mức số 05/2023-HĐCVHM/NHCT172-KHOANG SAN ngày 28/02/2023 giữa Ngân hàng TMCP Công thương Việt Nam - Chi nhánh Bắc Kạn (Bên cho vay) và Công ty Cổ phần Khoáng sản Bắc Kạn. Hạn mức cho vay 25.000.000.000 VND (Bằng chữ: Hai mươi lăm tỷ đồng Việt Nam) kèm theo văn bản sửa đổi, bổ sung hợp đồng cho vay hạn mức số 05/2023-HĐCVTL-SĐBS1/NHCT172-KHOANG SAN sửa đổi nâng hạn mức thành 27.000.000.000 VND (Bằng chữ: Hai mươi bảy tỷ đồng Việt Nam).
```

### VFB-SH-0015 — hard / formal

**Câu hỏi:** Trên báo cáo tài chính hợp nhất năm 2023 của Văn hóa Tân Bình, hao mòn lũy kế cuối năm của nhóm phương tiện vận tải, truyền dẫn là bao nhiêu?

**Đáp án:** 11.137.916.671 VND

```json
{"type": "number", "value": "11137916671", "unit": "vnd", "display": "11.137.916.671 VND", "key_points": []}
```

**Nguồn:** [ALT_2023, trang 29](../ViFinBench/neutral/ALT_2023/document.md); bảng `ALT_2023_p029_t001`; hàng `Số dư cuối năm`; cột `Phương tiện vận tải, truyền dẫn VND`.

**row_path:** Giá trị hao mòn lũy kế → Số dư cuối năm.

```text
Báo cáo tài chính hợp nhất
Cho năm tài chính kết thúc ngày 31/12/2023
### 11. TÀI SẢN CỐ ĐỊNH HỮU HÌNH
| Chỉ tiêu | Nhà cửa, vật kiến trúc VND | Máy móc, thiết bị VND | Phương tiện vận tải, truyền dẫn VND | Thiết bị, dụng cụ quản lý VND | Tài sản cố định khác VND | Cộng VND |
| --- | --- | --- | --- | --- | --- | --- |
| Giá trị hao mòn lũy kế |  |  |  |  |  |  |
| Số dư cuối năm | 34.237.017.840 | 94.734.412.454 | 11.137.916.671 | 6.125.564.417 | 231.129.596 | 146.466.040.978 |
```

## 5. Validation và bàn giao

Focused checks local PASS: JSONL/JSON parse; đúng 15 ID và phân bố 5/7/3, style 10/5; so sánh baseline xác nhận 14 câu nguyên văn và một câu chỉ mở rộng tên doanh nghiệp, display/đáp án thực tế giữ nguyên; answer types/number string/range min≤max/date ISO/unit hợp lệ; giữ key_points của text nhiều ý. Ba unit_evidence khớp nguyên văn đúng trang/cùng document; sáu quote tiền còn lại có VND. Hai row_path khớp hàng cha–con và thứ tự bảng; header/hàng/ô đáp án và references vẫn khớp neutral.

Metadata có 41 key trùng toàn bộ corpus và bao phủ 12 document Pilot; tên/năm đối chiếu nội dung từng tài liệu, scope không suy từ ô checkbox bỏ trống hoặc từ năm khác. Unknown được liệt kê ở mục 3. 123 neutral hashes, audit và mọi local changes ngoài task giữ nguyên. `git diff --check` PASS; không full CI, Gemini/API, evaluator hoặc sửa pipeline. Không sửa planning/checker vì brief giới hạn đúng bốn file.

Giới hạn: phạm vi unknown cần xác minh bổ sung khi dùng cho câu hỏi phụ thuộc riêng/hợp nhất; lượt này không mở rộng xác minh ảnh/PDF hoặc tính đầy đủ của corpus. Chất lượng nội dung được duyệt trong brief không đồng nghĩa accuracy toàn corpus hay kết quả chạy mô hình. Schema v1 là quy ước đã được ghi thành tài liệu, Finalize vẫn chờ nghiệm thu REVIEW.

Implementation là commit chứa đúng bốn file đầu ra; SHA được xác minh trong bàn giao Git.

**Next action:** Tech Lead nghiệm thu P1A-Finalize và Schema v1.
