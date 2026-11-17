# E2E-REMED-02 — Planning & Evidence Routing

Ngày17/11/2026 (Asia/Bangkok), **REVIEW**. Implementation
[`78a5e67202429cdd76556f883597abed35c939e4`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/78a5e67202429cdd76556f883597abed35c939e4),
baseline main9fec038, worktree riêng giữ local edits. M6/M7/Evidence Obligations,
raw/canonical JSON/EF-EG không đổi. Không mở thêm Pilot hoặc Full600.

## RCA và sửa trong phạm vi

Saved traces cho thấy planner sao chép ví dụ ba goals/hai operands/phép tính vào
lookup; MH0006 vượt cap7tasks hoặc bỏ owner của goal tổng hợp; Demand coi T1/T2
là S handles, MH0013 trả12retrieval trong array capped6. Source context thuyết
minh đã có nhưng trước đây chỉ cung cấp sau planning và không nằm trong digest
của TaskResult truyền downstream. Fusion còn lặp document requirements và không
truyền parent results vào query context của lane sau.

- Planner công bố thêm root JSON schema với max6tasks/16goals, enums nguồn và
  namespace S/T/E/D; bỏ ví dụ ba mục tiêu mặc định, giữ ví dụ lookup một goal.
  Schema được validate ở backend; không tuyên bố provider constrained decoding.
- Plan sai cấu trúc/owner hoặc thêm chỉ tiêu/kỳ rõ ràng được giữ raw trace rồi
  fallback một task/goal nguyên câu hỏi. Không retry planner, không xóa goal để
  báo complete. Fallback giảm phân rã; không chứng minh semantic completeness.
- Goal có canonical item+period unique có thể resolve S ordinal chọn nhầm bằng
  exact inventory identity; ambiguous/unknown không đoán. Raw proposal vẫn lưu.
- T/result/E reuse đúng dependency closure/ref/digest; không dùng task ID như
  một nguồn canonical. Demand tới16inputs được validate toàn bộ rồi chia batch
  tối đa6; không cắt6nguồn đầu hoặc đổi cap của một batch.
- Source context nguyên câu hỏi bổ sung query task, giữ exact pointers/caveats;
  TaskResult digest chứa D context và consumer nhận context của parent. `source_only`
  cho phép tiếp tục truy xuất từ evidence có nguồn, không tạo claim hay ACCEPT.
- Fusion deduplicate đúng lane/kind/span/execution/document requirement và chuyển
  dependencies sang identity giữ lại. Parent response/citations đi qua
  conversation_context hiện có như query context, không như evidence authority.

## Validation

3controls mới PASS: bounded/owned fallback + exact item binding;12demands chia
6+6không mất nguồn và reuse T/result/E; source-only context/digest tới consumer
mà không thành numeric claim.25targeted compatibility PASS; recheck fusion V2
PASS sau thay đổi dedup. Ruff/planning/diff PASS; không chạy lại legacy failures
đã xác minh ở task trước khi không có thay đổi liên quan.
Không fullsuite/fullCI/OCR/Gemini/API judge; engineering PASS không là accuracy.

## Live retest

Chỉ SH0006/MH0006/MH0013/MH0001 từ questions-only manifest đã freeze, không đưa
Gold vào runtime. Một đợt, một lượt/câu;40actual calls task/10calls mỗi câu,300s/request,
60s/provider, không transport retry. Existing bounded runtime repair vẫn áp dụng;
không có vòng sửa prompt/retest sau live. Before/after lấy từ saved Pilot/REMED-01;
Gold chỉ hậu kiểm, không tính kết quả4câu thành accuracy Pilot45.

| QA | Before | After | Calls trước→sau | Wall s trước→sau |
| --- | --- | --- | --- | --- |
| SH0006 | provider_unavailable | verification_blocked | 6→2 | 211,544→82,176 |
| MH0006 | internal_error | verification_blocked | 1→5 | 42,332→222,307 |
| MH0013 | internal_error | verification_blocked | 2→2 | 67,091→109,961 |
| MH0001 | provider_unavailable | provider_unavailable | 8→8 | 167,106→312,511 |

Before lấy bản gần nhất REMED-01 cho SH0006/MH0006/MH0001; MH0013 lấy VAL-01
vì không chạy trong REMED-01. Cả before và after **0correct/0partial/4abstain,
accuracy/answer coverage0/4**,0citations phát hành. Tổng **17actual calls,
95473known tokens/1unknown usage**,726,955s cộng wall gồm load/search/verification.
Wall MH0001 vượt300s do setup/fusion child requests; timeout cấu hình là request
budget, không phải hard wall timer cho toàn runner. Không tuyên bố speedup/accuracy gain.

- **SH0006:** raw plan giữ một lookup goal nhưng gán D2 vào input_handles.
  Adapter ghi nguyên failure và fallback một goal/T1 nguyên câu hỏi. T1 nhận đúng
  bảng JSON/ô khoảng thời gian, kết thúc source_only, không có runtime errors.
  Specialist viết đáp án bằng D2 trong evidence_ids; D context không canonical
  numeric/proof authority nên không tạo candidate M6 hợp lệ. Prose đúng Gold
  chưa là system answer phát hành; M6/M7 không bị nới để cứu câu này.
- **MH0006:** raw6tasks/7goals thiếu owner G1; backend fallback một task/goal
  nguyên câu hỏi, không mất mục tiêu tổng hợp. M6 có3ACCEPT/1INVESTIGATE và một
  repair runtime, nhưng không verified support cho G1 đầy đủ doanh thu/tài sản.
  Scalar/tỷ lệ được model đề xuất chưa đáp ứng goal; không lấy ACCEPT thay coverage.
  Không còn supervisor_invalid_envelope ở output thực thi, provider errors rỗng.
- **MH0013:** raw4goals có dependencies nhưng hai task dùng D handles ở S slots;
  fallback về nguyên câu hỏi, T1 source_only/không M6/citations, không runtime errors.
  Chưa có typed numeric domain/join đầy đủ cho named-bank→subsidiary→ownership.
  Không chứng minh live entity join hoặc live12demands; batching6+6/reuse namespace
  mới có positive control offline. Fallback thay toàn proposed DAG, nên không giữ
  được lợi ích phân rã/role assignment của những phần proposal vốn hợp lệ.
- **MH0001:** Fusion dedup3requirements thành2. Financial T1→T2 chạy, T2 nhận
  result:T1:v1/revision/digest, hai observations và source context. Demand dùng
  kỳ từ parent, exact-context join matched và không mất sources; document planner
  nhận parent status/verified refs qua conversation_context. Đây là positive live
  handoff, chưa có positive answer release.

  Target vẫn lệch: **S5 là tổng phải thu ngắn hạn130, câu hỏi cần phải thu khách
  hàng131**. Import hiện có131 với canonical_item_id=None, nên inventory không có
  target đúng; exact-item binder không sửa được taxonomy/mapping thiếu. Không
  hardcode alias/code, promote raw observation hay sửa EF-EG. Demand chọn max trên
  một item/một kỳ cũng chưa chứng minh phép so sánh hai khoản mục.

  M6 timeout60,165s (usage unknown1),4INVESTIGATE/0release; không retry transport.
  Parent chưa có winner verified nên document judge giữ NOT_RETRIEVED/REVISION_NEEDED.
  Không bịa thực thể dựa vào đoạn nhận dạng chưa có authority.

Raw model vẫn có lỗi schema/namespace/ownership. Những trường hợp trên được
backend xử lý bằng fallback có trace, không gọi model đã tuân schema hoàn toàn.
Trong4output cuối không có runtime schema/unknown-handle errors. Giới hạn còn lại
là chất lượng phân rã/target semantics, thiếu canonical và verification/timeout;
**chưa đủ điều kiện tiếp tục Pilot45**. Không sửa runtime thêm hoặc retest lần hai.

Per-QA Gold, output đầy đủ, before/after/calls, raw requests/responses, workspace,
tool/agent traces và Ledger nằm local `artifacts/evidence/E2E-REMED-02/qa-report.md`,
`comparison.json` và `live-final/`; không commit dataset/Gold/raw evidence.

## Integrity và giới hạn bằng chứng

186runtime blobs khớp implementation/frozen receipt.146raw JSON/28imported files
(gồm EF-EG)/3Pilot hashes bất biến;80local files và evidence cả hai task trước
nguyên byte. M6/M7 và module evidence không đổi.5TaskResult digests cùng dependency
input refs khớp;4Coordinator goals có owner. Fusion aggregate requirement IDs
không là Coordinator goals và được loại khỏi phép kiểm ownership này.
14cell-pointer occurrences trong saved source contexts khớp JSON gốc; đây không
là14đáp án hoặc financial facts độc lập, không PDF-verified.

Controls/SHA/hashes chứng minh engineering và provenance trong phạm vi task,
không chứng nhận chất lượng tài chính hoặc lợi ích Multi-Agent. Research review
vẫn cần Tech Lead, không tự DONE hoặc mở task sửa canonical/M6.

## Handoff

Next action: Tech Lead review planning/routing fixes và lỗi còn lại trước khi cho
phép tiếp tục ViFinBench Pilot.
