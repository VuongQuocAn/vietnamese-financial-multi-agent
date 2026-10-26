# Quyết định và điểm cần làm rõ

## 2026-10-26 — Missing Crop Audit & Bounded Recovery (M1-03d)

- M1-03c Tech Lead APPROVED, task cha M1-03 DONE; M1-03d độc lập dependency M1-03.
  Acceptance `5937b815135478ace1d0958ff7c2f31f2ae4cc51`, CI 40314189759 success.
- Audit manifest chọn đúng 193 trang; không full inventory. Source Colab roots/run
  còn TBD theo contract: không tự duyệt mapping. Tất cả 1.557 references unmapped,
  zero eligible/recovered; không biến unmapped thành missing hoặc ép bằng 572.
- Chỉ table.crop với approved image identity binding, matching dimensions/bbox;
  không suy đoán detection_view hoặc transformations. Color views unsupported.
- Pillow >=11,<13 cho PNG lossless; không dependency AI. Runtime audit records
  và manifests phụ trợ, không thêm public/versioned contract hoặc core whitelist.
- Default dry-run, output chỉ data/recovered_crops, exclusive PNG + hash sidecar,
  cap 12; trusted filesystem một writer, TOCTOU/aliases còn giới hạn. Chi tiết và
  kết quả thực tế ở [crop recovery](../docs/crop-recovery.md).

## 2026-10-26 — Read-Only OCR Data Loader (M1-03c)

- M1-03b Tech Lead APPROVED/DONE; acceptance `10eb4e9`, CI 40310998984 success.
- LoadedOCRPage frozen dataclass và OCRLoadError/code là runtime wrappers nội bộ,
  không đổi serialized contracts. Structural issues giữ paths/cause, quality riêng.
- Reuse resolver mới trước/sau read; bind root key, bounded O_RDONLY, fstat/lstat,
  O_NOFOLLOW/O_NONBLOCK khi có. Còn TOCTOU; không secure descriptor framework.
- Fingerprint dev/inode/size/mtime, POSIX thêm ctime; Windows ctime có semantics
  khác giữa lstat/fstat nên không dùng để so chéo.
- 32 MiB default hữu hạn chưa đo phù hợp corpus; đọc tối đa limit + 1 sentinel.
- UTF-8/BOM, reject duplicate JSON keys và NaN/Infinity constants; không sửa nguồn.
- Anchor kiểm tra exact symbol/year/page/image; không suy ra run identity.
- Đọc đúng 3 mẫu theo manifest, hash/metadata khớp; không scan hoặc benchmark.
  Chi tiết API/security/errors/verification ở [ocr-loader](../docs/ocr-loader.md).

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

## 2026-10-26 — Central Data Configuration (M1-03a)

- M1-02c Tech Lead APPROVED; task cha M1-02 DONE sau đối chiếu ba contracts,
  không chỉ dựa vào dependencies. Phase 1 355bec4/CI 40304977048 đã xác minh.
- Dùng bốn environment keys hiện hữu, không suy ra từ các biến thư mục cha.
  FINANCIAL_REPORT_DIR/FINANCIAL_OCR_DIR bắt buộc; NORMALIZED_DATA_DIR và
  CANONICAL_DATA_DIR optional vì chưa triển khai output stages. Key cung cấp rỗng
  luôn lỗi; lookup unconfigured không fallback. Chưa cần samples key.
- Source checkout default base từ module/markers; wheel cần base tuyệt đối
  tường minh. Không lấy CWD, đọc .env hoặc expand environment/home trong path.
- Chỉ native runtime paths, foreign styles bị từ chối; metadata vẫn ở Path Mapping.
  Root lookup trả Path, không nối suffix hoặc filesystem I/O. Core không import contracts.
- Frozen strict Pydantic, whitelist cố định; lexical overlap guard tách outputs
  khỏi inputs/outputs khác. Không stat dataset, không mkdir hoặc giải quyết symlink.
  Runtime containment/existence/access/race, source identity vẫn TBD cho M1-03b/c.

## 2026-10-26 — Read-Only Path Resolver (M1-03b)

- M1-03a Tech Lead APPROVED/DONE; acceptance 3d700a5, CI 40306938717 success.
- document_processing.resolve_path dùng lexical helper + get_root và result v1;
  không đổi contracts/core, local path không thêm field vào output.
- Chặn mọi symlink/reparse point qua lstat, kể cả root ancestors và link trong root;
  resolve component containment vẫn thực hiện. Không secure-open API.
- Roots overlap không làm đổi binding; shared_root_identity là issue thông tin
  khi samefile trùng, không chứng minh source/run identity.
- Missing chỉ khi selected root tồn tại, containment verified; filesystem errors
  unsafe/permission_denied hoặc filesystem_error, không che thành missing.
- Regular file + PNG/JSON structural extension + os.access metadata; không mở nội
  dung. Loader sau xử lý lỗi đọc/content và kiểm tra lại tại thời điểm dùng.
- TOCTOU, ACL/aliases/mounts/short names còn giới hạn; chi tiết ở
  [runtime policy](../docs/path-resolver.md). Không recovery, API/OCR/dataset scan.
