# QA-Fix-02 — M5 Planner & Downstream Recovery

Ngày06/11/2026 (Asia/Bangkok). **REVIEW — chờ Tech Lead nghiệm thu**.
[Spec](../planning/tasks/QA/QA-Fix-02.md). Baseline main/origin `0451b37`;
implementation là commit chứa báo cáo này; CI đối chiếu đúng SHA qua commit checks.

## A. Executive Summary

F02: **confirmed/fixed trong phạm vi capability/intent**. Broad domains cần
clarification, không tự chọn ratios. F03: client recovery đã bổ sung và kiểm bằng
OFFLINE_TEST; nguyên nhân sâu503 của QA-Q01 **unresolved**. Fresh task này:
**4/7** chạy đủ downstream (Q03, Q06, N02, N03),
8 Specialist invocations, 15/20 provider attempts,
15 success, HTTP503=0,
HTTP429=0; 50598 known tokens/0 unknown-usage calls.
Không đổi model `gemini-3.5-flash-lite`, không key rotation/OCR/extraction/M6/M7 release.
Sáu câu hỏi khác nhau,7fresh runs do một Q08 correction có căn cứ alias gap;
không thử lại để ép successful status. Bốn runs completed, Q07/Q08 và Q08correction
clarification_required;0failed. Tổng21candidate claims,8Specialist invocations.
Runtime sửa: `query_planner.py`, `planner_contracts.py`, `llm_gateway.py`,
`adaptive_router.py`, `orchestrator.py`; Supervisor/M4/M6/M7 implementation giữ nguyên.
CI chỉ thêm new regression file vào focused suite.

| Case | Planner | Orchestration | Specialists executed | Candidates | Calls | Tokens | Latency |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q03 | planned | completed | Profitability | 1 | 2 | 6247 | 28.707s |
| Q06 | planned | completed | Profitability, Liquidity & Leverage | 8 | 3 | 10184 | 41.048s |
| N02 | planned | completed | Profitability, Cash Flow & Earnings Quality | 3 | 3 | 7962 | 21.614s |
| N03 | planned | completed | Profitability, Liquidity & Leverage, Cash Flow & Earnings Quality | 9 | 4 | 12589 | 48.790s |
| Q07 | clarification_required | clarification_required | NOT_EXECUTED | 0 | 1 | 5137 | 3.351s |
| Q08 | clarification_required | clarification_required | NOT_EXECUTED | 0 | 1 | 4129 | 1.290s |
| Q08-correction | clarification_required | clarification_required | NOT_EXECUTED | 0 | 1 | 4350 | 2.508s |

## B. Root-Cause Analysis

| Finding | Root cause | Confidence | Fix |
| --- | --- | --- | --- |
| F02 | Saved Gemini proposal ghi cả ba registered role là unsupported, operations rỗng. `_resolve()` short-circuit unsupported trước Supervisor/Router. Prompt chưa phân biệt broad domain với exact targets; chưa có semantic guard. | Confirmed về proposal/stop/guard thiếu; prompt contribution probable | Prompt + bounded alias semantic policy; giữ raw và effective proposals |
| F03 | Saved3responses là provider HTTP503/category provider_unavailable, usage unknown. Adapter/Gateway không retry; SDK cũng attempts1. | Confirmed client behavior; provider outage/quota root cause unresolved | Opt-in Gateway retry một lần503,0,25s backoff,total deadline; preserve attempts |

Không có bằng chứng Router gây F02 hoặc503 do hết quota. Credential resolver giữ
key index0; không thử các key khác. HTTP429/rate-limit/quota, auth, timeout,
invalid JSON, schema-contract và semantic rejection là các nhóm riêng.

Planner kiểm schema rồi semantic policy, resolve metadata/catalog, materialize và
validate như trước. Recovery chỉ dựng operations khi aliases xác định explicit
targets, giữ metadata gốc và tất cả accounting gates. Không recovery thành số liệu.
Nếu proposal có DAG nhưng bỏ explicit target: clarify; unapproved metric không
được thay bằng approved metric khác. Supported+unsupported giữ unsupported portion
cho Router partial. Registered roles/capabilities không đồng nghĩa mọi metric thuộc
domain đã được approve.

## C. Planner Before/After

Q07 nguyên văn: “Phân tích khả năng sinh lời, tình hình nợ và dòng tiền kinh doanh của BBS năm 2025.”

- SAVED_TRACE trước: `unsupported`, intent unsupported,
  requirements/operations rỗng; unsupported cả3roles,0downstream.
- SAVED_TRACE sau: `clarification_required`; missing
  `explicit_target_for:cash_flow_and_earnings_quality;explicit_target_for:liquidity_and_leverage;explicit_target_for:profitability`. Giữ proposal gốc;
  không chọn ROA/ROE/gross margin/debt ratio đại diện.
- ACTUAL_EXECUTION sau: xem Q07 dưới; không coi replay là fresh collaboration.
- Hai paraphrases mới N02/N03 được chạy fresh; exact questions, intent,
  requirements/operations/stages bên dưới. OFFLINE_TEST còn đảo thứ tự domains,
  dùng TEST2030,2/3targets và scope/year/missing evidence controls.
- Q08 initial bộc lộ alias gap: “dòng tiền kinh doanh” chưa match CFO. Hai failing
  controls dẫn đến thêm query aliases này/CFO và đưa shared aliases vào prompt.
  Q08 correction nhận rõ revenue+CFO, model yêu cầu criteria cho quality verdict;
  downstream NOT_EXECUTED đúng policy. Fresh correction còn ghi generic omission
  reason: một failing control bổ sung đã sửa để giữ nguyên clarification detail;
  final-policy behavior kiểm OFFLINE_TEST, không gọi Gemini lần nữa.

## D–E. Actual Multi-Agent Results & Collaboration

Tools thực thi thật: {'find_financial_facts': 13, 'get_evidence_sources': 13, 'calculate_financial_metric': 5, 'get_metric_evidence_lineage': 5}. Specialists: {'profitability': 4, 'liquidity_and_leverage': 2, 'cash_flow_and_earnings_quality': 2}.
Supervisor gọi M4; các Specialists chia sẻ typed context/evidence do Orchestrator
project. Không có bằng chứng messaging trực tiếp agent-to-agent. Aggregation chỉ
tổng hợp candidates và giữ origins; không ghi ledger hoặc phát hành M7.

### Q03 — completed

> Biên lợi nhuận gộp của BBS năm 2025 là bao nhiêu? Hãy nêu công thức và các số liệu sử dụng.

Execution mode: **ACTUAL_EXECUTION**.

Planner: raw intent `evidence_explanation` → effective `evidence_explanation`, status `planned`. Requirements: `b02.gross_profit, b02.net_revenue`; formulas `gross_margin`.

Operations: find_financial_facts, find_financial_facts, get_evidence_sources, get_evidence_sources, calculate_financial_metric, get_metric_evidence_lineage. Missing/blocked: `none`; stop `all_required_evidence_resolved`.

Raw targets: `['b02.gross_profit', 'b02.net_revenue']`; raw missing: `[]`; raw unsupported: `[]`. Policy: `[{'stage': 'semantic_policy', 'outcome': 'consistent', 'reasons': []}, {'stage': 'semantic_policy', 'outcome': 'validated', 'reasons': []}]`.

| Stage | Selected | Executed | Status | Duration |
| --- | --- | --- | --- | --- |
| Planner | yes | yes | planned | 7050.8 ms |
| Supervisor | yes | yes | completed | 19752.0 ms |
| Router | yes | yes | routed | 118.5 ms |
| Profitability | yes | yes | generated | 1759.3 ms |
| Liquidity & Leverage | no | no | NOT_EXECUTED | — |
| Cash Flow & Earnings Quality | no | no | NOT_EXECUTED | — |
| Aggregation | yes | yes | completed | 25.8 ms |

Supervisor gọi M4; Specialists nhận typed evidence projection, không gọi thêm M4:

| Tool | Caller | Input chính | Result | Time | Evidence |
| --- | --- | --- | --- | --- | --- |
| find_financial_facts | Supervisor | b02.gross_profit / 2025 | completed/found | 2324.6 ms | op_0; PDF pages [7] |
| find_financial_facts | Supervisor | b02.net_revenue / 2025 | completed/found | 163.8 ms | op_1; PDF pages [7] |
| get_evidence_sources | Supervisor | fact | completed/found | 2320.2 ms | op_2; PDF pages [7] |
| get_evidence_sources | Supervisor | fact | completed/found | 185.0 ms | op_3; PDF pages [7] |
| calculate_financial_metric | Supervisor | gross_margin | completed/computed | 3077.0 ms | op_4; PDF pages [7] |
| get_metric_evidence_lineage | Supervisor | metric lineage | completed/found | 2690.6 ms | op_5, op_5_citations; PDF pages [7] |

Router: Profitability=minimum_specialist_cover (items=[], formulas=['gross_margin'], requirements=['op_4']); Liquidity & Leverage=no_requested_capability (items=[], formulas=[], requirements=[]); Cash Flow & Earnings Quality=no_requested_capability (items=[], formulas=[], requirements=[]).

Profitability projection: assigned ['op_4']; dependency closure 9; 13 citations. Status generated; thiếu []; model annotations [].

Independent checks: BBS_2025, scale1, source page đúng; formula/operands/period/unit kiểm riêng:

| Agent/evidence | Target | Value | Period | Operands/formula | PDF page |
| --- | --- | --- | --- | --- | --- |
| Profitability/E001 | gross_margin | 7.21 percent | 2025 | b02.gross_profit=32482519668; b02.net_revenue=450474531227; gross_profit / revenue ×100 | [7] |

Aggregation giữ origins, citations và caveats:

| Claim | Kind | Actual content | Origin | PDF pages | Disposition |
| --- | --- | --- | --- | --- | --- |
| C01 | approved_metric | Biên lợi nhuận gộp kỳ 2025 đạt 7,21%. | Profitability | [7] | candidate; caveats preserved |

Caveats: association_is_not_verified_semantic_support, calculation_eligible_does_not_mean_computed, candidate_claims_pending_M6_verification, computed_does_not_mean_financial_fact_verified, computed_result_is_separate_execution_artifact, formula_policy_not_approved, found_is_record_presence_not_financial_verification, gross_profit:missing_reporting_scope, gross_profit:source_reference_uncertain, gross_profit:unresolved_operand_context, gross_profit:unresolved_semantic_context, insufficient, missing_canonical_mapping, missing_reporting_scope, page_level_only, reporting_scope_source_insufficient, reporting_scope_unresolved, revenue:missing_reporting_scope, revenue:source_reference_uncertain, revenue:unresolved_operand_context, revenue:unresolved_semantic_context, source_reference_uncertain, unresolved_operand_context, unresolved_semantic_context, usable. Conflicts: 0; errors: []. Total 28.707s; provider calls 2; known tokens 6247; unknown-token calls 0.
### Q06 — completed

> Biên lợi nhuận gộp và tỷ lệ nợ trên tổng tài sản nói lên điều gì về khả năng sinh lời và mức độ sử dụng nợ của BBS năm 2025?

Execution mode: **ACTUAL_EXECUTION**.

Planner: raw intent `multi_step_analysis` → effective `multi_step_analysis`, status `planned`. Requirements: `b01.total_assets, b01.total_liabilities, b02.gross_profit, b02.net_revenue`; formulas `gross_margin, debt_to_assets`.

Operations: find_financial_facts, get_evidence_sources, find_financial_facts, get_evidence_sources, calculate_financial_metric, get_metric_evidence_lineage, find_financial_facts, get_evidence_sources, find_financial_facts, get_evidence_sources, calculate_financial_metric, get_metric_evidence_lineage, prepare_bundle. Missing/blocked: `none`; stop `all_required_evidence_resolved`.

Raw targets: `['b02.gross_profit', 'b02.net_revenue', 'b01.total_liabilities', 'b01.total_assets']`; raw missing: `[]`; raw unsupported: `[]`. Policy: `[{'stage': 'semantic_policy', 'outcome': 'consistent', 'reasons': []}]`.

| Stage | Selected | Executed | Status | Duration |
| --- | --- | --- | --- | --- |
| Planner | yes | yes | planned | 7867.9 ms |
| Supervisor | yes | yes | completed | 26013.0 ms |
| Router | yes | yes | routed | 355.5 ms |
| Profitability | yes | yes | generated | 4341.6 ms |
| Liquidity & Leverage | yes | yes | generated | 2373.7 ms |
| Cash Flow & Earnings Quality | no | no | NOT_EXECUTED | — |
| Aggregation | yes | yes | completed | 95.8 ms |

Supervisor gọi M4; Specialists nhận typed evidence projection, không gọi thêm M4:

| Tool | Caller | Input chính | Result | Time | Evidence |
| --- | --- | --- | --- | --- | --- |
| find_financial_facts | Supervisor | b02.gross_profit / 2025 | completed/found | 2379.2 ms | op_0; PDF pages [7] |
| get_evidence_sources | Supervisor | fact | completed/found | 2155.2 ms | op_1; PDF pages [7] |
| find_financial_facts | Supervisor | b02.net_revenue / 2025 | completed/found | 225.4 ms | op_2; PDF pages [7] |
| get_evidence_sources | Supervisor | fact | completed/found | 226.1 ms | op_3; PDF pages [7] |
| calculate_financial_metric | Supervisor | gross_margin | completed/computed | 2425.1 ms | op_4; PDF pages [7] |
| get_metric_evidence_lineage | Supervisor | metric lineage | completed/found | 2583.3 ms | op_5, op_5_citations; PDF pages [7] |
| find_financial_facts | Supervisor | b01.total_liabilities / 2025-12-31 | completed/found | 229.8 ms | op_6; PDF pages [6] |
| get_evidence_sources | Supervisor | fact | completed/found | 250.7 ms | op_7; PDF pages [6] |
| find_financial_facts | Supervisor | b01.total_assets / 2025-12-31 | completed/found | 249.1 ms | op_8; PDF pages [5] |
| get_evidence_sources | Supervisor | fact | completed/found | 260.5 ms | op_9; PDF pages [5] |
| calculate_financial_metric | Supervisor | debt_to_assets | completed/computed | 618.2 ms | op_10; PDF pages [5, 6] |
| get_metric_evidence_lineage | Supervisor | metric lineage | completed/found | 804.9 ms | op_11, op_11_citations; PDF pages [5, 6] |

Router: Profitability=minimum_specialist_cover (items=['b02.gross_profit', 'b02.net_revenue'], formulas=['gross_margin'], requirements=['op_0', 'op_2', 'op_4']); Liquidity & Leverage=minimum_specialist_cover (items=['b01.total_assets', 'b01.total_liabilities'], formulas=['debt_to_assets'], requirements=['op_10', 'op_6', 'op_8']); Cash Flow & Earnings Quality=no_requested_capability (items=[], formulas=[], requirements=[]).

Profitability projection: assigned ['op_0', 'op_2', 'op_4']; dependency closure 7; 13 citations. Status generated; thiếu []; model annotations [].

Liquidity & Leverage projection: assigned ['op_10', 'op_6', 'op_8']; dependency closure 7; 19 citations. Status generated; thiếu []; model annotations ['Biên lợi nhuận gộp'].

Independent checks: BBS_2025, scale1, source page đúng; formula/operands/period/unit kiểm riêng:

| Agent/evidence | Target | Value | Period | Operands/formula | PDF page |
| --- | --- | --- | --- | --- | --- |
| Profitability/E001 | b02.gross_profit | 32482519668 VND | 2025 | direct fact | [7] |
| Profitability/E002 | b02.net_revenue | 450474531227 VND | 2025 | direct fact | [7] |
| Profitability/E003 | gross_margin | 7.21 percent | 2025 | b02.gross_profit=32482519668; b02.net_revenue=450474531227; gross_profit / revenue ×100 | [7] |
| Liquidity & Leverage/E001 | b01.total_liabilities | 157146559558 VND | 2025-12-31 | direct fact | [6] |
| Liquidity & Leverage/E002 | b01.total_assets | 266086680765 VND | 2025-12-31 | direct fact | [5] |
| Liquidity & Leverage/E003 | debt_to_assets | 59.06 percent | 2025-12-31 | b01.total_liabilities=157146559558; b01.total_assets=266086680765; liabilities / assets ×100 | [5, 6] |

Aggregation giữ origins, citations và caveats:

| Claim | Kind | Actual content | Origin | PDF pages | Disposition |
| --- | --- | --- | --- | --- | --- |
| C01 | fact | Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. | Profitability | [7] | candidate; caveats preserved |
| C02 | fact | Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. | Profitability | [7] | candidate; caveats preserved |
| C03 | approved_metric | Biên lợi nhuận gộp kỳ 2025 đạt 7,21%. | Profitability | [7] | candidate; caveats preserved |
| C04 | supported_interpretation | Trong kỳ 2025, với mỗi 100 đồng doanh thu thuần tạo ra khoảng 7,21 đồng lợi nhuận gộp. | Profitability | [7] | candidate; caveats preserved |
| C05 | fact | Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. | Liquidity & Leverage | [6] | candidate; caveats preserved |
| C06 | fact | Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. | Liquidity & Leverage | [5] | candidate; caveats preserved |
| C07 | approved_metric | Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%. | Liquidity & Leverage | [5, 6] | candidate; caveats preserved |
| C08 | supported_interpretation | Nợ phải trả tương ứng khoảng 59,06 đồng trên mỗi 100 đồng tổng tài sản tại thời điểm báo cáo. | Liquidity & Leverage | [5, 6] | candidate; caveats preserved |

Caveats: Debt-to-Assets chỉ được diễn giải số học; chưa đủ căn cứ đánh giá khả năng thanh toán., Tổng nợ phải trả không đồng nghĩa với riêng nợ vay có lãi., assets:missing_reporting_scope, assets:source_reference_uncertain, assets:unresolved_operand_context, assets:unresolved_semantic_context, association_is_not_verified_semantic_support, calculation_eligible_does_not_mean_computed, candidate_claims_pending_M6_verification, computed_does_not_mean_financial_fact_verified, computed_result_is_separate_execution_artifact, formula_policy_not_approved, found_is_record_presence_not_financial_verification, gross_profit:missing_reporting_scope, gross_profit:source_reference_uncertain, gross_profit:unresolved_operand_context, gross_profit:unresolved_semantic_context, insufficient, liabilities:missing_reporting_scope, liabilities:source_reference_uncertain, liabilities:unresolved_operand_context, liabilities:unresolved_semantic_context, missing_canonical_mapping, missing_reporting_scope, page_level_only, reporting_scope_source_insufficient, reporting_scope_unresolved, revenue:missing_reporting_scope, revenue:source_reference_uncertain, revenue:unresolved_operand_context, revenue:unresolved_semantic_context, source_reference_uncertain, source_review_status:value_row_verified, specialist_annotation:liquidity_and_leverage:Biên lợi nhuận gộp, unresolved_operand_context, unresolved_semantic_context, usable. Conflicts: 0; errors: []. Total 41.048s; provider calls 3; known tokens 10184; unknown-token calls 0.
### N02 — completed

> Cho biết dòng tiền thuần từ hoạt động kinh doanh và doanh thu thuần của BBS năm 2025, kèm nguồn cho mỗi chỉ tiêu.

Execution mode: **ACTUAL_EXECUTION**.

Planner: raw intent `multi_step_analysis` → effective `multi_step_analysis`, status `planned`. Requirements: `b02.net_revenue, b03.operating_cash_flow`; formulas `none`.

Operations: find_financial_facts, get_evidence_sources, find_financial_facts, get_evidence_sources, prepare_bundle. Missing/blocked: `none`; stop `all_required_evidence_resolved`.

Raw targets: `['b03.operating_cash_flow', 'b02.net_revenue']`; raw missing: `[]`; raw unsupported: `[]`. Policy: `[{'stage': 'semantic_policy', 'outcome': 'consistent', 'reasons': []}]`.

| Stage | Selected | Executed | Status | Duration |
| --- | --- | --- | --- | --- |
| Planner | yes | yes | planned | 9118.1 ms |
| Supervisor | yes | yes | completed | 9813.8 ms |
| Router | yes | yes | routed | 31.5 ms |
| Profitability | yes | yes | generated | 1436.4 ms |
| Liquidity & Leverage | no | no | NOT_EXECUTED | — |
| Cash Flow & Earnings Quality | yes | yes | generated | 1209.7 ms |
| Aggregation | yes | yes | completed | 4.0 ms |

Supervisor gọi M4; Specialists nhận typed evidence projection, không gọi thêm M4:

| Tool | Caller | Input chính | Result | Time | Evidence |
| --- | --- | --- | --- | --- | --- |
| find_financial_facts | Supervisor | b03.operating_cash_flow / 2025 | completed/found | 2114.7 ms | op_0; PDF pages [8] |
| get_evidence_sources | Supervisor | fact | completed/found | 2052.6 ms | op_1; PDF pages [8] |
| find_financial_facts | Supervisor | b02.net_revenue / 2025 | completed/found | 91.3 ms | op_2; PDF pages [7] |
| get_evidence_sources | Supervisor | fact | completed/found | 110.0 ms | op_3; PDF pages [7] |

Router: Profitability=minimum_specialist_cover (items=['b02.net_revenue'], formulas=[], requirements=['op_2']); Liquidity & Leverage=no_requested_capability (items=[], formulas=[], requirements=[]); Cash Flow & Earnings Quality=minimum_specialist_cover_cash_profit_priority (items=['b03.operating_cash_flow'], formulas=[], requirements=['op_0']).

Profitability projection: assigned ['op_2']; dependency closure 2; 10 citations. Status generated; thiếu []; model annotations ['Dòng tiền thuần từ hoạt động kinh doanh năm 2025'].

Cash Flow & Earnings Quality projection: assigned ['op_0']; dependency closure 2; 11 citations. Status generated; thiếu []; model annotations ['Không có thông tin về doanh thu thuần của BBS năm 2025 trong bằng chứng hiện có.'].

Independent checks: BBS_2025, scale1, source page đúng; formula/operands/period/unit kiểm riêng:

| Agent/evidence | Target | Value | Period | Operands/formula | PDF page |
| --- | --- | --- | --- | --- | --- |
| Profitability/E001 | b02.net_revenue | 450474531227 VND | 2025 | direct fact | [7] |
| Cash Flow & Earnings Quality/E001 | b03.operating_cash_flow | 14319681754 VND | 2025 | direct fact | [8] |

Aggregation giữ origins, citations và caveats:

| Claim | Kind | Actual content | Origin | PDF pages | Disposition |
| --- | --- | --- | --- | --- | --- |
| C01 | fact | Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. | Profitability | [7] | candidate; caveats preserved |
| C02 | fact | Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 14.319.681.754 VND. | Cash Flow & Earnings Quality | [8] | candidate; caveats preserved |
| C03 | supported_interpretation | Lưu chuyển tiền thuần từ hoạt động kinh doanh trong kỳ 2025 là 14.319.681.754 VND, mang giá trị dương, phản ánh dòng tiền vào thuần từ hoạt động kinh doanh theo chỉ tiêu được báo cáo. | Cash Flow & Earnings Quality | [8] | candidate; caveats preserved |

Caveats: B02 và B03 có nguồn riêng; cùng filing không tự xác nhận reporting scope còn unresolved., Chưa đối chiếu đầy đủ điều chỉnh/tỷ giá để xác nhận cash bridge hoặc nguyên nhân chênh lệch., Chỉ mô tả facts và dấu dòng tiền; chưa đủ căn cứ kết luận chất lượng lợi nhuận cao/thấp., Không có approved earnings-quality ratio; không tự tính tỷ lệ hoặc chênh lệch CFO và lợi nhuận., association_is_not_verified_semantic_support, candidate_claims_pending_M6_verification, found_is_record_presence_not_financial_verification, insufficient, missing_canonical_mapping, missing_reporting_scope, page_level_only, reporting_scope_source_insufficient, reporting_scope_unresolved, source_reference_uncertain, source_review_status:unverified, source_review_status:value_row_verified, specialist_annotation:cash_flow_and_earnings_quality:Không có thông tin về doanh thu thuần của BBS năm 2025 trong bằng chứng hiện có., specialist_annotation:profitability:Dòng tiền thuần từ hoạt động kinh doanh năm 2025, unresolved_operand_context, unresolved_semantic_context, usable. Conflicts: 0; errors: []. Total 21.614s; provider calls 3; known tokens 7962; unknown-token calls 0.
### N03 — completed

> Hãy cho biết biên lợi nhuận gộp, tỷ lệ nợ trên tổng tài sản và dòng tiền thuần từ hoạt động kinh doanh của BBS năm 2025.

Execution mode: **ACTUAL_EXECUTION**.

Planner: raw intent `multi_step_analysis` → effective `multi_step_analysis`, status `planned`. Requirements: `b01.total_assets, b01.total_liabilities, b02.gross_profit, b02.net_revenue, b03.operating_cash_flow`; formulas `gross_margin, debt_to_assets`.

Operations: find_financial_facts, find_financial_facts, find_financial_facts, find_financial_facts, find_financial_facts, get_evidence_sources, get_evidence_sources, get_evidence_sources, get_evidence_sources, get_evidence_sources, calculate_financial_metric, get_metric_evidence_lineage, calculate_financial_metric, get_metric_evidence_lineage, prepare_bundle. Missing/blocked: `none`; stop `all_required_evidence_resolved`.

Raw targets: `['b02.gross_profit', 'b02.net_revenue', 'b01.total_liabilities', 'b01.total_assets', 'b03.operating_cash_flow']`; raw missing: `[]`; raw unsupported: `[]`. Policy: `[{'stage': 'semantic_policy', 'outcome': 'consistent', 'reasons': []}]`.

| Stage | Selected | Executed | Status | Duration |
| --- | --- | --- | --- | --- |
| Planner | yes | yes | planned | 9260.5 ms |
| Supervisor | yes | yes | completed | 30262.5 ms |
| Router | yes | yes | routed | 359.9 ms |
| Profitability | yes | yes | generated | 2221.8 ms |
| Liquidity & Leverage | yes | yes | generated | 4467.5 ms |
| Cash Flow & Earnings Quality | yes | yes | generated | 2143.9 ms |
| Aggregation | yes | yes | completed | 74.1 ms |

Supervisor gọi M4; Specialists nhận typed evidence projection, không gọi thêm M4:

| Tool | Caller | Input chính | Result | Time | Evidence |
| --- | --- | --- | --- | --- | --- |
| find_financial_facts | Supervisor | b02.gross_profit / 2025 | completed/found | 2369.2 ms | op_0; PDF pages [7] |
| find_financial_facts | Supervisor | b02.net_revenue / 2025 | completed/found | 281.3 ms | op_1; PDF pages [7] |
| find_financial_facts | Supervisor | b01.total_liabilities / 2025-12-31 | completed/found | 284.2 ms | op_2; PDF pages [6] |
| find_financial_facts | Supervisor | b01.total_assets / 2025-12-31 | completed/found | 305.4 ms | op_3; PDF pages [5] |
| find_financial_facts | Supervisor | b03.operating_cash_flow / 2025 | completed/found | 305.4 ms | op_4; PDF pages [8] |
| get_evidence_sources | Supervisor | fact | completed/found | 4085.8 ms | op_5; PDF pages [7] |
| get_evidence_sources | Supervisor | fact | completed/found | 270.8 ms | op_6; PDF pages [7] |
| get_evidence_sources | Supervisor | fact | completed/found | 268.3 ms | op_7; PDF pages [6] |
| get_evidence_sources | Supervisor | fact | completed/found | 278.4 ms | op_8; PDF pages [5] |
| get_evidence_sources | Supervisor | fact | completed/found | 298.9 ms | op_9; PDF pages [8] |
| calculate_financial_metric | Supervisor | gross_margin | completed/computed | 2517.4 ms | op_10; PDF pages [7] |
| get_metric_evidence_lineage | Supervisor | metric lineage | completed/found | 2601.4 ms | op_11, op_11_citations; PDF pages [7] |
| calculate_financial_metric | Supervisor | debt_to_assets | completed/computed | 633.8 ms | op_12; PDF pages [5, 6] |
| get_metric_evidence_lineage | Supervisor | metric lineage | completed/found | 812.6 ms | op_13, op_13_citations; PDF pages [5, 6] |

Router: Profitability=minimum_specialist_cover (items=['b02.gross_profit', 'b02.net_revenue'], formulas=['gross_margin'], requirements=['op_0', 'op_1', 'op_10']); Liquidity & Leverage=minimum_specialist_cover (items=['b01.total_assets', 'b01.total_liabilities'], formulas=['debt_to_assets'], requirements=['op_12', 'op_2', 'op_3']); Cash Flow & Earnings Quality=minimum_specialist_cover_cash_profit_priority (items=['b03.operating_cash_flow'], formulas=[], requirements=['op_4']).

Profitability projection: assigned ['op_0', 'op_1', 'op_10']; dependency closure 7; 13 citations. Status generated; thiếu []; model annotations [].

Liquidity & Leverage projection: assigned ['op_12', 'op_2', 'op_3']; dependency closure 7; 19 citations. Status generated; thiếu []; model annotations [].

Cash Flow & Earnings Quality projection: assigned ['op_4']; dependency closure 2; 11 citations. Status generated; thiếu []; model annotations ['Biên lợi nhuận gộp năm 2025', 'Tỷ lệ nợ trên tổng tài sản năm 2025'].

Independent checks: BBS_2025, scale1, source page đúng; formula/operands/period/unit kiểm riêng:

| Agent/evidence | Target | Value | Period | Operands/formula | PDF page |
| --- | --- | --- | --- | --- | --- |
| Profitability/E001 | b02.gross_profit | 32482519668 VND | 2025 | direct fact | [7] |
| Profitability/E002 | b02.net_revenue | 450474531227 VND | 2025 | direct fact | [7] |
| Profitability/E003 | gross_margin | 7.21 percent | 2025 | b02.gross_profit=32482519668; b02.net_revenue=450474531227; gross_profit / revenue ×100 | [7] |
| Liquidity & Leverage/E001 | b01.total_liabilities | 157146559558 VND | 2025-12-31 | direct fact | [6] |
| Liquidity & Leverage/E002 | b01.total_assets | 266086680765 VND | 2025-12-31 | direct fact | [5] |
| Liquidity & Leverage/E003 | debt_to_assets | 59.06 percent | 2025-12-31 | b01.total_liabilities=157146559558; b01.total_assets=266086680765; liabilities / assets ×100 | [5, 6] |
| Cash Flow & Earnings Quality/E001 | b03.operating_cash_flow | 14319681754 VND | 2025 | direct fact | [8] |

Aggregation giữ origins, citations và caveats:

| Claim | Kind | Actual content | Origin | PDF pages | Disposition |
| --- | --- | --- | --- | --- | --- |
| C01 | fact | Lợi nhuận gộp kỳ 2025 là 32.482.519.668 VND. | Profitability | [7] | candidate; caveats preserved |
| C02 | fact | Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. | Profitability | [7] | candidate; caveats preserved |
| C03 | approved_metric | Biên lợi nhuận gộp kỳ 2025 đạt 7,21%. | Profitability | [7] | candidate; caveats preserved |
| C04 | fact | Tổng nợ phải trả tại ngày 2025-12-31 là 157.146.559.558 VND. | Liquidity & Leverage | [6] | candidate; caveats preserved |
| C05 | fact | Tổng tài sản tại ngày 2025-12-31 là 266.086.680.765 VND. | Liquidity & Leverage | [5] | candidate; caveats preserved |
| C06 | approved_metric | Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%. | Liquidity & Leverage | [5, 6] | candidate; caveats preserved |
| C07 | supported_interpretation | Nợ phải trả tương ứng khoảng 59,06 đồng trên mỗi 100 đồng tổng tài sản tại thời điểm báo cáo. | Liquidity & Leverage | [5, 6] | candidate; caveats preserved |
| C08 | fact | Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 14.319.681.754 VND. | Cash Flow & Earnings Quality | [8] | candidate; caveats preserved |
| C09 | supported_interpretation | Lưu chuyển tiền thuần từ hoạt động kinh doanh trong kỳ 2025 là 14.319.681.754 VND, mang giá trị dương, phản ánh dòng tiền vào thuần từ hoạt động kinh doanh theo chỉ tiêu được báo cáo. | Cash Flow & Earnings Quality | [8] | candidate; caveats preserved |

Caveats: B02 và B03 có nguồn riêng; cùng filing không tự xác nhận reporting scope còn unresolved., Chưa đối chiếu đầy đủ điều chỉnh/tỷ giá để xác nhận cash bridge hoặc nguyên nhân chênh lệch., Chỉ mô tả facts và dấu dòng tiền; chưa đủ căn cứ kết luận chất lượng lợi nhuận cao/thấp., Debt-to-Assets chỉ được diễn giải số học; chưa đủ căn cứ đánh giá khả năng thanh toán., Không có approved earnings-quality ratio; không tự tính tỷ lệ hoặc chênh lệch CFO và lợi nhuận., Tổng nợ phải trả không đồng nghĩa với riêng nợ vay có lãi., assets:missing_reporting_scope, assets:source_reference_uncertain, assets:unresolved_operand_context, assets:unresolved_semantic_context, association_is_not_verified_semantic_support, calculation_eligible_does_not_mean_computed, candidate_claims_pending_M6_verification, computed_does_not_mean_financial_fact_verified, computed_result_is_separate_execution_artifact, formula_policy_not_approved, found_is_record_presence_not_financial_verification, gross_profit:missing_reporting_scope, gross_profit:source_reference_uncertain, gross_profit:unresolved_operand_context, gross_profit:unresolved_semantic_context, insufficient, liabilities:missing_reporting_scope, liabilities:source_reference_uncertain, liabilities:unresolved_operand_context, liabilities:unresolved_semantic_context, missing_canonical_mapping, missing_reporting_scope, page_level_only, reporting_scope_source_insufficient, reporting_scope_unresolved, revenue:missing_reporting_scope, revenue:source_reference_uncertain, revenue:unresolved_operand_context, revenue:unresolved_semantic_context, source_reference_uncertain, source_review_status:unverified, source_review_status:value_row_verified, specialist_annotation:cash_flow_and_earnings_quality:Biên lợi nhuận gộp năm 2025, specialist_annotation:cash_flow_and_earnings_quality:Tỷ lệ nợ trên tổng tài sản năm 2025, unresolved_operand_context, unresolved_semantic_context, usable. Conflicts: 0; errors: []. Total 48.790s; provider calls 4; known tokens 12589; unknown-token calls 0.
### Q07 — clarification_required

> Phân tích khả năng sinh lời, tình hình nợ và dòng tiền kinh doanh của BBS năm 2025.

Execution mode: **ACTUAL_EXECUTION**.

Planner: raw intent `multi_step_analysis` → effective `ambiguous`, status `clarification_required`. Requirements: `none`; formulas `none`.

Operations: . Missing/blocked: `explicit_target_for:cash_flow_and_earnings_quality;explicit_target_for:liquidity_and_leverage;explicit_target_for:profitability, explicit_target_for:cash_flow_and_earnings_quality;explicit_target_for:liquidity_and_leverage;explicit_target_for:profitability`; stop `proposal_requires_clarification`.

Raw targets: `['b02.net_revenue', 'b02.gross_profit', 'b02.profit_after_tax', 'b01.total_liabilities', 'b01.total_assets', 'b03.operating_cash_flow']`; raw missing: `[]`; raw unsupported: `[]`. Policy: `[{'stage': 'semantic_policy', 'outcome': 'ambiguous', 'reasons': ['supported_domain_requires_explicit_targets']}]`.

| Stage | Selected | Executed | Status | Duration |
| --- | --- | --- | --- | --- |
| Planner | yes | yes | clarification_required | 3350.6 ms |
| Supervisor | no | no | NOT_EXECUTED | 0.0 ms |
| Router | no | no | NOT_EXECUTED | 0.0 ms |
| Profitability | no | no | NOT_EXECUTED | — |
| Liquidity & Leverage | no | no | NOT_EXECUTED | — |
| Cash Flow & Earnings Quality | no | no | NOT_EXECUTED | — |
| Aggregation | no | no | NOT_EXECUTED | 0.0 ms |

Caveats: candidate_claims_pending_M6_verification. Conflicts: 0; errors: []. Total 3.351s; provider calls 1; known tokens 5137; unknown-token calls 0.
### Q08 — clarification_required

> Doanh thu thuần và dòng tiền kinh doanh của BBS năm 2025 có cho thấy chất lượng lợi nhuận tốt không? Giải thích dựa trên số liệu.

Execution mode: **ACTUAL_EXECUTION**.

Planner: raw intent `unsupported` → effective `ambiguous`, status `clarification_required`. Requirements: `b02.net_revenue`; formulas `none`.

Operations: . Missing/blocked: `explicit_target_for:cash_flow_and_earnings_quality, explicit_target_for:cash_flow_and_earnings_quality`; stop `proposal_requires_clarification`.

Raw targets: `[]`; raw missing: `[]`; raw unsupported: `['earnings_quality_evidence']`. Policy: `[{'stage': 'semantic_policy', 'outcome': 'ambiguous', 'reasons': ['registered_capability_misclassified:earnings_quality_evidence', 'supported_domain_requires_explicit_targets']}]`.

| Stage | Selected | Executed | Status | Duration |
| --- | --- | --- | --- | --- |
| Planner | yes | yes | clarification_required | 1290.3 ms |
| Supervisor | no | no | NOT_EXECUTED | 0.0 ms |
| Router | no | no | NOT_EXECUTED | 0.0 ms |
| Profitability | no | no | NOT_EXECUTED | — |
| Liquidity & Leverage | no | no | NOT_EXECUTED | — |
| Cash Flow & Earnings Quality | no | no | NOT_EXECUTED | — |
| Aggregation | no | no | NOT_EXECUTED | 0.0 ms |

Caveats: candidate_claims_pending_M6_verification. Conflicts: 0; errors: []. Total 1.290s; provider calls 1; known tokens 4129; unknown-token calls 0.
### Q08-correction — clarification_required

> Doanh thu thuần và dòng tiền kinh doanh của BBS năm 2025 có cho thấy chất lượng lợi nhuận tốt không? Giải thích dựa trên số liệu.

Execution mode: **ACTUAL_EXECUTION**.

Planner: raw intent `ambiguous` → effective `ambiguous`, status `clarification_required`. Requirements: `b02.net_revenue, b03.operating_cash_flow`; formulas `none`.

Operations: . Missing/blocked: `proposal_omits_explicit_target, proposal_omits_explicit_target`; stop `proposal_requires_clarification`.

Raw targets: `['b02.net_revenue', 'b03.operating_cash_flow']`; raw missing: `['Cần làm rõ tiêu chí cụ thể để đánh giá chất lượng lợi nhuận dựa trên doanh thu thuần và dòng tiền kinh doanh (ví dụ: tỷ lệ dòng tiền kinh doanh trên doanh thu hoặc trên lợi nhuận sau thuế).']`; raw unsupported: `[]`. Policy: `[{'stage': 'semantic_policy', 'outcome': 'ambiguous', 'reasons': ['explicit_targets_not_covered_by_proposal']}]`.

| Stage | Selected | Executed | Status | Duration |
| --- | --- | --- | --- | --- |
| Planner | yes | yes | clarification_required | 2508.2 ms |
| Supervisor | no | no | NOT_EXECUTED | 0.0 ms |
| Router | no | no | NOT_EXECUTED | 0.0 ms |
| Profitability | no | no | NOT_EXECUTED | — |
| Liquidity & Leverage | no | no | NOT_EXECUTED | — |
| Cash Flow & Earnings Quality | no | no | NOT_EXECUTED | — |
| Aggregation | no | no | NOT_EXECUTED | 0.0 ms |

Caveats: candidate_claims_pending_M6_verification. Conflicts: 0; errors: []. Total 2.508s; provider calls 1; known tokens 4350; unknown-token calls 0.

## F. Regression & Financial Checks

OFFLINE_TEST trước sửa: **19failed/3passed** (tests-before.txt), gồm capability,
partial/false substitution và API recovery chưa có. Các provider tests lúc này
fail cả do thiếu context/attempt metadata; không gọi đây là live503 recovery.
Sau sửa24new controls PASS (tests-policy-final.txt);305focused/consumer PASS
(tests-final.txt). Alias correction:2failing rồi66focused PASS; clarification
reason correction:1failing rồi final27new controls/focused group ở tests-final-m5.txt.
Final M5/Gateway/adapter: **133PASS**. Các Specialist/M6/M7 controls trong nhóm305
không bị alias/reason correction thay đổi; không chạy lại nhóm đã PASS.
Không sửa expected assertions của existing tests.
M5-02/03/07/08,3Specialists,Gateway/adapter và M6candidate/M7composer/firewall boundaries.
HTTP503→success/503, attempts1,429,401,403,invalidJSON,timeout,total deadline,
provenance,known11tokens+1unknown attempt và no fake downstream được kiểm.

EVIDENCE_LINEAGE audit độc lập dùng QA-Q01 visual PDF references, không lấy
Planner output làm gold. Gross margin32.482.519.668/450.474.531.227×100=
**7.21%**; liabilities157.146.559.558/assets266.086.680.765×100=
**59.06%**. Revenue **450.474.531.227 VND**, CFO
**14.319.681.754 VND**. BBS2025 PDF pages5/6/7/8; B01 instant31/12/2025,
B02/B03 fiscal2025, scale1. Audit kiểm values/operands/period/unit/formula approval,
document/snapshot/page và candidate provenance/caveats; không tự nâng candidates
thành verified. Interpretations phải đọc như mô tả tỷ lệ/dấu CFO, không kết luận
solvency hoặc chất lượng lợi nhuận tốt chỉ từ revenue+CFO.

## G. Remaining Limitations

Không còn provider failure trong fresh runs nếu503/429 bằng0; điều đó không xác
định nguyên nhân provider503 trước đây và không bảo đảm availability tương lai.
Specialists giữ one-attempt; retry opt-in hiện chỉ Planner. Broad-domain clarify
là policy outcome đúng. Unsupported metrics/missing evidence/accounting restrictions
vẫn giữ. Page-level/source_reference_uncertain, reporting_scope unresolved,
usable_with_caveat và các caveats inherited (kể cả formula_policy_not_approved
từ lineage cũ) không bị xóa; approval hiện hành kiểm riêng qua M4 gate.
Không benchmark accuracy toàn PDF/M8; không chứng minh M5→M6→M7 release tự động.
Chi phí tiền unknown; không quy đổi tokens thành tiền/quota còn lại.
Không phát hiện P0/P1 implementation còn lại trong F02/client recovery;
nguyên nhân sâu provider503 vẫn unresolved. Clarification text Gemini Q08 có
gợi ý ratios chưa approved; giữ raw để review, không coi đó là execution authority.

Ruff lint toàn repository PASS; format changed files/planning/diff checks được
ghi ở delivery checkpoint. Một full local format check gặp baseline CRLF trong
docs/m7-05-information-firewall.md: nội dung normalized đúng Git HEAD, Git blob LF;
không sửa file ngoài scope. CI chạy checkout LF và phải được xác nhận đúng SHA.

Selected-input integrity: chỉ hash Web local và14QA-Q01M5JSON (15files); kiểm logical
equality hydrated facts/metrics/source reviews trước/sau. Không hash toàn bộ
16.000+files và không tuyên bố đã kiểm hash tất cả protected dataset.
Artifacts ignored `artifacts/evidence/QA-Fix-02/`: actual-result, per-call
request/response, durable provider-ledgers, saved Q07 replay, integrity,
tests-before/final và independent-audit.json. Raw dataset không commit.
Delivery checkpoint local ghi implementation SHA, CI và current validation;
SHA/CI cuối được bàn giao trực tiếp cho Tech Lead, không tạo checkpoint commit.
[Fresh runner](../scripts/run_qa_fix_02.py), [independent audit](../scripts/audit_qa_fix_02.py).

## H. Next Action

Tech Lead review QA-Fix-02 và quyết định nghiệm thu trước khi giao QA-Fix-03.
**Dừng REVIEW; không tự triển khai task tiếp theo.**
