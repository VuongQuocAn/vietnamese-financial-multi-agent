# Financial AI Workspace — UI handoff

W-01 REVIEW; tham chiếu [kiến trúc](architecture.md), [API](api-contracts.md).
Đã đọc trực tiếp cả DESIGN.md và HTML/CSS/scripts, xem hai PNG gốc:

| Bộ | HTML | Design | Ảnh | Kích thước bytes HTML / MD / PNG |
| --- | --- | --- | --- | --- |
| Dashboard | [code.html](../UI/stitch_1/code.html) | [DESIGN.md](../UI/stitch_1/DESIGN.md) | [dashboard.png](../UI/stitch_1/dashboard.png) | 23600 / 9865 / 71683 |
| Evidence Explorer | [code.html](../UI/stitch_2/code.html) | [DESIGN.md](../UI/stitch_2/DESIGN.md) | [eviden.png](../UI/stitch_2/eviden.png) | 33489 / 9865 / 117659 |

Assets do người dùng cung cấp, tổng 266161 bytes, giữ nguyên bytes; HTML chỉ
reference, không chạy như app. Hai DESIGN.md giống hệt nhau (SHA256
`bbb94f367a3b36788452f416ed4a9f5c9a86a404177bb7b76b95bb364ec305e5`).
Hai DESIGN.md gốc có trailing whitespace tại dòng 121/138; staged diff check
báo bốn dòng này. Giữ nguyên theo yêu cầu bảo toàn Stitch; phần W-01 tự viết
được check riêng, không tắt whitespace checks hoặc sửa assets để che ngoại lệ.
HTML dùng Tailwind CDN, Google fonts/Material Symbols và ảnh googleusercontent
ở Explorer. Không có API thật: dashboard chỉ đổi label tên file; Explorer scripts
chỉ toggle panel/thumbnails và active row, chưa navigate PDF hoặc resize splitter.

## Đánh giá tính nhất quán

Hai ảnh nhất quán sidebar sáng, primary xanh đậm, nền xanh nhạt, upload card,
recent documents và bảng dense; font hiển thị trong PNG lại thiên serif, chữ nhỏ,
số cột so sánh bị khuất khi pane hẹp. DESIGN.md khai Inter/JetBrains Mono nhưng
prose mô tả sidebar Slate tối, palette slate/teal và evidence trái/PDF phải;
frontmatter palette khác prose, HTML/ảnh lại PDF trái/evidence phải (45/55).
HTML cả hai dùng primary `#00288e`, secondary `#0051d5`, fontFamily tất cả
trỏ Inter (kể cả data-mono); dashboard chỉ import Be Vietnam Pro, Explorer không
import Inter. CSS còn ẩn toàn bộ scrollbar; spacing HTML space-lg=20px/space-xl=32px
khác MD 16/24px. W-02 cần load font thật và giữ scrollbar để thấy bảng cuộn được.
Không thể copy nguyên design file để giải quyết các mâu thuẫn đó.

Đề xuất ưu tiên bố cục ảnh đã duyệt, tokens thống nhất dưới đây và typography
sans theo yêu cầu Tech Lead. Không coi prose về bbox, verified badge hay các
milestone giả trong DESIGN.md là chức năng được phép triển khai.

## Tokens tái sử dụng cho W-02

| Token | Giá trị đề xuất | Dùng cho |
| --- | --- | --- |
| background / panel | `#f8f9ff` / `#ffffff` | Canvas sáng từ frontmatter |
| surface-muted / selected | `#eff4ff` / `#e5eeff` | Card phụ và row được chọn |
| foreground / muted | `#0b1c30` / `#45464d` | Nội dung, nhãn phụ |
| border | `#c6c6cd` | Border 1px nhẹ |
| primary / on-primary | `#00288e` / `#ffffff` | Primary HTML cả hai bộ; thay primary đen trong YAML |
| secondary | `#006a61` | Link/trạng thái phụ, không ngụ ý verification |
| success / warning / danger | `#047857` / `#b45309` / `#b91c1c` | Hoàn tất / cần thông tin / lỗi; luôn có text |
| focus | `#0d9488`, outline 2px | Keyboard focus; kiểm contrast khi W-02 |
| spacing | 4, 8, 12, 16, 24px | Nhịp 4px từ hai DESIGN.md |
| radius | 4px controls, 8px cards | Ít shadow, ưu tiên border |
| sans | Inter có Vietnamese subset, fallback sans-serif | Toàn UI; Be Vietnam Pro là fallback quyết định W-02 |
| numbers | JetBrains Mono hoặc sans tabular-nums | Cột số 13–14px, right-aligned, no truncation |
| type | headings 28/36, 22/28, 18/24; body 14/20; small 13/18 | Không dùng 11px cho số liệu chính |

Desktop 1440×900; sidebar 240px mở/64px thu; header tối thiểu 48px.
Explorer split mặc định PDF trái 45%, evidence phải 55%, kéo được bằng chuột
và keyboard, min-width mỗi pane; laptop 1280px ưu tiên thu sidebar. Khi hẹp,
cho toggle một pane và giữ selected evidence/page/zoom; không ép số vào ellipsis.
Bảng min-width theo số kỳ và cuộn ngang độc lập; sticky mã/label nếu khả thi.

## Routes và reusable components

Chỉ bốn mục sidebar: Dashboard, Documents, Evidence Explorer, AI Financial Workspace.

| Route/màn hình | Components | Nguồn dữ liệu / tương tác |
| --- | --- | --- |
| `/` Dashboard | AppShell, UploadDropzone, RecentDocuments, StatusBadge, ComingSoonCard | GET documents; upload PDF; empty state khi rỗng; không OCR logs/accuracy |
| `/documents` | DocumentList, UploadDropzone | Danh sách API có pagination; tên/kỳ/status thật; mở detail |
| `/documents/[id]` | MetadataReviewForm, ProcessingStatus, ErrorNotice | Gợi ý + user corrections, confirmation; process/preflight retry; n/N không ETA |
| `/evidence` | DocumentPicker | Chọn tài liệu hiện có, empty state; không tự chọn dữ liệu demo |
| `/evidence/[id]` | ResizableEvidenceLayout, PdfViewer, StatementTabs, FinancialTable, SourceDetails, AnnotationDetails | GET inventory/evidence/file, chọn cell/row → trang nguồn PDF |
| `/ai-workspace` | ComingSoonPanel | Giải thích QA/analysis/report tương lai, không input chat hoặc response giả |

PdfViewer client-only: PDF gốc qua API, zoom, previous/next, số trang 1-based,
fit-width, fullscreen, thumbnail tùy chọn/lazy render. Không tái dựng PDF bằng HTML
financial text như Stitch, không dùng ảnh remote giả. Nếu không mở được viewer,
có link mở PDF gốc local và message lỗi. Loading/cancel/unmount phải giải phóng
PDF resources trong W-05. Không cần bbox cho row → page navigation.

FinancialTable dùng source item code dạng string (giữ `01`, `411a`), raw label
tiếng Việt, header kỳ động, currency/scale theo cell/context. Không chỉ hiện các
canonical IDs; unmapped vẫn có row. Không gộp hai observations khác context/page
chỉ vì trùng mã. Group row bằng source table/row binding trong attempt, mỗi kỳ
là cell riêng với evidence_id; xung đột giữ mọi candidate, không chọn số đầu tiên.
Raw value là chế độ mặc định; normalized string xem chi tiết, không tự scale hay
đổi glyph dash. Thiếu hiển thị “Thiếu”; dash giữ raw glyph kèm nghĩa “không có số”;
zero hiển thị `0`. Unresolved/conflicted có nhãn và lý do, không bị ẩn khỏi bảng.

Chọn dòng chuyển trang nguồn đầu tiên thuộc row; chọn cell dùng source của cell,
nhiều sources cho phép chọn từng trang. SourceDetails giữ raw/normalized value,
period/type, unit/scale/scope, page, raw label/code, caveats/issues; JSON pointers
ẩn dưới details cho người cần kiểm tra. Không trình bày pointer thành bbox hoặc
cell đã xác minh. Annotations chỉ xuất hiện khi backend trả checks thật; unavailable
ghi “Chưa đánh giá”, không “Cân đối hoàn hảo”. Không tô green check toàn row.

B01/B02/B03 lấy evidence DTO; B09 chỉ inventory các trang notes và link viewer,
ghi rõ chưa có notes QA. Evidence Graph là tab Coming Soon trong Explorer.
Không thêm navigation riêng cho verification/report hoặc từng agent.

## Điều chỉnh bắt buộc so với Stitch

- Bỏ Q2/2024, BBS/VNM/HPG/FPT, niên độ, tên auditor, TT200 và tài khoản cá nhân
  hardcode khỏi runtime UI; chỉ hiển thị metadata có nguồn/xác nhận.
- Bỏ “Đã ánh xạ 100%”, “Đã đối soát”, verified/check_circle và accuracy/confidence
  tự tạo. Job completed nghĩa chạy xong, không chứng minh số đúng.
- Bỏ vùng highlight PDF giả và notes links V.01–V.05 đã xác minh; mã thuyết minh
  nếu giữ từ nguồn chỉ là text, không có verified link.
- Giữ dashboard gọn, upload nổi bật, recent documents, split viewer, tabs B01–B09,
  source disclosure và AI Coming Soon. Bỏ controls export/search/account không có
  backend thay vì tạo nút hoạt động giả; Documents có thể filter danh sách đã tải.
- Viết React components dùng state/API và accessibility: label input, focus visible,
  tabs keyboard, row/cell source link keyboard, status live region; không DOM query
  listeners và không CDN Tailwind trong production source.

## Mở rộng sau V1 và nghiệm thu UI

M3 bổ sung Evidence Graph/retrieval trong Explorer. M4–M7 dùng AI Workspace chung
cho tools/QA, planner/specialists, citation/verification trace và grounded reports;
M6 verification cho analytical claims không bắt mọi extracted fact qua full ledger.
M8 evaluation/integration theo task. Chưa implement các extension points.

W-05/W-06/W-07 kiểm nghiệm bằng dữ liệu được giao: chọn evidence chuyển đúng PDF
page, multi-period horizontal scroll, numeric zero/dash/missing/conflict riêng,
unmapped vẫn xem được, partial/error rõ, không có false verification. Kiểm màn
1440px/laptop, zoom/font tiếng Việt và keyboard; W-01 chưa chạy web/E2E tests.
