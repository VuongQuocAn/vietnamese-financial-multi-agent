# EXT-01 — Full-Document Evidence Coverage & Extraction Completion

## 1. Executive Summary

Trạng thái: **REVIEW**, chờ Tech Lead nghiệm thu.
Implementation `34209fc02c065557cb9b1596c511f4d4feb22471` đã push main;
[CI42343884351](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42343884351)
completed/SUCCESS đúng SHA: 1.115 Python/9 Web smoke PASS, cùng
lint/format/planning/typecheck/build; full unit regression manual SKIPPED.
Baseline main `7187075`;
QA-01a accepted `d2b28634adc6a24b0d019de00897cbf3ce26a781`.
EXT-01 mở rộng coverage qua Gemini-native → UnifiedPage → existing repository →
composition → BM25. Không sửa financial facts, EF-EG hoặc M6 gates.
Coverage nguồn, chất lượng OCR và verification được đo riêng.

Artifacts đầy đủ giữ local tại `artifacts/evidence/EXT-01/`; dữ liệu tài chính,
PDF, ảnh, raw responses và ledger thực nghiệm không được đưa vào Git.

## 2. Baseline Coverage Before EXT-01

INT-01a có 151 records = 127 TextEvidence + 24 TableEvidence trên 17 trang.
BBS 2025: 5/24 trang; BCC 2025: 4/30; BCC 2024: 4/41;
BBS 2022 và 2024: mỗi PDF 2/26 trang trong composition.
Discovery BCC 71/71 của GEN-01a chỉ dùng làm inventory, không phải OCR.

| PDF | Total pages | Before | Reused | Newly extracted | Missing | QA-retrievable |
|---|---:|---:|---:|---:|---:|---:|
| BBS 2025 | 24 | 5 | 6 | 19 | 0 | 24 |
| BCC 2025 | 30 | 4 | 4 | 29 | 0 | 30 |
| BCC 2024 | 41 | 4 | 4 | 40 | 0 | 41 |
| BBS 2022 | 26 | 2 | 2 | 1 | 0 trong phạm vi 11/18 | 2 |
| BBS 2024 | 26 | 2 | 2 | 0 | 0 trong phạm vi 21/24 | 2 |

Mẫu số lịch sử là phạm vi được giao, không phải toàn bộ 26 trang.
`baseline-inventory.json` và `inventory.json` liệt kê mọi trang của năm PDF.
`full_prose=pending_independent_review` không được tính thành full narrative.
89 trang Gemini mới gồm 86 full-page requests và 3 footer supplements; 18 trang
cache được giữ/tái sử dụng. Có 8 trang vừa giữ bảng cũ vừa bổ sung text nên không
cộng hai cột thành page coverage: tổng unique retrievable là 99/147 trang inventory,
gồm 95/95 trang của ba PDF ưu tiên và 4 trang lịch sử được giao.
Discovery là 147/147, hoàn toàn tách khỏi extraction và visual fidelity.

## 3. Saved Cache Reuse

Kiểm tra cache M1-15/M1-16, D-01, GEN-01 và approved INT-01a.
Cache native BBS 2025 trang 7/8/14/15 được replay; trang 5 giữ nguyên accepted
native evidence. Trang tài chính 6 được bind từ D-01 với record-index pointers
gốc, không tính lại facts. Bổ sung footer riêng ở BBS 2025 trang 6,
BCC 2025 trang 6 và BCC 2024 trang 10; các bảng tài chính giữ nguồn cũ.
Historical B09 context/tables không được coi là full prose.
Legacy OCR thiếu PDF/image binding không được hydrate tự động.

## 4. Gemini Targeted Extraction

`complete_document_evidence.py` giới hạn số trang mỗi run, cache-first,
không tự retry failed page, lưu response ngay sau từng trang thành công.
Gateway Free Tier, model, key rotation, retry và quota hiện có được giữ nguyên;
composition service nhận thêm schema OCR qua tham số tùy chọn.

Document mode giữ paragraphs, headings, audit basis/opinion, footers, cells,
reading order và bbox candidates; không suy diễn số liệu hoặc danh tính từ chữ ký.
`recover_document_page.py` cho phép một nhóm attempt recovery mỗi trang,
thêm tối đa một nhóm nếu response trước là HTTP 503 và chưa có output,
hoặc có visual review xác nhận lỗi glyph/layout cần render 300 DPI;
giữ ảnh full page và hướng chú ý vào vùng lỗi để bảo toàn binding và section context.
Response đầu không bị ghi đè; chỉ chọn recovery sau PDF review.

## 5. Signer/Role Structural Evidence

PDF BBS 2025 trang 7–8 có ba cột ký riêng, mỗi cột gồm heading chức vụ,
vùng chữ ký và tên in bên dưới đường kẻ. Sáu candidates lưu role/person IDs,
page, tọa độ trên review render 120 DPI, image hash, PDF reference, rationale
và uncertainty. Không suy quan hệ từ thứ tự JSON hoặc nhận dạng nét chữ ký.

Bbox Gemini cũ có sai hệ tọa độ; giữ nguyên và không rescale để giả geometry
đã xác minh. Tọa độ review được lưu riêng. Supplement vẫn dùng TextEvidence,
raw role text và exact original pointer; M6 chưa hỗ trợ candidate layout policy
nên quan hệ tiếp tục INVESTIGATE. Không sửa verification gates.

## 6. Auditor Opinion Coverage

BBS 2025 trang PDF 4 có opinion, cơ sở và trách nhiệm kiểm toán.
BCC 2025 audit nằm trang 4, gồm cả “Vấn đề khác”; BCC 2024 audit trải trang 7–8,
opinion ở trang 8. Reporting scope BCC 2025 là riêng, BCC 2024 là hợp nhất.
Semantic opinion verification vẫn bị policy QA-01a chặn dù retrieval có nguồn.

## 7. B09 Narrative Coverage

BBS 2025 ưu tiên trang 9–24, giữ cache 14/15. BCC 2025 từ trang 9,
BCC 2024 từ trang 13. BBS 2022/2024 chỉ xử lý gaps đã chỉ định.
Trang lịch sử chỉ chứa bảng được ghi nhận riêng, không dùng số text elements
để suy ra full narrative. Mẫu review phân bố ở đầu, giữa và cuối phần notes.

## 8. Materialization & Composition

Dùng existing adapters và DocumentEvidenceRepository. `put_many` kiểm tra toàn
batch trước một atomic write, giữ idempotence/quarantine/conflict semantics.
Composition loader đọc một document một lần thay vì parse toàn repository
cho từng source. Đây là hỗ trợ materialization nhiều trang, không thêm storage engine.

Composition mới có ID `EXT-01/<PDF>/v1`; giữ nguyên sources/pins đã accepted.
Evidence có caveat từ visual review dùng projection mới có parent snapshot rõ ràng;
không sửa original snapshots hoặc raw payload. Exact text/cell/pointer fidelity
được đối chiếu với saved response trước persist. Index là derived projection.
Approved compositions hydrate 1.787 records = 1.629 TextEvidence + 158 TableEvidence.
Toàn bộ 151 records cũ và financial descriptors giữ exact payload; delta là
1.502 text + 134 table records. Repository còn giữ các projections không được chọn;
chúng không được hydrate hoặc search qua composition hiện hành.

## 9. BM25 Retrieval Results

Không đổi score, tokenizer hoặc generic search để ép query PASS.
Query audit BBS 2025 trả title ở hạng 1, basis và opinion đều trong top 5,
cùng PDF page 4. Kết quả đầy đủ lưu trong `qa-after/quick-qa.json`.
20 negative/reload/scope controls PASS, gồm thử ghép nguồn BCC hợp nhất 2024
với BCC riêng 2025 bị từ chối; source ngoài pins không xuất hiện trong index.

## 10. QA Before/After

Oracle 18 câu được chuẩn bị từ PDF renders trước khi đọc câu trả lời tương ứng.
Có audit, signer, policies, notes, tables, missing-source và wrong-document.
Baseline → EXT-01: relevant retrieval 4/16 → 16/16 positive cases;
M6 ACCEPT 3 → 12 claims, 3 → 11 câu có ít nhất một ACCEPT;
INVESTIGATE 3 → 5 claims; M7 có citations 3 → 10 câu.
Hai negative cases đều không có unsupported release; không cộng vào recall.
16 câu đầu và hai câu revenue/receivables bổ sung chạy riêng, không lặp lại cases PASS.
Mỗi case giữ question, expected behavior, source quote/page, retrieval hits,
toàn trace M5/M6/M7 và citations. Không tạo expected answers từ output QA.


### Source samples

| PDF / PDF page | Original short quote | Original source / pointer |
|---|---|---|
| BBS_2025 / 4 | Theo ý kiến của chúng tôi, báo cáo tài chính kèm theo đã phản ánh trung thực và hợp lý, trên các khía cạnh trọng… | `artifacts/evidence/EXT-01/BBS_2025/responses/page-4.json` / `/text_elements/21` |
| BBS_2025 / 9 | Niên độ kế toán của Công ty bắt đầu từ ngày 01/01 và kết thúc vào ngày 31/12 năm dương lịch. | `artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-9.json` / `/text_elements/15` |
| BBS_2022 / 11 | Tài sản cố định hữu hình được khấu hao theo phương pháp đường thẳng, số khấu hao được tính bằng nguyên giá chia… | `artifacts/evidence/EXT-01/BBS_2022/responses/page-11.json` / `/text_elements/7` |
| BBS_2024 / 21 | Chi tiết các khoản vay ngắn hạn của Công ty tại ngày 31/12/2024 như sau: | `artifacts/evidence/D-01/2024/result.json` / `/context/4` |
| BCC_2025 / 9 | 1.3. Chu kỳ sản xuất, kinh doanh thông thường | `artifacts/evidence/EXT-01/BCC_2025/responses-recovery/page-9-attempt-2.json` / `/text_elements/15` |
| BCC_2024 / 13 | Công ty mẹ của Công ty là Tổng Công ty Xi măng Việt Nam ("Tổng Công ty"). | `artifacts/evidence/EXT-01/BCC_2024/responses/page-13.json` / `/text_elements/10` |

## 11. Root Causes & Fixes

| Earliest failing stage | Finding | Xử lý trong EXT-01 |
|---|---|---|
| Extraction | Một số paragraphs bị chia theo dòng; trang 9 BBS 2025 lặp đoạn | Prompt giữ paragraph, bounded targeted recovery, giữ response ban đầu |
| Extraction | Bảng bị flatten hoặc khai báo thiếu cột | Không sửa raw theo suy luận; recovery có giới hạn, giữ layout unresolved nếu chưa đạt |
| Extraction | Recovery trang 13 BBS 2025 sửa thiếu từ nhưng đảo một mệnh đề thuế hoãn lại | Loại recovery, giữ bản đầu với caveat; không chọn output sai nghĩa chỉ vì schema PASS |
| Materialization | Windows từ chối một lần atomic replace khi ghi từng element | Response không mất; resume với atomic batch, giảm số lần ghi |
| Integration | Approved composition BBS chưa gồm financial page 6 | Bind accepted D-01 record, giữ snapshot/pointers gốc |
| Source quality | Bbox native cũ không phải pixel geometry | Review coordinates riêng; không sửa bbox cũ |
| QA context | “đường thẳng” trong quoted text bị normalize thành “thang” và nhận là kỳ tháng | Ghi limitation context parser; direct retrieval vẫn đo riêng; không nới M6 |
| QA intent/release | “Chu kỳ” bị hiểu thành “chữ ký”; heading và paragraph tạo hai exact claims khác nhau | Source đúng trang 9 BCC 2025 đã có; vẫn block do role requirements/ambiguous claims. Không sửa M5/M7 policy ngoài phạm vi |
| Verification | Semantic opinion và layout relation chưa được policy hỗ trợ | Giữ INVESTIGATE; không ép ACCEPT |
| Historical regression fixture | Q29 còn `semantic_role=null`; adapter GEN-01 trả `revenue` | Lưu diff một trường; adapter/inputs không đổi bởi EXT-01, không sửa ngoài scope |

## 12. Cost/Latency

Usage thực tế lưu trong `provider-usage.jsonl`, các `responses-recovery/*.usage.json`
và `last-run.json`. Known tokens cộng từ provider usage; unknown cost không được
đổi thành giá ước lượng. Số trang unique, page requests và provider attempts tách biệt.
Thời gian materialization/index và QA có trong metrics; không chạy M8/latency benchmark.
Tổng 107 page requests/107 provider attempts, 648.845 known tokens;
7 HTTP 503 có usage unknown, các mandatory page gaps đã recovery.
89 unique pages mới; 18 recovery requests qua các phiên bản riêng, mỗi trang tối đa
hai nhóm recovery. Không gọi lại trang để tăng test count hoặc đổi sang paid model.
Recorded Gateway/provider time 2.246,784 giây; materialization/index ở lượt offline
cuối 120,625 giây. QA trước/sau tổng thời gian hai lượt tương ứng 11,063/77,844 giây;
đây không phải benchmark so sánh latency vì corpus và cách khởi tạo khác nhau.
Provider không trả chi phí USD, nên cost giữ unknown dù cấu hình Free Tier.

Regression trên sources đã accepted: QA-01a 10/10; INT-01b 30 probes,
8/8 selection/rebuild controls, không leakage. Bộ QA tài chính cũ đạt 36/36
và restart exact, 18 metric assertions qua trước bước historical Q29.
Runner mở rộng dừng ở fixture Q29 nêu trên, **không báo full regression PASS**.
Runner tài chính cũ cũng tự kiểm tra hashes 2.670 protected inputs; đây là phạm vi
đọc rộng hơn dự kiến của EXT-01, không có OCR/LLM hoặc thay đổi dataset.
Không chạy lại runner rộng này; actual scores, responses và Q29 diff được giữ local.

## 13. Remaining Coverage Gaps

Không còn missing extraction page bắt buộc. Partial cells, unknown glyphs hoặc geometry unresolved
không được đổi thành verified facts. Visual checks do Codex thực hiện không thay
independent human gold set hoặc chứng minh financial accuracy toàn PDF.
Các lỗi còn biết: BBS 2025 trang 13 thiếu một từ “hoãn” trong OCR ban đầu;
recovery đã bị loại vì đảo nghĩa mệnh đề. BBS 2022 trang 11 có vài từ/qualifier bị thiếu;
native table flatten không thay thế accepted table cũ. Một số tables còn declared
extent khác cell indices; geometry model vẫn unresolved. Các visual caveats này được
giữ trong inventory và quality projection, không đánh dấu verified claim.

Visual review có một false positive tại BCC 2024 trang 26: crop phóng to xác nhận
`989.007.037` là số in thật và OCR đúng từ đầu; cờ nghi ngờ đã được gỡ, không sửa số.
Recovery 300 DPI trang 18 BCC 2025 cải thiện 11 fragments thành ba note table groups.
Không tuyên bố full OCR fidelity hoặc QA accuracy tăng chỉ từ page coverage.

## 14. Handoff EF-01

Không triển khai EF-01/QA-01b/M8. Bàn giao source-bound compositions, review caveats
và trace để Tech Lead nghiệm thu. GEN-01a/Web pending giữ riêng ngoài commit.
Next action: Tech Lead nghiệm thu hai điểm closure để quyết định DONE.

## 15. Closure theo CONDITIONAL APPROVAL

Tech Lead giữ EXT-01 ở REVIEW, cho phép source-quality gate M6 và đối chiếu Q29.
Implementation closure `faa662db8bc4008f6fd5c3374e55c7dff1a7df04` đã push main;
không gọi Gemini, chạy lại extraction hoặc hash audit.

P1 dùng chính `BBS_2025/responses/page-13.json`, `/text_elements/9`, truy vấn
`BBS 2025 ghi “thuế thu nhập lại phải trả” ở đâu?`. Đây là đoạn thiếu “hoãn”
đã đối chiếu PDF trang 13, không phải passage synthetic. Trước sửa M6 ACCEPT 1,
M7 xuất một citation; caveat chưa đủ để chặn lỗi. Sau sửa M6 INVESTIGATE với
`source_quality`, không admission, claim được dùng hoặc citation xuất ra.
Proof ACCEPT cũ bị rejected cả admission và đọc lại ledger
(`document_proof_not_accepted_on_replay`). Trace trước/sau và nguyên văn nguồn
giữ local tại `artifacts/evidence/EXT-01/closure/{before,after}/negative-qa.json`.

Gate dùng cờ lỗi `pdf_review:*` lấy từ evidence đã resolve, không phụ thuộc việc
candidate có lặp lại caveat. Review hiện gắn cờ theo trang, nên mọi record mang cờ
trên trang lỗi đều không được ACCEPT, kể cả phần khác có thể đọc đúng. Đây là
giới hạn bảo thủ có chủ đích; chưa triển khai phân vùng review. Các caveat thông
thường không mang cờ lỗi PDF không tự động bị chặn. Không thay raw OCR,
repository, composition hoặc bản recovery đã bị loại. Proof v1 sạch giữ nguyên
để ledger cũ hợp lệ vẫn replay. Các số QA ở phần trước là kết quả trước closure,
không dùng làm kết quả sau gate.

P2 xuất riêng code baseline trước EXT-01
`718707503a55fccc023d465645506954ea0df26b`, import package/adapter từ bản xuất đó,
chạy duy nhất Q29 với cùng persisted inputs. Toàn bộ output baseline bằng output
EXT-01; so fixture lịch sử chỉ khác `/matches/0/record/semantic_role`:
expected `null`, baseline và EXT-01 đều `revenue`. Bằng chứng tại
`artifacts/evidence/EXT-01/closure/Q29-baseline.json`; không sửa fixture và không
báo extended suite PASS. Không phải hồi quy do EXT-01.

Local closure: 91 tests PASS trong `test_document_qa_pipeline.py`,
`test_verified_claim_ledger.py`, `test_information_firewall.py`, gồm hai cases mới
cho known PDF defect và caveat thông thường. Ruff lint/format, planning và
`git diff --check` PASS.
[CI42345964918](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42345964918)
completed/SUCCESS đúng SHA closure `faa662db8bc4008f6fd5c3374e55c7dff1a7df04`:
1.117 Python/9 Web smoke PASS; lint/format/planning/typecheck/build đạt;
full unit regression manual SKIPPED. Giữ REVIEW, chờ Tech Lead quyết định DONE.
