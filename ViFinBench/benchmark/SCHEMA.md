# ViFinBench — Schema v1

**Khóa quy ước dữ liệu v1 ngày 13/11/2026.** Áp dụng các trường chung cho mọi
subset; P1A-Finalize chờ Tech Lead nghiệm thu REVIEW. JSON/JSONL dùng UTF-8;
mỗi dòng JSONL là một item, không có dòng trống. Metadata nằm ngoài từng item.

## 1. Item chung

| Trường | Kiểu / quy tắc |
| --- | --- |
| id | String duy nhất trong benchmark; P1A dùng VFB-SH-0001 đến VFB-SH-0015 |
| task | String tên task; P1A là single_hop; giá trị subset mới phải được duyệt |
| difficulty | easy, medium hoặc hard |
| question_style | natural hoặc formal |
| question | Câu hỏi tiếng Việt tự rõ doanh nghiệp, kỳ và phạm vi khi cần |
| answer | Object theo mục 2 |
| evidence | Object bằng chứng chính theo mục 3 |
| tags | Mảng string nhãn nội dung ngắn, không trùng trong cùng item |

Không lặp ticker/tên công ty/năm/scope thành metadata trong từng item. Khi viết
câu hỏi vẫn phải đủ rõ nếu người đọc chưa có bảng metadata.

## 2. Answer

Mọi answer có `type`, `unit`, `display`, `key_points`. `display` là string tiếng
Việt để đọc; `key_points` là mảng string các ý bắt buộc cho text nhiều điều kiện,
rỗng nếu không cần. Không chứa chuỗi suy luận hoặc quy tắc chấm sai số.

| type | Trường giá trị bắt buộc | Quy tắc |
| --- | --- | --- |
| number | value: string | Số thập phân chuẩn; không float, dấu phân cách nghìn hoặc ký pháp khoa học |
| range | min: string, max: string | Hai số chuẩn, min ≤ max; không có value; đơn vị chung cho hai đầu khoảng |
| text | value: string | Nội dung chuẩn; giữ đủ các điều kiện tài chính |
| date | value: string | Ngày đầy đủ ISO YYYY-MM-DD, ngày lịch hợp lệ |
| entity | value: string | Tên/định danh thực thể chuẩn có căn cứ nguồn |

String số dùng dấu `-` nếu âm, dấu `.` nếu có phần thập phân, không khoảng trắng
hoặc dấu `+`; phần nguyên không có số 0 thừa. Ví dụ `266086680765`, `-125`, `2.5`.
Số tiền hiện tại là số nguyên chính xác. Dấu chấm trong display có thể là dấu
phân cách nghìn tiếng Việt; không phân tích value theo định dạng display.

```json
{"type":"number","value":"266086680765","unit":"vnd","display":"266.086.680.765 VND","key_points":[]}
```

```json
{"type":"range","min":"2","max":"7","unit":"year","display":"Từ 2 đến 7 năm","key_points":[]}
```

Mã unit phân biệt hoa/thường, dùng đúng danh mục:

| Ý nghĩa | unit |
| --- | --- |
| Đồng Việt Nam | vnd |
| Người | person |
| Năm | year |
| Cổ phiếu | share |
| Không áp dụng | null |

Chỉ thêm mã đơn vị khi có dữ liệu thực tế và cập nhật danh mục được duyệt.
Không tự thêm tolerance vào QA; evaluator sẽ quy định sau.

## 3. Evidence

| Trường | Kiểu / quy tắc |
| --- | --- |
| document_id | String đúng định danh corpus, liên kết key trong document_metadata.json |
| page | Integer dương, số trang neutral; phải tồn tại trong tài liệu |
| table_id | String ID bảng nguồn, hoặc null cho văn bản |
| row_label | String nhãn hàng thật; null khi không áp dụng |
| column_header | String header thật của ô đáp án; null khi không áp dụng |
| quote | String trích nguyên văn, đủ ngữ cảnh kiểm đáp án |
| row_path | Mảng string nhãn cha→con thực tế, kết thúc bằng row_label; null khi không cần |
| unit_evidence | null hoặc object gồm page: integer dương, quote: string |

Các key trên hiện diện trong Evidence v1; dùng JSON null, không dùng chuỗi
"null". Với văn bản, table_id/row_label/column_header/row_path đều null. Với bảng,
quote có đầy đủ header và toàn bộ hàng đáp án; thêm hàng phân nhóm khi cần.
Được trích chọn các dòng nguyên văn theo thứ tự từ cùng bảng, không phải chép
cả bảng. Không dùng dấu ba chấm để thay phần bằng chứng quan trọng. Header JSON
có xuống dòng có thể được Markdown trình bày bằng khoảng trắng; nhãn lưu theo JSON.

row_path chỉ chứa cấp thật trong bảng; không biến tiêu đề báo cáo/thuyết minh
thành cấp giả. Ví dụ `["Giá trị hao mòn lũy kế", "Số dư cuối năm"]`. Bảng phẳng
có thể dùng null ngay cả khi row_label đã đủ định vị.

Với answer tiền: nếu quote chính đã xác định rõ đơn vị trình bày, unit_evidence
là null. Nếu chưa rõ, bổ sung quote xác nhận đơn vị ở **cùng document_id**;
page trong unit_evidence kế thừa tài liệu chính, không thêm document_id thứ hai.
Ưu tiên đơn vị bảng; chính sách tiền tệ kế toán không được ghi đè chỉ dẫn trình
bày nghìn/triệu hoặc đơn vị khác. Mâu thuẫn/thiếu đơn vị phải review, không suy đoán.
Nguồn phụ này chỉ xác nhận đơn vị, không dùng để ghép số liệu tạo đáp án Single-hop.

document_id có dạng namespace thực tế của corpus như BBS_2025, C69_2025; table_id
như BBS_2025_p005_t001 phải khớp tài liệu/trang trong tables.json và tham chiếu TXT.
Không tự tái tạo ID thay nguồn. Không đồng nhất page với trang in hoặc trang PDF;
không thêm page_pdf/page_printed, bbox, fingerprint, confidence hoặc metadata model.

## 4. Document metadata

[document_metadata.json](document_metadata.json) là một object, mỗi key là
document_id; mỗi record có đúng các trường:

| Trường | Kiểu / quy tắc |
| --- | --- |
| ticker | String mã doanh nghiệp theo namespace corpus |
| company_name | String tên đầy đủ xác nhận trong nội dung; null nếu chưa xác minh được |
| aliases | Mảng string tên rút gọn/ticker được phép; không dùng alias gây nhầm doanh nghiệp |
| fiscal_year | Integer năm kỳ báo cáo xác nhận từ nội dung; null nếu chưa xác minh được |
| statement_scope | separate, consolidated hoặc unknown |

Tên/alias được chuẩn hóa khoảng trắng và hoa/thường; không tự đổi chữ theo phỏng
đoán OCR. Tên có thể khác giữa các năm, như ATS_2023 và ATS_2024. Ticker ở đây
không phải chứng nhận đối chiếu sàn. Không suy scope chỉ vì thiếu chữ “hợp nhất”;
cần tiêu đề, nội dung công bố rõ hoặc checkbox đã đánh dấu. unknown là chưa xác nhận.

Scope mô tả BCTC trình bày hoặc được công bố trong tài liệu, không chứng nhận
export chứa đủ bộ BCTC. BCC_2025 là hai trang công bố/giải trình về báo cáo hợp
nhất; không ghép PDF khác cùng mã/năm. Không thêm industry hoặc dữ liệu suy đoán.

## 5. Mở rộng P1B/P1C

Giữ nguyên ý nghĩa, kiểu và mã của các trường chung v1. Multi-hop có thể bổ sung
danh sách bằng chứng hỗ trợ dùng cùng cấu trúc Evidence; Numerical có thể bổ
sung phép toán và tham chiếu toán hạng để kiểm chứng. Phải công bố phần mở rộng
được duyệt trước khi sinh subset; không đổi evidence gốc thành mảng hoặc đổi
number string thành float. Không triển khai schema mở rộng, evaluator hoặc QA
P1B/P1C trong P1A-Finalize.
