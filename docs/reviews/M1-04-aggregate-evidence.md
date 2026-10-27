# M1-04 — Aggregate acceptance evidence

Ngày 2026-10-27 (Asia/Bangkok). **REVIEW — chờ Tech Lead xác nhận cuối cùng**.
Đây là đối chiếu tổng hợp của Software Engineer theo giao việc mới, không phải
quyết định APPROVED/DONE cho parent. [Spec parent](../../planning/tasks/M1/M1-04.md).

## Phạm vi và điều kiện bắt đầu

Roadmap M1-04 yêu cầu validators và bounded pilot đạt, có evidence cấu trúc,
provenance/tái kiểm tra, nêu giới hạn chất lượng và không sửa dữ liệu để hết lỗi.
Không suy parent đạt chỉ từ trạng thái DONE của task con.

Baseline phiên 7b0bc52dd44cded9bfb5cc0a668433c4ff9b9576 sạch/fetch/origin khớp;
[CI 40437415893](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40437415893)
success exact SHA, từng step Python 3.11/3.12 được kiểm tra lại.
Checkpoint 1 finalize M1-04b tại **a0ffaaff317c046bebd023c9305b1303ddcf8451**,
đã push main/local/origin khớp;
[CI 40439127716](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40439127716)
**success exact SHA**, mọi steps Python 3.11/3.12, mỗi job **759 passed/11 skipped**.
Chỉ sau gate này mới thực hiện aggregate review và chuẩn bị parent REVIEW.

| Dependency | Status xác minh | Evidence |
| --- | --- | --- |
| M1-03 | DONE | Implementation 5c3f4d0e47127c37c90cf6a0b65cb65f4fcac3d2 / [CI 40312411308](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40312411308) success đúng SHA; registry DONE |
| M1-04a | DONE | Tech Lead APPROVED engineering; acceptance 6bfd43209d47ada1f236f8619ebc876c47c60f28 / [CI 40435213198](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40435213198) success đúng SHA |
| M1-04b | DONE | Tech Lead APPROVED 2026-10-27; acceptance a0ffaaff317c046bebd023c9305b1303ddcf8451 / CI 40439127716 success đúng SHA |

## M1-04a — kết quả Tech Lead đã APPROVED

Implementation **32a3d23362f494fe8a39fa8ed9b3983841e4f287** /
[CI 40432840930](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40432840930)
success đúng SHA, kiểm tra lại trong phiên này. [Spec](../../planning/tasks/M1/M1-04a.md)
ghi quyết định APPROVED engineering ngày 2026-10-27; [evidence](M1-04a-evidence.md)
giữ lịch sử checkpoint REVIEW trước approval, không coi nhãn cũ là trạng thái hiện tại.

Composition Raw OCR/Understanding validators, JSON–image dimensions/bounds,
source binding, original/reconstructed availability và recovery/ledger checks.
Structural/quality/artifact và not_verified giữ semantics/provenance riêng;
không sửa versioned contracts hoặc recovery engine.
Historical local tests **728 passed/2 skipped**, targeted **61 passed**;
CI implementation **719 passed/11 skipped** mỗi job. Smoke lịch sử **5 pages/50 refs**,
43 original/7 reconstructed, giữ 5 human bbox issues. Đây là smoke engineering,
không cộng vào sample/denominators của M1-04b hoặc coi là financial evaluation.

## M1-04b — kết quả Tech Lead đã APPROVED

Implementation **4a2a4ed4ae09924e073448029e884b030f61bc27** /
[CI 40437144971](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40437144971)
success exact SHA, Python 3.11/3.12 từng step đạt. Approval chỉ engineering protocol,
provenance, implementation và repeatability. [Evidence](M1-04b-evidence.md),
[statistics](M1-04b-statistics.json), [protocol](../../planning/tasks/M1/M1-04b.md).

| Kết quả / đơn vị | Coverage | Risk-focused |
| --- | ---: | ---: |
| Processed / selected pages | 14/14 | 9/9 |
| Raw valid / selected pages | 14/14 | 9/9 |
| Image checked / selected pages | 14/14 | 9/9 |
| Observed / expected reference occurrences | 331/331 | 67/67 |
| Existing original / reference occurrences | 261/331 | 55/67 |
| Reconstructed alternative / reference occurrences | 2/331 | 12/67 |
| Missing unrecovered / reference occurrences | 68/331 | 0/67 |
| Human bbox issues giữ requires_review / issue occurrences | 0 | 5 |

Giữ sample **23 pages/398 refs**, không tăng lên trần 30/500. Hai nhóm không trùng;
pool approved 193 là tập audit crop thiếu, khác toàn OCR inventory. Coverage 14/15
strata, thiếu BCC/2025. Hai nhóm purposive; không ngoại suy tần suất lỗi toàn corpus.
Sparse-table signals 28, empty-cell-text 95, invalid bbox geometry 2; không coi chúng
là nhãn OCR sai hoặc tự đặt quality pass threshold. Original missing vẫn **82**,
gồm 14 references có alternative, không gộp alternative vào original crops.

Theo local evidence đã được Tech Lead duyệt: **2 lượt deterministic**, canonical
reports/digests/membership bằng nhau; **472 selected snapshots unchanged** gồm
390 files và 82 absence states. Chỉ 28 selected recovered files được hash;
không hash toàn 199 outputs/corpus. Không conflict/failure trong pilot thực tế.
Private manifest/reports/fingerprints không đưa vào aggregate report hoặc Git.

## Parent aggregate review — đối chiếu từng tiêu chí

| # | Tiêu chí kiểm tra | Bằng chứng đối chiếu | Kết quả engineering |
| --- | --- | --- | --- |
| 1 | Validators đúng contracts | Approval M1-04a, contract/quality tests và API; ba versioned contracts/schema giữ nguyên | Đạt |
| 2 | Pilot dùng validators đã nghiệm thu | extraction_pilot.py import/call trực tiếp validate_extraction tại execute_manifest; không implementation validator thay thế | Đạt |
| 3 | Không regression/thay contracts ngoài scope | Git diff từ 32a3d23 đến a0ffaaf rỗng cho extraction_validation/extraction_artifacts, contracts, schemas và crop_recovery; full suite mới/CI checkpoint 1 đạt | Đạt |
| 4 | Sampling/frozen manifest có evidence | Protocol chốt trước real reads, deterministic selection, explicit freeze trước execution, immutable/conflict tests; approved evidence 23/398 | Đạt |
| 5 | Denominators và provenance rõ | Pages/references/issue occurrences riêng, coverage/risk riêng, source binding/tokens/field paths giữ trong private runtime reports | Đạt |
| 6 | Repeatability trong phạm vi local evidence | Hai canonical reports/digests và 472 selected snapshots khớp theo evidence được duyệt; rerun/conflict/mutation tests | Đạt |
| 7 | Human issues giữ nguyên | 5 requires_review, ledger consistent trong mẫu; tests cả structural/input failure, không tự đóng issue | Đạt |
| 8 | Raw OCR/ảnh gốc không sửa để hết lỗi | Selected integrity evidence và read-only execution; phiên finalization/aggregate chỉ docs/planning, không đọc lại hoặc ghi dataset/manifest | Đạt trong phạm vi evidence |
| 9 | CI/registry nhất quán | Dependencies DONE; CI checkpoint 1 success exact SHA, registry/spec/dashboard/planning checks đồng bộ; CI checkpoint parent kiểm tra riêng sau push | Đạt tại baseline; publication parent cần CI mới |
| 10 | Không blocker engineering bị bỏ sót | Không blocker mới qua code/evidence/diff/tests; các giới hạn bên dưới được giữ rõ | Đạt, chờ Tech Lead quyết định cuối |

Kết luận đối chiếu: đủ bằng chứng kỹ thuật cho **M1-04 REVIEW** theo scope roadmap.
Việc Tech Lead xác nhận aggregate cuối cùng **chưa đạt/chưa được cung cấp**;
parent không DONE. Hai task con đã APPROVED không thay thế quyết định này.

## Những giới hạn chưa giải quyết

- Năm human bbox issues chưa sửa; reconstructed pixels không chứng nhận table
  completeness hoặc original crop preprocessing/equivalence.
- Coverage BCC/2025 thiếu; approved pool thiên về missing crops. 68 unrecovered
  references vẫn hạn chế evidence retrieval; không chứng minh dataset-wide readiness.
- Original equivalence/Drive run identity chưa xác minh; mọi pilot page chỉ caller-bound
  với run unverified. Ledger consistency không phải xác thực reviewer bằng chữ ký.
- Không ground truth, OCR/financial accuracy evaluation, approved quality thresholds
  hoặc UnderstandingResult thật; không fake output hoặc nhãn để lấp chỗ thiếu.
- Trusted local FS/TOCTOU/hardlinks/aliases/concurrent writers vẫn giới hạn hiện hữu;
  selected snapshots không chứng minh toàn corpus bất biến.

## Checks và publication của phiên finalization/aggregate

Local mới theo giao việc: **768 passed/2 skipped**, 192,12 giây. Skips tách riêng:
case-insensitive filesystem và FIFO/os.mkfifo không hỗ trợ Windows. Ruff lint/format,
planning **75 tasks**, pip check, git diff --check đạt. CI checkpoint 1: **759 passed/
11 skipped** mỗi job Python 3.11/3.12; Linux skips Windows syntax/junction cases.

Parent checkpoint chỉ docs/planning, dùng lại full unit result mới của cùng source
code; chạy lại planning/diff checks sau chỉnh tài liệu, không lặp full suite vô cớ.
CI parent commit mới phải kiểm tra exact SHA sau push, không suy CI cũ cho commit mới.
Đây là synthetic checks; không rerun pilot, đọc dataset, thay frozen manifest,
hash lại nguồn, OCR/LLM/recovery hoặc sửa validators/statistics trong phiên này.

Stage chỉ allowlisted docs/planning, kiểm tra private paths/keys/full fingerprints,
ignore/index. Commit/CI checkpoint parent mới ghi ở báo cáo cuối sau xác minh,
không thêm commit tự tham chiếu SHA/CI của chính nó.

## Exact Next Action

Tech Lead review M1-04 aggregate acceptance; do not start another task.
