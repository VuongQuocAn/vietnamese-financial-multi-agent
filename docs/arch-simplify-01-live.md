# ARCH-SIMPLIFY-01 — Kết quả điều phối M5

Implementation `5cb38bd4853c7bbbe054a79ea18c54ba2b2d1408`.

## Luồng M5

Coordinator nhận câu hỏi và inventory của filing đã pin, chọn goals, role, tools,
nguồn và dependency trong một lượt. Python kiểm schema, handles và DAG. Task lỗi
và các task phụ thuộc bị ghi gap, các nhánh hợp lệ tiếp tục. Bỏ Regex suy mục tiêu,
ghi đè handle và fallback thay cả plan trong đường Qwen/V2. BM25 giờ là tool của
task trong cùng DAG. Lượt chọn nguồn theo kết quả mới chỉ chạy khi plan yêu cầu.

Specialists dùng chung Financial Tools, BM25 và EF-EG. Workspace lưu evidence,
candidate và provenance theo task và liên kết bản ghi dependency. Calculator
thực thi phép tính. M6 kiểm chứng claims tài chính và trích dẫn thuyết minh qua
các đường hiện hành. M7 dùng kết quả đã admit vào Ledger và citations.

## Kiểm thử

37 targeted tests PASS, gồm giữ nhánh hợp lệ, thứ tự DAG, chia sẻ nguồn,
truy xuất liên role và smoke mixed từ API đến M7. 8 tests của planning checker,
Ruff, planning check và diff check đều PASS.

Ba câu Pilot được chốt từ manifest trước khi đối chiếu Gold. Mỗi câu một
lượt trên Qwen đang phục vụ và corpus pin của E2E-REMED-04. Trace, request và
response lưu local trong `artifacts/evidence/ARCH-SIMPLIFY-01/live-three/`.

## Kết quả live

| QA Pilot | Kết quả M7 | Citations | API calls | Tokens | Wall (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| Single-hop · VFB-SH-0001 | Abstain (`internal_error`) | 0 | 1 | 4.329 | 36,131 |
| Multi-hop · VFB-NR-0013 | Abstain (`internal_error`) | 0 | 1 | 4.427 | 117,266 |
| Mixed · VFB-MH-0001 | Abstain (`internal_error`) | 0 | 1 | 5.402 | 95,370 |
| Tổng | 0 đúng, 0 partial, 3 abstain | 0 | 3 | 14.158 | 248,767 |

Accuracy và coverage đều 0/3 theo Gold. Cả ba phản hồi Qwen HTTP 200 và có
Thinking. Tổng provider latency 231,948 s. Usage đầy đủ gồm 10.377 input tokens
và 3.781 output tokens. Cả ba lượt chỉ thực thi Qwen Coordinator. Số lần thực thi
Specialist, Financial Tools/Calculator, BM25 và EF-EG đều bằng 0. M6 chưa nhận
candidate và M7 ghi lỗi kỹ thuật mà không phát hành claim.

- **Single-hop.** G1 chọn đúng handle tổng tài sản cuối 2025. Qwen trả
  `tasks: []`, nên G1 thiếu task thực thi.
- **Multi-hop.** Qwen gán cùng một chuỗi ghép hai S handles vào `source` của
  cả hai goals. Adapter báo `goal_source_invalid` rồi chặn T1 do thiếu goal
  hợp lệ. Plan chỉ chọn dòng tiền kinh doanh, thiếu khoản chi TSCĐ, và khai
  `power` cho phép chênh lệch. Inventory canonical của filing này cũng
  thiếu khoản chi TSCĐ.
- **Mixed.** Qwen chọn đúng hai số dư để so sánh, giao role
  `liquidity_and_leverage` và khai T2 dùng kết quả T1 để tìm bảng thuyết minh.
  Hai goals bị loại vì `source` chứa chuỗi ghép handles. T1 còn khai `power`
  cho so sánh. Label của T2 cũng thiếu yêu cầu chọn đối tượng lớn nhất mà
  phép chọn bảng hiện hành cần để replay.

Đối chiếu 190 runtime blobs với implementation SHA và receipt. Hash của 264
JSON nguồn, 115 pins nhập, 3 tệp Pilot và 80 local edits khớp. Ba lượt dùng đúng
một implementation. Các kết quả live ghi nhận điểm dừng ở lập kế hoạch, trước
khi có thể đo phối hợp, provenance phát hành hoặc chất lượng M6/M7.

**REVIEW**. Next action — Tech Lead review bằng chứng để quyết định chuyển sang
`E2E-GATE-09`.
