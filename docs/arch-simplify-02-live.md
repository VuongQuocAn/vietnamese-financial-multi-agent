# ARCH-SIMPLIFY-02 — Contract tối giản cho Coordinator

Implementation `25df8ebb184fc118373da68cfe0ef0808830d3f2` · **REVIEW**.

Coordinator chỉ xuất goal dạng text và task có role, objective, goal indexes và
dependencies. Adapter giữ task hợp lệ khi một nhánh có lỗi. Specialist chọn
nguồn và công cụ bằng lượt yêu cầu truy xuất hiện có. Python thực thi, lưu
provenance và đưa candidates qua các đường M6/M7 hiện hành.

20 targeted tests và Ruff lint/format PASS. Smoke offline đi qua hai Specialist,
Financial Tools, BM25, EF-EG và M6/M7. Một kiểm thử riêng thực thi Calculator với
provenance của toán hạng. Ba QA live dùng lại manifest ARCH-SIMPLIFY-01 và corpus
pin E2E-REMED-04. Mỗi câu chạy một lượt trên cùng SHA. Gold được đối chiếu sau khi
chạy. Trace và receipt nằm trong `artifacts/evidence/ARCH-SIMPLIFY-02/live-three/`.

| QA | Kết quả | Citations | API calls | Tokens ghi nhận | Wall (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| Single-hop · VFB-SH-0001 | Đúng theo Gold | 6 | 5 | 15.001 | 156,267 |
| Multi-hop · VFB-NR-0013 | Abstain · timeout Coordinator | 0 | 1 | Không có usage | 66,746 |
| Mixed · VFB-MH-0001 | Abstain · timeout Specialist | 0 | 3 | 5.462 + 1 call thiếu usage | 136,205 |
| Tổng | 1 đúng, 2 abstain | 6 | 9 | 20.463 + 2 calls thiếu usage | 359,218 |

Provider latency cộng dồn 339,988 s. Bảy phản hồi HTTP 200 và hai timeout trước
khi nhận HTTP response. Kết quả mẫu là 1/3 đúng và 1/3 có câu trả lời.

- **Single-hop.** Coordinator lập một goal và một task. Specialist
  `liquidity_and_leverage` gọi `get_financial_fact` và `get_evidence_sources` mỗi
  công cụ một lần, rồi tạo một candidate. M6 xử lý dấu đóng JSON thừa bằng cơ chế
  hiện có trong cùng response và ghi 1 ACCEPT. M7 phát hành 6 citations. Cả 6
  JSON pointers resolve theo hash nguồn, gồm 5 từ trang 5 và 1 từ trang 1 của BBS.
- **Multi-hop.** Lượt Coordinator timeout sau khoảng 60 s. Runtime ghi
  `provider_unavailable` trước Specialist và tools.
- **Mixed.** Coordinator lập hai goals và dependency T1 → T2. Specialist
  `liquidity_and_leverage` thực thi `get_financial_fact` và
  `get_evidence_sources` mỗi công cụ hai lần. Model chọn chỉ tiêu tổng phải thu
  ngắn hạn thay cho riêng phải thu khách hàng. Lượt tạo claim timeout sau khoảng
  60 s. T2 (`cash_flow_and_earnings_quality`) bị chặn vì thiếu kết quả T1.
  Hai lượt abstain đều ghi trạng thái kỹ thuật ở M7, với 0 candidate vào M6.

Calculator, BM25 và EF-EG có bằng chứng offline. Lượt live ghi 0 lần thực thi các
công cụ này, nên tiêu chí EF-EG live còn chờ xác nhận. Citations đã xác minh trên
JSON nguồn. Receipt khớp 190 runtime blobs, 264 JSON nguồn, 115 tệp corpus đã pin
và 3 tệp Pilot. Diff và tệp untracked của checkout gốc khớp trước/sau.

Next action — Tech Lead xem trace để quyết định chuyển sang `E2E-GATE-09`.
