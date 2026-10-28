# Trích xuất tài chính tự động — M2-04b

## API và cách chạy

Public API trong `accounting`: `run_automated_pdf`, `extract_financial_page`,
`validate_automated_extraction`, `parse_vietnamese_number`. Luồng offline:
PDF → renderer M1 `load_pages` → Gemini qua Shared Gateway → schema tài chính
`urn:financial-extraction/v1` → context/statement/item resolvers M2 → numeric links.
Không thêm client, agent, OCR framework hoặc thay đổi manual path M2-04a.

```python
from pathlib import Path
from vietnamese_financial_multi_agent.accounting import run_automated_pdf

records = run_automated_pdf(
    Path("data/raw/Financial_Report_pdf/BBS/2025/BBS_2025.pdf"),
    symbol="BBS",
    year="2025",
    pages=[5, 7, 8],
    service=service,
    credential_ref=credential_ref,
)
```

`service` là Gateway service đã cấu hình schema từ `extraction_schema_registry()`;
quota guard/cache dùng cùng registry. Model mặc định theo M1 là
`gemini-3.5-flash-lite`, API cho phép truyền model khác qua Gateway.

CLI tái sử dụng cấu hình/quota/cache và credential loader hiện có:

```powershell
python scripts/run_gemini_ingestion.py data/raw/Financial_Report_pdf/BBS/2025/BBS_2025.pdf --symbol BBS --year 2025 --pages 5,7,8 --output artifacts/item-mapping/M2-04b/new-run --financial --live --policy <local-policy.json> --key-file <local-key-file> --key-index 0
```

Bỏ `--live` để render dry-run, không gọi API. Chỉ ghi vào thư mục artifacts riêng,
không ghi đè output hoặc nguồn. Không xoay key. Retry có mục đích chạy đúng các
trang lỗi trong thư mục output mới; không tự gọi lại trang có cache hợp lệ.
API `cached_records={page_number: record}` render lại PDF và kiểm tra source identity,
image hash, dimensions và schema trước khi dùng cache; không tin trường extraction
đã lưu mà tính lại quyết định từ response. Sai image binding trả lỗi.

## Quyết định và provenance

Schema giữ statement type, context nguyên văn, table dimensions, label/code columns,
headers và cells với text/row/column/reading. Python kiểm tra title/form consistency,
unit/scale, nhãn theo catalog, mã in trên nguồn, bounds, duplicate positions, header
phía trên cùng cột số, reading observed và numeric parser. Binding item/kỳ trùng nhau
chặn cả hàng hợp lệ lẫn hàng mâu thuẫn. Header mô tả rõ ràng CHỈ TIÊU/Mã số/Thuyết minh
không tạo numeric slot. Header không nhận diện vẫn unresolved. B01 bare date được
diễn giải `as_of`; nguyên văn header vẫn được giữ riêng.

`accepted_extraction` có Financial Normalization v1: raw value, Decimal normalized
value, period, currency, scale và provenance. `uncertain` báo xung đột, `unresolved`
báo thiếu dữ liệu hoặc catalog chưa hỗ trợ; response đầy đủ luôn giữ để review.
Manual path vẫn dùng `LinkDecision.accepted` kèm `manual_review`, với ý nghĩa khác.
Không yêu cầu table M1 accepted, OCR witness độc lập hoặc bbox tuyệt đối.

Provenance gồm PDF SHA-256, renderer/DPI/trang, hash ảnh, Gateway model/request ID,
và selector vào **payload extraction** cho context/header/label/code/value.
FinancialSourceReference tái sử dụng trường source_pointer cho selector này;
không phải selector unified trong luồng mới, không bịa raw OCR IDs. Anchor cấp page,
status uncertain, không khẳng định geometry verified. Toàn bộ
`financial_fact_verified=false`. Accepted extraction không phải verified fact.

Parser chỉ nhận số nguyên, dấu chấm nhóm nghìn, dấu âm hoặc ngoặc âm bằng Decimal;
không float, không đổi scale. `-`, trống, `1.25`, dấu phẩy và định dạng không hỗ trợ
trả None. Không suy zero. Giá trị quy đổi theo scale chưa tạo trong task này.

## Pilot thực tế và giới hạn

Chạy PDF thật BBS2025, **chỉ trang 5/7/8 trong 24 trang**, render 200 DPI.
PDF SHA-256 `6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`
trước/sau giữ nguyên. Ảnh gửi SDK có hash trùng ảnh render; kết quả cuối được
replay qua public PDF entrypoint, không truyền ManualReview hoặc expected values.
Đánh giá thủ công thực hiện **sau runtime**: đọc ba ảnh PDF, đối chiếu toàn bộ
28 links accepted (nhãn, mã, kỳ, unit và raw digits); một reviewer. Expected40
từ pilot trước chỉ dùng trong script đánh giá độc lập, không import trong runtime.

| Báo cáo / trang | Hàng nhãn / chuỗi nhãn khác nhau | Mapped đúng / sai | Accepted đúng / sai | Decimal | Uncertain | Unresolved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B01 / 5 | 21 / 19 | 5 / 0 | 10 / 0 | 10 | 0 | 32 |
| B02 / 7 | 19 / 19 | 5 / 0 | 10 / 0 | 10 | 0 | 28 |
| B03 / 8 | 28 / 28 | 4 / 0 | 8 / 0 | 8 | 0 | 48 |
| Tổng | 68 / 66 | 14 / 0 | 28 / 0 | 28 | 0 | 108 |

Hàng nhãn bao gồm section headings, không phải ground truth toàn bộ chỉ tiêu.
Hai hàng B01 có nhãn lặp được đếm riêng. Mapped đúng/sai chỉ đánh giá 14 item
được map; không đo precision/recall toàn PDF. Mỗi hàng có hai period slots.
108 unresolved chủ yếu ngoài catalog, một số ô trống/dấu gạch; không mở rộng
catalog để tăng acceptance. Ví dụ B03 mã50 “Lưu chuyển tiền thuần trong năm”,
`1.208.501.810`, vẫn unresolved vì nhãn chưa hỗ trợ.

Trên cùng **baseline40**: B01 10 accepted/4 unresolved; B02 10/4; B03 8/4.
Tổng 28 đúng/0 sai/12 unresolved, so với M2-04a 6 đúng/0 sai/12 rejected/22 unresolved.
Baseline40 là tập con; không trộn 12 unresolved của nó với 108 unresolved toàn output.

Gemini: **5 API calls**, 3 lượt đầu + 2 recovery calls đúng trang 5/7; 0 provider
failure, 0 transport retry. Lượt đầu có row-count nhỏ hơn max row index ở B01/B02,
bị chặn; làm rõ prompt counts và gọi lại hai trang, không sửa payload thủ công.
Lượt recovery trả thêm descriptive headers; validator bỏ đúng header mô tả khỏi
numeric slots. B03 có cache tốt, không gọi lại. Tổng usage 31.449 tokens
(6.345 input, 25.104 output), monetary cost không đo; không suy bằng zero.
Live wall time chưa instrument. PDF render + cache validation cuối khoảng 1,38 giây
local, không bao gồm thời gian API, không phải benchmark.

Artifacts local ignored: `artifacts/item-mapping/M2-04b/live/` và `retry/`
(raw responses, source manifests, ảnh, meter receipts); `pdf-replay.json`
(quyết định cuối, expected40 comparison, hash trước/sau, post-run evaluation).
Ảnh minh họa thực ở `live/page-5.png`, `page-7.png`, `page-8.png`; không commit.

## Engineering evidence

70 targeted tests PASS: 36 automated mới, 14 manual recovery, 12 item mapping,
8 Gemini ingestion. Ruff changed files (kể cả code block Markdown), planning checker
và diff check PASS. Không chạy full local suite hoặc API trong CI.
[CI40646568615](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40646568615)
PASS mọi bước Python3.11/3.12 đúng [implementation checkpoint912916e](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/912916ed1318628750e160e28338a211e5fc2819).
Lượt130019e dừng ở format ví dụ Markdown; 912916e sửa format và CI PASS.
Chờ Tech Lead review; checkpoint evidence sau chỉ tài liệu.
