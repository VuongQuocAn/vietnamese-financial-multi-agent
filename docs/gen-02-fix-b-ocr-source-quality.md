# GEN-02-Fix-B — OCR Source Quality & Controlled Evidence Correction

Ngày09/11/2026, baseline `46aa45f`; status **REVIEW có P1 release blockers**.
Implementation `d78f1159517de6437bd039d5030040f2d05013b6` đã push main,14files.
[CI42549793493](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42549793493) completed/SUCCESS đúng implementation SHA; 1169 Python/9 Web PASS; full regression manual SKIPPED.

## Source audit

H08 BCC2024 PDF16, `/text_elements/7`: bản in ghi “người nợ **khó có khả năng
thanh toán**”; OCR ghi “người nợ **có khả năng thanh toán**”. Đây là sai khác
material về điều kiện trích lập dự phòng. RCA GEN-02 trước đó đọc nhầm thành
“không có khả năng thanh toán”; task này xác nhận lại PDF gốc ở crop phóng đại,
không dùng diễn giải cũ làm oracle. Original OCR, discrepancy/oracle cũ và accepted
release giữ nguyên; correction mới phải giữ đúng từ “khó”. Không có runtime keyword rule.

PDF SHA256 `866d6c9e212079c47974bddb2bdf0305ecf40008950a23fa5af856d50ee4ab5b`;
page image200dpi `842d9d43737cdd9266632fde46df3f468c495403dc99573096eec54fdc7e0f2a`.
Record/snapshot/full quote và source fingerprints giữ trong artifacts task.

## Workflow và authority

Original → PDF visual review → PROPOSED → VALIDATED → versioned candidate →
Tech Lead approval riêng → retrieval → M6 → Ledger → M7/Firewall.

Tái sử dụng EvidenceIdentity, page bindings, immutable repositories, composition
pins và atomic JSON. Validation kiểm tra original payload/pin/text, exact render,
PDF/page/image/selector và visual transcription có reviewer/reference; không tuyên
bố thuật toán tự xác minh ngữ nghĩa. Approval là operator-controlled record riêng
bind exact release digest, không phải model self-confirmation hay correction field.
Chưa có Tech Lead approval cho actual H08; candidate giữ pending. Fixture approval
chỉ chứng minh engineering workflow, không phải phục hồi accepted production release.

Current source policy ngoài raw evidence chặn confirmed material original identity
và pending correction tại M6/admission/replay. Ledger giữ entry cũ trên đĩa, lọc khỏi
trusted retrieval khi bị revoke, không chặn các claims sạch khác. Current trust không
được cache theo payload cũ. New snapshot/composition/pins/content digest khác bản cũ;
old proof không chứng minh changed text. Source-quality flags cũ vẫn giữ nguyên.

## Targeted results và independent audit

| Test | Expected | Actual | Correct |
| --- | --- | --- | --- |
| H08 trước source policy, sau Fix-A | Đo baseline thực tế | M6 ACCEPT1, phát hành OCR sai trong probe ledger riêng | Không; lỗi được xác nhận |
| H08 original sau confirmed review | Block defective text | verification_blocked, INVESTIGATE1,0claims/citations | Có |
| H08 corrected pending | Không phát hành corrected text | verification_blocked, INVESTIGATE1,0claims/citations | Có |
| Actual approved correction | Chỉ chạy nếu có approval thật | Chưa approved/released; không chạy accepted production recovery | Pending authority |
| Approved-state isolated fixture | Chứng minh pipeline với authority fixture | ACCEPT1, completed_with_caveats; đúng toàn bộ corrected paragraph/PDF16/selector7 | Có, chỉ fixture |
| Wrong document/snapshot/release/content/selector | Reject | Negative controls PASS tại M6/pin/proof checks | Có |
| No PDF proof, unapproved, cleared flags, suspected review | Reject/review required | Negative controls PASS; không tự approve | Có |
| Old proof dùng cho corrected version | Reject | ABSTAIN; current admission/replay rejected | Có |
| Unaffected ledger | Bảo toàn |17original accepted claims replay, bytes/hash không đổi | Có |
| QA-01b A7 | Financial useful partial, block defective document | ACCEPT1/INVESTIGATE1, partial_verified_coverage | Có |

H08 fixture dùng PDF thật và correction đã validated, nhưng approval record có nhãn
SYNTHETIC và nằm trong policy root/ledger riêng. Active operator policy có **0approvals**;
không có actual accepted corrected release. Request fixture/pending bind explicit
composition fingerprint và correction snapshot; không chọn latest hoặc fallback parent.
Independent audit so quotations với visual transcription và original PDF, không chỉ
dựa M6 ACCEPT; citations bind đúng PDF16/new snapshot/selector7. Gateway/provider calls0.

Một control về quyền sử dụng đất vẫn tìm được đoạn policy đúng PDF17/selector10,
nhưng M5 còn xuất thêm các đoạn rộng hơn: một claim chứa lỗi material PDF30/selector9.
Không coi trạng thái completed/M6 ACCEPT của control này là full PDF correctness.
Sau independent review, record30/9 được quarantine bằng cơ chế chung, current ledger
lọc claim đó dù đã warm cache; admission/replay từ chối, file ledger giữ nguyên.
Hai claims khác và required land-policy clause vẫn visible. Không chạy lại QA để nâng score.

## Additional audit — đúng5đoạn

| Source / selector | Risk | PDF comparison / disposition |
| --- | --- | --- |
| BCC2024 PDF17/10 | Phủ định | Khớp nội dung quyền sử dụng đất không trích khấu hao |
| BCC2024 PDF17/11 | Phương pháp,3–8năm | P2 thiếu “dựa” trong “đường thẳng dựa trên”; chưa correction/release |
| BCC2025 PDF13/23 | Ngoại lệ/điều kiện12tháng | Khớp nội dung trọng yếu |
| BBS2025 PDF11/15 | Thời gian/phân loại | P2 thiếu “hữu” trong “thời gian sử dụng hữu ích”; chưa correction/release |
| BCC2024 PDF30/9 | Sự kiện/ngày từ extra E2E quote | P1: OCR lẫn collateral text và biến ngày đáo hạn thành ngày hợp đồng; confirmed/quarantined, chưa replacement release |

Bốn đoạn đầu chọn có chủ đích theo nhóm rủi ro, đoạn thứ5 do output audit phát hiện
event/date đáng ngờ. Crop phóng đại xác minh các chữ bị thiếu. Đây không phải mẫu
ngẫu nhiên hoặc corpus OCR accuracy. PDF30 thực sự in ngày đáo hạn25/03/2021;
không tự sửa thành năm khác theo suy đoán kế toán. Chỉ lập review/quarantine cho
P1 bổ sung, không làm thêm release hoặc full-corpus cleanup.

Safety counts phải tách: H08 after-policy/pending không release sai; approved-state
fixture1claim khớp PDF. Control mở rộng từng phát hành **1material OCR claim sai trước
independent review**; sau review có0known-material claims visible trong ledger đó.
Không báo toàn task0unsupported một cách tuyệt đối, không coi source-coordinate
fidelity là OCR text accuracy. P2 lexical và các extra passages chưa audit đầy đủ vẫn
là giới hạn; cơ chế này chặn lỗi đã review, không tự phát hiện mọi OCR discrepancy.

## Validation và review package

Hai vòng implementation/test: nhóm65 PASS trước bổ sung suspected-review và
immutable-history checks; final66 PASS gồm12correction tests (10negative cases)
và document verification, ledger, BM25, composition compatibility. Các nhóm overlap,
không cộng thành số tests độc lập. Ruff lint/format5Python files PASS.
Actual final E2E chạy một lần; additional review chỉ thay trust state, không tune runtime.
Original38approved input files,4GEN-02 frozen files và inherited GEN-01a/Web phải
giữ nguyên; runtime lock ghi trước actual final execution. Không OCR/Gemini/full40
hoặc Fix-A fresh rerun. CI đã SUCCESS đúng implementation SHA; full regression manual SKIPPED.

Artifacts local `artifacts/evidence/GEN-02-Fix-B/`: `source-discrepancy.json`,
`correction-{proposal,validated}.json`, `candidate/{composition,release}.json`,
`additional-source-audit.json`, `additional-material-review.json`, `final-e2e.log`,
`final/{audit,reviewed-audit,old-proof-controls,legacy-compatibility}.json`,
`final-regression.log`, `final-A7/`. Raw actual traces được giữ nguyên; final RCA và
source-fidelity corrections nằm ở reviewed audit, không overwrite raw QA outcomes.

H08 correction digest `9c5e9844bfb584c4747625435c22f1082148246208844d31559f6041570d5229`;
candidate composition fingerprint `a7ba94c8ac7ca3dd039971008ee7cd841da93af6b93f5e1cb3d98e3c0b73a920`;
release digest cần authority bind là `082d30e483d2a0133d696e923c90a1a555aaf993e49da6bb9a200a5cfd6625bc`.
Active local trust store: `artifacts/source-quality/document-source-policy.json`,
cấu hình DOCUMENT_SOURCE_POLICY_ROOT; đi cùng dữ liệu triển khai, không commit private
reviews vào Git. Store giữ validated reviews/release history bất biến qua save API;
approvals tách riêng. Các fixtures không phải Tech Lead approval thực tế.

## Remaining blockers

P1: Tech Lead cần review chữ “khó”, provenance và exact H08 release digest trước khi
approve/promotion. Đề xuất giữ current quarantine và chỉ promote version có explicit
decision reference. PDF30/9 là P1 quarantine-only cần follow-up riêng nếu muốn recovery;
P2 lexical và overbroad extra excerpts ghi nhận, không sửa ngoài scope. Source workflow
text-only/selector-level, không tự clear inherited pdf_review flags. Chưa có actual
accepted corrected release, không tự DONE hoặc bắt đầu task tiếp theo.

## Closure — persistence, startup và promotion preflight

Tech Lead chấp nhận implementation `d78f115`, chưa approve H08 promotion; giao closure
nhỏ ngày09/11/2026. Closure không tạo approval thật hoặc tự chuyển DONE.

Root tương đối nay neo vào source project, nên đổi cwd không làm mất quarantine.
Configured store bị thiếu hoặc pin sai sẽ chặn API startup; M6/replay cũng fail closed.
Startup ghi canonical policy fingerprint trong app.state, không đưa source text vào API.
DOCUMENT_SOURCE_POLICY_SHA256 là `payload_sha256(policy.model_dump(mode="json"))`,
không phải hash bytes của JSON có whitespace. Môi trường có reviewed data cần giữ
DOCUMENT_SOURCE_POLICY_ROOT và pin cùng dữ liệu. Legacy không cấu hình/no store vẫn
empty; không dùng chế độ đó để triển khai dataset đã review.

17targeted tests PASS (correction + API), gồm3closure tests: persisted fixture approval
qua process/root/cwd khác; startup thiếu/sai policy bị chặn; exact release preflight
không tự cấp approval. Approval dương chỉ thuộc synthetic unit fixture.

Actual closure copy policy, candidate manifest/repository/release, PDF, saved-page,
review images và old ledgers vào root khác; so hash nguồn/đích, khởi động process/API
mới rồi kiểm tra candidate thật. Không chạy lại full QA hoặc tạo source correction mới.

| Check thật sau restart/transfer | Result |
| --- | --- |
| Policy canonical digest | `4f642dd00425612e45ce6bf90ab2b7d253e6cdad5a27a78ca559ab5c51fa036c` |
| Quarantines / actual approvals |2 /0, giữ PDF16 và PDF30 |
| H08 expected release digest | `082d30e483d2a0133d696e923c90a1a555aaf993e49da6bb9a200a5cfd6625bc` |
| Registered release/composition/content/selectors/PDF provenance | PASS |
| Promotion preflight | pending_approval, chỉ thiếu approval |
| Wrong expected release digest | blocked |
| Old H08 / PDF30 defective claims visible |0 /0;2claims khác trong ledger control vẫn visible |
| Accepted release / source files / old ledger bytes | Không thay đổi |

Artifacts local `artifacts/evidence/GEN-02-Fix-B/closure/`:
`restart-transfer-promotion.json`, `transfer-manifest.json`, `real-check.log` và
`moved-environment/`. Đây là mô phỏng chuyển storage/cwd/process trên cùng máy,
không tuyên bố đã deploy máy khác. PDF render phải tái lập đúng binding đã lưu;
fingerprint sai sẽ block thay vì âm thầm rebind. Khi có approval thật, phải giữ PDF30
review/quarantine trong policy, bind đúng H08 release digest rồi cập nhật deployment
pin và chọn composition có kiểm soát. Không dùng lại fixture approval.

Closure chưa commit/CI. Next action: hoàn tất checkpoint closure để Tech Lead review;
H08 actual promotion vẫn chờ quyết định riêng.
