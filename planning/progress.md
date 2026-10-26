# Progress Dashboard

Cập nhật: **2026-10-26** (Asia/Bangkok). Nguồn duy nhất: [Registry](tasks.md).
Đếm task đã đăng ký, không đo khối lượng hoặc chất lượng nghiên cứu bằng tỷ lệ.
Ba task cha M1-02/03/04 cũng được đếm; task con không được coi là phần trăm tiến
độ của cha. Khi tách/thêm task, cập nhật cả registry và dashboard trong cùng thay đổi.

## Số task theo milestone và trạng thái

| Milestone | Total | DONE | IN_PROGRESS | BLOCKED | TODO | READY | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M0 | 4 | 3 | 0 | 0 | 0 | 0 | 1 |
| M1 | 22 | 0 | 0 | 0 | 22 | 0 | 0 |
| M2 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M3 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M4 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M5 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| M6 | 6 | 0 | 0 | 0 | 6 | 0 | 0 |
| M7 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M8 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| TOTAL | 72 | 3 | 0 | 0 | 68 | 0 | 1 |

## Implementation thực tế

Bằng chứng baseline: commit `c86b86eb95ef91251a53b3768ae5c52c2ed73514`, CI
[40208843162](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40208843162).
Đã có packaging, cấu hình Ruff/pytest, CI và 11 smoke tests cài đặt/import.
Dataset được tổ chức local; không đồng nghĩa OCR pipeline đã được triển khai.

| Module | Trạng thái implementation đã xác minh |
| --- | --- |
| `core` | Chỉ package/docstring; chưa có config loader hoặc Gateway |
| `document_processing` | Chỉ package/docstring; chưa có loader, resolver hay xử lý OCR |
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

M0-04 ở `REVIEW`: checks local đã đạt, còn publication và ghi evidence. M1-01 còn `TODO` vì gate
M0-04 chưa DONE; spec đã được chuẩn bị, sẽ READY sau nghiệm thu M0-04. Không có
task M1 đang triển khai. Chi tiết tiếp tục tại [handoff](handoff.md).
