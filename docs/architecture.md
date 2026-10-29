# Kiến trúc hệ thống

Runtime Research MVP hiện hành được audit tại
[M1/M2 end-to-end](m1-m2-end-to-end-audit.md): financial structured extraction
độc lập nhánh OCR/unified, task-aware evidence và structured query/recovery probe.
Các lớp ledger/agents/output bên dưới vẫn là định hướng, chưa được M2-08 triển khai.

## Cơ sở và phạm vi

Nguồn: yêu cầu M0-01 và báo cáo giữa kỳ cục bộ `docs/report_midterm.docx`,
Chương 4–6. Tài liệu gốc không được đưa vào Git. Kiến trúc dưới đây là định hướng
thiết kế; code trong M0-01 chỉ là skeleton Python theo modular monolith.

## Offline Pipeline

Financial PDF → Document Processing & Accounting Normalization → Canonical
Evidence Layer → Executable Financial Evidence Graph (EF-EG).

Xử lý tài liệu tạo văn bản, bảng và vị trí nguồn. Chuẩn hóa kế toán giữ nguyên
khả năng truy nguyên khi chuẩn hóa chỉ tiêu, đơn vị, kỳ và phạm vi báo cáo.
Canonical Evidence Layer tổ chức facts, text/table evidence và provenance;
EF-EG liên kết bằng chứng với phép tính và nhận định.

## Định hướng M3 — Typed Executable Financial Evidence Graph

M3 hướng tới **Typed Executable Financial Evidence Graph with Semantic Compatibility
and Evidence-Quality Propagation**. Đây là định hướng nghiên cứu, chưa phải tuyên bố
thuật toán mới, novelty/SOTA hoặc kết quả thực nghiệm đã xác minh. Giữ Modular Monolith
và Offline → Online → Output; “Executable” tại M3 nghĩa là biểu diễn đủ để công cụ M4
thực thi và truy vết, không triển khai executor tại M3.

Giữ pipeline khái niệm gốc: `SourceFact → DerivedMetric → Claim → VerificationRecord`.
M3 chỉ chuẩn bị phần evidence và điểm mở rộng typed relations về sau. Candidate claims
thuộc luồng agents M5 và contracts/verification M6; `Claim`, `VerificationRecord` và
Verified Claim Ledger không được triển khai tại M3.

| Thành phần M3 | Vai trò và giới hạn dự kiến |
| --- | --- |
| `SourceFact` / `CanonicalFinancialFact` | Fact có nguồn và biểu diễn canonical khi mapping được duyệt; quan hệ/định danh cụ thể chốt ở M3-01, không mặc định là hai bản sao hoặc hai class. Canonical không có nghĩa là verified |
| `EvidenceAnchor` | Tham chiếu identity tài liệu/nguồn, trang và vùng/ô khi thực sự có bằng chứng; tái sử dụng provenance M1/M2, không nâng page-level thành cell-level |
| `TextEvidence`, `TableEvidence` | Văn bản/bảng giữ cấu trúc và liên kết anchors; không biến nguồn chưa xác minh thành fact đã xác minh |
| Typed graph relations | Kiểu nút/cạnh, miền tham chiếu và ràng buộc liên kết cần duyệt; phân biệt nguồn, operands và kết quả, mở rộng về Claim/VerificationRecord ở M5/M6 |
| `DerivedMetric` | Biểu diễn công thức, vai trò operands, inputs và kết quả nếu có; thực thi deterministic thuộc M4 |
| Calculation lineage | Truy metric về công thức, operands, facts và anchors; giữ inputs thiếu, nguồn unresolved và caveats |
| Evidence retrieval | Giao tiếp truy xuất facts/text/table/graph/lineage cùng IDs, nguồn và quality context, phục vụ công cụ M4 và đánh giá thực nghiệm |

### Semantic Compatibility Validation

M3-01 phải thiết kế semantic type rules cho financial item, reporting period,
reporting scope, unit/scale, document/source identity và formula operand roles.
Tương thích tùy phép toán và vai trò operand, không phải yêu cầu mọi field bằng nhau:
ví dụ so sánh hai kỳ cần giữ riêng kỳ và vai trò của từng đầu vào. Quy tắc chi tiết,
mapping và công thức chưa được phê duyệt là TBD; không tự suy quy tắc kế toán,
gộp identity hoặc mặc định metadata thiếu là tương thích. M3-04 biểu diễn các ràng buộc
này trong graph; công cụ M4 sử dụng contract được duyệt khi thực thi.

### Evidence-Quality Propagation

Giữ bốn quyết định theo tác vụ của M2: `usable`, `usable_with_caveat`, `insufficient`,
`conflicted`, kèm reasons và nguồn đánh giá. Unresolved provenance và missing operands
là tình trạng/lý do cần biểu diễn, không tự thêm vào enum quyết định hiện có.
Contract M3-06 phải bảo toàn và truyền các tín hiệu này qua facts, relations, metrics,
lineage và retrieval; không bỏ phần evidence còn dùng được hoặc biến missing thành zero.
Không tự đặt confidence score, thresholds, thứ tự gộp quality hoặc propagation algorithm;
thiết kế cụ thể và thực nghiệm còn TBD.

Phân biệt ba lớp: **source grounding** kiểm tra liên kết tới nguồn; **numerical
calculation validity** kiểm tra phép tính và operands theo quy tắc đã duyệt;
**claim verification** đánh giá nhận định ở M6. Có nguồn hoặc phép tính hợp lệ không
tự chứng nhận claim đúng. Không đổi `financial_fact_verified=false` của M2.

Ranh giới milestone: M3 representation/graph/provenance/lineage/retrieval;
M4 deterministic financial execution tools (kèm QA baseline đã có trong roadmap);
M5 adaptive planner/specialist agents; M6 claim verification/verified claim ledger;
M7 grounded QA/report generation; M8 controlled evaluation và ablation.
M3 chuẩn bị khả năng truy xuất evidence cho đánh giá, không tự chạy benchmark.
Storage engine vẫn TBD; preflight này không xây graph/vector database, agents hay frontend.

Giữ caveats M1/M2 và W-07: provenance unresolved hoặc chỉ cấp trang vẫn giữ nguyên;
usability/smoke không chứng minh financial accuracy. M2-09 chỉ có reference trên một
PDF, chưa tổng quát; W-07 CONDITIONAL GO cho local research demo, chưa đánh giá accuracy
toàn PDF/multi-document, chưa verified financial facts; IDM trên browser người dùng
chưa xác nhận, live phụ thuộc Gemini Free Tier. Không có bằng chứng mới từ preflight.

## Online Processing

Shared Executable Tool Space → Evidence/Risk-Aware Planner & Supervisor →
Specialist Agents → Claim-Level Verification → Verified Claim Ledger.

Planner và Supervisor lựa chọn công cụ, tác nhân theo nhu cầu bằng chứng và
tín hiệu rủi ro. Công cụ và tác nhân sử dụng chung cơ sở bằng chứng. Nhận định
đề xuất phải được kiểm chứng về số liệu, phép tính, nguồn và lập luận.

Theo Chương 4.5 và 5.6, kiểm chứng có thể dẫn đến `ACCEPT`, `REVISE`,
`INVESTIGATE` hoặc `ABSTAIN`. Việc sửa hoặc tìm thêm bằng chứng quay về luồng
phân tích có giới hạn; chỉ nhận định được chấp nhận mới vào ledger. Ngưỡng rủi ro,
quy tắc kích hoạt, giới hạn vận hành và schema trạng thái dùng trong code là `TBD`.

## Output

- Interactive Financial Question Answering: câu trả lời tiếng Việt có dẫn nguồn.
- Grounded Financial Report Generation: báo cáo phân tích có dẫn nguồn.

Hai đầu ra dùng chung Verified Claim Ledger. Theo cơ chế Information Firewall
trong Chương 5.7, bộ tạo đầu ra chỉ tổng hợp nhận định đã xác minh, không tự bổ
sung số liệu, tính toán hoặc truy xuất bằng chứng mới. Thiếu bằng chứng phải
được thể hiện rõ, có thể không đưa ra kết luận.

## Hạ tầng và các lựa chọn chưa chốt

Python 3.11+, modular monolith; ranh giới cụ thể ở
[module-boundaries.md](module-boundaries.md). LLM Gateway dùng chung dự kiến
thuộc hạ tầng `core`, hỗ trợ Gemini và các LLM khác, đổi model, structured
outputs và quản lý chi phí. Không triển khai Gateway trong M0-01.

Framework API, thư viện OCR, engine lưu trữ/đồ thị, SDK LLM, model, schema chi
tiết và cơ chế triển khai là `TBD`. Các công nghệ được nêu như phương án trong
báo cáo giữa kỳ không được coi là dependency đã được chốt trong repository.
