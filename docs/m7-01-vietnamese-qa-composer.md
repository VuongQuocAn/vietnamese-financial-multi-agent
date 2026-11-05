# M7-01 — Vietnamese QA Composer

Status **IN_PROGRESS**, Owner giao05/11/2026; baseline local/origin main
`67700c3ff4e3aa170d9af8c0da872032dc2be1d0`. Tech Lead phê duyệt M6 trong task mới.

## Architecture và API

VietnameseQARequest → catalog requirement matching → VerifiedClaimLedger.find_claims
→ GroundedAnswerPlan → protected segments → optional Gateway ordering → local gate
→ VietnameseQAResponse. Composer không sở hữu persistence, M5 execution hoặc M4 tools.

```python
from vietnamese_financial_multi_agent.outputs import VietnameseQAComposer, VietnameseQARequest
from vietnamese_financial_multi_agent.verification import (
    VerifiedClaimLedger,
    VerifiedClaimRepository,
)

ledger = VerifiedClaimLedger(VerifiedClaimRepository(configured_ledger_root))
composer = VietnameseQAComposer(ledger, gateway=shared_gateway)
response = composer.compose(
    VietnameseQARequest(
        question="Cho biết doanh thu và biên lợi nhuận gộp năm 2025.",
        document_id=document_id,
        snapshot_id=snapshot_id,
        allow_gateway=False,
    )
)
```

Caller phải bind exact snapshot và company/document. Năm trong câu hỏi chỉ lọc kỳ,
không chọn filing/snapshot. Một requirement có nhiều assertions/context khác nhau
yêu cầu làm rõ; không lấy match đầu. Các numeric ACCEPTs cùng typed value/unit/scale,
exact evidence reference/calculation identity/period/scope được giữ toàn bộ IDs.
Chỉ các đoạn có content/context giống hệt mới gộp hiển thị, hợp citations/caveats;
hai cách viết khác nhau được giữ nguyên riêng. Interpretation chỉ dùng content
ACCEPT của kind supported_interpretation. Không suy causal relationship mới.

Question understanding dùng understand, ITEM_RULES, EXTRA_ALIASES, FORMULA_ALIASES
công khai. Matcher nhiều ý nhỏ, không chạy lại M5 Planner. Các nhóm khái quát như
“khả năng sinh lời” cần chỉ rõ chỉ tiêu; unsupported metric không đổi thành operand.
So sánh nhiều năm/liên tài liệu bị D03-B10 chặn trước decomposition.

## Grounding, citations và caveats

Financial content render nguyên văn từ accepted_claim; không format/tính lại số.
Mỗi grounded segment có supporting verified IDs, exact EvidenceCitation objects,
company/document/snapshot/period và scope. Không tạo page/bbox/anchor mới. Không có
citation renderer đầy đủ M7-04; structured data chuẩn bị cho consumer sau.

Caveats hợp từ ledger, accepted claim, supporting evidence và citation limitations;
decision limitations/blockers/missing information ở segment limitations. Unknown
scope có ghi chú tiếng Việt. Confirmed scope chỉ từ embedded accepted calculation
reporting-scope resolution; caller intent hoặc năm filing không xác nhận scope.
Fact-only claim thiếu resolution vẫn unknown, kể cả khi filing đã được review ở
lớp khác. Yêu cầu scope không được xác nhận sẽ abstain, không tự gán scope.
Thiếu claim trong ledger không phải bằng chứng số liệu không tồn tại trong PDF.

Gate so toàn bộ protected segments/content/context/citations/caveats/limitations,
IDs thuộc retrieval, requirement coverage/status và finite display templates.
Invalid references fail closed; không chỉ kiểm regex số hoặc citation IDs.
Đây là local gate của QA, không phải Information Firewall tổng quát M7-05.

## Gemini và fallback

SharedLLMGateway nhận bounded projection của selected claims; không full history.
QACompositionProposal chỉ có claim_order (hoán vị đầy đủ) và introduction thuộc
hai lựa chọn cố định. Không có financial prose/paraphrase từ model. Unknown keys,
claim mới/trùng/thiếu hoặc câu dẫn ngoài allowlist bị reject. Backend tự giữ mọi
caveat/citation, nên model không thể bỏ caveat bằng một schema-valid proposal.

Tối đa12 selected IDs, prompt24.000 bytes, output1.600 tokens, timeout45s,
một call/request. Provider/timeout/malformed/adversarial output fallback deterministic.
Không retry hoặc chuyển paid API; effective model/usage/error giữ từ Gateway.

## Validation và evidence

33 QA engineering tests PASS ở vòng đầu sau sửa fixture; thêm2 targeted controls
cho duplicate caveats và mixed periods. BBS evaluation có fixed
oracle66 ca,40 saved-source và26 controls; SHA256
`8c44c0a85610aaae2d5c1e79ef1d9f8d58ffb5790726e2d0ac15ae002dbd3778`.
Oracle IDs/expected status được chốt từ accepted M6 histories trước Composer run.
Preflight hydrate58 verified entries:28 facts/28 metrics/2 interpretations.
Có BBS2021–2025 và recovery2022; original2022 thiếu accepted CFO claim.

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_vietnamese_qa_composer.py -q
.venv/Scripts/python.exe scripts/evaluate_m7_01_qa.py --output artifacts/evidence/M7-01-offline-new
.venv/Scripts/python.exe scripts/evaluate_m7_01_qa.py --mode live --output artifacts/evidence/M7-01-live-new
.venv/Scripts/python.exe scripts/evaluate_m7_01_qa.py --mode integrity --output artifacts/evidence/M7-01-integrity-new
```

Output phải mới, không overwrite accepted evidence. Saved replay hydrate qua real
repository/proof replay một lần, rồi dùng read-only view và public repository query
semantics trên entries đã xác minh; latency đo warm saved replay, không cold disk.
Vòng initial dừng sau4 ca PASS do chi phí parse/replay lặp của136MB ledger; giữ
artifact partial riêng, không overwrite. Runtime M6 và Composer không dùng view này.

Final saved replay tại ignored `artifacts/evidence/M7-01-offline-v2/summary.json`;
fresh tại `artifacts/evidence/M7-01-live-initial/summary.json`; integrity tại
`artifacts/evidence/M7-01-integrity-final/summary.json`.

| Chỉ số | Kết quả |
| --- | --- |
| BBS source-bound QA | 40/40 PASS,5 multi-intent revenue/margin và limitation/partial cases |
| Context/negative controls | 16/16 PASS |
| Fake transports trên saved BBS | 10/10 PASS;1 accepted/9 rejected proposals |
| Status/requirement agreement | 66/66 và66/66 (1.0);66 answered/21 unanswered requirements |
| Verified selection precision/recall | 1.0 trên tất cả cases có selected/required IDs |
| Citation binding / caveat retention | 100% trong bounded oracle; lost caveats0 |
| Unsupported statements / fabricated citations | 0 / 0 |
| Snapshot/scope violations | 0 |
| Unverified tool/candidate usage / new calculations | 0 / 0, guarded call counters |
| Deterministic fallback | 9/9 đúng oracle; không live provider failure |
| Warm replay latency min/mean/max | 4,46 / 19,31 / 52,28 ms; gồm fake transports |
| Protected integrity | 15.118 hashes unchanged, gồm toàn bộ data/accepted artifacts/Web local |
| Focused M4/M5/M6 compatibility | 236 PASS;1 existing Pydantic warning của invalid_decimal control |
| Fresh Gemini | 3/3 PASS;3 calls/5.555 tokens;3 accepted/0 fallback/0 provider errors |
| OCR/extraction calls | 0 |

Real-source cases là câu hỏi trên saved accepted BBS assertions, gồm các phiên bản
ACCEPT từ saved controlled histories; không tạo financial values/claims mới.
Ledger58 bao gồm57 primary và1 valid metric từ mixed-batch control M6-06. Đây không
phải58 independent financial observations. Fake/adversarial controls được đếm riêng.

Fresh provider-reported model `gemini-3.5-flash-lite` (không suy từ tên cấu hình):

| Case | Input/output/total tokens | Proposal | Status | Latency |
| --- | --- | --- | --- | --- |
| revenue-2021 | 1.193 / 86 / 1.279 | accepted | answered | 2.910 ms |
| multi-2021 | 2.501 / 145 / 2.646 | accepted | answered | 1.471 ms |
| interpretation-cfo (2025) | 1.545 / 85 / 1.630 | accepted | answered | 1.250 ms |

Mỗi fresh response giữ citations/caveats đúng source oracle. Task-wide call budget
đã dùng đủ3/3; không retry hoặc gọi thêm. Token usage provider_reported, không
có pricing estimate. Local Ruff toàn repo/format PASS; planning/diff PASS.
Implementation và exact-SHA CI sẽ ghi sau commit/push.

## Root causes và limitations

Fixture QA ban đầu dùng fact đầu tiên của M6 synthetic fixture (gross profit),
trong khi câu hỏi test là revenue; đã chọn revenue trong fixture rồi chạy lại đầy
đủ M6 checks/admission, không sửa oracle/runtime để cho qua. 33 tests PASS sau fix.
Các claim lặp của real ledger có caveat khác nhau, nên selection giữ toàn bộ
equivalent assertion IDs; không chọn một bản có ít caveats hơn để trả lời chắc chắn.

Matcher MVP có từ vựng hữu hạn, không diễn giải mọi paraphrase. Original/recovery
phải caller bind; các mô tả origin trong câu hỏi yêu cầu làm rõ. Không tự làm report,
discovery, financial calculation hoặc cross-document comparison. Scope projection
fact-only bảo thủ; full proof cold read tốn thời gian/RAM. Quality/caveats upstream
vẫn giữ, kể cả các nhãn lịch sử như formula_policy_not_approved trong ACCEPT.
Saved-policy QA/engineering PASS không là independent PDF financial accuracy hoặc
bằng chứng lợi ích Multi-Agent end-to-end. Implementation chưa commit.

Next action: hoàn tất evaluation và xác minh M7-01.
