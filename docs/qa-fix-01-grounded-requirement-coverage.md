# QA-Fix-01 — Grounded Requirement Coverage & Safe Financial Explanation

Ngày06/11/2026 (Asia/Bangkok). **DONE**, APPROVED theo quyết định nghiệm thu06/11/2026.
Baseline main/origin `2432bec`; implementation
`310459d137105e8a155fc23c939a64331663dcad` đã push main, origin khớp sau push.
[CI42135935859](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42135935859)
completed/SUCCESS đúng SHA: **1.017Python tests +9Web smoke PASS**;
lint/format/planning/typecheck/build đều SUCCESS, full regression manual SKIPPED.
Checkpoint sau implementation chỉ docs/planning `[skip ci]`, không gán CI cho SHA khác.

## A. Kết quả chính

Đã sửa F01 tại M7: bảo toàn facts, liên kết metric với công thức/toán hạng,
tách nghĩa của chỉ tiêu khỏi giá trị và giữ factual premises khi không có
supported interpretation phù hợp. Không đổi M6 admission hoặc phát sinh phép tính.

Q03 từ partial thành answered: **7,21%**, công thức lợi nhuận gộp/doanh thu thuần
×100%, operands **32.482.519.668 VND / 450.474.531.227 VND**, cùng kỳ2025.
Q08 giữ cả doanh thu **450.474.531.227 VND** và CFO **14.319.681.754 VND**;
vẫn partial, không kết luận chất lượng lợi nhuận tốt. Q02 nhận diện LNST cụ thể;
Q06 giữ hai ratios và nêu thiếu hai nhận định ACCEPT tương ứng.

Phân loại nội dung theo cùng tiêu chí QA-Q01: **2Correct/4PartiallyCorrect/
4abstention-clarification → 3Correct/3PartiallyCorrect/4abstention-clarification**,
0Incorrect được phát hành. Phân loại này là đánh giá mười câu cụ thể, không phải
financial accuracy toàn báo cáo hoặc benchmark Multi-Agent.

Code: `qa_contracts.py`, `qa_composer.py`, `firewall_qa_binding.py`, helper nhỏ
`qa_explanation.py`; thêm regression tests, QA-only capture/audit và CI test entry.
Không cần sửa implementation Citation Renderer hoặc Information Firewall core.

## B. Root cause và bằng chứng trước sửa

`failing-tests.txt`: **13 cases FAIL trước runtime edits**, không thay expected
outputs để che lỗi. `plans-before.json` ghi actual plans cho đủ mười câu.

| Cơ chế cũ | Bằng chứng | Thay đổi tổng quát |
| --- | --- | --- |
| Split “và”/dấu câu làm rơi dependency | Q03 chỉ có metric và một unsupported fragment cho “các số liệu sử dụng” | Follow-up có explicit target, recent metric hoặc unique forward metric; explanation phụ thuộc value requirement |
| Interpretation keywords quá hẹp | Q06 không biểu diễn “nói lên điều gì” thành hai yêu cầu diễn giải | Sentence intent chia cho financial conjuncts, interpretation là obligation riêng |
| Unsafe inference loại factual clause | Q08 bỏ CFO dù Q05 lấy được năm CFO ACCEPT entries | Tách hai factual premises và hai interpretation obligations; thiếu interpretation không loại facts |
| Chỉ render accepted content string | Q03 có trace trong final ACCEPT nhưng chỉ hiển thị tỷ lệ | Project typed calculation trong admitted claim thành protected explanation |
| Alias QA ngắn thiếu | Q02 không map “lợi nhuận sau thuế” | Alias trỏ vào ID đã có trong catalog, retrieval vẫn chỉ lấy ACCEPT |

Điều chỉnh kết luận chẩn đoán cũ: `b02.profit_after_tax` **đã tồn tại trong
ITEM_CATALOG**. Thiếu alias QA ngắn và standalone ACCEPT trong saved BBS ledger;
không phải cần phê duyệt metric/catalog item mới. Không tự sửa QA-Q01 evidence.
Test mới kiểm tra alias này không cấm một fact ACCEPT có target tương ứng.

Q03 đủ dữ liệu ngay trong `final.original_claim.calculation`, gồm trace policy,
approval/digest, operand values/context, `evidence.operands` và citations.
Không lấy thêm thông tin từ `history.contexts`, external saved proof hoặc lineage
ngoài admitted calculation. Q08 dùng existing direct CFO claims; không promote
metric operand. Q01 vẫn abstain dù assets xuất hiện trong debt/assets calculation.

## C. Contract và boundary

`QARequirement` giữ các trường cũ, thêm `aspect=value|formula|operands`,
`depends_on`, `interpretation_topic` và kind `explanation`. Giá trị và diễn giải
là requirements riêng; explanation chỉ có coverage khi parent value đã chọn
được claim và chính claim đó đủ admitted metadata. Nhiều metric nhưng không xác
định được explanation thuộc target nào thì giữ ambiguity, không tự chọn metric.

`request_inventory(original_request, admitted_entries)` là policy chung. Composer
gọi để lập kế hoạch; Firewall gọi lại từ original trusted request + read-only
ledger retrieval. Không tin plan, status hoặc validation flag do Composer đưa vào.
Giữ AND filters, annual/as-of periods, scope resolution, snapshot binding,
cross-document D03-B10 và maximum12claims. Broad questions thiếu targets vẫn clarify.

`GroundedSegment.explanation` chứa metric identity/formula version/digest,
verified result/unit, approved expression và typed operands có exact citations.
Formatter chỉ đổi role thành approved catalog label; không tính lại result,
không đổi rounding, unit, scale, period hoặc scope. Operands giữ numeric strings
nguyên trạng, hiển thị riêng hệ số đơn vị; không âm thầm chuyển sang đơn vị khác.

Explanation gate đối chiếu trace với typed operand facts/context/observation,
source-fact binding, admitted citations và existing approved policy validator.
Thiếu trace/operand/citation/approval thì giữ value và đánh dấu explanation partial.
Không sử dụng rejected/pending authority hoặc gọi calculator/retrieval fallback.

Explanation text nằm trong chính protected segment, có typed projection song
song. Local validator tái dựng toàn bộ slot từ ledger và requirement coverage;
Firewall kiểm lại slot cùng original request. Renderer gắn markers ở cuối toàn
segment, giữ exact selectors và mọi citation limitations. Per-operand source
bindings cũng nằm trong typed explanation/source fingerprint; không dựng citation
từ label hoặc số trang đoán được. Không nâng page-level provenance thành cell.

Interpretation chỉ chọn `supported_interpretation` ACCEPT đúng target/context;
earnings-quality topic còn phải khớp nội dung đã được ACCEPT. Verdict không có
bounded context như “an toàn/tốt hay xấu” tiếp tục thiếu hỗ trợ. Không dùng một
numeric ACCEPT hoặc CFO dương làm nhận định tổng thể. Gemini chỉ có quyền sắp
xếp protected slots như trước, không viết explanation tự do.

Semantic delta: QA có thêm metadata optional, dependent explanations và explicit
missing-interpretation coverage; nhãn requirement chưa đáp ứng được bổ sung tên
catalog/reason có giới hạn. Legacy requirement không có target/reason vẫn giữ
cách hiển thị ID cũ. Không sửa frozen M7 oracles hoặc existing test assertions.

## D. Mười câu BBS trước/sau

Actual production repository → Composer → Renderer → Firewall, zero external
calls. `final/` là capture cuối; lượt điều tra đầu được giữ riêng tại root evidence.
Sau correction alias LNST và legacy label, audit tái kiểm original bindings/slots
bằng final code + real admitted ledger cho cả mười outputs; không ghi đè captures.

| ID | Trước sửa | Sau sửa | Financial correctness | Requirement coverage | Firewall |
| --- | --- | --- | --- | --- | --- |
| Q01 | abstained | abstained | Không promote assets operand | Thiếu standalone assets ACCEPT | ALLOW safe refusal |
| Q02 | partial, LNST ambiguous | partial, LNST rõ target | Doanh thu450.474.531.227VND đúng | Revenue có; LNST thiếu ACCEPT | ALLOW_WITH_CAVEAT |
| Q03 | partial, chỉ7,21% | answered, formula+2operands | 7,21%; operands khớp PDF7 |3/3obligations đáp ứng | ALLOW_WITH_CAVEAT |
| Q04 | answered | answered | Debt/assets59,06%, total liabilities | Value giữ nguyên | ALLOW_WITH_CAVEAT |
| Q05 | answered | answered | CFO14.319.681.754VND đúng | Direct fact giữ nguyên | ALLOW_WITH_CAVEAT |
| Q06 | partial, ratios + unsupported fragment | partial, ratios +2missing interpretations |7,21% và59,06% giữ nguyên |2values có,2interpretations thiếu | ALLOW_WITH_CAVEAT |
| Q07 | clarification_required | clarification_required | Không tự chọn nhóm analysis | Broad domains cần targets cụ thể | CLARIFICATION_REQUIRED |
| Q08 | partial, chỉ revenue | partial, revenue+CFO | Hai facts đúng; không verdict mới |2facts có,2interpretations thiếu | ALLOW_WITH_CAVEAT |
| Q09 | unsupported | unsupported | Không tính quick ratio | Formula chưa approved | ALLOW safe refusal |
| Q10 | unsupported | unsupported | Không so sánh liên tài liệu | D03-B10 giữ nguyên | ALLOW safe refusal |

Selected entries Q01–Q10: **0/5/7/2/5/9/0/10/0/0**; 19uniqueIDs toàn bộ,
đều có saved final ACCEPT. Q03:2segments/13exact reference selectors;
Q08:3segments/21selectors (nhiều selectors không đồng nghĩa nhiều nguồn độc lập).
Không drop equivalent IDs/caveats hoặc dedup prose khác wording trong task này.

Các trích đoạn dưới đây nguyên văn phần tài chính/status từ actual Composer
answers. Renderer nối exact citation markers; **toàn bộ released final answers
trước/sau**, gồm mọi caveat và locator, có tại local
`artifacts/evidence/QA-Fix-01/before-after-verbatim.md` và per-case final files.

Q02 trước:

> Các yêu cầu chưa đáp ứng: r2.

Q02 sau:

> Các yêu cầu chưa đáp ứng: r2 (17. Lợi nhuận sau thuế thu nhập doanh nghiệp: chưa có claim ACCEPT).

Q03 trước:

> Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 đạt 7,21%.
>
> Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 là 7,21%.
>
> Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.
>
> Các yêu cầu chưa đáp ứng: r2.

Q03 sau (segment thứ nhất; segment wording tương đương vẫn được giữ):

```text
Kỳ 2025 — Biên lợi nhuận gộp kỳ 2025 đạt 7,21%.
Công thức: (5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ / 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ) × 100%.
Số liệu sử dụng trong phép tính đã xác minh:
- 5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ (gross_profit): 32482519668 VND; hệ số đơn vị 1; kỳ 2025.
- 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ (revenue): 450474531227 VND; hệ số đơn vị 1; kỳ 2025.
```

Q06 trước:

> Kỳ 2025-12-31 — Tỷ lệ nợ phải trả trên tổng tài sản tại ngày 2025-12-31 là 59,06%.
>
> Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.
>
> Các yêu cầu chưa đáp ứng: r3.

Q06 sau (hai gross-margin strings và debt/assets vẫn giữ như trước):

> Các yêu cầu chưa đáp ứng: r3 (nhận định về Biên lợi nhuận gộp: chưa có nhận định ACCEPT phù hợp), r4 (nhận định về Tỷ lệ nợ phải trả trên tổng tài sản: chưa có nhận định ACCEPT phù hợp).

Q08 trước:

> Kỳ 2025 — Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.
>
> Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.
>
> Các yêu cầu chưa đáp ứng: r2.

Q08 sau:

> Kỳ 2025 — Doanh thu thuần kỳ 2025 là 450.474.531.227 VND.
>
> Kỳ 2025 — Lưu chuyển tiền thuần từ hoạt động kinh doanh của kỳ 2025 là 14.319.681.754 VND.
>
> Kỳ 2025 — Lưu chuyển tiền thuần từ hoạt động kinh doanh kỳ 2025 là 14.319.681.754 VND.
>
> Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.
>
> Các yêu cầu chưa đáp ứng: r3 (nhận định về 3. Doanh thu thuần về bán hàng và cung cấp dịch vụ: chưa có nhận định ACCEPT phù hợp), r4 (nhận định về Lưu chuyển tiền thuần từ hoạt động kinh doanh: chưa có nhận định ACCEPT phù hợp).

Independent references lấy từ visual PDF readings QA-Q01, tách khỏi ledger proof.
Đã đọc lại renders PDF7 và8: gross profit/revenue ở cột2025, B02-DN đơn vịVND;
CFO ở dòng20/cột2025 B03-DN. Hai operands mới được công bố khớp số nhìn thấy.
Debt/assets59,06% và các financial assertions cũ giữ exact admitted strings/proofs.
Không lấy frozen oracle làm ground truth; không OCR, tính ratio mới hoặc admission mới.

## E. Validation và integrity

- Before:13failing regressions, actual plans trước runtime edits.
- New suite:40cases, gồm13generalized plan cases, broad/ambiguous dependency,
  LNST catalog matching,3approved formulas/các năm khác nhau, thiếu metadata,
  operand-only fact refusal, no-calculator, rejected authority và14attacks.
- Compatibility/boundary:211M7-01/M7-04/M7-05/M6ledger/candidate cases;
  planning checker tests3cases. **Final combined254PASS/0FAIL** (138,04s);
  gồm40new +211compatibility/boundary +3planning. Không sửa expected assertions cũ.
- Attacks đổi result, numerator, denominator, formula, unit, scale, period,
  snapshot, citation, explanation prose, original question, coverage,
  unsupported interpretation và caveat. Dù re-render/forge local flag, Firewall
  vẫn BLOCK; snapshot còn bị Renderer từ chối trước gate.
- Một compatibility failure do legacy unanswered label đã được sửa trong code;
  existing test giữ nguyên. Không đổi accepted oracles/expected financial values.
- Ruff lint toàn repository PASS; Ruff format các file Python đã sửa PASS;
  planning103tasks/diff PASS. Whole-tree format local còn lỗi CRLF code fence
  có sẵn tại `docs/m7-05-information-firewall.md`; không sửa accepted document.
  CI Linux kiểm lại format toàn repo theo workflow hiện hành.
- Protected **16.849files unchanged, added0**, ngoài bốn authorized M7 runtime
  source files. Giữ data/raw/processed/canonical, accepted M6/M7/QA-Q01 evidence,
  configs/prompts/evaluation/frozen oracles và local `web/next-env.d.ts`.
- Không local frontend build/full regression; CI hiện hành chạy focused Python
  và Web smoke do thay đổi `src`. Không gọi Gemini/M5/OCR/extraction;0paid switch.
- CI42135935859 đã xác minh completed/SUCCESS đúng implementation SHA:
  1.017focused Python PASS (251,35s),9browser smoke PASS (7,2s);
  cả Python3.12/Web smoke jobs SUCCESS, full regression manual SKIPPED.

Engineering PASS chỉ chứng minh boundaries/pipeline. Mười BBS outputs là bounded
real-source QA, không chứng minh accuracy toàn PDF hoặc lợi ích fresh Multi-Agent.

## F. Giới hạn còn lại

Q01 thiếu standalone assets; Q02 thiếu LNST ACCEPT dù PDF có số. Q06/Q08 chưa có
supported interpretation phù hợp. Không thêm quick-ratio formula hoặc bypass
D03-B10. Broad-domain policy và M5/provider503 không được sửa tại đây.
Unknown separate/consolidated scope, page-level uncertain provenance, warnings
lịch sử và lặp text/citations giữ nguyên. Không giải quyết latency deserialize
ledger (QA-Fix-04) hoặc compact presentation (QA-Fix-05).

Parser deterministic có vocabulary hữu hạn; không tuyên bố bao phủ mọi câu tiếng
Việt. Không có đủ semantic context thì giữ missing/unsupported/clarification.
Explanation yêu cầu đủ approved formula+operand evidence; chỉ có result thì partial.

## G. Bàn giao

Không còn P0/P1 đã xác định trong phạm vi F01 sau các controls/audit nêu trên;
implementation SHA/CI đã xác minh. F02/F03 thuộc backlog riêng vẫn còn nguyên.
QA-Fix-02 chưa được đăng ký/giao/READY trong task này; fresh M5 cần spec/budget riêng.

Phiên chuyển DONE chỉ cập nhật docs/planning và chạy planning/diff checks;
không chạy lại QA/tests/Gemini/OCR/extraction hoặc sửa accepted evidence/Web local.
Giữ nguyên kết quả và các limitations nêu trên.

**Next action duy nhất: chờ Owner/Tech Lead giao task tiếp theo;
không tự bắt đầu QA-Fix-02.**

Appendix local ignored: `hashes-before.json`, `integrity.json`,
`plans-before.json`, `failing-tests.txt`, `validation-complete.txt`,
`lnst-target-test.txt`, `before-after-audit.json`, `before-after-verbatim.md`,
`ci-result.json`, `ci-log.txt`, `execution-metadata.json`,
`final/m7-summary.json`, `final/m7-Q01..Q10-{request,composer,rendered,firewall}.json`,
`final/m7-Q01..Q10-final.txt`. Full claim IDs/formula digests/locators ở các JSON;
không commit source datasets, ledger proofs hoặc financial trace artifacts.
