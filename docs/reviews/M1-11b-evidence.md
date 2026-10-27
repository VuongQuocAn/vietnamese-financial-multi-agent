# M1-11b — Quality Gate Refinement & Real Pilot

Cập nhật 2026-10-27 (Asia/Bangkok). **REVIEW**, chờ Tech Lead nghiệm thu độc lập.
M1-11/M1-11a DONE; không tự DONE hoặc bắt đầu M1-12.

## Implementation và validation

Implementation `e3e86a3a879f7865868191e28f09c6e5ecd31fbd` đã push main.
[CI 40509984641](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40509984641)
success trên exact head SHA; Python 3.11/3.12, tất cả steps gồm full unit suite đạt.
Không tải full logs vì không có job thất bại. Local: **68 focused +111 infrastructure
regression +140 DU/extraction regression =319 passed**. Policy revalidation test chạy
lại sau bổ sung unsafe-cache assertion: passed. Ruff lint/format, planning/diff đạt.
Không full local suite, không thêm dependencies hoặc đổi approved contracts.

## Phân tích issue codes và gate

Trước pilot: 19 frozen pages, 17 trang có issues; aggregate **25 sparse_table,
79 empty_cell_text, 2 invalid_bbox_geometry**. Đây là tín hiệu review, không ground truth.
M1-11a blanket gate chặn 4/5 completed pages dù issues có thể ngoài vùng classification.

[Policy/issue matrix](../page-document-classification.md#evidence-aware-quality-policy--m1-11b)
ghi đủ 14 codes hiện hữu từ validate_quality(). Gate dùng source paths để chứng minh
issue disjoint với selected evidence và mọi code/title candidates toàn trang (cần cho
conflict detection). Không xóa bất kỳ text/cell nào khỏi catalog hoặc prompt.

- Blocking toàn trang: invalid_page_dimension, duplicate_id; unresolved_reference_type,
  unresolved_text_reference, unresolved_signature_reference, cell_reference_mismatch.
  References ngoài selected evidence vẫn giữ bảo thủ, chưa nới an toàn/TBD.
- Bbox geometry/outside-page: blocking tại selected/candidate element/cell/line hoặc
  containing table. Chỉ disjoint source scope mới non-blocking.
- Empty cell/line-count: cell scope; sparse/duplicate/negative positions: toàn table.
  Relevant cell bất kỳ trong table khiến topology issue blocking.
- Confidence signature/checkbox không tham gia classification nên disjoint non-blocking.
  Unknown code/path không xác định → uncertain → blocking.
- Code/title phải ở 2 regions độc lập không chồng bbox, enabled label/schema hợp lệ;
  conflicts toàn catalog và DU v1 source linkage giữ nguyên. Không đặt confidence/accuracy.
  Conflict/insufficient/LLM/schema failures giữ lý do riêng, không bị quality issue che.

Trong 9 resolved pages mới, **cả 9** đều có raw issues và đều sẽ bị blanket gate chặn
nếu áp lại trên chính prediction mới. Tổng issues disjoint ở 9 trang này: 17 sparse,
45 empty-cell, 2 bbox. Đã revalidate 18 resolved anchors, code/title độc lập và DU linkage
trên raw; không finding source sai trong kiểm tra này. Candidate labels: 7 B09, 2 B02;
đây là output thử nghiệm, không nhãn tài chính đã nghiệm thu hoặc semantic accuracy.

## Pilot thật và so sánh

Frozen M1-04b manifest giữ nguyên. Chọn đúng 19 pages/order/snapshots M1-11a, phủ 3 mã,
14 strata. Parent có 23 pages/14 strata; không bổ sung trang ngoài selection khi lỗi.
5 completed pages lịch sử là prefix 5 và đã đối chiếu requests/snapshots khớp trước live.

| Chỉ số | M1-11a lịch sử | M1-11b thực tế |
| --- | ---: | ---: |
| Selected / completed real pages | 19 / 5 | 19 / 19 |
| Completed coverage: mã / strata | 1 / 5 | 3 / 14 |
| Actual API requests (gồm smoke) | 6 =1+5 | 20 =1+19 |
| Resolved | 0/5 (0%) | 9/19 (47,4%) |
| Unresolved | 5/5 (100%) | 10/19 (52,6%) |
| OCR quality blocked | 4 | 0 |
| Insufficient / conflicting | 1 / 0 | 10 / 0 |
| Source validation failures | 0 | 0 |
| Schema / provider errors | 0 / 0 | 0 / 0 |
| Quota / local budget errors | 0 / 1 | 0 / 0 |
| Cache / checkpoint hits (gồm probes) | 5 / 0 | 10 / 9 |
| Provider input / output tokens | 12307 / 176 | 48847 / 676 |
| Provider total tokens | 12483 | 49523 |
| Unknown usage / failed requests | 0 / 0 | 0 / 0 |
| Source preservation | Có | Có |

Trên **đúng cùng 5 trang**: trước 0 resolved/5 unresolved (4 quality, 1 insufficient),
sau **4 resolved/1 unresolved** (0 quality, 1 insufficient), resolved rate 0% →80%.
Hai lượt API có prediction riêng, không claim output model bất biến dù temperature0.
Shadow check trên cùng prediction mới ở các resolved pages xác nhận policy là nguyên
nhân chặn dưới blanket gate cũ; không chứng minh prediction đọc đúng tài liệu gốc.
Không so resolved rate toàn mẫu 5 và19 như accuracy hoặc causal financial improvement.

10 unresolved đều insufficient_evidence: title/code/independent region requirement không
đủ theo gate, không nới taxonomy hoặc suy label. 0 quality-blocked không có nghĩa đã
sửa OCR: 17/19 raw pages vẫn có issues, source/provenance giữ nguyên. 43 anchors checked
bao gồm anchors của unresolved candidates; chỉ18 thuộc resolved classifications.

## Requests, quota và cost

Một lượt live duy nhất; 20/20 SDK responses thành công, không retries/rotation/fallback.
Giữ key index0 đã được chọn và các attestations free tier/data export/exclusive scope
trước đây; không log/commit keys hoặc private identifiers. Live marker exclusive vẫn còn.
Không gọi lại Gemini để publish docs hoặc audit checkpoint.

Total input budget mặc định **null**, không còn cap20000; đã xử lý 48847 input tokens.
Không truncate OCR hoặc giảm evidence/model. SDK input bound từng request100000 theo
local resource policy; guard reservation100512 gồm output512, policy TPM250000,
RPM5/RPD20 cho run. Pace >=12,1s trước guard và SDK start; dừng ngay lỗi không retry.
Historical project usage không được khẳng định đã reconstruct: provider quota remaining
vẫn unknown; bounded run allowance không đồng nghĩa tài khoản hết/đủ quota thực tế.

[Google Standard pricing](https://ai.google.dev/gemini-api/docs/pricing) đã kiểm tra lại
27/10/2026: model có free input/output theo tariff; [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
theo project. USD0 chỉ estimate conditional owner-confirmed free tier/tariff;
actual billing/project ID/quota remaining chưa independently verified. Guard monetary
status NOT_CONFIGURED, không gán actual LLMResponse.cost=0 hoặc cho paid fallback.

## Checkpoint/cache và bảo toàn nguồn

QUALITY_POLICY_REVISION=evidence-aware-v1 thêm vào checkpoint config fingerprint,
tách khỏi prediction request fingerprint cũ. Old accepted policy → STALE; schema-valid
prediction tương thích có thể cache HIT rồi revalidate current gate. Prompt/schema/model/
input/source/config/version đổi vẫn invalidate cache; tests giữ source/identity isolation.
Unsafe cached prediction bị current gate reject; integrity HIT không bypass DU validation.

Prior M1-11a cache chỉ RAM đã hết process; 0 resolved checkpoint files, không persisted
prediction đủ điều kiện reuse. Không dựng cache từ aggregate reports hoặc raw inputs.
Trong live mới: 9 checkpoint probes HIT/10 cache probes HIT, network khóa khi probe.
Audit offline sau process: 9 resolved checkpoint records/18 anchors revalidated;
resume trong process riêng với service bị khóa cho 9 HIT, **0 service/API calls**.
Cache compatibility/policy STALE và invalidation kiểm bằng focused integration tests.

Private manifest/dry-run/live-result/audit/resume records ở artifacts riêng M1-11b,
ignored/untracked. Snapshot hash+metadata của selected OCR và binding evidence khớp
trước/sau; original M1-11a manifests/report/interpretation và credential file bất biến.
Không đọc dataset-wide hoặc sửa data/raw, data/processed, crops/PDF và contracts.

## Limitations và nghiệm thu

Không independent reference labels/ground truth, không accuracy/confusion matrix.
Source validation chứng minh linkage và operational code/title rule, chưa chứng nhận
semantic OCR/financial correctness. Unknown/reference issues tiếp tục fail closed;
semantic text/line discrepancies không được validator hiện tại phát hiện vẫn TBD.
Taxonomy provisional và OCR run identity gốc unverified (exact artifact page-only binding).
Một bounded sample không đại diện dataset. Không còn blocker implementation/pilot/CI;
Tech Lead còn phải review gate/scope/evidence và quyết định nghiệm thu độc lập.

Next action: **Tech Lead review M1-11b; giữ REVIEW, không tự DONE/M1-12.**
