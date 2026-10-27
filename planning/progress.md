# Progress Dashboard

Cập nhật: **2026-10-27** (Asia/Bangkok). Nguồn duy nhất: [Registry](tasks.md).
Đếm task đã đăng ký, không đo khối lượng hoặc chất lượng nghiên cứu bằng tỷ lệ.
Ba task cha M1-02/03/04 cũng được đếm; task con không được coi là phần trăm tiến
độ của cha. Khi tách/thêm task, cập nhật cả registry và dashboard trong cùng thay đổi.

## Số task theo milestone và trạng thái

| Milestone | Total | DONE | IN_PROGRESS | BLOCKED | TODO | READY | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M0 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| M1 | 25 | 16 | 0 | 0 | 9 | 0 | 0 |
| M2 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M3 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M4 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M5 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| M6 | 6 | 0 | 0 | 0 | 6 | 0 | 0 |
| M7 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M8 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| TOTAL | 75 | 20 | 0 | 0 | 55 | 0 | 0 |

## Implementation thực tế

Bằng chứng baseline: commit `c86b86eb95ef91251a53b3768ae5c52c2ed73514`, CI
[40208843162](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40208843162).
Đã có packaging, cấu hình Ruff/pytest, CI và 11 smoke tests cài đặt/import.
Dataset được tổ chức local; không đồng nghĩa OCR pipeline đã được triển khai.
M0-04 đã có task tracking, checkpoint/resume và validator chạy trong
[CI 40269619726](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40269619726) cho commit `3c7d78c`.

| Module | Trạng thái implementation đã xác minh |
| --- | --- |
| `core` | DataConfig và M1-05 LLM contracts/validation đã triển khai, targeted 142 passed; chưa có runtime Gateway |
| `document_processing` | Contracts/resolver/loader và M1-03a/b/c/d/e/f DONE; M1-04a validators và M1-04b bounded pilot DONE; 199 reconstructed table crops được nghiệm thu engineering từ M1-03f |
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

Hiện tại **M1-05 DONE — Tech Lead APPROVED ngày 27/10/2026**;
dependencies M1-02/M1-04 DONE. Không có implementation task đang chạy.
Implementation f6de33cb5855847985069ab78e2ada8596cc8cd2 và
[CI 40458339034](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40458339034)
success exact SHA, mọi steps Python 3.11/3.12; mỗi job 901 passed/11 platform skips.
Targeted 142 passed/zero skips/warnings; full local 910 passed/2 platform skips.
Review checkpoint 7a54715369016a29ac886cf16b7480fd57ebc2f9 /
[CI 40458603189](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40458603189)
success exact SHA/từng step Python 3.11/3.12 đã xác minh trước finalization.
Acceptance chỉ docs/planning, giữ code/tests/schema và limitations; không lặp local
unit suite. CI acceptance kiểm tra riêng sau push, không tự tham chiếu SHA/CI.
Next action: **Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M1-06**.
M1-06..09 TODO. Chỉ contracts, chưa runtime Gateway.
Các đoạn bên dưới là lịch sử trước giao việc này.

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
Checkpoint REVIEW trước nghiệm thu: user/Tech Lead conditional approval thực tế đã ghi local,
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
Acceptance checkpoint 2026-10-27: **M1-03f DONE, Tech Lead APPROVED** engineering
cho 199 reconstructed table crops. Baseline nghiệm thu
`4902b1e28b00bdfead1839a71be96e35c0ca2980` fetch/remote khớp;
[CI 40428602056](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40428602056)
success đúng SHA đã xác minh lại. Commit/CI nghiệm thu mới được kiểm tra sau push,
không suy run cũ cho commit mới. Synthetic/pixel tests không chứng nhận OCR accuracy,
table completeness hoặc original crop equivalence; 5 bbox issues vẫn mở cho M1-04a.
Checks nghiệm thu mới: 655 passed/14 skipped, Ruff lint/format 79 files,
planning validator 75 tasks, pip check và git diff --check đạt.
Tại checkpoint nghiệm thu M1-03f chưa có active implementation task; lịch sử
M1-04a TODO ở thời điểm đó được thay bằng giao việc hiện tại bên dưới.
Next action tại checkpoint M1-03f là chờ giao M1-04a; task đã được giao bên dưới.

Tech Lead APPROVED M1-03e ngày 2026-10-26 theo task M1-03f: mapping,
193-page audit, 12 real crops/pixels/hash/rerun và source integrity được nghiệm thu.
Original preprocessing equivalence vẫn unverified; M1-03 giữ DONE.
Publication checkpoint b0168a0c37f5a0c29b53693833d8c300e338ff74.

Checkpoint M1-04a: REVIEW; A–G đã triển khai/test và push implementation.
Full local 728 passed/2 skipped, targeted 61 passed; Ruff 85 files/planning 75 tasks,
pip/diff check đạt. Bounded smoke 5 pages/50 refs, 43 original/7 reconstructed,
giữ 5 human bbox issues; deterministic/read-only integrity đạt.
Implementation 32a3d23362f494fe8a39fa8ed9b3983841e4f287 local/origin/main khớp,
[CI 40432840930](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40432840930)
success exact SHA, mọi steps Python 3.11/3.12; mỗi job 719 passed/11 skipped.
Checkpoint REVIEW chỉ cập nhật docs/planning; SHA/CI checkpoint mới kiểm tra riêng
sau push và ghi báo cáo cuối, không tạo commit tự tham chiếu.
Next action tại checkpoint REVIEW: Tech Lead review/accept M1-04a.

Acceptance 2026-10-27: **M1-04a DONE**, Tech Lead APPROVED engineering scope.
Implementation 32a3d23 / CI 40432840930 và checkpoint d782320 / CI 40433101346
success exact SHA, từng step Python 3.11/3.12 đã đối chiếu. Các đoạn REVIEW trên
là lịch sử. M1-04/M1-04b TODO; next action: push/check finalization CI trước spec M1-04b.

Checkpoint hiện tại M1-04b IN_PROGRESS: M1-04a DONE tại 6bfd43209d47ada1f236f8619ebc876c47c60f28,
CI 40435213198 success exact SHA Python 3.11/3.12. Spec/protocol A chốt trước real reads;
C frozen 23 pages/398 references; targeted 39 passed, Ruff/planning/pip/diff đạt.
M1-04 cha TODO. Next action: hai lượt pilot trên cùng manifest, integrity/digest comparison.

Checkpoint F/H draft M1-04b: first/second reports/digests khớp, 472 selected snapshots
bất biến, 316 original/14 reconstructed/68 unrecovered, 5 human issues giữ requires_review.
Targeted cuối 40 passed; full cuối 768 passed/2 skipped. Evidence/statistics đã có.
Next action hiện tại: diff review rồi allowlist implementation commit/push/exact-SHA CI.

Checkpoint bàn giao hiện tại: **M1-04b REVIEW, awaiting Tech Lead acceptance**.
Các đoạn IN_PROGRESS bên trên là lịch sử. Implementation
4a2a4ed4ae09924e073448029e884b030f61bc27 đã push/main khớp origin;
[CI 40437144971](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40437144971)
success exact SHA, từng step Python 3.11/3.12, mỗi job 759 passed/11 skipped.
Local final 768 passed/2 skipped, targeted 40; hai real runs deterministic, nguồn
selected bất biến, evidence/statistics sanitized đã xuất bản. M1-04 cha TODO.
Checkpoint REVIEW chỉ docs/planning, CI mới kiểm tra riêng sau push, không self-reference.
Exact next action: Tech Lead review/accept M1-04b; không tự DONE hoặc task mới.

Checkpoint finalization 2026-10-27: **M1-04b DONE**, Tech Lead APPROVED engineering
protocol/provenance/implementation/repeatability. Các đoạn REVIEW trên là lịch sử.
Baseline 7b0bc52dd44cded9bfb5cc0a668433c4ff9b9576 / CI 40437415893 success exact SHA;
implementation 4a2a4ed / CI 40437144971 success, Python 3.11/3.12 mọi steps verified.
Giữ nguyên pilot 23/398, năm human issues và các giới hạn; không rerun real data.
Local finalization mới 768 passed/2 skipped; Ruff/planning/pip/diff đạt.
M1-04 cha TODO tại checkpoint 1; next action: finalization commit/push/exact-SHA CI
trước aggregate review parent, không M1-05.

Checkpoint aggregate hiện tại: **M1-04 REVIEW**, chưa DONE; M1-03/M1-04a/M1-04b DONE.
M1-04b acceptance a0ffaaff317c046bebd023c9305b1303ddcf8451 /
[CI 40439127716](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40439127716)
success exact SHA, mọi steps Python 3.11/3.12, mỗi job 759 passed/11 skipped.
Sau gate này mới aggregate: matrix 10 checks đối chiếu scope roadmap, production
validators/contracts/schema/recovery diff rỗng; local mới 768 passed/2 skipped.
[Spec parent](tasks/M1/M1-04.md), [aggregate evidence](../docs/reviews/M1-04-aggregate-evidence.md).
Chỉ docs/planning; không rerun pilot/đổi statistics/manifest hoặc sửa 5 human issues.
Engineering criteria đủ bằng chứng, Tech Lead final confirmation còn chờ. CI checkpoint
parent kiểm tra sau push riêng; không self-reference hoặc suy CI cũ cho commit mới.
Exact next action: Tech Lead review M1-04 aggregate acceptance; do not start another task.

Final acceptance M1-04 **2026-10-27: M1-04 DONE, Tech Lead APPROVED** engineering
scope. M1-03/M1-04a/M1-04b DONE; các đoạn REVIEW bên trên là lịch sử trước approval.
Baseline ad39a946546b4ffc6bc73c7044caa55f6a357d7d /
[CI 40439654103](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40439654103)
success exact SHA, mọi steps Python 3.11/3.12 đã kiểm tra lại.
Registry/spec/evidence/handoff đồng bộ; không còn acceptance/implementation work M1-04
và không có implementation task đang chạy. Giữ nguyên số liệu/limitations/human issues;
không chứng nhận OCR accuracy/financial correctness/table completeness/dataset readiness.
Chỉ docs/planning finalization, checks mới phù hợp; không lặp unit suite/real pilot.
Commit/CI acceptance mới kiểm tra sau push riêng, không self-reference.
Exact next action: Chờ Tech Lead rà soát roadmap và giao task tiếp theo. Không tự bắt đầu implementation.
