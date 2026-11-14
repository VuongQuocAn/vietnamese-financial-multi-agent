# ViFinBench-MH-FULL — Báo cáo biên soạn

Trạng thái: **REVIEW**. Ngày bàn giao: 14/11/2026. Chờ Tech Lead nghiệm thu, chưa chuyển DONE.

## A. Phạm vi và tổng quan

Tạo **200 QA mới**, ID `VFB-MH-0016`–`VFB-MH-0215`, độc lập với 15 QA Pilot
đã được nghiệm thu tại `6f2d2829274880964041b921a2f6ea58aeb54669`.
Full không chứa hoặc sửa 15 câu Pilot; không sửa Single-hop, neutral, schema,
metadata, pipeline hoặc các local changes có sẵn. Hai deliverable là
`ViFinBench/benchmark/multi_hop/full.jsonl` và báo cáo này.

| Chỉ tiêu | Số lượng |
| --- | ---: |
| QA mới | 200 |
| Easy / Medium / Hard | 60 / 100 / 40 |
| Natural / Formal | 178 / 22 |
| Doanh nghiệp / tài liệu neutral | 15 / 41 |
| Single-document / Multi-document | 183 / 17 |
| Evidence | 450 |

Phân bố doanh nghiệp dưới đây dùng tài liệu đầu tiên trong `input_documents`
làm nhóm chính, nên tổng là 200. Một QA đối chiếu BTS–BBS–BPC dùng ba doanh nghiệp.

| Doanh nghiệp chính | QA |
| --- | ---: |
| ADC | 16 |
| AMC | 15 |
| ALT | 11 |
| AME | 11 |
| BBS | 10 |
| BED | 13 |
| ATS | 10 |
| ARM | 9 |
| BKC | 10 |
| BCC | 17 |
| BPC | 8 |
| BTS | 12 |
| BTW | 14 |
| C69 | 27 |
| CAG | 17 |

| Năm tài chính | QA theo tài liệu đầu tiên | QA có sử dụng năm này |
| --- | ---: | ---: |
| 2021 | 11 | 11 |
| 2022 | 8 | 8 |
| 2023 | 26 | 26 |
| 2024 | 30 | 38 |
| 2025 | 125 | 133 |

Cột cuối đếm mỗi niên độ một lần trong một QA; một QA nhiều niên độ đóng góp
cho nhiều hàng. Các năm so sánh được in trong bảng nguồn không tự trở thành
`input_documents` riêng. BCC_2025 chỉ có công bố/giải trình: QA 0205 dùng công văn
để chọn khoản chi phí, rồi tìm số gốc chính xác trong B02 BCC_2024; không giả định
có bộ BCTC 2025 đầy đủ trong tài liệu hai trang này.

## B. Phân bố suy luận và nguồn

Các thống kê là các góc nhìn có thể giao nhau, không phải các subset mới.
Nhãn đầu trong `tags` mô tả bài toán cụ thể; không xem 200 nhãn đó là 200 loại
suy luận độc lập.

| Góc nhìn | QA | Quy ước |
| --- | ---: | --- |
| Bridge/dependent | 103 | Kết quả chọn đối tượng/khoản mục quyết định tra cứu tiếp |
| Compositional/cross-evidence chính | 97 | Đối chiếu dấu, chiều, phân loại hoặc điều kiện giữa các nguồn |
| Chỉ bằng chứng bảng | 133 | Kết hợp ít nhất hai evidence bảng |
| Kết hợp bảng–văn bản | 61 | Có cả evidence bảng và đoạn văn |
| Chỉ bằng chứng văn bản | 6 | Kết hợp điều khoản/đoạn công bố riêng |
| Liên kỳ hoặc hai mốc thông tin | 76 | Gồm đầu–cuối kỳ, niên độ, hợp đồng hoặc sự kiện sau ngày kết thúc năm; rà theo nội dung câu |
| Nhiều tài liệu khác niên độ | 16 | Theo fiscal_year của tài liệu thực sự dùng |
| Nhiều tài liệu khác doanh nghiệp | 1 | Đối ứng phải thu/phải trả BTS–BBS–BPC |
| QA có yêu cầu kết luận nhị phân | 59 | Gồm câu nhiều điều kiện có phần Có/Không; vẫn phải nêu ý bắt buộc |

Các bài toán gồm liên kết khách hàng/nhà cung cấp và nhóm công nợ; bên liên quan
với quan hệ sở hữu/quản trị; gốc vay với hạn mức, kỳ hạn, thế chấp và chuyển phần
đến hạn; dự án với vốn hóa và chi phí kỳ; dự phòng với dòng tiền gián tiếp;
thuế hiện hành/hoãn lại/chuyển lỗ; phân phối vốn và EPS; thay đổi cơ cấu bộ phận;
đối chiếu nhiều báo cáo và trạng thái sau ngày kết thúc năm.

| Kết hợp loại nguồn | QA |
| --- | ---: |
| B01/B02/B03 với B09 | 44 |
| Chỉ B01/B02/B03 | 14 |
| B02 với công bố/giải trình | 1 |
| Chỉ các phần B09 | 141 |

Có **59 QA sử dụng báo cáo chính**, trong đó 12 QA kết hợp từ hai loại báo cáo
chính trở lên. Tần suất tham gia, có giao nhau: B01 **14**, B02 **26**, B03 **31**,
B09 **185**, công bố/giải trình **1**. Không gắn nhãn B09 cho công văn BCC_2025.
Nhóm B09 vẫn chiếm tỷ trọng cao do các liên kết hợp đồng, pháp nhân và công nợ;
đây là độ lệch còn lại của bộ, không phải bằng chứng bộ đã cân bằng các loại nguồn.

## C. Gold, độ khó và tự rà soát

| Answer type | QA |
| --- | ---: |
| text | 179 |
| entity | 13 |
| number | 6 |
| date | 2 |

Sáu đáp án number giữ số chuẩn dạng string; hai đáp án date dùng ngày ISO.
Text được dùng khi cần kết luận cùng đối tượng, kỳ, điều kiện hoặc cách phân loại.
`key_points` là các ý bắt buộc; có thể rỗng với đáp án số/thực thể đơn giản theo
v1. Không yêu cầu mô hình khớp nguyên văn `display` hoặc tái hiện `reasoning`.
Trả lời chỉ “Có/Không” khi thiếu đối tượng, chiều biến động hoặc điều kiện được
hỏi chưa đạt đầy đủ Gold. Các số trung gian trong reasoning không tự trở thành
yêu cầu chấm nếu không nằm trong câu hỏi/key_points.

Ghi nhận **28 QA được chỉnh sửa cụ thể** về số liệu, đơn vị, nhãn quan hệ,
câu hỏi hoặc evidence trong các checkpoint biên soạn. Trong đó, lượt cuối viết
lại **21 câu hỏi** để không tiết lộ dữ kiện đầu tiên rồi chỉ yêu cầu xác nhận dữ
kiện thứ hai. Có **2 ứng viên bị loại/thay** vì gần mô thức đã dùng: một câu dịch
vụ BBS bị loại trước ghép, một câu BTW được thay trong lượt rà cuối. Đây là số
đã ghi nhận, không phải tỷ lệ loại trên toàn bộ các vùng nguồn từng đọc.

Ví dụ chỉnh sửa: giá vốn thành phẩm AMC được sửa về đúng ô nguồn; mã đơn vị
đáp án tiền được chuẩn hóa `vnd`; chọn đúng dòng biến động vốn BED của năm nay;
giữ đúng quan hệ “cùng Tập đoàn” trong ARM_2023; bổ sung yêu cầu ngân hàng vào
câu hợp đồng C69; đổi nguồn phải thu ARM để không dùng một bảng vốn chứa cả hai
phía của đáp án. Các bảng không có title trong JSON được bổ sung tiêu đề mục
nguyên văn vào quote để giữ ngữ cảnh tài chính.

Easy chủ yếu là một phép chọn/ghép rõ ràng giữa hai nguồn. Medium cần phân biệt
nhóm số liệu, kỳ, dòng tiền với ghi nhận hoặc thỏa điều kiện kết hợp. Hard cần
theo nhiều khóa nối, phạm vi công ty mẹ/công ty con, phân loại kế toán hoặc chuỗi
điều khoản có thể gây nhầm. Nhãn độ khó là đánh giá biên soạn, chưa hiệu chỉnh
bằng kết quả mô hình. Số evidence không tự quyết định độ khó.

Phép so lớn/nhỏ, dấu hoặc một tích tỷ lệ đơn giản chỉ phục vụ chọn đối tượng,
giải thích lợi ích gián tiếp hay phân loại. Bộ không lấy tính tỷ số, tăng trưởng
hoặc công thức tài chính làm yêu cầu chính; các bài toán đó thuộc Numerical.

## D. Ví dụ tiêu biểu

### VFB-MH-0167 — Easy

**Câu hỏi:** Công ty liên kết có tỷ lệ lợi ích thấp nhất C69 cuối năm 2025 bắt đầu được ghi quan hệ liên kết từ ngày nào?

**Gold:** Palmyland; từ ngày 26/12/2025.

**Evidence:** `C69_2025`, trang 21, `C69_2025_p021_t001`; `C69_2025`, trang 46, `C69_2025_p046_t003`.

**Suy luận:** So tỷ lệ lợi ích trong danh sách liên kết để chọn Palmyland. → Theo tên tra ngày bắt đầu quan hệ trong danh sách bên liên quan.

### VFB-MH-0068 — Medium

**Câu hỏi:** Trong danh sách nợ xấu BBS cuối năm 2025, khách hàng có mức dự phòng lớn nhất đang có tổng phải thu khách hàng bao nhiêu?

**Gold:** Công ty Cổ phần Xi măng Hạ Long; tổng phải thu khách hàng 22.675.923.587 VND.

**Evidence:** `BBS_2025`, trang 15, `BBS_2025_p015_t001`; `BBS_2025`, trang 14, `BBS_2025_p014_t002`.

**Suy luận:** So sánh độ lớn dự phòng âm, Hạ Long có giá trị tuyệt đối lớn nhất. → Dùng tên Hạ Long tra bảng phải thu để lấy tổng dư nợ, không lấy riêng phần nợ xấu.

### VFB-MH-0166 — Hard

**Câu hỏi:** Vì sao công ty liên kết có tỷ lệ lợi ích thấp nhất trong danh sách C69 cuối năm 2025 lại có tỷ lệ biểu quyết cao hơn tỷ lệ lợi ích?

**Gold:** Palmyland được sở hữu qua công ty con Toàn Thắng: Toàn Thắng nắm 25% Palmyland, còn C69 có 51% lợi ích tại Toàn Thắng. Do đó báo cáo thể hiện lợi ích gián tiếp 12,75% và quyền biểu quyết 25%.

**Evidence:** `C69_2025`, trang 21, `C69_2025_p021_t001`; `C69_2025`, trang 21, đoạn văn; `C69_2025`, trang 20, `C69_2025_p020_t001`.

**Suy luận:** Chọn Palmyland là liên kết có lợi ích nhỏ nhất và nhận ra hai tỷ lệ khác nhau. → Theo (i) xác định Toàn Thắng là trung gian sở hữu. → Tra tỷ lệ lợi ích C69 tại Toàn Thắng để giải thích lợi ích gián tiếp và quyền biểu quyết.

### VFB-MH-0149 — Hard

**Câu hỏi:** Hai nhà cung cấp bao bì Bút Sơn và Bỉm Sơn mà BTS còn nợ cuối năm 2025 có ghi khoản phải thu BTS khớp với số phải trả BTS công bố không?

**Gold:** Có cho cả hai: Bao bì Bút Sơn ghi phải thu 32.822.068.156 VND và Bao bì Bỉm Sơn ghi 23.586.264.000 VND, khớp số phải trả tương ứng của BTS.

**Evidence:** `BTS_2025`, trang 36, `BTS_2025_p036_t001`; `BBS_2025`, trang 14, `BBS_2025_p014_t002`; `BPC_2025`, trang 14, `BPC_2025_p014_t003`.

**Suy luận:** Từ sổ phải trả BTS xác định hai doanh nghiệp bao bì và số dư từng bên. → Sang BBS và BPC lấy dòng khách hàng Xi măng Vicem Bút Sơn cùng ngày. → So riêng từng cặp đối ứng, không gộp hai công ty có tên gần giống.

### VFB-MH-0190 — Hard

**Câu hỏi:** Tổng điều chỉnh dự phòng dương trên B03 CAG năm 2025 chủ yếu gắn với tăng dự phòng đầu tư hay dự phòng phải thu? Khoản đầu tư tương ứng là gì?

**Gold:** Gắn với trích bổ sung dự phòng đầu tư vào Dầu khí Mêkông; dự phòng phải thu giữ nguyên và không có hoàn nhập trong năm.

**Evidence:** `CAG_2025`, trang 11, `CAG_2025_p011_t001`; `CAG_2025`, trang 22, `CAG_2025_p022_t001`; `CAG_2025`, trang 21, `CAG_2025_p021_t003`; `CAG_2025`, trang 24, `CAG_2025_p024_t001`.

**Suy luận:** Từ B03 lấy khoản điều chỉnh tổng dự phòng và dẫn chiếu hai thuyết minh. → Bảng dự phòng đầu tư ghi trích bổ sung cùng số, trong khi dự phòng phải thu không đổi. → Đồng nhất số dư dự phòng đầu tư với danh mục Dầu khí Mêkông.

## E. Hạn chế nguồn và giới hạn sử dụng

- Neutral là nguồn được chấp nhận trong task. Không xác minh lại PDF, ảnh hoặc
  toàn bộ OCR; focused validation không chứng nhận số liệu báo cáo gốc tuyệt đối đúng.
- Các vùng có mâu thuẫn trực tiếp được bỏ qua: bảng lệch cột ADC, một số số tổng
  và chi tiết đầu tư ATS/BKC, dòng tồn kho AME_2025, một số số so sánh/lợi nhuận
  ALT và lệch một đồng trong thành phần thuế ALT. Không suy ra cả tài liệu không dùng được.
- Không ghép BKC riêng lẻ và hợp nhất thành chuỗi tăng trưởng mặc định. Với năm
  có metadata scope unknown, không tự gán scope ngoài nội dung nguồn.
- Khi quote không xác định đơn vị trình bày, chỉ dùng định danh, thứ hạng, dấu
  hoặc tỷ lệ được in rõ; không biến các ô đó thành Gold tiền. Với Gold tiền,
  quote hoặc `unit_evidence` cùng tài liệu phải xác định được đơn vị. Không lấy
  chính sách tiền tệ kế toán để tự suy đơn vị nghìn/triệu của bảng.
- Dấu gạch/ô trống được giữ nguyên, không tự đổi thành số 0. Hợp đồng và sự kiện
  tương lai được giữ đúng kỳ; đề xuất hoàn trả không được gọi là tiền đã thu.
- Chú thích dự án công nghiệp C69 có biến thể Yên/Yến Châu; câu 0183 dùng dấu
  dẫn chiếu (i) và pháp nhân chủ đầu tư, không tự sửa tên trong quote.
- Năm 2025, B09 và đáp án text còn chiếm ưu thế. Một số SourceFact được tái dùng
  cho nhiệm vụ khác nhau; dữ liệu chưa có người thẩm định độc lập thứ hai, đánh
  giá thực nghiệm hoặc hiệu chỉnh độ khó. Các QA nhị phân vẫn có nguy cơ đoán
  nhãn; cần chấm đủ key_points, không chỉ từ Có/Không.

## F. Focused validation và bàn giao

**PASS kiểm tra dữ liệu có thể tự động hóa**, bằng Python nhẹ đọc trực tiếp
neutral và hai dataset, không thêm runner/framework vào repository:

- UTF-8/JSONL parse; đúng 200 dòng QA; ID duy nhất, liên tục 0016–0215; đúng
  60/100/40; task/style/Answer v1/Evidence v1 hợp lệ, ngày lịch ISO hợp lệ.
- `input_documents` đúng thứ tự nguồn xuất hiện, không thừa/trùng; setting khớp
  số tài liệu. Mỗi QA có ít nhất hai evidence.
- Document/page/table tồn tại; header và các hàng quote khớp Markdown và JSON
  nguồn; đoạn văn là trích nguyên văn; row_path đúng nhãn/thứ tự; unit_evidence
  tồn tại trong cùng tài liệu. Không phát hiện số tiền có dấu phân nhóm trong
  Gold display vắng khỏi evidence.
- Không trùng ID/câu hỏi nguyên văn với Pilot hoặc trong Full. So gần chuỗi chỉ
  dùng hỗ trợ rà; việc nhận định trùng nghĩa, tính cần thiết của evidence và
  chuỗi reasoning là tự rà nội dung, không phải chứng minh tự động.
- Đối chiếu SHA-256 của **950 file có sẵn ngoài hai deliverable**: bất biến,
  bao gồm Pilot, Single-hop và các local changes đã có. Không stage file ngoài task.
- `git diff --check` và kiểm tra whitespace phần staged: PASS.

SHA-256 Pilot trong Git (LF):
`7e098f09ccef84aa7c9080c8219e70c235d744f6245a11cee21e593e5b03882d`.

SHA-256 Pilot local (giữ nguyên CRLF): `754bb50d63e461f314a962fd48b127945d4d0d2c43a72472cd07092c285ec67a`.

SHA-256 Full (Git, LF): `581f2e8c60f1bc5c225fab4622a88e7d97e172fd62e5ef930d9159e30f804769`.

Không chạy full CI/regression, model evaluation, LLM Judge, Gemini/Qwen/API trả
phí hoặc OCR/PDF verification. PASS trên đây là bằng chứng về cấu trúc, nguồn
trích dẫn và tự rà biên soạn; chưa thay thế nghiệm thu chất lượng tài chính của
Tech Lead. Script/checkpoint tạm không nằm trong commit. Implementation SHA
được bàn giao cùng commit chứa hai file; có thể truy bằng
`git log -1 --format=%H -- ViFinBench/benchmark/multi_hop/full.jsonl`.

**Next action duy nhất:** Tech Lead nghiệm thu bộ MH-FULL đang ở REVIEW.
