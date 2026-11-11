# M5-LITE-01 — Simplified Multi-Agent Orchestration

Ngày11/11/2026; **REVIEW**, chờ Tech Lead nghiệm thu. Baseline `a7da263`.
Implementation: một commit `feat(m5): add simplified candidate orchestration` trên main;
SHA xác định bằng `git log -1 --format=%H -- src/agents/lite_orchestrator.py`.
CI exactSHA được xác minh sau push và báo trong bàn giao; chưa suy CI từ local.

## Kiến trúc và thay đổi

`m5_lite=False` giữ mặc định legacy. Bật flag: trusted context → SupervisorLite
→ tasks ngắn `{specialist,objective,sources}` → tools + Specialist → candidate
aggregation → **existing** `to_verification_input` → native M6 → Ledger → M7.
Chạy được cùng `m7_lite=True`; không sửa nghiệp vụ M6/M7. Document QA riêng vẫn
theo nhánh hiện có; phạm vi mới là financial orchestration.

Supervisor chỉ một plan, chọn trong ba roles hiện có: profitability,
liquidity_and_leverage, cash_flow_and_earnings_quality. `sources` là handles tùy
chọn để truy xuất từ inventory metadata ngắn; identity/period/scope do backend
đối chiếu catalog/context. Không là danh sách obligations. Không PlannerProposal,
DAG, required-target matching, Adaptive Judge, coverage approval hoặc replan.
JSON/provider lỗi có lexical fallback có ghi nhận; không retry. Các nhánh chạy
tuần tự độc lập; lỗi nhánh sau không hủy candidates nhánh trước.

Tái sử dụng evidence selection, numeric renderers và analyses/dynamic arithmetic
trong `specialist_common`/Financial Calculator; prompt Lite riêng cho phép nhận
định có evidence, assumptions, limitations và operations. Không dùng grammar
numeric làm điều kiện duyệt analyses. Full facts/citations/proofs giữ ở Python;
Gemini chỉ nhận objective và digest. Numeric shorthand `E001` ánh xạ đúng object
đã chọn trong backend; unknown IDs bị loại. Claims luôn là candidates, không
tự ACCEPT. Exact dedup/provenance và adapter M6 được tái sử dụng nguyên bản.

Files: module `src/agents/lite_orchestrator.py`; integration trong
`src/api/financial_qa_pipeline.py`, flag trong `qa_pipeline_contracts.py`;
`tests/unit/test_m5_lite.py`, `scripts/evaluate_m5_lite.py`; thêm test vào CI,
checker hỗ trợ M5-LITE ID, planning và báo cáo này. Các local edits có sẵn được
giữ ngoài implementation commit, bao gồm `specialist_common.py` và M7.

## Offline validation

- 4 Lite controls PASS: single/multi dispatch, tools/calculation, native adapter,
  source identities, partial/failure isolation, một plan, JSON/shorthand fallback,
  unknown sources và legacy flag. Fixtures engineering được ghi rõ synthetic.
- 15 legacy orchestration/native pipeline controls PASS; không full suite.
- BBS thật đã lưu: Case A3candidates, Case B8candidates/hai roles; cả hai adapter0issues.
- Một native M6→Ledger→M7 Lite smoke: **3 ACCEPT/stored**, không Gemini,
  final `partial_verified_coverage`; candidate chưa ACCEPT không được phát hành.
  Reporting scope có `undetermined` được giữ; không nâng thành chứng nhận accuracy.
- Final parser được replay trên responses live đã lưu: A4/B8candidates,
  adapter0issues; không thêm network. Những exclusions còn lại giữ trace.
- Exact staged tree tách khỏi local edits:19targeted tests PASS; Ruff check/format
  PASS(634files), planning checker PASS124tasks. Working planning125tasks gồm
  pending local GEN-01a được giữ ngoài commit. BBS A/B và native smoke trên
  staged code cũng PASS với3/8candidates,0adapterissues và3ACCEPT/stored.

Artifacts đầy đủ, không commit dữ liệu: `artifacts/evidence/M5-LITE-01/`:
`offline.json`, `pipeline-smoke.json`, `live.json`, `provider-events.json`,
`replay.json`; mỗi result giữ plan, execution/tool requests/responses,
candidate identities, fact references/citations/calculation proofs và adapter.

## Gemini live: đúng4calls, không retry/OCR

Model `gemini-3.5-flash-lite`. A dùng lexical Supervisor + một live Specialist;
B dùng live Supervisor + hai live Specialists để vừa hạn mức. Không tên case
hoặc kết quả hardcode trong runtime. Các câu hỏi nguyên văn:

A: “Doanh thu thuần năm 2025 và tăng trưởng doanh thu 2025 so với 2024 của BBS là bao nhiêu?”

B: “So sánh doanh thu thuần và lợi nhuận gộp giữa 2024 và 2025, đồng thời phân tích tổng tài sản và tổng nợ phải trả năm 2025 của BBS.”

| Call | Agent | Input chars | Input/output/total tokens | Kết quả |
| --- | --- | ---: | --- | --- |
| 1 | A Profitability | 2778 | 906/418/1324 | success; original1interpretation candidate |
| 2 | B Supervisor | 4954 | 1664/161/1825 | success; hai tasks phù hợp |
| 3 | B Profitability | 1912 | unknown/unknown/unknown | HTTP503; giữ4numeric candidates bằng fallback M4 |
| 4 | B Liquidity | 1487 | 498/426/924 | success; original2interpretation candidates |

Tổng biết được3068input+1005output=4073tokens, **một call usageunknown**, chi phíunknown.
Không coi unknown là0. Mọi payload dưới8000chars, output caps900Supervisor/2500Specialist.
Runner có reservation độc quyền và tối đa4requests, không có recovery/retry.

### Plan, tools và findings

A: một task Profitability, objective là câu hỏi A; nguồn doanh thu2025/2024 và
revenue_yoy. Trace: `get_financial_fact`4lần (hai lần cho metric operands),
`get_evidence_sources`2lần, `calculate_financial_metric`1lần→computed26,71%.
Doanh thu2025/2024 từ PDF7, selectors `link/4`/`link/5`, cùng exact document/snapshot.
Original Gemini chọn claims bằng IDs; parser đầu tiên reject3shorthand claims.
Một nhận định về hai doanh thu được giữ. Một analysis tăng trưởng bị loại do
trộn metric evidence vào dynamic fact operands; đây là giới hạn schema/tool input,
không phải PDF thiếu dữ liệu. **Original A chưa trả finding tăng trưởng** dù M4 tính được.

Final offline replay: giữ4candidates: hai facts doanh thu, approved revenue_yoy
với full calculation proof và một interpretation về doanh thu. Cả4candidates
qua native M6 adapter0issues. Analysis lỗi vẫn bị loại, trạng thái **partial**.
Numeric shorthand fix/prompt clarification chỉ offline replay, chưa live lại.

B Supervisor giao Profitability so sánh doanh thu/lợi nhuận gộp2024–2025
(S9,S10,S13,S14), Liquidity phân tích tổng tài sản/nợ2025(S3,S5).
Tools thật:6`get_financial_fact`+6`get_evidence_sources`; không calculation cần
cho các numeric facts. Profitability503 không cản Liquidity chạy; không replan.
Original6candidates:4numeric facts fallback và2interpretations của Liquidity.
Final replay8candidates: thêm2numeric facts từ shorthand, không tạo số mới.
Liquidity có ghi thiếu dữ kiện thuộc mục tiêu Profitability do nhìn full question;
những gaps này không loại findings khác. Chưa chứng minh lập luận so sánh sinh lời
live thành công vì nhánh đó lỗi provider.

| Nhóm candidate | Nguồn BBS giữ nguyên | Proof/kết quả |
| --- | --- | --- |
| Doanh thu2025/2024 | PDF7 link4/link5 | facts450.474.531.227/355.507.372.286VND |
| Tăng trưởng doanh thu | cùng hai facts trên | M4revenue_yoy26,71%, full approval/operand/lineage |
| Lợi nhuận gộp2025/2024 | PDF7 link8/link9 | facts32.482.519.668/36.432.410.381VND |
| Tài sản/nợ cuối2025 | PDF5link40/PDF6link0 | facts266.086.680.765/157.146.559.558VND |
| Interpretations | cùng sources được tham chiếu | candidate reasoning, assumptions/limitations giữ nguyên |

Offline B lexical còn lấy balances đầu2025 tại PDF5link41/PDF6link1; ngày gốc
`2025-01-01` giữ nguyên, không đổi thành cuối2024. Live Supervisor chọn cuối2025.

## M6 compatibility và giới hạn

Native adapter giữ claim identity/origin role, company/document/snapshot/period,
fact references, citations, calculation proof, kind và assumptions/limitations.
Original live7candidates và final replay12candidates đều0adapterissues. Đây là
**structural compatibility**, không phải ACCEPT. Live/replay findings không được
ghi Ledger hoặc đưa thẳng M7; chỉ smoke numeric riêng đi qua native M6 admission.

Chưa kiểm chứng semantic ACCEPT của các live interpretations, chưa live E2E M6/M7,
chưa đánh giá full PDF hoặc lợi ích Multi-Agent bằng benchmark đối chứng.
M6 reasoning/semantic support cần Tech Lead đánh giá trong M6-LITE-01 nếu được giao;
không sửa M6, không mở task tiếp theo. Chưa kiểm thử live Cash Flow và fallback429;
provider503 có evidence thực. Các scoped metadata ambiguities hiện có vẫn giữ.

## Git và bàn giao

Targeted checks/Ruff/planning/diff và staged-tree validation được xác minh trước
commit; CI remote thuộc đúng implementation SHA sau push. Chỉ một implementation
commit; không đưa local M7/GEN/Web hoặc artifacts/secrets vào index.

Next action: Tech Lead review M5-LITE-01 và giới hạn original live/final replay.
