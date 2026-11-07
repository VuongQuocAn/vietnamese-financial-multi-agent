# QA-01a — Kiểm chứng claim từ tài liệu

## 1. Kết quả

Quick QA trên evidence lưu từ PDF thật đạt 10/10 kỳ vọng. Bốn claim ACCEPT và
được nhập Ledger. Sáu claim nhãn chức vụ vào INVESTIGATE và bị Ledger từ chối.
Không có REVISE hoặc ABSTAIN ở cấp candidate trong bộ Quick QA.

## 2. Thành phần tái sử dụng

M5 dùng EvidenceAwareQueryPlanner, RiskAwareSupervisor và FinancialMultiAgentOrchestrator.
M4 dùng `search_document_evidence` và `get_evidence_sources` trên composition đã
qua preflight INT-01a. M6 dùng EvidenceContextBuilder và một nhánh quyết định xác
định cho document proof. M7 dùng VietnameseQAComposer, CitationRenderer và
InformationFirewall trên cùng Verified Claim Ledger.

## 3. Luồng ứng dụng

`FinancialQAPipeline.run` nhận câu hỏi tiếng Việt và metadata tài liệu của caller.
Luồng document chọn đúng một logical PDF và approved composition. Câu hỏi lẫn
chỉ tiêu tài chính và nội dung tài liệu trả unsupported. Nhiều PDF phù hợp trả
clarification. Kỳ chi tiết hoặc phạm vi báo cáo chưa có binding riêng cho
document QA cũng trả clarification.

## 4. Contracts và tương thích

DocumentCandidate v1 lưu logical ID, source document/snapshot, composition
fingerprint, references, quotations, caveats và citations. Period để null.
VerifiedDocumentClaim v1 cùng lưu trong JSON Ledger. Truy vấn document yêu cầu
composition fingerprint, tài liệu và các điều kiện nguồn. Các truy vấn tài chính
mặc định đọc các entries tài chính như trước.

## 5. M5

Một typed search operation cho mỗi yêu cầu, với tối đa năm hits mỗi operation.
Search trace lưu request đã bind, status, IDs bao gồm neighbor, snapshot,
page và lý do xếp hạng. Candidate dùng đoạn văn, quan hệ ghi rõ trong cùng dòng,
hoặc nhãn hàng có tọa độ logic từ TableEvidence.

## 6. M6

M6 phân giải lại reference qua M4 từ catalog đã kiểm tra pins. Policy đối chiếu
identity, citation gốc, nội dung, caveat và quan hệ. Đoạn B09 chỉ ghép các vùng
liên tiếp trên cùng page, snapshot và request của nguồn. Tên và chức vụ từ các
vùng độc lập chưa đủ cho ACCEPT. Khi có cặp ghi rõ, câu trả lời quy nội dung cho
tài liệu. Document policy dùng ACCEPT, INVESTIGATE hoặc ABSTAIN. Với claim
thiếu nguồn hay quan hệ, policy giữ nguyên proposition để kiểm tra, không tự
sửa tên hoặc ngữ nghĩa. Financial Judge và bounded revision giữ luồng hiện có.

## 7. Ledger

Ledger replay policy từ proof M6 rồi mới lưu atomically. Cache hit đọc đúng
composition và kiểm tra lại pins của composition hiện tại. Test restart xác
nhận ledger đọc được cả version document và giữ period null.

## 8. M7

Composer và Firewall lập lại danh sách yêu cầu từ request. Firewall đối chiếu
các protected slots, yêu cầu chưa đáp ứng, văn bản hiển thị, admitted IDs và
citations. Partial chỉ phát hành các yêu cầu có claim phù hợp. Bảng chỉ dẫn các
nhãn đọc được và giữ provenance cấp trang.

## 9. Ba ca PDF thực

| Câu hỏi | Trả lời thực tế, trích phần nội dung | Nguồn và trace |
| --- | --- | --- |
| Ai là người ký báo cáo tài chính BBS năm 2025? | Chưa có đủ claim đã xác minh cho yêu cầu này trong ledger. Người lập, Kế toán trưởng và Giám đốc đều còn thiếu căn cứ. | BBS 2025 trang 7 và 8. M5 chạy 3 searches, lấy nhãn và vùng liền kề. M6 phân giải 3 refs, cả 3 INVESTIGATE. Ledger từ chối cả 3. M7 abstained, Firewall ALLOW phần thông báo, không phát hành citation. |
| Thuyết minh BBS năm 2025 nói gì về nhân viên quản lý chủ chốt? | Tài liệu ghi «Các nhân viên quản lý chủ chốt có quyền và trách nhiệm về việc lập kế hoạch, quản lý và kiểm soát các hoạt động của Công ty: Những người lãnh đạo, các nhân viên quản lý của Công ty và các thành viên mật thiết trong gia đình của các cá nhân này.» | BBS 2025 trang 14, `/text_elements/4`, `/text_elements/5`, `/text_elements/6`. M5 BM25 và 2 neighbors tiếp nối. M6 phân giải 3 refs và ACCEPT. Ledger stored. M7 answered, Firewall ALLOW_WITH_CAVEAT, 3 citations gốc. |
| Báo cáo BBS 2025 trình bày những khoản mục tiền nào trong bảng tiền? | Các khoản mục đọc được trong bảng tiền gồm Tiền mặt, Tiền gửi ngân hàng. | BBS 2025 trang 14, `/tables/0` và `/cells/6`, `/cells/9` trong bảng. M5 BM25 table hit. M6 phân giải TableEvidence và ACCEPT nhãn hàng. Ledger stored. M7 answered, Firewall ALLOW_WITH_CAVEAT, 3 citations gốc. |

Ảnh PDF BBS trang 14 và original Gemini JSON khớp đoạn B09 và hai nhãn hàng.
Expected B09 và bảng được đọc từ file Gemini ban đầu trước khi chạy QA. Quick QA
còn xác nhận heading BBS trang 15, heading BCC 2025 trang 7, câu thiếu nguồn
opinion, chọn PDF mơ hồ, câu mixed, truy vấn nhầm công ty và câu ba chức vụ.

## 10. Lỗi và sửa

- M5 ban đầu khởi tạo planner tài chính bằng metadata chưa có trong financial
  catalog. Luồng document chuyển binding sang composition đã pin.
- Test tổng hợp ban đầu dùng ID nguồn thiếu SHA PDF và bị M4 từ chối đúng policy.
  Fixture dùng identity SHA hợp lệ, giữ logical ID riêng.
- Oracle yêu cầu bảng chỉ trích nguồn cho nhãn hiển thị. Projection lọc citation
  theo bảng và các cell nhãn được dùng.
- Nhánh mixed giữ cả ý định document và yêu cầu tính/đọc chỉ tiêu. Quick QA kiểm
  tra lại để chặn việc trả lời phần document rồi bỏ phần còn lại.

Trace đầy đủ, expected và actual answers nằm trong
`artifacts/evidence/QA-01a/verified-run/quick-qa.json` (local). Median end-to-end
khoảng 0,79 giây trên máy local, kể cả hai ca dừng ở context/routing. 0 Gemini
calls, 0 tokens, 0 OCR. Luồng xác định chạy được với Gateway giả lập lỗi; chưa
xác minh provider live hay semantic planner/critic bằng task này.

## 11. Hồi quy

426 test local đạt trước bản sửa định tuyến. Sau sửa, 67 test liên quan
đạt và Quick QA đạt lại 10/10. Sáu test planning đạt. Implementation `d2b28634adc6a24b0d019de00897cbf3ce26a781`
đã push main. CI trên đúng SHA đạt SUCCESS ở Python 3.12 và Web smoke. [CI42318884258](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42318884258)

Hồi quy local bao phủ planner, supervisor, orchestrator, validators, critics,
Judge, Ledger, Composer, Firewall, citation và financial pipeline. Ba test
document kiểm tra các đối chứng sửa tên/quan hệ/trang/snapshot/composition,
candidate chưa ACCEPT, request khác, partial và cache khi Gateway lỗi.

## 12. Giới hạn

Nguồn ký BBS có nhãn và tên tách rời, chưa có liên kết vị trí được xác minh.
Đoạn ý kiến kiểm toán nằm ở BBS 2025 trang PDF 4 (trang in 3), ngoài phạm vi
composition của ca kiểm thử. Vị trí được đối chiếu qua ảnh render từ PDF. QA hỗ trợ mẫu định tuyến xác định và tìm cụm
trích dẫn, chưa hiểu mọi cách hỏi tự do. Hybrid QA thuộc QA-01b.
