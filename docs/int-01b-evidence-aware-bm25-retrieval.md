# INT-01b — Evidence-Aware BM25 Retrieval

Ngày 06/11/2026 (Asia/Bangkok). **REVIEW**, chờ Tech Lead nghiệm thu.
Baseline main `8324d0e`; implementation
[`35258282ff7eed4b413c713510cadc7dff4f149b`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/35258282ff7eed4b413c713510cadc7dff4f149b)
đã push main. [CI42219245983](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42219245983)
đã **completed/SUCCESS**, xác minh đúng implementation SHA: **1.107 Python tests
+ 9 Web smoke PASS**, Ruff lint/format, planning109tasks, frontend typecheck/lint/
production build và browser/proxy checks SUCCESS; full regression SKIPPED.
Checkpoint sau implementation chỉ docs/planning `[skip ci]`, không gán CI này
cho SHA checkpoint. Local planning110tasks gồm GEN-01a pending ngoài commit.

## 1. Executive Summary

SQLite FTS5/BM25 tìm nội dung trên **151 units = 127 text + 24 tables**, đúng năm
compositions INT-01a. Không thêm kho facts, dependency, vector/LLM/reranker, OCR
hoặc Gemini calls. Typed operation `search_document_evidence` trả record/citations
gốc, snippet, cell selectors và neighboring regions tách biệt.

30 targeted probes: 24 positive, 6 negative; Recall@1/3/5 = **85,42%/100%/100%**,
MRR **1,00**, no-answer **6/6**, table hit@5 **11/11**, leakage **0**.
Đây là development probes trên cache nhỏ, đã dùng để sửa ranking; **không M8,
không held-out benchmark hoặc chứng minh financial accuracy**.

## 2. Existing Evidence Integration

`EvidenceRetrievalTools.from_composition(manifest, repository, document_id=…,
composition_id=…)` tạo index qua `load_composition()` rồi dùng SnapshotCatalog.
Không crawl JSON, latest/parent/recovery fallback hoặc dùng discovery summaries.
Mỗi pin vẫn qua exact payload/source validation INT-01a. Source có status
quarantine không vào catalog. Generic catalog cũ vẫn chạy exact tools; search
trên catalog đó trả `unavailable/explicit_composition_required`.

| Composition | Text | Table | Units |
| --- | ---: | ---: | ---: |
| BBS 2022 | 9 | 2 | 11 |
| BBS 2024 | 12 | 4 | 16 |
| BBS 2025 | 58 | 10 | 68 |
| BCC 2024 hợp nhất | 26 | 4 | 30 |
| BCC 2025 riêng | 22 | 4 | 26 |

## 3. Indexing Architecture

Một unit/evidence identity; normalized text chỉ ở in-memory SQLite. Table unit
index text của headers/cells; response giữ nguyên row/column/pointer và values,
không tái tính hoặc tạo canonical facts. Snippet chọn cells trùng keyword và
cùng hàng để giữ giá trị kề nhãn; full typed original table cũng còn trong record.
Repeated keywords trong nhiều ô không sinh duplicate table matches.

Text context gồm tối đa ba regions mỗi phía, chỉ khi `/text_elements/N` hoặc
`/context/N` liên tiếp cùng document/snapshot/page/image/source_ref/request.
Gặp gap dừng; unknown order không ghép. Đây là **source array order**, không
spatial reading order đã human verify. Mỗi neighbor có original record/citations,
order và identity riêng. Proximity không chứng minh quan hệ tên–chức vụ.

## 4. BM25 Implementation

FTS5 `bm25(units, 1.0, 0.25)` trên body/context; query dùng tham số SQL và escaped
normalized tokens, không cho caller truyền FTS syntax. SQLite sẵn có trong Python
3.11/3.12 phù hợp corpus; không cần triển khai engine thứ hai. FTS5 thiếu trên
Python build đặc biệt sẽ raise SQLite error khi build, không silently fallback.

Ranking lexicographic: direct exact phrase → direct unique-term coverage →
optional lexical section hint → BM25 → serialized original identity.
Score trả về là `-bm25`, dương và cao hơn là BM25 relevance tốt hơn; rank còn
chịu phrase/coverage/hint, vì vậy score không nhất thiết giảm theo rank.
Context đóng góp BM25 nhưng không tạo match khi primary thiếu keyword.
Direct keyword coverage tối thiểu 60% để hạn chế matches chỉ trùng âm tiết chung.
Đây là heuristic trên probes, có thể miss paraphrases; không confidence threshold.
Exact phrase bắt buộc nằm trong primary text hoặc một cell, không qua hai cells.

## 5. Search API/Contracts

Public imports từ `vietnamese_financial_multi_agent.tools`:
`SearchDocumentEvidenceRequest`, `DocumentSearchResponse`, `EvidenceRetrievalTools`.
Search có response riêng; union/response exact tools giữ nguyên semantics.

Request bắt buộc `document_id`, `composition_id`, `query`; optional `snapshot_id`,
`source_page` (PDF one-based), `evidence_type=text/table/both`, `section_hint`,
`exact_phrase`; `top_k` 1–20, mặc định 5. Query tối đa 2.000 ký tự. Section hint
là soft lexical boost, không inferred accounting section. Snapshot None nghĩa
là mọi snapshot **đã pin trong composition**, không chọn latest.

Match có rank, BM25 relevance, typed `RetrievalMatch` với original record/citations,
`evidence_ids`, document/snapshot/page, original snippet/cells, typed neighbors,
matched normalized terms, ranking reasons và limitations. Score không claim
confidence. Empty/punctuation và missing coverage trả `not_found` kèm reason;
absence trong selected cache không chứng minh PDF không có thông tin đó.
Caller gọi `close_search()` khi xong; restart build lại từ cùng manifest/repository.

## 6. Vietnamese Text Processing

Casefold → đ/d → Unicode NFKD → bỏ combining marks → word tokens/whitespace.
Hiển thị vẫn original Unicode. Có dấu/không dấu/uppercase/decomposed Unicode
retrieval cùng nhóm IDs. Exact phrase dùng normalized boundaries.

Sau real probes thêm các prefix nhỏ `tìm thông tin về`, `cho biết`, `thuyết minh về`,
suffix `gì` và role variant `người lập biểu` → `người lập`, chỉ cho non-exact queries.
Không hardcode tên người, PDF hoặc câu trả lời; không general query understanding.

## 7. Source/Snapshot Isolation

Sai document/composition trả not_found trước search; snapshot/page/type lọc AND.
Không index financial snapshots ngoài pins. Citations và neighbors đều giữ
identity gốc; evaluator kiểm tra mọi returned identity thuộc verified pins.
Wrong document, snapshot, composition, recovery/legacy và missing-page controls
đều không có kết quả. Loader vẫn fail-closed khi duplicate pins/conflicts/missing
materialization; các regression INT-01a giữ nguyên.

## 8. Real PDF Retrieval Results

Gold IDs được viết trước search trong evaluator, không lấy ranked results làm
expected. Có **31 expected-evidence occurrences** đối chiếu exact content với
original saved JSON. Đã xem ảnh render INT-01a của BBS2025 p7/8/14/15,
BBS2022 p11/18, BBS2024 p21/24, BCC2024 p11, BCC2025 p7.
Đối chiếu bởi Codex, không independent human gold. BBS2022 p11 có prose về
đường thẳng trên PDF nhưng saved cache chỉ context/table: P29 coverage missing.
BCC có signatures trên PDF nhưng accepted cache không chứa chúng.

| Query | PDF | Expected evidence | Top result | Rank | Source page | Status |
| --- | --- | --- | --- | ---: | ---: | --- |
| Người lập biểu | BBS2025 | p7 text/6 hoặc p8 text/8 | p8 text/8 | 1 | 8 | PASS |
| Kế toán trưởng | BBS2025 | p7 text/7 hoặc p8 text/9 | p8 text/9 | 1 | 8 | PASS |
| Nợ xấu và dự phòng phải thu khó đòi | BBS2025 | p15 text/4 | p15 text/4 | 1 | 15 | PASS |
| Tiền gửi ngân hàng | BBS2025 | p14 table/0 | p14 table/0 | 1 | 14 | PASS |
| Nhà cửa vật kiến trúc | BBS2022 | record/4/page/11/tables/0 | cùng ID | 1 | 11 | PASS |
| Chi tiết các khoản vay ngắn hạn | BBS2024 | record/4/page/21/context/4 | cùng ID | 1 | 21 | PASS |
| Báo cáo kết quả hoạt động kinh doanh hợp nhất | BCC2024 | record/2/page/11/context/4 | cùng ID | 1 | 11 | PASS |
| Giá vốn hàng bán | BCC2025 | record/2/page/7/tables/0 | cùng ID | 1 | 7 | PASS |
| phương pháp đường thẳng | BBS2022 | cache thiếu prose | không có | — | — | coverage missing |

Native IDs viết tắt trong bảng: `unified/page/{p}/text/text_elements/{n}` hoặc
`unified/page/{p}/table/tables/{n}`. Full identities/snapshots/source references,
30 actual rows, actual financial cells và **năm substantive examples, mỗi PDF
một mẫu**, ở `artifacts/evidence/INT-01b/final/actual-results.md` (local actual report).
Các samples gồm original text/table rows và full citations JSON, không chỉ PASS.
Corpus/quotes/số liệu riêng tư giữ artifacts ignored theo AGENTS, không đưa vào Git.

## 9. Retrieval Quality Metrics

Recall@k là macro-average `|top_k ∩ expected| / |expected|` trên 24 positives;
không phải hit rate. Các role/name queries có hai page IDs nên Recall@1 < 100%
dù first relevant result ở rank1 trên mọi positive. MRR tính first relevant ID.
No-answer denominator là sáu queries âm; table hit denominator 11 positives
có expected tables. Năm PDF có 151/151 evidence units index, không full PDF coverage.

| Metric | Trước sửa | Sau sửa |
| --- | ---: | ---: |
| Recall@1 | 83,33% | 85,42% |
| Recall@3 / @5 | 100% / 100% | 100% / 100% |
| MRR | 0,9792 | 1,0000 |
| No-answer | 2/6 | 6/6 |
| Table hit@5 | 11/11 | 11/11 |
| Wrong-source leakage | 0 | 0 |

Final single local run: end-to-end search median **18,96 ms**, max **105,09 ms**
(bao gồm typed payload/citations). Build gồm loader validation: BBS2022 **186 ms**,
BBS2024 **135 ms**, BBS2025 **548 ms**, BCC2024 **360 ms**, BCC2025 **340 ms**;
BBS2025 reopen/rebuild **1.339 ms**. Không warmup/multi-run performance benchmark;
hardware/background work ảnh hưởng latency. Full precision trong `metrics.json`.

## 10. Failures, Root Causes & Fixes

Baseline OR matching tạo false positives P26–29: auditor query match “toán/trừ”,
wrong-person query match “Thanh Hóa” hoặc “minh”, source-missing prose match
“phương tiện”. Nguyên nhân token coverage quá thấp. Thêm minimum 60% primary
coverage, không tăng chất lượng của source. P01 “Người lập biểu” rank2 vì đoạn
khác trùng “người/biểu”; controlled role variant sửa thành rank1.
Giữ nguyên 30 probes/expected IDs trước/sau, artifacts `before/` và `final/`.
Final không còn retrieval miss trong bộ nhỏ này. Không suy là mọi no-answer
hoặc paraphrase đều đúng; accent folding vẫn có collisions, synonyms chưa hỗ trợ.
Exact phrase có control không ghép qua hai unrelated cells; table layout/cell
reading caveats giữ nguyên. B09 narrative/cache thiếu là coverage gap riêng.

## 11. Compatibility/Regression

Local final unique coverage **241 PASS = 227 compatibility + 14 search tests**.
Một fixture mới dùng code_column=None không hợp lệ; sửa thành1 và rerun14search
PASS. Vòng compatibility227PASS không có thay đổi sau run. Một warning Decimal
có sẵn từ negative fixture.

Focused suites: search, composition, document evidence, exact retrieval/M4 tools,
financial retrieval/calculator, M6 Judge và M7 firewall. Kết quả và lệnh thực chạy
ghi `artifacts/evidence/INT-01b/final/regression-results.txt` cùng checkpoint.
Ruff file sửa, planning checker và diff check là engineering validation;
không dùng synthetic PASS như financial accuracy. CI thêm duy nhất search suite;
GEN-01a CI entries vẫn local, không commit cùng task.

Không sửa Financial Facts/EF-EG/M6/M7, GEN-01a runtime/tests hoặc Web pending.
Chỉ giữ checksum của inherited pending files cần bảo toàn, không hash dataset.

## 12. Handoff QA-01a

Public typed search dùng được trực tiếp, còn M5 dispatch/document claims/M6–M7
integration thuộc QA-01a/QA-01b. Consumer phải dùng typed citations/neighbor
boundaries, phân biệt relevance/source binding với semantic claim support;
không gán tên–chức vụ từ context và không coi table cell là verified fact mới.
Không bắt đầu QA-01a trong phiên này.

Next action: Tech Lead review INT-01b.
