# ViFinBench-P1A — Single-hop QA Pilot

Ngày thực hiện: **13/11/2026** (Asia/Bangkok). Trạng thái: **REVIEW**, chờ Tech Lead nghiệm thu.
Dataset: [pilot.jsonl](../ViFinBench/benchmark/single_hop/pilot.jsonl).

## 1. Phạm vi và cách tuyển chọn

Tạo đúng **15 QA: 5 Easy / 7 Medium / 3 Hard**, từ **12 doanh nghiệp, 12 tài liệu, 15 trang neutral**; các năm báo cáo 2021, 2023, 2024 và 2025. Mỗi tài liệu có tối đa hai câu. Có B01, B02, B03 và B09; 10 mẫu dùng bảng, 5 mẫu dùng văn bản. Không triển khai P1B/P1C, sửa neutral/audit, đổi pipeline hoặc gọi API.

Đọc Markdown để xác định doanh nghiệp, phạm vi báo cáo, kỳ và ý nghĩa mục; đọc Tables JSON để xác định chính xác hàng/cột, sau đó đọc lại trang nguồn cho từng QA. Mỗi đáp án lấy từ một hàng hoặc một đoạn liên tục; header/phần bảng và chính sách đơn vị tiền tệ là ngữ cảnh đọc nguồn, không kết hợp số liệu độc lập. Không câu nào cần phép tính mới. Trang là **số trang neutral**, không phải số trang in ở chân báo cáo.

Quyết định Owner/Tech Lead trong brief cho phép dùng toàn bộ neutral và chọn lọc thông tin có thể kiểm chứng; không bắt buộc PNG/PDF cho mọi mẫu. Phiên này chỉ kiểm neutral, không đối chiếu ảnh/PDF mới. Đây là bộ ứng viên Gold chờ review, chưa phải kết quả đánh giá mô hình hoặc chứng nhận độ chính xác toàn corpus.

## 2. Tổng hợp 15 QA

| ID | Doanh nghiệp | Năm báo cáo | Độ khó | Chủ đề |
| --- | --- | --- | --- | --- |
| VFB-SH-0001 | Vicem Bao bì Bút Sơn | 2025 | easy | Tổng tài sản (B01) |
| VFB-SH-0002 | Khoáng sản Á Châu | 2021 | easy | Doanh thu thuần (B02) |
| VFB-SH-0003 | Mĩ thuật và Truyền thông | 2021 | easy | Đơn vị kiểm toán |
| VFB-SH-0004 | Xi măng Bỉm Sơn | 2024 | easy | Dòng tiền kinh doanh hợp nhất (B03) |
| VFB-SH-0005 | Cảng An Giang | 2025 | easy | Cổ phiếu đang lưu hành (B09) |
| VFB-SH-0006 | Sách và Thiết bị trường học Đà Nẵng | 2025 | medium | Chính sách hàng tồn kho (B09) |
| VFB-SH-0007 | Cấp nước Bến Thành | 2025 | medium | Ghi nhận doanh thu dịch vụ (B09) |
| VFB-SH-0008 | Vicem Bao bì Bỉm Sơn | 2025 | medium | Giá trị hợp lý chứng khoán (B09) |
| VFB-SH-0009 | Xuất nhập khẩu Hàng không | 2023 | medium | Công nợ ủy thác (B09) |
| VFB-SH-0010 | Văn hóa Tân Bình | 2023 | medium | Thuế hiện hành tại công ty mẹ (B09) |
| VFB-SH-0011 | Tập đoàn Đầu tư ATS | 2024 | medium | Thời hạn gia hạn thuê văn phòng (B09) |
| VFB-SH-0012 | Cảng An Giang | 2025 | medium | Tiền cho thuê sẽ thu theo kỳ hạn (B09) |
| VFB-SH-0013 | Vicem Bao bì Bút Sơn | 2025 | hard | Điều kiện thời gian cấp hạn mức (B09) |
| VFB-SH-0014 | Khoáng sản Bắc Kạn | 2023 | hard | Hạn mức sau sửa đổi hợp đồng (B09) |
| VFB-SH-0015 | Văn hóa Tân Bình | 2023 | hard | Hao mòn lũy kế theo nhóm tài sản (B09) |

## 3. Câu hỏi, đáp án và bằng chứng

Các khối trích dẫn dưới đây giữ nguyên nội dung trường `quote` của JSONL. Header được ghi thêm để người review đọc đúng cột; dấu xuống dòng trong header JSON được thay bằng khoảng trắng khi hiển thị.

### VFB-SH-0001 — easy

**Câu hỏi:** Tổng tài sản của Công ty Cổ phần Vicem Bao bì Bút Sơn tại ngày 31/12/2025 là bao nhiêu?

**Đáp án:** 266.086.680.765 VND

**Loại đáp án:** `number`. **Nguồn:** [BBS_2025, trang 5](../ViFinBench/neutral/BBS_2025/document.md); bảng `BBS_2025_p005_t001`.

**Vị trí:** B01; hàng TỔNG CỘNG TÀI SẢN, mã số 270; cột 31/12/2025; đơn vị VND.

**Header nguồn:** `CHỈ TIÊU | Mã số | Thuyết minh | 31/12/2025 | 01/01/2025`.

```text
| TỔNG CỘNG TÀI SẢN | 270 |  | 266.086.680.765 | 291.306.659.104 |
```

**Căn cứ Single-hop / độ khó:** Tra trực tiếp chỉ tiêu tổng tài sản, không cộng các khoản mục.

### VFB-SH-0002 — easy

**Câu hỏi:** Năm 2021, Công ty Cổ phần Khoáng sản Á Châu ghi nhận doanh thu thuần về bán hàng và cung cấp dịch vụ là bao nhiêu?

**Đáp án:** 157.803.608.857 VND

**Loại đáp án:** `number`. **Nguồn:** [AMC_2021, trang 9](../ViFinBench/neutral/AMC_2021/document.md); bảng `AMC_2021_p009_t001`.

**Vị trí:** B02; hàng 2. Doanh thu thuần về bán hàng và cung cấp dịch vụ, mã số 10; cột Năm nay (2021); đơn vị VND theo cơ sở lập BCTC tại trang 11.

**Header nguồn:** `CHỈ TIÊU | Mã số | Thuyết minh | Năm nay | Năm trước`.

```text
| 2. Doanh thu thuần về bán hàng và cung cấp dịch vụ | 10 | VI.1 | 157.803.608.857 | 153.539.180.123 |
```

**Căn cứ Single-hop / độ khó:** Tra giá trị công bố ở cột năm báo cáo, không tính doanh thu thuần.

### VFB-SH-0003 — easy

**Câu hỏi:** Đơn vị nào kiểm toán báo cáo tài chính năm 2021 của Công ty Cổ phần Mĩ thuật và Truyền thông?

**Đáp án:** Công ty TNHH Kiểm toán và Kế toán AAC

**Loại đáp án:** `entity`. **Nguồn:** [ADC_2021, trang 7](../ViFinBench/neutral/ADC_2021/document.md); văn bản, `table_id=null`.

**Vị trí:** Báo cáo của Ban Giám đốc; mục Kiểm toán độc lập; câu đầu.

```text
Báo cáo tài chính này được kiểm toán bởi Công ty TNHH Kiểm toán và Kế toán AAC
```

**Căn cứ Single-hop / độ khó:** Tên đơn vị kiểm toán được nêu trực tiếp; trích nguyên văn phần đầu câu.

### VFB-SH-0004 — easy

**Câu hỏi:** Theo báo cáo lưu chuyển tiền tệ hợp nhất năm 2024, lưu chuyển tiền thuần từ hoạt động kinh doanh của Công ty Cổ phần Xi măng Bỉm Sơn là bao nhiêu?

**Đáp án:** 202.642.595.052 VND

**Loại đáp án:** `number`. **Nguồn:** [BCC_2024, trang 12](../ViFinBench/neutral/BCC_2024/document.md); bảng `BCC_2024_p012_t001`.

**Vị trí:** B03-DN/HN; hàng Lưu chuyển tiền thuần từ hoạt động kinh doanh, mã số 20; cột Năm nay (2024); đơn vị VND.

**Header nguồn:** `CHỈ TIÊU | Mã số | Năm nay | Năm trước`.

```text
| Lưu chuyển tiền thuần từ hoạt động kinh doanh | 20 | 202.642.595.052 | 28.673.341.455 |
```

**Căn cứ Single-hop / độ khó:** Tra tổng dòng tiền đã công bố; phạm vi hợp nhất ghi rõ trong câu hỏi.

### VFB-SH-0005 — easy

**Câu hỏi:** Tại ngày 31/12/2025, Công ty Cổ phần Cảng An Giang có bao nhiêu cổ phiếu đang lưu hành?

**Đáp án:** 13.800.000 cổ phiếu

**Loại đáp án:** `number`. **Nguồn:** [CAG_2025, trang 27](../ViFinBench/neutral/CAG_2025/document.md); bảng `CAG_2025_p027_t003`.

**Vị trí:** B09; mục 18c. Cổ phiếu; hàng Số lượng cổ phiếu đang lưu hành; cột Số cuối năm (31/12/2025).

**Header nguồn:** `Chỉ tiêu | Số cuối năm | Số đầu năm`.

```text
| Số lượng cổ phiếu đang lưu hành | 13.800.000 | 13.800.000 |
```

**Căn cứ Single-hop / độ khó:** Tra dòng tổng số cổ phiếu đang lưu hành, không tính từ vốn/mệnh giá.

### VFB-SH-0006 — medium

**Câu hỏi:** Theo chính sách kế toán trong báo cáo tài chính năm 2025 của Công ty Cổ phần Sách và Thiết bị trường học Đà Nẵng, giá gốc hàng tồn kho được xác định và hàng tồn kho được hạch toán theo các phương pháp nào?

**Đáp án:** Giá gốc xác định theo phương pháp bình quân gia quyền; hạch toán theo phương pháp kê khai thường xuyên.

**Loại đáp án:** `text`. **Nguồn:** [BED_2025, trang 15](../ViFinBench/neutral/BED_2025/document.md); văn bản, `table_id=null`.

**Vị trí:** B09; mục Phương pháp xác định giá trị hàng tồn kho; đoạn ngay dưới tiêu đề.

```text
Giá gốc của hàng tồn kho được xác định theo phương pháp bình quân gia quyền và được hạch toán theo phương pháp kê khai thường xuyên.
```

**Căn cứ Single-hop / độ khó:** Phân biệt phương pháp xác định giá gốc với phương pháp hạch toán; cả hai nằm trong cùng một câu.

### VFB-SH-0007 — medium

**Câu hỏi:** Theo báo cáo tài chính năm 2025 của Công ty Cổ phần Cấp nước Bến Thành, doanh thu cung cấp dịch vụ được ghi nhận như thế nào khi kết quả giao dịch không thể xác định chắc chắn?

**Đáp án:** Doanh thu được ghi nhận tương ứng với chi phí đã ghi nhận và có thể thu hồi.

**Loại đáp án:** `text`. **Nguồn:** [BTW_2025, trang 21](../ViFinBench/neutral/BTW_2025/document.md); văn bản, `table_id=null`.

**Vị trí:** B09; mục 4.12 Ghi nhận doanh thu, chi phí (tiếp); tiểu mục Doanh thu cung cấp dịch vụ; câu sau danh sách điều kiện.

```text
Khi kết quả của một giao dịch về cung cấp dịch vụ không thể xác định được chắc chắn thì doanh thu được ghi nhận tương ứng với chi phí đã ghi nhận và có thể thu hồi.
```

**Căn cứ Single-hop / độ khó:** Chọn trường hợp kết quả chưa chắc chắn, phân biệt với danh sách điều kiện ghi nhận thông thường.

### VFB-SH-0008 — medium

**Câu hỏi:** Tại ngày 31/12/2025, khoản cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai do Công ty Cổ phần Vicem Bao bì Bỉm Sơn nắm giữ được trình bày với giá trị hợp lý bao nhiêu?

**Đáp án:** 936.000.000 VND

**Loại đáp án:** `number`. **Nguồn:** [BPC_2025, trang 14](../ViFinBench/neutral/BPC_2025/document.md); bảng `BPC_2025_p014_t002`.

**Vị trí:** B09; mục 6, Chứng khoán kinh doanh tại ngày 31/12/2025; hàng Cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai; cột Giá trị hợp lý (VND), không phải Giá gốc hoặc Dự phòng.

**Header nguồn:** `Chỉ tiêu | Giá gốc (VND) | Giá trị hợp lý (VND) | Dự phòng (VND)`.

```text
| Cổ phiếu Công ty CP Xi măng Vicem Hoàng Mai | 2.952.000.000 | 936.000.000 | (2.016.000.000) |
```

**Căn cứ Single-hop / độ khó:** Phân biệt hai bảng cùng khoản đầu tư tại đầu/cuối năm và ba cơ sở giá trị.

### VFB-SH-0009 — medium

**Câu hỏi:** Trong thuyết minh phải trả khác, khoản phải trả, phải nộp về ủy thác cho Công ty ROHR của Công ty Cổ phần Xuất nhập khẩu Hàng không tại ngày 31/12/2023 là bao nhiêu?

**Đáp án:** 5.135.627.375 VND

**Loại đáp án:** `number`. **Nguồn:** [ARM_2023, trang 25](../ViFinBench/neutral/ARM_2023/document.md); bảng `ARM_2023_p025_t001`.

**Vị trí:** B09; mục 4.13 Phải trả khác; nhóm Ngắn hạn → Phải trả bên thứ ba → Các khoản phải trả, phải nộp về ủy thác; hàng Công ty ROHR; cột Tại ngày 31/12/2023 VND.

**Header nguồn:** `Chỉ tiêu | Tại ngày 31/12/2023 VND | Tại ngày 01/01/2023 VND`.

```text
| Công ty ROHR | 5.135.627.375 | 3.438.628.614 |
```

**Căn cứ Single-hop / độ khó:** Xác định đúng đối tác trong nhóm phải trả ủy thác bên thứ ba và đúng kỳ.

### VFB-SH-0010 — medium

**Câu hỏi:** Trong thuyết minh báo cáo tài chính hợp nhất năm 2023 của Công ty Cổ phần Văn hóa Tân Bình, chi phí thuế thu nhập doanh nghiệp hiện hành tại Công ty mẹ là bao nhiêu?

**Đáp án:** 1.314.130.355 VND

**Loại đáp án:** `number`. **Nguồn:** [ALT_2023, trang 42](../ViFinBench/neutral/ALT_2023/document.md); bảng `ALT_2023_p042_t001`.

**Vị trí:** B09 hợp nhất; mục 32; hàng Chi phí thuế TNDN hiện hành tại Công ty mẹ; cột Năm 2023; đơn vị VND theo chính sách đơn vị tiền tệ tại trang 14.

**Header nguồn:** `Chỉ tiêu | Năm 2023 | Năm 2022`.

```text
| Chi phí thuế TNDN hiện hành tại Công ty mẹ | 1.314.130.355 | 2.456.916.173 |
```

**Căn cứ Single-hop / độ khó:** Phân biệt phần công ty mẹ với công ty con, tổng chi phí thuế và số thuế phải nộp.

### VFB-SH-0011 — medium

**Câu hỏi:** Theo thuyết minh khoản đặt cọc thuê văn phòng trong báo cáo tài chính năm 2024 của Công ty Cổ phần Tập đoàn Đầu tư ATS, phụ lục gia hạn số 06 của hợp đồng TAC 20-F6/11 có thời hạn kết thúc vào ngày nào?

**Đáp án:** 30/06/2025

**Loại đáp án:** `date`. **Nguồn:** [ATS_2024, trang 22](../ViFinBench/neutral/ATS_2024/document.md); văn bản, `table_id=null`.

**Vị trí:** B09; mục 5.4 Phải thu khác ngắn hạn; đoạn chú thích (*) dưới bảng; ngày kết thúc thời hạn phụ lục số 06, không phải ngày ký.

```text
(*) Là khoản tiền đặt cọc để thuê văn phòng theo Hợp đồng thuê văn phòng và dịch vụ văn phòng số TAC 20-F6/11 ký ngày 01/07/2020 (kèm theo phụ lục gia hạn hợp đồng số 06 ký ngày 30/05/2024 với thời hạn từ 01/07/2024 đến ngày 30/06/2025) để làm văn phòng giao dịch tại Phòng 608, Tầng 6, Toà nhà Sky City Tower A số 88 Láng Hạ, Quận Đống Đa, Hà Nội.
```

**Căn cứ Single-hop / độ khó:** Phân biệt ngày ký hợp đồng, ngày ký phụ lục và ngày kết thúc thời hạn trong một đoạn.

### VFB-SH-0012 — medium

**Câu hỏi:** Tại ngày 31/12/2025, Công ty Cổ phần Cảng An Giang công bố số tiền thuê tối thiểu sẽ thu từ các hợp đồng cho thuê hoạt động không thể hủy ngang ở kỳ hạn trên 5 năm là bao nhiêu?

**Đáp án:** 5.879.280.000 VND

**Loại đáp án:** `number`. **Nguồn:** [CAG_2025, trang 30](../ViFinBench/neutral/CAG_2025/document.md); bảng `CAG_2025_p030_t004`.

**Vị trí:** B09; VII. Những thông tin khác, mục 1. Tài sản cho thuê hoạt động; hàng Trên 05 năm; cột Số cuối năm (31/12/2025); VND theo đơn vị kế toán trang 13. Đây là tiền thu từ cho thuê, không phải tiền phải trả cho tài sản thuê ngoài tại trang 27.

**Header nguồn:** `Chỉ tiêu | Số cuối năm | Số đầu năm`.

```text
| Trên 05 năm | 5.879.280.000 | 6.767.280.000 |
```

**Căn cứ Single-hop / độ khó:** Phân biệt vai trò bên cho thuê/bên đi thuê, nhóm kỳ hạn và cột cuối năm.

### VFB-SH-0013 — hard

**Câu hỏi:** Theo thuyết minh vay ngắn hạn tại ngày 31/12/2025 của Công ty Cổ phần Vicem Bao bì Bút Sơn, hợp đồng số 01/2025/VCB.NDI/7189524/CTD với Vietcombank Chi nhánh Nam Định quy định thời gian cấp hạn mức tín dụng như thế nào?

**Đáp án:** 13 tháng kể từ ngày 30/05/2025 nhưng không quá 12 tháng kể từ ngày 16/06/2025.

**Loại đáp án:** `text`. **Nguồn:** [BBS_2025, trang 19](../ViFinBench/neutral/BBS_2025/document.md); bảng `BBS_2025_p019_t001`.

**Vị trí:** B09; bảng chi tiết vay ngắn hạn; hàng (2) Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Nam Định, hợp đồng ngày 16/06/2025; cột Thời hạn và mục đích vay; giữ cả hai ràng buộc thời gian.

**Header nguồn:** `Ngân hàng | Hợp đồng | Hạn mức (VND) | Thời hạn và mục đích vay | Tài sản đảm bảo`.

```text
| (2) Ngân hàng TMCP Ngoại thương Việt Nam - Chi nhánh Nam Định | Hợp đồng cấp tín dụng số 01/2025/VCB.NDI/7189524/CTD, ngày 16/06/2025 | 50.000.000.000 | Thời gian cấp hạn mức tín dụng 13 tháng kể từ ngày 30/05/2025 nhưng không quá 12 tháng kể từ ngày 16/06/2025; Mục đích: bổ sung vốn lưu động, bảo lãnh, mở L/C |
```

**Căn cứ Single-hop / độ khó:** Bảng hợp đồng rộng, nhiều ngân hàng và nhiều loại thời hạn; phải giữ đồng thời hai giới hạn đã công bố, không tự tính ngày hết hạn.

### VFB-SH-0014 — hard

**Câu hỏi:** Theo thuyết minh báo cáo tài chính năm 2023 của Công ty Cổ phần Khoáng sản Bắc Kạn, hạn mức vay tại VietinBank Chi nhánh Bắc Kạn theo hợp đồng số 05/2023-HĐCVHM/NHCT172-KHOANG SAN sau sửa đổi, bổ sung được nâng lên bao nhiêu?

**Đáp án:** 27.000.000.000 VND

**Loại đáp án:** `number`. **Nguồn:** [BKC_2023, trang 30](../ViFinBench/neutral/BKC_2023/document.md); văn bản, `table_id=null`.

**Vị trí:** B09; mục 5.18 Vay và nợ thuê tài chính (tiếp theo); đoạn (1); văn bản 05/2023-HĐCVTL-SĐBS1/NHCT172-KHOANG SAN nâng hạn mức, không lấy hạn mức gốc hoặc dư nợ.

```text
Hợp đồng cho vay hạn mức số 05/2023-HĐCVHM/NHCT172-KHOANG SAN ngày 28/02/2023 giữa Ngân hàng TMCP Công thương Việt Nam - Chi nhánh Bắc Kạn (Bên cho vay) và Công ty Cổ phần Khoáng sản Bắc Kạn. Hạn mức cho vay 25.000.000.000 VND (Bằng chữ: Hai mươi lăm tỷ đồng Việt Nam) kèm theo văn bản sửa đổi, bổ sung hợp đồng cho vay hạn mức số 05/2023-HĐCVTL-SĐBS1/NHCT172-KHOANG SAN sửa đổi nâng hạn mức thành 27.000.000.000 VND (Bằng chữ: Hai mươi bảy tỷ đồng Việt Nam).
```

**Căn cứ Single-hop / độ khó:** Định vị hợp đồng trong danh sách dài; phân biệt hạn mức gốc 25 tỷ với 27 tỷ sau sửa đổi, không dùng dư nợ bảng trang trước.

### VFB-SH-0015 — hard

**Câu hỏi:** Theo thuyết minh tài sản cố định hữu hình trong báo cáo tài chính hợp nhất năm 2023 của Công ty Cổ phần Văn hóa Tân Bình, giá trị hao mòn lũy kế cuối năm của nhóm phương tiện vận tải, truyền dẫn là bao nhiêu?

**Đáp án:** 11.137.916.671 VND

**Loại đáp án:** `number`. **Nguồn:** [ALT_2023, trang 29](../ViFinBench/neutral/ALT_2023/document.md); bảng `ALT_2023_p029_t001`.

**Vị trí:** B09 hợp nhất; mục 11; bảng Tài sản cố định hữu hình; phần Giá trị hao mòn lũy kế, hàng Số dư cuối năm; cột Phương tiện vận tải, truyền dẫn VND (cột thứ 4, kể cả Chỉ tiêu). Không lấy Nguyên giá hoặc Giá trị còn lại.

**Header nguồn:** `Chỉ tiêu | Nhà cửa, vật kiến trúc VND | Máy móc, thiết bị VND | Phương tiện vận tải, truyền dẫn VND | Thiết bị, dụng cụ quản lý VND | Tài sản cố định khác VND | Cộng VND`.

```text
| Giá trị hao mòn lũy kế |  |  |  |  |  |  |
| Số dư đầu năm | 30.683.722.240 | 86.082.118.631 | 10.347.560.536 | 5.720.991.069 | 374.630.540 | 133.209.023.016 |
| - Khấu hao trong năm | 3.553.295.600 | 8.652.293.823 | 1.332.178.878 | 404.573.348 | (143.500.944) | 13.798.840.705 |
| - Thanh lý, nhượng bán | - | - | (541.822.743) | - | - | (541.822.743) |
| Số dư cuối năm | 34.237.017.840 | 94.734.412.454 | 11.137.916.671 | 6.125.564.417 | 231.129.596 | 146.466.040.978 |
```

**Căn cứ Single-hop / độ khó:** Bảng bảy cột có nhiều phần và lặp nhãn Số dư cuối năm; cần xác định đồng thời phần hao mòn, nhóm tài sản và cuối kỳ, không tính lại từ các biến động.

## 4. Đa dạng và giới hạn chất lượng

Các ý hỏi khác nhau: tổng tài sản, doanh thu, kiểm toán, dòng tiền, cổ phiếu, hàng tồn kho, ghi nhận doanh thu, giá trị hợp lý đầu tư, công nợ ủy thác, thuế tại công ty mẹ, gia hạn thuê văn phòng, tiền cho thuê sẽ thu, điều kiện thời gian tín dụng, hạn mức sau sửa đổi và hao mòn theo nhóm tài sản. Không có cặp chỉ thay tên doanh nghiệp/năm. Hai câu tín dụng khai thác điều kiện thời gian và sửa đổi hạn mức; hai câu thuê khai thác thời hạn hợp đồng đi thuê và tiền sẽ thu của bên cho thuê.

Độ khó được gán theo thao tác đọc: Easy tra trực tiếp; Medium phân biệt chính sách/trường hợp, vai trò, kỳ hoặc loại giá trị; Hard định vị hợp đồng và giới hạn lồng nhau hoặc hàng lặp trong bảng nhiều phần. Đây là đánh giá biên soạn, chưa hiệu chuẩn bằng kết quả người dùng/mô hình. Năm 2025 chiếm 7/15 mẫu; không ép đủ mọi năm hoặc mọi doanh nghiệp khi chỉ có 15 câu. Có 10 đáp án number, 3 text, 1 date và 1 entity.

Không suy dấu gạch/ô trống thành 0. Đáp án tiền giữ nguyên độ chính xác, dấu phân cách và VND; không tự quy đổi tỷ/triệu. Đơn vị AMC_2021 lấy từ phần cơ sở lập BCTC trang 11; ALT_2023 từ chính sách đơn vị tiền tệ trang 14; CAG_2025 từ trang 13. Phạm vi hợp nhất được ghi rõ cho BCC_2024 và ALT_2023.

## 5. Lỗi và điểm dễ nhầm đã xử lý

- Loại các vùng đã audit chỉ ra thiếu/mâu thuẫn/sai ánh xạ: BCC_2025 không phải bộ BCTC; ô chi phí tài chính so sánh BED_2025 bị mất; bảng ragged và các chỉ tiêu mâu thuẫn ALT_2024, AMC_2023, ARM_2024. Không sửa nguồn hoặc dùng số tính lại làm Gold.
- Khảo sát AMC_2022 trang 9 phát hiện phần thuế/lợi nhuận mâu thuẫn: 8.214.139.129 trước thuế, 11.894.667.360 chi phí thuế và 6.319.471.769 sau thuế; cột so sánh sau thuế là 17.079.045.972, khác 7.079.045.972 ở AMC_2021. Không dùng các ô này; chọn doanh thu AMC_2021, không tự sửa AMC_2022.
- BPC_2025 trang 14 có hai bảng đầu tư giống header: chọn đúng bảng cuối năm và cột giá trị hợp lý, không lấy giá gốc/dự phòng hoặc giá trị đầu năm.
- CAG_2025 có tiền thuê phải trả tại trang 27 và tiền cho thuê sẽ thu tại trang 30: mẫu 0012 chỉ hỏi tiền sẽ thu, không ghép hai bảng.
- BBS_2025 có hai giới hạn thời gian trong một ô: giữ đủ cả hai, không rút gọn còn 13 tháng hay tính ngày đáo hạn. BKC_2023 phân biệt hạn mức gốc/sau sửa đổi với dư nợ. ALT_2023 phân biệt ba phần nguyên giá/hao mòn/giá trị còn lại và các hàng cuối năm trùng tên.
- Không phát hiện lỗi buộc thay thế sau khi chốt 15 mẫu. Những điểm trên là kiểm soát tuyển chọn và lỗi nguồn đã gặp, không phải đánh giá tỷ lệ lỗi toàn corpus.

## 6. Validation và bàn giao

Kiểm tra nhẹ bằng Python trên corpus local: JSONL parse được; đúng schema/15 dòng; ID tuần tự và duy nhất; phân bố 5/7/3; không trùng câu hỏi. Toàn bộ 15 document/page references và 10 table references tồn tại, khớp Markdown/JSON/TXT. Trích dẫn là chuỗi nguyên văn liên tục trên đúng trang; các ô đáp án bảng được đối chiếu đúng hàng/cột JSON. Đọc lại 15 mẫu: đáp án phù hợp doanh nghiệp/kỳ/đơn vị, một đơn vị bằng chứng đủ trả lời, không Multi-hop/Numerical, không trùng bản chất câu hỏi. Kiểm thủ công là căn cứ cho ý nghĩa/độ khó; script chỉ kiểm cấu trúc và đối ứng nguồn.

Hash 123 file neutral và audit được đối chiếu trước/sau; giữ nguyên. Planning checker và `git diff --check` được chạy local. Không chạy full CI, Gemini/API, benchmark hoặc pipeline smoke.

**Schema:** giữ nguyên brief, không đề xuất thêm trường cho P1A. Dùng `table_id=null` cho văn bản; locator chứa kỳ, phần bảng và header khi cần. Không thêm metadata/reasoning vào dataset.

**Implementation:** commit chứa hai deliverables; planning ghi SHA implementation đã xác minh sau khi commit. Trạng thái **REVIEW**, chưa tự nghiệm thu DONE.

**Next action:** Tech Lead review 15 QA và phê duyệt hoặc yêu cầu chỉnh P1A.
