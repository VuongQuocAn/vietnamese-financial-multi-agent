# M5-06 — Cash Flow and Earnings Quality Specialist

Ngày 03/11/2026 (Asia/Bangkok). Baseline main/origin
`7364acc2f9c9e6310ac2b4a152d70ddbcc6cc6dc`. Trạng thái REVIEW;
implementation `b7bd376530e84e93ab04189361ae07672c7c72d2` đã push main.
[CI41552323768](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41552323768)
completed/SUCCESS đúng SHA: Python3.12 và Web smoke SUCCESS; full regression SKIPPED.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI implementation cho SHA đó.
Chỉ Tech Lead nghiệm thu DONE.

## Kiến trúc và public API

`CashFlowEarningsQualitySpecialist` nhận `SupervisorResult`, tái sử dụng
`select_evidence()` / `_fact_error()` / `_citations_valid()` và
`generate_candidates()` từ `specialist_common`. Tái sử dụng nguyên
`SpecialistEvidence`, `SpecialistCandidate`, `SpecialistResult`, `SpecialistTrace`,
`SharedLLMGateway` và `SPECIALIST_BOUNDARIES`.
Common chỉ bổ sung literals version/role; defaults, public APIs và outputs của
M5-04/M5-05 giữ nguyên. Không framework, routing, reflection loop hoặc M6.

```python
from vietnamese_financial_multi_agent.agents import CashFlowEarningsQualitySpecialist

specialist = CashFlowEarningsQualitySpecialist(gateway=gateway, model=model_identity)
result = specialist.analyze(question=question, supervisor_result=supervisor_result)
```

Default model `gemini-3.5-flash-lite`, cấu hình `ModelIdentity` được giữ cho các
benchmark sau. Một call/analysis nếu có evidence eligible. Digest chỉ gồm câu hỏi,
relevant B02/B03 values/labels/IDs, company/document/snapshot, period/unit/currency/
scale, semantic type, source caveats, missing evidence và upstream risks/status.
Không gửi PDF hoặc cho Gemini tự tạo citations.

Proposal typed gồm evidence ID, kind, meaning, period, sign và statement. Gemini
chọn chỉ tiêu, tạo factual proposals và diễn giải dấu trong ngữ pháp được duyệt;
backend so exact Decimal sign, toàn câu, period, numeric literals và ngữ nghĩa.
Fact statements được backend render; prose ngoài grammar, fabricated IDs/numbers/
citations, unapproved metrics hoặc mệnh đề nhân quả đều không thành candidate.

CFO và lợi nhuận tạo **hai factual candidates riêng**, mỗi candidate liên kết đủ
fact reference/evidence ID/citations của chính nó. Không tạo combined claim chỉ
dẫn một nguồn. Candidate giữ company/document/snapshot/period, caveats, raw
proposal/trace và Gateway usage/cost/provenance; `financial_fact_verified=False`.

## Coverage audit trước đánh giá

Audit lưu exact records/periods/document/snapshot/source lookup/citations ở
`artifacts/evidence/M5-06-audit/coverage-audit.json`, không sửa canonical data.

| Filing/snapshot | B03 dùng được với caveat | B02 cùng filing | Giới hạn |
| --- | --- | --- | --- |
| 2021 original | CFO, investing, financing, closing cash | PBT, PAT | Scope chưa confirmed |
| 2022 original normalized_projection | Không: cả bốn B03 bị quality blocked | PBT, PAT dùng được | Không tự chuyển recovery |
| 2022 recovery được chỉ định | CFO, investing, financing, closing cash | PBT, PAT | Số tiền giống original, quality/binding khác |
| 2023 original | CFO, investing, financing, closing cash | PBT, PAT | Scope chưa confirmed |
| 2024 original | CFO, investing, financing, closing cash | PBT, PAT | Scope chưa confirmed |
| 2025 original | CFO, investing, financing, closing cash | PBT, PAT | Scope chưa confirmed |

`net_cash_flow` và `opening_cash` không có accepted canonical facts trong toàn bộ
phạm vi trên. Scenario positive cho net cash được thay bằng missing-evidence
control thật; không dùng raw OCR line chưa mapped làm financial fact.
Các facts dùng ở đây là annual `fiscal_year`, unit/currency VND, scale 1.
B03 opening/closing cash là balance trong kỳ báo cáo, không đổi period thành as_of.

Source-review **lookup** phải `found`, có matches và citations hợp lệ theo common.
S07/S17 có row-review status `unverified`; thiếu
controlled manual row review không được biến thành row-verified. Giữ thêm caveat
`source_review_status:unverified` trên evidence/candidates. Missing lookup/matches,
source inconsistency, insufficient/conflicted decisions hoặc sai citations bị loại.
Provenance vẫn page-level/uncertain khi nguồn chỉ hỗ trợ mức đó.

## Domain policies

- B03 cash facts đúng statement B03, B02 profit đúng B02; fiscal-year/mapped ID,
  currency/unit/scale và query/selector context phải khớp. Không convert/rescale.
- Co-presentation yêu cầu cùng company/document/snapshot/period/unit/currency/scale
  và reporting-scope context; không chọn latest/original/recovery bằng suy đoán.
- Scope dùng `_explicit_constraints()` của M5-02. “Giữ riêng bằng chứng” không yêu
  cầu báo cáo riêng. Explicit riêng/hợp nhất chưa confirmed vẫn abstain; cả hai
  scopes thật sự cũng abstain. Synthetic confirmed-scope tests kiểm nhánh hợp lệ.
- Chỉ flow indicators có sign interpretation: dương → vào thuần, âm → ra thuần,
  zero → giá trị thuần bằng không; không suy không có gross inflows/outflows.
- Không CFO/Net Income, cash conversion, accrual, FCF, CFO margin, coverage hoặc
  earnings-quality score; không tính chênh lệch. Không cash bridge identity thiếu
  điều chỉnh/tỷ giá. Không kết luận chất lượng cao/thấp, thao túng, khả năng trả nợ,
  dòng tiền bền vững, dự báo hay nguyên nhân do phải thu/tồn kho/khấu hao.
- D03-B10 tiếp tục blocked. Chưa claim verification hoặc chất lượng tài chính toàn PDF.

## Phương pháp và initial failures

Manifest `evaluation/m5-06-scenarios.json` có 28 scenarios. Golden targets do
manifest chốt sau audit; số/context/citations từ persisted canonical facts và
accepted source construction, không lấy Gemini output hoặc specialist digest làm gold.
Scorer kiểm final text, exact value/sign, references, full citations, context,
semantic validity, coverage và abstention. Mutation test kiểm scorer loại đổi dấu,
đổi trang, thêm quality judgment và bỏ supporting evidence.

Các controls conflict/period/unit/citation/missing-profit là **synthetic injected
failures trên bản copy evidence BBS thật**. Những ca còn lại dùng persisted traces
S07/S17 hoặc deterministic Planner → Supervisor, không gọi lại Gemini Planner hay
Specialists cũ. Offline mock/replay không đo năng lực Gemini.

Initial failures được giữ nguyên:

1. `M5-06-offline-initial`: C12 kỳ vọng partial sai. Required net-cash fact thiếu
   ngay preflight làm toàn plan blocked theo contract đã duyệt. Sửa expected thành
   zero-call abstention, thêm C28 runtime missing-profit control eligible cho live;
   không bypass policy hoặc thay đổi Supervisor/Planner semantics.
2. C23 yêu cầu origin `original_extraction` trong khi audit snapshot gốc có origin
   `normalized_projection`. Sửa manifest chỉ định exact snapshot qua PlannerContext;
   không sửa catalog hoặc chọn fallback. Lần sửa manifest đầu bị PowerShell encoding
   làm hỏng chữ Việt; sửa UTF-8 trước đánh giá cuối.
3. `M5-06-offline-final`: gate mới đòi manual row reviews đã chặn sai accepted
   source-review lookups `found/unverified`. Bỏ gate vượt policy common, giữ caveat
   explicit và regression test cho found/unverified. Không nâng source quality.

Các lỗi trên đều offline, chưa tốn Gemini calls. Audit runner cũng đã sửa cách lấy
upstream từ saved S03/S06/S08 khi artifact cũ không lưu bản copy upstream riêng.

C20 được chỉnh expected để giữ profit độc lập khi CFO sai unit bị loại, thay vì
đòi abstain toàn bộ. Offline v2 đã chạy đủ 28 scenarios, sau đó summary writer lỗi
vì latency `None` của zero-call controls. Fix lọc latency unknown, thêm regression
test và dùng `--summarize-from` để tổng hợp scores đã lưu sang thư mục mới; không
chạy lại scenarios hoặc Gemini. Source hashes được lưu ở `summary-source.json`;
summary repair có `fresh_execution=False`. Các exceptions/failures cũ giữ nguyên.

## Kết quả và evidence

| Metric | Offline mock trên persisted BBS, prompt v2 | Gemini initial v1 | Gemini targeted v2 |
| --- | --- | --- | --- |
| Scenario correctness | 28/28 | 5/6 | 2/2 |
| Grounding / numeric / citations | 27/27 mỗi loại | 9/9 mỗi loại | 4/4 mỗi loại |
| Sign interpretation | 2/2 | 0 accepted | 2/2 |
| Accounting semantic validity | 27/27 | 9/9 | 4/4 |
| Multi-target completeness | 7/7 | 2/3 | 1/1 |
| Unsupported final claims | 0/27 | 0/9 | 0/4 |
| Appropriate abstention | 9/9 | N/A, eligible cases | N/A, eligible cases |
| Claim coverage | 27/27 | 9/10 | 3/3 |
| Actual calls | 0 (19 mock transports) | 6 | 2 |
| Tokens input/output/total | N/A | 11.385 / 1.498 / 12.883 | 3.810 / 410 / 4.220 |
| LLM latency median/max | Mock, không dùng làm live latency | 1.413 / 1.727 ms | 1.452 / 1.667 ms |

Initial C11 thiếu sign interpretation được chấp nhận: model điền enum `positive`,
raw number và activity rút gọn vào câu thay vì giữ placeholders. Các sign proposals
phụ ở C01/C09/C22 cũng bị backend loại. Không có unsupported final claim lọt qua.
Sửa **prompt v2**, không nới grammar/grounding: phân biệt sign enum với placeholder
tiếng Việt, thêm example nguyên template, yêu cầu copy placeholders. Regression
vẫn loại prose có enum `positive`. Targeted C01/C11 dùng saved real upstreams,
hai actual calls, không phải fresh six-case benchmark. C01 vẫn thêm diễn giải có
nguồn và ghi thiếu thông tin chi tiết; giữ partial, không xóa limitation để đẹp số.

Tổng 8 actual calls / 17.103 tokens, targeted chỉ 2/4 calls được phép; không retry,
rotation hoặc gọi Gemini Planner/Specialists cũ. Initial failures/raw proposals/
final candidates/usage/model/provenance/prompt versions giữ riêng. Giá tiền N/A
khi Gateway không cung cấp cost đã biết. Không công bố earnings-quality accuracy.

Evidence local (ignored):

- `M5-06-offline-v2`: 28 per-case scores/raw/result/upstream; summary repaired ở
  `M5-06-offline-v2-summary`, cùng đường dẫn gốc `artifacts/evidence/`.
- `M5-06-live-initial`: 6 initial attempts/responses/results/scores; không ghi đè.
- `M5-06-live-targeted-v2`: 2 targeted attempts/responses/results, tham chiếu initial.
- `M5-06-offline-complete/regression-summary.json`: bounded checks hoàn tất trước
  summary latency exception; giữ raw checks riêng, không coi exception là regression failure.
- `M5-06-compatibility-baseline` / `M5-06-compatibility-final`: 6 before/after
  outputs exact sau bỏ random IDs/correlation/timing. R08 ở bộ này là historical
  empty-proposal abstention; bổ sung accepted corrected R08 2 candidates exact ở
  `M5-06-handoff/compatibility-approved-R08.json`. Tổng 7/7 replays, 0 live calls.
- `M5-06-handoff/hash-validation.json`: 4.135 protected hashes so original audit
  unchanged; gồm accepted artifacts, dataset/PDF/OCR inputs theo manifest và Web local.

## Ba candidates thật và nguồn hai phía

1. Initial C01: “Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là
   14.319.681.754 VND.” BBS2025, B03 PDF trang 8; 11 exact source citations.
2. Initial C09: “Lợi nhuận kế toán trước thuế của kỳ 2025 là 9.113.447.433 VND.”
   BBS2025, B02 PDF trang 7; 10 exact source citations. C09 đồng thời có candidate
   CFO ở mục 1, cùng document/snapshot `D-01/normalized-v2`, period 2025, VND/scale1;
   hai candidates giữ fact references và nguồn riêng, không ratio/chênh lệch/causal claim.
3. Targeted C11: “Lưu chuyển tiền thuần từ hoạt động kinh doanh trong kỳ 2023 là
   44.460.337.825 VND, mang giá trị dương, phản ánh dòng tiền vào thuần từ hoạt động
   kinh doanh theo chỉ tiêu được báo cáo.” BBS2023, B03 trang 8; 11 exact citations,
   cùng supporting fact với factual candidate. Đây là **live supported interpretation**.

C22 initial giữ CFO fact và nêu rõ chưa đủ thông tin kết luận chất lượng lợi nhuận,
dòng tiền bền vững hoặc nguyên nhân từ tồn kho. Backend không có meaning/schema
cho những kết luận đó. D03-B10, explicit unknown scope và snapshot ambiguity vẫn
abstain; thiếu evidence không bị biến thành zero. Claims chưa verified.

## Regression và validation

Local: 245 bounded tests PASS ở vòng implementation; bản cuối 24 focused tests
PASS, gồm scope, sign, source/citations, independent scorer và summary regression.
Ruff modified files, planning checker và diff check đạt trước handoff.
Bounded real checks: 18 accepted calculations exact/independent arithmetic,
29 retrieval queries, 36 undetermined cross-document pairs, QA36 exact,
M5-01 15 contract cases, M5-03 19 preserved traces, D-06/D-07 giữ nguyên.
M5-02 offline18/fresh4/6/raw5/6/replay6/6 và M5-04/M5-05 live histories được bảo toàn,
không gọi lại thành fresh evaluation. Không full regression hoặc OCR/extraction.
CI41552323768 completed/SUCCESS đúng implementation SHA; metadata jobs/steps ở
`M5-06-handoff/ci-exact-sha.json`. Không gán CI này cho documentation checkpoint.

## Reproduce trong môi trường có persisted BBS

```powershell
.venv/Scripts/python.exe scripts/evaluate_m5_06_cash_flow.py --audit --output artifacts/evidence/M5-06-new-audit
.venv/Scripts/python.exe scripts/evaluate_m5_06_cash_flow.py --regressions --output artifacts/evidence/M5-06-new-offline
.venv/Scripts/python.exe scripts/evaluate_m5_06_cash_flow.py --allow-live --upstream-from artifacts/evidence/M5-06-offline-complete --output artifacts/evidence/M5-06-new-live
```

Lệnh live chỉ dùng khi còn ngân sách được Owner giao: evaluator đếm persisted
attempt ledger, tối đa 6 initial và 4 targeted, không auto retry/rotation. Sau khi
đã dùng hết ngân sách initial, muốn kiểm lại dùng saved-response replay; fresh live
cần task/ngân sách riêng. Key đọc qua resolver hiện có; không log hoặc commit key.
Mọi artifact mới ở thư mục ignored riêng; original inputs và Web local được hash.

Next action: Tech Lead review M5-06; không bắt đầu M5-07.
