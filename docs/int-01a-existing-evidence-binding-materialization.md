# INT-01a — Existing Evidence Binding & Materialization

Ngày 06/11/2026 (Asia/Bangkok). **REVIEW**, chờ Tech Lead nghiệm thu.
Baseline main `2c389296bdeedb965c1eeeb53dc55ef2bf274b00`. Theo vòng review tiếp theo,
Owner cho phép commit/push riêng INT-01a và yêu cầu CI đúng implementation SHA.
SHA/kết quả CI được ghi ở checkpoint sau khi run hoàn tất; không dùng CI task trước.

## 1. Executive Summary

Materialize/reuse **151 records: 127 text, 24 tables**, source-bound trên **17
trang / 5 PDF**. Exact ID lookup/reload 151/151; giữ toàn bộ page candidates.
**0 Gemini/OCR calls**, không sửa Financial Facts/EF-EG/metrics/reviews/ledger.
BBS2025 signer/footer p7/8, native B09 p14/15 và saved B09 BBS2022 p11/18,
BBS2024 p21/24 truy xuất được. BCC2024/2025 load được evidence hiện có.
Verified ở đây chỉ là **source binding**, không financial/claim verification.

Artifacts chính: `artifacts/evidence/INT-01a/final/`. Lần chạy đầu lưu ở task root;
giữ nguyên để trace. Chỉ thư mục `final/` là output bàn giao. Nội dung PDF riêng
tư và bảng mẫu actual nằm trong `final/real-pdf-checks.md`,
`final/sample-evidence-local.json`; không đưa corpus vào Git.

## 2. Existing Evidence Reuse

| Nguồn saved response | Có text/table | Export/evidence trước task | Catalog trước task | Output INT-01a |
| --- | --- | --- | --- | --- |
| M1-15 BBS2025 p5/7/8 | Có | M1-16 native + M3 native | Không trong E2E financial catalog | 33 text/3 tables |
| M1-15 BBS2025 p14/15 | Có | Chưa unified/M3 | Chưa hydrate | 25 text/7 tables |
| D-01 BBS2022 p11/18 | Context + tables | Không nằm selected normalized repository | Chưa hydrate B09 | 9 text/2 tables |
| D-01 BBS2024 p21/24 | Context + tables | Không nằm selected normalized repository | Chưa hydrate B09 | 12 text/4 tables |
| GEN-01 BCC2024 p9–12 | Context + tables | Persisted evidence | GEN-01 M4 | Reuse 26 text/4 tables |
| GEN-01 BCC2025 p5–8 | Context + tables | Persisted evidence | GEN-01 M4 | Reuse 22 text/4 tables |
| M1-16 existing legacy p5 | 6 text/1 table | M3 quarantine | Không approved | Loại 7 records |

Mọi approved source đều có page identity, PDF/image fingerprint và response
thật, không chỉ classification. `source-inventory.json` ghi từng trạng thái
EXTRACTED/PERSISTED/MATERIALIZED/BOUND/RETRIEVABLE, coverage và fidelity.
Đường dẫn D-01 lấy từ workspace/inventory thực tế; không đoán response từ filename.

## 3. Source/Snapshot Binding Decisions

`verify_saved_pages` hash đúng bytes PDF đưa cho PDFium; rerender đúng renderer
và DPI trong provenance, so **toàn bộ** provenance/source với saved record:
PDF hash, image hash, original page, source identity, dimensions và page count.
17/17 page bindings khớp. Không dùng filename, ticker/năm, dimensions hoặc text
similarity làm bằng chứng duy nhất. Không cần nới quy tắc cho renderer khác.

Legacy M1-16 existing thiếu verified PDF/image binding: giữ nguyên nguồn/quarantine
cũ, inventory exclusion rõ lý do; không đưa vào approved catalog. Zero approved
records bị quarantine mới, bảy legacy records bị loại. Không đổi source hash,
snapshot IDs hoặc original citations để hợp thức hóa retrieval.

## 4. Composition Manifest

`src/evidence/composition.py` thêm contract nhỏ `EvidenceComposition`, không
thay Document Evidence schema. Năm manifest `final/{BBS_2022,BBS_2024,BBS_2025,
BCC_2024,BCC_2025}/composition.json` pin logical document, financial descriptor,
document descriptor(s), original artifact/hash, verified/unverified pages,
binding method, evidence identities và exact payload fingerprints.

Financial BBS vẫn `D-01/normalized-v2`; B09 D-01 vẫn `D-01/extraction-v1`.
M1 native giữ snapshot `artifacts/document-understanding/M1-16/native.json`.
Hai trang mới p14/p15 dùng original cache locator làm snapshot riêng, không
mở rộng snapshot export đã nghiệm thu. BCC giữ UUID snapshot GEN-01 gốc.

Caller đọc manifest bằng `EvidenceComposition.model_validate_json`, gọi
`load_composition(manifest, DocumentEvidenceRepository(...), document_id=...,
composition_id=...)`, rồi truyền catalog vào **EvidenceRetrievalTools** hiện có.
Loader preflight toàn bộ pins; thiếu một record/payload conflict → từ chối toàn
composition, không fallback partial/latest. Chỉ hydrate sources được pin và
`status=verified`; records khác trong cùng repository không tự lọt vào catalog.
Catalog này phục vụ document retrieval; không merge facts/graph của financial
catalog hoặc nới D03-B10. Manifest là source selection, không claim approval.

## 5. Materialization Results

Reuse `run_document_understanding(... persisted_results=..., allow_live_ocr=False)`
cho p14/15, `evidence_from_unified_page`, `evidence_from_persisted_result` và
DocumentEvidenceRepository hiện có; BCC đọc trực tiếp typed persisted evidence.
Không thêm repository implementation thứ hai. Nguồn unbound nếu có được lưu
ngoài approved root bằng cùng repository, giữ nguyên identity cùng binding reason.

Fidelity exact **127 texts / 24 tables / 1.805 cells hoặc headers**. Native so
text/reading, row/column, bbox candidate và dimensions với saved payload; financial
tables so toàn bộ typed structure. Giữ nulls, unknowns, order, limitations và source
pointers. Không ghép tên–chức vụ; bảng M1 vẫn có geometry/layout caveats. Số tables
là structures Gemini đã lưu, không khẳng định số bảng logic đã được human verify.
Native M3 accepted 36 records được so lại exact identity/payload trong acceptance.

## 6. Retrieval API Results

Trace thật: saved response → existing adapter → document repository → composition
→ public M4 ID/page/source tools. `final/trace.json` và `retrieval-results.json`
giữ input/output identities, status/count/errors, PDF/trang và citations.
151 ID lookups đều `found` và payload equality; sources/citations đọc lại được.
17 page lookups giữ **mọi candidates**, status `ambiguous` theo API hiện có khi
có nhiều records. Không chọn candidate đầu làm đáp án. Không chạy M5/tools giả.

## 7. Real PDF Acceptance Tests

Vòng chốt Tech Lead bổ sung ba mẫu **nội dung thực chất** tại
`artifacts/evidence/INT-01a/review-closure/substantive-evidence.md` và JSON cùng tên:

- BBS2025 PDFp7: sáu text regions gốc `/text_elements/6` đến `/text_elements/11`
  trong snapshot `artifacts/document-understanding/M1-16/native.json`: ba chức vụ
  và ba họ tên in đầy đủ. Mỗi vùng có identity/citation riêng; không ghép người–role.
- BBS2025 PDFp14: nguyên đoạn B09 ba dòng liên tiếp `/text_elements/4`, `/5`, `/6`
  (đầy đủ prefix `/text_elements/`), mô tả nhân viên quản lý chủ chốt; giữ newline
  và source boundary. Snapshot `artifacts/gemini-ingestion/M1-15/pdf/page-14.json`.
- Cùng trang/snapshot: bảng `/tables/0`, các ô `/cells/6` đến `/cells/14`
  (đầy đủ prefix `/tables/0/`): tiền mặt, tiền gửi ngân hàng và cộng, hai cột ngày
  cùng số liệu thật. Giữ original dimensions/cell-layout issues, không tính lại.

Các quotes/số liệu riêng tư giữ local theo AGENTS; phản hồi bàn giao nêu trực tiếp
ba mẫu để Tech Lead đối chiếu. Public report không chỉ dựa vào headings.

Bảng actual đọc được ở **`artifacts/evidence/INT-01a/final/real-pdf-checks.md`**:
có 18 mẫu Source PDF, trang PDF one-based, evidence type, quote/cell thật, Binding,
Retrieval, original identity và source pointer. Toàn bộ quotes/cells nằm thêm
trong `sample-evidence-local.json`; ảnh full-page tại `final/visual/`.

| Real case | Binding / retrieval | Đối chiếu ảnh PDF |
| --- | --- | --- |
| BBS2025 p7/8 signer | Verified / đầy đủ page candidates | In rõ tên và chức vụ thành các vùng rời; không dùng chữ ký viết tay để nhận dạng |
| BBS2025 p14/15 B09 | Verified / 32 records | Notes, tiền/phải thu/hàng tồn kho, nợ xấu/chi phí trả trước; fidelity nguyên cache |
| BBS2022 p11/18 B09 | Verified / 11 records | Có prose trên PDF nhưng cache chỉ context/bảng; không tuyên bố full prose |
| BBS2024 p21/24 B09 | Verified / 16 records | Chi tiết vay và các bảng chi phí; có local sample source pointers |
| BCC2025 p7, BCC2024 p11 | Verified / compatibility | Tiêu đề B02 riêng/hợp nhất khác nhau; không ghép nguồn/kỳ/phạm vi |

Đã xem ảnh của mười trang ở trên; đây là spot review bởi Codex, không independent
human gold hoặc benchmark accuracy toàn PDF. Hai trang p7/8 BBS2025 tương ứng
printed page6/7: manifest/citations dùng **PDF page**, không đổi thành printed page.

## 8. Negative Cases

13 focused controls: wrong document/composition/snapshot/page/image, missing
fingerprint, duplicate evidence, payload conflict, descriptor conflict, different
PDF, partial materialization, legacy exclusion và restart/idempotence.
34 acceptance checks bổ sung trên identities/artifacts thật ở `final/acceptance-checks.json`:
wrong document/snapshot/page qua M4; manifest mutation page/image, duplicate,
payload conflict, missing record; repository conflict; actual wrong PDF render;
missing fingerprint; accepted M3 exact payload; protected inputs unchanged.
Không có negative fixture nào thay thế các real positive cases mục 7.

## 9. Financial Regression

193 targeted/compatibility tests PASS: composition, M3 document evidence, M4
retrieval tools/calculator, M6 Judge, M7 Information Firewall và planning; một
warning Pydantic có sẵn từ fixture intentional invalid Decimal. Sau đổi loader
sang batch read cùng repository, 30 composition/M4 tests PASS.
Không đổi M6/M7 hoặc accounting runtime. Selected accepted facts/evidence, graph,
reviews/metrics/results và tám inherited runtime/CI/Web files có before/after
hash trong `coverage-summary.json`; acceptance xác minh **72 inputs + 8 inherited
files unchanged**. Không đọc/ghi real Verified Claim Ledger; tests dùng fixtures.
Không chạy lại full E2E Gemini, benchmark hoặc full suite.
Ruff lint/format năm file Python đã sửa, planning checker **109 tasks** và
`git diff --check` PASS. `final/implementation-files.json` pin bytes code chưa commit.

## 10. Root Causes & Remaining Blockers

- Earliest missing stage của p14/15 là materialization: replay existing M1 pipeline
  sửa được bằng saved payload; không cần extraction mới.
- B09 D-01 đã persisted nhưng selected normalized repository không hydrate:
  materialize original snapshot và explicit composition giải quyết được.
- M1 native không được E2E financial catalog chọn; loader explicit source manifest
  cung cấp catalog cho caller mà không rewrite snapshots hoặc đổi QA gates.
- Acceptance runner ban đầu giả định page lookup luôn `found`; sửa giữ `ambiguous`
  + đầy đủ records đúng contract. Không đổi API để làm đẹp kết quả.
- Legacy PDF/image binding thiếu: vẫn excluded, cần source chứng minh được nếu
  muốn dùng sau này. BCC B09/audit narrative ngoài primary pages chưa có output
  được kiểm chứng trong phạm vi này; không báo PASS cho coverage thiếu.
- CI đúng implementation SHA đang được chốt theo chỉ đạo review; kết quả được ghi
  ở checkpoint CI sau khi xác minh run. Task giữ REVIEW, Tech Lead quyết định DONE.

## 11. Handoff INT-01b

INT-01b có thể dùng năm persisted compositions + shared document repository và
existing public M4 APIs; raw text/cells giữ nguyên, lexical projection xây riêng
sau khi được giao. Coverage thiếu/legacy exclusions đã tường minh. Chưa chạy
INT-01b, GEN-01a hoặc M8.

Reproduce offline: `.venv/Scripts/python.exe scripts/materialize_existing_evidence.py
--output artifacts/evidence/INT-01a/<new-run>`; output conflict không overwrite.
Reload/negative acceptance: thêm `--verify-only` với output đã hoàn tất. Cả hai
không khởi tạo Gateway/provider, không đọc credentials.

**Next action duy nhất:** Tech Lead review INT-01a, gồm real local evidence và
phần CI implementation SHA còn chờ khi được phép commit/push.
