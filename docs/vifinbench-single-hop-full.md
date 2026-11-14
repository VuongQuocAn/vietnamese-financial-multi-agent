# ViFinBench-SH-FULL — 200 Gold Single-hop QA

Ngày thực hiện: **14/11/2026** (Asia/Bangkok). Trạng thái: **REVIEW**, chờ Tech Lead nghiệm thu. Chỉ triển khai Single-hop; nhãn Gold ở đây là đáp án đã biên soạn và đối chiếu neutral, chưa phải xác nhận độc lập toàn bộ PDF scan.

## 1. Kết quả và bảo toàn Pilot

**200/200 QA: 15 Pilot giữ nguyên + 185 QA mới; 60 Easy / 100 Medium / 40 Hard; 130 natural (65%) / 70 formal (35%).** ID liên tục `VFB-SH-0001`–`VFB-SH-0200`. Toàn bộ 15 doanh nghiệp, 41 tài liệu và 5 năm tài chính 2021–2025 đều được sử dụng.

Phase 0 đã sao chép Pilot trước khi biên soạn QA mới. SHA-256 của Pilot và backup cùng là:

```text
0730714791e4ff4c1f4b4c426b28de5e70877dfc4d71e32325b36f9c7f9d2011
```

Commit nguồn Pilot: `f44e20828a85546f8fe1492902b0dcbd7d642fa5`; HEAD nguồn khi bắt đầu: `c611313c8dba19081c58b93f4cdee90f4cde7e1f`. Backup không được sửa sau khi tạo; 15 dòng đầu của `full.jsonl` local giữ nguyên byte và thứ tự của Pilot, gồm cả định dạng xuống dòng.

Git có `text=auto`, `core.autocrlf=true`: Pilot local là CRLF (18.237 bytes), blob nguồn là LF (18.222 bytes); nội dung khớp sau chuẩn hóa riêng xuống dòng. SHA-256 blob Pilot nguồn là `3e4011dacdfc154c0ff62b756ff7401f13e2e2fd4c5e1f8ef89e9e40a3003396`. Kiểm bảo toàn ở hai phạm vi: local Pilot = local backup nguyên byte; blob backup được stage = blob Pilot tại commit nguồn nguyên byte, và prefix full được stage = blob Pilot. Không đổi cấu hình Git hay chỉnh Pilot để ép hai kiểu xuống dòng thành một hash.

Ba deliverables:

- [pilot_backup_15.jsonl](../ViFinBench/benchmark/single_hop/pilot_backup_15.jsonl)
- [full.jsonl](../ViFinBench/benchmark/single_hop/full.jsonl)
- [Báo cáo này](vifinbench-single-hop-full.md)

Implementation là commit chứa ba file trên, tra bằng `git log -1 --format=%H -- ViFinBench/benchmark/single_hop/full.jsonl`. SHA cụ thể và kết quả đối chiếu remote được ghi trong bàn giao sau push; không tự gán SHA nguồn thành implementation SHA. Không thay planning vì brief giới hạn đúng ba file; trạng thái REVIEW được ghi tại báo cáo này, registry và các local edits có sẵn được bảo toàn.

## 2. Phân bố

| Độ khó | Pilot | Mới | Tổng |
| --- | ---: | ---: | ---: |
| Easy | 5 | 55 | 60 |
| Medium | 7 | 93 | 100 |
| Hard | 3 | 37 | 40 |
| **Tổng** | **15** | **185** | **200** |

| Nguồn chính | QA |
| --- | ---: |
| B01 | 9 |
| B02 | 23 |
| B03 | 13 |
| B09 | 145 |
| Khác | 10 |

B01/B02/B03 chỉ tính QA dẫn trực tiếp báo cáo chính; chi tiết thuyết minh về cùng chỉ tiêu tính B09. Khác gồm kiểm toán, thông tin doanh nghiệp trên báo cáo Ban Giám đốc và công bố/giải trình; không gán BCC_2025 thành BCTC đủ B01–B09.

**175 QA dẫn bảng / 25 QA dẫn văn bản.** Phân bố answer type:

| Answer type | QA |
| --- | ---: |
| number | 173 |
| range | 3 |
| text | 12 |
| date | 6 |
| entity | 6 |

Number là string số chính xác, giữ dấu âm; không float, không biến ô trống/gạch ngang thành 0. Hai đầu range là string `min`/`max`, không có `value`; ngày là ISO. Tất cả đáp án là giá trị/điều khoản công bố trực tiếp, không tính lại chỉ tiêu hay tỷ lệ. Text nhiều điều kiện có `key_points`.

### Theo doanh nghiệp, tài liệu và năm

| Doanh nghiệp | QA | Tài liệu được dùng (số QA) |
| --- | ---: | --- |
| ADC — Công ty Cổ phần Mĩ thuật và Truyền thông | 22 | ADC_2021 (5); ADC_2022 (4); ADC_2023 (4); ADC_2024 (4); ADC_2025 (5) |
| ALT — Công ty Cổ phần Văn hóa Tân Bình | 15 | ALT_2023 (6); ALT_2024 (4); ALT_2025 (5) |
| AMC — Công ty Cổ phần Khoáng sản Á Châu | 22 | AMC_2021 (5); AMC_2022 (4); AMC_2023 (4); AMC_2024 (5); AMC_2025 (4) |
| AME — Công ty Cổ phần Alphanam E&C | 12 | AME_2023 (3); AME_2024 (4); AME_2025 (5) |
| ARM — Công ty Cổ phần Xuất nhập khẩu Hàng không | 13 | ARM_2023 (5); ARM_2024 (4); ARM_2025 (4) |
| ATS — Công ty Cổ phần Tập đoàn Dược phẩm ATESCO | 14 | ATS_2023 (4); ATS_2024 (5); ATS_2025 (5) |
| BBS — Công ty Cổ phần Vicem Bao bì Bút Sơn | 14 | BBS_2023 (4); BBS_2024 (4); BBS_2025 (6) |
| BCC — Công ty Cổ phần Xi măng Bỉm Sơn | 19 | BCC_2021 (4); BCC_2022 (4); BCC_2023 (4); BCC_2024 (5); BCC_2025 (2) |
| BED — Công ty Cổ phần Sách và Thiết bị trường học Đà Nẵng | 13 | BED_2023 (4); BED_2024 (4); BED_2025 (5) |
| BKC — Công ty Cổ phần Khoáng sản Bắc Kạn | 14 | BKC_2023 (5); BKC_2024 (4); BKC_2025 (5) |
| BPC — Công ty Cổ phần Vicem Bao bì Bỉm Sơn | 8 | BPC_2025 (8) |
| BTS — Công ty Cổ phần Xi măng Vicem Bút Sơn | 8 | BTS_2025 (8) |
| BTW — Công ty Cổ phần Cấp nước Bến Thành | 9 | BTW_2025 (9) |
| C69 — Công ty Cổ phần Xây dựng 1369 | 7 | C69_2025 (7) |
| CAG — Công ty Cổ phần Cảng An Giang | 10 | CAG_2025 (10) |

ATS năm 2023 dùng tên Tập đoàn Dược phẩm ATESCO; từ 2024 dùng Tập đoàn Đầu tư ATS theo metadata. Không suy phạm vi riêng/hợp nhất cho tài liệu `unknown`.

| Năm tài chính của tài liệu | Tài liệu | QA |
| --- | ---: | ---: |
| 2021 | 3 | 14 |
| 2022 | 3 | 12 |
| 2023 | 10 | 43 |
| 2024 | 10 | 43 |
| 2025 | 15 | 88 |

Tài liệu nhiều QA nhất có 10 QA (5% bộ); doanh nghiệp nhiều QA nhất có 22 QA (11%). Đây là phân bổ chủ đích theo vùng nguồn rõ, không lấy mẫu ngẫu nhiên hoặc cân bằng ngành.

Phần ít khai thác: BCC_2025 chỉ có hai công văn nên dùng 2 QA công bố/giải trình; không ghép PDF riêng. Các tài liệu 2021–2022 ít hơn vì corpus chỉ có ADC/AMC/BCC ở hai năm này. Không dùng vùng thiếu AME_2024 p9–10, BKC_2025 p38, C69_2025 p30; phần còn rõ của cả ba export partial vẫn được dùng. Bảng ragged, giá trị hợp lý không xác định và các ô có mâu thuẫn không được dùng làm số Gold. Chủ đề đầu tư, công nợ, vay, tài sản, doanh thu, chi phí, thuế, thuê và chính sách khấu hao đều có QA; vẫn thiên về số liệu bảng (86,5% number), chưa đại diện mọi loại thuyết minh.

## 3. Đối chiếu chất lượng

Đã khảo sát cấu trúc/các vùng ứng viên của cả 41 tài liệu. Biên soạn bằng đọc nguồn neutral và chọn ô/đoạn cụ thể; ghi các đợt xuống file làm việc local. Sau đó đọc lại câu hỏi–đáp án cùng hàng/đoạn nguồn cho **185/185 QA mới** và chạy đối chiếu trực tiếp JSON/TXT, kể cả cột, dòng, nhóm cha và đơn vị. Đây là kiểm biên soạn bởi cùng một lượt tác nhân, chưa phải independent human review hoặc kiểm ảnh toàn bộ 185 QA. Pilot đã nghiệm thu chỉ được kiểm bảo toàn/cấu trúc và tính vào thống kê, không biên soạn lại.

Sau bản nháp đủ 200: **14 QA mới được sửa hoặc thay** (0043, 0044, 0047, 0071, 0076, 0078, 0079, 0083, 0107, 0124, 0141, 0160, 0196, 0197), trong đó **1 ứng viên được thay** tại 0071: chuyển từ quyền giám sát/bảo hiểm thế chấp khá trực tiếp sang điều khoản lãi suất biến đổi có công thức và ngoại lệ. Các sửa khác làm rõ câu hỏi, đồng nhất display với đáp án chọn, bổ sung hàng đơn vị/row_path hoặc chọn nguồn đơn vị gần/phù hợp hơn; không sửa 15 Pilot. Hai chỉnh row_path→ngữ cảnh phẳng ở 0031/0067 đã làm ở đợt biên soạn trước bản nháp đủ 200, ngoài con số sửa sau nháp này.

**0 câu trùng chính xác, 0 ô nguồn lặp và 0 mẫu trùng nghĩa được xác nhận phải loại trong bộ đã chọn.** So khớp câu hỏi bằng SequenceMatcher ngưỡng 0,83 phát hiện 2 cặp tương tự câu chữ: 0120/0154 và 0131/0173. Đọc lại cho thấy khác doanh nghiệp, năm và/hoặc bản chất (lỗ trong năm so với số dư cuối năm), nên giữ; điểm tương đồng không chứng minh không có mọi paraphrase trùng. Đã kiểm thêm cặp chỉ tiêu cùng kỳ xuất hiện lại trong báo cáo năm sau và không chọn lại cùng fact. Không có danh sách đầy đủ số ứng viên bị bỏ trước khi cấp ID nên không bịa số loại ở giai đoạn khảo sát.

Các vùng OCR/bố cục trực tiếp ảnh hưởng tuyển chọn:

- ADC_2021 p26 bảng doanh thu tách một phần chữ số sang cột thuyết minh; bỏ vùng này. ADC_2022 p9, p19–20 và một số bảng khác lệch số cột; không ghép bằng `zip` hoặc tự dịch cột để tạo đáp án.
- ALT_2025 p32 bảng vay có nhãn ngân hàng và dòng kỳ hạn bất nhất; bỏ ứng viên vay ở bảng này. ATS_2023 p22 bảng đầu tư có tổng không khớp các dòng; chỉ dùng thông tin hoạt động doanh nghiệp ở p23, không lấy tổng đầu tư đó.
- Giữ tránh các ô mâu thuẫn audit đã nêu: ALT_2024 p9 kỳ 2023; AMC_2023 p8 tổng nguồn vốn; ARM_2024 p10 tiền cuối năm kỳ so sánh; BED_2025 p10 chi phí tài chính kỳ 2024 bị mất ô. Việc bỏ ô lỗi không làm mất quyền dùng hàng/kỳ khác rõ ràng trong cùng tài liệu.
- Các số trong ngoặc được giữ âm; số dư/biến động, giá gốc/giá trị còn lại/dự phòng, phải thu/phải nộp được phân biệt. Hàng lặp giữ nhãn thật, không tự sửa OCR trong quote.

41 QA mới có `unit_evidence`; còn lại đáp án tiền có đơn vị trình bày trong quote chính. Ưu tiên đơn vị cùng trang/bảng hoặc lời xác nhận báo cáo được trình bày bằng VND; không dùng riêng chính sách tiền tệ ghi chép để suy đơn vị. Khi bảng không ghi đơn vị, dẫn header VND hay chỉ dẫn đơn vị báo cáo liên quan trong cùng tài liệu, đã đọc ngữ cảnh để tránh chỉ dẫn nghìn/triệu. Đây vẫn là hạn chế nguồn trình bày ở mức neutral; không thay bằng chứng bằng suy đoán kế toán. Ba nguồn đơn vị Pilot cũ giữ nguyên theo yêu cầu bảo toàn, gồm caveat chính sách tiền tệ của 0010/0012 đã nêu ở P1A.

Giới hạn: không kiểm lại PNG/PDF cho toàn bộ bộ QA; Markdown/TXT/JSON là các bản phái sinh cùng nguồn nên khớp nhau không phải ba chứng nhận độc lập. Không sửa corpus, metadata hay schema để che mâu thuẫn; không chứng nhận financial accuracy ngoài các evidence đã chọn. Cần giữ các caveat audit và scope `unknown`. Không chia train/dev/test, kiểm leakage đối với tập ngoài corpus, hay chạy mô hình để hiệu chỉnh độ khó trong task này.

## 4. Nhận xét độ khó

- **Easy:** tra cứu một giá trị/tên/ngày rõ; ví dụ 0186 lấy dòng tiền thuần tài chính đã công bố, không cộng các dòng thu/chi. Có hai cột kỳ nhưng không cần đối chiếu hay tính toán.
- **Medium:** cần chọn đúng loại doanh thu, đối tượng công nợ, kỳ hạn khoản gửi, nhóm ngắn/dài hạn hoặc đọc đúng điều kiện của một đoạn; ví dụ 0175 phân biệt kỳ hạn gốc 12–13 tháng và thời gian còn lại dưới 12 tháng, 0199 giữ cả hai lý do không xác định giá trị hợp lý.
- **Hard:** bảng rộng có các vai trò/cột gần nhau; nhãn lặp ở nhiều nhóm/năm; hoặc điều khoản hợp đồng có nhiều mốc, công thức và ngoại lệ. 0071 phải giữ kỳ điều chỉnh, điều kiện điều chỉnh và công thức lãi; 0127 phân biệt phân loại lại nguyên giá với hao mòn; 0141 chọn đúng doanh thu sau giảm trừ, bộ phận và năm trong bảng 7 cột.

Không dùng độ dài câu hỏi làm tiêu chí Hard và không yêu cầu tìm hai bằng chứng độc lập. Các QA hợp đồng như 0043/0083/0119 vẫn có thể dễ hơn dự kiến khi truy hồi đúng đoạn; độ khó phản ánh việc phân biệt hợp đồng/kỳ/đối tượng trên nguồn, chưa đo khả năng mô hình. Cả 40 nhãn Hard và ranh giới Medium/Hard cần Tech Lead review; không khẳng định đã hiệu chỉnh độ khó bằng thực nghiệm.

## 5. Ví dụ

### Easy — VFB-SH-0024

Tại ngày 31/12/2023, tài sản ngắn hạn của Mĩ thuật và Truyền thông là bao nhiêu?

**Đáp án:** 133.207.366.907 VND

**Nguồn:** `ADC_2023`, trang neutral 9, `ADC_2023_p009_t001`.

Chọn trực tiếp tổng tài sản ngắn hạn ở ngày hỏi.

### Easy — VFB-SH-0186

Năm 2025, dòng tiền thuần từ hoạt động tài chính của Vicem Bao bì Bỉm Sơn là bao nhiêu?

**Đáp án:** (719.750.986) VND

**Nguồn:** `BPC_2025`, trang neutral 8, `BPC_2025_p008_t001`.

Dòng tiền tài chính được công bố trực tiếp; giữ dấu âm.

### Easy — VFB-SH-0181

Đơn vị nào được chỉ định kiểm toán báo cáo hợp nhất năm 2025 của Xây dựng 1369?

**Đáp án:** Công ty TNHH Kiểm toán và Tư vấn A&C

**Nguồn:** `C69_2025`, trang neutral 10, văn bản.

Tên kiểm toán viên nằm trong một câu công bố.

### Medium — VFB-SH-0175

Cuối năm 2025, các khoản tiền gửi có kỳ hạn gốc 12–13 tháng nhưng còn dưới 12 tháng đến hạn của Cảng An Giang có giá trị ghi sổ bao nhiêu?

**Đáp án:** 50.000.000.000 VND

**Nguồn:** `CAG_2025`, trang neutral 21, `CAG_2025_p021_t002`.

Chọn giá trị ghi sổ và kỳ hạn còn lại, không nhầm tương đương tiền.

### Medium — VFB-SH-0196

Theo chính sách trong báo cáo tài chính riêng năm 2025, thời gian khấu hao nhà cửa và vật kiến trúc của Xi măng Vicem Bút Sơn nằm trong khoảng bao nhiêu năm?

**Đáp án:** Từ 5 đến 50 năm

**Nguồn:** `BTS_2025`, trang neutral 17, `BTS_2025_p017_t001`.

Đáp án là khoảng năm, không diễn giải thành phép trừ.

### Medium — VFB-SH-0199

Vì sao Alphanam E&C chưa xác định được giá trị hợp lý của khoản đầu tư Minh Nguyên tại cuối năm 2025 theo báo cáo hợp nhất?

**Đáp án:** Khoản đầu tư chưa được niêm yết trên thị trường và các chuẩn mực, chế độ kế toán Việt Nam cùng quy định pháp lý liên quan chưa có hướng dẫn chi tiết về cách tính giá trị hợp lý.

**Nguồn:** `AME_2025`, trang neutral 22, văn bản.

Giữ đủ hai lý do của cùng một đoạn thuyết minh.

### Hard — VFB-SH-0071

Theo thuyết minh hợp đồng 6220-LAV-201700906/HĐTD trong báo cáo riêng năm 2025 của Cấp nước Bến Thành, lãi vay từ tháng thứ 13 được tính và điều chỉnh như thế nào?

**Đáp án:** Áp dụng lãi suất biến đổi, điều chỉnh 6 tháng/lần hoặc khi có biến động lãi suất thị trường theo quy định của Ngân hàng Nhà nước Việt Nam và Agribank. Lãi suất bằng bình quân lãi suất huy động tiết kiệm dân cư kỳ hạn 12 tháng trả lãi sau của Agribank, Vietcombank, Vietinbank và BIDV tại thời điểm điều chỉnh, cộng 1,5%/năm; mức lãi suất theo từng giấy nhận nợ.

**Nguồn:** `BTW_2025`, trang neutral 31, văn bản.

Một điều khoản hợp đồng: lãi suất biến đổi từ tháng 13, chu kỳ/ngoại lệ và công thức.

### Hard — VFB-SH-0127

Trong bảng tài sản cố định hữu hình hợp nhất năm 2023 của Xi măng Bỉm Sơn, hao mòn lũy kế máy móc và thiết bị tăng do phân loại lại là bao nhiêu?

**Đáp án:** 108.146.065 VND

**Nguồn:** `BCC_2023`, trang neutral 25, `BCC_2023_p025_t001`.

Hàng Phân loại lại xuất hiện ở cả nguyên giá và hao mòn.

### Hard — VFB-SH-0141

Doanh thu sau các khoản giảm trừ của bộ phận Kinh doanh sách, VPP năm 2024 trong báo cáo bộ phận của Sách và Thiết bị trường học Đà Nẵng là bao nhiêu?

**Đáp án:** 68.654.625.203 VND

**Nguồn:** `BED_2024`, trang neutral 36, `BED_2024_p036_t001`.

Hai hàng Cộng, hai bộ phận và hai kỳ; giá trị đã công bố, không tính mới.

## 6. Validation và bàn giao

**Focused validation local: PASS.** Không chạy full CI, model judge, Gemini hay API trả phí.

| Kiểm tra | Kết quả |
| --- | --- |
| JSONL UTF-8, schema/answer types/units, số chuẩn và ngày ISO | PASS, 200 QA |
| ID duy nhất, liên tục, tổng và phân bố | PASS, 200; 60/100/40 |
| Pilot/backup và prefix full nguyên byte | PASS, 15/15 |
| Metadata/document/page/table references | PASS, 41/41 tài liệu |
| Đối chiếu QA mới với hàng/cột hoặc đoạn TXT | PASS, 185/185 |
| Header/hàng đủ, row_path và unit_evidence | PASS trong phạm vi neutral |
| Trùng câu/ô nguồn và hai cặp gần câu chữ | PASS; không xác nhận mẫu trùng nghĩa |
| Một đơn vị bằng chứng chính, không phép tính mới | Đã review 185 QA mới |
| 123 file neutral + schema/metadata/Pilot bất biến | PASS, 126 SHA-256 |
| git diff --check và staged diff --check | PASS trước commit |

Kiểm tra ô số đọc trực tiếp tables.json bằng parser số nguyên giữ ngoặc âm và xác nhận string mong đợi; kiểm văn bản bằng substring nguyên văn trong trang TXT. Range đối chiếu hai số đầu–cuối đã công bố. Chỉ giữ file dataset hoàn chỉnh và backup trong Git; scripts biên soạn/check, batch và cache nằm ngoài repository. Việc kiểm nội dung không thay thế nghiệm thu độc lập.

**Blocker thực tế: không có trong phạm vi biên soạn từ neutral.** Dừng ở REVIEW; không chuyển DONE và không triển khai Multi-hop/Numerical.

**Next action duy nhất:** Tech Lead nghiệm thu 200 QA và designed difficulty trước subset tiếp theo.
