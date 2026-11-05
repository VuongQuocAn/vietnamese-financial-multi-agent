# M7-03 — Grounded Report Writer

Owner giao05/11/2026; baseline HEAD/origin main
`b66919da3b26c7f05a0feb33bfed50a58ad7397a`. Implementation chưa commit.
Status **REVIEW**, chờ exact-SHA CI và Tech Lead nghiệm thu trước DONE.

## Luồng và API

Outline có sẵn + request gốc → truy vấn verified ledger đúng context → gate M7-02
độc lập → nhóm đoạn/khử assertions tương đương → optional Gemini proposal →
protected rendering → local report validator → GroundedFinancialReport.

```python
from vietnamese_financial_multi_agent.outputs import (
    GroundedReportRequest,
    GroundedReportWriter,
)

report = GroundedReportWriter(ledger=verified_ledger, gateway=shared_gateway).write(
    GroundedReportRequest(
        outline=grounded_outline,
        outline_request=original_outline_request,
        allow_gateway=True,
    )
)
```

Writer không gọi lại ReportOutlinePlanner. Nó tái dùng validate_report_outline,
query policy và B01 closing-date policy M7-02; đọc qua M6 facade, không rerun
verification/admission. Typed input bị sai contract ném ValidationError trước
Gateway; outline hợp đồng đúng nhưng bị giả mạo trả abstained, không claims/citations,
validation_result false. Không tin validation_result do caller cung cấp.

GroundedFinancialReport chứa title/status/scope/sections/body_vi và inventories.
ReportParagraph giữ source_slot_ids, verified_claim_ids, typed citations, caveats,
limitations và context cho từng slot (kind, period role, native period/source).
Phân biệt fact, approved_metric, supported_interpretation; chỉ loại cuối được
render thành verified_interpretation. READY → generated; partial giữ partial;
clarification_required/abstained/unsupported không được nâng trạng thái.

## Nội dung được bảo vệ và văn phong

Financial prose dùng nguyên văn accepted_content. Gemini chỉ nhóm/sắp xếp slot
indexes trong mỗi section và chọn transition thuộc allowlist; không có free prose,
financial values, citations hoặc caveat fields trong proposal. Catalog tiếng Việt
cung cấp câu dẫn, phạm vi, tổng quan liên kết các mục thực sự có evidence, giới hạn
và câu kết trung tính. Section order giữ nguyên outline đã được chấp nhận.

Khử trùng lặp tái dùng typed assertion signature đã duyệt M7-02, đồng thời yêu cầu
cùng native context/role/kind và cùng citation source identities. Không suy tương
đương từ text hoặc regex số. Chọn wording ACCEPT đầu tiên theo outline; mọi slot
IDs, verified IDs, citations và caveats/limitations của các bản tương đương đều
được giữ tại cùng paragraph. Gemini không được tách các bản tương đương ra nhiều
đoạn. Một đoạn có tối đa3 assertions khác nhau, có thể bao gồm nhiều source slots.
Different sources/semantics không bị ép gộp; interpretation và fact vẫn tách riêng.

Validator dựng lại chính xác toàn bộ report từ protected outline và grouping đã
kiểm tra. Nó đối chiếu paragraph types/text/bindings/context, inventories, status,
section metadata và body_vi; phát hiện cả kết luận sai không chứa chữ số. Gate
này thuộc M7-03, chưa là firewall M7-05. M7-04 sẽ xử lý citation display; body không
tạo số trang/citation labels. Typed citations giữ source provenance nguyên trạng.

Annual context phải caller khai báo ReportPeriodContext(period_end="2025-12-31").
Kỳ báo cáo2025 và số dư B01 tại2025-12-31 được trình bày riêng, không chuẩn hóa lại.
Original/recovery không trộn; included_periods không cấp quyền so sánh. D03-B10
giữ nguyên. Scope unknown được nêu rõ, không tự suy separate/consolidated.

Các caveat codes giữ đầy đủ trong structured output; chỉ mapping hữu hạn,
deterministic cho page_level_only/source_reference_uncertain/non-independent-audit
được dùng làm văn bản giải thích nguồn. Raw inventory không chen vào đoạn phân tích.

## Gateway và fallback

SharedLLMGateway, model mặc định DEFAULT_GEMINI_MODEL hiện hành
`gemini-3.5-flash-lite`; temperature0, tối đa1 call/report,2048output tokens,
45s,prompt≤32.000UTF-8 bytes. Dynamic schema chứa inventory section/slot thực tế,
short indexes và example. Không gửi full histories, retry hoặc chuyển paid API.
Unknown keys/indexes/transitions, thiếu/trùng slots, unsupported prose, invalid JSON,
provider errors và grouping sai bị reject; deterministic baseline giữ dữ kiện hữu ích.
Nếu baseline không qua gate thì abstain. Usage/error/model provenance giữ từ Gateway.

## Oracle và kết quả thực nghiệm

Oracle được cố định trước Writer BBS evaluation, lấy nhãn từ M6/M7-02 đã nghiệm thu:
`evaluation/m7-03-scenarios.json`, SHA256 LF
`4d8df72e5888e02602ed2648b90f8ca478eeef36b68146ddd62750e6271fffd3`.
Evaluator pin cả ledger và hai accepted outline oracles, chỉ chấp nhận Git CRLF/LF
equivalence. Không lấy report output làm nhãn và không thay oracle sau khi chấm.

Ledger hydrate/proof-validate58 entries một lần/session:28facts/28metrics/
2interpretations. Warm evaluation dùng read-only SavedVerifiedView với query semantics
M6 nguyên trạng; không đổi persistence. Cold read60,47s ở initial,69,99s ở final;
không cộng cold read vào warm generation latency.

| Phạm vi | Kết quả implementation cuối |
| --- | --- |
| BBS source-bound cases | 43/43 PASS;6 document/snapshot contexts, BBS2021–2025 và recovery2022 |
| Cơ cấu report cases | 12general,12focused,14partial; cùng context có nhiều loại báo cáo |
| Context/conflict controls | 13/13 PASS; conflict là detached adversarial injection, không admission |
| Fake Gateway controls | 17/17 PASS;1accepted,16fallback đúng oracle |
| Tampered outlines | 13/13 fail closed đúng oracle |
| Tổng bounded oracle | 86/86 PASS;status/required claims/sections/order/round-trip agreement1.0 |
| Verified usage precision/required coverage | 1.0 trong bounded oracle; giữ cả IDs của duplicate wordings |
| Citation/caveat/context | Exact source bindings và required caveats giữ đủ;zero violations |
| Unsupported statements/fabricated citations | 0/0 |
| Unauthorized calculations/unverified retrieval | 0/0;guarded tool counters |
| Warm saved-source generation min/mean/max | 3,24/36,49/97,31ms;43cases, không fake/live latency |
| Final saved Gemini replay | 3/3 proposals accepted;zero fresh calls, source/structure gates PASS |
| Engineering tests | 48Writer controls PASS (47suite+1targeted regression cuối);401focused compatibility PASS |
| Protected integrity | 15.727hashes unchanged, gồm accepted data/artifacts/oracles và Web local |

## Fresh Gemini và replay cuối

Đã dùng đúng3/3 fresh calls ở implementation trước sửa duplicate wording;
provider_reported_model là gemini-3.5-flash-lite, tất cả responses được chấp nhận,
zero provider errors/fallback,7.338provider-reported tokens. Không retry/gọi thêm.

| Case | Input/output/total tokens | Latency toàn write | Fresh proposal |
| --- | --- | --- | --- |
| profit-2025 | 1891/153/2044 | 2342ms | accepted |
| missing-2025 | 1387/71/1458 | 2006ms | accepted,partial |
| annual-general-2025 | 3519/317/3836 | 1642ms | accepted |

Sau đọc mẫu phát hiện các wordings tương đương lặp câu, đã sửa root cause bằng typed
deduplication và ràng buộc grouping. Implementation cuối replay nguyên3payloads
đã lưu qua Gateway với request binding mới:3/3accepted,không remap/sửa proposal,
không gọi thêm Gemini. Các tokens trong replay là usage lịch sử, không cộng lần hai.
Final prompt có thêm equivalence_index/ràng buộc; fake transports/schema tests đạt,
chưa có fresh call dùng prompt mới vì ngân sách đã hết. Báo cáo final dùng production
Writer với saved proposal, không phải prose viết tay bởi evaluator.

Regression test ban đầu đổi field của citation đang dùng chung trong synthetic
fixture, nên vô tình đổi cả hai nguồn. Đã sửa fixture bằng detached citation copies;
targeted regression1/1PASS, không sửa runtime/policy/oracle để làm test đạt.

## Artifacts và đọc báo cáo thực tế

Ignored artifacts mới, không overwrite accepted outputs:

```text
artifacts/evidence/M7-03-report-v1/live/summary.json
artifacts/evidence/M7-03-report-final/offline/summary.json
artifacts/evidence/M7-03-report-final/replay/summary.json
artifacts/evidence/M7-03-report-final/replay/reports/annual-general-2025.md
artifacts/evidence/M7-03-report-final/replay/reports/profit-2025.md
artifacts/evidence/M7-03-report-final/replay/reports/missing-2025.md
artifacts/evidence/M7-03-integrity-final/summary.json
```

Mỗi report có JSON đầy đủ và file -bindings.json giữ context/citation/caveat/limitation
inventory. Evaluator hỗ trợ offline,saved-source,fake,live,replay,integrity; output
phải là thư mục M7-03 mới. Live markers ở M7-03-call-budget ngăn vượt3calls/session
task. Chạy lại offline hoặc replay được; không chạy thêm live trong task này.

Đã đọc cả3mẫu initial và bản general final: các assertions về margin/pretax/CFO
tương đương đã bỏ lặp, sections theo outline, unknown scope/partial/source-quality
limits hiện rõ. Fact và supported interpretation về CFO còn có cùng giá trị vì
semantics khác nhau; giữ nguyên thay vì suy gộp. Văn phong dùng finite templates,
còn lặp câu dẫn/kết giữa sections và scope hiện source IDs dài. Không tự chấm điểm
ngôn ngữ; các descriptive heuristics chỉ đếm paragraph/group/repetition/visibility,
không chứng minh mức tự nhiên hay readability. Đã đọc cả3mẫu cuối; Tech Lead cần
đọc độc lập để nghiệm thu.

## Giới hạn và bàn giao

Chưa phát hiện remaining P0/P1 trong bounded checks. P2: văn phong template hữu hạn,
source IDs dài, caveat mapping hữu hạn, unknown reporting scope và cold ledger read
tốn thời gian; financial values/provenance còn phụ thuộc chất lượng nguồn đã nghiệm
thu. Đây là source-bound generation agreement, không independent PDF financial
accuracy, financial audit, hoặc bằng chứng lợi ích Multi-Agent end-to-end.

Next action: Tech Lead review M7-03; không tự bắt đầu M7-04.
