# GEN-02 — Cross-Company End-to-End Generalization & Blind QA Validation

Ngày 08/11/2026 (Asia/Bangkok). Status **REVIEW**, chờ Tech Lead; không tự DONE.
Baseline `02a160fdca013ac55972949c9002622dc643de01`; implementation `chưa commit`.
CI: chưa chạy remote. Giữ pending GEN-01a/Web ngoài implementation.

## 1. Executive Summary

Đây là engineering validation trên PDF scan thật, không M8 benchmark. 25 development
và15holdout đều chạy actual M5 → tools/BM25/EF-EG → M6 → Ledger → M7/Firewall bằng
persisted evidence/deterministic numeric pathways. Không mock kết quả chính.

**REVIEW có P1 blockers:** development22/22 fully-answerable đã đáp ứng đủ, nhưng
blind holdout chỉ7/12full,1partial và5source-answerable abstentions. Không có
unsupported release trong mẫu; không đề nghị coi generalization/M8 đã đạt.
H12 còn tái hiện positive QA-01b C1 partial→abstain regression về useful coverage;
safety controls và accepted ledger replay vẫn đạt. P1 cần Tech Lead quyết định
follow-up/fresh blind set; runtime không được tune theo holdout trong vòng này.

| Metric | Development before | Development after | Blind holdout |
| --- | ---: | ---: | ---: |
| Fully answerable cases (frozen/source oracle) | 22 | 22 | 12 |
| Fully answered | 10 | 22 | 7 |
| Partially answered | 4 | 1 | 1 |
| Abstained (tất cả lý do) | 10 | 2 | 7 |
| False abstentions (source-answerable) | 9 | 1 | 5 |
| Incorrect answers | 1 | 0 | 0 |
| Full Answer Rate | 10/22 | 22/22 | 7/12 |
| Useful Answer Rate / source-answerable | 14/25 | 23/25 | 8/13 |
| Citation correctness / source support | 191/191 | 249/249 | 84/84 |
| Unsupported released claims | 0/22 | 0/29 | 0/11 |
| Financial requirements fulfilled (kể cả capability gaps) | 11/16 | 15/16 | 7/9 |
| Document requirements fulfilled | 6/14 | 14/14 | 4/9 |
| Document retrieval coverage | 8/14 | 14/14 | 9/9 |
| Verified document source coverage | 6/14 | 14/14 | 4/9 |

Classification do independent audit quyết định theo từng requirement, không sao chép
status completed/partial của pipeline. Full cần đủ mọi ý; partial cần có ích thực sự.
Case-level và claim/citation-level denominators tách riêng. FAR giữ cả capability
gaps trong source-answerable denominator; ROE không được tính correct abstention
chỉ vì chưa có approved calculator. D03-B10 là valid restriction. D15 có đủ nội dung
được hỏi nhưng M7 còn conservatively báo partial vì một aspect bị tách thành unsupported.

Mọi numerator/denominator và danh sách IDs nằm trong `metrics-summary.json` và
`metrics` của từng `<phase>/independent-audit.json`. Financial coverage bổ sung
unsupported ROE requirement vào denominator: audit gốc operation-only giữ nguyên
để bảo toàn seal; supplementary denominator làm coverage thấp hơn, không tăng điểm.
Có cả source keys, coverage/retrieval/verification,
actual answers, citations, trace paths và unsupported claim IDs; không chỉ PASS/FAIL.

**development-before:** full=D01,D04,D05,D06,D09,D14,D17,D19,D20,D21; partial=D08,D18,D22,D23; abstain=D02,D03,D10,D11,D12,D13,D15,D16,D24,D25; incorrect=D07.
False abstention IDs: D02,D03,D10,D11,D12,D13,D15,D16,D24.

**development-after:** full=D01,D02,D03,D04,D05,D06,D07,D08,D09,D10,D11,D12,D13,D14,D15,D16,D17,D18,D19,D20,D21,D22; partial=D23; abstain=D24,D25; incorrect=.
False abstention IDs: D24.

**holdout:** full=H01,H02,H04,H05,H09,H10,H15; partial=H11; abstain=H03,H06,H07,H08,H12,H13,H14; incorrect=.
False abstention IDs: H03,H06,H07,H08,H12.

| Filing / subset | full | partial | abstain | fully-answerable denominator |
| --- | ---: | ---: | ---: | ---: |
| BBS_2025 / development-after | 12 | 1 | 0 | 12 |
| BCC_2024 / development-after | 4 | 0 | 1 | 4 |
| BCC_2025 / development-after | 6 | 0 | 1 | 6 |
| BBS_2024 / holdout | 1 | 0 | 0 | 1 |
| BBS_2025 / holdout | 2 | 1 | 3 | 4 |
| BCC_2024 / holdout | 1 | 0 | 3 | 3 |
| BCC_2025 / holdout | 3 | 0 | 1 | 4 |


## 2. Dataset, nguồn và blind integrity

40 câu tiếng Việt,25development/15holdout. Phân bố answerability: `{'FULLY_ANSWERABLE': 34, 'PARTIALLY_ANSWERABLE': 2, 'UNSUPPORTED_CAPABILITY': 1, 'POLICY_RESTRICTED': 1, 'UNANSWERABLE_SOURCE': 1, 'AMBIGUOUS': 1}`.
Phủ facts,3 approved metrics, operands/formulas, multi-step, policy/B09, vay/tồn kho/
dòng tiền, financial-document fusion, nhiều nguồn và5natural source/capability controls.
QA-01b adversarial controls chạy riêng, không đưa vào Answer Rate.

Author/oracle/auditor: Codex source-first, không phải independent human gold. Oracle
lấy accepted financial facts, công thức Decimal độc lập runtime và pinned document
selectors. PDF spot review đầu tiên: BBS2025 trang7/12, BCC2025 trang13, BCC2024
trang18; các trang quan trọng khác được đối chiếu bổ sung trong audit. Không dùng
system output làm oracle hoặc đổi expected answers để tăng điểm.

Freeze UTC `2026-11-08T13:18:54.630896+00:00`; development seal UTC `2026-11-08T14:37:42.152260+00:00`.
`freeze.json` hashes questions/sources/25dev/15holdout; `development-complete.json`
hashes final development audit và toàn bộ runtime. Runner từ chối holdout trước seal
hoặc khi runtime thay đổi sau seal. Không có actual holdout output trước seal;
không dùng holdout chọn fix/prompt/threshold. Runtime giữ nguyên sau holdout.

| Frozen file | SHA256 |
| --- | --- |
| questions.json | `6584039b63de50bbb76824c1ec154c8526251227aace93ee9efa0f74b34f6ad2` |
| sources.json | `2f6b1e314b1eddc97d9577c5ec219e64a32eba990154612bfd9a77e7996944ef` |
| development-oracles.json | `a36df988ac1ca6d61efbb4f2372f0ff54be26e2829e9d4a6b86d0119a552e1e5` |
| holdout-oracles.json | `e1505c874015ada9c611ba0152305cde47fd9c063e28ae5e7aacca3496352556` |


BBS2025 dùng D-01/normalized-v2; BCC2025 riêng và BCC2024 hợp nhất hydrate từ
`GEN-01/normalized-release` + `audit-release`, không diagnostic-final. BBS2024 chỉ
dùng accepted document evidence. Original document/snapshot/PDF identities giữ nguyên;
không xem BCC2024 hợp nhất và BCC2025 riêng là hai kỳ so sánh trực tiếp.
Environment/initial inherited hashes/source fingerprints: `environment-baseline.json`.
Oracle đầy đủ: `development-oracles.json`, `holdout-oracles.json`, `sources.json`.

**Capability oracle clarification H03:** expected numerical growth vẫn đúng theo
hai cột doanh thu trên PDF BCC2025 trang7. Oracle ban đầu đã nhầm global approved
formula với prepared metric tồn tại trong selected release; release chỉ có2metrics
gross_margin/debt_to_assets. `answerability-corrections.json` giữ nhãn gốc FA,
source=FA và pipeline=UNSUPPORTED_CAPABILITY. Primary denominator vẫn12 và score7/12;
không âm thầm dùng pipeline-only11 để nâng thành7/11. Không đổi frozen oracle/numeric
answer hoặc source-answerable FAR. H03 là M5 preparation/internal_error,0provider
calls; không phải provider outage hoặc thiếu số liệu PDF.

**Oracle/source correction công khai:** original PDF BCC2024 trang16 có từ “không”
nhưng frozen OCR `/text_elements/7` bị thiếu, đảo nghĩa điều kiện dự phòng phải thu.
Phát hiện khi đọc trang inventory trong development, trước holdout. Giữ original
oracle và source bytes; `pdf-review/discrepancies.json` lưu hai readings, lý do và
ảnh kiểm chứng. Independent audit coi phát hành đoạn lỗi này là unsupported dù
M6 ACCEPT. Không dùng sửa nhãn answerability để giảm false abstention. Không sửa
accepted catalog/OCR hoặc tự phê duyệt replacement release.

## 3. Root causes, fixes và regression

| Finding | Earliest stage | General fix / remaining boundary |
| --- | --- | --- |
| F01: D02/D03 ACCEPT nhưng scope bị M7 bỏ | M7 scope projection | Chỉ dùng admitted available/resolved fact contexts khớp exact snapshot và scope nhất quán; không dùng caller intent. |
| F02: D07 trả doanh thu tuyệt đối | M4/M5/M7 understanding | Shared growth paraphrase nhận company/year xen giữa, dùng approved revenue_yoy cùng filing. |
| F03: D08 bỏ operand follow-up | M7 requirements | Nhận “số liệu dùng” và giữ dependency tới metric; renderer chỉ dùng admitted operands. |
| F04: whole-sentence query | M5 topic parsing | Bounded general source topics, giữ unknown-topic fallback; không exact questions/company answers/oracle IDs. |
| F05: “quy định” bị coi là quarterly | Context understanding | Phân biệt cụm này; quarterly control vẫn unsupported. |
| F06: prefix thiếu điều kiện | M5 retrieval/excerpt; M7 coverage | Optional context_radius0–12, ranking vẫn3; tối đa12 contiguous references, không qua page/request/snapshot. Heading/bullets và declared condition count được kiểm tra ở builder/M7 selection. M6 literal-quotation replay giữ nguyên để bảo toàn accepted partial quotes. |
| F07: mất topic hoặc split noun | M5 decomposition | Giữ compound “vay và nợ thuê tài chính”; inventory nhiều document topics. |
| F08: live BBS empty model claims dù metric computed | Specialist generation | Chỉ fallback khi provider success, claims=[] và missing_information=[]; reuse existing numeric renderer sau selection gates, giữ raw model response và trace fallback, không tạo interpretation. Mọi candidate vẫn qua M6. |
| Source OCR omission | Extraction/evidence quality | Evidence gap đã ghi trực tiếp từ PDF; cần controlled replacement/review ngoài accepted inputs bất biến. |

Compatibility correction: một guard thử tại M6 làm BCC2024 accepted ledger không
replay được dù literal quote đúng. Guard được chuyển sang builder/M7 coverage trước
holdout; final development chạy lại toàn bộ, old ledgers chỉ đọc và không rewrite.
`failure-register.md` giữ evidence/RCA; intermediate failed/interrupted development
runs được bảo toàn nhưng không đưa vào final score. Numeric fixes không thêm formula,
agent, framework hoặc retrieval datastore. Không đổi D03-B10, nguồn, M6 quality gates,
ledger admission, claim-level citations hay Firewall. Graph association không là causal proof.

Targeted validation:4GEN-02 tests;138related regression trước fallback;70specialist/
GEN-02 sau fallback;43orchestrator/router/pipeline;35search/document/fusion sau final
boundary fix. Các nhóm có overlap, không cộng thành số tests độc lập. Real baseline
Sau compatibility correction:25GEN-02/document/fusion PASS;4GEN-02 final assertions
PASS;17accepted legacy claims replay nguyên file. Các kết quả trước guard thử không
được gán là final-policy evidence; `legacy-ledger-compatibility.json` xác minh riêng.
smoke8/8; final binding controls C3/D1–D6 đạt7/7. A7 real source-quality control giữ
ACCEPT1/INVESTIGATE1, không phát hành defective document. `regression.json` ghi lệnh/
thời điểm tương ứng. Lint/format, planning và diff checks là engineering evidence,
không chứng minh financial accuracy toàn PDF.

## 4. Agents, tools, M6/Ledger/M7

Traces giữ original request, bound identities, selected/executed roles, planner/
supervisor decisions, specialist candidates, tool order/selectors/results, source
quotations, graph paths, native decisions/reasons, admission/reuse, M7 inventory,
Firewall, final text/citations, latency/provider usage. Mixed traces có lane_results;
root stage NOT_EXECUTED không được hiểu là child stage bị bypass.

**Development after:** selected `{'profitability': 10, 'liquidity_and_leverage': 4, 'cash_flow_and_earnings_quality': 1, 'EvidenceAwareQueryPlanner': 13, 'RiskAwareSupervisor': 13, 'FinancialMultiAgentOrchestrator': 13}`; invoked `{'profitability': 10, 'liquidity_and_leverage': 4, 'cash_flow_and_earnings_quality': 1, 'EvidenceAwareQueryPlanner': 13, 'RiskAwareSupervisor': 13, 'FinancialMultiAgentOrchestrator': 13}`.
Tools `{'find_financial_facts': 24, 'get_evidence_sources': 63, 'calculate_financial_metric': 9, 'get_metric_evidence_lineage': 9, 'search_document_evidence': 14, 'get_graph_context': 3}`; M6 `{'ACCEPT': 29}`; Ledger `{'stored': 18, 'idempotent': 11}`.

**Blind holdout:** selected `{'profitability': 4, 'liquidity_and_leverage': 2, 'EvidenceAwareQueryPlanner': 8, 'RiskAwareSupervisor': 8, 'FinancialMultiAgentOrchestrator': 8}`; invoked `{'profitability': 4, 'liquidity_and_leverage': 2, 'EvidenceAwareQueryPlanner': 8, 'RiskAwareSupervisor': 8, 'FinancialMultiAgentOrchestrator': 8}`.
Tools `{'find_financial_facts': 8, 'get_evidence_sources': 22, 'calculate_financial_metric': 2, 'get_metric_evidence_lineage': 2, 'search_document_evidence': 8, 'get_graph_context': 1}`; M6 `{'ACCEPT': 11, 'INVESTIGATE': 1}`; Ledger `{'stored': 10, 'rejected': 1, 'idempotent': 1}`.


Selective specialists được gọi theo target, không gọi mọi agents cho mọi câu.
Financial/document components được verify độc lập. Không có ablation nên chưa định
lượng causal benefit của Multi-Agent; chỉ xác nhận coordination/grounding trong scope.

Live supplement: `live-development/` D18/D19 và `live-development-final/` D18. Tổng
budget6transport attempts, không repeated calls nâng điểm. D18 ban đầu partial vì
unexplained empty model output; sau fallback numeric + document đều full, trace giữ
`deterministic_numeric_fallback`, raw model claims=[] và M6 ACCEPT. D19 full qua model.
Tổng6Gateway transport invocations/19.742known tokens,0provider errors được báo;
cost và provider-side cached tokens chưa xác định.
Đây là development supplement, không blind score hoặc bằng chứng mọi câu chạy Gemini.
Final retrieval/list completeness fix được xác nhận thêm bằng deterministic real PDF
và regression sau live supplement; không tuyên bố live run có cùng toàn bộ runtime hash
với final holdout. Provider failures/tokens/cost/cache được giữ ở trace, không suy đoán
cost hoặc biến provider failures thành reasoning failures.

## 5. Latency và cache

| Phase | n | E2E median (s) | E2E P95 (s) |
| --- | ---: | ---: | ---: |
| development-before | 25 | 27.69 | 93.10 |
| development-after | 25 | 28.70 | 123.36 |
| holdout | 15 | 16.04 | 58.73 |

Ba cache probes development (không đưa vào QA score), trên biến thể trước compatibility correction; không phải OS-cold benchmark:

| Case | force-refresh (s) | cache reuse (s) | root mode | reused/new claims |
| --- | ---: | ---: | --- | --- |
| D01 | 11.91 | 14.11 | CACHE_HIT | 1/0 |
| D18 | 55.42 | 55.94 | CACHE_HIT | 2/0 |
| D19 | 49.76 | 49.28 | CACHE_HIT | 2/0 |


Chi tiết stage median/P95 nằm trong audit JSON, kể cả financial/document child stages.
Không cộng latency cha/con bị overlap. Main QA force_refresh=true; không báo chúng
là cache-hit benchmark. Warm-cache probes được lưu riêng nếu có. Catalog startup ở
ngoài p.run; OS cache/concurrent validation load không được kiểm soát. Không dùng
before/after latency để kết luận tối ưu hiệu năng; GEN-02 không triển khai PERF-01.
Graph materialization/validation, source hydration và proof/ledger replay vẫn là
chi phí đáng chú ý; cần đo riêng cold/warm và startup trong PERF-01.

## 6. Bảng 40 câu — independent final classification

Expected abbreviations: FA=FULLY_ANSWERABLE; PA=PARTIALLY_ANSWERABLE;
UC=UNSUPPORTED_CAPABILITY; PR=POLICY_RESTRICTED; US=UNANSWERABLE_SOURCE; AM=AMBIGUOUS.
Key tools rút gọn theo operation names; full results/citations nằm ở trace path tương ứng.

| ID | Company | Question | Expected | Actual classification | Agent(s) invoked | Key tools | M6/M7 | Citation | Root cause |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D01 | BBS_2025 | Cho tôi biết doanh thu thuần của BBS năm 2025. | FA | full | profitability | find_financial_facts, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 10/10 | đủ yêu cầu |
| D02 | BCC_2025 | Tổng tài sản cuối năm 2025 của BCC trên báo cáo riêng là bao nhiêu? | FA | full | liquidity_and_leverage | find_financial_facts, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 9/9 | đủ yêu cầu |
| D03 | BCC_2024 | Doanh thu thuần BCC năm 2024 trên báo cáo hợp nhất là bao nhiêu? | FA | full | profitability | find_financial_facts, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 11/11 | đủ yêu cầu |
| D04 | BBS_2025 | Dòng tiền thuần từ hoạt động kinh doanh của BBS năm 2025 là bao nhiêu? | FA | full | cash_flow_and_earnings_quality | find_financial_facts, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 11/11 | đủ yêu cầu |
| D05 | BBS_2025 | BBS năm 2025 có biên lợi nhuận gộp bao nhiêu phần trăm? | FA | full | profitability | find_financial_facts, calculate_financial_metric, get_metric_evidence_lineage | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 13/13 | đủ yêu cầu |
| D06 | BCC_2025 | Tỷ lệ nợ phải trả trên tổng tài sản BCC cuối năm 2025 là bao nhiêu? | FA | full | liquidity_and_leverage | find_financial_facts, calculate_financial_metric, get_metric_evidence_lineage | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 18/18 | đủ yêu cầu |
| D07 | BBS_2025 | Doanh thu BBS năm 2025 tăng hay giảm so với năm trước? | FA | full | profitability | find_financial_facts, calculate_financial_metric, get_metric_evidence_lineage | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 12/12 | đủ yêu cầu |
| D08 | BCC_2025 | Giải thích công thức biên lợi nhuận gộp BCC 2025 và nêu số liệu dùng để tính. | FA | full | profitability | find_financial_facts, calculate_financial_metric, get_metric_evidence_lineage | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 12/12 | đủ yêu cầu |
| D09 | BBS_2025 | Biên lợi nhuận gộp và tỷ lệ nợ trên tổng tài sản BBS năm 2025 lần lượt là bao nhiêu? | FA | full | profitability, liquidity_and_leverage | find_financial_facts, calculate_financial_metric, get_metric_evidence_lineage | {'ACCEPT': 2}/answered/ALLOW_WITH_CAVEAT | 32/32 | đủ yêu cầu |
| D10 | BBS_2025 | Thuyết minh BBS 2025 nêu những điều kiện nào để ghi nhận doanh thu bán hàng? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 6/6 | đủ yêu cầu |
| D11 | BCC_2025 | Chính sách ghi nhận doanh thu bán hàng của BCC năm 2025 gồm các điều kiện gì? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 6/6 | đủ yêu cầu |
| D12 | BCC_2024 | Thuyết minh BCC 2024 nói gì về các điều kiện ghi nhận doanh thu bán hàng? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 6/6 | đủ yêu cầu |
| D13 | BBS_2025 | BBS 2025 thuyết minh thế nào về việc phân loại các khoản vay ngắn hạn và dài hạn? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 2/2 | đủ yêu cầu |
| D14 | BCC_2025 | Báo cáo BCC 2025 thuyết minh gì về vay và nợ thuê tài chính? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 2/2 | đủ yêu cầu |
| D15 | BBS_2025 | Chính sách chi phí đi vay BBS 2025 quy định ghi nhận chi phí và vốn hóa ra sao? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/partial/ALLOW_WITH_CAVEAT | 5/5 | P2: dư unmet aspect, quote đủ nội dung |
| D16 | BCC_2024 | Thuyết minh BCC 2024 nói gì về phương pháp hạch toán hàng tồn kho? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 5/5 | đủ yêu cầu |
| D17 | BBS_2025 | Thuyết minh BBS 2025 nói gì về nhân viên quản lý chủ chốt? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 3/3 | đủ yêu cầu |
| D18 | BBS_2025 | Biên lợi nhuận gộp BBS 2025 là bao nhiêu và chính sách ghi nhận doanh thu bán hàng yêu cầu các điều kiện nào? | FA | full | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | find_financial_facts, calculate_financial_metric, get_metric_evidence_lineage, search_document_evidence, get_evidence_sources, get_graph_context | {'ACCEPT': 2}/answered/ALLOW_WITH_CAVEAT | 19/19 | đủ yêu cầu |
| D19 | BCC_2025 | Tỷ lệ nợ trên tổng tài sản BCC 2025 là bao nhiêu và thuyết minh gì về vay và nợ thuê tài chính? | FA | full | liquidity_and_leverage, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | find_financial_facts, calculate_financial_metric, get_metric_evidence_lineage, search_document_evidence, get_evidence_sources, get_graph_context | {'ACCEPT': 2}/answered/ALLOW_WITH_CAVEAT | 20/20 | đủ yêu cầu |
| D20 | BBS_2025 | Doanh thu thuần BBS 2025 là bao nhiêu và thuyết minh gì về nhân viên quản lý chủ chốt? | FA | full | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | find_financial_facts, get_evidence_sources, search_document_evidence | {'ACCEPT': 2}/answered/ALLOW_WITH_CAVEAT | 13/13 | đủ yêu cầu |
| D21 | BCC_2024 | Doanh thu thuần BCC 2024 là bao nhiêu và thuyết minh gì về các khoản giảm trừ doanh thu? | FA | full | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | find_financial_facts, get_evidence_sources, search_document_evidence | {'ACCEPT': 2}/answered/ALLOW_WITH_CAVEAT | 14/14 | đủ yêu cầu |
| D22 | BBS_2025 | Thuyết minh BBS 2025 nói gì về nhân viên quản lý chủ chốt và chính sách chi phí đi vay? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 2}/answered/ALLOW_WITH_CAVEAT | 8/8 | đủ yêu cầu |
| D23 | BBS_2025 | Doanh thu BBS năm 2025 tăng hay giảm so với năm trước và vì sao có biến động này? | PA | partial | profitability | find_financial_facts, calculate_financial_metric, get_metric_evidence_lineage, get_graph_context | {'ACCEPT': 1}/partial/ALLOW_WITH_CAVEAT | 12/12 | causal evidence gap / valid bounded inference |
| D24 | BCC_2025 | Tính ROE của BCC năm 2025 từ báo cáo riêng. | UC | abstain | — | — | {}/None/None | 0/0 | unsupported approved-calculator capability |
| D25 | BCC_2024 | So sánh doanh thu BCC 2024 hợp nhất với BCC 2025 riêng. | PR | abstain | — | — | {}/None/None | 0/0 | context D03-B10 restriction |
| H01 | BCC_2025 | Lợi nhuận gộp BCC trong năm 2025 là bao nhiêu? | FA | full | profitability | find_financial_facts, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 9/9 | đủ yêu cầu |
| H02 | BBS_2025 | Tại ngày 31/12/2025 tổng nợ phải trả BBS là bao nhiêu? | FA | full | liquidity_and_leverage | find_financial_facts, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 10/10 | đủ yêu cầu |
| H03 | BCC_2025 | BCC năm 2025 có tăng trưởng doanh thu bao nhiêu phần trăm? | FA | abstain | — | — | {}/None/None | 0/0 | M5 prepared metric materialization (P1) |
| H04 | BBS_2025 | Công thức tỷ lệ nợ trên tổng tài sản BBS 2025 dùng những số liệu nào? | FA | full | liquidity_and_leverage | find_financial_facts, calculate_financial_metric, get_metric_evidence_lineage | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 19/19 | đủ yêu cầu |
| H05 | BCC_2025 | Biên lợi nhuận gộp BCC 2025 là bao nhiêu và doanh thu thuần là bao nhiêu? | FA | full | profitability | find_financial_facts, get_evidence_sources, calculate_financial_metric, get_metric_evidence_lineage | {'ACCEPT': 2}/answered/ALLOW_WITH_CAVEAT | 12/12 | đủ yêu cầu |
| H06 | BCC_2024 | Thuyết minh BCC 2024 nói gì về khấu hao phần mềm máy tính? | FA | abstain | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence | {}/abstained/ALLOW | 0/0 | M5 semantic topic/excerpt selection (P1) |
| H07 | BBS_2025 | Thuyết minh BBS 2025 nói gì về tài sản cố định hữu hình và khấu hao? | FA | abstain | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'INVESTIGATE': 1}/abstained/ALLOW | 0/0 | M5 excerpt/page selection (P1), then valid M6 quality block |
| H08 | BCC_2024 | Thuyết minh BCC 2024 nói gì về dự phòng phải thu khó đòi? | FA | abstain | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence | {}/abstained/ALLOW | 0/0 | source extraction/OCR gap, then M5 topic rejection |
| H09 | BCC_2025 | Doanh thu thuần BCC 2025 là bao nhiêu và thuyết minh gì về ghi nhận doanh thu bán hàng? | FA | full | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | find_financial_facts, get_evidence_sources, search_document_evidence | {'ACCEPT': 2}/answered/ALLOW_WITH_CAVEAT | 15/15 | đủ yêu cầu |
| H10 | BCC_2024 | Doanh thu thuần BCC 2024 là bao nhiêu và chính sách chi phí đi vay được thuyết minh thế nào? | FA | full | profitability, EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | find_financial_facts, get_evidence_sources, search_document_evidence | {'ACCEPT': 2}/answered/ALLOW_WITH_CAVEAT | 13/13 | đủ yêu cầu |
| H11 | BBS_2025 | Thuyết minh BBS 2025 nói gì về các khoản nợ phải trả và về vay và nợ thuê tài chính? | FA | partial | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 5/5 | M5 document requirement decomposition (P1) |
| H12 | BCC_2024 | Biên lợi nhuận gộp BCC 2024 là bao nhiêu và thuyết minh gì về ghi nhận doanh thu? | PA | abstain | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_graph_context | {}/abstained/ALLOW | 0/0 | M4 accounting-basis gate + M5 nested-heading selection (P1) |
| H13 | BBS_2025 | BBS 2025 có công bố dự báo giá cổ phiếu năm tới không? | US | abstain | — | — | {}/None/None | 0/0 | source/capability absent |
| H14 | BBS_2025 | Cho tôi biết doanh thu thuần BBS. | AM | abstain | — | — | {}/None/None | 0/0 | context period disambiguation |
| H15 | BBS_2024 | BBS 2024 ghi “Chi tiết các khoản vay ngắn hạn” ở đâu trong báo cáo? | FA | full | EvidenceAwareQueryPlanner, RiskAwareSupervisor, FinancialMultiAgentOrchestrator | search_document_evidence, get_evidence_sources | {'ACCEPT': 1}/answered/ALLOW_WITH_CAVEAT | 1/1 | đủ yêu cầu |


Mỗi câu có expected facts/calculations hoặc source page/quote/selectors trong frozen
oracles; actual final answer/citations và requirement-level coverage nằm trong audit
JSON và `<phase>/<ID>.json`. Citation correctness kiểm tra binding, original selector/
page/image và support của quoted/calculated claim; semantic answer relevance và
completeness được chấm riêng. Không coi citation đúng trang là đủ financial proof.

Citations page-level/uncertain vẫn giữ caveats; chưa visual-gold từng ô. Retrieval
coverage tính expected selectors trong returned hits/neighbors, không đồng nghĩa
BM25 semantic relevance hoặc verification coverage: holdout9/9retrieved nhưng chỉ
4/9document requirements được verified/released. Đây là khoảng cách selection,
heading/context và source quality, không có bằng chứng cần đổi sang vector DB.

### Holdout RCA — runtime giữ nguyên sau seal

| ID | Earliest stage | Independent finding / downstream symptom |
| --- | --- | --- |
| H03 | M5 prepared metric materialization (P1) | No selected-filing revenue_yoy record despite approved formula and source inputs.0tools/0provider calls; not provider failure. Unhandled missing preparation becomes internal_error. Original answerability assumption and primary conservative denominator retained; see answerability-corrections.json. |
| H06 | M5 semantic topic/excerpt selection (P1) | BM25 returns expected software paragraph17/11 and full neighbors. Builder's strict topic/heading string match rejects reordered 'khấu hao phần mềm máy tính' vs source 'phần mềm máy tính được khấu hao';0candidates, M6 not reached. |
| H07 | M5 excerpt/page selection (P1), then valid M6 quality block | Clean depreciation method exists page11/9, but builder does not join/select that continuation; page10 candidate has an existing pdf_review flag and M6 correctly INVESTIGATE/source_quality. Do not weaken quality gate to answer. |
| H08 | source extraction/OCR gap, then M5 topic rejection | Frozen accepted paragraph16/7 omits negation vs original PDF. BM25 retrieves it, but builder generates0candidates; no defective claim released. Source-answerable capability gap remains counted; not a claimed quality-gate success. |
| H11 | M5 document requirement decomposition (P1) | Document cue is not inherited by bare second conjunct 'về vay và nợ thuê tài chính'. Only payables topic searched/verified; loan paragraph12/6 never requested. M7 reuses same bounded inventory and incorrectly reports completed; independent audit is partial1/2. |
| H12 | M4 accounting-basis gate + M5 nested-heading selection (P1) | Financial lane correctly blocks accounting_basis_missing. Document BM25 finds page18/5–11, but builder separates topic heading5 from sales-list header6, losing exact query phrase;0doc candidates. Expected useful document partial is lost. This also reproduces a positive QA-01b C1 partial→abstain regression; not a safety-control failure. Needs parent/lead-in heading grouping or explicit partial coverage design, with a fresh blind set before claiming post-fix generalization. |
| H13 | source/capability absent | No accepted forecast source; no stock-price prediction capability. Correct natural abstention control. |
| H14 | context period disambiguation | Missing reporting year; period_required clarification is correct. |


## 7. Remaining limitations và Tech Lead decisions

Independent holdout results và các failed requirements phải được xem trong audit;
không dùng chúng sửa runtime sau seal. Parser source topics/boundaries vẫn bounded,
chưa general semantic understanding hoặc cross-page/table-narrative joining hoàn chỉnh.
Các gaps cần phân biệt: bug/parsing, source OCR defect, approved capability missing
(ROE, accounting-basis eligibility), causal evidence absent và valid D03-B10.

Tech Lead cần quyết định scope tiếp theo: controlled source-quality replacement
release cho OCR omission; xử lý các P1 holdout trước khi nghiệm thu chất lượng QA
rộng hơn. Technical blockers cụ thể: không dùng lại15câu đã xem để chọn fix rồi gọi
post-fix là blind; cần Owner/Tech Lead giao follow-up và một fresh locked holdout.
Các proposal dưới đây chưa triển khai, không đổi approved policies trong GEN-02:

- H03: chuẩn bị DerivedMetric revenue_yoy vào release riêng từ approved same-filing
  facts/roles/policies, giữ original snapshots; trả capability/preparation reason thay
  vì internal_error khi record thiếu. Không thêm công thức hoặc sửa accepted release.
- H06/H07/H12: chọn đúng paragraph/topic-action; bảo toàn parent topic heading và
  lead-in/list header trong cùng source, xử lý continuation/table-narrative joins có
  proof. Ưu tiên grouping đủ list trước; nếu cần partial-document coverage contract,
  trình policy rõ trước khi đổi M7. Không mở quality gate hay bag-of-words proof.
- H11: giữ document intent qua bare conjunct, inventory cả payables và loans;
  M7 phải phản ánh thiếu requirement, không báo completed chỉ vì shared parser bỏ ý.
- H08: controlled PDF review/corrected source ở release mới trước khi mở rộng
  semantic selection, tránh một parser rộng hơn vô tình phát hành omitted-negation OCR.

ROE chưa approved, BCC2024 accounting basis unresolved, causal proof absent và
D03-B10 tiếp tục giữ nguyên. Các P1 trên là blockers được nêu cho REVIEW, không
được gọi là đã sửa hoặc dùng CI xanh để coi financial/generalization quality đạt.

PERF-01: profiling riêng graph/replay/startup/cache. WEB-02: có thể demo trong scope
approved sources với partial/abstention/caveats rõ; GEN-02 không redesign Web.
M8: chưa đủ điều kiện tuyên bố benchmark/financial accuracy; cần human gold độc lập,
nguồn OCR đáng tin và ablation, không suy rộng development score thành generalization.

Artifacts local giữ ngoài Git theo chính sách dữ liệu; implementation/report không
commit raw/OCR/PDF/normalized/canonical, secrets hoặc pending GEN-01a/Web.
Next action: **dừng REVIEW, chờ Tech Lead nghiệm thu và quyết định follow-up scope**.
