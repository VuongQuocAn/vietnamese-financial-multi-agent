# E2E-ARCH-02 — Full Pipeline Integration

Ngày17/11/2026 (Asia/Bangkok). **DONE — Owner xác nhận**; implementation
[`84ae70a9172dc63b105f57663a5dd2eb31d321f2`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/84ae70a9172dc63b105f57663a5dd2eb31d321f2), baseline remote `28cabc4`.
Worktree riêng, không đưa local edits có trước vào commit.

Owner nghiệm thu E2E-ARCH-02 tại bàn giao `b4c84b3` đã push main/remote SHA
verified; giữ nguyên evidence và các giới hạn bên dưới. Phiên đóng chỉ cập nhật
tài liệu/tracking và kiểm planning/diff/Git, không sửa runtime hoặc chạy lại
tests/Qwen/benchmark/CI; chưa triển khai E2E-VAL-01.

## Phạm vi và kết luận

Bảy câu tự soạn từ JSON BBS2025/ADC2021 đã import, không đọc/dùng câu hỏi hoặc
Gold của45Pilot/600Full ViFinBench. Dùng Qwen `qwen3-8b-awq-t4`, Gateway chung,
Adaptive Coordinator V2, Financial Tools/EF-EG, Docker Python, M6/Ledger và M7.
Không OCR/Gemini/PDF/fullCI hoặc benchmark. Không đổi pipeline/agents/contracts.

Đã phát hiện và sửa **một lỗi tích hợp quan trọng**: `release_lite()` ở API luôn
ép `allow_gateway=False` khi `integration_v2=True`. Vì vậy M7-ANSWER-01 hoạt động
khi gọi riêng nhưng Answer Agent bị bỏ qua trong pipeline đầy đủ. Bản sửa truyền
nguyên request đã bind sang `compose_lite`; giữ cờ caller, deterministic mode,
request budget, M6 ACCEPT, goal bindings, numerical guard và citation integrity.

Sáu câu baseline dùng runtime `28cabc4`; không gán những lượt này cho code cuối.
Sau sửa chỉ retest SH02 và thêm PY07 để kiểm Python với hai kỳ có nguồn rõ ràng;
không tối ưu prompt/code theo từng câu. Tổng cap40actual calls,10/request,
300s/request; không chủ động retry transport, không vòng FIX tiếp.

Đã chạy **7câu mới/8lượt,36actual Qwen calls,243.807known tokens,1unknown usage**
(Python generation timeout),0transport retry. Baseline29calls/207.236tokens;
final7calls/36.571tokens. Wall pipeline cộng821,601s, chưa gồm load catalog.
Hai ca final đều `completed_with_caveats`: SH02 natural answer và PY07 thực thi
Python → independent M6 replay →3ACCEPT/G1–G3 → Ledger v2 → natural RMS.
Trong7câu unique lấy SH02 bản cuối:2full coverage,2partial,3không phát hành.
Đây là integration probes, không phải accuracy benchmark hoặc quyết định GO Pilot.

## Kết quả từng câu

Coverage bên dưới là **satisfied/planned goals**, không phải completeness hay
accuracy độc lập. Citations là references hiển thị, nhiều references có thể cùng
trang JSON vì có value/label/header/unit/company anchors khác nhau. Latency là
wall của `FinancialQAPipeline.run`, chưa gồm load catalog; load được lưu riêng.

| Câu mới | Kết quả đối chiếu nguồn | Coverage / citations | Calls / latency |
| --- | --- | --- | --- |
| SH01: BBS2025, lợi nhuận gộp2024 | Đúng **36.432.410.381VND**, nhưng trả thêm2025 và tăng trưởng ngoài câu hỏi; `partial_verified_coverage` | 2/3;8refs | 7;177,054s |
| SH02: ADC2021, tổng lợi nhuận kế toán trước thuế | Đúng **13.624.955.440VND**, `completed_with_caveats`. Baseline M7 deterministic; final Qwen natural answer, không fallback | 1/1;5refs ở cả hai lượt | baseline2;24,164s → final3;30,760s |
| NU03: BBS, doanh thu thuần2025 trừ2024 | Đúng **94.967.158.941VND**; `partial_verified_coverage`. Hai operands ACCEPT nhưng thiếu verified support cho G1/G2 | 1/3;8refs | 5;108,244s |
| MH04: chọn năm doanh thu thấp hơn → lợi nhuận gộp cùng năm → tỷ lệ% | Không phát hành; `internal_error`. Có scalar2024 và join1:1, nhưng thiếu selection/domain proof; consumer dùng task IDs làm source handles | 0/3;0refs | 6;162,933s |
| PY05: độ lệch chuẩn tổng thể tổng tài sản2024/2025 | Không phát hành; `verification_blocked`. Python code generation timeout; sources có ngày01/01/2025 và31/12/2025, không tự nâng đầu kỳ thành31/12/2024 | 0/3;0refs | 7;204,790s |
| GAP06: ADC2021, doanh thu thuần | Không phát hành; `verification_blocked`. Ô nguồn tồn tại **299.308.198.903VND**, nhưng chưa mapped thành canonical revenue khả dụng | 0/1;0refs | 2;14,619s |
| PY07: RMS lợi nhuận gộp BBS2024/2025 | Đúng **34.514.016.067,04VND**, `completed_with_caveats`; independent replay khớp. M7 natural RMS, backend bổ sung2facts bị model bỏ sót | 3/3;8refs | 4;99,037s |

## Trace phối hợp và nguyên nhân

Ký hiệu: C=Coordinator Qwen; F=`get_financial_fact`; E=`get_evidence_sources`;
D=demand Qwen; S=specialist Qwen; V=M6; L=Ledger; A=M7 Answer Agent Qwen.
Role specialist được ghi riêng với việc role có gọi LLM hay dùng numeric proposal
từ observation; không đếm mọi role trace thành một provider call.

- **SH01:** C tự thêm G2/G3 → profitability T1/T2 →2F/2E,2S → V →
  repair1(D/S/V), reuse nhánh cũ →3ACCEPT/L → M7 deterministic. T3 dùng Calculator
  subtract/divide; prose số sai của specialist không thay thế số render từ nguồn.
  Planner còn gán `python_requirement=power` cho tăng trưởng; capability gate
  chặn Python vì câu hỏi không cần primitive đó. Lỗi lập kế hoạch/coverage,
  không mất nguồn ở handoff.
- **SH02 baseline/final:** C → profitability observation proposal →1F/1E →
  V semantic1call/1ACCEPT/G1 → L → M7. Final có thêm đúng1A, natural answer giữ
  số/coverage/citations; baseline0A do lỗi API nói trên. Đây là fresh full E2E
  trên implementation cuối, không phải replay riêng M7.
- **NU03:** C → T1/T2 revenue →2D →4F/4E → profitability T3 nhận dependencies →
  S/Calculator subtract → V semantic/3ACCEPT → L → M7 deterministic.
  G3 có support; G1/G2 không có support dù true scalar đã ACCEPT. Không tự cấp
  bindings từ arithmetic ACCEPT. Python bị gate dù planner đề xuất power.
- **MH04:** C → D/T1 scalar doanh thu2024 → D/T2 gross profit2024 → S/Calculator
  percentage → D/T3 dùng `source:T1/T2` → `demand_source_unknown_or_not_fact`.
  Có4F/4E/4`get_graph_context(found)` và join doanh thu↔gross profit matched1:1;
  T1 không có typed selection/domain chứng minh phép chọn trên cả hai năm.
  V trả3INVESTIGATE, raw semantic INSUFFICIENT;0admission/0release. Đây gồm lỗi
  reasoning/schema demand và verification thiếu support; không tự sửa handles
  hay nới obligations để cứu câu hỏi. Đối chiếu nguồn độc lập cho thấy tỷ lệ
  năm2024 đáng ra khoảng10,2480%, nhưng không dùng số này làm output hệ thống.
  Raw reasons còn dùng việc scalar không đáp ứng selection goal để bác truth
  của scalar; cần review việc tách truth khỏi goal support trước đánh giá Pilot.
- **PY05:** C → liquidity_and_leverage T1/T2 →2D/2S →4F/4E/4graph(found) →
  cash_flow_and_earnings_quality T3/Python → timeout1call → V. T1 đã chọn thêm
  total_liabilities cùng01/01/2025; không coi đó là tài sản2024. V có3ACCEPT và
  1INVESTIGATE nhưng không goal binding, L không cung cấp claim đủ quyền phát
  hành;0citations. Lỗi model chọn nguồn/kỳ và provider timeout, không chứng minh
  Docker execution/independent replay thành công ở lượt này.
- **GAP06:** C → profitability/S, source list rỗng →0F/0E/0candidate → không có
  semantic/admission → M7 giữ gap. Đây là gap canonical import/mapping; không
  kết luận toàn báo cáo/PDF thiếu doanh thu. Không sửa import/dữ liệu trong task.
- **PY07 final:** C → profitability T1/T2 observation proposals →2F/2E →
  cash_flow_and_earnings_quality T3 sau T1/T2 → Python Qwen1call → Docker worker →
  V independent Docker replay + semantic1call →3ACCEPT với G1/G2/G3 → L v2 → A.
  Không demand/S call thừa; cả2source rows được truyền qua dependency manifest,
  đúng gross profit2024/2025, raw/base VND và pointers trang7. Code/result có digest;
  replay exact `34514016067.03864443358779448481145VND`, khớp phép tính đối chiếu
  độc lập từ JSON. Worker image pin từ M5-PY-01, không host execution/image pull.
  M7 viết đoạn RMS đúng, nhưng bỏ2facts trung gian và tự ghi advisory gap trái
  Ledger. Backend bỏ advisory gap, phục hồi2ACCEPT facts (`fallback=true`,
  `omitted_verified_findings`), giữ coverage3/3 và8refs. Hai ca final tổng13refs. Không có
  câu “chưa ACCEPT RMS” trong output. Đây là giới hạn generation được chặn, không
  sửa tiếp model hoặc nới gate.

## Grounding và kiểm tra

Source đối chiếu thủ công: BBS JSON trang7, `/blocks/3/table/rows/4/5` cho gross
profit2024; revenue2025/2024 ở `/blocks/3/table/rows/2/4` và `/2/5`. ADC JSON
trang11, `/blocks/4/table/rows/14/3` cho profit-before-tax; revenue ở `/rows/2/3`.
Nguồn có values/labels/headers và source digests; scope vẫn unresolved, provenance
page-level/uncertain và **chưa PDF-verified**, giữ caveats trong output.

Audit offline từ saved trace/Ledger,0model calls: coverage tái tính khớp exact;
claim-source bindings và references khớp Ledger; TaskResult digests cùng
dependency handles/revisions/digests giữ nguyên. **34references/11claim-source
bindings** qua8lượt khớp; coverage từ released claims giữ nguyên M6 support.
Cả8graph calls baseline trả
found; graph chỉ là nguồn quan hệ cấu trúc, không tự cấp nghĩa kế toán.
Hợp57source JSON bất biến;185runtime hashes final khớp blob của implementation
`84ae70a`, không chỉ working tree.80local files có trước giữ nguyên byte;
checkout gốc vẫn ở local main `9a3adba`, publish từ worktree riêng để giữ edits.

**6targeted PASS**:3regression controls ở API→M6→Ledger→M7 (auto cho phép A,
deterministic và caller opt-out không gọi A),3controls M7 natural answer hiện có.
Regression tái hiện trước sửa:1FAIL đúng điểm M7 không được gọi/2PASS; sau sửa6PASS.
Ruff lint/format file sửa, planning checker và diff check được kiểm khi bàn giao.
Không chạy fullsuite/fullCI hoặc trình bày synthetic smoke như financial accuracy.

Evidence local tại `artifacts/evidence/E2E-ARCH-02/live-v2/` (baseline) và
`live-final/` (implementation cuối): requests/responses, trace, Ledger, receipt
runtime/source hashes và audit. `live-v1` lỗi setup runner thiếu thư mục output,
dừng trước HTTP/0API calls; đã sửa setup, không tính thành live financial probe.
Endpoint/key, full trace và dataset không đưa vào Git.

## Giới hạn và bàn giao

Lỗi handoff M7 đã sửa; chưa sửa overplanning, semantic đánh đồng truth/goal support,
task IDs dùng sai vị trí source handles, canonical mapping ADC, date selection
hoặc provider timeout. Không nới verification, tự tạo nguồn hoặc binding.
M7 còn bỏ findings/advisory gap sai ở PY07 nhưng guard đã xử lý; chưa chứng minh
mọi loại multi-hop hoặc Python formula đều chạy thành công;
không suy readiness45Pilot từ một vài câu E2E hay từ engineering PASS.

**Next action:** chờ Owner giao E2E-VAL-01.
