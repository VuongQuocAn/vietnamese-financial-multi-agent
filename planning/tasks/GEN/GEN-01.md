# TASK GEN-01 — Cross-Company Ingestion & EF-EG Generalization

## Metadata

- Milestone: GEN
- Status: REVIEW
- Priority: P1
- Dependencies: E2E-01
- Estimated Complexity: M

Owner giao 06/11/2026 và cho phép commit/push main. Owner xác nhận dùng
`BCC_2024.pdf` thay tên `BBC_2024.pdf` trong đề bài; giữ nguyên nội dung giao việc
bên dưới để truy nguyên, áp dụng tên đã được xác nhận khi thực thi.

## Context

Repository: `VuongQuocAn/vietnamese-financial-multi-agent`  
Branch: `main`

Vai trò:
- Project Owner: quyết định ưu tiên.
- ChatGPT: Tech Lead, Solution Architect và Independent Reviewer.
- Codex: Implementation Engineer.

Trạng thái:
- M1–M7: DONE.
- QA-Fix-01/02: DONE.
- E2E-01: **DONE**.
- E2E implementation: `9811a4443f24a8b8083491f1968ab641ee69b63a`.
- E2E closeout: `041146688c9d3db1c3c0a82b6ab14a9718ab241d`.

Hai PDF mới đã được Project Owner bổ sung vào workspace:

- `BCC_2025.pdf`
- `BBC_2024.pdf`

**Không giả định BCC và BBC là cùng doanh nghiệp.** Phải xác minh tên, mã chứng khoán, kỳ báo cáo và phạm vi từ tài liệu gốc.

## Objective

Kiểm chứng liệu hệ thống hiện tại có thể tiếp nhận báo cáo tài chính của doanh nghiệp mới mà không cần chỉnh code riêng cho BBS, BCC hoặc BBC.

Phạm vi pipeline:

`PDF → Discovery/Extraction → Financial Normalization → Canonical Facts → EF-EG → M4 Financial Tools`

**GEN-01 chưa chạy M5→M6→M7 trên hai báo cáo mới.** Phần đó thuộc GEN-02.

Mục tiêu quan trọng nhất là phát hiện và sửa những phụ thuộc BBS không hợp lý trong ingestion, mapping, graph construction và financial tool preparation.

## Inputs

Hai PDF local đã xác minh từ bìa/thuyết minh: BCC2025 riêng, BCC2024 hợp nhất;
approved M1–M4 runtime/contracts và policies. Không dùng BBS để bổ sung dữ liệu.

## Implementation Steps

Thực hiện Phase A–F trong ngân sách chung, lưu partial khi thiếu evidence.

## 3. Phase A — Preflight & Architecture Audit

Trước khi chạy Gemini:

1. Kiểm tra Git và workspace.
2. Tìm chính xác hai PDF trong workspace, không yêu cầu Owner nhập lại đường dẫn nếu file đã tồn tại.
3. Đọc metadata hai tài liệu: tên doanh nghiệp, loại báo cáo, năm, số trang, text layer, dạng scan.
4. Kiểm tra các entrypoints M1–M4 và Web ingestion hiện có.
5. Kiểm tra cách tạo document_id, company_id, snapshot_id.
6. Tìm những chỗ giả định BBS hoặc đường dẫn cố định trong runtime.
7. Phân biệt hardcode trong scripts demo/tests với hardcode ảnh hưởng production.

Lập bảng:

| Component | Generic / BBS-dependent | Evidence | Impact |
|---|---|---|---|
| PDF ingestion | | | |
| Discovery | | | |
| Extraction | | | |
| Context resolver | | | |
| Item mapping | | | |
| Canonical adapter | | | |
| EF-EG builder | | | |
| Financial Tools | | | |

Không sửa runtime nếu chưa xác nhận nguyên nhân.

## 4. Phase B — Fresh Cross-Company Ingestion

Chạy hai PDF mới bằng pipeline hiện có, ưu tiên entrypoints production.

Không sử dụng dữ liệu BBS để bổ sung missing facts của BCC/BBC.

### Yêu cầu

- Tự nhận diện các báo cáo B01/B02/B03 và thuyết minh nếu có.
- Giữ đúng document/company identity.
- Đúng kỳ, đơn vị, hệ số tỷ lệ và reporting scope.
- Trích xuất những trang cần thiết, không yêu cầu chọn trang thủ công nếu discovery hỗ trợ.
- Giữ số liệu gốc và reference tới PDF.
- Ghi rõ uncertain/unresolved thay vì ép ACCEPT.
- Không suy zero từ ô trống hoặc dấu gạch.
- Không gộp dữ liệu doanh nghiệp khác.

### Gemini budget

Dùng model và Gateway hiện tại.

Trước khi chạy live, xác định số trang và dự kiến số requests. Đặt ngân sách ban đầu **tối đa 60 provider attempts cho cả hai PDF**, tính cả retry và recovery.

Nếu tài liệu quá dài, thực hiện theo thứ tự ưu tiên B01/B02/B03, lưu kết quả partial và báo giới hạn. Không tự vượt ngân sách.

Không thay model trả phí hoặc tự xoay sang credential ngoài cấu hình hiện tại.

## 5. Phase C — Canonical Facts & EF-EG

Từ extracted evidence thực tế:

1. Tạo CanonicalFinancialFacts bằng adapter hiện có.
2. Gắn EvidenceAnchors và source references.
3. Build EF-EG từ facts/evidence mới.
4. Validate graph nodes, edges, identity và lineage.
5. Kiểm tra các quan hệ không bị tạo nhầm giữa BCC/BBC/BBS.
6. Ghi lại blocked/unresolved observations.

Không hardcode nodes/edges theo doanh nghiệp.

Nếu graph chỉ hỗ trợ tập relation cố định, giữ schema hiện hành; phân tích những loại dữ liệu mới không biểu diễn được.

Không tự tạo relation mới dựa vào suy đoán của Gemini.

## 6. Phase D — Financial Tools Readiness

Kiểm tra M4 trên từng tài liệu:

- Tổng tài sản.
- Nợ phải trả.
- Doanh thu thuần.
- Lợi nhuận gộp.
- Lợi nhuận sau thuế.
- Dòng tiền từ hoạt động kinh doanh.
- Gross Margin.
- Debt-to-Assets.

Chỉ tính metric khi có đủ operands và đáp ứng accounting gates hiện có.

Không xem `found` là financial fact verified.

Với mỗi chỉ tiêu, phân loại:

- Available and usable.
- Available with caveats.
- Ambiguous.
- Unsupported mapping.
- Missing evidence.
- Blocked by context/scope/policy.

Không mở rộng approved financial formulas chỉ để nâng coverage.

## 7. Phase E — Independent PDF Audit

Codex phải dùng khả năng đọc và phân tích PDF trực tiếp để đối chiếu kết quả pipeline.

Không dùng Gemini extraction output làm ground truth duy nhất.

Đối chiếu tối thiểu những chỉ tiêu quan trọng được tìm thấy ở B01/B02/B03.

Kiểm tra:
- Giá trị.
- Kỳ.
- Đơn vị.
- Tên chỉ tiêu.
- Statement type.
- Source page.
- Company/document identity.

Có thể sử dụng những tài liệu có ít chỉ tiêu hơn; phải ghi đúng coverage thực tế.

Báo cáo precision/correctness theo **số observations thực sự đã đối chiếu**, không tuyên bố accuracy toàn bộ báo cáo khi chưa kiểm tra đầy đủ.

## 8. Phase F — Generalized Root-Cause Fix

Khi phát hiện lỗi, phân loại:

| Loại lỗi | Hướng xử lý |
|---|---|
| Hardcode BBS | Loại bỏ phụ thuộc, thay bằng context từ tài liệu |
| Extraction sai | Sửa prompt/schema/validation chung |
| Mapping thiếu | Cân nhắc mở rộng canonical aliases có bằng chứng |
| Context sai | Sửa resolver theo chính sách chung |
| EF-EG sai | Sửa graph builder hoặc binding logic |
| Tool readiness sai | Sửa adapter/selection, không bỏ gate |
| Dữ liệu không đủ | Giữ partial/blocked |

Trước mỗi thay đổi runtime, tạo failing regression test và xác nhận nguyên nhân.

Không tạo `if company == "BCC"` hoặc `if company == "BBC"` để xử lý riêng.

Đảm bảo dữ liệu BBS cũ vẫn hoạt động bằng regression tests.

Ưu tiên sửa các lỗi P0/P1 trong phạm vi ingestion/normalization/EF-EG/M4. Lỗi ngoài phạm vi phải ghi rõ nguyên nhân và đề xuất cho GEN-02 hoặc task riêng.

## Outputs

Tạo:

`docs/gen-01-cross-company-ingestion-generalization.md`

Artifacts:

`artifacts/evidence/GEN-01/`

Báo cáo gồm:

### A. Document Inventory

Tên doanh nghiệp, mã, năm, pages, statement coverage, scan/text, scope.

### B. Pipeline Execution

Đối với BCC và BBC:

| Stage | Status | Input | Output | Time | Gemini calls |
|---|---|---|---|---|---|
| Discovery | | | | | |
| Extraction | | | | | |
| Normalization | | | | | |
| Canonical Facts | | | | | |
| EF-EG | | | | | |
| M4 Tools | | | | | |

### C. Financial Audit

Có bảng số liệu thực tế từ PDF, kết quả pipeline, sai lệch và source pages.

### D. Generalization Findings

Những thành phần chạy được ngay, những thành phần phải sửa, và lý do.

### E. Regression

Số tests mới, tests cũ, failures trước/sau.

### F. Limitations

Các chỉ tiêu chưa hỗ trợ, scope chưa rõ, mapping gaps, evidence quality, latency.

### G. Next Action

Đề xuất GEN-02 khi ingestion và evidence đã đủ usable.

Không thay thế kết quả thực tế bằng SHA hoặc JSON hashes.

## Allowed Changes

- Không chạy M5/M6/M7 trên BCC/BBC trong GEN-01.
- Không chạy M8.
- Không thay đổi dữ liệu BBS đã nghiệm thu.
- Không ghi đè PDF hoặc accepted snapshots.
- Không hash hàng chục nghìn file.
- Không tạo checkpoint commits hình thức.
- Không yêu cầu Project Owner đánh giá thủ công từng ô.
- Codex tự thực hiện independent audit trong khả năng của mình.
- Không cần tối ưu toàn bộ ledger latency trong task này.
- Dùng Git diff và focused tests để kiểm tra phạm vi.
- Commit/push `main`, xác minh CI đúng implementation SHA.
- Dừng tại REVIEW.

## Acceptance Criteria

- [ ] Hai PDF được nhận diện và xử lý thực tế.
- [ ] Có discovery/extraction results của từng báo cáo.
- [ ] Có Canonical Facts và EF-EG được xây từ dữ liệu mới.
- [ ] Có ít nhất một tập financial facts usable cho mỗi PDF, hoặc blocker rõ ràng kèm bằng chứng.
- [ ] M4 tools được thử trên cả hai tài liệu.
- [ ] Independent PDF audit được thực hiện.
- [ ] Không lẫn dữ liệu BBS/BCC/BBC.
- [ ] Lỗi hardcode được xác định và sửa tổng quát nếu có.
- [ ] BBS regression PASS.
- [ ] CI SUCCESS đúng SHA.
- [ ] Báo cáo có số liệu thực, không chỉ thống kê engineering.
- [ ] Không bắt đầu GEN-02/M8.
- [ ] Dừng REVIEW.

Nếu một hoặc cả hai PDF chưa thể hoàn tất do thiếu evidence, API/provider hoặc quality constraints, báo cáo chính xác phần đã chạy, earliest failing stage và root cause. Không tuyên bố PASS giả.

## Handoff Notes

**GEN-01 — REVIEW**

1. Implementation SHA + CI.
2. Metadata BCC/BBC.
3. Coverage discovery/extraction.
4. Canonical Fact counts.
5. EF-EG nodes/edges.
6. M4 usable facts/metrics.
7. Independent PDF audit.
8. Hardcode/generalization issues phát hiện và đã sửa.
9. BBS regression.
10. Gemini calls/tokens và latency.
11. P0/P1 tồn đọng.
12. Link báo cáo.

**DỪNG Ở REVIEW.** Tech Lead nghiệm thu trước khi triển khai GEN-02.

Next action: Tech Lead review GEN-01 và quyết định readiness GEN-02.

## Out of Scope

Không M5–M8 trên dữ liệu mới; không sửa BBS accepted snapshots, ledger latency,
formulas/schema relations, model hoặc credentials ngoài cấu hình hiện tại.

## Required Tests

Focused tests ingestion/context/mapping/quality/canonical/graph/M4; replay read-only
BBS32 mapped links và18 accepted metrics; independent PDF audit24 observations.
Ruff, planning checker, diff check và CI đúng implementation SHA.

## Risks and Blockers

2024 metrics bị chặn accounting basis; giữ các mapping gaps ngoài sáu chỉ tiêu.
Discovery partial trong ngân sách, provenance page-level; chưa accuracy toàn PDF.
REVIEW chờ CI và Tech Lead, không tự nghiệm thu DONE.

## Implementation Evidence

Baseline `041146688c9d3db1c3c0a82b6ab14a9718ab241d`; implementation chưa commit.
40/60 attempts, 105.149 known tokens,2 HTTP503;204 observations mỗi PDF.
24/24 PDF observations khớp;176 focused PASS;BBS32 links/18 metrics PASS.
Chi tiết và giới hạn: [report](../../../docs/gen-01-cross-company-ingestion-generalization.md).
