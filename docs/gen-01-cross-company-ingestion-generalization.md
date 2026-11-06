# GEN-01 — Cross-Company Ingestion & EF-EG Generalization

Ngày 06/11/2026 (Asia/Bangkok). **DONE**, APPROVED theo quyết định nghiệm thu.
Phiên đóng task chỉ cập nhật docs/planning và chạy planning/diff checks; không
chạy lại Gemini, tests hoặc benchmark. Giữ nguyên kết quả và limitations bên dưới.
Baseline `041146688c9d3db1c3c0a82b6ab14a9718ab241d`; implementation
`0a0d94041696e3210a073e28c789d0113b7b16e0` đã push main;
[CI42169755054](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42169755054)
completed/SUCCESS đúng SHA:1.078 Python/9 Web PASS; full regression SKIPPED.
Owner cho phép commit/push main và xác nhận dùng `BCC_2024.pdf`
thay tên `BBC_2024.pdf` trong đề bài. Không có bằng chứng đã xử lý một doanh nghiệp BBC.

Kết quả chính: hai PDF scan được discovery/extraction thực tế, mỗi PDF có204
canonical observations, trong đó48/30 có canonical mapping. Sáu chỉ tiêu chính/PDF
được M4 truy xuất;24/24 observations được chọn khớp PDF độc lập. Hai metric2025
computed; hai metric2024 blocked accounting basis. Đây là coverage được kiểm tra,
không phải accuracy toàn báo cáo hoặc financial facts đã verified.

## A. Document Inventory và preflight

| File | Doanh nghiệp / ticker có nguồn | Báo cáo / kỳ / scope | Pages / text layer | Primary statements |
| --- | --- | --- | --- | --- |
| BCC_2025.pdf | Công ty Cổ phần Xi măng Bỉm Sơn; BCC tại PDFp9 | Đã kiểm toán, năm kết thúc31/12/2025; riêng, bìap1 | 30;0 ký tự, scan | B01p5–6;B02p7;B03p8;B09 từp9 |
| BCC_2024.pdf | Cùng tên pháp nhân; BCC tại PDFp13 | Đã kiểm toán, năm kết thúc31/12/2024; hợp nhất, bìap3 | 41;0 ký tự, scan | B01p9–10;B02p11;B03p12;B09 từp13 |

Mã doanh nghiệp trong canonical là identity theo tên pháp nhân đã đọc, không
lấy từ filename; hai document dùng cùng company, khác PDF hash và snapshot UUID.
Ticker được xác minh sau preflight ở thuyết minh, không suy từ tên BCC.
Đơn vị primary statements: VND, scale1. B01 so sánh số cuối năm với số đầu năm;
B02/B03 so sánh năm báo cáo với năm trước. Riêng2024 trong PDF2025 không gộp với
hợp nhất2024 trong PDF2024, dù doanh thu thuần có cùng giá trị.

Git main/origin tại baseline khớp; local `web/next-env.d.ts` được giữ ngoài stage.
Không có dataset/artifacts/secrets trong index, ngoại trừ placeholder mẫu đã có.
Không sửa PDF, raw OCR, accepted BBS snapshots hoặc ledger.

| Component | Generic / BBS-dependent | Evidence | Impact |
| --- | --- | --- | --- |
| PDF ingestion | Generic | `gemini_ingestion.load_pages`, `DocumentStore`; content hash, page identity, configured storage | CLI dùng SHA-PDF, Web document dùng UUID; source PDF hash được giữ riêng |
| Discovery | Generic; expensive trên scan | `discover_financial_pages`: text classification hoặc một Vision request/trang | 71 trang vượt cap60 trước extraction; wrapper giữ partial và ưu tiên primary forms |
| Extraction | Generic; gap duplicate positions | `extract_financial_page`, validator; B02/2024 tách ordinal/label cùng cell | Thêm diagnostic và hướng dẫn prompt; một recovery, không ghép cell bằng suy đoán |
| Context resolver | Generic, trước thiếu relative periods/title scope | `context_resolution`, `column_period_evidence`, raw quality projection | Resolve bằng ngày hiện trên cùng trang; không filename year/default scope |
| Item mapping | Generic catalog, alias coverage hẹp | `ITEM_CATALOG`, exact statement/code; nhãn có công thức ở PDF2024 | Thêm6 aliases có nguồn và numeric ordinal normalization giới hạn |
| Canonical adapter | Generic; thiếu role preparation | `fact_from_m2` trước không copy semantic role cho core mappings | Copy role approved khi canonical/statement/source code khớp catalog; không map item mới |
| EF-EG builder | Generic | `build_graph`, `validate_graph`; identity có document/snapshot | Không cần sửa builder/schema; không phát sinh cross-document edges |
| Financial Tools | Generic; có accounting gates | `SnapshotCatalog`, `FinancialRetrievalTools`, `FinancialCalculator` |2025 tính được;2024 giữ blocked vì chưa có basis review phù hợp |

Tìm `BBS/bbs` trong `src`: hai reference tới mẫu nguồn ở arithmetic/relationship
rules, một comment Specialist và strata của extraction pilot. Không thấy branch
chọn công ty BBS hoặc đường dẫn BBS cố định trong ingestion→M4 runtime.
Các evaluator/demo BBS cố định là tooling cho accepted dataset, không dùng để
bổ sung BCC. Không cần thêm agent, relation hoặc thay pipeline.

## B. Pipeline Execution

Chạy production functions `discover_financial_pages` và `process_financial_pdf`,
sau đó adapter/graph/M4 hiện hành; không gọi HTTP Web hoặc tạo Web document.
Runner mới chỉ composition nghiên cứu, dùng Gateway/schema/cache/quota hiện tại.
Model `gemini-3.5-flash-lite`, một credential đang cấu hình, SDK attempts1,
không rotation. Durable task cap60 gồm retry/recovery, có test restart cap.
Preflight dự kiến30 discovery + tối đa16 extraction; thực tế40 provider attempts.

| BCC2025 stage | Status | Input → output | Time(s) | Gemini attempts |
| --- | --- | --- | ---: | ---: |
| Discovery | PARTIAL |30 pages inventoried;15 classified:4 primary/7 notes/4 other;15 deferred |92,046 wall /74,078 provider |15 |
| Extraction | COMPLETE primary |p5–8;4 payloads sau một B03 HTTP503 recovery;204 links |78,829 initial wall;20,016 recovery provider |4+1 |
| Normalization | COMPLETE with limitations |204 observations:48 usable/148 caveat/8 insufficient |3,593 offline replay |0 |
| Canonical Facts | COMPLETE representation |204 facts;48 mapped,156 unmapped |3,672 chung M3 |0 |
| EF-EG | VALID structurally |774 nodes/3.820 edges; thêm2 metric →776/3.824 |Chung M3; không đo riêng |0 |
| M4 Tools |6 facts found;2 computed |Gross Margin10,01%;Debt-to-Assets42,07% |10,016 chung audit/readiness |0 |

| BCC2024 stage | Status | Input → output | Time(s) | Gemini attempts |
| --- | --- | --- | ---: | ---: |
| Discovery | PARTIAL |41 pages inventoried;14 classified:4 primary/3 notes/7 other;1 HTTP503 và26 deferred |70,812 wall /56,673 provider |15 |
| Extraction | COMPLETE primary |p9–12;B02 initial duplicate positions; một structural recovery;204 links |99,625 initial wall;16,187 recovery provider |4+1 |
| Normalization | COMPLETE with limitations |204 observations:30 usable/166 caveat/8 insufficient |5,437 offline replay |0 |
| Canonical Facts | COMPLETE representation |204 facts;30 mapped,174 unmapped |4,813 chung M3 |0 |
| EF-EG | VALID structurally |795 nodes/4.245 edges; thêm2 metric →797/4.249 |Chung M3; không đo riêng |0 |
| M4 Tools |6 facts found;2 blocked |Accounting basis thiếu; không bỏ gate để tính |12,282 chung audit/readiness |0 |

Time M3 gồm canonical/document adapters, graph/validation và ghi artifacts; time
audit gồm controlled comparisons, graph metrics và M4. Không cộng các cột này
thành latency end-to-end; phiên có gián đoạn phát triển/review và offline replay.
Provider time tổng331,780s;known tokens105.149 (2025:49.305;2024:55.844),2 attempts
HTTP503 không có usage. Không tuyên bố tổng tokens chính xác hoặc chi phí billing.
Discovery chưa toàn bộ notes; uncertain pages vẫn selected/deferred trong inventory,
không bị coi như other. Không chọn primary pages thủ công cho extraction.

## C. Financial Audit và M4 readiness

Codex đọc ảnh render từ PDF gốc trước khi so pipeline, không dùng output Gemini
làm reference duy nhất.12 observations/PDF:6 chỉ tiêu ×2 cột. VND/scale1;
B01 current/prior dưới đây là31/12 và01/01 của năm trên bìa, B02/B03 là năm/năm trước.
Tên chỉ tiêu, form type, page, company/document/snapshot và selectors được đối chiếu.
Scope2025 được xác nhận từ bìa và bind bằng `ReportingScopeReview`, native fact
vẫn null;2024 native scope consolidated từ tiêu đề rõ ràng. Không điền scope vào
facts từ metadata để ép compatibility.

| PDF / chỉ tiêu | PDF current | Pipeline current | PDF comparative | Pipeline comparative | PDF page |
| --- | ---: | ---: | ---: | ---: | ---: |
|2025 tổng tài sản |3.275.086.920.922 |3.275.086.920.922 |3.259.760.193.795 |3.259.760.193.795 |5 |
|2025 nợ phải trả |1.377.855.526.955 |1.377.855.526.955 |1.409.664.731.646 |1.409.664.731.646 |6 |
|2025 doanh thu thuần |3.696.241.245.507 |3.696.241.245.507 |3.487.978.470.438 |3.487.978.470.438 |7 |
|2025 lợi nhuận gộp |369.838.783.346 |369.838.783.346 |306.759.698.803 |306.759.698.803 |7 |
|2025 lợi nhuận sau thuế |47.135.931.818 |47.135.931.818 |3.606.610.533 |3.606.610.533 |7 |
|2025 CFO |314.097.335.438 |314.097.335.438 |201.870.668.494 |201.870.668.494 |8 |
|2024 tổng tài sản |3.412.371.648.825 |3.412.371.648.825 |3.656.713.441.407 |3.656.713.441.407 |9 |
|2024 nợ phải trả |1.635.582.933.110 |1.635.582.933.110 |1.871.791.299.592 |1.871.791.299.592 |10 |
|2024 doanh thu thuần |3.487.978.470.438 |3.487.978.470.438 |3.081.365.372.469 |3.081.365.372.469 |11 |
|2024 lợi nhuận gộp |300.372.359.617 |300.372.359.617 |108.943.170.265 |108.943.170.265 |11 |
|2024 lỗ sau thuế |(8.133.426.100) |−8.133.426.100 |(233.536.479.368) |−233.536.479.368 |11 |
|2024 CFO |202.642.595.052 |202.642.595.052 |28.673.341.455 |28.673.341.455 |12 |

Sai lệch số học24/24:0; label/period/unit/page24/24 khớp.24 source reviews
`value_row_verified` có exact row/header/value selectors và PDF/render binding,
không phải independent human gold hoặc cell geometry verified. Precision/correctness
trên tập đã kiểm tra:24/24=100%; không suy rộng sang408 observations hoặc71 trang.
Sáu blank/dash observations/PDF vẫn null, không trở thành zero.

| Chỉ tiêu | BCC2025 | BCC2024 |
| --- | --- | --- |
| Tổng tài sản | Available with caveats | Available with caveats |
| Nợ phải trả | Available with caveats | Available with caveats |
| Doanh thu thuần | Available with caveats | Available with caveats |
| Lợi nhuận gộp | Available with caveats | Available with caveats |
| Lợi nhuận sau thuế | Available with caveats | Available with caveats; giữ dấu âm |
| CFO | Available with caveats | Available with caveats |
| Gross Margin | Available with caveats;computed10,01% | Blocked by context/scope/policy:basis |
| Debt-to-Assets | Available with caveats;computed42,07% | Blocked by context/scope/policy:basis |

Hai metric2025 dùng approved Decimal formula và original observations cùng snapshot;
không tính từ reference spreadsheet. Basis review2025 đối chiếu PDFp9 (VAS/TT200)
vàp10 (dồn tích/giá gốc). PDF2024p9–13 nêu TT202; p14 nêu VAS/chế độ kế toán/giá gốc,
nhưng chưa xác lập controlled record phù hợp enum `VAS/TT200/accrual-historical-cost`.
Earliest failing gate2024 là accounting basis/closure, sau khi đủ operands và
source reviews. Không gán enum bằng suy luận, không thêm basis policy mới trong GEN-01.
`found`, graph valid và calculator computed đều không đổi `financial_fact_verified=False`.

## D. Generalization Findings và fixes

Không phát hiện BBS-specific branch phải xóa. Các lỗi là coverage/preparation chung:

1. Relative column periods: narrow calendar-year rule từ một explicit date/year
   trên cùng trang, giữ raw header và provenance. Missing/conflicting/non-calendar
   context vẫn unresolved. Dùng chung cho mapped links và raw evidence để tránh
   conflict giả khi hai cột đều bị gán missing period.
2. Exact consolidated/separate primary titles được resolver nhận; scope explicit
   truyền vào normalized fact. Title không có scope vẫn null; cover review là overlay.
3. Sáu alias có bằng chứng PDF2024p9–12: tổng tài sản kèm công thức, `C. Nợ phải trả`,
   doanh thu thuần/gross profit rút gọn, lỗ sau thuế và tiền cuối năm kèm công thức.
   Numeric ordinal chỉ normalize khi có source code. Roman subtotal giữ gate:
   regression phát hiện scope mở rộng ban đầu làm BBS410 cạnh tranh400; đã thu hẹp,
   final BBS32 mapped links không đổi. Không parse/evaluate công thức in trong label.
4. Duplicate positions có page diagnostic; prompt yêu cầu ordinal+label trong một
   cell duy nhất. Giữ initial payload lỗi, không tự sửa/merge dữ liệu; một fresh
   recovery B02/2024 đúng cấu trúc và reference24/24.
5. Adapter copy approved semantic role từ catalog cho existing M2 mapping có
   canonical/statement/source code khớp. Không suy role từ company, label mới hoặc
   missing mapping; không thêm financial formula.

Graph chỉ giữ `from_source`, `associated_with`, `used_in`; không suy relation từ
Gemini. Combined graph408 facts/1.573 nodes/8.073 edges bằng đúng union hai graph,
không có extra cross-document edges; BBS observations trong catalog mới bằng0.
Company identity chung là có chủ đích vì PDF chứng minh cùng pháp nhân; document,
snapshot, source page và separate/consolidated context vẫn độc lập.

## E. Regression và validation

-6 tests tài chính/budget mới,1 planning test mới; đã quan sát failures trước từng
  nhóm fix (3 ban đầu;2 raw-period/duplicate;1 role;1 subtotal regression).
  Final176 focused PASS gồm6 mới/170 cũ;4 planning tests PASS gồm1 mới/3 cũ.
- BBS2025 cached production replay32 mapped links: cùng canonical/value/context/
  provenance như accepted result,0 changed. BBS saved M4 replay18/18 computed,
  kết quả khớp accepted `M4-03-final`,0 LLM calls; không ghi accepted inputs.
- Integration thực tế: hai scan, fresh Discovery/Extraction, final cache revalidation
  →Canonical→EF-EG→M4,24 PDF comparisons; boundary/isolation và null checks PASS.
- Ruff/lint/format, planning106 tasks và diff check PASS. CI42169755054
  completed/SUCCESS đúng implementation SHA:1.078 Python tests/9 Web smoke PASS,
  gồm typecheck/lint/build; full regression SKIPPED. Commit sau chỉ docs/planning
  và sửa trailing whitespace trong spec; không gán CI implementation cho SHA docs.
- Không chạy full local suite hoặc browser suite. Web không sửa; CI thực hiện
  nhóm kiểm tra hiện hành. Planning checker được mở rộng GEN ID/milestone, giữ
  nguyên dependency/status/spec/link validations.

## F. Limitations và artifacts

P0: không phát hiện trong phạm vi kiểm tra. P1 readiness còn tồn tại: hai metric
2024 blocked accounting basis như trên; không phải missing operands/LLM failure.
Không tự đưa GEN-02 vào thực thi để che blocker. Mapping còn156/174 unmapped
observations; nhiều raw rows vẫn usable with caveats, không trở thành canonical
financial facts đã verified.2025 có malformed numeric tokens/blank rows;2024 có
per-share unit chưa hỗ trợ trong nhãn `(Lỗ) cơ bản trên cổ phiếu`; giữ8 insufficient
observations/PDF. Không thêm aliases/gates ngoài những lỗi đã xác nhận phục vụ scope.

Discovery không phủ toàn bộ thuyết minh, không có OCR geometry/cell verification,
không đo QA/Multi-Agent improvement. Chỉ một doanh nghiệp mới so với BBS baseline,
hai báo cáo khác năm/scope; chưa chứng minh generalization nhiều ngành/layout.
Không M5/M6/M7 trên BCC, không M8, không tối ưu ledger latency.

Artifacts local, ignored, không commit PDF/ảnh/raw/normalized/canonical:

- `artifacts/evidence/GEN-01/manifest.json`, `metadata-reviews.json`,
  `independent-readings.json`, `BCC_2025/`, `BCC_2024/`: metadata/readings/renders gốc.
- `run-01/`: durable cap/requests, initial result; `run-01/recovery/`: recovery riêng,
  không ghi đè initial.40 attempts tổng, budget còn20; không có live call sau đó.
- `normalized-release/`: revalidate cùng PDF/image binding, quality/facts/evidence/
  graph/descriptor. `audit-release/`: controlled reviews, scope overlay, metrics,
  M4 responses, graph/validation và12 PDF comparisons mỗi báo cáo.
- `bbs-ingestion-regression.json`, `bbs-m4-regression.json`,
  `isolation-and-blank-checks.json`, `usage-summary.json`: kết quả thực tế.
- Các folder `normalized-final`, `normalized-v2`, `audit-final`, `audit-v2` là các
  vòng chẩn đoán offline trước sửa; không dùng làm kết quả cuối hoặc ground truth.

Reproduce offline vào folder mới bằng `scripts/run_cross_company_ingestion.py
--manifest <manifest> --replay-from <run-01/recovery> --output <new-output>`, sau đó
`scripts/audit_cross_company_ingestion.py --source <new-output> --readings <readings>
--metadata-reviews <metadata-reviews> --output <new-audit>`. Không dùng `--live` để
replay. Live continuation chỉ reuse durable budget, không reset cap hoặc xoay key.

## G. Next Action

Chờ Owner/Tech Lead giao nhiệm vụ tiếp theo; không tự bắt đầu GEN-02/M8.
