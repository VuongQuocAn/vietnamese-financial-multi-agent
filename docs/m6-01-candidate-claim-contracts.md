# M6-01 — Candidate Claim Contracts

Status: **REVIEW**, chờ Tech Lead nghiệm thu. Owner giao03/11/2026; baseline main/origin
`8407897f7dff75fa4614b508f7a035a872666138`.
Implementation `f803ebfc8ca8f7c41ee83e09808da453299e53c5` đã push trực tiếp main;
remote khớp SHA. [CI41636974349](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41636974349)
completed/SUCCESS đúng implementation SHA; Python3.12/Web smoke SUCCESS,
full regression SKIPPED. Checkpoint tiếp theo chỉ docs/planning [skip ci],
không gán CI implementation cho SHA checkpoint.

## API và mapping

Public API tại `vietnamese_financial_multi_agent.verification`:
`to_verification_input(result: OrchestrationResult) -> VerificationInput`.
Không I/O, financial tools, LLM hoặc inference trong adapter.

| M5 | M6 | Chính sách |
| --- | --- | --- |
| AggregatedCandidate / SpecialistCandidate fields | CandidateClaim kế thừa SpecialistCandidate | candidate_id/kind/content/company/document/snapshot/period, fact_references/metric_ids, supporting_evidence_ids, citations/calculation, caveats/missing_information/status giữ nguyên |
| candidate_id | ClaimProvenance.m5_candidate_id | Bằng candidate_id, không random ID |
| origins/origin_roles/supporting_references/conflict_ids | ClaimProvenance | Giữ thứ tự và exact payload; local evidence/candidate IDs có scope theo execution |
| supporting_evidence | VerificationEvidence | Alias SpecialistEvidence, không tạo schema cạnh tranh hoặc mất fields |
| CandidateConflict | VerificationInput.conflicts | Giữ toàn bộ candidate_ids; không chọn winner |
| OrchestrationResult.status | orchestration_status | Giữ nguyên; partial không bỏ claim |
| question/context và planner plan_id | question/context/source_plan_id | Trace về M5, không chép SupervisorResult vào mỗi claim |
| caveats/risks/missing_evidence/uncovered_requirements/stop_conditions/errors | Batch fields tương ứng | Global signals giữ nguyên |

`source_result_sha256` là SHA256 của JSON M5 canonical theo sorted keys,
ensure_ascii=False (gồm toàn bộ serialized result). Digest định danh exact input,
không phải stable semantic ID giữa các execution có timings khác nhau.
Candidate ID luôn là stable aggregated M5 ID; local candidate IDs giữ trong origins.

`CandidateClaim.status` giữ candidate/insufficient_evidence từ M5;
`verification_status=pending`, `financial_fact_verified=false`, `decision=null`.
Không suy verified từ approved_metric hoặc usable/usable_with_caveat.
`VerificationDecision` chỉ khai báo ACCEPT/REVISE/INVESTIGATE/ABSTAIN cho task sau;
M6-01 contract chưa nhận decision khác null. `VerificationFinding` khai báo bảy
loại mismatch/missing/unsupported/conflict/quality; adapter không phát sinh financial
finding. `ConversionIssue` dành riêng cho thiếu liên kết/cấu trúc trong handoff.

## Provenance và giới hạn

VerificationEvidence giữ exact RetrievalReference, company/document/snapshot/period,
operand_periods, label/value/unit/scale, canonical_item_id, citations và source caveats.
EvidenceCitation giữ EvidenceAnchor/FinancialSourceReference, PDF page, source_ref,
image, source_pointer, element/table/cell/line IDs, bbox/status và limitations hiện có.
Không nâng page-level thành cell-level. Quality/source-review annotations hiện có
được giữ verbatim; không tự suy thêm annotation không có ở M5.

FinancialCalculationResponse giữ formula/version/digest, approval, full trace operands,
supporting canonical references, closure, source reviews và reviewed MetricLineage.
Fact references của metric có thể là operands, không tự tạo independent fact claim.
Việc truy xuất lại EF-EG theo exact reference thuộc task sau; không materialize lại
EF-EG hoặc đưa toàn SupervisorResult vào claim.

Adapter deserialize/revalidate M5 JSON để bắt typed contract bị sửa sai, đồng thời
tách toàn bộ mutable objects khỏi M5 gốc. Missing citations/evidence/calculation/
origins và unresolved origin/conflict pointers tạo structured issues có source path;
payload vẫn được giữ, không bịa nguồn. Missing trace/lineage hoặc inconsistent citation
metadata cũng có issue; không kiểm tra giá trị/công thức đúng sai trong task này.
Invalid typed fields trả Pydantic ValidationError.
Không có candidate thì batch rỗng kể cả còn candidates trong SpecialistResult;
upstream stopped nhưng có aggregated candidates vẫn giữ payload cùng structured issue.
Reporting scope unresolved không ngăn biểu diễn single-document claim.

D03-B10/cross-document comparability, original/recovery2022, reporting scope,
source review/usable_with_caveat và ba approved formulas gross_margin/debt_to_assets/
revenue_yoy giữ nguyên; adapter không bypass hoặc chạy lại gates.

## Validation

95 bounded tests PASS (candidate contracts + Orchestrator/Router/ba Specialists);
sau bổ sung diagnostics metadata/trace, 10 final focused tests PASS. CI đã kiểm tra
final implementation SHA riêng. Ruff lint/format file đã sửa, planning101/diff PASS.
12.635 protected file hashes (raw/processed/accepted evidence và local Web) unchanged;
không stage artifacts/dataset/secrets. Không thay runtime M5, accepted outputs hoặc UI.

Final conversion tại `artifacts/evidence/M6-01-conversion-final/summary.json`:

| Nhóm | Cases PASS/total | Bản chất bằng chứng |
| --- | ---: | --- |
| Persisted BBS, mock generation đã lưu | 13/13 | E01/E02/E03/E06/E10/E11/E17/E18/E24/E25/E26/E31/E36 |
| Synthetic controls trên persisted BBS | 6/6 | E13/E23/E29/E30/E34/E35; missing/transport/dedup/conflict |
| Saved Gemini-response replay | 1/1 | E11; không fresh live |
| Saved replay có synthetic missing CFO | 1/1 | E37; không natural source failure |
| Tổng conversion integrity | 21/21 | 26 claims, 5 calculations, 1 conflict, 0 conversion issues |

Bao phủ BBS2021–2025; original/recovery2022 ambiguity giữ clarification_required
ở E17, recovery metric ở E25/E26. Ba approved formulas gross_margin/debt_to_assets/
revenue_yoy có full typed lineage giữ exact payload. Status counts: completed12,
partial4, clarification_required1, blocked2, failed2. Abstained/unsupported/no-candidate
và malformed evidence được kiểm bằng synthetic unit controls riêng, không nhận là
real-data outcome. Từng batch được convert hai lần, round-trip, dựng lại M5 candidate
fields để so exact, đối chiếu globals và input hash trước/sau. E34 giữ hai origins;
E35 giữ hai candidates/conflict, không sửa giá trị synthetic hoặc chọn winner.

Initial focused run: 9 PASS/1 FAIL do test giả định metric.fact_references rỗng.
Root cause: M5 dùng fact_references giữ supporting operand identities dù metric-only
không tạo independent fact claims. Sửa assertion theo actual contract, không sửa M5;
final10/10 PASS. Không có runtime defect từ accepted BBS conversions; zero live calls.

Script đọc accepted M5-08 source map và kiểm tra hash trước/sau, không chạy lại M5:

```powershell
python scripts/evaluate_m6_01_conversion.py --output artifacts/evidence/M6-01-conversion-new
```

Phân biệt persisted BBS + mock generation, synthetic controls trên persisted BBS,
saved Gemini-response replay và replay có synthetic control. Đây là kiểm tra
conversion/provenance integrity, chưa phải verification accuracy hay benchmark mới.

Next action: Tech Lead review M6-01.
