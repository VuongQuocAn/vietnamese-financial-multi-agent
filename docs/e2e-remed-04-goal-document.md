# E2E-REMED-04 — Goal Binding & Document Evidence

Ngày17/11/2026 (Asia/Bangkok). **DONE có giới hạn — Owner/Tech Lead chấp nhận
kết quả kỹ thuật và đóng task; chưa giải quyết trọn luồng live MH0001**. Implementation
`bac7362e07a81ca0ab1f3c0812315df72e58a539`, baseline52237cf; worktree riêng giữ
80local edits. Không sửa M7, raw JSON, EF-EG, ledger cũ hoặc nới ACCEPT/Obligations.

Nghiệm thu phạm vi kỹ thuật và RCA theo xác nhận Owner/Tech Lead ngày17/11/2026;
giữ các giới hạn bên dưới, không xác nhận readiness Pilot hoặc core live hoàn tất.
Bàn giao d659971 đã push main/remote verified. Phiên đóng chỉ tài liệu/tracking,
planning/diff và Git; không sửa runtime/artifacts hoặc chạy lại tests/Qwen/benchmark/CI.

## RCA và thay đổi

- “Hàng tồn kho” cùng span khớp cả inventory_total/gross; planner từng biến hai
  aliases thành hai nghĩa vụ đồng thời. M6 loại binding của comparison dù verdict
  SUPPORTED/G1. Nay giữ alternatives, không chọn nghĩa kế toán; indicators ghi rõ
  vẫn bắt buộc. M6 còn kiểm operands/kỳ/unit/operation và semantic goal support.
  Scalar đúng hoặc arithmetic khác không tự thỏa câu hỏi chọn khoản mục lớn hơn.
- Document lane trước chỉ tìm text/source_excerpt; BM25 bảng thiếu title. Nay
  index title đã pin và thêm candidate `table_selection` trong lane hiện có.
  Specialist chỉ chọn đề xuất có provenance; M6 resolve lại source/composition/
  citations và replay toàn miền bằng Decimal. Giữ aggregates/exclusions/ties;
  thiếu cột ngày/VND, dòng chưa phân loại, missing, continuation hoặc tổng không
  đối chiếu được thì không tạo kết luận. Không promote raw cells thành canonical.
- Query subject chỉ lấy từ comparison đã release qua ledger. JSON citations giữ
  pdf_page=None và source page/hash; sửa document replay từng đòi PDF page ngay cả
  với JSON, đồng nhất quy tắc fidelity đã có ở EvidenceContextBuilder.

## Bằng chứng offline

Saved MH trace/verdict replay: vẫn3ACCEPT, **chỉ comparison bind G1**, hai scalar
không có goal support; trước0/1→sau1/1 cho goal tài chính được replay. Không sửa
saved evidence hoặc coi replay verdict cũ là Qwen live mới.

JSON thật: tìm bảng trang14, đủ7đối tượng nêu tên riêng; nhóm khách hàng khác và
Cộng được giữ trong proof nhưng loại khỏi named domain. Candidate chọn đúng
Tam Điệp34.110.286.767VND; M6 ACCEPT và pipeline document standalone phát hành
31citations với caveat JSON-only. Tamper content/snapshot bị chặn. Một Gateway
control giả lập **chọn index**, không giả lập dữ liệu/M6, đi qua nhánh Specialist→
M6→ledger→M7. Đây là engineering integration, chưa là live Multi-Agent success.

3controls mới và44compatibility **47unique PASS**;1legacy deterministic Coordinator
FAIL tái hiện y hệt tại baseline52237cf. Nhóm liên quan: goal binding, obligations,
document/fusion/search/coordinator. Sau guard cuối,9goal/obligation controls PASS.
Ruff lint/format, planning checker và diff check PASS; không fullsuite/fullCI.

## Live retest cố định và quyết định dừng

Freeze trước live, cùng corpus pin: BBS/ADC dùng REMED03 projection, các filings
khác byte-copy snapshots hiện có; không reimport. Đúng2saved questions, cap20calls
tổng/10mỗi câu, Gateway request300s; không retry transport/model tuning hoặc vòng FIX.
Gold chỉ hậu kiểm từ bản Gold đã lưu cho9QA, không vào runtime.

| QA | Trước REMED03 → sau | Goal coverage trước→sau | Calls trước→sau | Wall s sau | Released citations sau |
| --- | --- | --- | --- | ---: | ---: |
| MH0001 | verification_blocked → provider_unavailable |0/4→0/9|8→9|360,383|0|
| NR0001 | completed_with_caveats → completed_with_caveats |1/1→1/1|5→5|199,212|7|

Hai câu: **1correct/1abstain**, accuracy50%→50%, answer coverage50%→50%, citations
7→7; calls13→14, cộng wall399,842→559,595s. **103.724known tokens/2unknown usage**
ở14actual Qwen calls;7/7released citations resolve đúng JSON/hash/pointer/claim.
NR vẫn tăng10,56%, đúng Gold. Đây không phải accuracy mới của9QA/Pilot45.

MH live: raw FusionPlanner thiếu typed document_requirement, fallback tạo nhiều
financial requirements và mất dependency document. Coordinator thêm task đầu năm
ngoài nhu cầu cuối năm;7candidates cùng task closure vượt48K semantic payload cap.
M6 semantic_calls=0,2ACCEPT scalar/5INVESTIGATE, không verified binding. Hai calls
timeout có usage unknown; document lane tới sau khi hết budget,0candidate. Goal
sets khác nhau0/4 và0/9 nên không coi đây là cùng phân rã để đo cải thiện coverage.
Gateway deadline không là hard wall cap toàn tool/hậu xử lý; wall MH360,383s.

Giới hạn binding khác: NR Planner gán goal số học thành analysis; semantic support
G1 gồm cả hai scalar premises. Final answer đúng không xác nhận mọi binding đều
chính xác. Không sửa tiếp hoặc tuyên bố core đạt hoàn toàn từ kết quả NR/offline.
**Dừng RCA; không chạy lại9QA**, không36Pilot/Full600/OCR/Gemini.

## Evidence và bàn giao

Local `artifacts/evidence/E2E-REMED-04/`: `offline-replay.json`,
`comparison.json`, `integrity-audit.json`, `retest-two/{receipt,provider,results,ledgers}`
và `review-gate.json`=false.189runtime/264source JSON/115imported pins/3Pilot hashes
khớp receipt;80local files/185parent evidence files nguyên byte. M7 Git blobs không
đổi; không có credentials trong task artifacts/staged files. Dataset/private evidence
không được stage. Implementation và handoff được push main, remote SHA ghi trong
`publication.json`; không gán CI hoặc financial/PDF accuracy cho engineering tests.

Next action: chờ Owner/Tech Lead giao nhiệm vụ tiếp theo.
