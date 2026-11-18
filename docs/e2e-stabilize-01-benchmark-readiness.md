# E2E-STABILIZE-01 — Bàn giao theo lệnh dừng

Ngày 18/11/2026 (Asia/Bangkok). **REVIEW — Owner yêu cầu dừng**. Implementation
`7b06babef9cad02c8ad894c3c0adb7f1babd5221`, baseline `bdf2fd7`. Không gửi thêm
QA/API hoặc sửa runtime sau lệnh dừng. Giữ mọi lượt dở và checkout gốc/80 local
edits. Không sửa server/model/context24K/raw/EF-EG/Gold/M7/Obligations hoặc nới ACCEPT.

## Lỗi đã sửa và bằng chứng

- **M5 mất mục tiêu:** giữ goal nguyên câu hỏi thành task có owner/dependencies,
  giữ DAG/roles hợp lệ; fallback provider/payload vẫn sở hữu câu hỏi. Control và
  saved MH replay PASS. Chưa bảo đảm model phân rã hoặc giải đúng mọi yêu cầu.
- **Retrieval sai lane/bỏ bảng:** literal lookup giữ cả câu, tránh tách tên/chủ đề
  tại “và”, tìm text/table và trích một dòng đầy đủ cùng title/headers/citations.
  Real-JSON smoke và live SH0006 đúng nguồn, 11 citations; M6 replay source/hash,
  không promote raw cells thành canonical.
- **M6 JSON/verdict/timeout:** chỉ phục hồi JSON hoàn chỉnh có dấu đóng thừa;
  giữ strict schema/duplicate/identity gates. Repair verdict thiếu tối đa một lần,
  giữ proof đã verified, không retry timeout. Offline timeout-preservation PASS;
  lượt `67405ff` phục hồi hai JSON verdict lỗi, vẫn giữ các gate ACCEPT/goal.
- **Model chép sai claim hash:** `7b06bab` dùng wire handles C1/C2, map exact về
  identity gốc; unknown/duplicate không được đoán hoặc fuzzy-match. Unknown handle/
  ledger control PASS; live final SH0001/MH0001 đi qua M6/ledger với protocol mới.
  NR0001 chưa được live xác minh lại sau fix.
- **Payload/budget:** chia sẻ lossless object nguồn lặp; clamp output trong context
  24576 theo estimate ceil(chars/2), reserve1024; stage180s/request600s hữu hạn.
  Saved prompt 44.498→30.780 ký tự, 15 roundtrips exact. Nhánh từng HTTP400 chạy
  thành công sau sửa; nguyên nhân context của400 cũ là suy luận từ payload/retest,
  không có raw server message để khẳng định. HTTP400 không khóa nhánh độc lập.

**15 targeted PASS trên code cuối**: ba controls mới cùng Thinking/obligations/
goal/document compatibility. Nhóm rộng trước đó 41PASS/2legacy FAIL; cả hai tái hiện
trên baseline `bdf2fd7`: deterministic Coordinator opt-out và v1 operand_bindings.
Sau lệnh dừng chỉ audit offline, Ruff/planning/diff; không chạy lại tests/model,
fullCI/fullsuite/OCR/Gemini. Engineering PASS không thay financial evaluation.

## Kết quả thực tế

**Code cuối chỉ hoàn thành 4/9 QA: 2 correct, 1 partial, 1 abstain.** Accuracy trên
bốn câu hoàn tất là50%; released-answer coverage75% (gồm partial), full-answer
coverage50%. **Không có score9QA/Pilot45**; không gộp các runtime thành accuracy.
Không dùng ngưỡng accuracy để quyết định readiness.

Có15 lượt QA hoàn tất trên7ID duy nhất. Bảng giữ output hoàn tất gần nhất cho mỗi
ID; ba câu thuộc runtime cũ được ghi rõ, không coi là đã retest trên code cuối.

| QA | Kết quả hoàn tất gần nhất | Runtime | Calls | Wall s | Citations |
| --- | --- | --- | ---: | ---: | ---: |
| SH0001 | Đúng | 7b06bab | 4 | 152,930 | 6 |
| SH0006 | Đúng | 7b06bab | 1 | 71,495 | 11 |
| SH0013 | Abstain / hệ thống | 7b06bab | 1 | 96,046 | 0 |
| MH0001 | Partial / model | 7b06bab | 8 | 503,825 | 6 |
| MH0006 | Abstain / transport và model | 67405ff | 3 | 241,148 | 0 |
| MH0013 | Abstain / model-evidence | 67405ff | 2 | 145,932 | 0 |
| NR0001 | Lỗi kỹ thuật trước fix | 67405ff | 8 | 425,204 | 0 |
| NR0006 | Chưa hoàn tất; hai attempts ở67405ff | — | — | — | — |
| NR0013 | Chưa chạy live | — | 0 | — | — |

IDs trong bảng có tiền tố `VFB-`. Gold chỉ hậu kiểm output hoàn tất, không vào
runtime; chưa có reviewer độc lập hoặc PDF verification. MH0001 chỉ phát hành đúng
số dư tồn kho, thiếu so sánh và đối tượng thuyết minh nên không nhận điểm correct.

## Tài nguyên tất cả lượt

| Lượt | SHA | QA hoàn tất | Attempts / responses | Known tokens / unknown usage | Wall QA hoàn tất s | Known transport s |
| --- | --- | ---: | --- | --- | ---: | ---: |
| live-nine | e812799 | 0 | 0 / 0 | 0 / 0 | 31,616* | 0 |
| live-nine-final | cedb3ea | 4 | 15 / 14 | 69339 / 3 | 611,455 | 752,575 |
| live-release | 67405ff | 7 | 29 / 28 | 171146 / 2 | 1659,514 | 1554,580 |
| final-nine | 7b06bab | 4 | 15 / 14 | 85163 / 1 | 824,296 | 713,514 |

**Tổng 59 API attempts/56 responses**, 284.712 input +40.936 output =
**325.648 known tokens/6 unknown usage**. Ba attempts bị ngắt chưa có response;
usage chưa biết không tính thành0. Output count có thể gồm Thinking.

\* Lượt đầu có chín runner exceptions vì request600s vượt contract300s, xảy ra
trước API; đã giữ nguyên. Sau đó nâng bounded cap và thêm preflight.

Known transport cộng3020,670s; wall của15QA hoàn tất cộng3095,265s, launcher lỗi
31,616s. Từ receipt đầu đến lệnh dừng4270,504s (71phút10,504s), gồm offline/gaps;
riêng code cuối từ receipt đến dừng964,732s, bốn QA hoàn tất824,296s. Không cộng
chồng wall với transport; ba calls dở không có latency kết thúc nên không báo
tổng inference time hoặc latency đủ cho9QA.

## Lỗi còn lại và readiness

- **Hệ thống/transport:** MH0006 có HTTP524 sau125,586s ở67405ff. Fallback giữ
  câu hỏi và Specialist tiếp tục; M6 chưa đủ full goal support. Call ở7b06bab bị
  Owner ngắt, chưa có verdict; không quy lỗi transport thành corpus absence.
- **Hệ thống/document-release:** SH0013 đã tìm đúng bảng, nhưng clause trong cell
  hợp đồng chưa thành literal-row proof; legacy release còn hiểu ngày hợp đồng
  thành reporting period. Không sửa M7 để cứu đáp án.
- **Định danh đã sửa, chưa live xác minh lại NR:** ở67405ff, NR0001 tính đúng nhưng
  model chép sai hash, lặp lại khi repair và kết thúc internal_error với
  `semantic_verdict_missing_or_invalid`. Short handles đã có15controls PASS và live
  ở câu khác; không tuyên bố NR0001 đã thành công trên7b06bab.
- **Giới hạn model/evidence đủ điều kiện:** MH0001 thiếu comparison/goal coverage;
  MH0013 chưa có candidate/domain/entity-join đủ căn cứ. Scalar/local binding
  không thay full original goal. Không kết luận raw corpus thiếu dữ liệu từ
  retrieval miss hoặc ghi correct chỉ vì phép tính/claim trung gian đúng.

**Chưa đủ bằng chứng xác nhận readiness Pilot45/technical gate sạch:** code cuối
chưa hoàn thành9QA và còn các giới hạn trên. Đây không phải quyết định theo
accuracy. Kết thúc ở REVIEW theo Owner; không tự mở FIX/REMED hoặc chạy tiếp QA.

## Integrity và artifacts

190runtime Git blobs khớp implementation;264JSON/115imported pins/3Pilot hashes,
297parent và68prior evidence files,80local files bất biến.63released citation/
pointer occurrences qua các lượt resolve đúng JSON/hash/claim membership; đây là
source fidelity, không chứng nhận PDF hoặc mọi goal binding đúng. M7/Obligations/
notebooks không đổi; credentials không xuất hiện trong artifacts/commit diff.

Artifacts local, không commit dataset/private traces:
`artifacts/evidence/E2E-STABILIZE-01/`. Giữ nguyên `live-nine/`, `live-nine-final/`,
`live-release/`, `final-nine/`, gồm questions/receipts/provider requests-responses/
results/ledgers/wire metadata, kể cả ba provider files chưa có response.
`stop-summary.json`, `stop-metrics.json` có từng agent/tool/calls/tokens/time;
`stop-reviews.json`, `stop-integrity-audit.json`, `preserved-artifacts.json` lưu
hậu kiểm và hashes. Các controls/replays trước đó cũng được giữ.

Implementation đã commit; push main và remote SHA được xác minh tại bàn giao.
Checkout gốc giữ nguyên, bản chạy nằm trong worktree riêng. Không suy CI từ local.

Next action: Tech Lead review bàn giao và quyết định Pilot45, không tiếp tục REMED theo từng QA.
