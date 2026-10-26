# Quyết định và điểm cần làm rõ

## Các lựa chọn cho M0-01

| Nội dung | Quyết định | Cơ sở |
| --- | --- | --- |
| Phạm vi | Chỉ skeleton, môi trường và tài liệu | Yêu cầu M0-01 |
| Ngôn ngữ | Python 3.11+ | Yêu cầu M0-01 |
| Kiến trúc | Modular monolith, Offline → Online → Output | Yêu cầu M0-01 và báo cáo Chương 4–6 |
| LLM | Gateway dùng chung; hỗ trợ đổi model, structured outputs và chi phí | Yêu cầu M0-01; chưa triển khai |
| Đầu ra | QA và báo cáo chỉ dùng nhận định trong Verified Claim Ledger | Báo cáo Chương 4.5, 5.7 |
| Đóng gói | setuptools; distribution `vietnamese-financial-multi-agent`, namespace `vietnamese_financial_multi_agent` ánh xạ vào `src/` | Lựa chọn thiết lập M0-01, giữ cây thư mục yêu cầu và tránh import tên chung |
| Kiểm tra | Ruff cho lint/format; pytest cho smoke tests cài đặt/import | Lựa chọn thiết lập tối thiểu M0-01 |
| Dependencies | Không có runtime dependency; dev chỉ có Ruff và pytest | Không cài thư viện AI khi chưa cần |
| CI | Kiểm tra package thường, lint/format và unit tests trên Python 3.11/3.12 | Xác minh mức Python tối thiểu và bản có tại máy |
| Tài liệu | Tiếng Việt; identifiers/tên code bằng tiếng Anh | Quy tắc nhất quán trong M0-01 |
| Git | Nhánh `main`, repository private; dữ liệu hiện có và tài liệu gốc nằm ngoài tập commit | Yêu cầu M0-01 |

Các khoảng phiên bản dev nằm trong `pyproject.toml`; chưa có lockfile. Phiên bản
đã kiểm tra sẽ được ghi trong trạng thái task. Chính sách khóa dependency cho
thực nghiệm tái lập là `TBD` trước khi triển khai benchmark.

Đã kiểm tra GitHub của `VuongQuocAn`: chưa có repository đúng tên
`vietnamese-financial-multi-agent` tại thời điểm khởi tạo. Repository sẵn có
`Mutil_Agent_Financial_Report` là public, đã có triển khai theo kiến trúc C1–C5;
không phù hợp với yêu cầu skeleton private và pipeline mới của M0-01. Giữ nguyên
repository đó, tạo repository private theo đúng tên được yêu cầu.

## Các vấn đề TBD

- Schema dữ liệu, provenance, facts, EF-EG, claim, ledger và versioning contracts.
- Backend lưu trữ, engine đồ thị, framework API, công cụ OCR và thư viện điều phối.
- SDK Gateway, Gemini model, nhà cung cấp bổ sung, hạn mức và cấu hình chi phí.
- Quy tắc kế toán, bảng ánh xạ, dung sai số học và điều kiện kiểm chứng chi tiết.
- Dataset chính thức, quyền sử dụng, manifest, chia tập và quy trình chú giải.
- Ngưỡng đánh giá, ngân sách thực nghiệm và baseline chốt triển khai.
- Phạm vi tuân thủ quy định: tên đề tài trong M0-01 có nội dung này, trong khi
  Chương 1 của báo cáo giữa kỳ nói kiểm tra tuân thủ pháp lý không thuộc phạm vi
  nghiên cứu chính. Giữ tên đề tài theo yêu cầu mới nhất; chưa tự chọn văn bản
  pháp luật, luật kiểm tra hay module tuân thủ cho đến khi phạm vi được làm rõ.

Không dùng danh sách công nghệ được đề xuất trong báo cáo như quyết định đã
được duyệt. Không tự mở rộng phạm vi trong task khởi tạo.

## 2026-10-26 — Tracking và handoff (M0-04)

- Master Task Registry là nguồn trạng thái chính; chỉ dùng sáu states đã quy
  định. Dashboard và metadata trong spec/handoff phải đồng bộ với registry.
- Task IDs bất biến. Giữ scope/ID M1-01..04 từ M0-03; M1-02/03/04 làm task cha
  nghiệm thu, chia phần nhỏ bằng hậu tố thay vì đánh số lại. Task mới khác dùng
  số tiếp theo, không tái sử dụng IDs.
- Có 72 task đã đăng ký, gồm ba task cha. Số đếm không phải ước lượng khối lượng
  hoặc phần trăm nghiên cứu; implementation/benchmark chưa có số đo thì N/A.
- Chỉ tạo spec đầy đủ cho M0-04 và task M1-01 có inputs/criteria rõ. Backlog xa
  dùng mô tả ngắn trong roadmap; trước READY cần spec riêng và xem xét chia M/L.
- Validator Python standard library kiểm tra IDs, dependency cycles, states,
  DONE evidence, dashboard, spec metadata và links; CI chạy cùng lint/unit tests.
  Script không đọc dataset, gọi API hoặc chọn công nghệ nghiệp vụ.
- Resume đọc bốn tài liệu nhỏ (AGENTS/current-status/handoff/active spec), xác
  minh Git rồi chỉ mở tài liệu liên quan. Ghi checkpoint sau phần độc lập đã
  kiểm thử; không suy đoán luôn kịp bàn giao khi quota hết.
- DONE/publication được ghi sau nghiệm thu với SHA đã biết; bản ghi status có
  thể đi ở commit tiếp theo để tránh ghi SHA tự tham chiếu hoặc claim push trước
  khi thực tế push. Run CI luôn gắn với commit cụ thể, không suy ra cho commit mới.

Đây là quyết định quản lý công việc, không đổi Modular Monolith, pipeline,
module boundaries, contracts hoặc đóng góp nghiên cứu. Framework/model/storage,
schema kế toán và phạm vi pháp lý vẫn TBD như phần trên.

## 2026-10-26 — Document Understanding v1 (M1-02b)

- Output ứng dụng sở hữu dùng strict/extra forbid; unknown fields gây structural
  error giữ payload, khác chính sách bảo toàn raw extra allow.
- Page-level result; anchors mang identity và ngữ cảnh element/table/cell/line.
  source_ref caller cung cấp nếu biết run/artifact; không giả định global uniqueness.
- Bbox observed/proposed riêng, pixel ảnh gốc; image-only anchor còn chưa xác minh.
- Optional spans không default 1; export exclude_unset phân biệt missing/null/value.
- Classification vocabulary mở, null = chưa biết; không thêm taxonomy/logic kế toán.
- Quality validation riêng, raw comparison tường minh trong bộ nhớ; không sửa dữ liệu.
- Global run binding, taxonomy, migration và header relationships còn TBD.
Chi tiết fields, status semantics và giới hạn ở [data contracts](../docs/data-contracts.md).

## 2026-10-26 — Path Mapping v1 (M1-02c)

- Root config là explicit approved source root + path style + category + logical
  destination root key. Runtime M1-03a/b bind key, không hardcode local paths.
- So root theo components, exact case, giữ source string nguyên văn. Suffix dùng
  `/` để biểu diễn components độc lập host. Không marker search/basename fallback.
- Nhiều rules cùng category khớp đều ambiguous, kể cả nested roots hoặc cùng đích;
  không ưu tiên theo thứ tự. Config lỗi/duplicate IDs làm request unsafe.
- Policy portable fail closed cho traversal, separator lẫn, encoding, stream/device
  syntax. Lexical checks không chứng minh containment qua symlink/junction.
- Helper chỉ sinh not_checked/unsafe/unmapped/ambiguous. Runtime resolved/missing
  cần evidence tường minh và quality/status validation; không xác minh file content.
- Strict structural parsing tách quality validation; giữ payload lỗi và missing/null.
  PathReference tái sử dụng SourceAnchor, không sửa Raw OCR/Understanding models.
- Runtime policy, root/run identity, migration và recovery vẫn TBD. Không đăng ký
  M1-03d hoặc triển khai runtime ở task contracts.
