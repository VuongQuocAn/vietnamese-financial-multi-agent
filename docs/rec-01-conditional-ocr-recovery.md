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

Next action: Tech Lead xem lỗi structured output còn chặn transcription đầu-cuối.
