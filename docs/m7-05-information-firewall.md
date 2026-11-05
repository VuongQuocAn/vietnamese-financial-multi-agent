# M7-05 — Information Firewall & Unified Output Validation

Owner giao05/11/2026; baseline main/origin
`6e33269ad8c812d057d202c1eecfd069c606d509`. Task dừng **REVIEW**, không nghiệm thu
milestone M7 hoặc bắt đầu M8. Implementation
`b22d8319ee94c8f400cc7c12face24baacbb2b2e` đã push main; HEAD/origin khớp.
[CI41989606269](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41989606269)
completed/SUCCESS đúng implementation SHA:977focused tests và9Web smoke PASS;
Python3.12 lint/format/planning, Web typecheck/lint/build đều SUCCESS; full unit
regression manual SKIPPED. Checkpoint sau chỉ docs/planning [skip ci],
không gán CI cho SHA checkpoint. Main-first, không tạo branch/PR mới.

## Architecture audit và trust boundary

```text
M6 admission/proof histories → verified-only ledger (trusted authority)
                                        ↓ exact AND queries
Trusted original QA/report request → M7-05 final gate ← QA/report + citation view
                                        ↓
               ALLOW / ALLOW_WITH_CAVEAT / BLOCK / CLARIFICATION_REQUIRED
                                        ↓
                              ValidatedOutput riêng
```

| Lớp | Đã kiểm tra | M7-05 tái sử dụng/bổ sung |
| --- | --- | --- |
| M6 | Admission replay, ACCEPT, identity/content/source digests, saved proof history | Public find_claims; không admission/reverification; kiểm lại verified/ACCEPT và identity/context của entries |
| M7-01 | Protected segments, exact accepted content, citations/caveats, requirement coverage, finite answer template | validate_qa_response; bổ sung original request inventory, scope constraints, status và selection completeness |
| M7-02 | Protected outline, exact typed slots, section inventory, annual B01 policy, D03-B10 | validate_report_outline với original outline request và retrieved entries |
| M7-03 | Protected paragraphs/body, dedup theo typed premises và source, finite transitions, coverage/status | validate_grounded_report với original GroundedReportRequest, cùng entries |
| M7-04 | Exact citation registry/projection, locators, markers, source fingerprint và annotations | validate_rendered_citations trên detached source với fresh local validation |

Khoảng trống liên module: QA local validator không nhận original request;
citation validator tin typed source đã được upstream kiểm định. Caller có thể
sửa source và display cùng lúc mà hai object vẫn nhất quán. Firewall dùng request
gốc và ledger độc lập để kiểm tra lại; cờ validation_result của caller không cấp
quyền phát hành. Không sao chép bốn validators thành rule engine mới.

Trusted inputs là original typed request, admitted M6 ledger và policy code.
Caller tích hợp phải giữ request ban đầu ngoài output có thể bị sửa. Firewall
không chứng minh lịch sử tạo output bằng chữ ký: nếu caller thay toàn bộ trusted
request, ledger và policy thì nằm ngoài ranh giới này. Những request chỉ khác nhãn
không render hoặc metadata model có thể cùng tạo một approved projection;
fingerprint ghi đúng request đã kiểm tra, không chứng thực một request lịch sử
không được cung cấp. Không signing/auth service hoặc persistence mới.

## APIs và contracts

```python
from vietnamese_financial_multi_agent.outputs import InformationFirewall

firewall = InformationFirewall(ledger=verified_ledger)
qa_decision = firewall.evaluate_qa(
    request=original_qa_request, response=qa_response, rendered=rendered_qa
)
report_decision = firewall.evaluate_report(
    request=original_report_request, report=report, rendered=rendered_report
)
safe_view = qa_decision.validated_output
```

Không gọi Composer, Writer, OutlinePlanner hoặc Gemini từ firewall. Helper
firewall_qa_binding chỉ dựng requirement inventory/selection/status, không sinh
financial content. Nó dùng understand/understand_requirements, target matcher,
typed assertion signature và claim_scope đã nghiệm thu. Unsupported/ambiguous,
scope/year conflict, original/recovery wording, missing binding và D03-B10 giữ
thứ tự ưu tiên của QA policy; không tự suy ngày cuối kỳ hoặc scope.

FinancialModel strict/extra=forbid. Input được reparse kể cả model_copy/construct;
đầu vào sai contract được BLOCK với F01 và check downstream không thể kiểm định.
Các original objects không bị mutate. FirewallCheckResult có ID, status,
severity, reason_code/reasons và affected claim/segment/citation IDs.

FirewallDecision có version/output type/verdict, original/release statuses,
validated IDs, checks, blockers, warnings, limitations, fingerprints,
ValidatedOutput, fresh validation_result và ledger_queries. Safe release contract
không cho body/references/claim IDs/caveats của unreleased output đi qua view.
Các model là dữ liệu ứng dụng, không phải authorization token chống caller có
quyền sửa chính model sau khi evaluate.

## Ledger revalidation và deterministic checks

| Check | Nội dung |
| --- | --- |
| F01 | Typed request/output/rendered view hợp lệ |
| F02 | QA original question, exact requirement plan/status/reasons/missing inputs; report request/outline binding |
| F03 | Bounded query filters đúng, IDs tồn tại duy nhất, không unknown/unverified candidate |
| F04 | verification_status=verified và final decision=ACCEPT |
| F05 | Identity ↔ accepted claim/context/kind/content hash/final decision digest; evidence/citation source consistency |
| F06 | Requested reporting scope được source-backed claim_scope xác nhận |
| F07 | Report outline/annual/native periods/selected slots/section inventory; QA not_applicable |
| F08 | Existing QA/report content validator: protected assertions, prose/templates, citations/caveats/limitations và status |
| F09 | Existing citation validator: complete rendered view, references, locator, bindings, markers và fingerprints |
| F10 | Output type/original status tương ứng source |
| F11 | Mandatory caveat, partial coverage, unknown scope, page-level hoặc unresolved source location warnings |

Mỗi entry phải khớp filters company/document/snapshot/period trước khi chọn B01.
Unknown/duplicate IDs fail closed; không lookup M5 storage hoặc M4 raw facts.
Final decision digest được tính lại bằng pure serialization/hash, không rerun
M6 critic/judge/calculator. M6 repository vẫn sở hữu admission và full proof
validation. Source fingerprint gồm original request + sorted ledger identity và
payload hashes; output fingerprint gồm exact source output + rendered view.
Các fingerprint là traceability, không phải chữ ký hoặc bằng chứng PDF đúng.

QA tối đa một query; report thường một, annual thêm đúng một query closing date.
Cùng retrieved entries tái sử dụng giữa các checks; không hydrate ledger cho từng
check. Production facade/persistence không đổi. Khi ledger read thất bại, BLOCK
vì không thể kiểm tra authority độc lập, kể cả upstream tự báo abstained.

## Financial assertions và citation integrity

Protected content inventory + approved deterministic presentation + exact
comparison chặn cả số liệu giả lẫn kết luận không có số. Sửa content, ratio,
percentage/unit, causal claim, recommendation, unsupported comparison/calculation
hoặc free financial prose không được coi là paraphrase hợp lệ. Không dùng regex
làm bằng chứng duy nhất và không dùng LLM kiểm định LLM.

Report validator giữ policy dedup M7-03: cùng typed assertion, native context,
kind/role và exact source thì hiển thị một accepted wording; giữ union equivalent
IDs, source slots, citations/caveats/limitations. Không ép mỗi ID thành câu lặp
lại, không suy tương đương từ cùng số. Outline giả merge/split mất binding bị chặn.

Fresh validation result được đặt trên detached source copy trước khi gọi citation
validator, độc lập cờ caller True/False. Rendered validation flag cũng không làm
authority. Marker/reference/source citation/locator/page/anchor/selector/pointer/
provenance/bbox/context/segment/claim IDs và annotation tails đều được so bằng
existing deterministic projection. Không tạo vị trí hoặc nâng provenance.
EvidenceCitation.financial_fact_verified=False giữ nguyên: source retrieval
authority khác M6 ACCEPT. Không đổi cờ thành True để đạt kiểm tra.

Page-level/unresolved/location_unavailable được ALLOW_WITH_CAVEAT khi identity
và accepted source vẫn nhất quán, original limitations còn đủ và renderer giữ
resolution status thật. Missing resource mapping giữ not_provided; không tự tạo
PDF URL hoặc tuyên bố mở được tài liệu. Source/document/snapshot conflict BLOCK.

## Decision aggregation và safe release

Ưu tiên cố định: bất kỳ failed check → BLOCK; không failed check và upstream
clarification_required đã được chứng minh → CLARIFICATION_REQUIRED; có mandatory
warning → ALLOW_WITH_CAVEAT; còn lại ALLOW. Warning không che critical failure.
Giới hạn thường trực như REPORT_LIMIT không tự biến mọi refusal thành caveated
financial output. Partial giữ partial; abstained/unsupported hợp lệ vẫn releasable.

ALLOW/ALLOW_WITH_CAVEAT chứa exact rendered text, structured references/locators,
bindings, caveats/limitations và verified IDs. BLOCK chỉ có thông báo trung tính
và structured reason codes; không financial body. Clarification chỉ có thông báo
trung tính yêu cầu làm rõ; không gửi financial assertions. original_status được
giữ khi typed output hợp lệ; unknown khi parse input thất bại. Caller chỉ nên
hiển thị validated_output, không source output đính kèm ở ngoài gate.

Annual period2025 + explicit period_end2025-12-31 giữ native roles exact_period/
closing_balance qua policy M7-02. Không suy31/12 từ năm. B01 sai document,
recovery snapshot hoặc closing date không được đưa vào output. D03-B10 giữ nguyên;
included_periods không cấp quyền cross-year/cross-document comparison.

## Frozen real-data evaluation và controls

Oracle `evaluation/m7-05-scenarios.json`, SHA256 LF
`b382e4232a94f9f695cdf83f142f6c3cc82815eab1d28e12e26656d73ae2063e`.
Được freeze trước run, từ accepted M6/M7-01/M7-03 oracles và exact saved outputs;
citation expectations dùng independent M7-04 oracle helper. Không lấy firewall
decision làm label; predecessor oracle/source/ledger hashes được pin và giữ nguyên.
Mỗi case pin request/context, status, exact claim/citation inventory, warnings,
blockers/release expectation và source artifact. Known mutations có expected
BLOCK và expected failing gate; không đổi nhãn sau run.

40 QA source-bound BBS và42 report có citations,8 refusals/clarifications,
40 adversarial controls trên accepted BBS outputs. Nhóm report saved_source có43
requests nhưng cash2022 không có accepted CFO support và là valid abstention;
vì vậy chỉ42 được đếm là report có real financial support. Nguồn gồm5 documents
BBS2021–2025,6 document/snapshot pairs kể cả recovery2022,58 admitted entries.
Các năm/kịch bản dùng lại sources; không phải82 PDF độc lập.

Controls bao phủ fake/pending IDs, accepted changed content, request/source/
snapshot/year/scope, caveat/citation deletion, unsupported cause/recommendation/
ratio, value/unit mutations, prose/status/flags/requirements/request co-tampering,
annual date/recovery, paragraph order/removal, invalid equivalent merge,
page/cell/anchor/pointer, render status/markers/text/provenance và bindings.
Synthetic malformed-ledger/duplicate/authority tests tách khỏi real cases.

```powershell
.venv/Scripts/python.exe scripts/evaluate_m7_05_firewall.py --output artifacts/evidence/M7-05-new
.venv/Scripts/python.exe -m pytest tests/unit/test_information_firewall.py -q
```

Output directory phải mới; không overwrite accepted artifacts. Cold hydrate qua
real M6 repository một lần, warm replay dùng read-only SavedVerifiedView và public
AND-query implementation M6. Đây là evaluation view, không persistence mới.
Composer/Writer không được gọi trong gate; OutlinePlanner chỉ được dùng ngoài gate
để khôi phục original report request từ saved accepted oracle. Production source
outputs được đọc từ saved JSON, không tạo synthetic claims thành real evidence.

## Kết quả, performance và samples

Final replay **130/130 PASS**, decision agreement100%, false acceptance/rejection0/0.
Lượt initial decision agreement130/130 nhưng strict checks129/130 do schema failure
chưa có F08 explanation; giữ run này riêng. Final-v2 tăng độ sát hai controls bằng
thay trực tiếp financial value/unit, không chỉ thêm một câu sai; labels/oracle giữ
nguyên. Final artifacts tại `artifacts/evidence/M7-05-final-v2/`.

| Expected / Actual | ALLOW | ALLOW_WITH_CAVEAT | BLOCK | CLARIFICATION_REQUIRED |
| --- | ---: | ---: | ---: | ---: |
| ALLOW | 6 | 0 | 0 | 0 |
| ALLOW_WITH_CAVEAT | 0 | 82 | 0 | 0 |
| BLOCK | 0 | 0 | 40 | 0 |
| CLARIFICATION_REQUIRED | 0 | 0 | 0 | 2 |

Allow/caveated/block/clarification agreement đều100% trong tập này. Zero unverified
claim leakage/unsupported financial statements/calculations/value-unit mutations
hoặc citation/source/scope/snapshot/period violations được phát hành trong các
controls tương ứng. Claim/citation/context/locator/caveat-retention checks đạt100%;
valid partial/abstained/unsupported outputs giữ semantics, page-level uncertain
được release có caveat. Không suy những kết quả này ra toàn bộ inputs tương lai.

| Performance / integrity | Final-v2 |
| --- | --- |
| Cold real M6 repository proof-validated load58 entries | 57,842s |
| Warm QA median/max, gồm controls | 191,15 / 2.050,54ms |
| Warm report median/max, gồm controls | 166,95 / 2.226,64ms |
| Warm real QA median/max | 154,04 / 1.856,26ms |
| Warm real report median/max | 141,47 / 1.775,51ms |
| Queries trong130 evaluations | 153;0–1/QA,0–2/report |
| Checks/result | 11 bình thường;2 khi invalid typed input chặn sớm |
| Serialized result median/max | 40.529,5 /192.467bytes |
| LLM/OCR/extraction/calculator calls | 0;Gateway/retrieval/calculator/generation sentinels không bị gọi |
| Protected hashes/Web local | 16.190/16.190 unchanged |

Cold proof replay tách khỏi warm evaluation; warm figures không đại diện cold
persistence latency. Thời gian đo local, có concurrency với focused tests.
Engineering validation:64 firewall controls (63 suite +1 percentage targeted),
263 M6/M7/source-context compatibility PASS. Ruff toàn repository/format/planning/
diff PASS. Compatibility XML tại M7-05-final/compatibility.xml; unit XML tại
M7-05-final-v2/firewall-unit.xml và percentage-control.xml. Không chạy full regression.

Ba samples: samples/qa-revenue-2025.json, samples/report-annual-general-2025.json,
samples/blocked-financial-mutation.json; mỗi sample có original identity,
checks/reasons/safe view và evidence mapping (blocked sample trỏ về base case).

## Root causes/fixes và giới hạn còn lại

1. Cross-module P1: local QA validator không có original request nên không phát
   hiện request scope/requirements bị đổi độc lập. Failing-boundary test chứng minh
   upstream validator vẫn valid; F02/F06 của firewall chặn. Không sửa accepted M7 code.
2. Cross-module P1: co-tampered source + rendered view có thể qua citation validator;
   independent ledger/request + protected validators chặn tại final gate.
3. Initial strict-trace failure: missing required citation bị schema chặn F01 nhưng
   thiếu check nội dung cụ thể. Bổ sung stage-specific F08/F09/F02 failure khi contract
   không đủ để kiểm định. Oracle giữ nguyên; không có leaked financial output.
4. Engineering fixture mới ban đầu xóa slot ở overview vốn trống, nên mutation là
   no-op. Sửa chọn section thực sự có slots; không thay production policy/oracle.

Không P0/P1 đã biết sau final validation. P2: exact-template gate
chưa chấp thuận free-form financial paraphrase; QA request inventory phải cập nhật
cùng future M7-01 policy; page-level locations/resource mapping; cold proof-history
load lớn; chưa independent PDF audit hoặc Multi-Agent benefit/end-to-end validation.

## What the Firewall Proves / What It Does Not Prove

Trong phạm vi oracle/controls, output nhất quán với admitted M6 ACCEPT ledger,
original request, approved scope/period/snapshot policy và exact citations;
financial body chưa đạt kiểm định không được phát hành. Partial/refusal/location
uncertainty được phân biệt với grounding failure.

Chưa chứng minh độc lập số liệu gốc trong PDF đúng; chưa chứng minh accuracy của
free financial prose từ LLM; chưa chứng minh mở đúng PDF khi resource mapping chưa
tồn tại; không chứng minh caller toàn quyền sửa trusted inputs là đáng tin; không
đánh đồng oracle agreement, engineering smoke và chất lượng tài chính end-to-end.

Next action: Tech Lead review M7-05 và đánh giá điều kiện hoàn thành milestone M7;
không tự bắt đầu M8.
