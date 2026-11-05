# M7-04 — Unified Citation Rendering

Owner giao05/11/2026; baseline main/origin
`3c2e9cd5d202f3abddc7437f4ef1db27dc611ba9`, Web local được giữ nguyên.
Status **DONE**, Tech Lead APPROVED ngày05/11/2026; accepted implementation
`731e28c2045b6e4a7d81e96bfeb305d4e1693651` đã push main, HEAD/origin khớp.
[CI41983340107](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41983340107)
completed/SUCCESS đúng SHA:913focused tests và9Web smoke PASS.
Checkpoint sau chỉ docs/planning [skip ci], không gán CI này cho checkpoint SHA.
Tech Lead không yêu cầu sửa runtime hoặc chạy lại evaluation. Phiên nghiệm thu
chỉ cập nhật docs/planning và chạy planning/diff checks; giữ evidence và limitations.

## Kiến trúc và public API

Validated VietnameseQAResponse/GroundedFinancialReport → typed reparse → structural
source/context checks → registry theo exact source → đánh số theo lần xuất hiện
→ markers tại segment/paragraph → danh sách nguồn → locator → rendered view riêng.
Không I/O/model/Gateway/calculator/ledger history trong renderer.

```python
from vietnamese_financial_multi_agent.outputs import (
    CitationRenderer,
    validate_rendered_citations,
)

renderer = CitationRenderer()
cited_qa = renderer.render_qa(qa_response)
cited_report = renderer.render_report(grounded_report)
assert validate_rendered_citations(cited_qa, qa_response).valid
locator = cited_report.references[0].source_locator
```

Caller cung cấp original đã qua validator M7-01/M7-03. Renderer reparse typed input,
kiểm tra validation_result và consistency của presentation/citation projections,
scope document/snapshot, required claim/source bindings. Không thực hiện lại M6
hoặc chứng minh admission từ một object có cờ valid do caller tự gán. Validator
citation đối chiếu với typed original này; thay cả original và rendered view cần
upstream gate/provenance pin của caller để phát hiện. Đây là ranh giới M7-04,
không phải Information Firewall tổng quát M7-05.

Source conflict/invalid source gây ValueError, không trả text có vẻ grounded.
Location thiếu nhưng identity nhất quán được render với location_limited và caveat;
original_status giữ nguyên. Source không có grounded content không sinh số citation.

## Contracts và identity

- CitationReference: stable citation_id, display_number/label, original identity,
  provenance/anchor, source_locator, exact source_citations, limitations và union
  verified claims/output segments.
- CitationBinding: đúng segment/paragraph, claim IDs, citation IDs/numbers, native
  claim contexts và source_slot_ids. Binding paragraph có nhiều claims giữ union
  của paragraph gốc; không tự suy claim → một selector hẹp hơn.
- RenderedCitationOutput: qa/report, input fingerprint, original status,
  rendered/location_limited, text, references/bindings, caveats/limitations và gate.
- CitationLocator: document/snapshot/page/source_ref/source_pointer/image,
  original element/table/cell/line/observed_bbox, provenance/resolution status.
  resource_mapping_status luôn not_provided; không dựng URL hay map tài nguyên.

ID là `citation:` + SHA256 của canonical JSON tuple EvidenceAnchor.source_key():
document, snapshot, PDF page, image, source_ref, element/table/cell/line,
observed_bbox, source_pointer. Không dùng text/value/page đơn lẻ/display number.
Khi reference thiếu hoàn toàn, fallback hash exact citation metadata, loại limitations;
locator location_unavailable, không tạo selector/page. Thiếu document/snapshot bị chặn.

Cùng exact identity tái dùng số cũ, hợp claim IDs/segment IDs/limitation variants;
source_citations giữ từng upstream variant nguyên vẹn. Cùng anchor_id mà khác
source identity bị chặn. Khác selectors trên cùng trang vẫn khác references;
khác snapshots/documents có IDs khác nhau. Metadata locator của cùng exact key
mâu thuẫn cũng fail closed. Display numbers luôn theo lần xuất hiện đầu trong
segment/paragraph order; top-level citation inventory không quyết định numbering.

## Presentation và provenance

Convention duy nhất: `[1][2]` ngay cuối segment/paragraph; `## Nguồn tham chiếu`
ở cuối. Reference có document/snapshot identity đầy đủ, PDF page và caveats.
Không suy tên doanh nghiệp/tên file từ SHA. Không hỗ trợ trusted display-name
mapping ở MVP; full identities luôn giữ trong metadata và reference text.

QA dùng lại deterministic template M7-01 trên detached copy, thêm suffix theo
segment ID, đối chiếu answer gốc trước render. Không text replacement. Report
dựng lại headings/paragraphs theo original order, đối chiếu body_vi gốc trước
render; original body không thay đổi. Partial/unanswered/clarification/abstain,
missing sections và interpretation giữ nguyên. Common annotation tail giữ cả
limitations chỉ có trong metadata; có thể lặp caveat đã hiện trong upstream text.

Page provenance chỉ hiển thị trang, kể cả source_pointer chứa chuỗi `/cells/`.
Chỉ provenance cell cùng table_id/cell_id xác nhận mới hiển thị ô; không dịch
IDs thành tọa độ Excel. Element/line/table giữ identifiers gốc. Locator giữ page
number gốc (không trừ1); chỉ observed_bbox được project, proposed_bbox không được
dùng để highlight. Source uncertain/unresolved hoặc thiếu anchor_id giữ trạng
thái unresolved dù có page. Thiếu reference giữ location_unavailable; source
metadata tự mâu thuẫn bị chặn. Không đổi financial verification authority/status.

## Local validation và controls

validate_rendered_citations reparse output và dựng lại complete expected projection
từ typed source, so mọi field: identity/fingerprint/status/text/reference/locator,
numbering/labels/bindings/claims/contexts/slots/annotations/validation_result.
Không chỉ đếm regex markers. Oracle độc lập bên dưới kiểm tra lại các expected
identities, locator hashes, first-use numbers, binding hashes và exact cited body.

Controls thay document/snapshot/page/anchor/cell/bbox/pointer/image/provenance,
reference dư/thiếu, marker/number/label, segment/claim/context, financial text,
caveats/limitations và original citation metadata đều phải bị reject.

## Frozen evaluation protocol

`evaluation/m7-04-scenarios.json` cố định trước lượt đánh giá đầu; 43 saved-source
cases và50 mutations trên QA/report. Oracle được dựng bằng raw JSON + stdlib trong
nhánh --freeze-oracle, không import renderer hoặc lấy renderer output làm nhãn.
Expected cited QA body dùng cursor theo segment order trên original answer, report
body dùng raw paragraph structure. Oracle giữ source artifact byte hashes,
expected source-key hashes, numbers/binding/context/locator/caveat hashes và body
fingerprint; không sao chép ledger136MB hoặc raw financial dataset vào Git.

Oracle pin chuẩn hóa duy nhất CRLF/LF:
`a4bf893d4b129c32b33774294449b8d97364283c1a07d87f9a0ba4b25681981d`.
Byte hash file local lúc freeze:
`f243f1f88cd092d53e197e53356736a1d9b59d3d66e4c90eb395392264d0f981`.
Source artifact pins và accepted M6/M7 oracles cũ không sửa.

```powershell
.venv/Scripts/python.exe scripts/evaluate_m7_04_citations.py --output artifacts/evidence/M7-04-report-final
```

Mọi output dùng exclusive creation, không ghi đè accepted artifacts. Saved sources
có sẵn từ M7-01-offline-v2 và M7-03-report-final/offline/replay/reports, bao phủ
BBS2021–2025 và recovery2022. Không tái chạy verification/extraction. CI không cần
private artifacts; chạy synthetic contracts/controls và pin test offline.
Đường dẫn trên là lượt final đã chạy; replay mới cần thư mục --output mới.

## Kết quả

Lượt đầu: 43/43 oracle PASS, gồm19 QA BBS +18 reports BBS +6 empty/refusal controls;
627 rendered references qua các output,70 segment/paragraph bindings.50/50 adversarial
controls rejected. Precision/recall, binding, locator, page, provenance, reuse,
caveats, identity/content, JSON round-trip/determinism và local validation đều
43/43 case agreement;627/627 expected reference occurrences đúng identity/thứ tự.
Final replay sau status-coverage guard cũng43/43 và50/50 PASS, cùng oracle pin.

Protected baseline15.611 files gồm raw/processed, accepted evidence/oracles và Web
local: final run unchanged toàn bộ. Zero LLM/Gemini/OCR/extraction/calculation calls.
Bổ sung đối chiếu440 paths từ accepted M7-03 baseline (recovered crops và Web),
toàn bộ unchanged;15.287 overlapping baseline hashes cũng khớp nhau.
Tổng hợp16.051protected files unchanged, gồm toàn bộ15.727protected paths M7-03.
Bằng chứng: `artifacts/evidence/M7-04-report-final/supplemental-protected-integrity.json`.
Local:80 citation tests và185 focused compatibility tests PASS (M6-06/M7-01–03,
evidence retrieval/canonical facts). Combined run đầu262PASS/1fixture failure;
sau sửa shared-context fixture, citation module78/78PASS và targeted1/1PASS;
final module80/80PASS sau thêm2 status-coverage controls.
Không chạy lại185 compatibility đã PASS vì không đổi runtime sau run đó.
Ruff check/format toàn repo489 files, planning101tasks và diff check PASS.
CI41983022766 của core730807b được hủy khi bổ sung status-coverage guard,
không dùng làm bằng chứng nghiệm thu. CI41983340107 completed/SUCCESS đúng731e28c:
913focused PASS,Python3.12 lint/format/planning SUCCESS,Web typecheck/lint/build
và9browser/proxy smoke PASS;full regression manual SKIPPED.

## Ví dụ đối chiếu đầy đủ một QA segment

Trích nguyên segment đầu của sample `qa-multi-2025.md`:

```text
Kỳ 2025 — Doanh thu thuần kỳ 2025 là 450.474.531.227 VND. [1][2][3][4][5][6][7][8][9][10]
```

Mười references của đoạn này đều có document
`sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1`,
snapshot `D-01/normalized-v2`, Trang PDF7, provenance page, resolution unresolved.
Danh sách dưới rút gọn identity lặp lại theo khai báo chung này; sample Markdown
giữ nguyên identity đầy đủ trong từng dòng nguồn:

| Reference | Trang PDF | Original source_pointer |
| --- | ---: | --- |
| [1] | 7 | /context/0 |
| [2] | 7 | /context/1 |
| [3] | 7 | /context/2 |
| [4] | 7 | /context/3 |
| [5] | 7 | /context/4 |
| [6] | 7 | /context/5 |
| [7] | 7 | /tables/0/headers/3 |
| [8] | 7 | /tables/0/cells/10 |
| [9] | 7 | /tables/0/cells/11 |
| [10] | 7 | /tables/0/cells/13 |

Không nâng các pointers8–10 thành cell provenance. Reference[1] hiển thị:

```text
[1] Tài liệu sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1 — Snapshot D-01/normalized-v2 — Trang PDF 7. Giới hạn nguồn: source_reference_uncertain; page_level_only; Vị trí chứng cứ hiện chỉ được xác định ở cấp trang.; Vị trí nguồn chưa được phân giải đầy đủ.
```

Locator[1] trong structured sample:

```json
{
  "document_id": "sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1",
  "snapshot_id": "D-01/normalized-v2",
  "pdf_page": 7,
  "source_ref": "sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1",
  "source_pointer": "/context/0",
  "image_reference": "sha256:945e0ed02026b42edd35e3b5f471730ca8c72ad869bedc797040e0d2e551d728",
  "element_id": null,
  "table_id": null,
  "cell_id": null,
  "line_id": null,
  "observed_bbox": null,
  "provenance_level": "page",
  "resolution_status": "unresolved",
  "resource_mapping_status": "not_provided"
}
```

Original EvidenceCitation[1] giữ nguyên trong source_citations:

```json
{
  "anchor_id": "anchor:19144f75b4acea6c01a31ab28ee03ee355b298248573802f95bf5958d66bdaa5",
  "document_id": "sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1",
  "snapshot_id": "D-01/normalized-v2",
  "pdf_page": 7,
  "provenance_level": "page",
  "source": {
    "document_id": "sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1",
    "snapshot_id": "D-01/normalized-v2",
    "reference": {
      "anchor": {
        "page": {
          "symbol": "document:32d18769-ad63-4df5-88ea-8eb06596f244",
          "year": "2025",
          "page": 7,
          "image": "sha256:945e0ed02026b42edd35e3b5f471730ca8c72ad869bedc797040e0d2e551d728",
          "source_ref": "sha256:6c261d2a1328daa267976d615282f1841b8daaf64e8ab534c21e19a73a149ce1"
        },
        "element_id": null,
        "table_id": null,
        "cell_id": null,
        "line_id": null,
        "observed_bbox": null,
        "proposed_bbox": null,
        "status": "uncertain"
      },
      "source_pointer": "/context/0",
      "provenance_level": "page"
    }
  },
  "limitations": ["source_reference_uncertain", "page_level_only"],
  "financial_fact_verified": false
}
```

Marker[1] → citation:19144f… → original anchor:19144f… → exact document/snapshot,
page7 và source_pointer/context0. Binding giữ nguyên toàn bộ verified claim IDs
của segment, gồm các ACCEPT tương đương. Source flag financial_fact_verified=false
không bị đổi thành true; ledger verification và source location là hai việc riêng.

Report sample annual-general-2025 giữ5 financial paragraphs, bao gồm B01 tại ngày
2025-12-31 và B02/B03 kỳ2025; paragraphs cash_flow:p2/p3 cùng nguồn tái dùng số38–48.
Sample partial-2025 giữ missing sections/limitations và original_status partial.

Ba bộ samples tại `artifacts/evidence/M7-04-report-final/samples/`: qa-multi-2025,
annual-general-2025, partial-2025. Mỗi bộ có Markdown, rendered typed JSON với
original source_citations, locator JSON và validation summary JSON; không commit
private evidence/artifacts.

## Root causes, fixes và giới hạn

- Report top-level citation order theo outline có thể khác narrative order: kiểm
  tra exact source inventory theo tập, đánh số theo paragraph traversal.
- Trùng paragraph ID có thể làm suffix lan sang scope paragraph: chặn duplicate
  IDs trên toàn report, kể cả đoạn không có citations.
- Source rỗng khai báo answered/generated hoặc nguồn có claims nhưng khai báo
  refusal tự mâu thuẫn: kiểm tra status phải phù hợp với required bindings.
- Fixture ban đầu dùng sai ClaimKind và chia sẻ mutable context giữa paragraphs:
  sửa fixture theo typed contract; không thay upstream behavior.
- Oracle pin theo bytes phụ thuộc CRLF/LF: pin chuẩn hóa newline, label mutation
  vẫn bị reject; source byte pins gốc và protected baseline không thay đổi.

Không còn lỗi core citation đã biết. P2: BBS real chỉ page-level uncertain;
element/cell/observed-bbox mới được kiểm tra bằng synthetic engineering fixtures.
Chưa có resource mapping/PDF viewer hoặc independent PDF citation/financial
accuracy. Broad upstream citation lists và annotation tail có thể dài; giữ đủ
nguồn thay vì tự thu hẹp financial attribution. Văn phong upstream giữ nguyên.

Next action: chờ Owner/Tech Lead giao nhiệm vụ mới; không tự bắt đầu M7-05.
