# E2E-TECH-FIX-01 — Lỗi kỹ thuật trước Benchmark

**DONE — Tech Lead APPROVED với giới hạn ngày 18/11/2026**.
Implementation cuối `6b181024135bc252abe1f07e45a419e48a01f6e1`; bàn giao `e5b102f`
đã push main và xác minh remote. Phiên đóng chỉ tài liệu/tracking và kiểm
planning/diff/Git; không sửa runtime hoặc chạy lại tests/API/benchmark/CI.
Ba probes chạy trên `a8db198acd43212edf9f98c0e297ee5dd9fa73bf`; baseline `3a08371`.
Ngày 18/11/2026 (Asia/Bangkok). Worktree riêng giữ local edits checkout gốc.

## Nguyên nhân và sửa tối thiểu

| Trường hợp saved gate | Nguyên nhân | Xử lý |
| --- | --- | --- |
| SH-0013, provider 010 | Qwen đặt boolean `use_graph` trong `document_search`; schema extra-forbid loại cả request và BM25 không chạy | Parser chuyển đúng boolean về root nếu không mâu thuẫn; giữ query, kind, goal và raw response. Không chọn công cụ thay LLM; trường lạ/kiểu sai/xung đột vẫn bị loại |
| MH-0006, provider 019 | Demand trả partial, dùng hết 1.200 completion tokens, gồm Thinking và final JSON; input chỉ 2.231 tokens | Cap demand 2.500, bằng Coordinator/Specialist hiện có. RequestGateway tiếp tục giới hạn theo context 24K và deadline; không tăng context/server hoặc retry |
| NR-0006, provider 038–039 | Financial Tools `found` hai records nhưng cả unit/currency/scale đều null; `json_fact_bound=False`, Specialist loại `json_fact_unbound_or_ineligible` | Phân loại thiếu unit/scale trong facts đã pin, không phải mất record/handle qua M5. Replay corpus pin cho đúng hai records, giá trị/pointers giữ nguyên. Không tự gán đơn vị hoặc nới eligibility/M6 |
| SH-0013, probe mới | BM25 tìm bảng, projection đọc `UnderstoodCell.column` dù contract dùng `col`, gây AttributeError trước candidate | Ánh xạ `col` cho UnderstoodCell, giữ `column` của unified/extraction. Sửa đúng field, không đổi nội dung, cách chọn nhãn hay provenance; chỉ xác minh offline, không lặp probe |

NR-0006 còn chọn `b02.sales_revenue` thay `b02.net_revenue` làm toán hạng.
Đây là lựa chọn nguồn của Qwen, giữ nguyên theo phạm vi task. Bảng nguồn ALT
trang 9 không có khai báo đơn vị. Trang 13 nêu tiền tệ ghi chép kế toán; contract
hiện có không tự xem đó là đơn vị trình bày của bảng. Không lấy sự hiện diện số
liệu làm bằng chứng cho unit/scale; không sửa corpus pin trong task này.
`found` không đồng nghĩa đủ điều kiện tạo numeric candidate.
HTTP 524 ở gate thuộc endpoint, tách khỏi lỗi code; không sửa/retry bằng Python.

## Offline

8 targeted controls PASS: 3 tests mới cho cấu trúc request, cap Thinking/context
và `found`/eligibility; 3 evidence coordination controls hiện có; Calculator với
operand provenance; integration smoke M5–Tools–M6/M7. Sau sửa mapping ô bảng,
6 targeted PASS, gồm cả ba controls mới, hai document pipeline/proof controls và
smoke M5–M7. Replay đúng search response gây AttributeError xử lý được một bảng,
bốn nhãn; giữ nguyên record và trả 0 candidates vì kind/query do Qwen chọn
không hỗ trợ claim. Không dùng dữ liệu/LLM giả để báo live thành công.
Ruff lint/format, planning checker và diff check PASS; không full suite/CI hoặc
benchmark. Replay/audit offline không gọi API.

## Live probes

Ba QA có sẵn trong manifest gate, mỗi câu một lượt: SH-0013 kiểm tool request,
MH-0006 kiểm demand và SH-0001 làm đối chứng đủ evidence cho M6/M7. Giữ corpus
pin, model, context 24K, tối đa 10 calls/QA và deadline 600 s; không gửi Gold.
Không live NR-0006 vì replay đã xác nhận thiếu metadata; không chạy lại gate9.

| Probe | Kết quả thực tế trên `a8db198` | Calls | Tokens | Citations | Wall (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| SH-0013 | BM25 found; AttributeError ở projection bảng nhánh phụ thuộc, M6 không chạy | 3 | 10.425 | 0 | 123,466 |
| MH-0006 | Partial; qua Specialists/Financial Tools, M6 4 ACCEPT/1 INVESTIGATE/1 ABSTAIN, M7 phát hành phần có nguồn | 10 | 57.333 | 7 | 520,549 |
| SH-0001 | Completed with caveats; M6 1 ACCEPT, M7 phát hành | 5 | 14.991 | 6 | 136,680 |
| **Tổng** | **Đúng ba probes, không chạy lại** | **18** | **82.749** | **13** | **780,695** |

18/18 HTTP 200 và có Thinking; 0 usage thiếu, 0 HTTP 524, 0 client timeout.
Demand từng hết token ở nhánh tổng tài sản nay hoàn tất JSON với 1.415 completion
tokens, dưới cap 2.500; input của call này 2.247 tokens. M7 vẫn thiếu coverage
tổng tài sản/yếu tố ảnh hưởng. Specialist dùng `E1`/`E2` không được cấp và có
derived proposal thiếu phép tính; đây là output/suy luận của Qwen, không sửa bằng
mapping tùy đoán. SH-0013 còn demand lấy kỳ từ parent chỉ có văn bản và kind/query
không phù hợp, giữ lỗi model. Không đánh giá đây là accuracy benchmark.

Sửa mapping ô bảng ở `6b18102` chỉ có bằng chứng offline, **chưa fresh live**.
Không thêm hoặc lặp probes sau sửa này. Hai lỗi HTTP 524 của gate cũ vẫn được
ghi riêng là endpoint; không lấy việc lượt mới không gặp lỗi làm bằng chứng đã sửa.

190 runtime blobs của live khớp `a8db198`; runtime cuối khớp `6b18102`, chỉ khác
live ở helper projection ô bảng. 264 JSON nguồn, 115 tệp corpus pin, 3 tệp Pilot
và diff/index/untracked checkout gốc bất biến; 13 citation pointers resolve nguồn.
M6 ACCEPT, EF-EG, Gold, model và Colab giữ nguyên. Không còn lỗi implementation
đơn giản đã xác nhận chưa xử lý trong phạm vi ba nhánh được kiểm; giới hạn chất
lượng model, metadata corpus và mapping chưa live lại được giữ rõ khi bàn giao.

Receipts, saved-trace audit, provider traces và outputs lưu local tại
`artifacts/evidence/E2E-TECH-FIX-01/`; không commit dữ liệu/secrets.

Next action — chờ giao Pilot 45 trên runtime đã freeze, chấm theo Gold/rubric
ViFinBench; không tiếp tục FIX nhằm tăng accuracy.
