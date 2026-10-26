# Progress Dashboard

Cập nhật: **2026-10-26** (Asia/Bangkok). Nguồn duy nhất: [Registry](tasks.md).
Đếm task đã đăng ký, không đo khối lượng hoặc chất lượng nghiên cứu bằng tỷ lệ.
Ba task cha M1-02/03/04 cũng được đếm; task con không được coi là phần trăm tiến
độ của cha. Khi tách/thêm task, cập nhật cả registry và dashboard trong cùng thay đổi.

## Số task theo milestone và trạng thái

| Milestone | Total | DONE | IN_PROGRESS | BLOCKED | TODO | READY | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M0 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| M1 | 22 | 7 | 0 | 0 | 15 | 0 | 0 |
| M2 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M3 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M4 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M5 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| M6 | 6 | 0 | 0 | 0 | 6 | 0 | 0 |
| M7 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M8 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| TOTAL | 72 | 11 | 0 | 0 | 61 | 0 | 0 |

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
| `document_processing` | Raw OCR v1, Document Understanding v1 và Path Mapping v1; pure validation/lexical helper, read-only resolver runtime; chưa có loader |
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
M1-03b REVIEW: A/B/C hoàn tất. Windows Python 3.12 full suite
442 passed/11 skipped, gồm 80 resolver cases (69 passed/11 skipped).
Ruff lint/format 54 files, pip check và planning validator 72 tasks đạt.
Implementation `3cb32f8409a76d94747f0080186092a8f9ad1be6` push/remote khớp;
[CI 40308129287](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40308129287)
success đúng SHA, từng step Python 3.11/3.12 xác minh. Mỗi job 445 passed/8 skipped;
77 resolver cases đạt Linux (gồm symlink/FIFO/case-sensitive), 3 junction cases skip.
Bản ghi evidence sau implementation cần CI riêng, không suy ra từ implementation.
Tech Lead APPROVED M1-03b 2026-10-26: trạng thái hiện tại DONE.
Acceptance baseline `13a39ea`, CI 40308268296 success đúng SHA và từng step.
Next action: triển khai M1-03c sau khi checkpoint acceptance được xác minh.
