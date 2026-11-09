# REC-01 — Conditional OCR Recovery & Approved Release Activation

Ngày 09/11/2026 (Asia/Bangkok). Status **REVIEW**; baseline `0a66240`.
Implementation `81ce0f67cf2b800ddae074b95825e41cc4be4d64` đã push main;
[CI42571562562](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42571562562)
SUCCESS đúng SHA: **1193 Python/9 Web PASS**; lint/format/planning/typecheck/build
và browser/proxy smoke đạt; full regression manual SKIPPED. Chỉ một CI run.
Giữ pending GEN-01a/Web, accepted EXT-01, frozen GEN-02 và source policy.

## Kiến trúc và cấu hình

`FinancialQAPipeline.__init__` chọn release bằng `active-releases.json` trong
`DOCUMENT_RELEASE_ROOT` (mặc định checkout `artifacts/source-quality`). Manifest
ghim logical document, composition ID/digest, release digest và policy fingerprint;
các đường dẫn composition/repository/PDF/saved-page phải nằm trong storage root.
Không có latest, database mới hoặc thay accepted files. Configured root thiếu file
hoặc selection sai làm startup fail; không fallback sang OCR cũ. Wheel không cấu hình
giữ legacy behavior; deployment phải cấp root tuyệt đối cùng policy root/pin.

Startup gọi `check_correction_promotion`: actual approval, VALIDATED correction,
exact content/pins/selectors và render đúng original PDF/image. Repository được
chọn theo source document; các logical documents khác giữ nguồn cũ. Restart đọc lại
manifest và preflight; approval không được tạo mới. M6 và ledger vẫn kiểm tra current
source policy, kể cả sau khi cache ấm hoặc approval thay đổi.

Điểm nối recovery ở document lane, ngay sau M6 và trước ledger admission. Chỉ
decision có `source_quality=false` mới xét evidence được reference chính xác.
Trigger dùng confirmed transcription discrepancy hoặc `pdf_review:*` hiện có;
missing search, thiếu toán hạng, sai scope/logic/provider semantic không kích hoạt.
Corrected snapshot hoặc original đã có approved release không gọi Gemini.
Mixed lanes dùng chung budget request; tối đa một recovery attempt trong request.

`recovery-sources.json` ánh xạ exact evidence payload digest tới composition digest,
PDF, saved-page và selector. Không scan corpus. Lazy loader chỉ render đúng một trang,
đối chiếu PDF/page/image/provenance với persisted save; chưa có trusted bbox nên dùng
full-page image, không suy đoán crop. Clean M6 chỉ kiểm tra boolean, không khởi tạo
credential/adapter, không đọc ảnh/PDF hoặc gửi network request.

Gemini qua `SharedLLMGateway` và adapter hiện có, một generate, không retry;
`OCR_RECOVERY_TIMEOUT_SECONDS=10` mặc định sau bản sửa provider bên dưới,
model qua `OCR_RECOVERY_MODEL`.
Prompt yêu cầu transcription nguyên văn, đặc biệt phủ định/ngày/số/đơn vị;
JSON được local-validate theo `Transcription`, gồm page/selector/readability/spans.
Result giữ provider/usage/cost/latency/error và exact provenance trong
`recovery-candidates/`. Readability không là calibrated confidence.

Proposal chưa có independent visual review nên không tạo `DocumentCorrection`
với `PDFTextReview` giả. Trạng thái: unchanged giữ source-quality block;
uncertain → pending_review; transcription thay đổi có cấu trúc → proposal_pending_review.
Reviewer sau đó dùng workflow `PDFTextReview` → `validate_correction` →
`build_correction_version` → separate `CorrectionApproval` → exact activation.
Không có approval workflow thứ hai. Recovery không sửa evidence hoặc M6 decision
trong request; claims còn hợp lệ vẫn có thể đi qua Ledger→M7→Firewall.

## Kết quả thật

| Scenario | Trigger | Gemini live calls | Result | Latency |
| --- | --- | ---: | --- | ---: |
| Clean financial D01 | No | 0 | Answer/source citations/M6/M7/Firewall tương đương | 18,930→20,287s |
| Clean document D17 | No | 0 | Answer/source citations/M6/M7/Firewall tương đương | 11,155→10,993s |
| Mixed clean D18 | No | 0 | Answer/source citations/M6/M7/Firewall tương đương | 67,464→64,276s |
| H08 approved correction | No | 0 | 2 ACCEPT/stored; M7 answered; Firewall ALLOW_WITH_CAVEAT | 11,438s |
| PDF30/9 confirmed discrepancy | Yes | 1 | Provider invalid_request; không retry, selector 9 INVESTIGATE | Recovery 5,315s; QA 18,613s |
| Cùng PDF30, recorded review fixture | Yes | 0 | proposal_pending_review, chưa approval/release | 2,441s |
| Cùng PDF30, recorded uncertain fixture | Yes | 0 | pending_review, chưa approval/release | 2,526s |

Recorded fixtures lấy transcription từ independent review đã lưu trước task,
không là Gemini output live hoặc đánh giá OCR accuracy mới. Gateway invocation
trong fixture được phân biệt với actual Gemini call. Live task: **1 call**, token
usage/cost unknown, provider trả invalid_request; không suy nguyên nhân HTTP/quota
khi không có evidence. Không có live transcription thành công để đánh giá accuracy.
Trace live đo tổng recovery branch 5,315s, chưa tách provider-call latency; final
instrumentation thêm `call_latency_ms`/safe provider error code cho các lượt sau,
không gọi live lần hai để bổ sung số đo. Assertion timing này đã PASS trong CI.

H08 chạy đúng một QA E2E sau persistent selection. M5 lấy corrected selector 7;
M6 ACCEPT hai claims, ledger stored hai, M7 answered. Hai citations đều trang 16:
selector 7 dùng `correction:9c5e9844…`, selector 6 giữ original snapshot hợp lệ.
Đây là hai source bindings riêng được ghim trong cùng composition, không chuyển
old proof sang corrected snapshot. Runner assertion ban đầu đòi mọi citation thuộc
correction snapshot là quá chặt; sửa assertion và đọc lại saved result, không rerun H08.
Process mới chỉ kiểm tra startup selection, không chạy QA lần hai.

H08 release `082d30e483d2a0133d696e923c90a1a555aaf993e49da6bb9a200a5cfd6625bc`,
composition `a7ba94c8ac7ca3dd039971008ee7cd841da93af6b93f5e1cb3d98e3c0b73a920`,
policy `4682f615df2fd70ec470b001f67eda74ab2b6a1d6f1aff4a8b351d8c79bb26e7`.
Local activation copies verified bytes vào storage riêng; accepted source không đổi.

PDF30/9 vẫn quarantine, không release/approval/activation cho selector đó.
Live request bound đúng page-30 snapshot để không lấy các đoạn tên công ty từ trang
khác. M6 INVESTIGATE selector 9; một clean selector 12 ACCEPT, citation duy nhất
trang 30/12; không dùng lỗi OCR để trả lời. Những truy vấn chuẩn bị chứa năm trong
mã hợp đồng hoặc từ “quý” bị existing planner chặn trước retrieval, calls=0;
không sửa planner ngoài scope.

## Safety và validation

17 REC fixture controls kiểm tra clean/missing, eligible, page/selector/image/
composition mismatch, timeout, ambiguous/unchanged transcription, request budget,
unapproved/wrong digest/policy/missing config/storage escape và restart selection.
Approval dương trong unit tests là synthetic; H08 E2E dùng actual approval đã có.
Existing tests kiểm tra source quarantine, warm ledger/revocation/replay, immutable
history, cross-snapshot proof và citations. Vòng 1:54 PASS; vòng 2:99 PASS
(overlap, không cộng thành153). Thêm call-timing metadata/assertion sau local vòng2;
CI đã PASS exact final SHA, gồm timing assertion mới. Không mở vòng focused sửa thuật toán thứ ba.

Real old H08/PDF30 histories được đọc read-only, current retrieval loại defective
claims và `build_verified_claim` từ old histories bị reject; unrelated controls còn
visible. Không rewrite old ledger/source policy; new H08 ledger lưu riêng REC-01.
Timeout/ambiguous fixtures không thay accepted content, không tạo trusted claim.
Đây là engineering controls và một H08 source fidelity case, không chứng minh chất
lượng tài chính toàn corpus hoặc M8-ready.

## Performance và giới hạn

Đã đo before/after D01/D17/D18 từ PERF-01, cùng cấu hình local, một lượt/case,
ledger riêng giống nhau. Không chạy tests đồng thời với phép đo. Dùng baseline
pipeline từ `0a66240`, giữ các modules/pending code còn lại như after. Baseline chỉ
thêm tương thích keyword budget rỗng cho mixed runner; không thay thuật toán.
Instrument image loading sau startup; startup approved-release preflight có render
H08 và được tách khỏi QA latency. Không tuyên bố đã cải thiện latency từ một sample.
D01 chậm7,17%,D17 nhanh1,45%,D18 nhanh4,73%; detection financial0/document0,0048ms/
mixed0,0062ms. Không thêm image/PDF loading hoặc OCR trên cả ba clean requests.

Hai ledgers không byte-exact: fresh financial proofs chứa random plan/origin IDs,
timing và hashes phụ thuộc chúng, dẫn tới verified claim IDs D01/D18 khác nhau.
Đối chiếu accepted claims giữ toàn bộ fields trừ transient provenance.origins[].candidate_id;
ghép từng claim một-một rồi dùng explicit ID mapping để so sánh output bindings.
Answer text, citation IDs/PDF/page/image/selector/source bindings, Decimal values,
M6 decisions, M7/Firewall và caveats khớp; D17 verified IDs cũng khớp nguyên.
Không loại source pins/content hoặc tuyên bố raw response/ledger byte equivalence.
Artifact comparison giữ ID mapping và limitation này; không rerun để chọn số đẹp.

Recovery tự động chỉ dừng ở bounded transcription/proposal; material changes vẫn
cần reviewer và actual approval. Missing binding/invalid config/provider failure
giữ quarantine hoặc source unavailable. Live provider error còn chặn xác nhận
chất lượng re-OCR; recorded fixture không thay thế live validation. Không thêm
reviewer Web UI, không recovery corpus hoặc promote PDF30. Không sửa accounting
policies, không benchmark GEN-02/M8 hoặc đổi mặc định toàn bộ corpus.

Artifacts local `artifacts/evidence/REC-01/`: initial-state, activation-operation,
h08, restart, quarantine-controls, fresh-pdf30-eligible, recorded-real-proposals,
round-1/round-2 tests và performance before/after. Recorded candidates được tách
khỏi operator store sang `recorded-fixture-candidates/`, giữ bytes/hash và external
provenance labels; không giả thành successful Gemini output. Private inputs/proposals/PDF/key
không commit. Pending GEN-01a/Web và approved/frozen inputs được đối chiếu hash.

## Sửa invalid_request theo quyết định Tech Lead

REC-01 giữ REVIEW, chưa DONE; không CHAT-01. Bản sửa deadline được ghi trong Git checkpoint riêng;
CI1193/9 phía trên chỉ xác minh implementation cũ, không là CI của bản sửa này.

Replay diagnostic đúng request BCC2024 PDF30/selector9 nhận **HTTP400 INVALID_ARGUMENT**:
`Manually set deadline 8s is too short. Minimum allowed deadline is 10s.`
SDK config gốc: model gemini-3.5-flash-lite, temperature0, max_output_tokens2048,
application/json, không schema_ref, timeout8000ms, attempts1; một PNG1719579bytes,
đúng persisted PDF/page/image binding. Offline `_config` hợp lệ. Đây là lỗi deadline
được provider chỉ rõ, không phải quota/rate-limit/model/image/schema hoặc lỗi định
tuyến gateway. Không gọi thêm để thử các giả thuyết đó.

Lỗi cũ không lưu provider body nên cần một diagnostic network call có kiểm soát.
Script capture ban đầu truy cập nhầm `response_json` sau khi SDK đã trả ClientError;
exact body được giữ từ exception thực tế trong transcript và artifact, không gọi lại
diagnostic. Request JSON serialize đầy đủ có optional null không dùng trực tiếp để
replay: lọc omitted generation fields, giữ temperature/max tokens nguyên bản.

Sửa nhỏ: default10s trong recovery và env example; deadline cấu hình dưới10s bị
chặn locally trước render/network, `recovery_timeout_below_provider_minimum`,
không tự vượt budget. Kiến trúc/binding/quarantine/approval không đổi. Lỗi output
schema/identity được phân biệt bằng mã riêng, vẫn fail closed.

Đúng **một lượt live xác nhận sau sửa**, không retry: provider **success/STOP**,
requested/reported model gemini-3.5-flash-lite; input1495/output206/total1701tokens;
call6553,324ms, branch8204,205ms, deadline10s. HTTP400 đã hết với thay đổi duy nhất
trong request là timeout8→10s; image/prompt/generation/schema giữ nguyên.

**Chưa xác nhận transcription thành công đầu-cuối**: JSON live có thêm field
`additionalProperties:false`; local `Transcription` với extra=forbid từ chối.
Text provider trả lại trùng OCR cũ, không giải quyết discrepancy đã review; không
coi provider success hoặc text copy là corrected transcription đáng tin cậy.
Giữ raw response/error/result, không strip field để ép PASS hoặc gọi live lần hai.
Live artifact ban đầu còn mã generic; local replay response đã lưu kiểm tra mã mới
`recovery_output_schema_invalid`, không thay lịch sử live. PDF30/9 vẫn quarantine,
không candidate hợp lệ/approval/release/activation; policy/selection/repository hashes nguyên.

Focused local **22PASS** (19conditional recovery +3adapter), gồm deadline10s,
deadline8s blocked không ảnh/network, timeout, schema echo rejected và no retry.
Không chạy1193tests/full CI/H08/clean benchmark. Hai network calls mới:1diagnostic
HTTP400 và1validation provider success/schema fail; tổng lịch sử REC-01 là3calls,
1701known tokens cho validation; hai error calls usage unknown. Quyết định mới của
Owner cho phép diagnostic/fix/validation trong chính REC-01; không mở task mới.
Artifacts local `provider-fix/`: offline-root-cause, provider-original-error,
live-provider-response, live-confirmation, private request snapshots và focused-tests.

## Sửa prompt/output theo chỉ đạo Tech Lead sau `0285817`

REC-01 tiếp tục REVIEW. Chỉ thay prompt recovery và assertions offline; không sửa
M5–M7, validation, activation H08 hoặc source policy. Bỏ toàn bộ model_json_schema
khỏi prompt; hướng dẫn ngắn yêu cầu chính xác text/readability/ambiguous_spans/page/
selector, không trường khác. Yêu cầu đọc ảnh trước, current_text chỉ là locator
OCR lỗi, không là đáp án mẫu; không copy hoặc ghép đoạn bên cạnh. extra=forbid
giữ nguyên, không xóa additionalProperties để ép PASS.

**19offline tests PASS** trước live, lint/format PASS. Assertions kiểm tra đúng
prompt/locator/image/deadline, không schema annotations và field thừa vẫn bị reject.
Không chạy lại CI lớn, H08, M5–M7 E2E hoặc benchmark clean path.

Đúng **một lượt Gemini live** PDF thật BCC2024 trang30/selector9 sau offline tests:
provider success/STOP, model gemini-3.5-flash-lite; 1412input/197output/**1609tokens**;
call6082,999ms, branch8552,703ms; timeout10s; không retry, cost unknown.
JSON đúng năm fields, strict validation PASS, runtime proposal_pending_review.

**Source-fidelity FAIL — chưa phục hồi OCR**. Đã kiểm tra exact-render image cùng
binding hash và ảnh xoay để đọc (chỉ review, provider vẫn nhận ảnh gốc):

- Đoạn (i) trên ảnh in ngày đáo hạn **25/03/2021**; live output vẫn bỏ câu đó.
- Tài sản bảo đảm nằm dưới heading riêng ở đoạn tiếp theo; output vẫn ghép vào (i).
- Ngày hợp đồng trong collateral bullet là **03/03/2011**; output ghi **03/03/2021**.

Text chỉ thay đổi nhỏ dấu câu/case so với OCR cũ, giữ material defects. Readability
provider trả readable/empty ambiguous_spans không chứng minh đúng ảnh. Vì vậy không
gọi proposal này là correction đã verified hoặc trusted recovery; không cấp review/
approval, không tạo release/activation mới. PDF30/9 quarantine và H08 activation giữ
nguyên byte hashes. Không gọi live lần hai để chọn output đẹp hoặc tự mở scope mới.

Artifacts local `artifacts/evidence/REC-01/prompt-fix/`: offline-tests.log,
exact-page30.png, fixed-request-private.json, live-provider-response.json,
live-confirmation.json, visual-audit.json, protected-before.json, runtime-lock.json.
Console script có dòng generic “Live transcription succeeded” chỉ là structured
payload có sẵn; **visual-audit.json mới là kết luận cuối: recovered=false**.
Một call mới/1609known tokens; lịch sử REC-01 tổng4calls,3310known tokens ở hai
responses success,usage của hai HTTP400 unknown. Không suy accuracy toàn corpus.

## Kiểm tra vùng ảnh theo chỉ đạo Tech Lead sau `a229b5e`

REC-01 giữ REVIEW. Một lượt audit có mục tiêu, read-only; không sửa prompt/runtime,
M5–M7 hoặc H08 activation. **Không có trusted region, không Gemini call/proposal mới.**

Đã truy vết PDF30/selector9 qua saved Gemini → M1 understanding → unified region →
canonical source anchor, rồi kiểm tra raw OCR page30 và ảnh raw tương ứng:

| Nguồn định vị | Dữ liệu thực tế | Kết luận |
| --- | --- | --- |
| Saved `/text_elements/9` | candidate_bbox `[899,172,946,894]`, status unresolved, issue not_independently_verified, bounds_valid=true | Kiểm tra trên đúng ảnh200DPI cắt bảng số; không phải đoạn(i). In-bounds không chứng minh đúng vùng. |
| M1 anchor | Chỉ page identity, status unresolved; không observed_bbox hoặc element/line ID | Không có tọa độ observed đã xác minh. |
| Unified region | bbox=null, geometry_verified=false, raw_element_id=null, provenance_level=page | Không có selector→raw element binding. |
| Canonical anchor | observed_bbox/proposed_bbox và element/line IDs đều null, status uncertain | Chỉ bảo đảm vị trí cấp trang. |
| Raw OCR text_0018/0019 | Có text gần đoạn(i), boxes `[1480,2772,2421,2824]` / `[1480,2828,2419,2873]` trên ảnh2484×3509/300DPI | Inspection union đúng các box có sẵn cắt ngang nhiều đoạn xoay dọc; không bao trọn đoạn(i), không dùng làm crop OCR. |

Nguồn files: `artifacts/evidence/EXT-01/BCC_2024/responses/page-30.json`,
`unified/page-30.json`; raw `data/processed/Financial_Report_OCR/BCC/2024/ocr_json/page_30.json`
và `data/raw/Financial_Report/BCC/2024/page_30.png`. Không sửa các files này.
Recovery image200DPI1656×2339, hash `156ee899…`; raw image300DPI2484×3509,
hash `49248da2…`. So render PDF gốc ở300DPI: cùng dimensions nhưng PNG bytes và
decoded RGB pixels đều khác; không thể xác nhận raw binding chỉ bằng tên trang/DPI.
Không suy đoán nguyên nhân khác pixels hoặc tự suy rotate/rescale để ghép tọa độ.

**Dữ liệu còn thiếu chính xác:**

1. Ánh xạ đã kiểm tra từ selector9 tới raw element/line IDs; không dùng text similarity
   để cấp binding, đặc biệt OCR selector9 đang ghép collateral sai.
2. `observed_bbox` đã review cho riêng đoạn(i), gắn exact image hash, kích thước,
   hệ tọa độ pixel và provenance/reviewer; box phải bao trọn hai dòng, loại collateral.
3. Verified binding PDF/page→raw PNG và phép biến đổi rotation/resize/coordinate frame
   nếu dùng hệ ảnh khác. Không dùng tỷ lệ200/300 như chứng minh mapping.
4. Ranh giới đã xác minh giữa đoạn(i) và heading/bullet collateral để chừa lề nhỏ
   mà không lấy nội dung đoạn kế tiếp.

Hai ảnh cắt trong artifact chỉ dùng **inspection các tọa độ có sẵn**, không là trusted
crop hoặc provider input, không đoán vùng mới. Không có eligible crop nên dừng trước
live, không gửi full page/current_text và không tạo correction proposal. Ba lỗi nội
dung đã biết giữ kết luận visual FAIL của lượt trước; không có kết quả OCR mới để
đối chiếu lại hoặc kết luận phục hồi. Giữ PDF30 quarantine và exact H08 selection.

Artifacts local `artifacts/evidence/REC-01/region-audit/`: region-audit.json,
image-binding-check.json, hai unverified inspection PNGs và protected-hashes.json.
Docs-only checkpoint; planning/diff checks, không unit suite/CI lớn hoặc calls trả phí.

## Automatic Evidence Region Binding — tiếp tục REC-01

Baseline `182b288`; REC-01 giữ **REVIEW**, không mở task hoặc vòng tối ưu khác.
Đã triển khai binding/resolver dùng chung và tích hợp recovery; **chưa đạt acceptance
tạo crop đúng trên hai PDF scan thật**. Không gọi Gemini khi geometry chưa đạt.

### Nguyên nhân và code thay đổi

Nhánh raw `_existing_page` đã giữ raw element IDs, nhưng geometry chỉ candidate;
nhánh Gemini `_native_page` tạo `/text_elements/N` độc lập, không có raw IDs.
`adapt_to_m1` cố ý chỉ tạo page anchor vì bbox do model chưa verified. Unified
và DocumentEvidence không nên nâng candidate thành observed bbox. Không có mapping
giữa hai nhánh/ảnh render nên text selector mất đường tới vùng thực tế; đây không
phải lỗi chỉ cần copy bbox từ raw JSON sang anchor là sửa được.

- `region_geometry.py`: sidecar versioned ghim page identity, image hash, dimensions,
  hệ original-image pixels; region IDs, loại, bbox, reading order và selector mapping
  theo unique exact complete-line run/text digest, không fuzzy match/OCR mới/hardcode.
- `gemini_ingestion.py`: khi render PDF mới, lấy vị trí glyph từ PDF text layer
  (nếu có), qua chính PDFium render position converter để xử lý DPI/rotation;
  ingest tự lưu record.geometry. Có thể truyền raw_ocr theo page; chỉ sử dụng nếu
  raw có image_sha256/page/dimensions/coordinate_space đúng chính ảnh render.
- `understanding_pipeline.py`: truyền raw_ocr_pages tới ingest, giữ geometry qua
  persisted replay/unified.source_references; nhánh raw giữ candidate index với
  selector→raw IDs/reading order/bbox/dimensions và lý do chưa verified.
  `document_adapter` hiện hữu đã copy source_references nên không cần sửa M3/M5–M7.
- Resolver kiểm tra exact image/page/frame/text-version, IDs duy nhất, chỉ text,
  thứ tự liên tiếp, khoảng cách dòng/cột, không overlap unselected table/heading,
  có ink và không cắt ink ở viền crop. Margin nhỏ suy ra từ chiều cao dòng, không
  có tọa độ PDF-specific. Bounds hợp lệ đơn lẻ không đủ. Chỉ hỗ trợ paragraph runs
  có layout xác định; text dọc/nhiều cột hoặc ranh giới không rõ bị từ chối.
- `conditional_recovery.py`: sau source-quality trigger và source pins hiện có,
  lấy geometry metadata hoặc dựng lại từ PDF/raw được cấu hình trong storage,
  resolve rồi crop. Chỉ gửi crop + page/selector, **không gửi full page/current_text**.
  Unresolved lưu failure record calls0, không transcription/correction proposal;
  strict schema/approval/quarantine giữ nguyên. Clean decisions không vào resolver,
  không đọc ảnh; không thêm detection vào đường QA sạch.
- `evaluate_region_geometry.py`: runner offline chung nhận danh sách case từ local
  JSON, không hardcode công ty/selector/bbox, không gọi LLM; lưu geometry/resolution
  và chỉ ghi crop khi resolved.

Region IDs `pdf_text_line:*` là vị trí text layer, không giả là raw OCR IDs.
PDF/bitmap transform dựa API renderer; không tự áp tỷ lệ200/300 hoặc swap axes lên
legacy OCR. Text layer/geometry chỉ hỗ trợ source localization, không chứng minh
OCR transcription hoặc claim tài chính đúng.

### Hai PDF thật — cùng thuật toán

| Case và layout | Selector/reference | Kết quả thực tế | Crop/live |
| --- | --- | --- | --- |
| BCC2024 PDF30, trang scan xoay có bảng và đoạn(i)/collateral | /text_elements/9; độc lập đã thấy đáo hạn25/03/2021,collateral riêng và hợp đồng2011 | unresolved:raw_image_hash_or_coordinate_frame_unverified; text layer0chars | Không crop,0calls |
| BBS2025 PDF14, trang portrait gồm thuyết minh và bảng tiền | /text_elements/4, đoạn nhân viên quản lý chủ chốt đã dùng trong QA-01a source audit | cùng reason; text layer0chars | Không crop,0calls |

Input BBS dùng saved M1-15 page14 được composition EXT-01 ghim; không có file đó
trong EXT-01/responses. Lượt runner đầu dừng do sai đường dẫn này sau BCC; giữ
artifacts partial, sửa đúng source path rồi chạy hai case chung, không tuning dữ liệu.
Legacy raw hai trang không có hash ảnh/coordinate frame và kích thước300DPI khác
recovery200DPI. Không tự xác nhận binding từ symbol/year/page hoặc text similarity.
Không có crop thật đủ điều kiện nên **không có live Gemini**, không đánh giá lại
ba lỗi bằng output mới; PDF30 vẫn source-fidelity FAIL ở evidence trước.

### Kiểm thử và ví dụ crop

Final **41focused PASS**:4geometry checks +19conditional +gemini ingestion/
understanding compatibility. Vòng đầu35PASS/6fail do page fixtures dạng
SimpleNamespace chưa có optional geometry; sửa getattr compatibility, không nới
validation. Ruff lint/format PASS; planning/diff checks. Không full1193/CI lớn,
benchmark GEN-02 hoặc rerun H08. Smoke thật `recover_record` PDF30:
blocked/recovery_region_unresolved,0calls, không proposal/approval.

Ví dụ **synthetic, không phải PDF tài chính thật**: fixture PDF text layer mới tự
map và crop dòng “Loan matures 25 March 2021.”, loại heading “Collateral heading”.
Hai render144DPI/0° và216DPI/90° đều giữ đúng dòng qua crop; đã xem PNG độc lập.
File local `automatic-regions/test-output/test_pdf_text_layer_automatic_0/crop-144-0.png`
và `..._1/crop-216-90.png`. Test mới còn kiểm tra ingest→unified→DocumentEvidence
giữ binding, sai hash/text version, thiếu raw-frame, table overlap, paragraph gap;
conditional tests giữ strict output, crop-only/no old OCR và clean-path early exit.
Không dùng synthetic crops như bằng chứng hai scan thật đã đạt.

### Giới hạn còn lại

PDF mới có text layer có thể tự tạo binding/crop trong phạm vi exact, unambiguous
line runs đã test. PDF scan cần raw OCR từ **đúng ảnh render** và coordinate frame
có provenance; mới giữ candidates nếu không đủ điều kiện. Không tự sửa producer
legacy có box/rotation sai, không đọc lại chữ từ pixels bằng OCR engine mới, không
thể phục hồi geometry chỉ bằng text. Reading order raw hiện giữ thứ tự producer;
nếu sai hoặc paragraph nhiều cột, resolver từ chối, không tự suy reorder.
So khớp exact bảo thủ có thể bỏ lỡ source OCR đã sai, thay vì chọn nhầm đoạn.
Layout/ink checks là engineering guards, không detector semantic boundaries hoàn hảo.

Chưa chứng minh tự định vị thành công trên scan mới hoặc hai case thật được yêu cầu;
không báo toàn bộ acceptance đạt. Chưa có crop/live thực tế mới. Fast path giữ early
exit/no ảnh/no resolver theo focused test; chưa đo định lượng overhead E2E mới.
Ingest/startup có thêm text-layer extraction, không tính đó là QA clean request.
H08 activation/policy/accepted repositories/PDF30 quarantine/pending GEN-01a/Web
được đối chiếu hash, không sửa. Private geometry/proposals/images không commit.

Artifacts `artifacts/evidence/REC-01/automatic-regions/`: real-final/results.json,
hai .geometry.json, real-recovery-smoke.json, focused-final.log, test-output PNG/PDF,
protected-before.json. Trạng thái vẫn REVIEW, không tự triển khai producer OCR tiếp.

Next action: Tech Lead review phạm vi đã chạy và gap binding trên PDF scan thật.
