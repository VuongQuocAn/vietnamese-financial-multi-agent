# FIX-02-ACCEPT — Final Live Acceptance

## Khôi phục adapter — kết quả hiện tại

Owner phê duyệt đúng một lượt sửa bổ sung ngày 10/11/2026: bỏ toàn bộ Pydantic
schema khỏi generation API, smoke L01 trước rồi mới chạy manifest10ca. Đã làm đúng
trình tự trên implementation `513ba5751c4e28254f8f7091c4890057e398e773`, đã push main.
Chỉ runtime `src/api/qa_gateway.py` thay đổi so với `93d5829`; giữ mọi cải tiến
downstream, typed validation/DAG và M6/Firewall. Test mới yêu cầu JSON MIME, không
gửi `response_json_schema` hoặc `response_schema`. Không nghiên cứu schema tối ưu.

**Hồi quy HTTP400 đã được khắc phục; FIX-02 vẫn BLOCKED, chưa đủ điều kiện DONE.**
Planner smoke L01: một call Gemini thật,6.600tokens,6,691giây,planned và DAG hợp lệ/
execution eligible. Chỉ sau smoke này mới chạy lại nguyên manifest10ca/11lượt trên
source Git đã đóng băng đúng `513ba57`; không đổi câu hỏi, oracle hoặc chọn lại ca.

| Ca | Đánh giá nội dung cuối | Bằng chứng chính |
| --- | --- | --- |
| L01 | CORRECT_WITH_CAVEAT | BCC assets3.275.086.920.922VND, đúng PDF5. |
| L02 | CORRECT_WITH_CAVEAT | BCC gross margin10,01%, đủ công thức/operands, đúng PDF7. |
| L03 | CORRECT_WITH_CAVEAT | CFO−PAT7.070.123.808VND, đủ hai số nguồn;5ACCEPT. M7partial vì thêm mục tiêu diễn giải ngoài câu hỏi, không vì phép tính thiếu. |
| L04/Q21 | PARTIAL | Hai facts, chênh lệch và greater(CFO,PAT) đã phát hành;5ACCEPT/1ABSTAIN, chưa có đánh giá chất lượng lợi nhuận đáp ứng yêu cầu. |
| L05/Q23 | UNJUSTIFIED_ABSTAIN | 6ACCEPT nhưng final chỉ yêu cầu làm rõ; Firewall CLARIFICATION_REQUIRED, không phát hành các phần độc lập đã xác minh. |
| L06 | CORRECT_WITH_CAVEAT | So sánh hai kỳ cùng filing: PAT tăng1.059.972.358VND,17,13%;3ACCEPT, đã live xác nhận sửa multi-period. |
| L07 | CORRECT_WITH_CAVEAT | Đủ doanh thu/PAT/CFO và nguồn;3ACCEPT/1INVESTIGATE, nhánh không hợp lệ không bị promote. |
| L08 | PARTIAL | Ratio59,06%, công thức/operands đúng;2ACCEPT/1INVESTIGATE. Diễn giải per100 đã ACCEPT nhưng không được M7 chọn. |
| L09/MH03 | PARTIAL | Chênh lệch417.992.011.559VND đúng và có nguồn; thiếu lời giải thích được hỏi về tính chất đối chiếu không chuẩn. Không gán kết quả tốt hơn của vòng1 cho câu trả lời mới này. |
| L10 | RUNTIME_FAILURE | Lượt1 doanh thu đúng; lượt2 kế thừa đúng context nhưng Planner trả JSON lỗi cú pháp,structured_output_invalid. |

Tổng **5/10 CORRECT_WITH_CAVEAT,3PARTIAL,1UNJUSTIFIED_ABSTAIN,1RUNTIME_FAILURE**.
Không thấy sai số liệu/phép tính/citation trong các phần đã phát hành và đối chiếu;
không dùng số ACCEPT hay statusPARTIAL để thay đánh giá nội dung. Chưa đạt8/10 và
còn các lỗi P1 có bằng chứng, nên không chuyển DONE/CONDITIONAL DONE.

### Những lỗi còn lại có bằng chứng cụ thể

- **P1 Q21:** candidate `candidate:aa43b5f583f9eccf048a025d` ABSTAIN vì
  `required_semantic_assessment_unavailable`. Provider response023 của Evidence
  Critic có assertionsA3/A6 là supported nhưng evidence_ids rỗng; Logic Critic không
  được gọi cho claim này. Phép tính hợp lệ vẫn giữ, phần đánh giá yêu cầu chưa đạt.
- **P1 Q23:** round0 có6ACCEPT; revision sau thất bại với
  `revision_adds_unrequested_formula`. Final chuyển clarification dù binding
  document/snapshot đã có; cần bảo toàn last-valid goals và các nhánh ACCEPT khi
  revision không thực thi được, giữ nguyên gate cho formula không hợp lệ.
- **P1 L08:** per100 interpretation `candidate:7de43e82479771b140b3f4c9` đã ACCEPT
  nhưng không phủ goal required_indicators. Supporting evidence là metric; trong
  `matches_financial_target`, operands chỉ được đưa vào indicator set cho kind
  approved_metric. Cần đối chiếu coverage của metric-backed interpretations với
  proof đã được chấp nhận, không phê duyệt lại bằng M7.
- **L10 protocol failure:** response050 finishSTOP nhưng JSON có `- inputs"` trong
  reasoning_steps. Context kế thừa đủ company/document/snapshot/period; không
  gọi đây là mất ngữ cảnh. Prefix recovery không phục hồi được object đủ typed
  fields, nên chưa kiểm chứng được answer YoY ở lượt2. Không retry vì muốn output đẹp.
- L09 thiếu qualification được hỏi; các caveats dài/lặp còn lại không tự mở thành
  công việc thẩm mỹ. Không dùng lượt sửa adapter để triển khai thêm các thay đổi này.

### Usage, source audit và checks của lượt bổ sung

Full manifest:50actual attempts,281.216known tokens/7unknown usage;7HTTP503 được
ghi nhận theo retry/backoff hiện hữu,0HTTP400; một response malformed JSON.
Tổng latency11lượt658,661giây, loại startup. Cộng smoke:51attempts,
287.816known tokens/7unknown. Cùng gemini-3.5-flash-lite, không đổi key/model.
Đây là quick acceptance, không M8 hoặc financial accuracy benchmark.

Đã đọc lại sáu trang scan nguồn liên quan và đối chiếu số liệu/phép tính độc lập
ở phần audit lịch sử:141display-reference occurrences thuộc đúng PDF/trang,
0wrong-source trong kiểm tra này. `integrity.json` xác nhận imported runtime đúng
SHA,578protected files không đổi trong lượt;414original inputs/reference,manifest
và12local files ngoài task giữ hash trước khi cập nhật planning. Source caveats
page-level/BBS scope unresolved vẫn nguyên, không nâng thành cell-level certainty.

Local:5targeted tests PASS; Ruff lint/format và diff check PASS. Không chạy lại
full offline suite. [CI42810151159](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42810151159)
SUCCESS đúng513ba57:145Python/9Web,lint/format/planning/typecheck/build đạt;
không dùng CI thay quality acceptance. Planning sẽ được kiểm cả working tree và
index riêng để giữ local changes ngoài task không vào commit.

Artifacts local, không commit dữ liệu riêng tư:
`artifacts/evidence/FIX-02/final-acceptance/emergency-smoke/summary.json`;
`emergency-acceptance/results.json`, `assessment.json`, `audit-summary.json`,
`provider/`, `ledger/`, `Lxx-turnN-answer.txt`, `integrity.json` cùng thư mục gốc;
CI receipt tại `ci-513ba57.json`. Giữ toàn bộ failures và original/resolved turns.

**Next action duy nhất:** Tech Lead quyết định phạm vi remediation các P1 đã có
trace trên `513ba57`; adapter HTTP400 không còn là blocker. Không tự mở task mới,
thêm kiến trúc hoặc vòng sửa khác ngoài lượt adapter được phê duyệt.

---

## Hồ sơ nghiệm thu trước khôi phục adapter

Các phần dưới giữ lịch sử tới checkpoint629eb08. “Bản cuối” trong hồ sơ này là
vòng2 `93d5829`, không phải implementation hiện tại `513ba57` nêu ở trên.
Next action cũ về adapter đã được chỉ đạo bổ sung của Owner thay thế.

Ngày 10/11/2026, Asia/Bangkok. **Kết luận: BLOCKED, chưa đề xuất DONE.**
Đã chạy đủ 10 ca/11 lượt trên baseline và sau mỗi vòng sửa, tổng cộng hai vòng
corrective implementation. Bản cuối gây hồi quy tích hợp: 10 request Planner
nhận HTTP 400 `invalid_request`; lượt tiếp nối L10 phải hỏi làm rõ vì lượt đầu
không có kết quả. Không có câu trả lời tài chính được phát hành trên bản cuối.
**`93d5829` không phải checkpoint demo Gemini QA chạy được.**

## SHA và phạm vi

| Vai trò | SHA |
| --- | --- |
| Baseline implementation | `af4eae958bdb72f1449d606e15beeadb22be5c4f` |
| Checkpoint lúc nhận việc | `e11fa52` |
| Corrective implementation 1 | `066032a10b9675fcfff977c865fc117f6aa9f147` |
| Corrective implementation 2, cuối | `93d58299478a6ec884d243aab217c50a8ffeae1a` |

Cả hai implementation đã commit/push trực tiếp `main` theo chỉ đạo. Mỗi lượt live
import source bằng `git archive` đúng SHA; không dùng các module đang sửa local.
Giữ pipeline M5 → Tools → M6 → Ledger → M7 → Firewall; mọi provider request qua
Gateway, cùng `gemini-3.5-flash-lite`, không mock/recorded response thay live.
Không extraction/OCR/recovery mới, không sửa canonical facts, approvals, source
policy hoặc oracle; không M8, Web implementation hay agent/framework mới.

## Manifest cố định và nguồn

Manifest local: `artifacts/evidence/FIX-02/final-acceptance/manifest.json` được
ghi trước provider call đầu tiên, giữ nguyên qua ba lượt. Catalog document/fact
và snapshot binding của mỗi lượt được ghi trước khi gọi provider.

- L01–L02: BCC 2025, báo cáo riêng, PDF gốc `BCC_2025.pdf`, snapshot
  `a49f826f-8e45-49c1-9e40-95f44e467e46`; đối chiếu trang PDF 5 và 7.
- L03–L10: BBS 2025, PDF gốc `BBS_2025.pdf`, snapshot `D-01/normalized-v2`;
  B01 trang PDF 5–6, B02 trang 7, B03 trang 8. Scope BBS chưa được xác nhận;
  không gán riêng/hợp nhất. Các kỳ 2024 lấy cột so sánh trong filing 2025.
- SHA-256 PDF, document IDs và source-reference IDs nằm trong manifest/catalog
  local. `E2E-02/reference.json` được giữ nguyên hash; không thay oracle sau output.

| ID | Câu hỏi nguyên văn | Reasoning/điều kiện cần kiểm chứng |
| --- | --- | --- |
| L01 / Q03 | Tổng tài sản BCC tại ngày 31/12/2025 trên báo cáo riêng là bao nhiêu? | Direct fact; đúng scope, ngày, đơn vị và PDF 5. |
| L02 / Q14 | Biên lợi nhuận gộp BCC 2025 trên báo cáo riêng là bao nhiêu? | Công thức, hai operands, Decimal, PDF 7. |
| L03 | Tính chênh lệch giữa dòng tiền thuần từ hoạt động kinh doanh và lợi nhuận sau thuế BBS năm 2025 bằng VND; dẫn nguồn hai số liệu. | CFO − PAT ad hoc; đúng hai nguồn, không cần formula registry. |
| L04 / Q21 | Đánh giá chất lượng lợi nhuận BBS 2025 qua lợi nhuận sau thuế và dòng tiền thuần từ hoạt động kinh doanh; dẫn số liệu và giới hạn kết luận. | Thực sự diễn giải quan hệ PAT/CFO; không chỉ liệt kê facts, không kết luận toàn diện. |
| L05 / Q23 | Doanh thu thuần BBS 2025 tăng nhưng lợi nhuận gộp giảm so với 2024: các số liệu cho thấy điều gì? Không suy đoán nguyên nhân. | Kiểm tra tiền đề qua hai kỳ; diễn giải biên thu hẹp, không bịa nguyên nhân. |
| L06 / Q20 | So sánh lợi nhuận sau thuế BBS 2025 với năm 2024 theo báo cáo năm 2025. | Hai kỳ cùng filing, phép đối chiếu có nguồn. |
| L07 | Cho biết doanh thu thuần, lợi nhuận sau thuế và dòng tiền thuần từ hoạt động kinh doanh của BBS năm 2025; dẫn nguồn cho từng chỉ tiêu. | Đủ ba facts độc lập, không làm mất nhánh hợp lệ. |
| L08 | Đánh giá mức độ sử dụng nợ của BBS cuối năm 2025 qua tỷ lệ nợ phải trả trên tổng tài sản; nêu số liệu, phép tính và giới hạn kết luận. | Debt/assets và diễn giải có giới hạn; không suy ra mất khả năng thanh toán. |
| L09 / MH03 | Tính chênh lệch doanh thu thuần và lợi nhuận gộp BBS 2025 bằng VND; dẫn nguồn và giải thích đây là phép đối chiếu, không phải chỉ tiêu kế toán chuẩn. | Dynamic subtraction và giới hạn ad hoc, phục hồi đường từng bị preflight chặn. |
| L10, lượt 1 / Q29 | Doanh thu BBS năm 2025 là bao nhiêu? | Thiết lập context từ kết quả có nguồn. |
| L10, lượt 2 / Q30 | So với năm trước thì sao? | Kế thừa BBS/filing 2025, so với cột 2024, không đổi tài liệu. |

Q21/Q23/MH03 giữ nguyên câu chữ và định danh gốc. L10 tính là một ca; cả hai lượt
được lưu riêng trong trace, không lấy lịch sử synthetic hoặc answer recorded làm input.

## Đánh giá nội dung trước/sau sửa

Đánh giá từ câu trả lời tiếng Việt cuối cùng, bản scan và phép tính độc lập;
không suy từ `completed`, số claims ACCEPT hay Judge PASS.

| Ca | Baseline | Vòng 1 | Bản cuối |
| --- | --- | --- | --- |
| L01 | CORRECT_WITH_CAVEAT | CORRECT_WITH_CAVEAT | RUNTIME_FAILURE |
| L02 | CORRECT_WITH_CAVEAT | CORRECT_WITH_CAVEAT | RUNTIME_FAILURE |
| L03 | UNJUSTIFIED_ABSTAIN | UNJUSTIFIED_ABSTAIN | RUNTIME_FAILURE |
| L04 | UNJUSTIFIED_ABSTAIN | PARTIAL | RUNTIME_FAILURE |
| L05 | UNJUSTIFIED_ABSTAIN | UNJUSTIFIED_ABSTAIN | RUNTIME_FAILURE |
| L06 | UNJUSTIFIED_ABSTAIN | RUNTIME_FAILURE | RUNTIME_FAILURE |
| L07 | CORRECT_WITH_CAVEAT | CORRECT_WITH_CAVEAT | RUNTIME_FAILURE |
| L08 | RUNTIME_FAILURE | PARTIAL | RUNTIME_FAILURE |
| L09 | PARTIAL | CORRECT_WITH_CAVEAT | RUNTIME_FAILURE |
| L10 | RUNTIME_FAILURE | RUNTIME_FAILURE | RUNTIME_FAILURE |
| Đạt CORRECT hoặc CORRECT_WITH_CAVEAT | **3/10** | **4/10** | **0/10** |

- L01 đúng 3.275.086.920.922 VND và PDF 5. L02 đúng 10,01%, công thức và cả
  hai operands. Baseline L02 bị status PARTIAL do tự thêm yêu cầu diễn giải;
  nội dung vẫn đáp ứng câu hỏi chỉ hỏi giá trị.
- L07 có đủ doanh thu 450.474.531.227, PAT 7.249.557.946 và CFO
  14.319.681.754 VND với nguồn. Baseline thêm obligation về nguồn không cần thiết;
  không vì vậy hạ chất lượng ba facts đã trả đúng.
- Vòng 1 L04 giữ hai facts và phép tính CFO−PAT, CFO/PAT. Tuy nhiên chưa phát
  hành phần diễn giải chất lượng lợi nhuận: PARTIAL, không gọi là CORRECT chỉ vì
  có 4 ACCEPT. L08 cũng chỉ phát hành ratio/operands, chưa diễn giải yêu cầu.
- Vòng 1 L09 trả đúng 417.992.011.559,00 VND và nêu phép tính ad hoc không tự
  trở thành chỉ tiêu kế toán chuẩn. Status PARTIAL vì còn obligation diễn giải
  thừa; nội dung cốt lõi của câu hỏi đã được trả lời với giới hạn hợp lý.
- L10 baseline/vòng 1 trả đúng lượt đầu nhưng lỗi lượt hai. Trên bản cuối, lượt
  đầu HTTP 400, lượt hai clarification do không có context thành công; không coi
  clarification đó là bằng chứng multi-turn PASS hoặc một lỗi mới của resolver.
- Không thấy số liệu/phép tính sai được phát hành trong các phần đã audit của
  baseline/vòng 1. Bản cuối không phát hành số liệu nào; điều này **không** chứng
  minh chất lượng tài chính hoặc đạt yêu cầu bắt buộc.

## Execution trace, reasoning và verification

Artifact gốc, gồm cả failures, được giữ riêng theo lượt:

- Baseline: `artifacts/evidence/FIX-02/final-acceptance/baseline/results.json`.
- Vòng 1: `artifacts/evidence/FIX-02/final-acceptance/correction-1/results.json`.
- Bản cuối: `artifacts/evidence/FIX-02/final-acceptance/correction-2/results.json`.

Trong mỗi `results.json`: original question; conversation original/resolved context;
`financial_execution.planner_result` raw/effective proposal; assignments;
Supervisor/Router projections; Specialist outputs; tool requests/results và evidence;
public reasoning operations, Decimal proof; `adaptive_rounds` có Critic/M6/Judge
feedback/revisions; candidate outcomes; M7 requirements/coverage và Firewall.
Đây là public execution reasoning, không phải chain-of-thought nội bộ của model.
`provider/*.request.json` và `*.response.json` lưu từng actual attempt; Ledger của
mỗi lượt là `ledger/verified-claims.json`. Các file `Lxx-turnN-answer.txt` giữ nguyên
toàn bộ câu trả lời tiếng Việt, gồm nguồn, để Tech Lead đọc trực tiếp.

Các điểm kiểm chứng nổi bật ở vòng 1:

| Ca | Native M6 outcome cuối | M7 / Firewall và reasoning thực tế |
| --- | --- | --- |
| L01 | 1 ACCEPT | Answered, ALLOW_WITH_CAVEAT; assets fact. |
| L02 | 1 ACCEPT | Answered, ALLOW_WITH_CAVEAT; gross margin được replay. |
| L03 | Chưa đến M6 | Planner JSON lỗi ở đầu output, không thể phục hồi prefix an toàn. |
| L04 | 4 ACCEPT / 1 ABSTAIN | Partial, ALLOW_WITH_CAVEAT; giữ facts và hai arithmetic proofs; semantic assessment chưa hợp lệ/đủ cho analysis. |
| L05 | Chưa đến M6 | Planner gộp hai operand years vào filing years; D03-B10 chặn. |
| L06 | Chưa đến M6 | Router đã giao đủ hai kỳ; Orchestrator assignment gate còn bắt cùng kỳ, làm Specialist execution fail. |
| L07 | 4 ACCEPT / 2 INVESTIGATE | Answered, ALLOW_WITH_CAVEAT; ba facts được giữ, analysis thừa không được promote. |
| L08 | 1 ACCEPT / 1 INVESTIGATE | Partial, ALLOW_WITH_CAVEAT; metric đúng, arithmetic paraphrase thiếu binding mà validator nhận diện. |
| L09 | 3 ACCEPT / 1 INVESTIGATE | Partial, ALLOW_WITH_CAVEAT; subtraction đã được M6 kiểm chứng/phát hành. |
| L10 | Lượt 1: 1 ACCEPT; lượt 2 chưa đến M6 | Lượt 1 answered/ALLOW_WITH_CAVEAT; lượt 2 `operation_period_not_requested`. |

Judge đã thực sự gọi provider và tạo feedback/revisions trong các nhánh phân tích;
Q21 có cả REVISION_NEEDED và PASS nhưng analysis vẫn không được native M6 chấp
nhận. Không dùng Judge PASS để lách M6. Ledger baseline có 7 entries; vòng 1 có
11 entries. Các nhánh derived được kiểm chứng vẫn tồn tại khi analysis bị ABSTAIN.
Trên `93d5829`, **Tools, M6, Judge, Ledger admission, M7 và Firewall không được
thực thi cho 10 request Planner thất bại**; không gán kết quả vòng 1 cho SHA này.

## Decimal và source audit độc lập

Đã render PDF gốc bằng PDFium sẵn có và đọc đầy đủ sáu trang liên quan:
BBS PDF 5–8 và BCC PDF 5,7; Poppler không có trong PATH. Giữ heading, năm,
đơn vị VND và hai cột kỳ. Không thay canonical values theo kết quả QA.
Audit local: `artifacts/evidence/FIX-02/final-acceptance/pdf-audit/independent-audit.json`
ghi hash render và phép tính Decimal34 độc lập:

| Phép đối chiếu | Kết quả độc lập |
| --- | --- |
| BCC gross margin | 369.838.783.346 / 3.696.241.245.507 × 100 = 10,005807…%, hiển thị 10,01% |
| BBS CFO − PAT | 14.319.681.754 − 7.249.557.946 = 7.070.123.808 VND |
| BBS CFO / PAT | 1,975248… lần, hiển thị 1,98 lần; ad hoc, không metric chuẩn |
| Revenue 2025 so với 2024 | +26,713133…% |
| Gross profit 2025 so với 2024 | −10,841694…%; gross margin 10,248004…% → 7,210733…% |
| PAT 2025 so với 2024 | +1.059.972.358 VND, tương đương +17,125094…% |
| BBS debt/assets cuối năm | 157.146.559.558 / 266.086.680.765 × 100 = 59,058408…% |
| BBS revenue − gross profit | 417.992.011.559 VND |

Final audit: `artifacts/evidence/FIX-02/final-acceptance/final-audit.json`:
65 display-reference occurrences baseline và 108 ở vòng 1 đều thuộc đúng PDF và
các trang đã đọc. Bản cuối có 0 citations. Kiểm tra page-level này không nâng
anchors uncertain thành cell-level hoặc chứng nhận toàn bộ PDF/dataset.
Renderer vòng 1 đã bỏ các status kỹ thuật `usable/insufficient` và raw document
UUID khỏi nhãn nguồn; giữ identifiers/provenance trong typed trace. Caveats còn
dài/lặp và một số không cần cho câu hỏi; không tự sửa thẩm mỹ ngoài phạm vi.

## Root causes và hai vòng sửa

Vòng 1 (`066032a`):

- Routing coi “dẫn nguồn” là relation lane, đưa câu tài chính trở lại Mixed QA
  đệ quy và mất mục tiêu phép tính. Giữ financial citation request trong một lane;
  document/causal requirements vẫn phân biệt như trước.
- Planner mất toàn kế hoạch khi optional tail JSON lỗi/cắt. Chỉ phục hồi các
  top-level fields đã decode hoàn chỉnh, không đoán/repair giá trị; vẫn validate
  typed DAG/context đầy đủ. Tăng output budget 3.000 → 6.000 để tránh truncation.
- Router loại comparative operand vì khác filing year. Chỉ cho phép period đã
  bind đúng document/snapshot và được yêu cầu; sai document vẫn bị chặn.
- Normalize high-level planning operations trong coverage, khôi phục metric-value
  goals đơn giản, date “cuối năm” và exact inherited company ID; vệ sinh metadata.

Vòng 2 (`93d5829`):

- Thêm `QAGeminiAdapter` đưa schema Planner vào `response_json_schema`, nhằm chặn
  JSON syntax lỗi ở đầu output. **Đây là thay đổi gây hồi quy live HTTP 400.**
- Sửa Orchestrator cho phép comparative support được bind trong arithmetic proof
  có `across_periods`; company/document/snapshot và native M6 vẫn kiểm độc lập.
- Derived-only candidates dùng backend renderer; khôi phục bound filing year khi
  Planner nhầm operand years; cho phép đúng prior operand của approved YoY metric.
- Gắn kỳ vào registered per-100-assets paraphrase, tách formula/operands khỏi
  interpretation goals; làm rõ assumptions và semantic Critic output contract.
  Dịch caveats mặc định còn thuật ngữ metadata sang tiếng Việt.

Không đổi oracle, không tắt M6/Firewall, không hardcode đáp án test. Các sửa vòng 2
ngoài adapter chỉ có engineering/saved-trace evidence; **chưa được live xác nhận**
vì Planner request bị từ chối trước các tầng này.

## Provider usage và ngân sách

| Lượt | Actual attempts | Known tokens | Attempts usage unknown | Tổng latency 11 lượt, giây |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 55 | 220.942 | 9 | 447,689 |
| Vòng 1 | 41 | 278.618 | 4 | 392,053 |
| Bản cuối | 10 | 0 known | 10 | 66,444 |
| Tổng | **106** | **499.560 known** | **23** | **906,185** |

Không hiểu 0 known là 0 tokens thực tế/miễn phí. Cost không có báo giá đã xác minh,
không tự ước lượng tiền. Latency loại thời gian load catalog/startup; một sample
mỗi case/lượt, không là performance benchmark.

Mỗi lượt có trần 240 actual attempts, mỗi turn 20 logical Gateway calls/300 giây,
bounded Judge/revisions hiện hữu. Transport chỉ retry tối đa một lần, backoff
3 giây, cho HTTP 429/500/502/503/504 hoặc timeout; không đổi câu hỏi, không rotation
key/model. Không retry output vì không đạt mong muốn, không retry HTTP 400.
Số actual attempts khác logical calls trong trace vì transient transport retries.

## Engineering checks và CI đúng SHA

- Vòng 1: 96 distinct focused controls đạt qua các nhóm đã chạy; assertion mới
  về routing causal được sửa sau khi xác nhận quy tắc cũ. Exact committed-runtime
  smoke phục hồi hai captured malformed plans, cho comparative operand và chặn
  wrong document, 0 network.
- Vòng 2: 113 distinct focused controls đạt sau targeted rerun hai failures:
  thiếu `generation` trong test request mới và canonical paraphrase chưa idempotent.
  Saved L06 assignment và L08 numeric-period replay đạt; không phải live evidence.
- Ruff lint/format các files sửa và `git diff --check` đạt. Planning checker chạy
  khi cập nhật bàn giao. Không full offline regression hoặc benchmark M8.
- [Baseline CI42774786427](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42774786427):
  SUCCESS đúng `af4eae9`, đã xác minh.
- [CI42804627083](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42804627083):
  SUCCESS đúng `066032a`, Python 3.12 và Web smoke.
- [CI42806510730](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42806510730):
  SUCCESS đúng `93d5829`, 145 Python/9 Web; lint/format/planning/build/typecheck đạt.
  CI offline **không** phát hiện provider HTTP 400 và không thay thế live acceptance.
  Receipt local: `artifacts/evidence/FIX-02/final-acceptance/ci-93d5829.json`.

## Preservation và giới hạn bàn giao

Cả ba `integrity.json` xác nhận đúng imported runtime, manifest bất biến,
578 selected protected files không đổi trong lượt chạy (164 runtime + 414
inputs/reference). Sau hai vòng, toàn bộ 414 inputs/reference và 12 local files
ngoài task vẫn giữ hash trước khi cập nhật planning; phần planning dùng chung chỉ
thay nội dung FIX-02/counts, giữ các thay đổi local khác ngoài index.
Artifacts có source payload/PDF render/trace chi tiết ở ignored local storage,
không commit/push dữ liệu riêng tư hoặc secrets. Chỉ report, runner, code/tests
FIX-02 và planning hunk của task được stage.

## Blocker và quyết định

**P1 — Gemini Planner generation configuration không chạy trên bản cuối.**
Mười request nhận HTTP 400 sau khi đưa toàn bộ Planner schema vào generation.
Đây là hồi quy tích hợp, không được xem là thiếu dữ liệu thật hay lỗi provider
tạm thời có thể bỏ qua. Adapter chỉ lưu safe error code; message rejection gốc
không được giữ, nên chưa khẳng định chính xác keyword/độ phức tạp schema nào bị
provider từ chối. Không có căn cứ tuyên bố các sửa downstream đã live PASS.

Cách khắc phục cần kiểm chứng: chốt schema generation mà model/API thực sự hỗ
trợ, dùng schema gọn tương thích; nếu phải quay về JSON MIME, giữ phục hồi có
kiểm soát và typed validation nội bộ. Không hạ M6/Firewall, không retry 400 vô hạn.
Sau remediation phải chạy lại manifest trên implementation SHA mới và đọc các
câu trả lời, đặc biệt Q21/Q23, multi-period, leverage và hội thoại tiếp nối.

Đã dùng đủ hai vòng corrective implementation được giao. Dừng sửa/live tại đây.
**FIX-02 BLOCKED:** 0/10 trên bản cuối, dưới ngưỡng 8/10 và còn P1 integration
failure; không đề xuất DONE/CONDITIONAL DONE. Không mở task mới.

**Next action duy nhất:** Tech Lead quyết định remediation cho blocker adapter
JSON Schema trên `93d5829` cùng phạm vi live validation tiếp theo.
