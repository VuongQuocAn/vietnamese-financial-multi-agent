# VFB-IMPORT-03 — Full Corpus Import

Ngày16/11/2026 (Asia/Bangkok). **Chấp thuận về mặt chức năng** theo kết quả Codex
báo cáo, người dùng xác nhận ngày16/11/2026. Tracking giữ **REVIEW** chờ
implementation SHA; chưa commit, baseline `2b3c2ab`
cùng local implementation IMPORT01/02/E2E02. Các task trước giữ REVIEW.

## Phạm vi và cách sử dụng

Chỉ đọc `ViFinBench/refined/`, không OCR lại, không đọc Gold Answer để xây evidence,
không gọi Gateway/Gemini và không chạy benchmark600. Dùng adapter, normalization,
repositories, typed EF-EG, SnapshotCatalog, Financial Tools và M5 hiện có.

Runner [validate_vifinbench_json_pipeline.py](../scripts/validate_vifinbench_json_pipeline.py)
hỗ trợ `--all` hoặc `--documents`. Mỗi lần chạy cần output mới, giữ nguyên artifacts
pilot và JSON nguồn. Inventory manifest được ghim trước import và đối chiếu lại
cuối run. Projection suffix tách khỏi snapshot pilot trước đó. Bộ `full-final`
giữ các bundle `vfb-import-03` đã kiểm tra, riêng BCC_2024 dùng
`vfb-import-03-cover-v1` sau sửa cover; manifest/index ghim đúng snapshot từng
filing. Chạy lại đồng nhất trên code mới bằng suffix mới như lệnh dưới.

```powershell
.venv/Scripts/python.exe scripts/validate_vifinbench_json_pipeline.py --all --output artifacts/evidence/VFB-IMPORT-03/new-run --projection-version vfb-import-03-cover-v1
```

Artifacts local ignored: `artifacts/evidence/VFB-IMPORT-03/`. Mỗi bundle có manifest,
canonical-facts, document-evidence, graph, graph-validation, pipeline-probes và summary.
Ở corpus root có source-inventory, catalog-index, summary, coverage.csv và coverage.md.
Không tự activate catalog trong backend mặc định; caller chọn explicit document.

```python
from pathlib import Path
from vietnamese_financial_multi_agent.evidence.json_catalog import load_json_corpus_document
from vietnamese_financial_multi_agent.tools.financial_retrieval import FinancialRetrievalTools
from vietnamese_financial_multi_agent.agents.lite_orchestrator import FinancialLiteOrchestrator

catalog = load_json_corpus_document(
    Path("ViFinBench/refined"),
    Path("artifacts/evidence/VFB-IMPORT-03/full-final"),
    "ADC_2021",
)
tools = FinancialRetrievalTools(catalog)
m5 = FinancialLiteOrchestrator(catalog)
# Dùng descriptor.document_id/snapshot_id và company/period của filing đã chọn.
```

Loader index chỉ chọn bundle trong corpus root, đối chiếu identity với descriptor
và gọi lại `load_json_catalog`; không gộp các filing hoặc cấp phép tính liên tài liệu.
E2E runner hiện có có thể nhận cùng corpus root qua `--bundle-root` khi được giao
live run sau này; runner đó hiện vẫn chỉ có bốn case pilot, chưa phải harness600.

## Định nghĩa coverage và validation

Observation là ô giá trị được pipeline giữ lại, gồm cả ô trống/unresolved. Mapped
là observation có canonical item ID trong catalog hiện có, chưa có nghĩa usable.
Eligible là mapped fact đạt `json_fact_bound`: company, period/type, unit/currency/
scale, numeric value, quality và binding/hash/pointers của nguồn JSON đều hợp lệ.
Các missing/conflict được giữ và thống kê; không đổi ô trống thành zero.

Mỗi filing được persist/reload qua repositories và JSON catalog; đối chiếu payload,
validate graph và zero orphan. Fidelity replay từng text/header/cell/value pointer
và toàn bộ source references. Financial Tools kiểm mọi eligible fact cùng một
negative exclusion probe nếu có. Text/Table lookup giữ citations JSON và `pdf_page=null`.
Dynamic Calculator dùng ratio từ gross profit/net revenue hoặc cash/assets khi
cùng kỳ/unit/scale và mẫu số khác0; không tự đăng ký standard financial metric.

M5 smoke dùng Supervisor lexical và câu hỏi theo vocabulary catalog hiện có,
`use_graph=true`; không lấy câu hỏi/operands từ benchmark. Đây là kiểm nối tools và
graph, chưa đánh giá paraphrase, reasoning, M6/M7 hay độ đúng trả lời E2E toàn corpus.
Lượt đầu dừng ở ADC_2024 vì nhãn nguồn “C. NỢ PHẢI TRẢ” khác nhãn M5 “Tổng nợ phải trả”.
Đã sửa cách tạo câu hỏi smoke; không mở rộng mapping hoặc sửa dữ liệu để qua smoke.
M5 lexical cũng bỏ qua source thiếu kỳ khi câu hỏi có năm, thay vì slice `None`.

Adapter bổ sung fallback cover ở trang2–5 khi trang1 không bind được công ty:
chỉ nhận trang không có bảng, có tên công ty, tiêu đề BCTC tường minh và kỳ đã
resolve; các ứng viên phải cùng company. Không lấy tên từ thuyết minh hay ticker.
BCC_2024 có hai trang Deloitte/chữ ký trước cover thực tại JSON p3; fallback giữ
pointer p3 cho company/kỳ. Mapped facts đủ kỳ26→30, eligible0→30; M5 completed.
Giữ full-v2 và cover-v1 riêng; full-final ghép bundle vào vị trí mới, đối chiếu
byte copies và tái import projection41/41 với code cuối để xác nhận payload không
đổi ở các filing khác. Không chạy lại M5 trên40 bundle không đổi.
Sau khi ghép, process mới nạp qua corpus index cho ADC_2024/BCC_2024/CAG_2025:
3/3 Financial Tools found, JSON-bound, không PDF claim; sai document bị từ chối.
Bằng chứng tại `full-final/corpus-index-probes.json` và
`full-final/projection-equivalence.json`.

## Kết quả thực tế

Lượt bàn giao **full-final**, toàn bộ **41 tài liệu/15 doanh nghiệp/1.488 trang** đã
import và kiểm lại hashes, không sửa JSON nguồn. Có **13.199 Text Evidence,
2.068 Table Evidence, 26.126 observations**, trong đó
21.989 giá trị parse được, 1.270 mapped và
**1.043 facts eligible trên 37/41 filing**.
Financial Tools exact lookups đạt **1.043/1.043**.

EF-EG có **134.073 nodes/518.276 edges**, mọi assessment valid,
zero invalid/unresolved/orphan. Restart payload exact41/41; Text lookup41/41,
Table lookup40/40 tài liệu có bảng. Fidelity gồm 90.597
text/header/cell pointers, 26.126 value pointers và
339.520 source references. Toàn bộ1.488 hashes
được đối chiếu cuối run. Tổng thời gian các document smoke 1107.981s;
đây gồm import/persistence/graph/M4/M5, không phải latency answering hoặc benchmark.

M5 offline: `{'completed': 36, 'partial': 1, 'blocked': 2, 'clarification_required': 2}`; tổng 54 candidate claims chưa verified.
Dynamic Calculator: `{'computed': 31, 'no_eligible_pair': 10}`. Xem nguyên trace tại
`<bundle>/pipeline-probes.json`, kết quả graph tại `<bundle>/graph-validation.json`.
Lượt `full-v1/` chưa hoàn tất được giữ, không tính chung vào coverage cuối.

### Coverage41

Số có kỳ/unit tính trên mọi observations, không chỉ mapped; eligible là giao đủ
điều kiện, không cộng các cột này. [CSV đầy đủ](vfb-import-03-coverage.csv) có thêm
numeric count, kỳ chính xác và phân bố unit/scale theo filing, eligible periods,
mapped exclusions, graph counts và M5 candidates. Bảng dưới giữ counts để dễ đọc.

| Tài liệu | Trang | Text | Table | Obs. | Mapped | Có kỳ | Có unit | Eligible | M5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| ADC_2021 | 33 | 371 | 58 | 754 | 30 | 572 | 750 | 28 | completed |
| ADC_2022 | 33 | 392 | 50 | 672 | 24 | 488 | 668 | 22 | completed |
| ADC_2023 | 34 | 413 | 55 | 616 | 18 | 402 | 604 | 18 | completed |
| ADC_2024 | 32 | 360 | 55 | 595 | 18 | 372 | 583 | 18 | completed |
| ADC_2025 | 42 | 341 | 56 | 182 | 38 | 182 | 182 | 36 | completed |
| ALT_2023 | 47 | 435 | 68 | 254 | 36 | 254 | 228 | 34 | completed |
| ALT_2024 | 47 | 264 | 68 | 254 | 34 | 254 | 110 | 14 | completed |
| ALT_2025 | 44 | 232 | 65 | 248 | 36 | 248 | 142 | 12 | partial |
| AMC_2021 | 34 | 328 | 46 | 779 | 34 | 376 | 767 | 34 | completed |
| AMC_2022 | 35 | 305 | 40 | 719 | 34 | 368 | 703 | 34 | completed |
| AMC_2023 | 33 | 320 | 46 | 764 | 40 | 372 | 750 | 40 | completed |
| AMC_2024 | 34 | 337 | 47 | 857 | 40 | 458 | 834 | 40 | completed |
| AMC_2025 | 35 | 373 | 49 | 868 | 40 | 432 | 841 | 40 | completed |
| AME_2023 | 42 | 271 | 62 | 980 | 46 | 144 | 974 | 24 | completed |
| AME_2024 | 40 | 219 | 48 | 906 | 16 | 488 | 663 | 0 | blocked |
| AME_2025 | 37 | 185 | 51 | 218 | 26 | 218 | 216 | 26 | completed |
| ARM_2023 | 40 | 385 | 47 | 158 | 26 | 158 | 156 | 24 | completed |
| ARM_2024 | 42 | 400 | 50 | 166 | 26 | 166 | 164 | 24 | completed |
| ARM_2025 | 40 | 346 | 54 | 1136 | 22 | 778 | 1105 | 20 | completed |
| ATS_2023 | 32 | 177 | 46 | 78 | 14 | 78 | 0 | 0 | blocked |
| ATS_2024 | 31 | 253 | 43 | 612 | 44 | 554 | 540 | 36 | completed |
| ATS_2025 | 29 | 229 | 39 | 341 | 28 | 148 | 287 | 8 | completed |
| BBS_2023 | 29 | 300 | 43 | 814 | 48 | 602 | 812 | 47 | completed |
| BBS_2024 | 26 | 277 | 35 | 610 | 48 | 396 | 594 | 46 | completed |
| BBS_2025 | 24 | 263 | 35 | 643 | 48 | 442 | 625 | 46 | completed |
| BCC_2021 | 40 | 367 | 53 | 811 | 28 | 164 | 807 | 24 | completed |
| BCC_2022 | 38 | 346 | 52 | 724 | 20 | 356 | 717 | 20 | completed |
| BCC_2023 | 44 | 399 | 51 | 880 | 22 | 152 | 874 | 18 | completed |
| BCC_2024 | 41 | 346 | 53 | 827 | 30 | 510 | 823 | 30 | completed |
| BCC_2025 | 2 | 27 | 0 | 0 | 0 | 0 | 0 | 0 | clarification_required |
| BED_2023 | 40 | 315 | 56 | 833 | 36 | 608 | 819 | 36 | completed |
| BED_2024 | 40 | 312 | 65 | 936 | 36 | 654 | 924 | 36 | completed |
| BED_2025 | 41 | 341 | 64 | 892 | 34 | 670 | 880 | 34 | completed |
| BKC_2023 | 41 | 290 | 51 | 1002 | 22 | 756 | 988 | 20 | completed |
| BKC_2024 | 39 | 275 | 51 | 964 | 24 | 768 | 950 | 21 | completed |
| BKC_2025 | 39 | 321 | 53 | 980 | 22 | 804 | 966 | 20 | completed |
| BPC_2025 | 24 | 244 | 39 | 525 | 44 | 404 | 521 | 43 | completed |
| BTS_2025 | 37 | 327 | 44 | 587 | 22 | 140 | 417 | 10 | completed |
| BTW_2025 | 44 | 427 | 48 | 152 | 32 | 86 | 150 | 18 | completed |
| C69_2025 | 48 | 609 | 76 | 1111 | 40 | 662 | 1105 | 0 | clarification_required |
| CAG_2025 | 35 | 477 | 56 | 678 | 44 | 614 | 670 | 42 | completed |
| **Tổng** | 1.488 | 13.199 | 2.068 | 26.126 | 1.270 | 16.298 | 24.909 | 1.043 | — |

## Hạn chế và readiness

JSON-grounded luôn khác PDF-grounded. Nguồn vẫn có `json_source_not_pdf_verified`,
anchor uncertain, không ảnh/bbox PDF, `pdf_page=null`, `financial_fact_verified=false`.
Graph hợp lệ chỉ xác nhận cấu trúc/reference; source hash đúng chỉ xác nhận fidelity,
không chứng minh OCR/financial accuracy. Không tạo PDF review hoặc metric approval giả.

Catalog chỉ tiêu hữu hạn và matching có kiểm soát; B09, prose, bảng thiếu statement,
ragged/multilevel headers và các quan hệ hàng phức tạp chưa thành financial facts
đủ điều kiện. Text/Table Evidence vẫn giữ đầy đủ nguồn để truy xuất. Company ID từ
cover JSON chưa phải registry ticker/issuer được đối chiếu giữa nhiều năm; không
suy quyền tính liên tài liệu từ ticker hoặc tên thư mục. `missing_pages` chỉ phát
hiện lỗ hổng trong khoảng1..max JSON page, chưa xác nhận đủ số trang PDF gốc.

Các exclusions còn lại sau import:

| Filing | Hạn chế thực tế |
| --- | --- |
| AME_2024 | Thiếu JSON p9–10;16 mapped B01 facts thiếu presentation unit,0eligible. |
| ATS_2023 | 14 mapped facts thiếu unit; chỉ có khai báo đồng tiền ghi sổ ở p13, không suy scale cho bảng. |
| BCC_2025 | Công văn2trang,27 Text Evidence, không bảng/observations; không tạo số liệu từ prose. |
| C69_2025 | 40 mapped facts thiếu company binding; công văn p1 có company field song ngữ, cover p7 tách tên qua nhiều heading, ngoài fallback cover hiện có. Còn6 mapped thiếu kỳ và2 giá trị unresolved. |

Inventory còn thiếu BKC_2025 p38 và C69_2025 p30. Tổng cộng227 mapped facts chưa
eligible; các lý do có thể chồng lấn:96 thiếu unit,60 thiếu kỳ,40 thiếu company,
42 giá trị unresolved và100 bị quality gate chặn. Có694 bảng chưa resolve
statement,21 bảng ragged và2 bảng rỗng (counts issues có thể chồng lấn); tất cả
vẫn giữ Table Evidence, không ép thành facts. ALT_2025 có12eligible và2candidates
nhưng M5 status `partial`; không diễn giải thành một câu trả lời E2E đầy đủ.

**Readiness:** đạt tầng import/lưu trữ/JSON retrieval cho toàn corpus; có thể dùng
bộ bundle/index này để chuẩn bị harness E2E và ghi nhận cả kết quả blocked.
Chưa đủ để cam kết QA coverage600 hoặc financial accuracy toàn corpus. Cần kiểm
E2E có giới hạn ngoài pilot trước khi phê duyệt ngân sách600:37filing có eligible
facts chưa chứng minh LLM tự chọn đúng nguồn/phép toán hoặc M6/M7 trả lời đúng.
Company binding C69 và coverage mapping/context/B09 là hạn chế đã định vị, không
được che bằng cách chuyển trusted company từ tên thư mục hay bỏ QA khỏi mẫu số.

Coverage không dùng Gold, không đo tỷ lệ câu hỏi600 có thể trả lời và không nâng
engineering smoke thành financial accuracy. Khi thiết kế benchmark phải giữ cả
blocked/unsupported trong mẫu số, công bố JSON-grounded riêng; không lọc QA theo
eligible facts rồi gọi đó là kết quả toàn corpus.

## Validation và bàn giao

13tests khác nhau PASS:3corpus controls,3JSON pipeline,3refined import và4M5 Lite;
có kiểm cover sau auditor sheets, provenance và negative cover không phải BCTC.
Các nhóm được chạy lại sau sửa cover; không full regression/browser/CI.
Ruff lint/format, planning checker và `git diff --check` PASS local trước bàn giao.
Nguồn refined và artifacts có ignore rules, không nằm trong Git index; không stage,
commit hoặc push. Runtime fingerprints và baseline đã ghi tại
`artifacts/evidence/VFB-IMPORT-03/implementation.json`; không gán SHA baseline
cho implementation chưa commit. Source hashes/fidelity và projection equivalence
được kiểm trên dữ liệu thật; smoke PASS không chứng nhận chất lượng tài chính.

## Chấp thuận chức năng — 16/11/2026

Người dùng xác nhận: “VFB-IMPORT-03: Chấp thuận về mặt chức năng theo kết quả Codex
báo cáo.” Phạm vi chấp thuận là kết quả import/coverage đã báo cáo; giữ nguyên
exclusions và phân biệt JSON-grounded/PDF-grounded. Đây chưa phải phê duyệt chạy
benchmark600 hoặc nghiệm thu financial accuracy.

Đã đối chiếu lại fingerprints runtime với evidence local: khớp code hiện tại;
summary vẫn41tài liệu/1488trang/1043eligible. Không chạy lại tests/import/API.
Git HEAD vẫn là baseline `2b3c2ab`; implementation chưa commit. Theo quy tắc
nghiệm thu/tracking của repository, giữ REVIEW chờ SHA implementation để đóng
DONE; không dùng SHA baseline làm bằng chứng implementation mới.

**Next action:** chờ Owner giao bước chốt checkpoint Git/implementation SHA.
