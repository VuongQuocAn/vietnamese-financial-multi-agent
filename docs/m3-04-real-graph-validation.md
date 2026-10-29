# M3-04 — Real-artifact graph validation

Kết quả dưới đây là checkpoint ban đầu `5722912`. **CHANGES REQUESTED** vì status
gộp structural với uncertainty/context. Kết quả sửa semantics nằm ở phần
**Review correction** cuối tài liệu; không sửa hoặc diễn giải lại artifact cũ.

Ngày 29/10/2026. Scope chốt trước đánh giá: toàn bộ hai W-07 storage/fresh-storage
attempts BBS_2025 và cả bốn repositories M3-03 final (M1-existing, M1-native,
W07-storage, W07-fresh-storage). Không chọn subset theo kết quả PASS; không extraction.

Không còn canonical-facts.json từ smoke trước trên đĩa tại preflight. Runner dùng
`facts_from_persisted_result()` M3-02 trên quality projections đã persist của cả hai
W-07 attempts; lưu canonical repository mới dưới output ignored, restart và đọc toàn
bộ indexed facts. Đây là materialization deterministic, không replay M1/M2 hoặc
điền company/context. Text/table đọc nguyên records/quarantine đã persist M3-03.

```powershell
.venv/Scripts/python.exe scripts/validate_m3_graph.py --output artifacts/evidence/M3-04/final
```

Output phải là thư mục mới. Graph, assessments, source hashes và chi tiết controls
ở output ignored; không commit dữ liệu canonical/OCR/PDF hoặc đường dẫn cá nhân.

## Structural graph validity

| Mẫu số / metric | Kết quả |
| --- | ---: |
| Canonical facts: hai attempts, mỗi attempt 178 | 356 indexed / 356 |
| Document evidence trong bốn repositories | 99: 92 indexed, 7 quarantine |
| SourceFact nodes | 356 |
| TextEvidence nodes | 81 |
| TableEvidence nodes | 11 |
| EvidenceAnchor nodes | 1299 |
| Tổng nodes / đã validate | 1747 / 1747 |
| from_source edges | 4887 |
| associated_with edges | 2520 |
| Tổng edges / đã validate | 7407 / 7407 |
| Edge valid / invalid / unresolved | 0 / 0 / 7407 |
| Node valid / invalid / unresolved | 0 / 0 / 1747 |
| Orphan indexed nodes | 0 / 1747 |
| Identity collisions/duplicates, source binding conflicts | 0 / 0 |
| Missing record identities ngoài indexed nodes | 7 / 455 input records |
| Graph JSON restart round-trip | Exact |

Typed domain/reference/identity checks không phát hiện known violation trong scope.
Không gọi unresolved là valid: tất cả nguồn uncertain, tất cả records có resolution
issues. 7407/7407 edges giữ cả `source_reference_uncertain` và
`unresolved_record_context`. Zero invalid không có nghĩa evidence đã được xác minh.

## Identity/provenance correctness và association coverage

356/356 indexed facts có ít nhất một exact association; 2520 edges gồm nhiều
context associations cho mỗi observation. 3588 matching-source occurrences trong
các associations đều **page-level**, không phải 3588 cells verified. 1299/1299 unique
anchor nodes page-level; không sinh cell IDs/bbox hoặc dùng page number làm global ID.
Hai W-07 attempts có document IDs/snapshot IDs riêng, không merge vì cùng PDF.
M1-native giữ fingerprint/snapshot export riêng; không ghép với W-07 để tăng coverage.

7 records M1-existing thiếu document binding giữ nguyên quarantine, không có graph
node/anchor/source ID giả. 97 cell references cũ của nhóm quarantine không biến
thành indexed cell-level nodes. Missing source indexed records: 0 trong scope.
Chỉ có một PDF BBS_2025; cross-document identity invariant còn được kiểm tra bằng
synthetic test với cùng semantic metadata. BBS_2024 extraction **NOT VERIFIED**.

Toàn bộ 1299 unique graph selectors đối chiếu page metadata và resolve được vào
payload persisted W-07 hoặc native M1-15 tương ứng. Validator kiểm tra exact anchor
metadata từ record cho mọi from_source edge. 53 source files hash trước/sau không
đổi, gồm PDF/raw/source snapshots và bốn M3-03 repositories.

Các records thực cùng page/document/snapshot đều có exact shared source context;
số cặp same-page nhưng không exact trong scope này là **0**. Không báo đây là
negative coverage thực. Negative control loại mọi selector/raw ID trên copies thật
đã chứng minh builder không tạo association vì page co-location; cạnh cố tình chèn
vào bị unresolved với `exact_association_not_established`.

## Relationship sample review

Mẫu chốt theo task và M3-03 trước đánh giá, gồm ba codes/trang, hai kỳ và hai attempts.
Đối chiếu exact selector/binding bằng records thật; status quan hệ vẫn unresolved.

| Statement / trang / codes | Fact observations | Associations | Kết luận |
| --- | ---: | ---: | --- |
| B01 / 5 / 110,130,270 | 12 | 72 | Exact source association; UNRESOLVED |
| B01 / 6 / 300,410,440 | 12 | 84 | Exact source association; UNRESOLVED |
| B02 / 7 / 10,20,60 | 12 | 84 | Exact source association; UNRESOLVED |
| B03 / 8 / 20,50,70 | 12 | 96 | Exact source association; UNRESOLVED |
| B09 / 14–15 | 0 | 0 | NOT VERIFIED: không indexed evidence hợp lệ trong selected exports |

Mẫu có 48 observation occurrences cho 24 numeric tokens của 12 physical rows,
không phải 48 nguồn độc lập. Context edges chỉ cho biết nguồn được tham chiếu chung,
không xác nhận context hỗ trợ nội dung tài chính. Không diễn giải table association
thành verified fact; tất cả financial_fact_verified giữ false.

M1-native trang 5 có hai headers cùng column=3, đã ghi 6 ambiguous period bindings
ở M3-03. Graph giữ record/structure qua reference và resolution issues, không tạo
M1-native→W07 association hoặc sửa kỳ/columns. Tất cả nodes/edges M1-native vẫn
unresolved, không biến ambiguous period thành verified.

## Negative controls và PDF-grounded correctness

10/10 controls trên copies của fact/table thực được phát hiện: sai document,
snapshot, dangling reference, sai source/target domain, duplicate node, duplicate
edge, unsupported cell level và unknown level → invalid; missing source và
page-only association không selector → unresolved. Focused tests thêm known
cross-document/snapshot/request association conflicts, missing catalog refs,
identity collisions, cross-document observations và schema từ chối future types.

M3-04 không đọc lại PDF để chấm financial accuracy. [M3-03 PDF review](m3-03-real-evidence-validation.md)
đã có mẫu page/token đối chiếu và các lỗi period/glyph/segmentation; chỉ dùng như
evidence trước đó, không nâng thành kết quả mới. PDF-grounded relationship/cell
correctness và full-PDF financial accuracy ở M3-04: **NOT VERIFIED**. B09 raw nguồn
có tồn tại nhưng chưa có export/adapter binding phù hợp để xây graph tại scope này.

Zero Gemini/OCR/extraction calls, zero raw/source changes. Đây là structural/source
association review, không financial benchmark hoặc một accuracy tổng hợp.

## Review correction — tách ba chiều validation

Tech Lead yêu cầu sửa semantics, giữ REVIEW/chưa DONE. Chạy cùng scope, cùng 356
facts/99 evidence (92 indexed + 7 quarantine), không thêm nguồn hoặc chọn subset.
Output mới: `artifacts/evidence/M3-04/review-correction`; invocation như trên với
`--output` trỏ thư mục mới này. `usability-probes.json` giữ value/context/operands
chi tiết trong storage ignored, không commit financial payload.

| Chiều / mẫu số | Trước correction | Sau correction |
| --- | --- | --- |
| Structural nodes valid/invalid/unresolved | 0/0/1747 (status gộp) | 1747/0/0 |
| Structural edges valid/invalid/unresolved | 0/0/7407 (status gộp) | 7407/0/0 |
| Grounding unique anchors page/element/cell | 1299/0/0 | 1299/0/0 |
| Grounding uncertain / resolved unique anchors | 1299/0 | 1299/0 |
| Missing/unsupported source trong indexed records | 0/0 | 0/0 |
| M2 direct_qa usable/usable_with_caveat/insufficient/conflicted | 46/246/64/0 trong source context, chưa báo riêng | 46/246/64/0 (356 annotations trên 356 facts) |
| Direct retrieval usability | Chưa probe | 292/356 display được với caveat; 64 blocked |
| Analytical readiness gross margin kỳ 2025 | Chưa probe | 2 pairs: 0 compatible, 0 incompatible, 2 undetermined |
| Missing identities/quarantine | 7 | 7, không indexed node/source ID giả |
| Orphans/collisions/source binding conflicts | 0/0/0 | 0/0/0 |
| Existing real negative controls | 10/10 phát hiện | 10/10 phát hiện, status/reasons giữ nguyên |

Không đặt ngưỡng PASS; counts structural valid đến từ tách dimensions. Các checks
identity/types/references/document/snapshot/request/exact selectors và unsupported
provenance giữ nguyên. Source statuses không được sửa thành resolved. Tất cả 7407
edges vẫn có grounding reason `source_reference_uncertain`; mọi financial_fact_verified
giữ false. Graph có 4887 from_source và 2520 associated_with như trước, không đổi
node/edge topology. 1299/1299 unique selectors vẫn resolve/page-bind đúng với source
payload; 53/53 source hashes unchanged, gồm raw/PDF và M3-03 repositories.
Đối chiếu bổ sung hai canonical snapshots trước/sau byte-for-byte identical;
356/356 graph evidence contexts giữ exact quality_context/resolution_issues của
facts gốc; EvidenceGraph models trước/sau bằng nhau, không tạo topology mới.

Resolution reasons được giữ riêng: missing_company_id 356, missing_reporting_scope
356, missing_canonical_mapping 300, m2_extraction_issue 76; 92 indexed document records
vẫn giữ source_reference_uncertain/page_level_provenance/missing_source_anchor_id.
M2 decisions không được recompute; 92 text/table records không có M2 annotation
không được tự gán usable. Analytical usability không suy từ direct_qa decision.

Direct retrieval predicate chốt trong runner: structural node valid, có raw và
normalized value, period, unit, source page và đúng một persisted direct_qa decision
usable/usable_with_caveat. 292 đáp ứng; 64 blocked đều có M2 insufficient, gồm 30
missing normalized value và 16 missing raw value (reasons có thể overlap). Lấy
observation đầu tiên đáp ứng qua `CanonicalFactRepository.get(ObservationIdentity)`
sau restart, so exact model JSON với input. Trả raw/normalized value, period/unit,
context (currency/scale), nguyên quality context/resolution reasons/source pages
và limitation: extracted display với page provenance uncertain, chưa cell/financial
verified. Không đòi cell-level provenance để hiển thị có caveat và không nâng
insufficient thành usable. Chi tiết giá trị thật chỉ lưu ở output ignored.

Analytical spec tường minh lấy example gross_margin M3-01: B02 net_revenue role
revenue và gross_profit role gross_profit, cùng kỳ, cùng document. Chọn kỳ 2025,
mỗi attempt hai canonical item observations (không chọn tùy tiện khi duplicate).
Chạy `assess_compatibility()` không sửa operands: 2/2 pairs undetermined vì
missing_company_id, missing_reporting_scope, missing_semantic_role,
unresolved_operand_context và source_reference_uncertain. Period 2025 có sẵn,
không báo giả missing_period hoặc điền scope/company/roles để đạt compatible.
Reasons occurrences: company 2, scope 2, semantic_role 4, unresolved context 4,
uncertain-source 40 (lặp theo source refs). **Không thực thi phép tính.**

Mẫu B01/B02/B03 vẫn có 72/84/84/96 associations structural valid, grounding
uncertain; B09 vẫn NOT VERIFIED. Cả 2520 associations có exact sources nhưng
**chưa chứng minh semantic support**; 3588 matching-source occurrences vẫn page-level.
Same-page negative case thực trong scope là 0, control cố ý bỏ selectors vẫn chặn
association như trước. Ambiguous period/cell geometry/full-PDF accuracy vẫn giữ
limitations cũ, không được hợp thức hóa bởi structural valid.

Local focused tests, Ruff/planning/diff và implementation SHA/CI cập nhật ở
[task evidence](../planning/tasks/M3/M3-04.md). Zero Gemini/OCR/extraction/raw changes;
chỉ usability probe, không M4 tool hoặc benchmark tài chính.
