# QA-01b — Multi-Agent Financial & Document Evidence Fusion

Ngày 07/11/2026 (Asia/Bangkok). Status **REVIEW**, chờ Tech Lead nghiệm thu.
Baseline `0e985d2`; implementation `808bc77ebd9d7e9cf80f4b116b717ecc312e7630` đã push main.
[CI42380771375](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42380771375) completed/SUCCESS đúng SHA: **1.147 Python tests và 9 Web smoke PASS**;
lint/format/planning/typecheck/build đạt. Full regression manual SKIPPED.

## 1. Executive Summary

Mixed QA dùng lại M5/M4/BM25/EF-EG/M6/Ledger/M7 trên cùng approved filing.
Financial và document claims được kiểm chứng riêng rồi phát hành với citations riêng;
không tạo causal claim từ đồng xuất hiện. Bộ offline sau sửa đạt 20/20 oracle:
8 fully answered có caveats, 5 partial, 7 refused/clarified. Audit216 citations không lỗi.
Hai câu BBS/BCC trên prompt cuối đều live full. Chưa nghiệm thu DONE.

## 2. Existing Architecture & Integration Changes

Giữ FinancialQAPipeline, FinancialMultiAgentOrchestrator, Planner/Supervisor,
Adaptive Router và ba specialists. Fusion coordinator bind original request trước
subrequests; mỗi lane tiếp tục dùng orchestration/verification hiện có. Không tạo
framework, agent hoặc datastore mới. Financial-only/document-only giữ đường chạy
mặc định; deterministic numeric execution là tùy chọn rõ ràng.

## 3. Unified Requirements

FusionRequirement lưu ID, original span, execution question, target, lane/kind,
dependencies, evidence needs, verification requirements, support status và missing
information/reason. Causal/unsupported requirements vẫn ở inventory, không bị bỏ.
Một số paraphrase của approved operations được chuyển về catalog; không thêm công thức.
Tối đa12 requirements. M7/Firewall tự tính lại inventory từ original request.

## 4. M5 Adaptive Routing & Agent Collaboration

Orchestrator lập fusion plan. Financial lane tiếp tục Planner → Supervisor → Router →
specialists được chọn; document lane chỉ chạy khi có requirement tương ứng. Không gọi
cả ba specialists. Gemini Planner/specialists chạy khi request cho phép Gateway.
Chế độ deterministic chỉ dùng fact/metric numeric renderers hiện có, không giả model response.
Các diễn giải/quan hệ không được hỗ trợ giữ unmet.

## 5. Financial / BM25 / EF-EG Tool Execution

M4 giữ retrieval/calculator/source/lineage và accounting gates. BM25 tìm text/table
trong approved composition. Source excerpts cần cụm topic liên tục, nội dung thực
chất và kết thúc đoạn; tối đa3 selectors liên tiếp cùng source/page/request.
Không coi trích đoạn là tóm tắt toàn bộ thuyết minh. Graph dùng typed bounded requests
cho metric operands/source context; structural/contextual paths không là claim proof.

## 6. Evidence Fusion Contracts

EvidenceFusionBundle giữ bound context/reporting year/scope resolution/financial
descriptor, requirements, full lane results, financial execution, document candidates,
graph paths/original citations/basis, source quality, missing evidence và policy
independent_verified_components_only. Original identities không đổi.
Financial descriptor phải khớp approved composition; không lấy latest snapshot.
GEN-01 được hydrate từ normalized-release/audit-release theo báo cáo nghiệm thu;
normalized-final/audit-final là vòng chẩn đoán, không dùng làm oracle cuối.

## 7. M6 Cross-Evidence Verification

Giữ DeterministicFinancialValidator, EvidenceCritic, FinancialLogicCritic, Judge và
bounded revision. Document policy replay exact content/citations/continuity/quality.
Chỉ phát hành independent verified components; không có policy/proof cho causal
relation thì requirement đó unmet. Graph không đi vào admission proof.
BBS2025 trang13 vẫn INVESTIGATE do source-quality review.

## 8. Ledger Admission & Reuse

Financial/document entries giữ typed identities/proof versions. M7 truy vấn hai lanes
riêng: financial snapshot và document composition fingerprint/original snapshots.
Không gộp snapshots hoặc tạo claim tổng hợp giả. Document cache tiếp tục kiểm tra
pins trước reuse. Old false-relevance proof của run thử bị từ chối khi replay;
không rewrite accepted financial/document source artifacts.

## 9. M7 Grounded Output & Firewall

Composer/Firewall không tin inventory M5: tự phân rã original request và đọc admitted
Ledger. Thiếu bất kỳ ý nào thì partial; chỉ ACCEPT claims có citations đúng mới xuất.
Renderer cho phép original document namespaces trong mixed context, vẫn giữ một
financial context và một company. Mọi prose/causal assertion thêm ngoài protected
slots bị chặn. Không gọi model paraphrase sau Firewall.

## 10. Real PDF Quick QA

20 cases trên BBS2025/BCC2025/BCC2024. Oracles được lưu trước execution từ approved
facts/calculations, pinned evidence và PDF/source-quality review; không lấy output
pipeline làm ground truth. Đã xem trực tiếp renders BBS trang12/13, BCC2025 trang13,
BCC2024 trang18. Đây là Quick QA, không phải M8 hoặc full-PDF financial audit.

| Chỉ số | Offline sau sửa |
| --- | ---: |
| Cases / đạt oracle | 20 / 20 |
| Fully answered có caveats | 8 |
| Partially answered | 5 |
| Correctly refused/clarified | 7 (1 unsupported, 6 clarification) |
| Incorrect/unsupported release | 0 |
| Financial requirements covered | 12/14 |
| Document requirements covered | 12/14 |
| Citations audit đúng | 216/216 |
| Source/snapshot leakage | 0 |
| Unsupported causal claims phát hành | 0 |
| Causal requirement giữ unmet | 1 |
| Cases có graph retrieval | 9/20 |
| M6 ACCEPT / INVESTIGATE / ABSTAIN | 35 / 3 / 0 |
| Ledger stored / idempotent / rejected | 17 / 18 / 3 |

Coverage đếm13 cases bind được context;7 intentional binding/comparison controls không
thực thi requirements. Unsupported ROE/accounting restriction vẫn ở denominator
financial; hai nguồn quality-blocked vẫn ở denominator document.
Artifacts cuối: `artifacts/evidence/QA-01b/after-topic-fix/` (oracles, actual answers,
full traces, summary, independent-audit, integrity). Trước topic fix: `review-run/`,
17/20 oracle; B1/B2/B3 có thêm quote sai relevance. Giữ nguyên run lỗi để RCA.

### Năm actual E2E examples

Trích ngắn content được phát hành bên dưới; đáp án/citations đầy đủ ở từng case JSON.

#### A1

| Thành phần | Actual |
| --- | --- |
| Question | Biên lợi nhuận gộp BBS 2025 là bao nhiêu và báo cáo có thuyết minh gì về chính sách ghi nhận doanh thu? |
| Requirements | metric: gross_margin; document_evidence: chinh sach ghi nhan doanh thu |
| Agents executed | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'find_financial_facts': 2, 'calculate_financial_metric': 1, 'get_metric_evidence_lineage': 1, 'search_document_evidence': 1, 'get_evidence_sources': 9, 'get_graph_context': 1}; financial/document outcomes ở các dòng nguồn và M6 |
| Financial source | PDF trang [7]; snapshot `D-01/normalized-v2`; selector `/context/0` |
| Document source | PDF trang [12]; snapshot `artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json`; selector `/text_elements/18` |
| Graph | found; 2 structural/contextual edges; không claim support |
| M6 | {'ACCEPT': 4} |
| Ledger | {'stored': 4} |
| M7 | completed_with_caveats; Firewall ALLOW_WITH_CAVEAT; trích: Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 đạt 7,21%. [1][2][3][4][5][6][7][8][9][10][11][12][13] Tài liệu ghi «Doanh thu được xác định tương đối chắc chắn. Khi hợp đồng quy định người mua được quyền trả lại sản phẩm, hàng hóa đã mua theo những điều kiện cụ thể, Công ty chỉ được ghi nhận doanh thu khi những điều kiện cụ thể đó không còn tồn tại và người mua không được quyền trả lại sản phẩm, hàng hóa (trừ trường hợp khách … |
| Assessment | full; oracle/audit PASS |

#### A2

| Thành phần | Actual |
| --- | --- |
| Question | Nợ phải trả chiếm bao nhiêu phần trăm tổng tài sản BBS 2025? Báo cáo có thuyết minh về các khoản vay không? |
| Requirements | metric: debt_to_assets; document_evidence: vay |
| Agents executed | liquidity_and_leverage, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'find_financial_facts': 2, 'calculate_financial_metric': 1, 'get_metric_evidence_lineage': 1, 'search_document_evidence': 1, 'get_evidence_sources': 9, 'get_graph_context': 1}; financial/document outcomes ở các dòng nguồn và M6 |
| Financial source | PDF trang [5, 6]; snapshot `D-01/normalized-v2`; selector `/context/0` |
| Document source | PDF trang [12]; snapshot `artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json`; selector `/text_elements/8` |
| Graph | found; 2 structural/contextual edges; không claim support |
| M6 | {'ACCEPT': 4} |
| Ledger | {'stored': 4} |
| M7 | completed_with_caveats; Firewall ALLOW_WITH_CAVEAT; trích: Kỳ 2025-12-31 — Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%. [1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19] Tài liệu ghi «Chi phí đi vay bao gồm lãi tiền vay và các chi phí khác liên quan trực tiếp đến các khoản vay. Chi phí đi vay được ghi nhận vào chi phí sản xuất, kinh doanh trong năm khi phát sinh, ngoại trừ chi phí đi vay liên quan trực tiếp đến việc đầu tư, xây dựng ho… |
| Assessment | full; oracle/audit PASS |

#### A5

| Thành phần | Actual |
| --- | --- |
| Question | Doanh thu BBS 2025 tăng hay giảm so với năm trước và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu và nguyên nhân là gì? |
| Requirements | metric: revenue_yoy; document_evidence: chinh sach ghi nhan doanh thu; causal_explanation: unsupported_causal_inference |
| Agents executed | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'find_financial_facts': 2, 'calculate_financial_metric': 1, 'get_metric_evidence_lineage': 1, 'search_document_evidence': 1, 'get_evidence_sources': 9, 'get_graph_context': 1}; financial/document outcomes ở các dòng nguồn và M6 |
| Financial source | PDF trang [7]; snapshot `D-01/normalized-v2`; selector `/context/0` |
| Document source | PDF trang [12]; snapshot `artifacts/evidence/EXT-01/BBS_2025/responses-recovery/page-12.json`; selector `/text_elements/18` |
| Graph | found; 2 structural/contextual edges; không claim support |
| M6 | {'ACCEPT': 4} |
| Ledger | {'idempotent': 4} |
| M7 | partial_verified_coverage; Firewall ALLOW_WITH_CAVEAT; trích: Kỳ 2025 — Tăng trưởng doanh thu kỳ 2025 đạt 26,71%. [1][2][3][4][5][6][7][8][9][10][11][12] Tài liệu ghi «Doanh thu được xác định tương đối chắc chắn. Khi hợp đồng quy định người mua được quyền trả lại sản phẩm, hàng hóa đã mua theo những điều kiện cụ thể, Công ty chỉ được ghi nhận doanh thu khi những điều kiện cụ thể đó không còn tồn tại và người mua không được quyền trả lại sản phẩm, hàng hóa (trừ trường hợp khách … |
| Assessment | partial; oracle/audit PASS |

#### B2

| Thành phần | Actual |
| --- | --- |
| Question | Biên lợi nhuận gộp BCC 2025 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu? |
| Requirements | metric: gross_margin; document_evidence: chinh sach ghi nhan doanh thu |
| Agents executed | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'find_financial_facts': 2, 'calculate_financial_metric': 1, 'get_metric_evidence_lineage': 1, 'search_document_evidence': 1, 'get_evidence_sources': 6, 'get_graph_context': 1}; financial/document outcomes ở các dòng nguồn và M6 |
| Financial source | PDF trang [7]; snapshot `a49f826f-8e45-49c1-9e40-95f44e467e46`; selector `/context/0` |
| Document source | PDF trang [13]; snapshot `artifacts/evidence/EXT-01/BCC_2025/responses/page-13.json`; selector `/text_elements/16` |
| Graph | found; 2 structural/contextual edges; không claim support |
| M6 | {'ACCEPT': 3} |
| Ledger | {'stored': 1, 'idempotent': 2} |
| M7 | completed_with_caveats; Firewall ALLOW_WITH_CAVEAT; trích: Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 đạt 10,01%. [1][2][3][4][5][6][7][8][9][10][11][12] Tài liệu ghi «- Doanh thu được xác định tương đối chắc chắn. Khi hợp đồng quy định người mua được quyền trả lại sản phẩm, hàng hóa đã mua theo những điều kiện cụ thể, Công ty chỉ được ghi nhận doanh thu khi những điều kiện cụ thể đó không còn tồn tại và người mua không được quyền trả lại sản phẩm, hàng hóa (trừ trường hợp khách h… |
| Assessment | full; oracle/audit PASS |

#### C1

| Thành phần | Actual |
| --- | --- |
| Question | Biên lợi nhuận gộp BCC 2024 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu? |
| Requirements | metric: gross_margin; document_evidence: chinh sach ghi nhan doanh thu |
| Agents executed | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator |
| Tools / results | {'search_document_evidence': 1, 'get_evidence_sources': 3, 'get_graph_context': 1}; financial/document outcomes ở các dòng nguồn và M6 |
| Financial source | Không phát hành |
| Document source | PDF trang [18]; snapshot `artifacts/evidence/EXT-01/BCC_2024/responses/page-18.json`; selector `/text_elements/5` |
| Graph | found; 2 structural/contextual edges; không claim support |
| M6 | {'ACCEPT': 1} |
| Ledger | {'stored': 1} |
| M7 | partial_verified_coverage; Firewall ALLOW_WITH_CAVEAT; trích: Tài liệu ghi «Ghi nhận doanh thu Doanh thu bán hàng được ghi nhận khi đồng thời thỏa mãn tất cả năm (5) điều kiện sau: (a) Công ty đã chuyển giao phần lớn rủi ro và lợi ích gắn liền với quyền sở hữu sản phẩm hoặc hàng hóa cho người mua;» [1][2][3] Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh. Các yêu cầu chưa đáp ứng: U1:r1 (Biên lợi nhuận gộp: chưa có claim ACCEPT).… |
| Assessment | partial; oracle/audit PASS |

## 11. Agent/Tool Traces

Mỗi case giữ question/context, requirements, planner proposal/effective plan,
validated operations/dependencies, selected/executed agents, tool parameters/results,
candidates, graph paths, M6/admission, M7 selection/Firewall, answer/citations và
stage/provider latency. Không ghi registry agents là executed.
Specialists selected/executed: Profitability10 cases, Liquidity/Leverage2, Cash Flow0.
Document Planner/Supervisor/Orchestrator executed trong13 cases. Nhiều requirements
cùng case có trace riêng; số trên là cases, không phải số HTTP/model calls.
Tool invocations trong trace: find_financial_facts21; calculate_financial_metric9;
get_metric_evidence_lineage9; search_document_evidence14; get_evidence_sources79;
get_graph_context9. Không gọi mọi agents/tools cho mọi câu hỏi.

## 12. Negative Controls

Wrong company/document/composition/financial snapshot/document snapshot/scope và
D03-B10 không phát hành claim/citation. `D03-final-utf8-control.json` kiểm exact reason
cross_document_comparison_blocked_D03_B10 trên code cuối. BBS trang13 và inventory
quality-blocked giữ partial, không dùng rejected citations.
Unit controls gồm missing operand/graph, provider failure, arbitrary LLM tool,
causal-topic precedence, causal prose tampering, cooccurring topic words, unverified
proof, partial status và restart. `cache-controls/`: restart/cache cùng claims,
0provider calls/0executed agents; missing document vẫn giữ numeric verified partial;
source-context request có citations, không tạo relation assertion. Local latency:
restart/cache51,12s; missing document51,97s; source-context50,17s.
`cross-snapshot-graph-control.json`:7contextual paths và7snapshot_blocked nodes còn
original_citations;0claims admitted. `topic-fix-old-proof-rejection.json`: old false
relevance proof bị từ chối admission replay. Graph không thành semantic/causal proof.

## 13. Root Causes & Fixes

- Mixed bị chặn tại pipeline/M7: thêm unified inventory và release hai lanes.
- Ledger default query chỉ tìm financial: dùng hai typed queries, giữ original identities.
- Renderer chỉ chấp nhận một namespace: giữ một financial context/company, cho phép
  document source contexts qua mixed inventory/Firewall.
- Topic policy có tiền tố mô tả yêu cầu: bỏ “chính sách” khỏi query, giữ original label,
  kiểm chứng exact excerpts thay vì viết paraphrase mới.
- Run trước sửa đạt17/20: B1/B2/B3 lấy thêm đoạn BCC trang11 không liên quan vì
  matching dùng bag of words. Shared source_assertion nay yêu cầu cụm topic liên tục
  trên source text liên tiếp, áp dụng chung M5/M6; không hardcode company/page/answer.
  Old false proof bị từ chối khi replay; run sau đạt20/20 và audit216/216 citations.
- Ưu tiên đoạn liên tiếp dài hơn thay cho các prefix lặp cùng selectors.
- “Có phải do chính sách…” phải là causal requirement trước document lookup, tránh
  âm thầm bỏ quan hệ được hỏi. Chưa có policy/proof causal thì giữ unmet.
- BCC loader chọn accepted release, không dùng diagnostic-final làm ground truth.
- Oracle A4 ban đầu bỏ qua pdf_review trên nguồn inventory: sửa kỳ vọng theo approved
  source-quality metadata thành partial; không nới gate để đạt PASS.
- Live BCC: Planner/M4 đúng nhưng Specialist nói metric chưa approved do stale caveat.
  Prompt chung bổ sung typed current_metric_executions từ selected evidence (status,
  eligibility, approval), giữ caveats và candidate_pending_M6. Không sửa LLM response
  thành đáp án giả hoặc bypass M6. Live BCC và BBS trên prompt cuối đều full.

## 14. Regression

Local:593 relevant M4/M5/M6/M7/INT/QA-01a/EF tests PASS vòng rộng;138 integration/
coverage/render tests PASS sau sửa;20 fusion/document tests PASS sau topic fix;
D03 exact-reason control PASS;66 specialist tests và stale-caveat projection test
PASS sau live root-cause fix. Các nhóm overlap, không cộng thành unique test count.
Ruff/planning/diff đạt. [CI42380771375](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42380771375) completed/SUCCESS đúng implementation `808bc77ebd9d7e9cf80f4b116b717ecc312e7630`:
1.147 Python và9Web smoke PASS; lint/format/planning/typecheck/build đạt.
Full regression manual SKIPPED. Local engineering tests không phải full financial accuracy.

## 15. Gemini Usage & Latency

Offline20 cases:0Gemini calls/tokens, không OCR/extraction. Local pipeline median51,74s,
P95187,33s, gồm intentional blocked cases. Không phải M8/performance benchmark.

| Live run | Outcome | Transport calls | Known tokens | Latency |
| --- | --- | ---: | ---: | ---: |
| A1 initial | Full; current-policy audit PASS | 2 | 6445 | 94,76s |
| B2 trước prompt fix | Partial; metric bị bỏ do stale caveat | 2 | 6416 | 67,53s |
| B2 sau prompt fix | Full; audit PASS | 3 | 6763 | 55,59s |
| A1 sau prompt fix | Full; audit PASS | 2 | 6882 | 77,41s |

Tổng9transport attempts/12cap,26.506known tokens;1HTTP503 có usage unknown được
existing Planner recovery một lần trong bound2. Median live72,47s/P9594,76s
(n=4, gồm initial partial). BBS/BCC trên prompt cuối đều full. Không xoay key/model,
không paid fallback hoặc OCR; cost chưa được provider cung cấp, không báo bằng0.
Cached/offline không được gọi là live. M7 không paraphrase sau Firewall.

## 16. Limitations

Quick QA trên saved real-PDF evidence, không phải M8 hoặc independent full-document
financial audit. Trích đoạn không bảo đảm bao phủ toàn bộ policy. Decomposition còn
bounded theo catalog/intent patterns và existing Gemini financial planner; ambiguity
có thể cần clarification. Không có causal policy mới. Reporting scopes/accounting
restrictions vẫn có thể chặn financial lane. Source caveats/page-level locations
giữ nguyên. Latency local còn cao; không triển khai PERF-01 trong task này.

## 17. Handoff GEN-02

**QA-01b REVIEW**, chưa DONE. Implementation `808bc77ebd9d7e9cf80f4b116b717ecc312e7630` đã push main;
CI SUCCESS đúng SHA đã xác minh. Giữ GEN-01a/Web ngoài commit; không bắt đầu
GEN-02/PERF-01/CHAT-01/M8. Next action: Tech Lead review QA-01b và actual evidence.
