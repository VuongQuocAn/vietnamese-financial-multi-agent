# ViFinBench-DATA-AUDIT-01 — Audit Neutral Corpus

Ngày khảo sát: **13/11/2026**, Asia/Bangkok. Trạng thái task: **REVIEW**,
chờ Tech Lead; kết luận dữ liệu: **READY_WITH_CAVEATS cho Pilot có kiểm chứng nguồn**.
Full 600 chưa đủ bằng chứng để phê duyệt. Đây là benchmark độc lập DACNTT.

## 1. Kết quả chính và phương pháp

Corpus thực tế ở `ViFinBench/neutral`: **15 doanh nghiệp, 41 thư mục tài liệu,
123 file, 1.488 trang đã xuất, 9.861.632 bytes (9,405 MiB)**. Có **2.068 bảng,
16.829 hàng, 69.578 ô**, trên 1.080 trang có bảng. Không phải 41 BCTC đầy đủ:
38 export ghi `complete`, 3 export `partial`; trong 38 complete có BCC_2025 thực chất
là công văn công bố/giải trình 2 trang. Vì vậy có **37 BCTC complete theo export,
3 BCTC partial và 1 tài liệu công bố/giải trình**, chưa xác minh toàn bộ tính đầy đủ
so với nguồn gốc của 37 BCTC.

Kiểm kê toàn bộ 123 file bằng [script](../scripts/audit_vifinbench_neutral.py),
không gọi model/API. Script đọc UTF-8/JSON, duplicate JSON keys, page markers,
table references/IDs, hàng/cột, tái dựng Markdown, hash/trùng và số học.
Đọc mẫu có mục tiêu 46 trang neutral thuộc 19 tài liệu/15 doanh nghiệp, gồm excerpt
văn bản và các bảng được chọn; không chấm mọi ký tự/ô của 46 trang. Đọc bổ sung
các bảng có mâu thuẫn số học/liên kỳ. Đối chiếu trực quan **14 PNG nguồn của 6 tài
liệu/3 doanh nghiệp** và **3 trang PDF BCC_2025** để kiểm danh tính. Mẫu chủ đích,
thiên về lỗi và bảng phức tạp, không phải mẫu ngẫu nhiên để ước lượng accuracy.

Evidence local tái lập được ở `artifacts/evidence/ViFinBench-DATA-AUDIT-01/`:
`inventory.json`, `text-sample-selection.json`, `visual-source-manifest.json`,
`topic-coverage.json`, `reference-calculations.json`, `visual/`.
Ảnh/raw/PDF và kết quả local này không đưa vào Git. Chạy lại kiểm kê:

```bash
python scripts/audit_vifinbench_neutral.py --output artifacts/evidence/ViFinBench-DATA-AUDIT-01/inventory.json
```

## 2. Kiểm kê theo doanh nghiệp và năm

Mỗi ô năm: `năm:số trang xuất`; `*` làpartial. Dung lượng gồm cả 3 định dạng,
không phải ba corpus độc lập. Tên doanh nghiệp lấy từ nội dung neutral, chưa phải
registry pháp nhân đã xác minh bên ngoài.

| Mã / doanh nghiệp | Năm:trang | Tài liệu | Trang xuất | Bảng | Bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| ADC — Mĩ thuật và Truyền thông | 2021:33;2022:33;2023:34;2024:32;2025:42 | 5 | 174 | 274 | 1.111.001 |
| ALT — Văn hóa Tân Bình | 2023:47;2024:47;2025:44 | 3 | 138 | 201 | 937.019 |
| AMC — Khoáng sản Á Châu | 2021:34;2022:35;2023:33;2024:34;2025:35 | 5 | 171 | 228 | 1.165.317 |
| AME — Alphanam E&C | 2023:42;2024:40*;2025:37 | 3 | 119 | 161 | 821.280 |
| ARM — Xuất nhập khẩu Hàng không | 2023:40;2024:42;2025:40 | 3 | 122 | 151 | 774.392 |
| ATS — Tập đoàn Đầu tư ATS | 2023:32;2024:31;2025:29 | 3 | 92 | 128 | 570.335 |
| BBS — Vicem Bao bì Bút Sơn | 2023:29;2024:26;2025:24 | 3 | 79 | 113 | 550.972 |
| BCC — Xi măng Bỉm Sơn | 2021:40;2022:38;2023:44;2024:41;2025:2† | 5 | 165 | 209 | 1.103.300 |
| BED — Sách và Thiết bị trường học Đà Nẵng | 2023:40;2024:40;2025:41 | 3 | 121 | 185 | 737.349 |
| BKC — Khoáng sản Bắc Kạn | 2023:41;2024:39;2025:39* | 3 | 119 | 155 | 793.258 |
| BPC — Vicem Bao bì Bỉm Sơn | 2025:24 | 1 | 24 | 39 | 161.184 |
| BTS — Xi măng Vicem Bút Sơn | 2025:37 | 1 | 37 | 44 | 231.375 |
| BTW — Cấp nước Bến Thành | 2025:44 | 1 | 44 | 48 | 260.476 |
| C 69 — Xây dựng 1369 | 2025:48* | 1 | 48 | 76 | 384.544 |
| CAG — Cảng An Giang | 2025:35 | 1 | 35 | 56 | 259.830 |
| **Tổng** | 2021–2025 | **41** | **1.488** | **2.068** | **9.861.632** |

† BCC_2025 không có bảng và không chứa bộ BCTC được nhắc đến trong công văn.
Phân bố tài liệu theo năm:2021=3,2022=3,2023=10,2024=10,2025=15.
Độ sâu thư mục 1–5 năm đúng; độ sâu **BCTC thực có** củaBCC chỉ 4 năm 2021–2024.

| Export partial | Trang có / trang theo nhãn và missing_pages | Trang thiếu |
| --- | ---: | --- |
| AME_2024 | 40/42 | 9,10 |
| BKC_2025 | 39/40 | 38 |
| C69_2025 | 48/49 | 30 |

Cộng 1.492 vị trí trang theo metadata (1.488+4), **không phải số trang PDF độc lập
đã xác minh**. AME_2024 p8 là phần tài sản, p11 là LCTT: khoảng thiếu p9–10 nằm
ngay vùng báo cáo chính; không tạo QA cần những trang đó. BKC p37→39 và C 69 p29→31
bị gián đoạn; không diễn giải vắng thông tin là doanh nghiệp không có giao dịch.

## 3. Chất lượng và tính nhất quán định dạng

Tên thư mục `<SYMBOL>_<YEAR>`; complete có `document.txt`, `document.md`,
`tables.json`; partial có hậu tố `_PARTIAL` trên cả 3 file. Không thiếu file trong
bộ 3 tương ứng trạng thái; không có file rỗng, lỗi UTF-8/JSON, duplicate JSON key,
document ID sai, trang lặp/đảo thứ tự hoặc tham chiếu bảng mất đích được phát hiện.

TXT dùng `[PAGE n]` và `[TABLE: id]`, **không chứa hàng/ô bảng**. Markdown có
`<!-- document=...; page=n -->`, heading và bảng. JSON có `document_id`, `status`,
`missing_pages`, `tables`; mỗi bảng có `table_id`, `document_id`, `page`, `table`.
Toàn bộ 2.068 bảng khớp tham chiếu TXT/trang và tái dựng Markdown theo quy tắc
export; token văn bản ngoài bảng khớp TXT/MD sau bỏ heading/list markup và tiêu
đề bảng được exporter thêm từ JSON. Đây là đối ứng **giữa các bản phái sinh cùng
nguồn refinement**, không phải 3 lần xác minh độc lập. So sánh token cũng không
kiểm mọi dấu câu/khoảng trắng.

TXT 2.445.364 bytes; Markdown 4.084.160 bytes; JSON 3.332.108 bytes. Không thấy ký tự
replacement U+FFFD. Các đoạn đọc được phần lớn giữ câu/đoạn và dấu tiếng Việt;
vẫn có lỗi rõ như ADC_2021 p11 `Dou thu`, p5 `BẢO CÁO`, địa chỉ `Giàng Võ` ởp11
so với `Giảng Võ` ởp8. Không có ảnh tương ứng ADC để xác định lỗi sinh ở bước nào.
Đầu trang BED_2025 p15 bắt đầu bằng phần câu tiếp từ trang trước; đây là nối trang
cần bảo toàn, không được tự kết luận mất câu. Đoạn chính sách tồn kho/khấu hao p15
khớp nội dung và 4 khoảng thời gian trên PNG đã xem.

**173 hàng tại 21 bảng/10 tài liệu khác độ dài columns**:168 hàng thừa ô,5 hàng thiếu
ô. Markdown exporter đệm header/row cho đủ chiều rộng nên nhìn được bảng không
đồng nghĩa ánh xạ đúng. Ví dụ ADC_2022_p009_t001 có 4 header nhưng 5 ô/hàng; ô đầu
là tên chỉ tiêu trong khi header đầu là `Mã số`. ALT_2024_p032_t001 có 7 header,
8 ô/hàng ở bảng thuế. Không dùng `zip(columns,row)` để lấy Gold vì sẽ lệch/cắt ô.
Không tự sửa nguồn trong audit.

Có 2 bảng không có hàng dữ liệu: `ALT_2023_p047_t003` (vùng ký tên) và
`C69_2025_p024_t001` (header loại TSCĐ/số năm). Bảng thứ hai có thể thiếu nội
dung quan trọng; chưa có PNG để kết luận. Trong 69.578 ô có 8.043 ôtrống,5.506 dấu
gạch và 2.358 số đặt trong ngoặc; toàn bộ ô làstring, không cónull. Những dấu
ngoặc/số âm được giữ ở nhiều mẫu, nhưng ôtrống/gạch không tự mang nghĩa 0.

## 4. Mẫu nguồn và các vấn đề thực tế

| Mẫu xem trực quan | Phạm vi đối chiếu / kết quả |
| --- | --- |
| BBS_2023 PNG p21 | Hợp đồng vay, hạn mức, ngày và tài sản đảm bảo; sau phóng to, cụm `12 tháng kể từ ngày20/05/2023` có trên ảnh, không phải bằng chứng model tự bổ sung |
| BBS_2025 PNG p5,7,8 | BCĐKT/KQKD/LCTT: kỳ, mã chỉ tiêu, số âm và các operand nêu ở§6 khớp phần ảnh đã xem |
| BBS_2025 PNG p18,19 | Bảng biến động vay và hợp đồng vay rộng/nhiều dòng; số dư, tăng/giảm, hạn mức được giữ; nhãn chi nhánh bị tách thành hàng riêng, cần nối đúng ngân hàng |
| BCC_2024 PNG p9,11,12 | Bảng hợp nhất, số âm lớn, lợi nhuận mẹ/NCI và dòng tiền; các số minh họa ở§6 khớp ảnh; sourcep11 cũng in công thức doanh thu `10=01`, nên không tin công thức in sẵn thay cho operand |
| BED_2023 PNG p28 | Bảng vốn chủ sở hữu xoay 90 độ: ảnh có 6 cột kể cả nhãn, JSON có 6 header nhưng 7 ô/hàng do thừa một ôtrống; số quỹ/LNST/tổng bị lệch nếu đọc theo index header |
| BED_2025 PNG p10 | **Lỗi mất số đã xác minh:** hàng mã 22, kỳ 2024 trên ảnh là 21.200.004 VND, JSON làchuỗi rỗng; mã 23 cùng kỳ vẫn giữ 21.200.004. Bảng rectangular và vài tổng khớp không phát hiện được mất ô này |
| BED_2025 PNG p15 | Đoạn chính sách và bảng khấu hao đọc tốt; phải phân biệt khoảng năm với phép trừ và số kế toán |
| BCC_2025 PNG p1,2 | Công văn 933/935, công bố và giải trình BCTC hợp nhất; p2 có số làm tròn 25,48 tỷ/33,61 tỷ và tỷ lệ, không có báo cáo chính |
| BCC_2025 PDF p1–3 | PDF 30 trang làBCTC **riêng**, cover/mục lục/báo cáo BGĐ khác PNG/neutral 2 trang. Cùng mã/năm không đủ để bind nguồn |

Không xác nhận được nội dung Gemini bịa thêm trong các đoạn đã đối chiếu; cũng
**không thể loại trừ** trên toàn corpus hoặc quy mọi mâu thuẫn choGemini. Nguồn
raw OCR/trang refined, prompt/model/fingerprint không đi kèm neutral. Không dùng
kiến thức kế toán thông thường để tự điền phần bị thiếu.

Mẫu đọc neutral bổ sung: ADC_2021 p3,8,11; ADC_2022 p9,10; ALT_2024 p8,32,34;
AMC_2022 p6,10; AME_2024 p8,11; ARM_2023 p8,25; ATS_2025 p8,20;
BKC_2025 p14,37,39; BPC_2025 p6,14; BTS_2025 p7,24; BTW_2025 p10,21;
C69_2025 p16,24,29,31; CAG_2025 p7,27,30. Các mẫu này bao phủ kiểm toán,
chính sách, sở hữu, thuế, khoản vay, dự phòng, tài sản cố định, giao dịch liên
kết và EPS; nhiều mẫu chỉ đọc excerpt/bảng, chưa kiểm nguồn trực quan.

## 5. Provenance và trùng lặp

Có thể dẫn chính xác tới **document ID, trang export, table ID, row/column index
và nguyên văn header/label**. Ví dụ `BBS_2025_p007_t001`, row 4/col 4 tính từ 0,
header `Năm2025`, mã 20; nên lưu cả label thực tế để tránh index đổi sau sửa dữ
liệu. MD không cótable IDhiển thị, vì vậy cần đối ứng JSON+TXT. Số `p007` là
trang export; trên ảnh BBS p7 footer in 6. Không đồng nhất trang scan với trang in.

Neutral không chứa URL tải gốc, hashPDF/PNG, bbox/ô ảnh, report scope chuẩn hóa,
trạng thái audit của từng ô, hay uncertainty flags: **0/2.068 table records có
trường `uncertain`**. `complete` chỉ là trạng thái export theo tập đầu vào,
không chứng minh đúng tài liệu/đủ BCTC/đúng số. Năm kỳ và đơn vị đôi khi chỉ ở
đoạn ngoài bảng (`Năm nay`, `Số cuối năm`), phải đọc ngữ cảnh trang/report.

PNG local có cho 11 tài liệu trùng key: BBS 2023–25,BCC 2021–25,BED 2023–25,
tổng 365 trang, tương ứng 10 BCTC và 1 công văn. **Chỉ 14 PNG đã được xem trực quan**;
sự hiện diện file không chứng nhận mọi trang đã bind đúng. 30 keycòn lại chưa
thấy nguồn trực quan trong storage đã khảo sát. Có 7 PDF trong storage: BBS 2021–25,
BCC 2024–25; BBS 2021/22 không thuộc neutral. BCC 2025 đã xác nhận mismatch; bốn PDF
cùng keycòn lại chưa xác minh đầy đủ association trong audit này. Không truy
cập tài khoản Drive, không tải thêm dữ liệu và không quét toàn bộ ổ đĩa cá nhân.

Không cófile trùng byte hoặc nguyên bộ tài liệu trùng hoàn toàn. Có 29 nhóm bảng
trùng cấu trúc+nội dung (35 bản vượt bản đầu), nhiều bảng ký tên/chính sách. Có
1 cặp trang TXT giống sau chuẩn hóa whitespace: BBS_2023 p12/BBS_2024 p14.
Đây là so sánh phần TXT với placeholder, không khẳng định bảng trên 2 trang giống.
Không đo fuzzy/semantic duplication toàn corpus; boilerplate và cùng kỳ xuất
hiện ở báo cáo kế tiếp vẫn có thể gây trùng và leakage.

## 6. Đối chiếu số học bằng Python

**358 phép đối chiếu cùng bảng/kỳ, trên 40 tài liệu có bảng:354 khớp,4 không khớp.**
Parser chỉ nhận số nguyên hoặc grouping nghìn rõ bằng dấu chấm/phẩy, bảo toàn
ngoặc âm; không chuyển blank/gạch thành 0. Bỏ bảng ragged, thiếu mã/operand và
trường hợp không đọc rõ cột kỳ. Có cả header `Mã số` và`MS`; không kiểm hết
mọi đẳng thức, không phải tỷ lệ chính xác extraction 354/358.

| Bảng / kỳ | Mâu thuẫn từ các ô JSON | Chênh lệch actual − expected |
| --- | --- | ---: |
| ALT_2024_p009_t001 /2023 | mã 50=8.565.483.318; mã 30+mã 40=17.016.921.523+1.548.561.795=18.565.483.318 | −10.000.000.000 |
| Cùng bảng/kỳ | mã 60=17.019.439.906; 50−51−52=7.019.439.906 | +10.000.000.000 |
| AMC_2023_p008_t001 /cuối năm | mã 440=178.361.908.165; 300+400=27.168.900.820+51.193.007.345=78.361.908.165 | +100.000.000.000 |
| ARM_2024_p010_t001 /2023 | mã 70=17.556.416.481; 50+60+61=−384.125.424+7.935.462.995+5.078.910=7.556.416.481 | +10.000.000.000 |

Đọc liên bảng/kỳ để chẩn đoán: AMC_2023 p7 mã 270 và AMC_2024 p8 số đầu năm đều
78.361.908.165; ARM_2023 p10 và ARM_2024 p10 số đầu năm 2024 đều 7.556.416.481.
ALT_2023 p10 ghi mã 30=7.016.921.523 và 60=7.019.439.906. Những đối ứng này củng
cố nghi vấn chữ số thừa ở bản sau, **không thay thế PDF/PNG và không cho phép
tự sửa số**, nhất là có header `Trình bày lại`/`đã điều chỉnh` ở corpus.

Một số phép tính tham chiếu từ mẫu có ảnh, không tạo thành bộ QA:

- BBS 2025 p5:203.054.141.595+63.032.539.170=266.086.680.765 VND.
- BBS 2025 p7:450.474.531.227−417.992.011.559=32.482.519.668 VND.
  Tăng doanh thu so 2024=26,7131%; biên gộp2025=7,2107%,2024=10,2480%,
  giảm 3,0373**điểm phần trăm**. Doanh thu tăng không có nghĩa biên lợi nhuận tăng.
- BBS 2025 p8: CFO 14.319.681.754−LNST p7 7.249.557.946=7.070.123.808 VND;
  không suy nguyên nhân dòng tiền nếu chưa đọc các khoản điều chỉnh.
- BBS 2025 p18:107.335.623.456+412.590.165.180−412.029.033.352
  =107.896.755.284 VND; tổng đi vay/trả gốc còn đối ứng p8.
  BIDV dư nợp18/hạn mứcp19=29.962.860.942/30.000.000.000=99,8762%;
  đây chỉ là tỷ số hai giá trị công bố, không chứng nhận room tín dụng khả dụng.
- BCC 2024 p12:202.642.595.052−15.430.447.284−225.042.212.668
  =−37.830.064.900 VND; cộng 188.202.362.327 và 332.433.113
  =150.704.730.540 VND cuối năm. Phải giữ ảnh hưởng tỷ giá.

Ô chi phí tài chính bị mất tạiBED 2025 cho thấy tổng đúng ở các probe khác không
chứng minh mọi ô đúng. Tính toán từ số đã sai vẫn có thể ra đáp án nhất quán.

## 7. Khả năng xây dựng QA và ước lượng

**Chưa tạo QA, chưa có QA nào được chứng nhận Gold trong task này.** Các khoảng
dưới đây là kịch bản lập kế hoạch sau lọc/sửa ánh xạ bên ngoài và đối chiếu nguồn,
không phải đếm candidate đã soạn, confidence interval hay cam kết năng suất.

| Subset | Đánh giá lượng có thể tuyển chọn | Cơ sở và giới hạn |
| --- | --- | --- |
| Single-hop | **200–300 case có nội dung/bằng chứng riêng là khả thi có điều kiện** | Kịch bản 5–7,5 anchor khác nhau trên 40 tài liệu có BCTC; ưu tiên chỉ tiêu, kỳ, đơn vị và thuyết minh cụ thể. Dung lượng đủ nhưng chưa chứng minh yield sau kiểm nguồn |
| Multi-hop | **80–120 case là khoảng lập kế hoạch thận trọng;200 chưa được chứng minh** | Kịch bản 2–3 chuỗi bằng chứng thực chất/BCTC; không tính đặt 2 câu hỏi đơn cạnh nhau. Hạn chế ở join ngữ nghĩa, thiếu trang, restatement và nguồn khác phạm vi |
| Numerical | **80–160 case tính toán có ngữ cảnh/bằng chứng riêng;200 chưa được chứng minh theo yêu cầu đa dạng** | Kịch bản 2–4 bài tính đủ operand/BCTC. Khoảng 12–18 họ phép tính có thể khai thác; nhiều doanh nghiệp cùng một công thức không thành 200 bản chất toán học khác nhau |

Phép nhân trên chỉ giải thích quy mô phân bổ cần thử; **chưa biết tỷ lệ lọc bỏ**.
Nếu yêu cầu số lượng Gold có thể bảo đảm ngay từ audit, câu trả lời là **chưa đủ
cơ sở ước lượng** cho cả 3 subset. Không cộng các khoảng thành một bộ đã đạt chất
lượng;200 mỗi subset vẫn là mục tiêu nghiên cứu, không phải kết quả audit.

### Single-hop

Điểm mạnh: hàng nghìn hàng bảng, mã chỉ tiêu và các thuyết minh đặc thù. Chất
lượng tốt nhất là lấy một giá trị/chính sách có ngữ cảnh duy nhất, phân biệt
giá gốc/dự phòng/giá trị ròng, khoản vay/hạn mức, LNST hợp nhất/mẹ/NCI,
ngày cuối kỳ/số so sánh. Hard có thể dựa vào bảng dài/nhiều header và chi tiết
đảm bảo vay BBS p19, nhưng khó truy xuất không được thay cho câu hỏi mơ hồ.
Phải kiểm chứng riêng mục tiêu 40 Hard; không mặc định đủ bằng số trang.

### Multi-hop

Chuỗi có ý nghĩa đã thấy: ngân hàng→số dư vayp18→điều khoản/hạn mứcp19;
thay đổi khoản mục→thuyết minh thành phần→phần giải trình; chính sách dự
phòng→giá gốc/dự phòng→giá trị trình bày. Đáp án phải cần ít nhất 2 đơn vị bằng
chứng và phép kết nối; nếu bỏ một nguồn vẫn trả lời đủ thì không nhận làMulti-hop.
Hai operand cùng hàng để tính tỷ lệ thuộcNumerical, không tự thànhMulti-hop.

40 tài liệu có BCTC chỉ tạo 25 cặp năm kề nhau trong cùng doanh nghiệp trước lọc
partial; nhiều số kỳ trước đã có ngay một bảng nên không cần truy 2 báo cáo.
ARM có `Trình bày lại`, ALT có`đã điều chỉnh`; phải khóa phiên bản số liệu khi
so sánh. Liên doanh nghiệp dễ tạo so sánh cơ học nhưng không chứng minh suy
luận mới; scope hợp nhất/riêng, ngành và đơn vị khác nhau có thể làm câu hỏi
không hợp lệ. BCC 2025 không nối với PDF riêng để hoàn thiện chuỗi hợp nhất.

### Numerical

Có nguyên liệu cho khoảng 12–18 họ: chênh lệch tuyệt đối, tăng trưởng, biên gộp,
biên ròng, tỷ trọng cơ cấu, đóng góp vào biến động, tỷ số thanh khoản, đòn bẩy,
vòng quay/ngày tồn kho, vòng quay/ngày phải thu, ROA/ROE với số bình quân,
đối chiếu tiền, roll-forward vay/vốn, bao phủ lãi vay, EPS và tỷ số dư nợ/hạn
mức. Đây là danh mục khả năng, **chưa xác nhận mọi công thức có đủ operand ở
mọi doanh nghiệp**. Không tự áp công thức thiếu định nghĩa/scope hay ngày quy ước.

Python kiểm được kết quả chính xác, signs, tỷ lệ, làm tròn và đối chiếu liên
bảng; không chứng minh số OCR/đơn vị/kỳ đúng. Chia 0, kỳ gốc âm/chuyển lỗ sang
lãi, phần trăm so với điểm phần trăm, quy đổi VND/tỷ và EPS làm tròn cần quy
ước rõ ở từng câu. CAG 2025 p30 cho EPS/SLCP, BPC 2025 p14 cho giá gốc/giá trị hợp
lý/dự phòng, BBS 2025 p18 cho vay biến động là các dạng ngữ cảnh khác nhau.

## 8. Năng lực Codex và quota tương đối

Codex đọc corpus này, soạn đồng thời câu hỏi/đáp án/evidence/reasoning hoặc
calculation được về mặt thao tác. Trong audit đã tự kiểm kê toàn corpus,
phát hiện mâu thuẫn và đối chiếu một số ảnh. **Chưa đo độ chính xác sinh QA**;
không có cơ sở đưa ra tỷ lệ Gold đáng tin hay khẳng định tự hoàn thành 600 mẫu
chất lượng cao mà không rà nguồn/review.

| Công việc | Mức tự động hóa đáng dùng | Giới hạn |
| --- | --- | --- |
| Đếm, parse, hash, reference, dedup chính xác | Cao bằng Python | Semantic duplication và đủ tài liệu chưa được chứng minh |
| Soạn câu/đáp án/provenance/chuỗi suy luận | Codex làm bản nháp được | Sinh và tự chấm cùng lượt dễ cùng giữ một sai sót |
| Kết quả số và rounding | Cao khi operand/định nghĩa đã khóa | Code không xác minh chữ số nguồn hoặc lựa chọn công thức |
| Kiểm nội dung/chữ số/ô gộp/scope | Phải đọc trực tiếp PDF/PNG | Chưa có ảnh cho 30 key; một số ảnh xoay/thiếu header |
| Công nhận Gold | Cần bước kiểm chứng tách và Tech Lead review | Không lấy tự tin của model hoặc tổng số khớp làm chuẩn |

Lỗi dễ mắc: lẫn kỳ/mã số giữa các báo cáo, trượt header khi ragged, coi ôtrống
là 0, mất ngoặc âm, nhầm chi nhánh/hợp đồng, LNST mẹ với toàn tập đoàn, áp số
trước điều chỉnh vào câu hỏi sau điều chỉnh, bịa nguyên nhân biến động, suy
vắng mặt từ trang thiếu, paraphrase thành mẫu mới và ghi đúng giá trị nhưng
dẫn sai trang. BED/AMC/ALT/ARM/BCC nêu trên là lý do thực tế cần các bước kiểm.

Quota tương đối khi cùng độ khó: Single-hop **thấp–vừa**; Numerical **vừa–cao**
(tính bằng code rẻ, xác minh operand và định nghĩa tốn hơn); Multi-hop **cao**
do phải giữ nhiều nguồn và kiểm từng liên kết. Hard/nhiều ảnh/mâu thuẫn có
thể làm thứ tự thay đổi. Chưa cópilotđo nên không ước lượng token, chi phí,
thời gian hoặc số lượt Codex cho 600 mẫu.

Chưa cần bổ sung doanh nghiệp để bắt đầu Pilot hẹp. Trước Full cần ưu tiên nguồn
trực quan tương ứng 30 key, trang thiếu 4 vị trí và đúng BCTC hợp nhất BCC 2025 nếu
muốn dùng kỳ này; metadata tối thiểu gồm danh tính/scope, hashảnh/PDF, trang
export↔trang in, kỳ/đơn vị và phiên bản điều chỉnh. Không xây schema/framework
mới trong audit; ghi mapping ngoài raw khi được giao tiếp.

## 9. Quy trình đề xuất cho Pilot 45

**Có thể bắt đầu tuyển chọn có kiểm chứng sau Tech Lead review**, dùng 10 BCTC
cóPNG local: BBS 2023–25,BED 2023–25,BCC 2021–24. Chưa gọi corpus nguyên khối là
Gold-ready; chưa tự bắt đầu ViFinBench-P1.

1. Chọn trang/evidence từ 10 BCTC; xác nhận danh tính, scope, kỳ, đơn vị và các
   operand trực tiếp trên ảnh. Tạm loại ôBED 2025 mã 22 kỳ 2024, bảngBED 2023 p28 và
   mọi bảng có ambiguity nếu chưa có mapping được kiểm. Không sửa raw/neutral.
2. Lập danh mục candidate gọn, giới hạn tập trung một report/template; không
   dùng lại cùng fact/computation graph ở nhiều subset chỉ bằng đổi cách hỏi.
   Single-hop cần 1 nguồn, Multi-hop cần liên kết thực chất, Numerical cần phép tính.
3. Tuyển 15 mỗi subset theo **5 Easy/7 Medium/3 Hard**, tổng 45. Độ khó theo yêu cầu
   truy xuất/join/tính và ambiguity đã giải quyết; không gán Hard vì OCR sai.
4. Với mỗi candidate lưu câu, đáp án, doc/scope/kỳ/đơn vị, trang/table/row/col
   hoặc đoạn trích, nguyên văn giá trị và ảnh nguồn; Multi-hop lưu chuỗi hỗ trợ,
   Numerical lưu công thức/operand/rounding và kết quả Python. Đây là thông tin
   cần cho Gold, chưa áp đặt định dạng dữ liệu mới.
5. Đọc kiểm chứng tách khỏi lượt soạn; kiểm cả con số và mức hỗ trợ của mỗi
   câu trả lời. Loại câu không thể xác minh; không bù quota bằng paraphrase.
   Chỉ đưa vào Gold saureview, ghi rõ chưa giải quyết nếu còn mâu thuẫn.
6. Đo số đề xuất/giữ/loại và lý do theo subset/difficulty, công sức/quota quan
   sát thực tế. Khóa nguồn và xem leakage do số so sánh, boilerplate, cùng phép
   tính trước khi thiết kế split. Dùng kết quả này quyết định lại Full 200/subset
   và phân bổ 60 Easy/100 Medium/40 Hard.

Rào cản Full: nguồn không đầy đủ/khác scope; số sai/mất ô; mapping phức tạp;
thiếu bằng chứng 200 Multi-hop thực chất và 200 Numerical đa dạng; chưa đo yield
Gold. Những điểm này không chặn một Pilot có giới hạn, có kiểm trực tiếp.

## 10. Git và validation

Owner cho phép riêng corpus neutral vào Git trong task này. Trước stage đã kiểm
123 file/9.861.632 bytes, file lớn nhất `C69_2025/document_PARTIAL.md`
160.851 bytes; phù hợp Git thông thường, không cần LFS. `.gitignore` hiện có
không bỏ qua neutral; không sửa ignore để mở rộng quyền với data/raw/processed.
Không có PDF/PNG, cache/log/.env/credentials/file tạm trong corpus. Quét các mẫu
Google/GitHub/AWS key, private key và credential JSON field không có finding; đây
là kiểm tra theo pattern, không chứng nhận tuyệt đối mọi dạng secret.

Giữ nguyên 123 file và hash nguồn; manifest SHA256 theo JSON sort_keys/separators
compact của trường `manifest` trong inventory:
`0689379042a006c2e16c4d9b6faa42d9bf923c41f7581f2d70cc89b18038b8ad`.
Mọi file corpus có LF; `.gitattributes` đặt `-text` riêng neutral để checkout
không đổi newline/byte, đồng thời bỏ kiểm trailing whitespace/blank EOF của
snapshot gốc. Lần diffcheck đầu báo whitespace có sẵn; không trim dữ liệu để
làm sạch check. Các file code/docs vẫn kiểm whitespace bình thường. Tách riêng các thay
đổi planning/checker của task khi stage vì working tree có local edits từ task
khác; không stage notebooks/runtime/.env.example/.gitignore hoặc evidence cũ.

Implementation commit **`b613c5894acc4258ad0693ddeb56350dd60c07c3`** đã push
`main`; remote SHA đã xác minh. Commit kế tiếp chỉ cập nhật tracking/checker
và nội dung bàn giao của audit, không sửa corpus hoặc pipeline.

Validation local: **3 targeted tests PASS, Ruff PASS, planning checker PASS,
git diff --check PASS** sau áp dụng thuộc tính snapshot nêu trên. Các targeted
engineering tests kiểm signs/grouping/unknown, cột mã động và mismatch, giữ ô
thừa khi render; **không phải financial accuracy tests**. Đối chiếu 123 hash
working/index khớp inventory; các local edits ngoài task được giữ nguyên. Không full CI,
không pipeline/Gemini/re-extraction, không sinh 45 QA.

**Kết luận:** READY_WITH_CAVEATS cho quy trình tuyển chọn Pilot có ảnh và review;
chưa đủ cơ sở nghiệm thu Full 600. Next action: **Tech Lead review audit và
quyết định phạm vi ViFinBench-P1**.
