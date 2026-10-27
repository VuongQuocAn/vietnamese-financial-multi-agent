# Progress Dashboard

Cập nhật: **2026-10-27** (Asia/Bangkok). Nguồn duy nhất: [Registry](tasks.md).
Đếm task đã đăng ký, không đo khối lượng hoặc chất lượng nghiên cứu bằng tỷ lệ.
Ba task cha M1-02/03/04 cũng được đếm; task con không được coi là phần trăm tiến
độ của cha. Khi tách/thêm task, cập nhật cả registry và dashboard trong cùng thay đổi.

## Số task theo milestone và trạng thái

| Milestone | Total | DONE | IN_PROGRESS | BLOCKED | TODO | READY | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M0 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| M1 | 25 | 11 | 0 | 0 | 13 | 0 | 1 |
| M2 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M3 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M4 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M5 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| M6 | 6 | 0 | 0 | 0 | 6 | 0 | 0 |
| M7 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M8 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| TOTAL | 75 | 15 | 0 | 0 | 59 | 0 | 1 |

## Implementation thực tế

Bằng chứng baseline: commit `c86b86eb95ef91251a53b3768ae5c52c2ed73514`, CI
[40208843162](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40208843162).
Đã có packaging, cấu hình Ruff/pytest, CI và 11 smoke tests cài đặt/import.
Dataset được tổ chức local; không đồng nghĩa OCR pipeline đã được triển khai.
M0-04 đã có task tracking, checkpoint/resume và validator chạy trong
[CI 40269619726](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40269619726) cho commit `3c7d78c`.

| Module | Trạng thái implementation đã xác minh |
| --- | --- |
| `core` | DataConfig/loading/whitelist lookup đã triển khai; chưa có Gateway |
| `document_processing` | Contracts/resolver/loader và M1-03d/e DONE; M1-03f 199 table crops validated, REVIEW |
| `accounting` | Chỉ package/docstring; chưa có normalization hoặc validators |
| `evidence` | Chỉ package/docstring; chưa có canonical layer, EF-EG hoặc retrieval |
| `tools` | Chỉ package/docstring; chưa có shared executable tools |
| `agents` | Chỉ package/docstring; chưa có Planner/Supervisor/Specialists |
| `verification` | Chỉ package/docstring; chưa có critics/Judge/ledger |
| `outputs` | Chỉ package/docstring; chưa có QA/report generation |
| `api` | Chỉ package/docstring; chưa có endpoints |

Tiến độ implementation nghiệp vụ, chất lượng OCR/QA/report và độ bao phủ
benchmark: **N/A** (chưa có implementation hoặc số đo hợp lệ).

## Active task và việc tiếp theo

M1-03a DONE theo Tech Lead APPROVED; acceptance `3d700a5` đã push/remote khớp,
CI 40306938717 success đúng SHA Python 3.11/3.12 và từng step đã xác minh.
M1-03b DONE theo Tech Lead APPROVED 2026-10-26; acceptance `10eb4e9`
khớp remote, CI 40310998984 success đúng SHA/từng step Python 3.11/3.12.
M1-03c và task cha M1-03 DONE theo Tech Lead APPROVED.
Ba task con đạt criteria roadmap, cùng contracts và bounded integration.
Acceptance `5937b81`, CI 40314189759 success Python 3.11/3.12.
M1-03d DONE theo Tech Lead APPROVED engineering/synthetic/zero-output: audit 193 trang/1.557 references/1.553 paths, all
unmapped, 773 requires_review/784 unsupported_view; zero eligible/recovered vì
chưa có approved bindings. Full local 575 passed/13 skipped, crop 57 passed/1 skipped,
native junction đạt; Ruff 64 files, planning 73 tasks/pip check đạt.
Stable implementation `6e30ba67fa6b3cf7dd8f6e74021c0dbbad9343a6`, remote khớp;
CI 40315855062 success đúng SHA/mọi step Python 3.11/3.12, 578 passed/10 skipped mỗi job.
M1-03e DONE, A/B/C/D hoàn tất: 2 mappings/193 page bindings verified,
1.178 positive/4 negative controls. Audit đúng 193 trang/1.557 references;
existing 985, missing 572 (unique/contextual 572), baseline khớp. Eligible 199;
dry-run 12, recovered 12, rerun 12 already_recovered, conflicts/failures 0.
193 JSON và 193 raw images hash/metadata không đổi. Full local 614 passed/13 skipped;
Ruff 71 files/planning 74 tasks/pip check đạt. Checkpoint acceptance `1e7fe34`,
CI 40340730395 success Python 3.11/3.12.
Stable implementation `6c2b8c7738631b578c97b9b0d930b51ff69c6162`, remote khớp;
CI 40342491992 success mọi steps Python 3.11/3.12, mỗi job 617 passed/10 skipped.
[Sanitized evidence](../docs/reviews/M1-03e-evidence.md) dành cho Tech Lead.
Checkpoint trước approval: M1-03f từng BLOCKED; re-audit 193 trang, 199 eligible, reconstructed 12/pending 187,
conflicts 0; đã tạo 12 review sheets local, chưa human approval, chưa expansion.
Full local 655 passed/14 skipped; Ruff lint/format 79 files, planning 75 tasks/pip check đạt.
Stable implementation `a91492e17a0644c8f9d7e4e655ba73dda26c79f0`, remote khớp;
CI 40349513656 success mọi steps Python 3.11/3.12, mỗi job 658 passed/11 skipped.
M1-03f hiện REVIEW: user/Tech Lead conditional approval thực tế đã ghi local,
12 IDs/hashes giữ nguyên, chỉ bbox-faithful reconstruction. 8 batch 7 × 24 + 19
= 187 PNG mới; tổng 199 PNG/sidecars, 0 pending eligible, conflicts/failures 0/0.
Source hashes/metadata 193 JSON + 193 raw images khớp trước/sau từng batch;
mọi output cũ bất biến. Fresh final CLI verify 199 already_recovered/new_outputs 0.
Sheets 02/03/08/11/12 có 5 bbox coverage issues cho M1-04a, chưa sửa bbox hoặc
coi crop là bảng hoàn chỉnh. Non-table 85/views 288 vẫn ngoài scope.
[Sanitized evidence](../docs/reviews/M1-03f-evidence.md) và fixed-allowlist statistics
đã cập nhật; production code không đổi. Publication
`b3f278b3cc66d67fecc50299d0afadabfcc585b2` đã push/remote khớp;
[CI 40428368035](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40428368035)
success đúng SHA/mọi steps Python 3.11/3.12, mỗi job 658 passed/11 skipped.
Metadata CI đi sau checkpoint; không suy run cũ cho HEAD mới.
Không có active implementation task. Exact next action: Tech Lead nghiệm thu M1-03f;
không bắt đầu M1-04a/b.

Tech Lead APPROVED M1-03e ngày 2026-10-26 theo task M1-03f: mapping,
193-page audit, 12 real crops/pixels/hash/rerun và source integrity được nghiệm thu.
Original preprocessing equivalence vẫn unverified; M1-03 giữ DONE.
Publication checkpoint b0168a0c37f5a0c29b53693833d8c300e338ff74.
