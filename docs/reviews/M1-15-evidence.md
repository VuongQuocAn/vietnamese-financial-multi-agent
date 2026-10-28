# M1-15 — Gemini-native ingestion evidence

Ngày 2026-10-28; **REVIEW**, chờ Tech Lead. Baseline acceptance
`160de34cd06c8d500c2159be6a93f0f964f594e4`. Một implementation commit chứa report
này; lấy SHA bằng `git log -1 --format=%H`. CI exact SHA xác minh sau push trong
bàn giao cuối phiên, không tạo publication commit chỉ để ghi CI.

PDF thật BBS 2025: 14.501.790 bytes, header PDF, **24 trang scan**, không text layer.
SHA-256 `6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`.
Chọn PDF pages **5 (B01), 7 (B02), 8 (B03), 14/15 (B09)** theo contact sheet;
số trang in trên giấy lần lượt 4/6/7/13/14. Render200 DPI: 1656×2339;
page15 landscape2339×1656, giữ hướng gốc. Manifest lưu PDF/image hashes,
document identity, page number/count, kích thước/DPI. Không ghi source/OCR cũ.

| PDF page | Text accepted / unresolved | Tables accepted / unresolved | Cell text accepted / unresolved | Cell layout accepted / total |
| --- | --- | --- | --- | --- |
| 5 | 6 / 0 | 0 / 1 | 97 / 15 | 64 / 112 |
| 7 | 13 / 0 | 0 / 1 | 87 / 13 | 100 / 100 |
| 8 | 14 / 0 | 0 / 1 | 105 / 18 | 121 / 123 |
| 14 | 18 / 0 | 0 / 3 | 79 / 9 | 80 / 88 |
| 15 | 7 / 0 | 0 / 4 | 137 / 6 | 143 / 143 |
| Tổng | **58 / 0** | **0 / 10** | **505 / 61** | **508 / 566** |

Schema valid5/5; component output5/5, failure0; structure accepted pages0/5.
Geometry accepted0/624, unresolved624; bounds valid562 không chứng minh đúng vị trí.
**M1-compatible:5/5 ở mức partial text/schema adapter**, DU parse thực tế đạt;
raw-loader compatible0/5, DU quality accepted0/5 (missing region provenance).
Không gọi đó là resolved hoặc pipeline M1 đầy đủ. `content_correct=null` toàn trang.
Adapter chỉ map observed text; IDs là JSON pointers của intermediate, không phải
OCR cell IDs. Không thêm bbox/row/column giả; bảng giữ nguyên intermediate vì
DU table origin/raw references chưa biểu diễn được Gemini-native table trung thực.

Đối chiếu trực tiếp ảnh nguồn pages5/14: tiêu đề B01/B09 đúng, tổng tài sản,
khoản dự phòng âm, tiền mặt và tiền gửi ngân hàng đọc đúng trong các mẫu đã chọn.
Lỗi thấy được: dấu gạch ngang thành `_`; page5 khai4 columns dù ảnh5 cột,
hai cột tiền cùng column3; page14 bảng tiền khai rows4 nhưng có cells row4.
Bbox vẫn có dấu hiệu đảo trục/khác thang; không tự sửa. Private
`artifacts/gemini-ingestion/M1-15/pdf/visual-review.json` giữ selectors, hashes và
ví dụ số đúng/sai. Đây là Codex visual spot check, chưa human second review;
không phải accuracy toàn trang/dataset. Không gọi lại Gemini để cải thiện kết quả.

Gemini `gemini-3.5-flash-lite`, selected credential index0/project từ policy đã
xác nhận. **5 requests / 7723 input / 42818 output / 50541 total tokens**;
provider failures0, unknown usage0, retry0. SDK boundary ghi hash/byte count của
một PNG/request; cả5 hashes khớp rendered manifest. Giữ15 RPM/250000 TPM/500 RPD,
không tổng input-token cap; cache Gateway hiện có, marker chống live replay.
Source PDF hash trước/sau khớp. Không tự tuyên bố chi phí billing thực tế.

Entrypoint: `python scripts/run_gemini_ingestion.py <source.pdf|source.png>
--symbol BBS --year 2025 --pages 5,7-8,14-15 --output artifacts/<new-run>`.
PDF hỗ trợ danh sách/khoảng trang; PNG nhận đúng một original page number.
Mặc định dry-run/render, không API. Live thêm `--live --policy <private-policy>
--key-file <private-key-file> --key-index 0`. Output bắt buộc dưới `artifacts/`,
không overwrite; live marker chặn reset/replay. Không log secrets/paths vào prompts.
Một PNG cũ BCC2025/page1 đã dry-run cùng CLI, giữ nguyên bytes2550×3300;
không live PNG bổ sung. Unit test chứng minh PNG bytes đi tới SDK qua Gateway.

Local: **8 focused tests passed**, Ruff lint/format changed files, planning checker,
diff check. Không full local regression; full unit3.11/3.12 do CI hiện có chạy sau
push. Artifacts/data/secrets đều ignored, không stage dataset hay PDF/PNG/JSON.
Next action: Tech Lead review implementation, CI exact SHA và giới hạn adapter trước nghiệm thu.
