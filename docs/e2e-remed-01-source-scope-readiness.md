# E2E-REMED-01 — Source & Scope Readiness

**REVIEW**, ngày17/11/2026 (Asia/Bangkok). Implementation
[`02093495863bec10424659bcad7175e69edad457`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/02093495863bec10424659bcad7175e69edad457),
baseline remote main f4d598e, worktree riêng giữ local edits.
Binding/truy xuất đã tiến triển; **accuracy/coverage của4QA bị ảnh hưởng vẫn0/4**.
Chưa đủ điều kiện chạy tiếp Pilot. Không sửa M6/M7 hoặc thay Evidence Obligations.

## Nguyên nhân và thay đổi

- Scope JSON trước đây chỉ đọc `fact.context.reporting_scope`, bỏ sót checkbox
  BCTC được chọn. Overlay mới đọc title/selected option đúng front matter,
  giữ ContextEvidence với pointer/hash. BTW/BTS có selected separate thực tế;
  unselected/unknown/uncertain/conflict không tự thành separate. Không dùng Gold,
  tên doanh nghiệp, thiếu chữ hợp nhất hoặc metadata unknown để suy scope.
- Composition/search trước đây có giả định PDF. API nay bind đúng một snapshot
  JSON đã pin; EvidenceComposition/EvidencePin replay record/bytes/cells trước
  hydrate. `verified` ở source là fidelity, không financial approval, không tạo
  PDF hash/image hoặc approved review giả. Reuse EF-EG trong memory, không ghi lại.
- Bảng import dùng UnderstoodCell `col`/`id`, nhưng search đọc `column` và dựng
  `/cells/...` không tồn tại trong JSON. Search nay trả column/pointer gốc của
  `/columns/...` và `/rows/...`; JSON có `source_page`, `pdf_page=null`.
- M5 có context D từ Financial/Evidence Tools và FTS hiện có, tối đa16term probes,
  top3records, bounded snippets/cells, giữ source refs/truncation/caveats và
  imported/mapped/eligible counts. D không là numeric evidence_id/operand và
  không tự satisfy goal. Missing mapping/unit vẫn không đủ quyền tính hoặc ACCEPT.
- Lượt đầu MH0001 qua composition rồi lộ parser hiểu **“tên riêng”** thành scope
  báo cáo riêng. Sửa generic qualifier tên/nêu/liệt kê/trình bày/hiển thị riêng,
  vẫn giữ shorthand scope hợp lệ. Fusion context nhận `json_bound` giống financial
  lane, chỉ khi scope resolved/đúng yêu cầu. Không nới M6 admission/ACCEPT.

## Retest thực tế

Chỉ4QA duy nhất từ manifest câu hỏi đã freeze của E2E-VAL-01; không đọc Gold trong
answering. Một đợt4câu trên bản source binding đầu, rồi kiểm riêng MH0001 sau sửa
false scope; trace trung gian0calls được giữ riêng. Không chạy lại3câu khác.
Cap task40calls,10/câu; phần kiểm bổ sung trừ calls đã dùng. Không transport retry,
API judge, Gemini/OCR/PDF/fullCI hoặc36Pilot/Full600.

| QA | Trước E2E-VAL-01 | Sau | Calls trước→sau | Wall s trước→sau | Lỗi còn lại |
| --- | --- | --- | --- | --- | --- |
| MH0006 | clarification_required | internal_error | 0→1 | 3,951→42,332 | Scope đã qua; Supervisor invalid envelope |
| MH0001 | composition_required | provider_unavailable | 0→8 | 5,414→167,106 | Composition/scope đã qua; chọn nợ thay phải thu, query phụ thuộc chưa resolve, document requirements trùng |
| SH0006 | verification_blocked | provider_unavailable | 7→6 | 241,945→211,544 | D context có bảng khấu hao; planning/handles và1structured_output_invalid, chưa verified goal coverage |
| NR0001 | verification_blocked | verification_blocked | 3→3 | 42,925→73,524 | Query mơ hồ/không đúng hàng; net_revenue chưa có canonical fact trong import |

Cả4 **abstain**,0citations phát hành; accuracy/answer coverage trước0/4→sau0/4.
Không diễn giải gate/source availability thành financial correctness. MH0001
trung gian requested_scope_unconfirmed/0calls/7,175s không trộn vào latest outcome.
Tổng5attempts: **18actual Qwen calls/102082known tokens/0unknown**,501,681s cộng
wall gồm load/validate. Riêng latest4outcomes494,506s. Không tuyên bố speedup.

MH0001 cuối đi qua financial binding, fusion planner, financial/document lanes,
graph context và M6:2ACCEPT/1INVESTIGATE nhưng không release. S15 là nợ phải trả,
không phải nguồn phải thu cần so sánh; document planner lặp nguyên câu phụ thuộc,
không có document candidate. API status `provider_unavailable` không đồng nghĩa
endpoint hỏng:8transport responses success và provider_errors rỗng.
SH0006 tương tự có3ACCEPT scalar/1ABSTAIN,1malformed specialist; không tự cấp coverage.

Requests004/006 của SH0006 lưu source D trỏ đúng bảng JSON khấu hao với4cells,
bao gồm ô khoảng thời gian; nguồn đã tới specialist nhưng chưa có proof/goal
support cho câu trả lời. NR0001 có source context nhưng query của planner mơ hồ
trả các đoạn khác. Bảng B02 trang11 chứa raw revenue, nhưng import cũ loại toàn
bảng vì ragged row. **Không khôi phục/rebuild canonical/EF-EG trong task này**;
đây là import/query/handle gap, không phải raw corpus absence.

Gold, output đầy đủ, source contexts, before/after, calls/latency và link trace ở
local `artifacts/evidence/E2E-REMED-01/qa-report.md` và `comparison.json`.
Hai đợt evidence `live-final/` và `final-scope-check/` giữ receipt/runtime hashes,
provider requests/responses, outcomes/Ledger. Raw traces/Gold/dataset không commit.

## Validation và giới hạn

3new controls PASS: scope positive/negative/conflict/tamper + qualifier parsing;
composition/cell-pointer fidelity; M5 source context không thành numeric handles.
Compatibility nhóm JSON/PDF composition/search/scope:61PASS; nhóm QA/fusion:
71PASS/2FAIL (có overlap scope control).2FAIL legacy về metric substitution và
malformed-provider retry **FAIL y hệt baseline f4d598e**, không sửa ngoài scope.
Ruff/planning/diff PASS; engineering controls không chứng nhận accuracy tài chính.

Offline smoke xác nhận scope BTW/BTS separate có provenance và search lấy bảng
khấu hao; scope thiếu ở tài liệu khác giữ unresolved. M6 document vẫn có kiểm tra
PDF-specific; chưa thêm authority cho JSON document claims. Live chưa tạo được
document candidate để chứng minh release loại claim này, không gọi đó là PASS.

Audit186runtime blobs cuối khớp implementation; đợt đầu khác đúng2files scope
parser/fusion context, ghi rõ trong receipt/audit, không gán tất cả outcomes cho
cùng implementation.143raw JSON/28imported files (gồm EF-EG) và3Pilot hashes bất
biến,80local files cùng evidence E2E-VAL-01 nguyên byte. M6/M7 blobs không đổi.
Không reimport, đổi unit/mapping, sửa nguồn hoặc dùng raw D để tạo số liệu.

**Next action:** Tech Lead review các binding/source fixes và các lỗi
Planning/query/source handles/canonical eligibility còn lại trước khi cho phép
tiếp tục Pilot45; không tự chạy36Pilot hoặc Full600.
