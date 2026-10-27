# M1-04a — Evidence kiểm định cấu trúc extraction

Ngày 2026-10-27 (Asia/Bangkok). Engineering validation; local checks đạt, chờ publication/CI.

## Baseline và scope

Baseline `895087deeb06801ff4c67f198f8b1392a7da59de`, main sạch/local/origin khớp sau fetch.
[CI 40430400703](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40430400703)
success đúng SHA Python 3.11/3.12, từng step đã đối chiếu.
M1-03/M1-03f DONE; chỉ M1-04a được triển khai, M1-04/M1-04b vẫn TODO.

Modules mới `extraction_validation`/`extraction_artifacts` compose APIs hiện có;
không sửa contracts/schema versions, loader/resolver hoặc recovery engine.
[API/trust boundary](../extraction-validation.md) mô tả chi tiết runtime model và
các trạng thái chưa xác minh. Không OCR/LLM/API hoặc recovery execution.

## Bounded real smoke

Đã công bố scope trước chạy: tối đa 5 pages từ 5 ledger issues M1-03f, tối đa
100 crop references. Dùng frozen plan/approved local bindings và recovery index
hiện có; không chạy full audit/verify expansion hoặc discovery dataset.
Read-only source/recovery/ledger; output mới riêng
`artifacts/extraction-validation/M1-04a/` bị ignore, exclusive report creation.
Stop conditions: vượt sample limit, source/binding không khớp, non-determinism,
source/output mutation hoặc human issue preservation khác năm.

| Kết quả | Số lượng |
| --- | ---: |
| Pages | 5 |
| Crop references | 50 |
| Raw structure valid / image checked | 5 / 5 |
| Existing original usable | 43 |
| Reconstructed alternatives verified | 7 |
| Missing unrecovered trong mẫu | 0 |
| Human-reviewed bbox issues giữ requires_review | 5 |
| Sparse table / empty cell text quality issues | 10 / 47 |
| Original missing_target giữ nguyên dù có alternative | 7 |
| Run identity not verified | 5 |

Hai lượt/trang cho reports bằng nhau. Hash/size/mtime/inode của JSON/ảnh và selected
recovered PNG/sidecars cùng evidence inputs trước/sau khớp. Metadata size/mtime/inode
của cả 199 PNG + 199 sidecars (398 files) khớp; không hash lại toàn 199 outputs.
Không tuyên bố đã re-hash toàn 193 source JSON/images ở task này: chỉ các nguồn
trong mẫu được đối chiếu, code không có source write/recovery execution.

Năm issues sheets 02/03/08/11/12 được đối chiếu với recovery IDs/hashes/page/element/
bbox và plan context từ ledger thật; không tạo nhãn/hashes thật trong public tests.
Ledger và original crop references không thay đổi; không đóng issue hay chứng nhận
table complete. Original equivalence và OCR/Drive run identity vẫn unverified.

## Synthetic và checks

Targeted tests bản cuối: **61 passed**, gồm recovered-header guard và symlink
targets. Lượt đầu 57 passed/3 skipped do quyền symlink; lượt cuối tạo được symlinks
và toàn bộ cases đã chạy. CI Linux kiểm tra độc lập trên nền tảng đó.
Full local **728 passed/2 skipped**; skips do case-insensitive FS và FIFO không
hỗ trợ Windows. Không có regression; symlink tests đã chạy đạt. Python 3.12.0,
Pillow 12.3.0. Ruff lint/format **85 files**, planning **75 tasks**, pip check và
git diff --check đạt. CI vẫn phải kiểm tra độc lập sau push.

## Private artifacts và giới hạn

Local `smoke.py`, `smoke-report-final.json`, `smoke-summary-final.json` dưới artifacts directory
ở trên giữ reproducibility context; không stage chúng. Tech Lead chỉ cần mở private
reports nếu cần đối chiếu per-file evidence; public report này và
[statistics](M1-04a-statistics.json) chỉ số liệu tổng hợp.
Không commit datasets, original paths, IDs/hashes từng crop, OCR text hoặc secrets.

Smoke chỉ chứng minh validator hoạt động trên mẫu này. Không phải OCR accuracy,
precision/recall, table completeness accuracy, dataset-wide quality hoặc financial
correctness. Trusted FS/TOCTOU/aliases/hardlinks/concurrent writers giữ giới hạn cũ.

## Publication

Implementation/push/exact SHA CI: pending. Không dùng CI baseline thay CI implementation;
không tạo commit tự tham chiếu để nhúng SHA của chính nó. Kết quả exact SHA/CI mới
sẽ ghi trong báo cáo bàn giao sau push. Dừng ở REVIEW khi engineering gates đạt,
chờ Tech Lead acceptance; không tự DONE.
