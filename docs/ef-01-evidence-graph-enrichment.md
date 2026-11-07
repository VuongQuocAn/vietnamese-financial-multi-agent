# EF-01 — Evidence Graph Enrichment & Cross-Snapshot Evidence Linking

Ngày 07/11/2026, Asia/Bangkok. Baseline `fbda889`.
Implementation/CI: đang chuẩn bị commit; bằng chứng local bên dưới, chưa suy diễn CI.

## 1. Executive Summary

CompositionGraphView tái sử dụng typed EF-EG v1, thêm approved Document Evidence và
overlay `same_extraction_context`. Không migration hoặc graph engine mới. Năm
compositions đưa đủ 1.787 records vào view; 294 contextual links chỉ ở BBS2025.
Không tạo cạnh semantic revenue → B09 khi thiếu item/section selectors.

12 ca inspection trên nguồn thật và 13 negative controls đạt; tất cả views rebuild
deterministic, không orphan hoặc wrong-document/snapshot leakage trong các ca kiểm tra.
Đây là engineering evaluation trên saved source-bound extraction, không M8 hoặc
đánh giá độc lập độ chính xác tài chính/toàn bộ PDF. Không Gemini/OCR calls.

## 2. Existing EF-EG Architecture

`build_graph`, `validate_graph`, `associate_fact` giữ nguyên. Existing source facts,
text/table, anchor, derived metric và ba relations `from_source`, `associated_with`,
`used_in` tiếp tục đúng contracts cũ. Không có Claim/ACCEPT node mới.

Phase A đã đọc graph/contracts, exact association rules và năm compositions trước
viết enrichment; audit local: `artifacts/evidence/EF-01/source-audit.md`.

| Relationship | Existing support | Safe to link? | Required evidence |
|---|---|---|---|
| Fact → SourceAnchor | v1 | Yes | Original source |
| DocumentEvidence → SourceAnchor | v1 | Yes | Pin + page/image/PDF binding |
| Fact → Exact Evidence | associate_fact | Conditional | Same snapshot/request + exact selector |
| Fact → Document Context | Overlay | Conditional | Composition + original request + bound page + pointer |
| DocumentEvidence → Verified Claim | M6/Ledger authority | Conditional | Accepted proof; không làm trong EF-01 |
| Same page → Semantic support | Invalid | No | Independent claim proof |

## 3. Source/Snapshot Integration

Inputs chỉ gồm năm explicit EXT-01 manifests/repository, BBS accepted M4 catalog
và BCC GEN-01 normalized-final/audit-final. Không scan saved JSON làm graph inputs.
`load_composition` xác minh pins, payload fingerprint, snapshot/PDF/page/image và
loại quarantine. `select_financial_catalog` chọn induced view đúng financial descriptor;
đối chiếu nodes/edges với records và kiểm tra PDF source scope, không latest fallback.

Không đổi document_id/snapshot_id. BBS2025 còn original UUID document namespace
trong bảy records accepted, khác logical SHA document. Overlay giữ cả hai identity
và bound PDF. M4 cũ chặn namespace này bằng `snapshot_blocked`; graph giữ guarded
status đó, đồng thời trả `original_citations` từ approved source projection để đọc
đường đi. Citation structural không trở thành M6 admission proof.

BCC2025 riêng và BCC2024 hợp nhất có PDF hash/composition riêng. Source reviews,
metric operands/lineage và accounting-basis restrictions tiếp tục qua M4; không
gọi calculator hoặc tính lại tỷ số. Financial artifacts không được rewrite.

## 4. Graph Model & Relation Semantics

`CompositionGraph` chứa EvidenceGraph v1 cùng contextual overlay độc lập, không
sửa GraphEdge schema. ContextRelation giữ source/target node IDs và typed original
references, logical document/composition, PDF hash, request, hai source anchors,
basis và `verification=contextual_only`, caveat `not_semantic_claim_support`.

## 5. Composition-Aware Enrichment

Merge theo original identities; payload collision bị từ chối, cùng trang không
merge anchors. Financial nodes/edges phải hiện diện nguyên trạng. New source
edges và same-snapshot exact associations vẫn do build_graph/associate_fact tạo.
Không tạo fact/metric mới. Views sắp xếp deterministic; original persisted graph
không thay đổi thứ tự hoặc payload.

## 6. Exact vs Contextual Associations

Overlay chỉ tạo khi cùng request trích xuất gốc, cùng bound page/image/PDF và
explicit same source pointer hoặc cell nằm trong table pointer được tham chiếu.
Request index giới hạn candidate set; không nối Cartesian toàn PDF. Pointer giống
nhau ở hai requests độc lập không đủ. Same-snapshot relations tiếp tục thuộc M3.

294 links BBS2025 dẫn tới bảy original records trang 6 được composition chọn.
Chúng giúp QA truy nguồn extraction trước chuẩn hóa, không giải thích biến động
doanh thu hoặc chứng minh chính sách kế toán. Các PDF khác không có cross-snapshot
selector đủ điều kiện; 0 contextual links là kết quả có chủ đích.

## 7. Quality Propagation

Graph giữ GraphValidation/evidence quality, grounding levels/status/reasons,
source metadata và original citations. Retrieval trả quality/caveats cùng từng
node; anchors giữ metadata/quality của source records. Unknown reading, truncated
paragraph, structural/layout/table geometry metadata không bị loại khi graph hóa.

BBS2025 trang13 vẫn trả `pdf_review:omitted_hoan_in_deferred_tax_liability_phrase`.
Replay câu OCR lỗi thực tế: M6 INVESTIGATE1, 0 accepted claims, 0 citations; old
proof admission rejected. Không sửa M6 judge, ledger hoặc M7 firewall.

## 8. Graph Retrieval API

Public facade: `EvidenceRetrievalTools.from_composition(..., financial_catalog=...)`
và `get_graph_context(GetGraphContextRequest(...))`; có thể dùng GraphRetrievalTools
trực tiếp từ CompositionGraphView. Typed contracts ở `src/tools/graph_retrieval.py`.

Request yêu cầu explicit document_id/composition_id/node_id, relation filters,
depth1–3, limit1–50. Traversal hai chiều nhưng giữ nguyên hướng cạnh nguồn.
Response giữ start/matched nodes/depth, typed edges/basis/verification, M4 evidence
status/reasons/reviews/lineage, original citations/quality và truncated flag.
`found` là graph presence, mỗi node vẫn có guarded evidence status riêng;
`not_found` là node ngoài view, `unavailable` là composition sai/chưa hydrate.
Input ambiguity/collision bị từ chối lúc build, không tự chọn candidate.

## 9. Real PDF Results

Document total gồm financial evidence cũ và approved composition records đã dedup;
cột EXT records chỉ đếm pins được chọn. Exact counts là structural v1 relations,
không phải số semantic claims. Counts không được dùng làm accuracy score.

| PDF | Facts | EXT records | All document nodes | Anchors | Metrics | from_source | Exact | used_in | Context |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BBS_2022 | 196 | 40 | 66 | 604 | 3 | 2462 | 1274 | 6 | 0 |
| BBS_2024 | 186 | 16 | 43 | 625 | 3 | 2457 | 1274 | 6 | 0 |
| BBS_2025 | 178 | 439 | 467 | 2535 | 3 | 4335 | 1260 | 6 | 294 |
| BCC_2024 | 204 | 676 | 676 | 3030 | 2 | 5178 | 1536 | 4 | 0 |
| BCC_2025 | 204 | 616 | 616 | 2818 | 2 | 4762 | 1332 | 4 | 0 |

Tất cả node/edge validations valid, orphan0, constructed invalid/unresolved0;
không có nghĩa mọi cặp record đã được đánh giá semantic. Negative proposals được
báo riêng. Rebuild từ approved inputs giống hệt cả năm views; selected accepted
graph/metrics/reviews/composition/repository fingerprints giữ nguyên.

12 cases gồm revenue source từng PDF, gross-margin operands, B09 personnel,
known OCR defect, hai filing BCC, signer layout và cross-snapshot selector.
Năm revenue traversals depth2 đạt limit50, trả `truncated=true`; không báo đó là
toàn bộ neighborhood. Metric/path B09/context không bị cắt.

Ba đường đi thật (IDs đầy đủ, PDF/image fingerprints và actual edges ở local JSON):

| Case | Actual path | Original source | Ý nghĩa và quality |
|---|---|---|---|
| G03 | BBS2025 revenue `.../page/7/link/4` → from_source → `/tables/0/cells/13` | `D-01/normalized-v2`, PDF page7 | Source selector; page-level/uncertain, không financial verification |
| G06 | Gross margin `derived_metric:ccffa7fe4cda4d77bd4d96fdb3e57501394d372e0fe482e153d1603fb3c9617c` ← used_in(revenue/gross_profit) ← facts → anchors | Original operands page7, cùng financial snapshot | Giữ operand roles, lineage và blockers; không recalculation |
| G07 | Text `unified/page/14/text/text_elements/4` → from_source → `/text_elements/4` | `artifacts/gemini-ingestion/M1-15/pdf/page-14.json`, PDF page14 | B09 narrative source; không tạo financial fact hoặc role claim |

Đường chéo G12: fact `.../page/6/link/33` trong `D-01/normalized-v2`
→ same_extraction_context → original UUID snapshot
`4f5be1e8-5e4a-4f3d-8bb8-6ceea20b42c6`, `record/1/page/6/context/1`.
Hai anchors giữ `/context/1`, same request và bound page6/image, verification
contextual_only. Không ép relation này thành associated_with hoặc semantic support.

Local artifacts: `artifacts/evidence/EF-01/final/{inventory,cases,negative-controls,integrity,summary}.json`,
`<PDF>/graph-view.json`, `paths/G01.json`–`G12.json`, `m6-boundary/source-quality-gate.json`.
Không commit PDF/raw extraction/canonical payload hoặc full graph views riêng tư.

## 10. Negative Relation Controls

13 controls: wrong-year BBS, cross-company BCC, unbound composition, legacy OCR,
wrong pointer/page, duplicate overlay, missing overlay endpoint, same-page-only,
independent request, signer-role promotion, duplicate v1 và dangling v1 endpoint.
Tất cả bị từ chối/không tạo edge phù hợp. Unit controls thêm quarantine, changed
PDF binding, unbound financial snapshot, typed identity tampering và bounds.

## 11. Root Causes & Fixes

Không ép cross-snapshot vào GraphEdge v1: overlay giữ contracts và original IDs.
Original UUID records làm guarded M4 source lookup unavailable dù approved pins:
thêm original_citations structural riêng, vẫn giữ snapshot_blocked; không đổi M4/M6 gates.
Document anchor lookup cần graph của approved document catalog: hydrate bằng
build_graph v1 thay vì tạo anchor identity mới. Strict Decimal JSON của BCC cần
validate_json khi đọc accepted artifacts; lỗi nằm ở evaluation loader, không sửa data.
Planning checker chưa biết EF: thêm branch EF và một fixture regression.

## 12. Compatibility & Regression

Local: 284 targeted compatibility tests PASS; sau bổ sung structural citations,
29 graph/M4 tests PASS và 13 graph tests PASS với UUID gate control mới.
Không chạy lại full regression; CI sẽ chạy focused suite trên implementation SHA.
Ruff, planning và diff checks được ghi tại registry khi chốt. M6 replay nguồn thật
đạt như mục7; GEN-01a/Web pending được giữ ngoài commit.

## 13. Limitations

Không suy section membership/B09 semantic links từ từ khóa. Missing selector,
missing section metadata và unsupported semantic association là ba giới hạn
riêng; không có source coverage gap được graph tự sửa. Views không chứng nhận
OCR/financial accuracy. V1 exact associations có thể dựa shared context anchors:
nhiều cạnh không có nghĩa nhiều bằng chứng độc lập. Source uncertainty và BCC2024
accounting restrictions giữ nguyên. Traversal trong run local: 9.4–2977.2 ms (không gồm dựng facade); chưa
được tối ưu hoặc so sánh benchmark; kết quả thời gian chỉ một run trên máy local.

## 14. Handoff QA-01b

QA-01b có thể dùng typed get_graph_context với explicit composition/node,
đọc original typed references/citations và guarded reasons, rồi yêu cầu M6 resolve
nguồn thật. Không dùng graph status/association thay ACCEPT proof. EF-01 không sửa
M5 routing/M7 output và không bắt đầu QA-01b. Chờ Tech Lead nghiệm thu REVIEW.
