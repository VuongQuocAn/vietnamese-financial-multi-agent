# QWEN-GEN-02 — Pipeline Generalization Fix

Ngày 12/11/2026; **DONE — điều kiện focused numeric binding fix của Tech Lead đã đạt**.
Implementation `451d9fd52bca3c32075cce867d832ff854f0ae1e` đã commit/push main, remote SHA verified; baseline `8f9fde9ae20a46515193183943a20fa47c77b4c8`
cùng các local edits/dependencies có sẵn. DONE trong phạm vi Tech Lead cho phép sau focused regression, không phải nghiệm thu chất lượng tài chính tổng quát.

## Kết quả

Đã triển khai bốn nhóm thay đổi nhỏ và dừng sau một smoke bốn câu.
Không thêm agent/verifier, không thay thiết kế pipeline, không chạy lại 25 câu
hoặc full CI. Runtime không thay đổi trong lượt smoke. Sau đó Tech Lead cho phép đúng một focused offline fix, ghi ở phần cuối; không gọi API thêm.

- **M5:** mapped facts trong đúng company/document/snapshot đi vào inventory
  theo statement B01/B02/B03, thay vì bị loại vì thiếu tên trong ITEM_LABELS.
  Specialist dùng nhãn của các facts được Tools giao, vẫn giữ identity, source
  review, quality/citation validation. Không tự chuẩn hóa chỉ tiêu chưa mapped.
  Scope filter dùng resolver hiện có, không bắt facts gốc phải được sửa scope.
  Supervisor được nhắc chọn metric đúng tên và không thay mục tiêu thiếu bằng
  chỉ tiêu gần giống. Đây là prompt guidance, không bảo đảm model luôn chọn đúng.
- **M6 semantic:** trong cùng batch hiện có, thêm evidence_id → canonical
  item/value/period/unit và operation input → typed operand bindings. Prompt
  yêu cầu kiểm tra đúng định nghĩa/vai trò operands và các qualifiers như trạng
  thái kiểm toán, không chỉ arithmetic. Không thêm call hoặc tầng verification.
  Projection bổ sung chỉ từ supporting evidence đã có trong verification input;
  legacy semantic payload digest giữ nguyên để các ledger đã lưu còn replay được.
  Không thay verdict schema hoặc tự sửa claim.
- **M7:** kế thừa các yêu cầu số liệu/dấu/phép tính của câu trước; phục hồi các
  mục tiêu catalog bị parser đơn kỳ đánh dấu unsupported vì nhiều năm. Kiểm tra
  các kỳ, nguồn và accepted proof; một phép tính có thêm bước hợp lệ không làm
  mất bước đã được hỏi. Yêu cầu causal/unknown và thiếu accepted conclusions
  vẫn không được coi là covered. Không bỏ tất cả các unsupported goals.
- **Reporting scope:** claim selection có thể dùng ReportingScopeResolution
  confirmed hiện có, nhưng chỉ khi đúng document/snapshot/scope yêu cầu.
  Không tạo scope review mới, không bỏ gate scope unresolved, không cấp phép
  so sánh liên tài liệu và không sửa scope/caveats của source/ledger gốc.
- **B09 và harness:** câu hỏi phương pháp/cơ sở/ngoại lệ của chính sách không
  tự thành financial scalar request chỉ vì có từ “giá trị”. Conjunct hỏi số
  riêng vẫn giữ mixed intent. Harness mới không truyền financial snapshot
  vào pure document request; search chỉ dùng verified pins của composition.
  Caller chỉ định snapshot rõ ràng vẫn được runtime kiểm tra như trước.

## Offline validation

**38 targeted tests PASS**, gồm ba tests mới và các nhóm liên quan:
`test_qwen_generalization`, `test_m5_lite`, `test_m6_lite`,
`test_qa_lite_coverage`, `test_qa_lite`, `test_document_qa_pipeline`.
Không coi fixtures synthetic là bằng chứng financial accuracy.

Saved evidence QWEN-GEN-01 được đọc, không ghi đè:

| Probe | Kết quả |
| --- | --- |
| M7 Q04/Q06/Q07/Q13: giữ nguyên ACCEPT contents/proofs | 4/4 chuyển completed_with_caveats, không Gap B giả |
| Cùng bốn câu, chỉ giao fact claims và bỏ conclusions | 4/4 vẫn partial/blocked, không tự suy coverage |
| Q01/Q02/Q05 facts đã có nhưng trước thiếu inventory | 3/3 có đúng canonical item trong inventory |
| Q16/Q18/Q20 note routing + composition search không khóa snapshot tài chính | 3/3 truy xuất được toàn bộ reference records trong bounded result pool |
| Synthetic scope controls | confirmed cùng owner được giữ; thiếu confirmation hoặc snapshot khác vẫn bị loại |
| Synthetic M6 request | một semantic call, có đúng IDs/operand bindings và nghĩa vụ kiểm tra definition/qualifiers |

Các replay M7 kiểm tra selection/coverage từ claims đã lưu; không tái xác minh
tài chính hoặc chạy lại Qwen. Control M6 kiểm tra payload/contract, **không chứng
minh model sẽ bác mọi claim sai định nghĩa**. Không có adversarial semantic
benchmark bổ sung trong ngân sách task này.

Ruff lint/format, planning checker và git diff checks là kiểm tra bàn giao.
Offline helper/evidence ở `artifacts/evidence/QWEN-GEN-02/` được Git ignore.

## Smoke API thật — đúng một lượt bốn câu

References lấy từ tập đã freeze của QWEN-GEN-01 trước khi gọi API. Bốn case gồm
fact ngoài inventory cũ, phép tính, B09 và negative control. Không chọn lại case
hoặc thay prompt theo kết quả. Một preflight nhẹ; Qwen alias `qwen3-8b-awq-t4`
qua SharedLLMGateway, cấu hình/key local ignored, không log URL/key.
Mỗi case ledger mới, tối đa 6 calls/300s, không retry/fallback model.

| Case | Expected | Kết quả cuối | M6 | Calls / tokens | E2E |
| --- | --- | --- | --- | --- | --- |
| Q05, giảm trừ doanh thu BCC2025 | 173.405.357.408 VND | **FAIL**: M5 đã chọn đúng fact và numeric candidate, nhưng final verification_blocked | INVESTIGATE2 | 2 / 4827 | 18,092s |
| Q13, chênh lệch PAT BBS2025/2024 | 1.059.972.358 VND, đúng operands/phép trừ | **PASS**, completed_with_caveats, nguồn PDFp7; không Gap B | ACCEPT4, một semantic call | 4 / 10604 | 44,700s |
| Q20, ngắn/dài hạn vay BCC2025 | Trên12tháng dài hạn; đến hạn trong12tháng tiếp theo ngắn hạn | **PASS**, trích đủ đoạn PDFp13, completed_with_caveats | ACCEPT1 document | 1 / 662 | 10,345s |
| Q25, doanh thu khách hàng không có trong nguồn | Không bịa doanh thu khách hàng | **PASS về abstention disposition**, verification_blocked, không phát hành con số; giải thích vẫn chung chung | Không candidate | 1 / 2930 | 3,647s |

Tổng smoke **8 evaluation calls/19023tokens**, cộng preflight
**9 calls/19046tokens** (17972input+1074output); 0provider errors/retries.
Runtime hashes giữ nguyên từ trước smoke đến cuối smoke. Đây là **3/4 smoke
dispositions phù hợp**, không phải measured accuracy/generalization score sau sửa.

Q20 đi nhánh DocumentPlanner/BM25/document verification hiện có và M7 legacy;
không phải mọi case đều thực thi M6/M7 Lite. Q25 không tạo Specialist claim;
không coi safe fallback là chứng minh Qwen suy luận đúng nguồn khách hàng.

## Thiếu hụt còn lại và phạm vi kết luận

**Tại checkpoint smoke, Q05 chưa được sửa end-to-end.** M5 nay giao đúng 173.405.357.408 VND và model
không lặp phép tính nhầm lợi nhuận gộp. Tuy nhiên grammar
`verification.numeric.extract_assertion` còn dùng nhãn của Specialist cũ.
Chỉ tiêu mới không bind được, tạo `content_period_unbound` và
`numeric_assertion_not_unambiguously_bound`; semantic verifier chưa được gọi
cho case này. Không nên mở rộng inventory được xem là đã đủ nếu grammar M6
chưa hỗ trợ các facts được mở thêm. Lỗi này được báo riêng, không gán model
không tìm được nguồn hoặc báo Q05 PASS chỉ vì số đúng trong trace.

Tại checkpoint trước chỉ đạo focused cuối, dừng ở kết quả smoke và chưa sửa thêm runtime. Chỉ đạo mới của Tech Lead cho phép focused binding fix ở phần sau, không chạy thêm live API. Prompt/bindings M6 tốt hơn chưa đủ bằng chứng để
tuyên bố false semantic acceptance Q02/Q05 lịch sử đã được loại bỏ tổng quát;
không replay verdict SUPPORTED cũ như bằng chứng chất lượng của prompt mới.

M7 coverage đã được kiểm tra trên bốn failures và missing-conclusion controls,
không phải tất cả dạng diễn đạt. Chưa sửa quy tắc rounding một chữ số của Q09,
quarterly-period capability, mọi alias/formula hoặc toàn bộ source/scope coverage.
QWEN-GEN-01 giữ REVIEW. QWEN-GEN-02 được chốt DONE sau focused final fix theo điều kiện Tech Lead ở phần sau; không mở task sửa tiếp.

## Evidence và bàn giao

- `baseline.json`, `before/`: baseline và các source files trước sửa.
- `coverage-replay.json`, `binding-controls.json`, `offline.py`: offline evidence.
- `smoke-references.json`, `smoke-freeze.json`: reference và runtime hashes.
- `live-01/{Q05,Q13,Q20,Q25}.json`, ledgers, `provider-events.json`,
  `results.json`, `runtime-hashes.json`: answers, Tools, claims, verdicts,
  citations và usage có thể đọc lại offline, không cần API.
- `completion-receipt.json`: hashes và validation cuối; implementation SHA và remote receipt được xác minh sau focused final fix.

Harness dùng lại các loaders/pipeline hiện có:
`scripts/smoke_qwen_generalization.py`; không xây evaluation framework mới.
Giữ source provenance, dataset và local edits khác; không stage dữ liệu/secrets.

Next action: **dừng chuỗi QWEN-GEN, chờ Owner giao nhiệm vụ mới**.


## Focused closure theo chỉ đạo Tech Lead

Tech Lead cho phép đúng một chỉnh sửa cuối trong cùng QWEN-GEN-02, kiểm tra
offline, commit/push và DONE nếu grammar được giải quyết không tạo false ACCEPT.
Không mở task FIX mới hoặc tối ưu theo từng câu.

**Chẩn đoán chính xác:** đây không phải lỗi dấu phân cách hay giá trị sai.
Parser `parse_number` đã đọc cả `173.405.357.408`, `173405357408` và
`173405357408,00` thành Decimal173405357408 từ trước sửa. Source raw ở BCC2025
PDFp7 là `173.405.357.408`; normalized=173405357408, item=
`b02.revenue_deductions`, period2025, unitVND/scale1. Source fact/link IDs và
selectors được giữ trong local diagnostic, không đổi source data.

Hai candidates bị chặn trong smoke:

- Fact backend `candidate:0bc3780d1a4f5390c00be052`: `2. Các khoản giảm trừ doanh thu kỳ 2025 là 173.405.357.408 VND.`
- Analysis model `candidate:dee9c1e4c1dbb264985310b4`: `Các khoản giảm trừ doanh thu của BCC năm 2025 được ghi nhận là 173.405.357.408 VND.`
  Premise backend của analysis cũng có nhãn nguồn `2. Các khoản giảm trừ doanh thu`.

`extract_assertion` trước đây chỉ nhận ITEM_LABELS của các Specialist, không có
chỉ tiêu này, và không nhận tiền tố dòng `2.`. Vì không tạo được NumericAssertion,
validator sinh `content_period_unbound` và
`numeric_assertion_not_unambiguously_bound` dù dữ liệu nguồn đúng.

**Sửa chung tại verification/numeric.py:** dùng aliases trong ITEM_CATALOG đã có,
bỏ đúng tiền tố liệt kê ở đầu nhãn (`2.`, `IV.`…), không đoán giá trị hoặc đơn vị.
Chỉ trả assertion khi mapping duy nhất; bare label trùng nhiều canonical IDs vẫn
unresolved. Không đổi NUMBER/parse_number, numeric equality, unit-scale, period,
source/quality/provenance hay semantic verdict rules. Không yêu cầu model đổi
định dạng và không thêm verifier. Định nghĩa chỉ tiêu vẫn qua canonical target
binding và semantic gate hiện có; parser không tự approve phép tính mang tên sai.

**Bằng chứng:** 71focused tests PASS ở working tree và71PASS trên isolated staged source (61,42s), gồm ba controls mới về parser,
representations và wrong-value/unit/period/item/ambiguous/malformed cases.
Replay Q05 dùng hai payload M5 cũ, Tools/canonical source và M6 thật tại code mới,
không gọi Qwen: numeric fact được ACCEPT; analysis vẫn INVESTIGATE khi không có
semantic verdict, không giả SUPPORTED. M7 chỉ từ numeric fact trả đúng số, status
completed_with_caveats. Bốn mutations trên chính fact thực tế (số+1, USD,2024,
đổi sang doanh thu thuần) đều không ACCEPT. Đây là offline replay, không sửa lại
kết quả smoke lịch sử hoặc tuyên bố fresh live PASS.

Local evidence bổ sung: `final-numeric-fix-02/{batch,verdicts,histories,m7,
negative-controls}.json`, giữ claim IDs, source refs và checks. Diagnostic lần đầu
đã qua assertions fact/M7 nhưng lỗi ghi Decimal ra JSON; lần02 sửa helper serializer,
không sửa runtime hoặc nguồn và không gọi API. Staged Python blobs khớp byte-for-byte với isolated source đã test; planning isolated136tasks PASS. Implementation SHA `451d9fd52bca3c32075cce867d832ff854f0ae1e` đã xác minh sau commit/push. Không lặp lại25câu hoặc full CI.

Giới hạn còn lại về độ chính xác semantic, rounding, alias mơ hồ, quý/năm và coverage
ngoài controls vẫn giữ nguyên; không mở thêm chuỗi sửa QWEN-GEN.

Tech Lead đã cho phép chốt DONE khi focused grammar/binding fix và negative controls đạt.
Điều kiện đạt với71focused tests trên working/isolated source và actual Q05offline replay.
Phiên chốt trạng thái chỉ docs/planning checks, không chạy lại tests hoặc API.
