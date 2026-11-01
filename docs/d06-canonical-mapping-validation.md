# D-06 — Canonical mapping và source financial validation

Ngày 01/11/2026, Asia/Bangkok. Baseline main `004957b`, accepted D-05
`401c12a4f5172e186b820252c6bcce9adb47d9df`. Trạng thái **REVIEW**, chờ Tech Lead
nghiệm thu B05/B11 trong phạm vi bên dưới. Main-first; giữ web/next-env.d.ts.

## Nguyên nhân được xác nhận trước sửa

Đã ghi `before.json` và input manifest **trước khi sửa production code**, trên
explicit **D-05/corrected-v1**, không lấy facts/reviews từ D-04 recovery.

| Case | Before | First point / phân loại |
| --- | --- | --- |
| QA09, code310 B01/2024 tại 2024-12-31 | `unavailable`, `canonical_mapping_missing` | `ITEM_CATALOG` thiếu item; nguồn đã có, không phải thiếu period/value |
| QA15, B01/2023 | `insufficient_data`; missing `b01.total_funding`; `source_unconfirmed:b01.total_funding;funding_page_not_in_pilot` | Thiếu catalog440 và registry stale; source funding thực tế đã có |
| Funding decomposition | IDs `b01.liabilities`, `b01.equity` và unavailable flag pilot | Sai canonical references; catalog hiện dùng `b01.total_liabilities`, `b01.total_equity` |

QA09 được đọc trên ảnh original PDF2024 trang8: code310, “I. Nợ ngắn hạn”,
header31/12/2024, **183.476.510.255 VND**, scale1. QA15 original PDF2023 trang5–6:
270=299.356.744.957, 300=192.158.253.057, 400=107.198.491.900,
440=299.356.744.957 VND, cùng reporting date31/12/2023, scale1.
Đây là controlled source reading, không independent human gold.

## Thay đổi trong shared runtime

`accounting/item_mapping.py::ItemRule/map_item_label` dùng catalog version
`financial-item-mapping-v2`: statement, exact source code, source-backed aliases,
semantic role, period types, monetary unit kind; rule/candidate có version ID.
Không company/ticker/year/PDF path trong mapping rules. Exact source readings
được lưu ở evaluation/report riêng. Không map bằng code đơn lẻ hoặc substring.

8 IDs mới, không tạo IDs đồng nghĩa với total assets/liabilities/equity đã có:

| Statement/code | Canonical ID | Vai trò |
| --- | --- | --- |
| B01/100 | b01.current_assets | current assets |
| B01/200 | b01.noncurrent_assets | non-current assets |
| B01/310 | b01.short_term_liabilities | current liabilities |
| B01/440 | b01.total_funding | funding total |
| B02/01 | b02.sales_revenue | gross revenue |
| B02/02 | b02.revenue_deductions | revenue deductions |
| B03/50 | b03.net_cash_flow | net cash flow during period |
| B03/60 | b03.opening_cash | opening cash balance in cash-flow statement |

Các rules mới bắt buộc source code. Normalization giữ dấu tiếng Việt/words,
NFC/case/whitespace, giới hạn punctuation/ordinal. Giữ hierarchy của existing
rules: subtotal code410 “I. Vốn chủ sở hữu” không được coi là total400.
Label thiếu/bất đồng code/statement hoặc nhiều canonical candidates thì abstain.
Legacy label-only API cho catalog cũ vẫn hỗ trợ candidate discovery; automatic
extraction, unified-table linking và reviewed recovery truyền code đã bind nguồn.

`automated_extraction.py::validate_automated_extraction` tiếp tục giữ candidate
identity của conflicting row để duplicate guard chặn cả dòng có vẻ hợp lệ.
Không giữ candidate thành canonical mapping cho dòng conflict. Code sai không
được vượt guard bằng cách biến dòng trùng thành unmapped.

`accounting/arithmetic.py::ARITHMETIC_RULES` sửa funding operands thành total_*
IDs; mở assets decomposition, net revenue decomposition và net cash-flow sum
khi operands thực sự đủ. `relationships.py::RELATIONSHIP_RULES` mở assets=funding,
thêm assets=liabilities+equity và áp as-of guard cho B01. Rule/check có version
`source-arithmetic-v2` hoặc `source-relationship-v2`. Exchange effect vẫn required;
retained earnings vẫn chặn bởi adjustments/distributions. Không tự missing=zero.

`evidence/source_validation.py::evaluate_source_validations` là adapter dùng chung
trên existing canonical contracts; caller truyền descriptor và period tường minh.
Chỉ lấy đúng document/snapshot, không parent fallback. Kiểm exact identities,
source bindings, canonical/label/code/role, quality/extraction conflicts, period,
unit/scale rồi gọi **existing M2 evaluators**; không viết phép tính riêng cho BBS.
Cross-statement endpoint dùng existing source-backed date resolver.

`SourceValidation` trả rule/version, consistent/inconsistent/insufficient/undetermined,
document/snapshot/period, full operand identities/sources/quality, typed exact Decimal
residual và shared M2 check. M2 statuses cũ vẫn giữ trong nested check; chỉ adapter
dịch tên trạng thái theo contract D-06. Unknown scope và page/uncertain anchors
giữ caveats, không thành scope approval hoặc verified facts.

Đây là **direct source arithmetic**, không phải M4 analytical execution. Không
đổi policies/approvals cho gross margin, debt/assets hoặc revenue YoY.

## Snapshot và integrity

Projection cuối **D-06/mapping-v2.1**, parent **D-05/corrected-v1** của từng
document. 910 financial slots giữ identity local, giá trị/unit/period/raw nguồn;
snapshot identity mới và mapping/quality mới. Original responses, five raw overlays,
structural overlays và terminal EPS recovery giữ nguyên. Không ghép recovery2022
D-04 vào D-05/2022. D-06 không có metrics/reviews từ ancestors; preparation-ready0.
Chỉ bảy readings mới cho QA09 và sáu B01/2023 rows được bind SourceReview đúng
snapshot mới. Các facts khác giữ source-unverified/page-level caveats.

Các exploratory outputs riêng không phải checkpoint được nghiệm thu; lượt đầu
đã giúp phát hiện hierarchy/quality regression và lỗi path trong evaluator.
Projection cuối có assertion ngăn downgrade quality của mapped facts cũ.
Không sửa accepted evidence để làm regression PASS.

Ignored artifacts: `artifacts/evidence/D-06-final/` chứa final projection và exact
restart repositories; báo cáo checks cuối ở `artifacts/evidence/D-06-review/`.
Before, coverage theo statement/code, added/unmapped identities, validation operands/
residuals, SourceReviews, retrieval queries, hashes và summary đều ở outputs này.
Không commit dataset/PDF/OCR/ảnh/keys. Zero Gateway/live extraction.

## Giới hạn và nghiệm thu

## Kết quả real-data trước/sau

Catalog **16 → 24 IDs**; đúng **80 financial slots** được mapping thêm,
trong đó73 numeric,11 vẫn quality-blocked (7 null/malformed deductions và4 B03/2022
layout slots). Mapping không đồng nghĩa usable:69/80 slots mới không bị quality
block. Corrected denominator910 giữ nguyên; mapped160→240, unmapped750→670.

| Statement/code | Before mapped | After mapped | Financial slots | Numeric slots |
| --- | ---: | ---: | ---: | ---: |
| B01/100 | 0 | 10 | 10 | 10 |
| B01/200 | 0 | 10 | 10 | 10 |
| B01/310 | 0 | 10 | 10 | 10 |
| B01/440 | 0 | 10 | 10 | 10 |
| B02/01 | 0 | 10 | 10 | 10 |
| B02/02 | 0 | 10 | 10 | 3 |
| B03/50 | 0 | 10 | 10 | 10 |
| B03/60 | 0 | 10 | 10 | 10 |

**QA09 after:** `found`, đúng một fact tại2024-12-31, code310; value/source giữ
đúng như before raw slot. **QA15 after:** cả assets=liabilities+equity và
assets=funding đều `consistent`, exact Decimal residual **0**, từ operands thật.
Không dùng diagnostic residual D-03 thay formal rule.

Citation snapshot cho bảng dưới là **D-06/mapping-v2.1**. Local identity bằng
`sha256:<PDF hash>/page/<page>/link/<link>`; value selector là JSON pointer trong
effective source payload, không phải cell bbox đã xác minh:

| Case/operand | PDF hash | PDF page/link | Value selector |
| --- | --- | --- | --- |
| QA09 B01/310 | f4e696a85c65f33cb1a1fa982dbfc6b3dccb5a227d14084d5f02b0d673f57c54 | 8/2 | /tables/0/cells/8 |
| QA15 B01/270 | 81d8035271a11a7421141dd8a4ce82c8280add30a8f75db35584c30b57d55a9a | 5/52 | /tables/0/cells/133 |
| QA15 B01/300 | 81d8035271a11a7421141dd8a4ce82c8280add30a8f75db35584c30b57d55a9a | 6/0 | /tables/0/cells/3 |
| QA15 B01/400 | 81d8035271a11a7421141dd8a4ce82c8280add30a8f75db35584c30b57d55a9a | 6/24 | /tables/0/cells/63 |
| QA15 B01/440 | 81d8035271a11a7421141dd8a4ce82c8280add30a8f75db35584c30b57d55a9a | 6/44 | /tables/0/cells/113 |

100 checks =10 registered rules ×2 selected periods ×5 filings; **8 distinct
rules thực sự tính với numeric operands**,65 consistent/0 inconsistent/35
insufficient/0 undetermined. Tất cả65 residuals đã tính bằng Decimal đều0.
Không có real inconsistent case trong bounded set; inconsistent được kiểm bằng
synthetic negative controls, không suy nguồn thật luôn đúng.

| Filing | Consistent | Insufficient | B01 assets=L+E / assets=funding (current và opening) | Asset / funding decomposition (hai kỳ) |
| --- | ---: | ---: | --- | --- |
| 2021 | 14 | 6 | consistent, residual0 /0 | consistent, residual0 /0 |
| 2022 | 11 | 9 | consistent, residual0 /0 | consistent, residual0 /0 |
| 2023 | 14 | 6 | consistent, residual0 /0 | consistent, residual0 /0 |
| 2024 | 13 | 7 | consistent, residual0 /0 | consistent, residual0 /0 |
| 2025 | 13 | 7 | consistent, residual0 /0 | consistent, residual0 /0 |

| Rule | Consistent | Insufficient | Exact blocker / phạm vi |
| --- | ---: | ---: | --- |
| b01.assets_liabilities_equity | 10 | 0 | Cùng document/snapshot/date/unit/scale, scope caveat giữ nguyên |
| b01.balance_identity | 10 | 0 | Dùng440 thật; stale pilot flag đã bỏ |
| b01.total_assets | 10 | 0 | 100+200=270 |
| b01.total_funding | 10 | 0 | 300+400=440, đúng total_* IDs |
| b02.gross_profit | 10 | 0 | Existing source subtraction |
| b02.net_revenue | 3 | 7 | 2021 comparative2020,2022 current2022,2023 comparative2022 có numeric deductions; còn lại `value_unresolved:b02.revenue_deductions`, giữ quality reasons |
| b03.net_cash_flow | 8 | 2 | D-05/2022 có `table_position_conflict`; không lấy recovery D-04 thay thế |
| b01_b03.closing_cash | 4 | 6 | 2022 current quality-blocked;5 opening B01 dates không có cùng endpoint B03 closing, không shift năm |
| b03.cash_reconciliation | 0 | 10 | Missing `b03.exchange_effect`, `catalog_missing:b03.exchange_effect;missing_is_not_zero`;2022 thêm layout blocker |
| b01_b02.retained_earnings | 0 | 10 | Missing retained-earnings mapping và `adjustments_and_distributions_missing;no_direct_equality` |

Citations B01 current: cùng snapshot D-06/mapping-v2.1; mỗi ô là
`code:page/link:value-selector`. Opening operands có identities riêng trong JSON.

| Filing / PDF SHA256 | Operand citations |
| --- | --- |
| 2021 / bcf81efa8b41b7dc5221ce6cd12b7a62bdbf97ae52983c1e7ae58789e2740353 | 270:6/link/48:/tables/0/cells/123; 300:7/link/0:/tables/0/cells/3; 400:7/link/24:/tables/0/cells/63; 440:7/link/44:/tables/0/cells/113 |
| 2022 / 480854b56c27737c9327e3f7650f8f6fde84fbcaab552b83dbbe72431c9da0ee | 270:5/link/50:/tables/0/cells/128; 300:6/link/0:/tables/0/cells/3; 400:6/link/24:/tables/0/cells/63; 440:6/link/44:/tables/0/cells/113 |
| 2023 / 81d8035271a11a7421141dd8a4ce82c8280add30a8f75db35584c30b57d55a9a | 270:5/link/52:/tables/0/cells/133; 300:6/link/0:/tables/0/cells/3; 400:6/link/24:/tables/0/cells/63; 440:6/link/44:/tables/0/cells/113 |
| 2024 / f4e696a85c65f33cb1a1fa982dbfc6b3dccb5a227d14084d5f02b0d673f57c54 | 270:7/link/48:/tables/0/cells/123; 300:8/link/0:/tables/0/cells/3; 400:8/link/20:/tables/0/cells/53; 440:8/link/40:/tables/0/cells/103 |
| 2025 / 6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1 | 270:5/link/40:/tables/0/cells/103; 300:6/link/0:/tables/0/cells/3; 400:6/link/20:/tables/0/cells/53; 440:6/link/40:/tables/0/cells/103 |

Full exact operands, raw values, document hashes, source image identities,
period/type/unit/scale, quality/source caveats và Decimal residual nằm trong
`D-06-review/validation.json`; không chỉ có aggregate PASS. B01 current/opening
không được ghép với nhau. Deductions2021 current raw `_`,2022 comparative raw `-.`
giữ malformed/null; blank/dash các filing sau cũng không trở thành0.

Còn **670 slots/71 statement-code pairs** unmapped: B01=360/39 (chi tiết assets,
liabilities, capital/retained earnings và hierarchy410); B02=118/12 (operating/
financial expenses, taxes, EPS70); B03=192/20 (chi tiết adjustments/cash receipts/
payments). Đây chủ yếu là bounded catalog gaps, không bị gọi là thiếu dữ liệu PDF.
Danh sách labels/codes/identities nằm trong `unmapped.json`; không mở taxonomy100%.

## Regression, generic tests và hashes

Local **322 focused PASS**, gồm30 D-06 generic cases, existing mapping/arithmetic/
relationships/extraction/quality/recovery, D-05 và M3/D-02/D-04 contracts. Hai
synthetic documents độc lập chạy balance cả consistent và deliberate inconsistent;
same code/different statement, aliases, ambiguity, valid unmapped, missing funding,
period/snapshot/document mismatch, unit/scale, null, duplicates, deduction sign,
valid/invalid B03 relation, unknown scope, quality/source conflicts và hierarchy
410/400 đều được kiểm. Không full unit/frontend suite.

Real accepted regressions: **15/15 baseline**, **3/3 recovery**, execution eligible0;
graph exact,15 baseline+3 recovery lineages exact,36 cross-year pairs exact,
1.177 accepted exact fact lookups và29 existing queries exact. Lượt final checks
reuse bằng chứng regression này sau khi xác nhận input hashes không đổi; không
chạy lại catalog/lineage regression đã PASS chỉ để đổi output folder.

Replay riêng29 queries trên D-06:23 found/5 ambiguous/1 not_found. Q25 trước là
mapping gap, nay ambiguous vì query không chọn kỳ và có hai310 candidates; QA09
có period selector nên found1. Missing snapshot không parent fallback. Q07/2022
vẫn có quality caveat/blocker từ D-05; D-04 recovery là explicit alternative.
Giữ D-05 corrected910,10 EPS VND/share,5 raw corrections và terminal coverage
`covered`. Không tự rebind metric readiness/reviews từ ancestor.

**2.506 protected input hashes trước=sau**, gồm accepted evidence/raw scope và web
local; projection riêng cũng được hash trước/sau lượt final validation. Machine
manifests: `hashes-before.json`, `hashes-after.json`, `projection-hashes.json`.
SHA256 input manifest: `5f7f1651df3210e3012cec3346f27c7722362589b07eb8416e0a18a72daa7752`.
SHA256 manifest26 projection files: `0c810ad8dd38589f85643e132e00641a3a07c51fcb02cb4b3a380e90c9aa8c8b`.
Ruff toàn repository, planning checker và diff check chạy trước bàn giao.

Tái đánh giá final persisted projection, dùng output mới; không gọi Gateway hoặc
ghi lại projection/accepted inputs:

```powershell
.venv/Scripts/python.exe scripts/evaluate_d06_validation.py --output artifacts/evidence/D-06-reproduce --from-projection artifacts/evidence/D-06-final
.venv/Scripts/python.exe -m pytest tests/unit/test_d06_validation.py -q
```

Before lịch sử nằm trong `before.json`, được capture trên baseline004957b trước
runtime fix; chạy `--before` trên code mới không tái tạo registry stale của baseline.

## Giới hạn và nghiệm thu

Chỉ mở rộng tám chỉ tiêu/rules hữu ích, không toàn taxonomy. Không kết luận
full-PDF accuracy, generalization accuracy trên doanh nghiệp thật khác hoặc
restatement consistency từ cân số. Các template/code/label chưa hỗ trợ phải giữ
unresolved; cần source review để mở thêm rules. Synthetic documents chỉ chứng minh
generic execution/guards. Reporting scope, cross-year approvals, EPS semantic
restatement, Web bridge và M4–M7 giữ ngoài phạm vi.

**Next action duy nhất:** Tech Lead independent review D-06 và disposition B05/B11.
