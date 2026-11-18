# E2E-GATE-09 — Qwen Thinking và 9 QA Pilot

Implementation `5022a42e9634dc6718e562b65f8122cfc8834441` · **REVIEW**.

## Timeout và preflight

Hai trace ARCH-SIMPLIFY-02 có deadline QA 600 s và timeout HTTPX 60 s.
Coordinator dừng sau 60,208 s, Specialist dừng sau 60,007 s, cả hai trước khi
nhận HTTP response. Profile Thinking đã có ở RequestGateway nhưng mặc định tắt.
Khi profile tắt, Gateway chỉ rút ngắn timeout stage theo deadline còn lại, nên
ngân sách QA dài hơn vẫn giữ mức 60 s do stage khai báo.

Profile nay mặc định bật cho Qwen trong RequestGateway. HTTPX nhận mức tối đa
180 s đã dùng trong QWEN-THINK-01, giới hạn theo deadline còn lại. Các stage giữ
cap token đã khai báo trong context 24K và bỏ floor 8.192 token. Cấu hình
`QWEN_THINKING_BUDGET=false` dùng lại ngân sách do stage khai báo. Lượt 9 QA dùng deadline 600 s
và tối đa 10 calls mỗi câu theo cấu hình Pilot hiện có.

| Probe riêng lẻ | Timeout client | Max output | Kết quả | Tokens ghi nhận | Wall (s) |
| --- | ---: | ---: | --- | ---: | ---: |
| Coordinator | 180 s | 1.800 | HTTP 200, chạm trần token trước JSON hoàn chỉnh | 2.535 | 97,999 |
| Specialist | 180 s | 2.500 | HTTP 524 từ endpoint | Thiếu usage | 125,596 |

Probe Coordinator dùng đúng 1.800 completion tokens. Cap riêng của Coordinator
được đưa lên 2.500 token, bằng cap Specialist, rồi chốt runtime. Hai probe kiểm
tra call riêng. Bản dựng replay ban đầu giữ các trường null của trace và dừng
trước transport. Tổng preflight có 2 calls thật. 11 targeted tests, Ruff
lint/format và diff check đạt trên implementation đã freeze.

## Một lượt 9 QA

Cả 9 QA từ manifest E2E-VAL-01 chạy đúng một lượt trên corpus pin E2E-REMED-04
và cùng implementation SHA. Gold được đối chiếu hậu kiểm. Partial ghi nhận
phần đúng đã phát hành, gồm toán hạng khi thiếu đáp số cuối. IDs có tiền tố `VFB-`.

| QA | Hậu kiểm | Điểm dừng hoặc kết quả | Citations | Calls | Tokens ghi nhận | Wall (s) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| SH-0001 | Correct | Đúng tổng tài sản, M6 ACCEPT và M7 phát hành | 6 | 5 | 15.051 | 170,221 |
| SH-0006 | Abstain | BM25 có kết quả, thiếu candidate về thời gian khấu hao. Plan thêm goal VAS/IFRS | 0 | 3 | 7.712 | 106,944 |
| SH-0013 | Abstain | Specialist đặt `use_graph` sai tầng trong tool request. Hai task phụ thuộc bị chặn | 0 | 3 | 7.633 | 124,560 |
| MH-0001 | Abstain | Financial Tools tìm hai nguồn, gồm sai phạm vi phải thu. HTTP 524 ở Specialist trước claim | 0 | 3 | 5.462 + 1 thiếu usage | 202,017 |
| MH-0006 | Partial | Đúng phần doanh thu. Demand của nhánh tổng tài sản chạm cap 1.200 token. BM25 có một miss | 7 | 9 | 45.171 | 524,175 |
| MH-0013 | Abstain | DAG ba Specialist chạy. BM25 có kết quả và một miss, chưa liên kết chi nhánh, khoản vay và quyền biểu quyết thành claim | 0 | 4 | 11.381 | 202,514 |
| NR-0001 | Partial | Phát hành đúng hai toán hạng. Calculator ra tỷ lệ dạng ratio. M6 loại claim tăng trưởng vì diễn giải và làm tròn sai | 7 | 9 | 41.127 | 482,829 |
| NR-0006 | Abstain | Hai kết quả Financial Tools có trạng thái found, bằng chứng số không đủ điều kiện tạo candidate | 0 | 3 | 5.980 | 90,249 |
| NR-0013 | Abstain | HTTP 524 ở Coordinator trước khi có plan | 0 | 1 | Thiếu usage | 132,061 |
| **Tổng** | **1 correct, 2 partial, 0 incorrect, 6 abstain** | **2 QA gặp lỗi HTTP 524** | **20** | **40** | **139.517 + 2 thiếu usage** | **2.035,570** |

Provider latency cộng dồn 1.952,246 s. 38 phản hồi HTTP 200, 37 có Thinking
được ghi nhận. Sáu calls thành công sau mốc 60 s, 0 client timeout trong gate.
Hai HTTP 524 xuất hiện khoảng 125,5 s ở hai stage khác nhau. Một phản hồi M6
có dấu JSON đóng thừa, được xử lý trong cùng response theo cơ chế hiện có.
Một demand của Specialist hết token. Hai probes ở trên tính riêng khỏi bảng.

## Agent, tools và provenance

- Coordinator có 8 plan hợp lệ cấu trúc và 1 call lỗi HTTP 524. Dependency
  được thực thi trong MH-0013 và NR-0001. Một số plan mở rộng quá yêu cầu, như
  thêm chuẩn mực kế toán hoặc tác động tài chính ở nhóm Single-hop.
- Specialists thực hiện 16 calls chọn công cụ gồm 10 `profitability`, 5
  `liquidity_and_leverage` và 1 `cash_flow_and_earnings_quality`. Có thêm 9
  calls tạo claim gồm 6 `profitability` và 3 `liquidity_and_leverage`.
- Financial Tools tìm được 9 facts và 9 kết quả provenance. BM25 chạy 6 lần,
  gồm 4 found và 2 not_found. EF-EG trả 4 graph contexts trên MH-0006.
  Calculator thực thi `percentage_change` ở MH-0006 và `subtract`, `divide`
  ở NR-0001.
- M6 có 3 API calls, 6 ACCEPT, 1 INVESTIGATE và 1 ABSTAIN. M7 có 3 API calls
  và phát hành 20 citations ở ba QA. Cả 20 pointers resolve theo hash nguồn
  JSON và trỏ về claims trong Ledger.

Receipts, trace và hậu kiểm lưu local trong
`artifacts/evidence/E2E-GATE-09/`. Xác minh 190 runtime blobs đúng SHA, 264 JSON
nguồn, 115 tệp corpus pin và 3 tệp Pilot giữ nguyên. Diff, index và tệp
untracked của checkout gốc khớp trước/sau.

Next action — Tech Lead dùng trace gate và hai lỗi HTTP 524 để quyết định Pilot 45.
