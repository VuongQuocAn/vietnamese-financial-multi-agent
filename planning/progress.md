# Progress Dashboard

Cập nhật: **2026-10-28** (Asia/Bangkok). Nguồn duy nhất: [Registry](tasks.md).
Đếm task đã đăng ký, không đo khối lượng hoặc chất lượng nghiên cứu bằng tỷ lệ.
Ba task cha M1-02/03/04 cũng được đếm; task con không được coi là phần trăm tiến
độ của cha. Khi tách/thêm task, cập nhật cả registry và dashboard trong cùng thay đổi.

## Số task theo milestone và trạng thái

| Milestone | Total | DONE | IN_PROGRESS | BLOCKED | TODO | READY | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M0 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| M1 | 28 | 27 | 0 | 0 | 1 | 0 | 0 |
| M2 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M3 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M4 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M5 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| M6 | 6 | 0 | 0 | 0 | 6 | 0 | 0 |
| M7 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M8 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| TOTAL | 78 | 31 | 0 | 0 | 47 | 0 | 0 |

## Implementation thực tế

Bằng chứng baseline: commit `c86b86eb95ef91251a53b3768ae5c52c2ed73514`, CI
[40208843162](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40208843162).
Đã có packaging, cấu hình Ruff/pytest, CI và 11 smoke tests cài đặt/import.
Dataset được tổ chức local; không đồng nghĩa OCR pipeline đã được triển khai.
M0-04 đã có task tracking, checkpoint/resume và validator chạy trong
[CI 40269619726](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40269619726) cho commit `3c7d78c`.

| Module | Trạng thái implementation đã xác minh |
| --- | --- |
| `core` | DataConfig/contracts/Gateway/Gemini/quota guard DONE; M1-09 cache DONE; targeted 139 passed; CI mỗi Python 3.11/3.12: 1040 passed/11 skipped |
| `document_processing` | Contracts/resolver/loader và M1-03a/b/c/d/e/f DONE; M1-04a/b DONE, 199 reconstructed table crops nghiệm thu engineering; M1-10 checkpoints DONE; M1-11 classifier DONE; M1-11a bounded pilot DONE; M1-11b evidence-aware gate DONE (Tech Lead APPROVED), 319 targeted/regression passed, live 20 requests/19 pages/9 resolved; M1-12 reconstruction DONE (Tech Lead APPROVED), 219 targeted/real 1 resolved/7 unresolved; CI exact 01b235c success 3.11/3.12; M1-12a assisted reconstruction DONE (Tech Lead APPROVED), 261 targeted; same8 2 resolved/6 unresolved, 7 requests |
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

**M1-13 DONE** — Tech Lead APPROVED có điều kiện; CI exact SHA đã xác minh PASS.
M1-12a DONE; không implementation task khác active. 11 focused +47 regression passed.
Pilot2 pages/2 requests, 0 corrections, 17450 input/40 output/17490 total tokens;
raw bất biến, model bỏ sót lỗi chữ trực quan; không ground truth/accuracy.
[Spec](tasks/M1/M1-13.md), [usage/evidence](../docs/reviews/M1-13-evidence.md).
[CI 40609685619](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40609685619)
PASS đúng implementation `5bfff54365a78b0658eab1a64cc2c108d066037d`, Python3.11/3.12.
Next action: chờ Tech Lead giao task tiếp theo; không tự bắt đầu M1-14.
Các đoạn dưới là lịch sử.

**M1-11a DONE**, Tech Lead APPROVED 27/10/2026; M1-11 DONE, M1-12 TODO,
không task triển khai active.
Baseline HEAD/origin `e5ae508c69bbbe7e2543e8c9b5973cbaa5fa51b5` sạch/khớp sau fetch.
Dry-run 19 pages/3 symbols/14 strata; live 6 requests gồm smoke +5 pages,
12307 input/12483 total tokens; 0 resolved/5 unresolved, cache HIT 5/checkpoint HIT 0.
Dừng trước send kế tiếp vì input-token reservation; 17 focused +146 regression passed.
Implementation `063bd2935a47832d928a6869ea35a2bd0cf6f9f2` /
[CI 40505711042](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40505711042)
success exact SHA, jobs/mọi steps 3.11/3.12; mỗi job 1130 passed/11 skipped.
Review checkpoint `ad2a1664faa33f54ccc90e4a0cbace41ab48fbc7` /
[CI 40506143468](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40506143468)
success exact SHA 3.11/3.12 đã kiểm tra lại. Acceptance chỉ 7 docs/planning files;
Ruff/planning/diff, không unit/API rerun; acceptance SHA/CI kiểm tra riêng sau push.
Hai follow-up chưa triển khai: đánh giá lại OCR quality gate; loại bỏ giới hạn
20.000 input tokens tùy ý ở pilot tiếp theo. Giữ nguyên kết quả và implementation hiện tại.
Next action: Chờ Tech Lead giao việc; không tự bắt đầu M1-12 hoặc task khác.
Các đoạn sau là lịch sử trước M1-11a.

**M1-11 DONE**, Tech Lead APPROVED engineering scope 27/10/2026, không blocking issues;
dependencies DONE, không implementation task active; M1-12 TODO.
Implementation `e8e757fe7b9f2d1cd1af75f3eb4c026e8fca86c5` đã push;
[CI 40500929151](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40500929151)
success exact SHA, tất cả steps 3.11/3.12, mỗi job 1113 passed/11 skipped.
35 focused + 333 related regression passed; Ruff/planning/diff đạt, không live API.
Taxonomy candidates B01/B02/B03/B09 opt-in, approval kế toán TBD; text-only.
Live 0 requests vì chưa xác nhận credential/project/quota/budget; [evidence](../docs/reviews/M1-11-evidence.md).
Review checkpoint `7a3614559e2542414166d78e300507d533b84217` /
[CI 40501298126](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40501298126)
success exact SHA 3.11/3.12 đã kiểm tra lại. Taxonomy chưa được duyệt chính thức,
text-only gate bảo thủ, live Gemini chưa verified (0 requests) giữ nguyên.
Acceptance chỉ 7 docs/planning files; local Ruff/planning/diff, không rerun unit suite/API.
Acceptance SHA/CI xác minh riêng sau push và báo cuối.
Next action: Chờ Tech Lead giao việc; không tự bắt đầu M1-12.
Các đoạn bên dưới là lịch sử trước M1-11.

**M1-10 DONE**, Tech Lead APPROVED 27/10/2026; M1-11 TODO, không task triển khai active.
Implementation 796e4664e6faf1d32354f7db62770bb7e4e1304e /
[CI 40497588383](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40497588383)
success exact SHA, mọi steps Python 3.11/3.12; mỗi job 1078 passed/11 skipped.
38 checkpoint + 246 regression passed; Ruff/planning/diff đạt, không API/dataset thật.
[Evidence](../docs/reviews/M1-10-evidence.md). Review checkpoint 21f1834 /
[CI 40497942861](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40497942861)
success exact SHA, mọi steps 3.11/3.12 đã xác minh. Acceptance chỉ docs/planning;
local Ruff/planning/diff, không rerun unit suite/API; acceptance CI kiểm tra riêng sau push.
Next action: **Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M1-11.**
Các đoạn M1-09 bên dưới là lịch sử trước giao việc M1-10.

**M1-09 DONE**, Tech Lead APPROVED ngày 27/10/2026; dependencies M1-06/07/08 DONE.
Implementation afb866f760fea63cb3a960d3056a6909139b6294 / [CI 40468254692](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40468254692) success exact SHA;
mọi steps Python 3.11/3.12 đạt, mỗi job 1040 passed/11 skipped.
Local 34 cache + 105 regression passed; Ruff/planning/diff và ví dụ offline đạt.
Không live API/dataset/keys hoặc thay contracts; cache opt-in, TTL/LRU, process-local.
Acceptance chỉ docs/planning, không production code/tests hoặc live Gemini API.
CI acceptance xác minh riêng exact SHA sau push và báo cuối.
Next action: **Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M1-10/M1-11.**
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
