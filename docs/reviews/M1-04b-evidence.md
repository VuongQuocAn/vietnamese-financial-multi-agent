# M1-04b — Evidence bounded extraction pilot

Ngày 2026-10-27 (Asia/Bangkok). **M1-04b — REVIEW, awaiting Tech Lead acceptance.**
Engineering pilot/local checks/implementation publication/CI đạt; không tự APPROVED/DONE.

## Objective, baseline và scope

Đo reproducible structural/artifact/verification signals bằng validators M1-04a;
không phát triển OCR/extraction model, không đo accuracy hoặc financial correctness.
M1-04a được Tech Lead APPROVED engineering 2026-10-27 và finalize DONE tại
6bfd43209d47ada1f236f8619ebc876c47c60f28;
[CI 40435213198](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40435213198)
success exact SHA, mọi steps Python 3.11/3.12 đã kiểm tra. Baseline phiên
d78232028f619cb6416a89b2bbe5735f4d09d023 sạch/fetch/origin khớp.

Chỉ thêm runner/CLI/tests/docs trong document_processing boundary. Không đổi
validators, contracts, recovery engine hoặc raw/processed/recovered/index/ledger.
Không LLM/API/Drive download, recovery hoặc full dataset run.

## Dataset subset và methodology

[Protocol/spec](../../planning/tasks/M1/M1-04b.md) chốt trước đọc thêm dữ liệu thật.
Existing M1-01 inventory được intersect với M1-03f approved plan/bindings: pool
193 pages thuộc 14/15 strata, khác toàn OCR inventory 500 pages. Không scan corpus,
không suy statement type/run identity từ filename hoặc tuple symbol/year/page.

Reserve năm pages có human-reviewed issues vào risk, coverage một page/stratum
từ phần còn lại, sort diversity element types/cells giảm dần rồi exact source tăng
dần. Risk bổ sung bốn pages theo invalid bbox/empty text/sparse/missing crop signals.
Duplicate positions **not_observed_in_candidate_metadata**: zero candidate trong
approved pool, không tạo synthetic thật hoặc mở rộng scope để lấp signal.
Không budget omissions, không loại trang sau khi validator trả issue.

| Scope | Coverage | Risk-focused |
| --- | ---: | ---: |
| Selected pages | 14 | 9 |
| Processed / selected pages | 14/14 | 9/9 |
| Failed / selected pages | 0/14 | 0/9 |
| Expected / observed crop occurrences | 331/331 | 67/67 |
| Unverified crop occurrences / expected | 0/331 | 0/67 |
| Elements theo selected inventory metadata | 405 | 194 |
| Tables theo selected inventory metadata | 15 | 24 |
| Cells theo selected inventory metadata | 1.202 | 693 |

Tổng **23 pages/398 references**, dưới trần **30/500**. Coverage **14/15** tổ hợp
BBS/BCC/BED × 2021–2025; thiếu **BCC/2025** vì không có approved page binding trong
pool được giao. Không tự xác minh/mapping thêm trang ngoài pool. Hai nhóm không trùng.
Các số elements/tables/cells chỉ mô tả metadata của subset, không phải số đối tượng
đã được human annotation. Không dùng chúng làm denominator cho accuracy.

Cả hai nhóm đều purposive. Pool 193 đã thiên về crop thiếu từ audit cũ, nên coverage
theo mã–năm cũng không đại diện phân bố tự nhiên corpus. Risk frequencies chỉ mô tả
các trường hợp chủ đích; không gộp hai nhóm thành ước lượng tỷ lệ lỗi dataset.

## Manifest, execution và reproducibility

Protocol **bounded_extraction_pilot_v1**. Default preflight → explicit freeze → first
→ second theo [CLI/API policy](../extraction-pilot.md). Manifest frozen trước gọi
validate_extraction; chứa exact membership/group/reasons, artifact references,
expected identities, approved mappings/image bindings, evidence context và snapshots.
Digest manifest không tự chứa chính nó. Không overwrite hoặc sampling lại khi execute.

Hai canonical reports bằng nhau hoàn toàn; report digests và manifest binding khớp.
Mỗi invocation kiểm tra selected inputs trước/sau đọc và sau ghi output. Đối chiếu
cuối độc lập vẫn khớp **472 snapshots: 390 file hiện có và 82 file absence**; gồm
selected JSON/raw images/original crops, evidence inputs và **28 recovered files**
(14 PNG/14 sidecars). Không hash lại toàn 199 recovered crops hoặc toàn corpus.
Full manifest/report digests, membership, per-page/runtime tokens và fingerprints
chỉ ở ignored local artifacts; không công bố IDs/hashes/path nguồn trong evidence này.

**2 lượt**, determinism đạt, **0 conflicts/0 failures**, không input mutations quan
sát được trong phạm vi selected hashes/metadata/absence checks. Ngoài tập selected
không có full-content proof; runner không có source write/recovery execution.
Các tests synthetic kiểm tra riêng idempotence, manifest/output conflict, nguồn đổi
giữa lượt/trong lượt, không chọn lại trang và từ chối ghi đè khi nondeterministic.

## Structural và JSON–image consistency

| Page-level numerator / selected-page denominator | Coverage | Risk-focused |
| --- | ---: | ---: |
| Raw structure valid | 14/14 | 9/9 |
| Raw structure invalid / not_verified | 0/14, 0/14 | 0/9, 0/9 |
| Image checked | 14/14 | 9/9 |
| Image invalid / not_verified | 0/14, 0/14 | 0/9, 0/9 |
| Caller-bound nhưng run unverified | 14/14 | 9/9 |
| Ledger consistent | 14/14 | 9/9 |

Không dimension mismatch, bbox_outside_image hoặc source-binding mismatch trong mẫu;
không biến absence của issue thành chứng nhận nội dung ảnh và OCR cùng run.
Raw structure valid vẫn có quality issues. Understanding **not_supplied**: không có
UnderstandingResult thật được giao, không tạo giả; validation corresponding N/A.

## Crop availability — reference-occurrence level

| Numerator / expected reference denominator | Coverage | Risk-focused |
| --- | ---: | ---: |
| Existing original usable | 261/331 | 55/67 |
| Reconstructed alternative verified | 2/331 | 12/67 |
| Missing unrecovered | 68/331 | 0/67 |
| Original mapping resolved | 261/331 | 55/67 |
| Original mapping missing | 70/331 | 12/67 |
| Original mapping unsafe/unmapped/ambiguous | 0/331 | 0/67 |

Tổng vận hành **316 original, 14 reconstructed, 68 unrecovered**, đơn vị reference
occurrences. **82 original missing** vẫn missing, dù 14 có alternative dùng được;
không gộp reconstructed vào original availability. Recovery giúp truy cập vùng ảnh
cho 14 table references; 68 non-table/view references vẫn không có alternative
được xác minh. Không recovery thêm hoặc coi mọi missing crop tái dựng được.
Selected recovery alternatives qua index/canonical binding/sidecar/hash/pixel checks;
không recovery verification failure trong mẫu. Original equivalence vẫn unverified.

## Structural, quality và artifact findings

Các số dưới đây là **issue occurrences; ngoặc là số pages có code / selected pages**.
Một page có thể chứa nhiều code; không cộng page counts để suy số pages lỗi duy nhất.

| Code | Coverage (14 pages) | Risk-focused (9 pages) |
| --- | ---: | ---: |
| sparse_table | 13 (11/14 pages) | 15 (6/9 pages) |
| empty_cell_text | 34 (2/14 pages) | 61 (3/9 pages) |
| invalid_bbox_geometry | 0 (0/14 pages) | 2 (1/9 pages) |
| source_bbox_incomplete_table | 0 (0/14 pages) | 5 (5/9 pages) |
| duplicate_cell_position | 0 (0/14 pages) | 0 (0/9 pages) |
| bbox_outside_image / line_count_mismatch | 0 / 0 | 0 / 0 |

Quality **47/83 occurrences**, artifact **152/21 occurrences**, structural **0/0**
(coverage/risk). Artifact breakdown: missing_target **70/12**, recovery_entry_missing
**68/0**, run_identity_not_verified **14/9**. Runtime issue statuses not_verified
**82/9 occurrences**, không phải số trang. Tổng **199/104 issues**, có provenance/
source field paths trong private per-page reports; không có quality score/pass threshold.

Sparse grid và empty text xuất hiện nhiều nhất trong quality signals. Chúng có thể
phản ánh ô trống/merged cells/layout hoặc OCR thiếu; chưa có annotations để kết luận
recognition sai. Không sửa lưới/text để giảm số issues. Hai invalid geometry issues
cần kiểm tra trước dùng coordinates downstream. Missing crop views hạn chế evidence
retrieval dù JSON parse được. Run identity chưa xác minh ở mọi page giới hạn provenance.
Raw parse success không cho phép tự chuyển tất cả dữ liệu vào financial normalization.

## Human review

Ledger có đúng **5 issues**, đều gắn vào năm selected risk pages; **5 requires_review**,
**0 human issue not_verified**, **0 ledger inconsistent pages** trong mẫu.
Giữ nguyên năm issues M1-03f sheets 02/03/08/11/12; không thay attribution/bbox/status.
Ledger consistency chứng minh recorded binding, không xác thực chữ ký reviewer.
Pixel-faithful alternatives không chứng minh đầy đủ bảng hoặc hết vấn đề bbox.

## Tests và security

Targeted cuối: **40 passed**, gồm deterministic selection/dedup/bounds/missing
strata/bindings; mutated manifest, freeze rerun/conflict; valid/structural failures,
missing/unsafe image, missing original/verified alternative/invalid recovery;
source mutation/error isolation/human preservation; denominators/page union,
not_verified/empty groups; output conflict, path traversal, symlink/junction,
public allowlist và ignored/untracked datasets/artifacts.

Full suite bản cuối: **768 passed/2 skipped** (192,45 giây local Windows).
Lượt trước regression page-union: 767 passed/2 skipped; targeted cuối đạt 40.
Windows skips chỉ case-insensitive filesystem và FIFO không được os.mkfifo hỗ trợ;
symlink/junction test pilot đã chạy đạt, không tính skipped như passed.
Ruff lint/format, planning **75 tasks**, pip check/diff check đạt;
đã kiểm tra lại sau cập nhật docs. CI synthetic bên dưới không phải real pilot.

## Giới hạn và downstream recommendation

Không có approved quality thresholds/ground truth, OCR rerun, accounting validation,
Understanding output hoặc xác nhận original Drive/run identity. Không CER/WER,
precision/recall, completeness accuracy, financial accuracy hoặc global readiness.
Nguồn trusted local FS; TOCTOU/hardlinks/aliases/concurrent writer limitations giữ nguyên.
Coverage thiếu BCC/2025 và khung sampling thiên về crop thiếu; không extrapolate.
985 existing/572 missing/199 recovered của M1-03 là lịch sử audit, không thay số pilot.

Đề nghị Tech Lead nghiệm thu **engineering protocol/provenance/repeatability** khi
review code/manifest methodology/results/CI đạt. Giữ issues cho downstream review,
đặc biệt bbox completeness/geometry và crop views chưa khả dụng. M1-04 cha **TODO**
cho đến quyết định nghiệm thu riêng; M1-05 không bắt đầu. Không đề nghị dataset-wide
quality pass hoặc tự đóng năm human issues.

## Git/CI và evidence access

Public [statistics](M1-04b-statistics.json) dùng fixed numeric/boolean/enum allowlist;
không original/source paths, OCR text, financial values, IDs hoặc hashes từng file.
Private manifest.json, first.json, second.json, canonical-report.json, verification.json
ở ignored artifact directory của task; Tech Lead có thể yêu cầu local review riêng
để đối chiếu membership/bindings/full digests và runtime provenance.
Implementation **4a2a4ed4ae09924e073448029e884b030f61bc27** đã push main, fetch/local/
origin/main khớp, working tree sạch trước checkpoint REVIEW.
[CI 40437144971](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40437144971)
**success exact SHA**; Python 3.11/3.12 install/lint/format/planning/unit/post steps
đều success. Logs mỗi job **759 passed/11 skipped**. CI Linux skips: Windows runtime
syntax (5) và native junction (6); local Windows kiểm tra độc lập. CI không có real
dataset, không chứng minh financial quality hoặc thay selected integrity checks local.

Đã stage đúng 11 allowlisted files; rà cached diff và source paths/keys/full digests,
ignore/index: không datasets/private artifacts/.env. Không sửa production validators,
contracts/recovery hoặc human ledger. Checkpoint REVIEW tiếp theo chỉ docs/planning;
exact SHA/CI checkpoint đó kiểm tra sau push, ghi báo cáo cuối, không self-reference.
