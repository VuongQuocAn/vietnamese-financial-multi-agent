# FIX-02-MH — Suy luận nhiều bước có kiểm chứng

Ngày 10/11/2026. Phạm vi tiếp nối FIX-02 trên baseline `a320e8c`,
checkpoint `b4de4f0`; không phải bản vá riêng Q21.

## Restriction & Reasoning Gap Matrix

| Gate tại baseline | Vai trò đúng | Khoảng trống | Xử lý |
| --- | --- | --- | --- |
| Specialist cấm chữ số/tỷ lệ và metric premises trong analyses | Không bịa số | Chặn cả số/kỳ đã có nguồn, so sánh hợp lệ | Public reasoning proof; numeric binding; M6 replay |
| M4 chỉ chạy ba formula đã duyệt | Bảo toàn metric chuẩn | Không tính được chênh lệch/tỷ số ad hoc | Typed Decimal DAG trong calculator hiện hữu; không cấp nhãn standard metric |
| Analysis chỉ gồm facts cùng kỳ | Ngăn trộn context | Chặn approved metric và so sánh hai kỳ trong một filing | Kiểm từng premise độc lập; across_periods tường minh; giữ từng kỳ trong trace |
| Evidence phải hỗ trợ nguyên văn kết luận | Bảo vệ quotation | Derived relation không phải quotation PDF | Derived statement do backend render; inference được Critics xét từ proof |
| Logic grammar gắn từ khóa với thiếu comparison/context | Không suy nguyên nhân/đánh giá quá mức | Không nhận ra comparison đã được tính | Structured proof đi qua semantic assessment sau arithmetic gates |
| M7 earnings quality cần từ khóa/quan hệ theo regex | Không dùng CFO sign thay analysis | Paraphrase hợp lệ có thể không khớp | Với proof mới, dùng Critic purpose + đủ premises + calculation; không dùng keyword gate |
| Goal động chỉ neo vào indicator | Không đáp ứng nhầm câu hỏi | Difference/ratio/comparison cùng operands gây ambiguity | Bind operators và periods trong answer goal; nếu chưa rõ giữ clarification |
| Renderer nối lại caveats thô sau Composer | Bảo toàn trace | PLANNER_TASK/reason codes quay lại final text | Sanitize ở cả paragraph/nguồn; metadata và fingerprint giữ nguyên |
| Aggregate identity bỏ reasoning proof | Dedup numeric facts | Hai proof khác nhau có thể chung ID | Proof mới tham gia identity; identity lịch sử không đổi |
| Feedback chỉ nói thiếu coverage | Bounded revisions | Revision chỉ lặp facts | Inventory + prior conclusions + computations + bước phân tích còn thiếu |

## Luồng và contracts

Planner giữ execution DAG hiện có; `reasoning_steps` biểu diễn retrieve, compare,
calculate, interpret, alternative, limitations và conclusion. Đây là kế hoạch công
khai, không phải chain-of-thought nội bộ. Assignment vẫn bị Router/capability gates
kiểm tra. Không thêm agent/framework hoặc thay Offline → Online → Output.

Specialist dùng `AnalysisProposal.operations` với inputs là evidence ID hoặc output
bước trước. Backend chạy cùng Decimal interpreter của M4, sinh `ReasoningProof`.
Phép tính là candidate riêng với content deterministic; diễn giải là candidate khác,
cùng liên kết nguồn. Một nhánh lỗi không xoá facts hoặc nhánh tính độc lập hợp lệ.

M4 `FinancialCalculator.calculate_dynamic` lấy lại exact canonical observation,
quality/source review/citations và reporting context, rồi chạy typed operations.
Không `eval`, arbitrary constants hoặc Python expression. Add/subtract/ratio,
relative difference, percentage change, comparisons, sum/mean và multiplication
với ratio vô hướng được hỗ trợ. Giá trị chuẩn hoá scale, Decimal34/HALF_EVEN,
display 2 decimals; operands và intermediate strings được giữ trong proof.

M6 phân biệt direct fact theo kind cũ và derived/reasoned/conditional qua proof.
Mỗi source premise đi qua các checks M6 sẵn có. Dynamic trace được tính lại từ
catalog độc lập; sửa value/operator/period/source/result đều không tạo ACCEPT.
Derived content phải bằng renderer của calculation đã replay. Diễn giải cần
Evidence Critic và Logic Critic; số đúng không tự chứng minh causality hoặc đánh giá
toàn diện. Một giả thuyết có assumptions chưa chứng minh không vào Verified Ledger.

M7 chỉ đọc admitted claims. Kết luận có giới hạn có thể đáp ứng goal nếu Critic xác
nhận đúng quan hệ, đủ nguồn và phép tính khi có khẳng định định lượng; không cần
một kết luận tốt/xấu tuyệt đối. Phần tính toán độc lập vẫn được hiển thị khi diễn
giải phụ thuộc nó chưa đạt, nhưng original analytical goal vẫn unanswered.
Phép tính ad hoc dùng topic `dynamic_calculation`, với operators/periods tương ứng.
Arithmetic proof được hiển thị cùng insight; citation dùng tên filing và trang,
không đưa operation IDs/diagnostic annotations vào prose. Firewall kiểm tra toàn
Composer → CitationRenderer → final release. Các kỳ nguồn khác kỳ owner chỉ được
phép khi calculation proof đã khai báo across_periods và giữ binding từng nguồn.

## Checks bắt buộc và giới hạn

Giữ missing/ambiguous/conflicted inputs, nguồn/citation giả, company/document/
snapshot/scope sai, non-finite values, unit mismatch, missing dependency/cycles,
zero denominator, wrong arithmetic và promotion trái native M6. Cross-document
accounting comparability chưa được cấp phép; không dùng graph edge thiếu để từ
chối exact facts trong cùng filing. Không sửa OCR hoặc nâng quality/provenance.

Các fields mới rỗng được bỏ khỏi wire serialization để replay proof/identity cũ.
Không có migration/ghi lại historical Ledger. Conditional scenario chưa chứng
minh vẫn ngoài Ledger; bản này chưa thêm kênh M7 phát hành kịch bản giả định riêng.
Đây là giới hạn cần báo cáo, không đổi conditional thành verified để đạt coverage.

Kết quả offline/live/CI và next action được cập nhật tại
[báo cáo FIX-02](fix-02-adaptive-llm-agents.md).
