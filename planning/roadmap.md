# Roadmap M0–M8

Roadmap bám [kiến trúc](../docs/architecture.md),
[ranh giới module](../docs/module-boundaries.md),
[data contracts](../docs/data-contracts.md) và định hướng Chương 4–8 của báo cáo
midterm đã đối chiếu trong M0. Danh sách sau là phân rã công việc, không phải
quyết định chọn framework/model/storage hoặc thay đổi đóng góp nghiên cứu.
Trạng thái task chỉ lấy từ [Master Task Registry](tasks.md).

## Thứ tự và điều kiện triển khai

`M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8` là thứ tự các gate hoàn thành.
Dependencies task trong registry là ràng buộc cụ thể; không tự mở milestone mới
hoặc chạy task chỉ vì đã xuất hiện trong kế hoạch. Quyền truy cập dữ liệu, schema,
model, thresholds, budget, engine và lịch/người phụ trách còn thiếu đều là `TBD`.

M1-01 đến M1-04 giữ nguyên phạm vi đã đăng ký ở M0-03. Ba task lớn M1-02/03/04
được giữ làm task cha nghiệm thu; phần triển khai chia thành task con nhỏ, tránh
đổi ID hoặc gộp thiết kế contracts với toàn bộ pipeline. Các mô tả xa dưới đây
là spec ngắn dự kiến, phải được cụ thể hóa bằng [template](task-template.md)
trước READY. Nếu vẫn là M/L khi chuẩn bị, tiếp tục chia bằng ID mới/hậu tố.

## W — Web Demo V1 giữa M2 và M3

Housekeeping29/10: PR#1→#2→#3 MERGED main không conflict, CI sau từng merge PASS.
dev.ps1 chạy cả web/API bằng một lệnh, tự nạp local key và Ctrl+C cleanup đã test.
W-03 DONE — Tech Lead APPROVED29/10/2026, engineering scope. Live synthetic
upload→auto-ready PASS, chưa accuracy PDF BBS_2025 thực tế; chưa W-04/M3.
Launcher d8e7026 đã push main, CI40791847627 SUCCESS exact SHA, remote khớp.
Next action: Chờ chỉ đạo tiếp theo; không bắt đầu W-04.
Các checkpoint PR draft/OPEN dưới đây là lịch sử trước housekeeping.

W-03 final refinement REVIEW: auto-accept core có nguồn, key-file-only Free Tier
rotation với cap chung, UI neutral/human-on-exception. Live scan synthetic2 trang
PASS, auto-ready/user edit, không xác minh dataset thật. [Evidence](../docs/web-demo-v1/w-03-validation.md).
PR #3 draft base W-02; không merge/W-04/M3. Refinement7048d92 đã push/remote khớp,
[CI40718128314](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40718128314)
SUCCESS exact SHA Python3.11/3.12 và Web; REVIEW không đồng nghĩa DONE.
Next action: Tech Lead nghiệm thu độc lập W-03.
Các checkpoint W-03/W-02/W-01 bên dưới là lịch sử trước final refinement.

W-03 REVIEW — người dùng đã giao 28/10/2026; [spec](tasks/W/W-03.md).
Upload PDF thật/local storage, metadata-only worker và Vision Gateway preflight,
review/confirm/revision đã có; [evidence](../docs/web-demo-v1/w-03-validation.md).
W-04 orchestration/extraction và W-05 viewer chưa bắt đầu.
Implementation b494788 đã push/remote khớp, draft PR #3 base W-02;
[CI 40710376652](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40710376652)
SUCCESS exact implementation SHA, không đồng nghĩa Tech Lead đã nghiệm thu.
Next action: Tech Lead nghiệm thu độc lập W-03.
Các đoạn W-01/W-02 bên dưới là lịch sử checkpoint đã nghiệm thu.

W-01 DONE — Tech Lead APPROVED ngày 28/10/2026, Research MVP Lean v3 —
Architecture/Design/Contracts; evaluation scope Architecture/Design/API Contracts.
Phụ thuộc M2-09 DONE; chỉ nghiệm thu thiết kế, chưa có website hoạt động.
W-02 DONE — Tech Lead APPROVED 28/10/2026 theo Research MVP Lean v3;
[spec W-02](tasks/W/W-02.md), accepted `db25039b818f7251cba7b4ed091dd2afa0dbc6ec`.
[CI 40703400345](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40703400345)
SUCCESS Python 3.11/3.12 và Web skeleton. Skeleton local bốn màn hình đã nghiệm
thu; chưa upload/extraction. PR #1/#2 OPEN, PR #2 stacked base W-01, chưa merge.
Next action: Chờ chỉ đạo tiếp theo.
Nhánh ứng dụng này không thay M3–M8, không đưa M3 vào IN_PROGRESS.
[Spec W-01](tasks/W/W-01.md), [thiết kế](../docs/web-demo-v1/architecture.md),
[API](../docs/web-demo-v1/api-contracts.md), [UI](../docs/web-demo-v1/ui-handoff.md).
W-01/W-02 DONE, W-03 REVIEW đã đăng ký; W-04 trở đi vẫn là đề xuất, chưa cấp
quyền bắt đầu và chưa tạo placeholder specs. Chuẩn bị spec/inputs/criteria trước READY.

| Task dự kiến | Dependencies dự kiến | Đầu ra / criteria cần cụ thể hóa |
| --- | --- | --- |
| W-02 Frontend/Backend Skeleton & Local Development | W-01 DONE | DONE: Next.js/FastAPI skeleton, health/proxy local, shell bốn modules; chưa storage/limits hoặc live extraction |
| W-03 PDF Upload & Metadata Preflight | W-02 DONE | REVIEW: upload/storage/Vision preflight/review, tests; live NOT RUN khi thiếu policy; không extraction |
| W-04 Processing Sessions & Progress | W-03 DONE | Bounded worker, page snapshots/polling, partial/retry/restart và quota recovery; giữ runtime M1–M2 |
| W-05 PDF Viewer & Page Navigation | W-03 DONE | PDF gốc, page/zoom/fullscreen, file Range; có thể chuẩn bị độc lập W-04 nhưng không tự mở song song |
| W-06 Financial Evidence Tables & Source Linking | W-04 và W-05 DONE | B01/B02/B03 multi-period/raw/unmapped/quality/source; B09 inventory; cell → PDF page |
| W-07 Integration, Regression & Web Demo V1 Acceptance | W-06 DONE | Integration/error/partial/restart/security, demo acceptance; CI/evaluation đúng ngân sách được giao |

Một task implementation chính tại một thời điểm. W-02 chỉ bắt đầu sau nghiệm thu
W-01 và giao việc rõ ràng; chia nhỏ task khi chuẩn bị nếu cần.
M3 thêm Evidence Graph trong Explorer; M4 tools/QA, M5 planner/specialists,
M6 verification và M7 QA/report dùng AI Workspace chung; M8 evaluation.
Chưa xây hạ tầng tương lai.

<a id="m0"></a>

## M0 — Project Foundation

Mục tiêu: Repository, CI, môi trường, tài liệu, task tracking và handoff.

Phụ thuộc milestone: Không có milestone trước.

Điều kiện hoàn thành: M0-01 đến M0-04 đạt criteria, có bằng chứng Git/CI hoặc blocker được task cho phép ghi rõ.

| Task | Đầu ra dự kiến | Tiêu chí nghiệm thu dự kiến |
| --- | --- | --- |
| <a id="m0-01"></a>M0-01 — Initialize Project Repository | Skeleton, cấu hình và tài liệu nền tảng | Cài môi trường, lint/test, Git/GitHub được xác minh |
| <a id="m0-02"></a>M0-02 — Reorganize Financial Dataset & Commit to GitHub | Dataset local được tổ chức và cấu hình đường dẫn | Bảo toàn dữ liệu, kiểm tra ignore, commit/push thành công |
| <a id="m0-03"></a>M0-03 — Repository Housekeeping & Planning Synchronization | Trạng thái, quy tắc và kế hoạch được đồng bộ | Đối chiếu GitHub/CI, giữ nguyên nghiệp vụ và dữ liệu |
| <a id="m0-04"></a>M0-04 — Project Task Tracking & Codex Handoff System | Registry, dashboard, handoff và roadmap M0–M8 | IDs/dependencies/status/evidence/links nhất quán, kiểm tra và publication |

<a id="m1"></a>

## M1 — Document Understanding

Mục tiêu: Khám phá OCR, contracts, loader/resolver, LLM Gateway, Gemini structured outputs, quota/cache/checkpoint, phân loại tài liệu, dựng bảng, hiệu chỉnh và đánh giá.

Phụ thuộc milestone: M0; các nhánh nội bộ theo registry.

Điều kiện hoàn thành: Input/output contracts được duyệt, provenance giữ nguyên, raw/OCR read-only; các task M1 và đánh giá có bằng chứng, không còn quality blocker chưa xử lý.

| Task | Đầu ra dự kiến | Tiêu chí nghiệm thu dự kiến |
| --- | --- | --- |
| <a id="m1-01"></a>M1-01 — Dataset Inventory & Provenance Review | Manifest local và báo cáo khám phá OCR/provenance | Metadata khớp, mẫu có giới hạn, chỉ công bố thống kê không nhạy cảm |
| <a id="m1-02"></a>M1-02 — Data Contracts & Path Mapping Design | Tổng hợp thiết kế trong phạm vi M1-02 đã đăng ký | Task cha: ba thiết kế con được rà soát, contracts được duyệt trước implementation |
| <a id="m1-02a"></a>M1-02a — Raw OCR Contracts | Contract raw OCR dựa trên cấu trúc quan sát được | Trường nguồn và trường chưa biết được phân biệt; không suy đoán dữ liệu |
| <a id="m1-02b"></a>M1-02b — Document Understanding Contracts | Contract đầu ra hiểu tài liệu và liên kết raw OCR | Provenance, loại kết quả và lỗi được định nghĩa, không thêm schema kế toán |
| <a id="m1-02c"></a>M1-02c — Path Mapping Contract | Quy tắc ánh xạ nguồn Colab/local | Định nghĩa lỗi thiếu, trùng tên, thoát gốc; raw JSON giữ nguyên |
| <a id="m1-03"></a>M1-03 — Configuration & Read-Only OCR Adapter | Tích hợp cấu hình, resolver và adapter đúng phạm vi cũ | Task cha: ba task con đạt và giao tiếp theo contracts đã duyệt |
| <a id="m1-03a"></a>M1-03a — Central Data Configuration | Bộ nạp cấu hình đường dẫn trong core | Kiểm thử biến môi trường, đường dẫn tương đối và cấu hình thiếu |
| <a id="m1-03b"></a>M1-03b — Read-Only Path Resolver | Resolver theo contract, không sửa JSON nguồn | Kiểm thử file thiếu/trùng, đường dẫn ngoài gốc và ánh xạ provenance |
| <a id="m1-03c"></a>M1-03c — Read-Only OCR Data Loader | Adapter đọc OCR trong document_processing | Đọc mẫu hợp lệ, lỗi rõ ràng, không ghi raw/processed |
| <a id="m1-03d"></a>M1-03d — Missing Crop Audit & Bounded Recovery | Audit/tooling và pilot có giới hạn | DONE theo nghiệm thu engineering/synthetic/zero-output |
| <a id="m1-03e"></a>M1-03e — Verified Local Mapping & Real Crop Recovery Pilot | Local mappings và 12 real reconstructed crops | DONE theo Tech Lead APPROVED; equivalence gốc unverified |
| <a id="m1-03f"></a>M1-03f — Controlled Table Crop Recovery Expansion | Batch <=24, tổng <=199, index/provenance và evidence | Human visual approval trước expansion, nguồn bất biến; checkpoint REVIEW đã được Tech Lead APPROVED 2026-10-27, DONE |
| <a id="m1-04"></a>M1-04 — Extraction Quality Validation & Pilot | Tổng hợp validation và pilot giữ phạm vi cũ | Task cha: validators và pilot con đạt, nêu rõ giới hạn chất lượng |
| <a id="m1-04a"></a>M1-04a — Extraction Structure Validators | Kiểm tra cấu trúc và liên kết JSON–ảnh | Bắt lỗi theo contract, lưu issue có nguồn, không sửa dữ liệu để làm hết lỗi |
| <a id="m1-04b"></a>M1-04b — Bounded Extraction Pilot | Báo cáo pilot trên tập con được giao | Có manifest mẫu, kết quả tái kiểm tra được, không xử lý toàn dataset |
| <a id="m1-05"></a>M1-05 — LLM Gateway Contract | Contract chung cho model, structured output và usage/cost | Được rà soát trước chọn SDK/model; không gọi nhà cung cấp trực tiếp ngoài gateway |
| <a id="m1-06"></a>M1-06 — Shared LLM Gateway | Implementation gateway theo contract | Test đổi cấu hình model, lỗi, structured result và ghi usage bằng transport giả lập |
| <a id="m1-07"></a>M1-07 — Gemini Structured Output Adapter | Adapter Gemini đi qua gateway | Validate output theo schema đã duyệt; live API chỉ khi task cho phép |
| <a id="m1-08"></a>M1-08 — Quota and Budget Management | Chính sách quota, retry và giới hạn chi phí | Test giới hạn/dừng, không vượt ngân sách đã cấu hình |
| <a id="m1-09"></a>M1-09 — LLM Response Cache | Cache theo request/model/schema version | Kiểm thử hit/miss/invalidation và không lưu secrets |
| <a id="m1-10"></a>M1-10 — Document Processing Checkpoints | Checkpoint/resume cho đơn vị xử lý tài liệu | Không làm lại kết quả đã xác minh; phiên bản input/config được đối chiếu |
| <a id="m1-11"></a>M1-11 — Page and Document Classification | Kết quả phân loại có provenance | Taxonomy được duyệt, trả unresolved khi thiếu bằng chứng |
| <a id="m1-12"></a>M1-12 — Table Structure Reconstruction | Cấu trúc bảng dẫn về vùng raw OCR | Kiểm thử hàng/cột và ô gộp trên mẫu đã chú giải, không tự thêm số liệu |
| <a id="m1-12a"></a>M1-12a — Gemini-Assisted Table Reconstruction | Đề xuất cấu trúc cho bảng deterministic unresolved qua Gateway/Gemini Adapter hiện có | Structured output + local schema/source/evidence validation; không sinh nội dung, giữ provenance; same8 pilot với max15 requests; [spec](tasks/M1/M1-12a.md), REVIEW chờ Tech Lead |
| <a id="m1-13"></a>M1-13 — Evidence-Preserving OCR Correction | Bản hiệu chỉnh riêng kèm nguồn và lý do | Raw OCR bất biến; phân biệt đề xuất, xác nhận và unresolved |
| <a id="m1-14"></a>M1-14 — Document Understanding Evaluation | Protocol và kết quả đánh giá hiểu tài liệu | Mẫu/nhãn/ngưỡng được chốt, phân biệt chất lượng thực tế với smoke tests |

<a id="m2"></a>

## M2 — Accounting Normalization

Mục tiêu: Contracts tài chính, kỳ/đơn vị/phạm vi, nhận diện B01/B02/B03/B09, mapping chỉ tiêu, kiểm tra số học/quan hệ và quality gates.

Phụ thuộc milestone: M1; dữ liệu hiểu tài liệu và contracts đã được nghiệm thu.

Điều kiện hoàn thành: Kết quả chuẩn hóa truy nguyên được, số học được kiểm tra bằng quy tắc đã duyệt, dữ liệu thiếu/mơ hồ được giữ là unresolved.

| Task | Đầu ra dự kiến | Tiêu chí nghiệm thu dự kiến |
| --- | --- | --- |
| <a id="m2-01"></a>M2-01 — Financial Normalization Contracts | Contracts chuẩn hóa tài chính được rà soát | Định nghĩa giá trị, kỳ, đơn vị, phạm vi và provenance; mapping chi tiết cần duyệt |
| <a id="m2-02"></a>M2-02 — Period Unit and Reporting Scope | Chuẩn hóa kỳ, đơn vị và riêng/hợp nhất | Giữ nguồn, đánh dấu mơ hồ, kiểm thử nhiều định dạng đã xác định |
| <a id="m2-03"></a>M2-03 — Statement Type Recognition | Nhận diện B01/B02/B03/B09 theo ngữ cảnh | Không dựa riêng tên file; báo unresolved khi không đủ căn cứ |
| <a id="m2-04"></a>M2-04 — Financial Item Mapping | Mapping chỉ tiêu theo danh mục đã duyệt | Lưu mapping evidence, không tự tạo quy tắc kế toán |
| <a id="m2-04a"></a>M2-04a — Gemini-Assisted Table Recovery & Numeric Linking | Khôi phục bảng và liên kết số có bằng chứng | Pilot ảnh thực và validation độc lập; [spec](tasks/M2/M2-04a.md) |
| <a id="m2-04b"></a>M2-04b — Gemini-First Automated Financial Extraction & Numeric Linking | PDF → Gemini → mapping → numeric links tự động và Decimal | Không ManualReview runtime; pilot B01/B02/B03, giữ provenance; [spec](tasks/M2/M2-04b.md); dependency của M2-05 |
| <a id="m2-05"></a>M2-05 — Deterministic Arithmetic Checks | Kiểm tra số học theo công thức được duyệt | Test đơn vị/dung sai/làm tròn và lineage đầu vào |
| <a id="m2-06"></a>M2-06 — Accounting Relationship Checks | Kiểm tra quan hệ giữa các báo cáo | Phân biệt lỗi, nghi vấn và dữ liệu thiếu; không tự kết luận vi phạm pháp lý |
| <a id="m2-07"></a>M2-07 — Task-Aware Normalization Quality Gates | Annotations theo tác vụ, giữ raw ngoài catalog và partial evidence | Usability có nguồn/reasons; không global gate; [API/pilot](../docs/task-aware-quality.md) |

<a id="m3"></a>

## M3 — Canonical Evidence & EF-EG

Mục tiêu: **Typed Executable Financial Evidence Graph with Semantic Compatibility
and Evidence-Quality Propagation** theo [kiến trúc M3](../docs/architecture.md#định-hướng-m3--typed-executable-financial-evidence-graph).
Đây là định hướng nghiên cứu, chưa tuyên bố thuật toán mới, novelty/SOTA hoặc kết quả
thực nghiệm đã xác minh. M3 chưa bắt đầu; preflight chỉ đồng bộ tài liệu.

Phụ thuộc milestone: M2; giữ provenance từ M1, không chờ đến M3 mới ghi nguồn.

Giữ pipeline `SourceFact → DerivedMetric → Claim → VerificationRecord`.
M3 gồm SourceFact/CanonicalFinancialFact, EvidenceAnchor, TextEvidence/TableEvidence,
typed graph relations, DerivedMetric representations, lineage và retrieval.
Claim thuộc luồng M5/M6; Claim, VerificationRecord và Verified Claim Ledger không
triển khai tại M3. M4 thực thi deterministic financial tools và baseline đã đăng ký;
M5 adaptive planner/specialists; M6 verification/ledger; M7 grounded QA/report;
M8 controlled evaluation/ablation. “Executable” tại M3 là biểu diễn phục vụ M4.

Semantic compatibility phải xét financial item, reporting period, reporting scope,
unit/scale, document/source identity và formula operand roles theo quy tắc được duyệt;
không tự suy quy tắc kế toán. Quality contract bảo toàn `usable`, `usable_with_caveat`,
`insufficient`, `conflicted`, cùng unresolved provenance và missing operands dưới dạng
reasons/tình trạng. Phân biệt source grounding, numerical calculation validity và claim
verification; không đặt confidence score, thresholds hoặc propagation algorithm tại preflight.

Điều kiện hoàn thành dự kiến: Contracts canonical/provenance/semantic types và quality
propagation được duyệt; facts/evidence/lineage truy nguyên được; retrieval có kiểm thử, giữ quality
context và hỗ trợ đánh giá thực nghiệm sau này. Quy tắc chi tiết, cách đo và engine
lưu trữ còn TBD. Không tự xây graph/vector database, LLM agents hay frontend.
Giữ nguyên caveats M1/M2/W-07; usability hoặc smoke không chứng nhận financial accuracy.
Giữ nguyên bảy task, IDs, dependencies và TODO trong registry; không tạo M3-08.

| Task | Đầu ra dự kiến | Tiêu chí nghiệm thu dự kiến |
| --- | --- | --- |
| <a id="m3-01"></a>M3-01 — Canonical and Provenance Contracts | Contracts SourceFact/CanonicalFinancialFact, EvidenceAnchor và semantic type rules | Rà soát identity/provenance và compatibility của item, kỳ, scope, unit/scale, document/source, operand roles; unknown giữ TBD/unresolved, không tự tạo quy tắc kế toán |
| <a id="m3-02"></a>M3-02 — Canonical Financial Facts | Biểu diễn/lưu/truy xuất facts chuẩn hóa có nguồn | Giữ raw/context/quality và mapping đã duyệt; raw ngoài catalog còn truy xuất được, không tự gộp identity hoặc nâng thành verified |
| <a id="m3-03"></a>M3-03 — Text and Table Evidence | TextEvidence/TableEvidence liên kết EvidenceAnchor | Truy nguyên đoạn/vùng/bảng theo contract; không nâng page-level thành cell-level khi chưa có bằng chứng |
| <a id="m3-04"></a>M3-04 — EF-EG Nodes and Edges | Typed nodes/relations theo contracts, mở rộng về Claim/VerificationRecord | Kiểm tra types, references và semantic constraints được duyệt trên graph mẫu; không triển khai claim/verification/ledger tại M3, storage TBD |
| <a id="m3-05"></a>M3-05 — Derived Metric Records | DerivedMetric representations: công thức, operand roles, inputs và kết quả nếu có | Giữ tham chiếu typed facts/evidence và operands thiếu; executor deterministic thuộc M4, không dùng LLM làm máy tính |
| <a id="m3-06"></a>M3-06 — Calculation Lineage | Lineage và evidence-quality propagation contract | Truy metric → công thức/operands → facts/anchors; giữ bốn quality decisions, caveats/conflicts, unresolved provenance và missing operands; đủ input cho M4 thực thi lại khi có thể, không tự đặt scores/thresholds/algorithm |
| <a id="m3-07"></a>M3-07 — Evidence Retrieval Interface | Truy xuất facts/text/table/graph/lineage phục vụ tools và đánh giá thực nghiệm | Trả IDs, nguồn, semantic/quality context và thiếu/mâu thuẫn để đối chiếu; chuẩn bị khả năng đánh giá, không tự chạy benchmark hoặc chọn engine chưa duyệt |

<a id="m4"></a>

## M4 — Financial Tools & QA Baseline

Mục tiêu: Shared Executable Tool Space, retrieval, calculator và baseline QA.

Phụ thuộc milestone: M3 và Gateway của M1.

Điều kiện hoàn thành: Tools có contracts, kết quả/lineage kiểm tra được; baseline có protocol, được phân biệt với verified output chính thức.

| Task | Đầu ra dự kiến | Tiêu chí nghiệm thu dự kiến |
| --- | --- | --- |
| <a id="m4-01"></a>M4-01 — Executable Tool Contracts | Contracts Shared Executable Tool Space | Đầu vào/ra/lỗi/provenance có kiểu và được duyệt |
| <a id="m4-02"></a>M4-02 — Typed Financial Retrieval Tools | Công cụ truy xuất facts/metrics | Đối chiếu kỳ, đơn vị, phạm vi và evidence IDs |
| <a id="m4-03"></a>M4-03 — Calculator and Formula Executor | Thực thi công thức được duyệt bằng công cụ xác định | Kiểm thử input thiếu, số học, dung sai và khả năng tính lại qua lineage |
| <a id="m4-04"></a>M4-04 — Evidence Retrieval Tools | Tool wrappers cho truy xuất bằng chứng | Dùng interface M3, trả nguồn và trạng thái; không thêm storage engine ngầm |
| <a id="m4-05"></a>M4-05 — Question Answering Baseline | Baseline QA nghiên cứu có công cụ và bằng chứng | Kết quả baseline được nhận diện riêng, không được coi là verified output chính thức |

<a id="m5"></a>

## M5 — Adaptive Multi-Agent

Mục tiêu: Evidence Plan, Query Planner, Supervisor, ba specialist roles đã nêu trong báo cáo, adaptive routing và orchestration.

Phụ thuộc milestone: M4.

Điều kiện hoàn thành: Điều phối theo evidence/risk có trace và điều kiện dừng; specialist outputs vẫn là candidate claims cần kiểm chứng. Không tự thêm agent.

| Task | Đầu ra dự kiến | Tiêu chí nghiệm thu dự kiến |
| --- | --- | --- |
| <a id="m5-01"></a>M5-01 — Evidence Plan and Planner Contracts | Contracts query/evidence plan và trạng thái điều phối | Nhu cầu bằng chứng, lỗi và điều kiện dừng được rà soát |
| <a id="m5-02"></a>M5-02 — Evidence-Aware Query Planner | Planner chọn bước truy xuất/tính toán | Kế hoạch bám nhu cầu bằng chứng và tập công cụ đã có |
| <a id="m5-03"></a>M5-03 — Risk-Aware Supervisor | Supervisor quản lý trạng thái và giới hạn thực thi | Theo dõi thiếu/mâu thuẫn bằng chứng, kiểm thử điều kiện dừng |
| <a id="m5-04"></a>M5-04 — Profitability Specialist | Tác nhân lợi nhuận theo vai trò đã nêu trong báo cáo | Chỉ tạo candidate claims có nguồn qua shared tools |
| <a id="m5-05"></a>M5-05 — Liquidity and Leverage Specialist | Tác nhân thanh khoản/đòn bẩy theo thiết kế đã có | Không tự thêm chỉ số hoặc công thức chưa được duyệt |
| <a id="m5-06"></a>M5-06 — Cash Flow and Earnings Quality Specialist | Tác nhân dòng tiền/chất lượng lợi nhuận theo thiết kế đã có | Giữ evidence lineage và giới hạn khi thiếu thuyết minh |
| <a id="m5-07"></a>M5-07 — Adaptive Routing Rules | Routing theo evidence/risk signals đã được duyệt | Ngưỡng là cấu hình có căn cứ; không tự thêm agent mới |
| <a id="m5-08"></a>M5-08 — Agent and Tool Orchestration | Phối hợp planner/supervisor/specialists/tools | Luồng có trace, giới hạn và xử lý bằng chứng mâu thuẫn |

<a id="m6"></a>

## M6 — Claim Verification

Mục tiêu: Candidate Claim contracts, deterministic validators, Evidence Critic, Financial Logic Critic, Judge và Verified Claim Ledger.

Phụ thuộc milestone: M5 và shared tools.

Điều kiện hoàn thành: ACCEPT/REVISE/INVESTIGATE/ABSTAIN được kiểm thử; chỉ claim được chấp nhận vào ledger, có nguồn và lịch sử kiểm chứng.

| Task | Đầu ra dự kiến | Tiêu chí nghiệm thu dự kiến |
| --- | --- | --- |
| <a id="m6-01"></a>M6-01 — Candidate Claim Contracts | Contract claim và bằng chứng kiểm chứng | Phân biệt fact, metric, diễn giải và trạng thái xác minh |
| <a id="m6-02"></a>M6-02 — Deterministic Financial Validators | Kiểm tra số, công thức, kỳ, đơn vị, phạm vi | Test validators bằng quy tắc đã duyệt và giữ calculation lineage |
| <a id="m6-03"></a>M6-03 — Evidence Critic | Kiểm tra bằng chứng và citation support | Không chấp nhận claim thiếu nguồn hoặc suy diễn ngoài bằng chứng |
| <a id="m6-04"></a>M6-04 — Financial Logic Critic | Kiểm tra tính hợp lý của lập luận | Ghi rõ giới hạn và mâu thuẫn, không biến nghi vấn thành kết luận |
| <a id="m6-05"></a>M6-05 — Verification Decisions | Judge với ACCEPT/REVISE/INVESTIGATE/ABSTAIN | Vòng kiểm chứng bị giới hạn; safe abstention khi thiếu bằng chứng |
| <a id="m6-06"></a>M6-06 — Verified Claim Ledger | Ledger claim được chấp nhận và lịch sử xác minh | Claim chưa ACCEPT không vào verified ledger; truy vết được quyết định |

<a id="m7"></a>

## M7 — Grounded Output

Mục tiêu: Vietnamese QA Composer, Report Outline Planner, Grounded Writer, citation rendering và Information Firewall.

Phụ thuộc milestone: M6.

Điều kiện hoàn thành: QA/report chỉ dùng ledger; citation có thể đối chiếu, không tự thêm dữ kiện/truy xuất/tính toán ở lớp output.

| Task | Đầu ra dự kiến | Tiêu chí nghiệm thu dự kiến |
| --- | --- | --- |
| <a id="m7-01"></a>M7-01 — Vietnamese QA Composer | Câu trả lời tiếng Việt từ verified ledger | Không tạo số liệu hoặc truy xuất mới ngoài ledger |
| <a id="m7-02"></a>M7-02 — Report Outline Planner | Dàn ý báo cáo dựa trên verified claims | Không bổ sung nhiệm vụ phân tích hoặc dữ kiện mới tại lớp output |
| <a id="m7-03"></a>M7-03 — Grounded Report Writer | Báo cáo tiếng Việt có căn cứ | Mọi nhận định tài chính gắn với verified claim và nguồn |
| <a id="m7-04"></a>M7-04 — Citation Rendering | Trình bày citation dùng chung | Citation đối chiếu được về nguồn/vị trí theo contract |
| <a id="m7-05"></a>M7-05 — Information Firewall and Output Validation | Gate đầu ra và kiểm tra QA/report | Chặn claim chưa xác minh và nội dung không có trong ledger |

<a id="m8"></a>

## M8 — Evaluation & Integration

Mục tiêu: Dataset đánh giá, baselines, QA/report metrics, ablation, usage/latency/cost, end-to-end integration và demo.

Phụ thuộc milestone: M7; protocol/nhãn/ngân sách phải xác định trước thực nghiệm.

Điều kiện hoàn thành: Protocol và cấu hình tái kiểm tra được, số đo thực tế có bằng chứng; công bố giới hạn, chi phí và kết quả hai luồng, không suy diễn từ smoke tests.

| Task | Đầu ra dự kiến | Tiêu chí nghiệm thu dự kiến |
| --- | --- | --- |
| <a id="m8-01"></a>M8-01 — Evaluation Dataset Protocol | Tập chia, chú giải và manifest đánh giá được duyệt | Không rò rỉ doanh nghiệp giữa tập; dữ liệu lớn không vào Git |
| <a id="m8-02"></a>M8-02 — Controlled Baseline Experiments | Các baseline được chọn theo protocol | Cùng model/dữ liệu/ngân sách; phạm vi từng experiment được giao riêng |
| <a id="m8-03"></a>M8-03 — Interactive QA Metrics | Đánh giá QA và hội thoại | Công thức, reference labels và dung sai được chốt, không bịa điểm |
| <a id="m8-04"></a>M8-04 — Report Generation Metrics | Đánh giá support, citation và chất lượng báo cáo | Protocol tự động/thủ công được xác định, nêu rõ độ bao phủ |
| <a id="m8-05"></a>M8-05 — Ablation Experiments | Thực nghiệm bỏ từng cơ chế theo thiết kế | Có cấu hình so sánh và ngân sách; không chạy hàng loạt ngoài task |
| <a id="m8-06"></a>M8-06 — Usage Latency and Cost Evaluation | Đo tokens, calls, latency và cost | Đo từ usage thực tế, có model/config/budget của lần chạy |
| <a id="m8-07"></a>M8-07 — End-to-End Integration | Kiểm thử hai luồng từ dữ liệu đến đầu ra | Provenance, verification, firewall và lỗi thiếu bằng chứng được kiểm tra |
| <a id="m8-08"></a>M8-08 — Application Demo | Demo tối thiểu theo phạm vi được giao | QA/report hoạt động với dữ liệu được phép, công bố giới hạn và chi phí |

## Các ràng buộc xuyên suốt

Giữ Modular Monolith và ba lớp Offline → Online → Output. Mọi LLM đi qua
Gateway; không triển khai Gateway cùng OCR trong một task. Không gộp EF-EG với
Multi-Agent, QA với Report Generation, hoặc hệ thống với toàn bộ benchmark vào
một task. Thực nghiệm/live API chỉ chạy khi task cho phép và có ngân sách.

Contracts, công thức kế toán, ngưỡng rủi ro/đánh giá và model chưa chốt không
được tự suy đoán. Công việc ngoài phạm vi phải ghi thành đề xuất task mới.
M0-04 chỉ thiết lập tài liệu quản lý; dừng sau M0-04, không bắt đầu M1-01.

## M2-08 — Audit bổ sung được giao

[M2-08](tasks/M2/M2-08.md) DONE, dependency M2-07 DONE.
Tech Lead APPROVED Research MVP Lean v3 ngày 2026-10-28; nghiệm thu planning-only.
Gemini structured financial extraction là primary path; OCR/unified, manual recovery
và accounting checks optional theo tác vụ. Benchmark một PDF BBS2025, structured
intents:23/26→25/26 answered; gain từ recovery thêm trang6, chưa đánh giá NL chatbot.
Sau nghiệm thu M2-08, Tech Lead giao thêm M2-09 trước quyết định Web Demo V1;
chưa tự bắt đầu Web Demo hoặc M3.

## M2-09 — Full-PDF evaluation bổ sung được giao

[M2-09](tasks/M2/M2-09.md) DONE, dependency M2-08 DONE. Tech Lead APPROVED
Research MVP Lean v3, Evaluation Level 1 ngày 2026-10-28; nghiệm thu planning-only.
Một PDF BBS2025/24 trang, discovery đúng 24/24: B01 5–6, B02 7, B03 8, B09 9–24.
Reference 163 numeric cells +7 dash; precision/recall/kỳ/đơn vị/grounding 163/163
trong reference. 7 dash sai raw glyph vẫn missing, không suy zero.
25 calls mới/37.382 tokens, discovery 116,11 giây. Một agent đối chiếu trực tiếp PDF,
không reviewer độc lập thứ hai; chưa đánh giá tổng quát, notes QA hoặc chatbot.
Gemini-first, tự chọn trang, optional accounting checks, không ManualReview gate.
Tech Lead đồng ý CONDITIONAL GO Document Explorer B01/B02/B03, B09 chỉ inventory/viewer.
Implementation
`bd5a3c525f4cfe1d3f5204983e86746e748b1c93` đã push;
[CI40661431781](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40661431781)
SUCCESS đúng SHA, Python 3.11/3.12 mọi bước đã xác minh lại.
Chỉ planning checker/diff; không sửa implementation/tests/dữ liệu/artifacts,
không gọi Gemini/chạy lại pytest/CI. [Báo cáo](../docs/m2-09-full-pdf-evaluation.md)
giữ checkpoint REVIEW lịch sử. Next action: Chờ Tech Lead giao Web Demo V1;
không tự bắt đầu Web Demo V1 hoặc M3.
