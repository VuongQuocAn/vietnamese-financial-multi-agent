# D-01 — Canonical coverage nhiều năm và analytical readiness

Đánh giá dữ liệu thật ngày 30/10/2026 (Asia/Bangkok); phạm vi năm original filings
BBS 2021–2025, không executor hoặc chatbot trả lời bằng LLM. Trạng thái triển khai
và evidence cuối cùng tại [D-01](../planning/tasks/D/D-01.md).

## Cách chạy và provenance

`scripts/run_d01_coverage.py` dùng lại full-page financial discovery, page-level
Gemini extraction, M2 normalization/quality và CanonicalFactRepository hiện có.
Raw PDF/OCR không thay đổi; OCR cũ chưa có binding đủ mạnh với PDF hiện tại nên
không dùng làm nguồn numeric extraction. Discovery không lấy page ranges từ filing
2025. B09 được inventory, không yêu cầu extraction toàn bộ thuyết minh.
Nếu discovery lỗi provider, runtime hiện có vẫn đọc trang đó theo fallback; payload
thuyết minh phát sinh được giữ ở extraction gốc. Canonical projection đánh giá chỉ
lấy B01/B02/B03, ghi riêng excluded non-primary pages, không trộn bảng B09 vào số
đếm mapped/unmapped của các báo cáo chính.

```powershell
$env:GEMINI_API_KEY_FILE = 'src/api/api_key/api_gemini.txt'
.venv/Scripts/python.exe scripts/run_d01_coverage.py --live
.venv/Scripts/python.exe scripts/evaluate_d01_coverage.py --output artifacts/evidence/D-01/evaluation
```

Mặc định runner chỉ kiểm kê; `--live` là opt-in theo ủy quyền D-01. Gateway/key pool
hiện có giới hạn quota/rotation, ghi telemetry không secrets. Checkpoint từng trang
giữ provider failures; resume reuse responses và xác minh PDF/image identity, không
retry vô hạn. Filing 2025 reuse W-07 fresh-storage sau khi đối chiếu original PDF
SHA-256 và từng ảnh render, giữ runtime identity của cache. Artifacts lớn, dữ liệu,
metadata bindings và visual references nằm local trong ignored storage.
Evaluation offline hỗ trợ `--resume`; projection đã lưu phải khớp trước khi reuse.
Lượt đầu gặp Windows `WinError 5` tại atomic replace repository 2022. Runner đánh
giá thêm đúng một local retry cho lỗi này, không sửa core persistence, không retry
provider; phần đã persist được reuse qua repository idempotence. Những lỗi khác
hoặc lỗi ghi file lặp lại vẫn được trả về. Không gọi lại extraction/Gemini vì lỗi này.

`evaluate_d01_coverage.py` tạo normalized-v2 từ source-bound records qua M2/M3
adapters; không sửa facts cũ. Mapping catalog bổ sung đúng source labels/code 300
(liabilities), 400 (equity), alias ordinal 16 cho profit after tax của filing 2021.
Code kiểm tra source code như trước, không map chỉ bằng mã số. Semantic roles nhỏ
dựa trên các reference formula definitions M3-05: revenue, gross_profit, assets,
liabilities. Không mở rộng taxonomy hoặc nới compatibility engine.

## Source-backed metadata policy

Controlled visual reading trang thuyết minh đầu của từng PDF cho thấy cùng mã đăng
ký doanh nghiệp và tên reporting entity. Binding dùng mã đăng ký được in trong
đúng tài liệu, namespace `vn-business-registration`, giữ document SHA-256, PDF page,
render hash, source text và policy `D-01/source-registration-v1`. Trang nguồn lần
lượt 2021:10, 2022:9, 2023:9, 2024:11, 2025:9. Không gộp từ folder/filename hoặc
chỉ vì trùng tên; không tuyên bố đã xác minh cơ quan đăng ký bên ngoài. Mã cổ phiếu
có in trong thuyết minh, không suy từ folder BBS. Trang 9 của filing 2025 xoay 180°;
visual review dùng bản render xoay cho dễ đọc, cache runtime vẫn giữ ảnh gốc.

Chưa có tiêu đề explicit “riêng”/“hợp nhất” đủ để bind scope. Không mặc định separate.
Company binding vào adapter và role vào projection mới; missing scope, source
uncertainty và quality issues được giữ. Không xóa provenance issues để ép compatible.

## Phân biệt các kết quả

- Engineering: targeted tests, repository restart, source binding, typed retrieval,
  graph/lineage structural checks; không phải financial accuracy.
- Data coverage: raw observations, mapped/unmapped, numeric/context completeness
  được đếm riêng. Mapped ID không tự chứng minh period/unit/value đã đầy đủ.
- Financial accuracy: 48 ô tham chiếu cố định từ PDF gốc, đọc trực tiếp qua ảnh,
  trước khi xem outputs 2022–2024. Mỗi filing 12 ô: assets, liabilities, net revenue,
  gross profit, operating/investing cash flow; mỗi item có cả current/comparative.
  Có số âm và exact raw/normalized comparison. Đây là kiểm tra tham chiếu nhỏ do
  implementation agent đọc ảnh, chưa independent human gold hoặc accuracy toàn PDF.
- Analytical usability: 29 fixed queries, các observations không deduplicate,
  metric bindings và blockers. Kết quả computed luôn không có.

## Giới hạn và can thiệp tối thiểu

Ngay cả khi đủ operands/company/roles, scope chưa có nguồn explicit và page-level
anchors vẫn uncertain. Approved compatibility phải giữ undetermined; execution còn
bị chặn vì formula definitions chỉ `reference_example`. Không cần bỏ yêu cầu legal
company ID trong D-01 vì đã có source-backed registration evidence. Can thiệp nhỏ
tiếp theo cần Tech Lead quyết định policy cho unknown scope cùng tài liệu và tiêu
chuẩn xác nhận page/selector provenance; dữ liệu hiện tại không cấp phép tự điền
scope hoặc nâng anchor thành cell-level. Không thêm experimental result thay approved.

B01 cột đầu kỳ in 01/01 của năm hiện tại: giữ nguyên as-of date, không đổi thành
31/12 năm trước để tăng cross-year coverage. Các annual B02/B03 cùng kỳ từ filing
gốc và comparative có thể đối chiếu numeric values nhưng chưa kết luận consistency
khi scope thiếu. Difference không tự bị gọi OCR error hoặc restatement.

## Kết quả real run

Nguồn: ignored `artifacts/evidence/D-01/evaluation/summary.json`, repositories theo
năm, discovery-coverage, retrieval, metrics, lineages, cross-year và spot-checks.
Evaluation hoàn tất sau khi sửa lời gọi validate_graph thiếu catalog và resume;
các lần đánh giá offline không tạo thêm API calls hoặc sửa extraction.

| Filing | PDF/OCR pages | B01 / B02 / B03 PDF pages | B09 pages | Primary observations | Mapped / unmapped | Numeric |
| --- | --- | --- | ---: | ---: | --- | ---: |
| 2021 | 28 / 28 | 6–7 / 8 / 9 | 19 | 223 | 37 / 186 | 191 |
| 2022 | 26 / 26 | 5–6 / 7 / 8 | 18 | 196 | 32 / 164 | 182 |
| 2023 | 29 / 29 | 5–6 / 7 / 8 | 21 | 198 | 32 / 166 | 179 |
| 2024 | 26 / 26 | 7–8 / 9 / 10 | 16 | 186 | 32 / 154 | 166 |
| 2025 | 24 / 24 | 5–6 / 7 / 8 | 16 | 178 | 32 / 146 | 163 |
| Total | 133 / 133 | 20 primary pages | 90 | 981 | 165 / 816 | 881 |

Discovery mới 109 trang của bốn PDF; 16 primary pages extraction mới và bốn B09
fallback pages (2022:11,18; 2024:21,24). Filing 2025 reuse 24-page inventory và
bốn extraction pages. B09 counts dùng extraction reconciliation tại bốn trang
discovery provider failure, không sửa cache discovery cũ; các trang other vẫn giữ
classification riêng. Không phải trích xuất đủ 90 trang B09.

129 Gemini Gateway attempts, model `gemini-3.5-flash-lite`: 125 success,
4 provider_unavailable; 260,593 provider-reported known tokens, không có usage đầy
đủ của bốn lỗi. Không suy monetary cost từ token count. Sau extraction: zero API
calls trong projection/evaluation/restart/resume.

981 source observations được lưu CanonicalFinancialFact repository và exact
retrieval 981/981, restart exact. Trong 881 numeric observations có 161 mapped và
720 unmapped; 160 mapped observations có period. Năm mapped slots thừa của 2021
đến từ header mô tả “Thuyết số” do extractor trả về, period unresolved; giữ raw và
quality blocked, không xem chúng là current/comparative financial values.
Không gọi mọi unmapped slot hoặc canonical ID đã gán là verified financial fact.
981 source-backed company bindings, 41 semantic-role annotations, zero scope bindings.
Graph 3,599 nodes / 18,848 edges, 22,447 structural valid, zero invalid/unresolved/
orphan; structural valid không nâng provenance hoặc quality.

| Readiness | Baseline M3-05 | D-01 |
| --- | --- | --- |
| Cùng sáu metrics của hai attempts 2025 | 4 complete / 2 incomplete; 6 undetermined | 6 complete; 6 undetermined |
| Năm primary filings, ba metrics/filing | 2021–2024 chưa canonical | 15 complete bindings / 15 complete lineages; 30/30 roles resolve |
| Approved compatibility | 0 compatible | 0 compatible / 0 incompatible / 15 undetermined |
| Computed results | Không | Không |
| Revenue trend | Chưa đủ original filings | 5/5 current-period original-filing observations kèm citations |
| Assets/liabilities/equity readiness | Liabilities mapping thiếu | Mỗi năm đủ 3/3 current-period numeric operands, chưa thực thi relationship |

Missing company và semantic roles đã được xử lý trong projection mới; liabilities
không còn thiếu operand. Cả 15 metrics vẫn có `missing_reporting_scope`,
`source_reference_uncertain`, `unresolved_operand_context`. Blocker là source
context/provenance và approved compatibility policy, cộng execution policy chỉ
reference examples; không còn là legal identity hoặc operand mapping gap.
15 lineage arithmetic preparations đủ inputs, analytical interpretation undetermined,
calculation blocked. Sáu matched metrics vẫn giữ cả quality context của storage
attempt cũ; không biến insufficient thành usable.

Cross-year: 36 original/comparative pairs cùng canonical item và annual period,
từ nhiều filings; 36/36 numeric equal, 36 undetermined vì missing scope. Không
deduplicate hoặc chọn latest. B01 opening/closing dates khác nhau không nằm trong
36 same-period pairs; không tự tạo date equivalence hoặc chứng nhận restatement.

| Fixed retrieval evaluation (29 queries) | Count |
| --- | ---: |
| Answer-data available, có caveats/citations | 22 |
| Answer-data partial | 0 |
| Quality blocked | 1 |
| Ambiguous, giữ nhiều observations/snapshots | 4 |
| Missing mapping | 1 |
| Missing canonical extraction | 0 |
| Source limitations / requested snapshot absent | 1 |

23 found / 4 ambiguous / 1 unavailable / 1 not_found. Q07 operating cash flow 2022
có đúng sampled value nhưng vẫn bị M2 blocked bởi `table_position_conflict`; không
override chỉ vì numeric spot check khớp. Can thiệp tối thiểu: một page-8 full-table
re-extraction qua Gateway hiện có vào attempt mới, kiểm tra dimensions/header/cells,
giữ attempt lỗi và so sánh; không cần chạy lại toàn bộ PDF hoặc các năm khác.

Financial spot checks: 48 numeric cells correct / 0 incorrect / 0 uncertain;
48 raw-label occurrences correct (24 distinct sampled rows). Cả current/comparative,
dấu âm và period binding khớp mẫu ảnh PDF. 833 numeric observations còn lại của
primary scope **NOT CHECKED trong D-01**, toàn PDF và independent human gold
**NOT VERIFIED**; không suy tỷ lệ accuracy toàn dataset từ 48 ô này.

## Engineering và source integrity

119 targeted/core regression tests PASS: extraction/item mapping, canonical contracts/
compatibility, retrieval, metrics, lineage và D-01 period/comparison/retry controls.
Ruff lint/format toàn repository PASS (312 files); planning checker 94 tasks PASS;
git diff --check PASS. Không frontend/browser local hoặc full unit regression.
Implementation `0f2ca6124cd4a4c994f38c32557d3f9b88f42e7c` đã push trực tiếp main.
[CI41064083725](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41064083725)
completed/SUCCESS đúng implementation SHA; Python 3.12 và Web smoke đều SUCCESS,
các steps đã xác minh. Không gán CI này cho documentation checkpoint sau đó.

139 task input hashes before=after; 172 accepted M3-07 input hashes đối chiếu vẫn
khớp, tổng union 173 files bao gồm unrelated local web/next-env.d.ts. Không ghi đè
raw PDF/OCR, accepted artifacts hoặc facts cũ. PDF 2021 hiện là BBS_2021.pdf,
hash trùng BB2_2021.pdf trong inventory cũ; Codex không đổi tên nguồn.

| Filing | SHA-256 trước = sau |
| --- | --- |
| 2021 | bcf81efa8b41b7dc5221ce6cd12b7a62bdbf97ae52983c1e7ae58789e2740353 |
| 2022 | 480854b56c27737c9327e3f7650f8f6fde84fbcaab552b83dbbe72431c9da0ee |
| 2023 | 81d8035271a11a7421141dd8a4ce82c8280add30a8f75db35584c30b57d55a9a |
| 2024 | f4e696a85c65f33cb1a1fa982dbfc6b3dccb5a227d14084d5f02b0d673f57c54 |
| 2025 | 6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1 |

## Các mapping được kiểm tra trong D-01

| Canonical item | Mã nguồn | Quyết định |
| --- | --- | --- |
| b01.total_assets | 270 | Reuse mapping được duyệt, kiểm tra lại mẫu original PDF |
| b01.total_liabilities | 300 | Bổ sung từ nhãn C - NỢ PHẢI TRẢ và code tương ứng |
| b01.total_equity | 400 | Bổ sung từ nhãn D - VỐN CHỦ SỞ HỮU, không lấy subtotal 410 |
| b01.cash_equivalents | 110 | Reuse, không gộp với closing cash của B03 |
| b02.net_revenue | 10 | Reuse, giữ current và comparative độc lập |
| b02.gross_profit | 20 | Reuse trong statement B02, phân biệt code 20 B03 |
| b02.profit_after_tax | 60 | Reuse; thêm ordinal 16 có trên original filing 2021 |
| b03.operating_cash_flow | 20 | Reuse trong statement B03 |

Short-term liabilities (310), cash flow opening cash (60 B03), nhiều chi tiết tài
sản/nợ/vốn vẫn không có approved canonical mapping; giữ raw/source/quality và báo
unmapped. Query thiếu mapping dùng candidate key `b01.short_term_liabilities`, có
source code 310 thực tế để xác định inventory gap; không tạo facts với key này.
