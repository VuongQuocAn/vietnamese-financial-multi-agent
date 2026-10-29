# M3-04 — Real-artifact graph validation

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
