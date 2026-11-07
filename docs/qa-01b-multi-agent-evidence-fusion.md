# QA-01b — Multi-Agent Financial & Document Evidence Fusion

Ngày 07/11/2026 (Asia/Bangkok). Baseline `0e985d2`. Đang triển khai/chưa commit.

## 1. Executive Summary

Mixed QA dùng lại hai lanes đã nghiệm thu, cùng một approved filing. Financial
và document claims được M6 kiểm chứng riêng, lưu đúng typed identities, rồi M7
phát hành độc lập với citations riêng. Không tạo causal claim từ đồng xuất hiện.
Kết quả Quick QA/regression/live đang được hoàn thiện; chưa nghiệm thu DONE.

## 2. Existing Architecture & Integration Changes

Giữ FinancialQAPipeline, FinancialMultiAgentOrchestrator, Planner/Supervisor,
Adaptive Router và ba specialists. `fusion_pipeline` điều phối request-scoped
lanes; không có framework, agent hay datastore mới. Context được kiểm tra trên
original request trước bất kỳ subrequest nào. Financial-only/document-only giữ
luồng mặc định; deterministic numeric execution là tùy chọn rõ ràng.

## 3. Unified Requirements

`FusionRequirement` lưu ID, original span, catalog target, lane/kind, dependencies,
evidence/verification needs, support status, missing information/reason. Mọi ý
không hỗ trợ vẫn vào inventory. Một số paraphrase của ba approved operations
được chuẩn hóa thành yêu cầu catalog; không có công thức kế toán mới. Ambiguity
không được biến thành claim. Tối đa 12 requirements/thực thi.

## 4. M5 Adaptive Routing & Agent Collaboration

Orchestrator lập fusion plan; mỗi financial lane tiếp tục Planner → Supervisor →
Router → specialists được chọn. Document lane chỉ chạy khi có document requirement.
Existing Gemini Planner/specialists hoạt động khi request chọn Gemini và cho phép
Gateway. Chế độ deterministic chỉ chọn fact/metric và dùng renderer số hiện có;
không sinh financial interpretation hoặc giả lập một provider response.

## 5. Financial / BM25 / EF-EG Tool Execution

M4 vẫn sở hữu retrieval/calculator/source/lineage. BM25 tìm source-bound text/table.
Source excerpts phải có topic tokens, nội dung thực chất và kết thúc đoạn; có thể
nối tối đa ba selectors liên tiếp cùng source/page/request. Đây là trích đoạn,
không khẳng định tóm tắt đầy đủ. Graph được dùng cho context của metric/source;
typed depth/limit giữ structural/contextual basis và caveats.

## 6. Evidence Fusion Contracts

`EvidenceFusionBundle` giữ bound request, requirements, full lane results/financial
execution, document candidates/retrieval, graph paths, original citations, quality,
missing evidence và policy `independent_verified_components_only`. Không đổi
snapshot IDs. Financial descriptor phải đúng approved composition; các nguồn
document giữ original namespaces. GEN-01 phải load `normalized-release/audit-release`
đúng báo cáo nghiệm thu, không lấy các vòng chẩn đoán `*-final` làm ground truth.

## 7. M6 Cross-Evidence Verification

DeterministicFinancialValidator, EvidenceCritic, FinancialLogicCritic, Judge và
bounded revision giữ nguyên. Document policy replay exact quotations/citations,
continuity, relationship và source quality. Chỉ phát hành independent components;
causal/explanatory relation không có accepted policy/proof luôn unmet. Graph không
đi vào admission proof. BBS trang 13 có review defect vẫn INVESTIGATE.

## 8. Ledger Admission & Reuse

Giữ financial/document ledger entries và proof versions. Mixed M7 truy vấn hai
typed lanes riêng với financial snapshot và document composition fingerprint;
không truy vấn một snapshot chung. Request-scoped aggregation không lưu claim
tổng hợp giả. Document cache tiếp tục kiểm tra pins trước reuse.

## 9. M7 Grounded Output & Firewall

Composer và Firewall tự phân rã lại original request; không nhận inventory từ M5
làm authority. Coverage kiểm từng requirement; thiếu bất kỳ ý nào phải partial.
Renderer giữ từng segment/source context; chỉ cho phép nhiều source namespaces
trong mixed context, financial context vẫn duy nhất, company vẫn duy nhất.
Firewall kiểm accepted Ledger/protected slots/citations/original requirements.

## 10. Real PDF Quick QA

20 cases c? oracle ??ng b?ng tr??c execution, tr?n BBS2025/BCC2025/BCC2024.
Expected l?y t? PDF renders, accepted M4 saves, pinned source records v? source-quality
policies; kh?ng l?y output pipeline l?m ground truth. ?? xem tr?c ti?p BBS trang12/13,
BCC2025 trang13 v? BCC2024 trang18. ??y l? Quick QA, kh?ng ph?i M8/full-PDF audit.

| Ch? s? | K?t qu? offline sau s?a |
| --- | ---: |
| Cases / ??t oracle | 20 / 20 |
| Fully answered (c? caveats) | 8 |
| Partially answered | 5 |
| Correctly refused/clarified | 7 (1 unsupported, 6 clarification) |
| Incorrect/unsupported release | 0 |
| Financial requirements | 12/14 |
| Document requirements | 12/14 |
| Citations ???c audit ??ng | 216/216 |
| Source/snapshot leakage | 0 |
| Unsupported causal claims ph?t h?nh | 0 |
| Causal requirement gi? unmet | 1 |
| Graph context s? d?ng | 9/20 cases |
| M6 ACCEPT / INVESTIGATE / ABSTAIN | 35 / 3 / 0 |
| Ledger stored / idempotent / rejected | 17 / 18 / 3 |

Coverage ch? ??m 13 cases ?? bind context; 7 intentional binding/comparison controls
kh?ng c? y?u c?u n?o ???c th?c thi. Unsupported ROE v? accounting-basis restriction
v?n t?nh v?o denominator t?i ch?nh; hai ngu?n quality-blocked t?nh v?o denominator document.

Artifacts cu?i: `artifacts/evidence/QA-01b/after-topic-fix/` g?m oracles, actual answers,
full traces, summary, independent-audit v? integrity. Run tr??c s?a topic n?m ?
`review-run/`: 17/20 oracle, B1/B2/B3 c? th?m ?o?n sai relevance. Kh?ng x?a run l?i.

### N?m actual E2E examples

B?ng d??i tr?ch ng?n content ???c ph?t h?nh; c?u tr? l?i/citations ??y ?? ? t?ng case JSON.

#### A1

| Th?nh ph?n | Actual |
| --- | --- |
| Question | Biên lợi nhuận gộp BBS 2025 là bao nhiêu và báo cáo có thuyết minh gì về chính sách ghi nhận doanh thu? |
| Requirements | metric: gross_margin; document_evidence: chinh sach ghi nhan doanh thu |
| Agents (executed) | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'find_financial_facts': 2, 'calculate_financial_metric': 1, 'get_metric_evidence_lineage': 1, 'search_document_evidence': 1, 'get_evidence_sources': 9, 'get_graph_context': 1}; financial/doc results xem source v? M6 b?n d??i |
| Financial source | PDF trang [7]; snapshot `D-01/normalized-v2`; selector `/context/0` |
| Document source | PDF trang [12]; snapshot `artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json`; selector `/text_elements/18` |
| Graph | found; 2 edges (structural/contextual, kh?ng claim support) |
| M6 | {'ACCEPT': 4} |
| Ledger | {'stored': 4} |
| M7 | completed_with_caveats; Firewall ALLOW_WITH_CAVEAT; tr?ch: Theo các nội dung đã được xác minh trong ledger: Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 đạt 7,21%. [1][2][3][4][5][6][7][8][9][10][11][12][13] Tài liệu ghi «Doanh thu được xác định tương đối chắc chắn. Khi hợp đồng quy định người mua được quyền trả lại sản phẩm, hàng hóa đã mua theo những điều kiện cụ thể, Công ty chỉ được ghi nhận doanh thu khi những điều kiện cụ thể đó không còn tồn tại và người mua không được quyền ? |
| Assessment | full; oracle/audit PASS |

#### A2

| Th?nh ph?n | Actual |
| --- | --- |
| Question | Nợ phải trả chiếm bao nhiêu phần trăm tổng tài sản BBS 2025? Báo cáo có thuyết minh về các khoản vay không? |
| Requirements | metric: debt_to_assets; document_evidence: vay |
| Agents (executed) | liquidity_and_leverage, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'find_financial_facts': 2, 'calculate_financial_metric': 1, 'get_metric_evidence_lineage': 1, 'search_document_evidence': 1, 'get_evidence_sources': 9, 'get_graph_context': 1}; financial/doc results xem source v? M6 b?n d??i |
| Financial source | PDF trang [5, 6]; snapshot `D-01/normalized-v2`; selector `/context/0` |
| Document source | PDF trang [12]; snapshot `artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json`; selector `/text_elements/8` |
| Graph | found; 2 edges (structural/contextual, kh?ng claim support) |
| M6 | {'ACCEPT': 4} |
| Ledger | {'stored': 4} |
| M7 | completed_with_caveats; Firewall ALLOW_WITH_CAVEAT; tr?ch: Theo các nội dung đã được xác minh trong ledger: Kỳ 2025-12-31 — Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%. [1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19] Tài liệu ghi «Chi phí đi vay bao gồm lãi tiền vay và các chi phí khác liên quan trực tiếp đến các khoản vay. Chi phí đi vay được ghi nhận vào chi phí sản xuất, kinh doanh trong năm khi phát sinh, ngoại trừ chi phí đi vay? |
| Assessment | full; oracle/audit PASS |

#### A5

| Th?nh ph?n | Actual |
| --- | --- |
| Question | Doanh thu BBS 2025 tăng hay giảm so với năm trước và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu và nguyên nhân là gì? |
| Requirements | metric: revenue_yoy; document_evidence: chinh sach ghi nhan doanh thu; causal_explanation: unsupported_causal_inference |
| Agents (executed) | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'find_financial_facts': 2, 'calculate_financial_metric': 1, 'get_metric_evidence_lineage': 1, 'search_document_evidence': 1, 'get_evidence_sources': 9, 'get_graph_context': 1}; financial/doc results xem source v? M6 b?n d??i |
| Financial source | PDF trang [7]; snapshot `D-01/normalized-v2`; selector `/context/0` |
| Document source | PDF trang [12]; snapshot `artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json`; selector `/text_elements/18` |
| Graph | found; 2 edges (structural/contextual, kh?ng claim support) |
| M6 | {'ACCEPT': 4} |
| Ledger | {'idempotent': 4} |
| M7 | partial_verified_coverage; Firewall ALLOW_WITH_CAVEAT; tr?ch: Theo các nội dung đã được xác minh trong ledger: Kỳ 2025 — Tăng trưởng doanh thu kỳ 2025 đạt 26,71%. [1][2][3][4][5][6][7][8][9][10][11][12] Tài liệu ghi «Doanh thu được xác định tương đối chắc chắn. Khi hợp đồng quy định người mua được quyền trả lại sản phẩm, hàng hóa đã mua theo những điều kiện cụ thể, Công ty chỉ được ghi nhận doanh thu khi những điều kiện cụ thể đó không còn tồn tại và người mua không được quyền ? |
| Assessment | partial; oracle/audit PASS |

#### B2

| Th?nh ph?n | Actual |
| --- | --- |
| Question | Biên lợi nhuận gộp BCC 2025 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu? |
| Requirements | metric: gross_margin; document_evidence: chinh sach ghi nhan doanh thu |
| Agents (executed) | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'find_financial_facts': 2, 'calculate_financial_metric': 1, 'get_metric_evidence_lineage': 1, 'search_document_evidence': 1, 'get_evidence_sources': 6, 'get_graph_context': 1}; financial/doc results xem source v? M6 b?n d??i |
| Financial source | PDF trang [7]; snapshot `a49f826f-8e45-49c1-9e40-95f44e467e46`; selector `/context/0` |
| Document source | PDF trang [13]; snapshot `artifacts/evidence/EXT-01/BCC_2025/responses/page-13.json`; selector `/text_elements/16` |
| Graph | found; 2 edges (structural/contextual, kh?ng claim support) |
| M6 | {'ACCEPT': 3} |
| Ledger | {'stored': 1, 'idempotent': 2} |
| M7 | completed_with_caveats; Firewall ALLOW_WITH_CAVEAT; tr?ch: Theo các nội dung đã được xác minh trong ledger: Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 đạt 10,01%. [1][2][3][4][5][6][7][8][9][10][11][12] Tài liệu ghi «- Doanh thu được xác định tương đối chắc chắn. Khi hợp đồng quy định người mua được quyền trả lại sản phẩm, hàng hóa đã mua theo những điều kiện cụ thể, Công ty chỉ được ghi nhận doanh thu khi những điều kiện cụ thể đó không còn tồn tại và người mua không được quyền t? |
| Assessment | full; oracle/audit PASS |

#### C1

| Th?nh ph?n | Actual |
| --- | --- |
| Question | Biên lợi nhuận gộp BCC 2024 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu? |
| Requirements | metric: gross_margin; document_evidence: chinh sach ghi nhan doanh thu |
| Agents (executed) | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'search_document_evidence': 1, 'get_evidence_sources': 3, 'get_graph_context': 1}; financial/doc results xem source v? M6 b?n d??i |
| Financial source | Kh?ng ph?t h?nh |
| Document source | PDF trang [18]; snapshot `artifacts/evidence/EXT-01/BCC_2024/responses/page-18.json`; selector `/text_elements/5` |
| Graph | found; 2 edges (structural/contextual, kh?ng claim support) |
| M6 | {'ACCEPT': 1} |
| Ledger | {'stored': 1} |
| M7 | partial_verified_coverage; Firewall ALLOW_WITH_CAVEAT; tr?ch: Theo các nội dung đã được xác minh trong ledger: Tài liệu ghi «Ghi nhận doanh thu Doanh thu bán hàng được ghi nhận khi đồng thời thỏa mãn tất cả năm (5) điều kiện sau: (a) Công ty đã chuyển giao phần lớn rủi ro và lợi ích gắn liền với quyền sở hữu sản phẩm hoặc hàng hóa cho người mua;» [1][2][3] Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh. Các yêu cầu chưa đáp ứng: U1:r1 (Biên lợi nhuận gộp:? |
| Assessment | partial; oracle/audit PASS |

## 11. Agent/Tool Traces

M?i case JSON gi? question/context, unified requirements, planner proposal/effective plan,
validated operations/dependencies, selected/executed agents, tool parameters/results,
financial/document candidates, graph paths, M6 decisions/admission, M7 requirements,
Firewall checks, answer/citations v? stage/provider latency. Kh?ng ghi registry agents l? executed.

Specialists selected/executed: Profitability 10 cases, Liquidity/Leverage 2, Cash Flow 0.
Document Planner/Supervisor/Orchestrator executed trong 13 cases; nhi?u requirements
c?ng case ???c trace ri?ng. S? n?y l? cases c? execution, kh?ng ph?i s? HTTP/model calls.

Tool invocations trong trace: find_financial_facts21; calculate_financial_metric9;
get_metric_evidence_lineage9; search_document_evidence14; get_evidence_sources79;
get_graph_context9. Kh?ng g?i t?t c? specialists/tools cho m?i c?u h?i.

## 12. Negative Controls

Wrong company/document/composition/financial snapshot/document snapshot/scope v?
D03-B10 kh?ng ph?t h?nh claim/citation. C3 exact-reason closure tr?n code cu?i:
`D03-final-reason-control.json` gi? `cross_document_comparison_blocked_D03_B10`.

BBS trang13 v?n INVESTIGATE, kh?ng d?ng citation c?a claim b? t? ch?i. Inventory
page quality-blocked A4 c?ng partial. Unit controls bao g?m missing operand/graph,
provider failure, arbitrary LLM tool, causal-topic precedence, fabricated causal prose,
source-topic cooccurrence, unverified proof, partial status v? restart.

Real controls b? sung (`cache-controls/`): restart/cache completed v?i c?ng claims,
0 provider calls v? 0 executed agents; thi?u document evidence tr? partial, gi? numeric
claim h?p l?; source-context request c? citations, kh?ng th?m relation assertion.
Cache/restart 51,12s, missing document51,97s, source-context50,17s (local, ch?a t?i ?u).

`cross-snapshot-graph-control.json`: 7 contextual paths v? 7 nodes c?
snapshot_blocked nh?ng v?n c? original_citations, 0 claims admitted. Context kh?ng
th?nh semantic/causal proof. `topic-fix-old-proof-rejection.json` x?c nh?n old false
relevance proof b? t? ch?i khi replay, kh?ng rewrite accepted source data.

## 13. Root Causes & Fixes

- Mixed bị chặn tại pipeline/M7: thêm typed inventory và release hai lanes.
- Ledger default query chỉ tìm financial: dùng hai queries đúng typed identities.
- Citation renderer chỉ chấp nhận một namespace: giữ single financial context,
  cho phép original document contexts qua mixed inventory/Firewall.
- Cụm truy vấn policy gồm từ mô tả yêu cầu: bỏ tiền tố “chính sách” khỏi topic,
  giữ label gốc, kiểm chứng trích đoạn nguyên văn thay vì sinh paraphrase.
- Run trước sửa đạt 17/20 oracle: B1/B2/B3 lấy thêm đoạn BCC trang11 không liên
  quan vì topic bị kiểm tra như bag of words. Fix tổng quát tại `source_assertion`
  yêu cầu cụm topic liên tục trên source text liên tiếp, áp dụng chung M5/M6;
  không hardcode công ty/trang/answer. Old proof sai bị từ chối khi admission replay.
- Câu “có phải do chính sách…” phải được nhận diện là causal requirement trước
  document lookup. Thêm negative control để không âm thầm bỏ quan hệ người dùng hỏi.
- Các prefix trích đoạn lặp: ưu tiên đoạn liên tiếp dài hơn cùng selectors.
- BCC diagnostic folders khác accepted release: runner chọn đúng accepted release.
- Oracle A4 ban đầu bỏ qua `pdf_review:*` trên nguồn inventory; sửa kỳ vọng theo
  source-quality metadata đã duyệt thành partial. Không sửa/nới gate để đạt PASS.

## 14. Regression

Local: 593 relevant M4/M5/M6/M7/INT/QA-01a/EF tests PASS ? v?ng r?ng;
138 integration/coverage/render tests PASS sau s?a; 20 fusion/document tests PASS
sau topic fix; D03 exact-reason test PASS; 66 specialist tests v? m?t stale-caveat
projection control PASS sau live root-cause fix. C?c nh?m c? overlap, kh?ng c?ng
th?nh s? tests unique. Ruff lint/format, planning checker v? diff check ??t.
CI implementation: ch? push/ki?m tra ??ng SHA; kh?ng suy local PASS th?nh CI PASS.

## 15. Gemini Usage & Latency

Offline20 cases: 0 Gemini calls/tokens, kh?ng OCR/extraction. Median51,74s,
P95187,33s (local pipeline latency, g?m c? c?c intentional blocked cases).

| Live run | Outcome | Transport calls | Known tokens | Latency |
| --- | --- | ---: | ---: | ---: |
| A1 | Full; audit PASS | 2 | 6445 | 94,76s |
| B2 tr??c prompt fix | Partial; metric b? b? do stale caveat | 2 | 6416 | 67,53s |
| B2 sau prompt fix | Full; audit PASS | 3 | 6763 | 55,59s |
| A1 sau prompt fix | Full; audit PASS | 2 | 6882 | 77,41s |

T?ng9 transport attempts/12 cap, 26.506 known tokens; m?t HTTP503 c? usage unknown,
???c existing Planner recovery m?t l?n trong bound2. Live median72,47s/P9594,76s
(n=4, g?m initial partial); kh?ng ph?i benchmark hi?u n?ng. Model theo Gateway hi?n
c?; kh?ng ??i key/model ho?c paid fallback. Provider kh?ng cung c?p chi ph?, kh?ng
b?o chi ph? b?ng0. Kh?ng g?i cached/offline l? live. A1 proof ???c audit l?i theo
policy topic m?i; c? BBS/BCC ???c ch?y live l?i sau prompt fix v? ??u full. M7 kh?ng g?i model ?? paraphrase sau Firewall.

## 16. Limitations

Đây là Quick QA trên saved real-PDF evidence, không phải M8 hoặc independent
full-document financial audit. Trích đoạn không bảo đảm bao phủ toàn bộ policy.
Không có causal claim policy mới. Reporting scopes/accounting gates vẫn có thể
chặn phần tài chính; source caveats và page-level limitations vẫn hiển thị.

## 17. Handoff GEN-02

**QA-01b REVIEW**, ch?a DONE. Implementation s? ghi ??ng SHA sau commit v? CI.
Gi? GEN-01a/Web ngo?i commit; kh?ng b?t ??u GEN-02/PERF-01/CHAT-01/M8.
Next action: Tech Lead review implementation, actual answers v? evidence QA-01b.
