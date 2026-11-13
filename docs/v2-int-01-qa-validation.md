# V2-INT-01 — Hoàn thiện và kiểm chứng QA V2

## Bổ sung sửa source, claim-local period và coverage — 13/11/2026

**REVIEW**, implementation `474cc218498512748aaaa96ab463c070b27f9228`, base `68c22ee` trên main;
`integration_v2` vẫn opt-in. Owner giao sửa tiếp đúng V2-INT-01, không mở task/nhánh,
không gọi Qwen. Các phần phía dưới giữ bằng chứng lịch sử của lượt live trước sửa.

### Nguyên nhân và code sửa

- `lite_orchestrator.resolve_source/resolve_requirements/run`: source lookup cũ chỉ
  nhận S handles; requirements lại dùng chính handles như canonical target. Python
  nay resolve handle/canonical item trong inventory đã ghim company/document/snapshot/
  reporting scope, chọn đúng kỳ từ assigned requirements và operand periods. Không
  dùng requirement ID làm source ID; unknown, period mismatch và ambiguous có reason
  riêng, không chọn một record tùy ý. Metric inventory cần operands cùng pinned scope.
  Role không cấm đọc nguồn hợp lệ của domain khác. Giữ requirement IDs/text và refs.
- `integration_workspace._matches_metric_expression/matches_requirement/export`:
  normalize targets/indicators trước binding; đối chiếu cấu trúc biểu thức với
  definition và ordered canonical operands/kỳ trong inventory, cùng requested unit.
  Vì vậy percentage_change hợp lệ có thể đáp ứng revenue_yoy, nhưng quotient của chỉ
  tiêu khác, đảo operands hoặc sai kỳ/đơn vị không đáp ứng. Không thêm formula/policy.
  Scalar retrieval bị model gắn nhầm kind=metric/interpretation được chuẩn hóa tại M5;
  yêu cầu diễn giải rõ ràng vẫn cần semantic support.
- `validators._requested_periods/_context/_reasoning`: V2 dùng kỳ của claim và sources,
  thay comparison periods của toàn câu. Vẫn kiểm canonical period/type, exact request
  pins, company/document/snapshot/scope, values/units, operands và citations. Legacy
  giữ cách kiểm cũ. `lite_runtime.verify` giữ binding của derived proof đã ACCEPT mà
  không đòi thêm semantic verdict; diễn giải vẫn đi cùng semantic batch hiện có.
- `qa_lite.compose_lite`: chỉ với V2 sidecar, gộp segments có cùng nội dung và scope;
  hợp nhất claim IDs/citations, giữ các findings khác nhau. M7 chỉ chiếu binding từ
  verified claims thực sự phát hành, không diễn giải lại requirement hay kiểm tài chính.

### Raw replay trước/sau

Runner `scripts/replay_v2_raw.py` dùng **nguyên response** trong
`qa-completion/live/provider-events.json` cho C01/C07, chạy lại pipeline thật bằng
SavedGateway chỉ đọc file, không tạo provider adapter. Không sửa Qwen output, thêm
verdict còn thiếu hoặc thay response bằng fixture. Trước là execution đã lưu cùng
lượt live; sau là replay trên source đã stage riêng, tách khỏi local runtime ngoài task.

| Case | Trước | Sau offline |
| --- | --- | --- |
| C01 | 7 ACCEPT / 6 ABSTAIN / 1 INVESTIGATE, 6 unique releases; 3 requirements unverified; 26,71% lặp 3 lần | 11 ACCEPT / 1 ABSTAIN / 2 INVESTIGATE, 9 unique releases; 3 numeric requirements satisfied; 26,71% đúng 1 lần |
| C07 | 0 financial facts retrieved; 1 document ACCEPT/release PDF12 | LNST2025 và2024 được resolve/truy xuất đúng; 2 financial facts ACCEPT từ numeric fallback V2 sẵn có, cộng đúng document ACCEPT cũ; citations PDF7/12 |

C07 không giả Qwen sinh numeric claims mới: hai responses specialist gốc vẫn claims=[],
khai thiếu dữ liệu và analyses hỏng schema. Chỉ numeric source fallback **đã có từ trước**
mới tạo candidates qua M6 sau khi retrieval được sửa; absence prose không được phát hành.
Requirement2024 do model thêm vẫn còn, chưa sửa planning ngoài ba nguyên nhân được giao.

| C01 candidate (suffix) | Trước → sau | Ý nghĩa |
| --- | --- | --- |
| `eb85321eafb8cfc367d7fb9a` | ABSTAIN → ACCEPT | Nợ phải trả tại2025-12-31 |
| `37663657fb14968dbe7421b2` | ABSTAIN → ACCEPT | Tổng tài sản tại2025-12-31 |
| `f3d5f7da6c87b5bccc13935f`, `01912929fd8e191bf2d18c29` | ABSTAIN → ACCEPT | Hai candidates cùng phép nợ/tài sản; một ledger identity/paragraph |
| `af00458bddec0650bff909df` | ABSTAIN → INVESTIGATE | Hết lỗi kỳ; response M6 cũ không có verdict cho claim này, không tự bổ sung |
| `2285c67b1361fd374c95e34f` | ABSTAIN → ABSTAIN | Prose59,06% dùng proof ratio; vẫn unbound number/unit |

| Binding | Trước | Sau |
| --- | --- | --- |
| C01 R001 | S34, indicators S11/S9; không binding | debt_to_assets, total_liabilities/total_assets; verified derived ratio đã render |
| C01 R002 | S35, indicators S15/S16; không binding | revenue_yoy, net_revenue với đúng2025/2024; verified percentage_change đã render |
| C01 R003 | S25, kind metric; không binding | b03.operating_cash_flow, kind fact, kỳ2025/VND; verified CFO fact đã render |
| C07 R1:R001/R002 | canonical target có nhưng sources canonical bị loại; không binding | sources resolve đúng2025/2024; hai verified LNST facts đã render |
| C07 R2/R2:R1 | document ACCEPT đã phát hành | Giữ nguyên verified ID và citation PDF12 |

C01 vẫn `partial_verified_coverage`: thiếu semantic verdict gốc cho claim nợ mới qua
deterministic gates được ghi technical error; CFO inference vẫn INVESTIGATE. Cả ba
numeric rows satisfied không đồng nghĩa đã có nhận xét tổng hợp đầy đủ. C07 replay
`completed_with_caveats` không chứng minh Qwen sẽ tự dùng nguồn mới hoặc giữ negative
constraint trong một lượt mới. Chưa xác nhận synthesis/constraint hoặc live quality.

### Kiểm chứng và giới hạn bàn giao

- Source stage riêng: **46 targeted PASS, 1 deselected** qua V2 integration, M5/M6 Lite,
  M7 Lite và comparative-period controls. Ba tests mới kiểm source variants/pins/role,
  công thức/ordered operands/units/kỳ/goal và claim-local negative controls. Đây là
  counterfactual fixtures kiểm logic, tách biệt raw replay nêu trên.
- Test deselected `test_m7_restores_omitted_accepted_comparison_without_new_verification`
  đã FAIL cả với `qa_lite.py` trước task: restored_calculation_claims rỗng khi test mong
  một ID. Giữ nguyên test, không sửa lỗi ngoài scope; không báo toàn suite xanh.
- Saved C04: ba absence claims không ACCEPT khi retrieval chưa đủ. Saved C10: hai
  proofs đúng và current-assets fact ACCEPT, phép trừ sai không ACCEPT. Không live C10.
- Controls sai giá trị, nguồn, company/document/snapshot, kỳ/type, unit, thiếu citation,
  tên chỉ tiêu và đảo operands vẫn bị chặn; ambiguous source giữ unresolved.
- Raw provider/execution inputs giữ nguyên; artifacts mới riêng tại
  `artifacts/evidence/V2-INT-01/source-period-coverage/staged-raw/`. Không OCR/Gemini,
  benchmark, full CI hoặc dataset/hash audit diện rộng. Không ghi/lưu API key.
- Ruff lint/format, planning checker và diff check đạt. Source ngoài task giữ local;
  không gom dataset, notebooks hoặc credential/config vào commit. Các SHA verified IDs
  mới phụ thuộc history/input digest; report JSON giữ toàn bộ bindings để đối chiếu.

**Next action:** Tech Lead/Owner review bằng chứng offline và quyết định có cấp phép
một lượt live xác nhận; chưa gọi Qwen và không tự nghiệm thu DONE.

## Lịch sử QA trước lần sửa này

**REVIEW — chờ Tech Lead nghiệm thu**, 13/11/2026 (Asia/Bangkok).
Implementation: `2783e7dd71b1a53db91c1a363d757fff67630622`, baseline main
`8b669be77f209a8cc0a6fb56ab36fa906a940092`. Tiếp tục V2-INT-01 theo Owner,
không tạo nhánh/task FIX mới; `integration_v2` vẫn opt-in.

**Kết quả QA thật: C01 PARTIAL, C07 PARTIAL, C10 INTERRUPTED do API timeout.**
11provider attempts,10success; **35.653tokens đã biết +1call usage unknown**,
0retry. Đã dừng ngay tại timeout, không gọi tiếp và không sửa runtime sau live.
C07 không còn mất document ACCEPT ở root, nhưng yêu cầu financial+document đầy đủ
chưa đạt vì financial retrieval không được thực hiện. Không báo GO/QA PASS.

## Thay đổi đúng phạm vi

`src/api/fusion_pipeline.py::compose_fusion_v2` nối **exact child released IDs**
với current verified ledger theo company/document/financial snapshot hoặc document
composition pins. Bỏ lookup lại target từ câu hỏi ở bước tổng V2; parent và child
requirement IDs được namespace để tránh va chạm. Claim hợp lệ tiếp tục phát hành
khi requirement khác thiếu; coverage vẫn giữ các phần chưa đáp ứng.

`src/outputs/qa_lite.py` tái dùng rendering/citation projection cho cả financial
và document ACCEPT. Chỉ hiển thị content/proofs đã admit, không sinh số hoặc nhận
định mới. Không đổi M6, Ledger, policy, OCR, EF-EG hoặc Financial Tools; không thêm
verifier/firewall. Legacy fusion giữ path cũ, V2 dùng M7 Lite đã có.

`src/agents/qa_planning.py::plan_fusion` làm rõ phân loại policy/điều kiện/ngoại lệ
vào document lane và gom cùng chủ đề, thay vì tạo nhiều financial subrequests cho
chính sách. Không hardcode case, số liệu hoặc nguồn của C01/C07/C10.

## Offline trước live

- Saved-data replay C01 giữ3task/assignments và7shared evidence identities;
  fixture requirement IDs được gắn nhãn counterfactual, không giả Qwen đã sinh chúng.
- C04 ba absence claims không ACCEPT; C10 hai proofs đúng và current-assets fact
  ACCEPT, phép trừ model sai không ACCEPT. Kiểm giá trị/đơn vị/kỳ/nguồn giữ nguyên.
- C07 replay nguyên document history trước đây: ID ACCEPT được khôi phục ở root,
  citation PDF12. Ghép deterministic financial counterfactual cho thấy cả financial
  và document citations PDF7/12; không phải lời hứa model sẽ chọn đúng nguồn.
- Control mixed mới giữ child releases dù parent target khác; ID không tồn tại
  trong current ledger không được phát hành; phần đúng được giữ khi có lỗi/thiếu.
- 22historic ledger entries serialize/replay nguyên vẹn;607non-runtime protected
  files unchanged; source JSON E2E không ghi đè. Kết quả mới ở
  `artifacts/evidence/V2-INT-01/qa-completion/`, không commit dataset/credentials.
- Run đầu:6PASS/1FAIL do fixture dùng model_copy với model dict chưa deserialize;
  đã sửa fixture, control mixed1PASS. Nhóm targeted cuối27PASS; Ruff lint/format,
  planning checker143tasks working tree và diff check đạt. Không full CI/M8.

Đây là engineering/boundary evidence, không thay thế độ đúng và độ đầy đủ QA thật.
Runtime được đóng băng trước live; không sửa hoặc gọi thêm lượt live sau FAIL/PARTIAL.

## Một lượt live được Owner cấp phép

Thứ tự C01→C07→C10; mỗi câu một lượt, max6calls/câu và18tổng; giữ model/endpoint/
key đã cấp, không retry hoặc provider fallback. Dùng lại token cap180.000tổng và
timeout300giây/câu của ngân sách trước, không nới giới hạn. Fail-stop trước call
tiếp theo khi provider/network lỗi. Manifest giữ exact runtime hashes và câu hỏi.

Working tree còn local edits từ trước, không gom chúng vào implementation commit;
không gán live quality cho riêng SHA nếu bỏ các runtime local đó. File hash của
lượt chạy nằm trong `implementation-receipt.json` và `live/manifest.json`.

### Tổng kết lượt chạy

Trạng thái runner: **STOPPED**; **11 calls / 35.653 known tokens +1unknown usage**,
không retry. Không tính failed timeout call là0tokens. Không có lượt live thứ hai.
Dừng: `provider_error_fail_stop`; không tiếp tục case còn lại.

### C01 — Kết quả thực tế

**Câu hỏi nguyên văn:**

> Lập nhận xét ngắn về BBS năm 2025 gồm ba phần: tăng trưởng doanh thu thuần so với 2024, tỷ trọng nợ trong tài sản cuối năm và dòng tiền kinh doanh. Nêu số liệu cho từng phần, không dùng một chỉ tiêu để kết luận toàn bộ sức khỏe tài chính.

**Câu trả lời thực tế nguyên văn** (giữ cả lặp/gaps/caveats):

> (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. [1]
>
> (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. [1]
>
> (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. [1]
>
> Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1]
>
> Lưu chuyển tiền thuần từ hoạt động kinh doanh kỳ 2025 là 14.319.681.754 VND. [2]
>
> Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa đáp ứng: Tính tỷ lệ nợ trên tổng tài sản (debt_to_assets) cho năm 2025-12-31.; Tính tỷ lệ tăng trưởng doanh thu thuần (revenue_yoy) giữa năm 2025 và 2024.; Tính dòng tiền thuần từ hoạt động kinh doanh (operating_cash_flow) cho năm 2025.
>
> Nguồn tham chiếu
>
> [1] Tài liệu nguồn 2025 — Trang PDF 7. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
> [2] Tài liệu nguồn 2025 — Trang PDF 8. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Status `partial_verified_coverage`; 5calls; 26,802tokens; 156.45giây.

**Chuẩn/điểm cần kiểm chứng:** Doanh thu2025=450.474.531.227VND,2024=355.507.372.286VND, tăng26,71%; nợ157.146.559.558/tài sản266.086.680.765=59,06%; CFO dương14.319.681.754VND, kết luận giới hạn theo ba nhánh.

**Agents/stages thực gọi qua Gateway:** `m5-lite-supervisor`×1; `m5-lite-liquidity_and_leverage`×1; `m5-lite-profitability`×1; `m5-lite-cash_flow_and_earnings_quality`×1; `m6-lite`×1.

**Tools:** `get_financial_fact`×5; `get_evidence_sources`×5.

**M6 decisions thực tế** (không dùng ACCEPT làm gold):

| Candidate | Mệnh đề candidate | Decision / reasons | Admission |
| --- | --- | --- | --- |
| `candidate:af00458bddec0650bff909df` | Tỷ trọng nợ trong tài sản cuối năm 2025 được tính bằng tỷ lệ giữa tổng nợ phải trả và tổng tài sản. Tỷ lệ này cho thấy mức độ phụ thuộc vào nợ của doanh nghiệp. | ABSTAIN: context_mismatch; reasoning_comparison_period_mismatch | NOT_EXECUTED |
| `candidate:f3d5f7da6c87b5bccc13935f` | Tổng nợ phải trả (kỳ 2025-12-31) / Tổng tài sản (kỳ 2025-12-31): 0,59 lần (tỷ số đối chiếu). | ABSTAIN: context_mismatch; reasoning_comparison_period_mismatch | NOT_EXECUTED |
| `candidate:eb85321eafb8cfc367d7fb9a` | Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. | ABSTAIN: context_mismatch | NOT_EXECUTED |
| `candidate:37663657fb14968dbe7421b2` | Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. | ABSTAIN: context_mismatch | NOT_EXECUTED |
| `candidate:7cd7d4647464ad6a9c1bee57` | Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. | ACCEPT: deterministic_source_and_calculation_verified | stored |
| `candidate:bc13cb26bebe9761e9131a5a` | Doanh thu thuần kỳ 2024 là 355.507.372.286 VND. | ACCEPT: deterministic_source_and_calculation_verified | stored |
| `candidate:5c1da1bf605b709a5b775754` | Lưu chuyển tiền thuần từ hoạt động kinh doanh kỳ 2025 là 14.319.681.754 VND. | ACCEPT: deterministic_source_and_calculation_verified | stored |
| `candidate:1387910614fc94c0f9407928` | Tỷ lệ tăng trưởng doanh thu thuần giữa năm 2025 và 2024 được tính bằng tỷ lệ phần trăm tăng trưởng (percentage change) giữa doanh thu thuần năm 2025 và doanh thu thuần năm 2024. | ACCEPT: semantic_supported; Statement is directly supported by the provided facts and calculations. The percentage change between 2025 and 2024 revenue is correctly calculated as 26.71% using the given values and the percentage change operation. | stored |
| `candidate:ae178f65bf2253d61c7d2975` | (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. | ACCEPT: deterministic_source_and_calculation_verified | stored |
| `candidate:cca283e3c1db09f8173fa768` | Lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2025 là 14.319.681.754 VND, cho thấy khả năng sinh tiền từ hoạt động kinh doanh chính của doanh nghiệp trong năm. | INVESTIGATE: semantic_insufficient; The statement provides a fact about operating cash flow but includes an interpretation ('cho thấy khả năng sinh tiền từ hoạt động kinh doanh chính') that is not directly supported by the evidence. The evidence only confirms the cash flow value, not its implications. | NOT_EXECUTED |
| `candidate:1b928f009f247bae84c795b4` | So sánh với doanh thu thuần năm 2024 (355.507.372.286 VND), doanh thu thuần năm 2025 (450.474.531.227 VND) tăng 26,71%, cho thấy sự tăng trưởng mạnh trong hoạt động kinh doanh. | ACCEPT: semantic_supported; The statement is supported by the provided facts and calculations. The percentage change between 2025 and 2024 revenue is correctly calculated as 26.71% using the given values and the percentage change operation. | stored |
| `candidate:71fdd25046cda7e49811bc2d` | (Doanh thu thuần (kỳ 2025) − Doanh thu thuần (kỳ 2024)) / Doanh thu thuần (kỳ 2024) × 100: 26,71 %. | ACCEPT: deterministic_source_and_calculation_verified | idempotent |
| `candidate:2285c67b1361fd374c95e34f` | Tỷ lệ nợ trên tổng tài sản năm 2025 là 59,06%, cho thấy doanh nghiệp có mức độ phụ thuộc vào nợ tương đối cao. | ABSTAIN: context_mismatch; lite_unbound_number; lite_unbound_unit; reasoning_comparison_period_mismatch | NOT_EXECUTED |
| `candidate:01912929fd8e191bf2d18c29` | Tổng nợ phải trả (kỳ 2025-12-31) / Tổng tài sản (kỳ 2025-12-31): 0,59 lần (tỷ số đối chiếu). | ABSTAIN: context_mismatch; reasoning_comparison_period_mismatch | NOT_EXECUTED |

**M6 → Ledger → M7:** {'ABSTAIN': 6, 'ACCEPT': 7, 'INVESTIGATE': 1}; 6unique admitted IDs; 6ledger entries; 6root released IDs. Ledger-not-released: `[]`. Released-outside-ledger: `[]`.

| Verified ID | Root M7 | Citation PDF pages |
| --- | --- | --- |
| `verified:078f675351614d34ce0b552b33acd5e44979ba1e693a9038393d4cdea2b38f4c` | released | [7] |
| `verified:1e5f1509597a20a3c3205eca8e5314169436507dc703967c3d6db5141c8b6ce4` | released | [8] |
| `verified:44dad4d1cfe1aad22664ab34ffd099de4fe6dcf7f6ed6036f18d4d189acf34e7` | released | [7] |
| `verified:861c26deb972969c4d0a137cf1f25dffafbdb30dc92b74a7bc1541418a36c202` | released | [7] |
| `verified:c4dc144c35934096a1c51bc78089cde3ab457e9cea26e92a90024cbe52621d51` | released | [7] |
| `verified:d52ea7a531658b7649ee3156b1ddb81a5efa1093176e87ef5a43e0c2b7f95660` | released | [7] |

**Coverage thực tế:**
- `R001`: Tính tỷ lệ nợ trên tổng tài sản (debt_to_assets) cho năm 2025-12-31.; unverified; verified IDs=[].
- `R002`: Tính tỷ lệ tăng trưởng doanh thu thuần (revenue_yoy) giữa năm 2025 và 2024.; unverified; verified IDs=[].
- `R003`: Tính dòng tiền thuần từ hoạt động kinh doanh (operating_cash_flow) cho năm 2025.; unverified; verified IDs=[].

Nguồn evidence: local `qa-completion/live/execution/C01.json` và `provider-events.json`. Root errors: `[]`.

### C07 — Kết quả thực tế

**Câu hỏi nguyên văn:**

> Nêu LNST BBS năm 2025 rồi đối chiếu chính sách chi phí đi vay trong thuyết minh: khoản nào ghi chi phí, khoản nào có thể vốn hóa? Không suy ra số lãi vay vốn hóa thực tế từ chính sách.

**Câu trả lời thực tế nguyên văn** (giữ cả lặp/gaps/caveats):

> Tài liệu ghi «4.12. Chi phí đi vay Chi phí đi vay bao gồm lãi tiền vay và các chi phí khác liên quan trực tiếp đến các khoản vay. Chi phí đi vay được ghi nhận vào chi phí sản xuất, kinh doanh trong năm khi phát sinh, ngoại trừ chi phí đi vay liên quan trực tiếp đến việc đầu tư, xây dựng hoặc sản xuất tài sản dở dang cần có một thời gian đủ dài (trên 12 tháng), để có thể đưa vào sử dụng theo mục đích định trước hoặc bán, được tính vào giá trị của tài sản đó (được vốn hóa) khi có đủ các điều kiện quy định của Chuẩn mực kế toán Việt Nam số 16 - Chi phí đi vay. Đối với khoản vay riêng phục vụ việc xây dựng tài sản cố định, lãi vay được vốn hóa kể cả khi thời gian xây dựng từ 12 tháng trở xuống. Đối với các khoản vốn vay chung, trong đó có sử dụng cho mục đích đầu tư xây dựng hoặc sản xuất tài sản dở dang thì số chi phí đi vay được vốn hóa được xác định theo tỷ lệ vốn hóa đối với chi phí lũy kế bình quân gia quyền phát sinh cho việc đầu tư xây dựng hoặc sản xuất tài sản đó. Tỷ lệ vốn hóa được tính theo tỷ lệ lãi suất bình quân gia quyền của các khoản vay chưa trả trong năm, ngoại trừ các khoản vay riêng biệt phục vụ cho mục đích hình thành một tài sản cụ thể.» [1]
>
> Lưu ý: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.
>
> Chưa đáp ứng: Tìm LNST của BBS năm 2025; Tìm LNST của BBS năm 2024; Nêu LNST BBS năm 2025
>
> Nguồn tham chiếu
>
> [1] BBS 2025 — Trang PDF 12. Giới hạn nguồn: Bằng chứng được lưu còn giới hạn về nguồn hoặc ngữ cảnh.

Status `partial_verified_coverage`; 5calls; 8,851tokens; 107.40giây.

**Chuẩn/điểm cần kiểm chứng:** LNST BBS2025=7.249.557.946VND (PDF7); chính sách chi phí đi vay PDF12: thường ghi chi phí khi phát sinh, vốn hóa tài sản dở dang đủ điều kiện VAS16 và ngoại lệ vay riêng xây dựng TSCĐ kể cả<=12tháng. Không suy số vốn hóa thực tế từ chính sách.

**Agents/stages thực gọi qua Gateway:** `fusion-planner`×1; `m5-lite-supervisor`×1; `m5-lite-profitability`×2; `document-planner`×1.

**Tools:** `search_document_evidence`×4; `get_evidence_sources`×5; `get_graph_context`×1.

**M6 decisions thực tế** (không dùng ACCEPT làm gold):

| Candidate | Mệnh đề candidate | Decision / reasons | Admission |
| --- | --- | --- | --- |
| `document:702135aa78af81180a240c294ec279189b982483cb0adbef2ff583282946c032` | Tài liệu ghi «4.12. Chi phí đi vay Chi phí đi vay bao gồm lãi tiền vay và các chi phí khác liên quan trực tiếp đến các khoản vay. Chi phí đi vay được ghi nhận vào chi phí sản xuất, kinh doanh trong năm khi phát sinh, ngoại trừ chi phí đi vay liên quan trực tiếp đến việc đầu tư, xây dựng hoặc sản xuất tài sản dở dang cần có một thời gian đủ dài (trên 12 tháng), để có thể đưa vào sử dụng theo mục đích định trước hoặc bán, được tính vào giá trị của tài sản đó (được vốn hóa) khi có đủ các điều kiện quy định của Chuẩn mực kế toán Việt Nam số 16 - Chi phí đi vay. Đối với khoản vay riêng phục vụ việc xây dựng tài sản cố định, lãi vay được vốn hóa kể cả khi thời gian xây dựng từ 12 tháng trở xuống. Đối với các khoản vốn vay chung, trong đó có sử dụng cho mục đích đầu tư xây dựng hoặc sản xuất tài sản dở dang thì số chi phí đi vay được vốn hóa được xác định theo tỷ lệ vốn hóa đối với chi phí lũy kế bình quân gia quyền phát sinh cho việc đầu tư xây dựng hoặc sản xuất tài sản đó. Tỷ lệ vốn hóa được tính theo tỷ lệ lãi suất bình quân gia quyền của các khoản vay chưa trả trong năm, ngoại trừ các khoản vay riêng biệt phục vụ cho mục đích hình thành một tài sản cụ thể.» | ACCEPT: exact_source_support | stored |

**M6 → Ledger → M7:** {'ACCEPT': 1}; 1unique admitted IDs; 1ledger entries; 1root released IDs. Ledger-not-released: `[]`. Released-outside-ledger: `[]`.

| Verified ID | Root M7 | Citation PDF pages |
| --- | --- | --- |
| `verified:51a072f22f60714682823b1c9c84a755a7c31beb8eefb28c68cafb28795fb9b0` | released | [12] |

**Child → root:**
- `R1`/financial: verification_blocked, child IDs=[]; mất ở root=[].
- `R2`/document: completed_with_caveats, child IDs=['verified:51a072f22f60714682823b1c9c84a755a7c31beb8eefb28c68cafb28795fb9b0']; mất ở root=[].

**Coverage thực tế:**
- `R1:R001`: Tìm LNST của BBS năm 2025; unverified; verified IDs=[].
- `R1:R002`: Tìm LNST của BBS năm 2024; unverified; verified IDs=[].
- `R1`: Nêu LNST BBS năm 2025; unverified; verified IDs=[].
- `R2:R1`: chi phí đi vay; satisfied; verified IDs=['verified:51a072f22f60714682823b1c9c84a755a7c31beb8eefb28c68cafb28795fb9b0'].
- `R2`: đối chiếu chính sách chi phí đi vay trong thuyết minh: khoản nào ghi chi phí, khoản nào có thể vốn hóa; satisfied; verified IDs=['verified:51a072f22f60714682823b1c9c84a755a7c31beb8eefb28c68cafb28795fb9b0'].

Nguồn evidence: local `qa-completion/live/execution/C07.json` và `provider-events.json`. Root errors: `[]`.

### C10 — Kết quả thực tế

**Câu hỏi nguyên văn:**

> Tại 31/12/2025, BCC có vốn lưu động ròng (tài sản ngắn hạn trừ nợ ngắn hạn) bao nhiêu và hệ số thanh toán hiện hành mấy lần? Đặt hai kết quả bên cạnh CFO dương năm 2025 và nêu giới hạn khi đánh giá thanh khoản.

**Chưa có final answer**: INTERRUPTED. Không tự suy ra câu trả lời hoặc verdict khi chưa chạy tới bước đó.

**Chuẩn/điểm cần kiểm chứng:** Vốn lưu động ròng767.374.839.317−1.368.031.294.449=−600.656.455.132VND; current ratio0,560933688…≈0,56lần; CFO dương314.097.335.438VND; dữ liệu này không chứng minh chắc chắn khả năng thanh toán tương lai.

Provider event cuối: `m5-lite-supervisor`, status=`error`, category/code=`timeout`,
retryability=`not_retryable`, origin=`adapter`; request timeout60giây. Một call
đã thử, input/output/total usage đều unknown; không có response content để quote,
không có tool call/M6 decision/ledger entry/M7 answer. Runner không lưu elapsed
E2E của case bị BaseException interrupt, nên **không có thời gian C10 chính xác
để báo**;60giây là cấu hình timeout, không phải số đo E2E. Không dùng đây làm
FAIL chất lượng financial verification; C10 hiện chỉ có bằng chứng offline.

## Đối chiếu từng phần và nguyên nhân còn lại

| Case | Đã đạt nội dung thật | Còn thiếu / nguyên nhân cụ thể |
| --- | --- | --- |
| C01 — PARTIAL | Doanh thu hai kỳ, phép tăng26,71%, CFO14.319.681.754VND và citations PDF7/8; đủ3roles được gọi, shared evidence được dùng | Thiếu nợ/tài sản59,06% và kết luận tổng hợp có giới hạn. `LitePlan.requirements` dùng `target_id=S34/S35/S25`, `required_indicators` cũng là S handles thay canonical IDs; CFO còn khai kind=metric. `IntegrationWorkspace.export` không match được nên toàn bộ candidate_requirements rỗng; M7 báo thiếu cả phần đã có số. Đây là model contract error được schema string hiện tại cho qua; không phải thiếu corpus. |
| C01 — phần nợ | M5 có nợ157.146.559.558VND/tài sản266.086.680.765VND, phép ratio0,59 và một prose59,06% | M6 `_context/_reasoning` dùng `comparison_periods(batch.question)` toàn câu={2024,2025}; các nguồn as-of2025-12-31 không nằm trong tập fiscal-year đó nên context_mismatch/reasoning_comparison_period_mismatch. Một analysis59,06% còn dùng ratio proof nên lite_unbound_unit/number. Đây là lỗi scope còn tồn tại tại boundary kiểm chứng cùng lỗi đại lượng do model, không được quy cho M7 làm rơi ACCEPT. |
| C01 — coverage/presentation | 7native ACCEPT hợp thành6unique ledger entries,1idempotent;6/6đến M7, không ledger entry bị mất | Accepted findings/proofs trùng mục tiêu khiến phép26,71% xuất hiện3lần. Coverage chưa canonical-bind nên báo thiếu phần đúng. M6 giữ CFO fact nhưng INVESTIGATE inference về khả năng sinh tiền. Không có cơ sở gọi whole answer đầy đủ. |
| C07 — PARTIAL | Chính sách ghi chi phí/vốn hóa và ngoại lệ được phát hành nguyên văn, citation PDF12. Child document ACCEPT có đúng cùng ID ở root | Thiếu LNST7.249.557.946VND, vì supervisor financial đặt `sources=['b02.profit_after_tax']` thay source handles S…; retrieval không chạy, `unknown_or_foreign_source` trong task bundle, specialists abstain/invalid_analysis_schema. Model còn thêm requirement2024 không được hỏi. Không có numeric claim tới M6; không phải M6 bác LNST đúng hoặc tài liệu thiếu LNST. |
| C07 — constraint | Không bịa số vốn hóa thực tế, không tạo nhận định tài chính mới ở M7 | Fusion plan không giữ negative constraint thành requirement riêng; final không giải thích rõ giới hạn “không suy số vốn hóa thực tế”. Câu trả lời chỉ có document evidence, chưa đồng thời có financial evidence. |
| C10 — INTERRUPTED | Typed verifier đã có offline replay đúng3candidate, chặn model subtraction sai | API timeout tại supervisor trước retrieval; không quan sát được end-to-end C10 mới. Tokens và thời gian E2E case này không có đủ telemetry, không tự điền0. |

Code/trace evidence: `src/agents/integration_workspace.py::matches_requirement/export`,
`src/agents/lite_orchestrator.py::integration_plan/run`,
`src/verification/validators.py::_context/_reasoning`,
`src/verification/lite_runtime.py::LiteFinancialValidator._analysis`;
`live/execution/C01.json#/response/trace/financial_execution/integration_context`,
`C07.json#/response/trace/fusion_bundle/lane_results`, `live/provider-events.json`.
Không sửa các nguyên nhân quan sát sau live, không thử prompt/model/case khác.

**Phân biệt sửa và giới hạn:** lỗi child document ACCEPT mất ở root đã được sửa
và xác nhận cả saved replay lẫn live C07 (1/1child release được giữ). Binding
target/source-handle do model, M6 global comparison-period scope, negative
constraint và lặp presentation vẫn còn. Financial+document completeness và live
C10 chưa được chứng minh. Không thay quality verdict bằng số unit tests PASS.

## Bàn giao

Trạng thái REVIEW; không tự nghiệm thu DONE, không mở vòng FIX hoặc tự triển khai
task tiếp theo. Next action duy nhất: Tech Lead review kết quả QA thật và phạm vi
đã kiểm chứng trước quyết định nghiệm thu.
