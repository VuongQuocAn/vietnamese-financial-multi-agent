# Progress Dashboard

Cập nhật: **2026-10-29** (Asia/Bangkok). Nguồn duy nhất: [Registry](tasks.md).
Đếm task đã đăng ký, không đo khối lượng hoặc chất lượng nghiên cứu bằng tỷ lệ.
Ba task cha M1-02/03/04 cũng được đếm; task con không được coi là phần trăm tiến
độ của cha. Khi tách/thêm task, cập nhật cả registry và dashboard trong cùng thay đổi.

## Số task theo milestone và trạng thái

| Milestone | Total | DONE | IN_PROGRESS | BLOCKED | TODO | READY | REVIEW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M0 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| M1 | 32 | 32 | 0 | 0 | 0 | 0 | 0 |
| M2 | 11 | 11 | 0 | 0 | 0 | 0 | 0 |
| M3 | 7 | 0 | 0 | 0 | 7 | 0 | 0 |
| M4 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M5 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| M6 | 6 | 0 | 0 | 0 | 6 | 0 | 0 |
| M7 | 5 | 0 | 0 | 0 | 5 | 0 | 0 |
| M8 | 8 | 0 | 0 | 0 | 8 | 0 | 0 |
| W | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 92 | 53 | 0 | 0 | 39 | 0 | 0 |

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
| `accounting` | M2-01 DONE, Tech Lead APPROVED: Financial Normalization v1, Decimal/context/provenance, schema và quality signals; 8 focused PASS; M2-02 resolver context DONE, Tech Lead APPROVED 2026-10-28, 10 focused mới PASS, chưa mapping ô/chỉ tiêu; M2-03 DONE, Tech Lead APPROVED Research MVP 2026-10-28, 11 focused mới PASS và pilot8 đủ bốn loại; chưa chứng minh accuracy toàn dataset; M2-04 DONE, Tech Lead APPROVED Research MVP Lean v3:14 internal IDs,41 targeted PASS trước nghiệm thu,pilot20/14 mapped,0 real numeric links accepted tại checkpoint M2-04; M2-04a DONE: pilot40 slots 6 đúng,0 sai,12 rejected,22 unresolved; 6 links B02 trang7 manual image review, chưa xác minh B01/B03, chưa automatic glyph verification hoặc verified facts |
| `evidence` | Chỉ package/docstring; chưa có canonical layer, EF-EG hoặc retrieval |
| `tools` | M2-08 structured financial query probe: exact source/page/code/period, Decimal và citations; chưa có full shared tool space hoặc natural-language QA |
| `agents` | Chỉ package/docstring; chưa có Planner/Supervisor/Specialists |
| `verification` | Chỉ package/docstring; chưa có critics/Judge/ledger |
| `outputs` | Chỉ package/docstring; chưa có QA/report generation |
| `api` | W-02 DONE: FastAPI GET /api/health và Next.js proxy; chưa nối M1–M2 |

Full chatbot QA/report accuracy vẫn **N/A**; M2-08 có benchmark structured query
trên một PDF, công bố riêng trong audit và không suy thành chatbot accuracy.

## Active task và việc tiếp theo

W-06 DONE — Tech Lead APPROVED Engineering Scope 29/10/2026; CI40805486808 SUCCESS
đúng b5de0a2. BBS_2025 178 observations, source linking B01/B02/B03 PASS;
zero/precision/conflict chỉ synthetic, chưa accuracy toàn báo cáo.
[Spec/evidence](tasks/W/W-06.md).
Next action: chờ chỉ đạo tiếp theo; không bắt đầu W-07.

Checkpoint trước:

W-05 DONE — Tech Lead APPROVED Engineering Scope 29/10/2026; CI40801877913 SUCCESS,
BBS_2025 viewer PASS. [Evidence](tasks/W/W-05.md).
Next action: chờ chỉ đạo tiếp theo; không bắt đầu W-06.
Các đoạn dưới là checkpoint lịch sử.

W-04 DONE — Tech Lead APPROVED Engineering Scope 29/10/2026; [evidence](tasks/W/W-04.md).

Housekeeping W-03 — 2026-10-29: PR#1/#2/#3 đã MERGED main tuần tự, CI main sau
từng merge SUCCESS; baseline6dd0d1d. Root dev.ps1 một lệnh, local keys tự nạp,
Ctrl+C/ports/failure cleanup và live scan upload→ready PASS (1 call/2794tokens).
W-03 DONE — Tech Lead APPROVED29/10/2026, engineering scope. Live synthetic PASS,
chưa accuracy PDF BBS_2025 thực tế; không bắt đầu W-04. [Evidence](../docs/web-demo-v1/w-03-validation.md).
Launcher d8e7026 đã push main/remote khớp; [CI40791847627](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40791847627)
SUCCESS exact SHA: Python3.11/3.12 mỗi job1502 PASS/11 SKIP, Web13 PASS.
Next action: Chờ chỉ đạo tiếp theo; không bắt đầu W-04.
Các checkpoint bên dưới là lịch sử trước housekeeping/merge.

**W-03 REVIEW — final refinement**: auto-first core có nguồn → ready; key-file
rotation/cooldown/cap chung, bỏ policy/scope thủ công, UI neutral/form tùy chọn.
8 browser targeted PASS (1440/1366 và mobile tối thiểu), 44 Python focused cases.
Live scan synthetic2 trang PASS, model gemini-3.5-flash-lite, provenance trang2,
auto-ready/edit PASS;3 attempts tổng gồm2 HTTP400 ban đầu và1 success/2805tokens.
Baseline f617e68, PR#3 draft base W-02. Refinement7048d92 đã push/remote khớp;
[CI40718128314](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40718128314)
SUCCESS exact SHA: Python3.11/3.12 mỗi job1502 PASS/11 SKIP; Web13 PASS.
[Evidence](../docs/web-demo-v1/w-03-validation.md).
Next action: Tech Lead nghiệm thu độc lập W-03.

Các checkpoint W-03 bên dưới là lịch sử trước final refinement.

**W-03 REVIEW** — upload/storage/Vision preflight và metadata review đã có.
36 focused unit/integration, 139 Gateway/quota/cache regression và 11 browser/proxy
PASS; Ruff/TypeScript/lint/build PASS. Live Gemini NOT RUN vì thiếu policy/budget
scope W-03 mới được xác nhận. [Spec](tasks/W/W-03.md),
[evidence](../docs/web-demo-v1/w-03-validation.md), [usage](../docs/web-demo-v1/w-03-usage.md).
Stacked W-02 HEAD 78a50c6, PR #1/#2 OPEN; không merge/W-04/M3.
Implementation b494788 đã push/remote khớp; [PR #3](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/3)
draft OPEN base W-02. [CI 40710376652](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40710376652)
SUCCESS exact SHA: Python 3.11/3.12 mỗi job 1494 PASS/11 SKIP; Web 11 PASS.
Next action: Tech Lead nghiệm thu độc lập W-03.

Các checkpoint W-02 bên dưới là lịch sử.

**W-02 DONE** — Tech Lead APPROVED ngày 28/10/2026 theo Research MVP Lean v3.
Commit đã nghiệm thu `db25039b818f7251cba7b4ed091dd2afa0dbc6ec`, local/origin
khớp sau fetch. [CI 40703400345](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40703400345)
SUCCESS exact SHA: Python 3.11/3.12 qua lint/format/planning/unit tests, mỗi job
1460 PASS/11 SKIP; Web skeleton typecheck/lint/build và 5 browser/proxy tests PASS.
Lỗi format W-01 đã khắc phục. PR #1/#2 OPEN, PR #2 vẫn stacked trên W-01.
Phiên nghiệm thu chỉ sáu planning files, checker/diff PASS; commit [skip ci] theo
chỉ đạo. Giữ nguyên thay đổi local web/next-env.d.ts, không stage.
Không sửa implementation/tests/UI/M1–M2/Stitch, không bắt đầu W-03/M3.
Next action: Chờ chỉ đạo tiếp theo.

Checkpoint W-02 REVIEW dưới đây là lịch sử trước approval và trước fix format.

**W-02 REVIEW** — Next.js 16.4.3/React 19.3.1 + FastAPI local, bốn routes,
app shell và empty/Coming Soon states theo W-01. Typecheck/lint/build, 16 targeted
Python và 5 browser/proxy tests PASS; screenshots desktop/laptop/mobile đã xem.
Ruff Python/planning PASS; full local suite 1469 PASS/2 SKIP (Windows).
Full-tree format FAIL baseline architecture W-01 với Ruff 0.17.2, không sửa ngoài
scope. CI 40701696004 Python 3.11/3.12 FAIL formatting baseline, unit/planning
SKIPPED; Web skeleton SUCCESS (typecheck/lint/build + 5 browser/proxy tests).
Implementation `22c48a5897350673d6082d6d9868f24df520c1a9` đã push/remote khớp;
[PR #2](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/2)
OPEN base W-01. [Evidence](../docs/web-demo-v1/w-02-validation.md).
Stacked từ `31ca5704c388b31ac102b19577b030fcb1026628`; PR #1 OPEN/chưa merge,
CI skipped. [Spec W-02](tasks/W/W-02.md),
[local run](../docs/web-demo-v1/local-development.md).
Next action: Tech Lead nghiệm thu độc lập W-02 và quyết định xử lý lỗi format baseline.

Các checkpoint bên dưới là lịch sử trước W-02.

**W-01 DONE** — Tech Lead APPROVED ngày 28/10/2026, Research MVP Lean v3 —
Architecture/Design/Contracts; evaluation scope Architecture/Design/API Contracts.
Dependency M2-09 DONE; chỉ nghiệm thu thiết kế, chưa có website hoạt động.
Phiên nghiệm thu chỉ sửa sáu tài liệu planning, chạy planning checker/diff check;
giữ nguyên design/API/Stitch/M1–M2/checker/tests và dữ liệu nguồn.
Design `7a158f31e2feab0895d4ca5054bdbb56e78526be`, review/planning evidence
`ac52100a68863d13bffed96d4218977a8f445779` đã xác minh không thay design/assets.
CI chưa chạy trên nhánh tại checkpoint nghiệm thu; không tuyên bố CI SUCCESS.
PR/CI sẽ được kiểm tra sau push nghiệm thu; không tự merge. W-02 chưa bắt đầu.
Next action: Chờ giao W-02.

Checkpoint W-01 REVIEW dưới đây là lịch sử trước approval.

**W-01 REVIEW** — thiết kế Web Demo V1, dependency M2-09 DONE.
[Spec](tasks/W/W-01.md), [architecture](../docs/web-demo-v1/architecture.md),
[API](../docs/web-demo-v1/api-contracts.md), [UI](../docs/web-demo-v1/ui-handoff.md).
Baseline đã fetch local/origin `5c8a80e4ceedb735dcbad12e267620b0b8046adb`.
Đã đối chiếu backend M1–M2 và sáu Stitch assets, giữ nguyên bytes nguồn.
Local: planning 87 tasks PASS, checker regressions 3 PASS, Ruff PASS;
diff phần W-01 tự viết PASS; toàn staged báo bốn trailing spaces trong Stitch
DESIGN.md gốc, giữ nguyên theo yêu cầu không sửa reference.
11 JSON examples parse PASS. Chưa chạy web/financial evaluation/Gemini.
Design/checker/assets đã push [7a158f3](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/7a158f31e2feab0895d4ca5054bdbb56e78526be),
remote SHA khớp. CI không có run (workflow chỉ push main hoặc PR; nhánh chưa mở PR),
không gán CI cũ cho W-01. [Handoff](handoff.md) ghi checkpoint.
Next action: Tech Lead nghiệm thu độc lập W-01.

Checkpoint M2-09 dưới đây là lịch sử trước W-01, đã nghiệm thu DONE.

M2-09 DONE — Tech Lead APPROVED Research MVP Lean v3, Evaluation Level 1 ngày
2026-10-28; nghiệm thu planning-only, dependency M2-08 DONE. Một PDF BBS2025/24 trang,
discovery đúng 24/24; B01 5–6, B02 7, B03 8, B09 9–24, other 1–4.
Primary coverage 4/4; numeric precision/recall/kỳ/unit/grounding/usability 163/163;
reference 163 numeric cells +7 dash, toàn bộ coded rows; 7 dash sai raw glyph giữ
missing, không suy zero. Notes sample 6/6 riêng.
Queries M2-08 giữ 25/26 answered đúng/grounded; không runtime regression.
25 live calls/37.382 tokens, discovery 116,11 giây; recovery 0.
140 targeted PASS trước nghiệm thu; phiên này chỉ planning checker và diff check.
Implementation `bd5a3c525f4cfe1d3f5204983e86746e748b1c93` đã push;
[CI40661431781](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40661431781)
SUCCESS đúng SHA, mọi bước Python 3.11/3.12 đã xác minh lại.
[Báo cáo/API](../docs/m2-09-full-pdf-evaluation.md), [spec](tasks/M2/M2-09.md).
Tech Lead đồng ý CONDITIONAL GO cho Document Explorer B01/B02/B03;
B09 chỉ inventory/viewer. Gemini-first, tự chọn trang, accounting checks optional,
không ManualReview gate. Reference do một agent đối chiếu trực tiếp PDF, không có
reviewer độc lập thứ hai; chưa đánh giá tổng quát, notes QA, chatbot hoặc fresh-run stability.

Baseline nghiệm thu sạch local/origin `c774b1dd7cc81195aee460708a272e3bf328dfc8`.
Không sửa implementation/tests/PDF/cache/reference/artifacts, không gọi Gemini hoặc
chạy lại pytest/CI. Commit nghiệm thu chỉ planning [skip ci]; không gán CI implementation
cho SHA nghiệm thu. Các checkpoint REVIEW trong báo cáo là lịch sử trước approval.
Next action: Chờ Tech Lead giao Web Demo V1; không tự bắt đầu Web Demo V1 hoặc M3.

Các checkpoint M2-04a bên dưới là lịch sử.

**M2-04a DONE** — Tech Lead APPROVED ngày 2026-10-28 trong phạm vi Research MVP.
Pilot 40 slots: 6 accepted đúng, 0 sai, 12 rejected, 22 unresolved. 6 liên kết chỉ thuộc B02 trang 7, có manual image review; chưa có automatic glyph verification, chưa xác minh numeric linking thực tế cho B01/B03, chưa phải verified financial facts.
[Implementation](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/4d6221cf222d3bf6faa1380da11cbbe92ffcd5bd); [CI40644142273](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40644142273) SUCCESS đúng SHA, mọi bước Python 3.11/3.12.
Nghiệm thu chỉ planning; không chạy lại pytest, Gemini hoặc CI. [Spec](tasks/M2/M2-04a.md), [issue](tasks/M2/issues/M2-04-numeric-linking.md).
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2-05.

Các checkpoint bên dưới là lịch sử.

**M2-04 DONE** — [spec](tasks/M2/M2-04.md), [API/evidence](../docs/financial-item-mapping.md).
Tech Lead APPROVED ngày 2026-10-28 trong phạm vi Research MVP Lean v3.
14 internal IDs; 41 targeted PASS trước nghiệm thu; pilot3/20:14 đúng/0 sai/0 uncertain/6 unresolved.
Numeric slots0 accepted/28 rejected/12 chưa xét; hash5 nguồn không đổi.
Implementation `8b1c020d743934e1e6bcf0216de57c3935ddcf7c` đã push; [CI40641035898](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40641035898) SUCCESS exact SHA, mọi steps Python3.11/3.12 đã xác minh. Nghiệm thu chỉ planning; không gán CI này cho SHA mới.
Chưa có positive numeric linking trên dữ liệu thực; M2-05/M2-06 chưa được coi là validated end-to-end.
Baseline nghiệm thu sạch local/origin `59a70dc0d1a8ef9ca6cad63de72723a4a168e52a`; diff từ implementation chỉ docs/planning.
Phiên này chỉ 5 planning files, planning checker82/diff PASS; không chạy lại pytest/Gemini.
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2-05.
Các mục trước M2-04 bên dưới là lịch sử.

**M2-03 DONE** — Tech Lead APPROVED ngày 2026-10-28 trong phạm vi Research MVP.
Page resolver và document inventory không kế thừa nhãn.
[Spec](tasks/M2/M2-03.md), [API/evidence](../docs/statement-type-recognition.md).
29 targeted PASS; pilot8:6 resolved đúng/0 sai/1 uncertain/1 unresolved, đủ bốn loại;
hash7 nguồn không đổi. Implementation `972d124ccd03d840375e37a3bbbcc62ed2eacb01` đã push; [CI 40639663139](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40639663139) SUCCESS exact SHA, mọi steps Python3.11/3.12 đã xác minh.
Nghiệm thu tại baseline sạch local/origin `063eca618f0ad3ab3d3539282c95d0e8e3e67c84`;
code/tests/schema không đổi từ implementation. Pilot chỉ theo OCR text, chưa
chứng minh accuracy toàn dataset. Phiên này chỉ 5 planning files; planning checker
và diff check PASS, không chạy lại pytest/Gemini hoặc yêu cầu full CI mới.
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2-04.
Các đoạn dưới là lịch sử.

**M2-02 DONE** — Tech Lead APPROVED 2026-10-28; resolver period/unit/scope và adapter M1.
[Spec](tasks/M2/M2-02.md), [API/evidence](../docs/financial-context-resolution.md).
18 targeted PASS; pilot5 trang: 5 resolved đúng/0 sai/3 uncertain/7 unresolved.
Không API, hash nguồn giữ nguyên. [CI 40638428927](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40638428927) SUCCESS đúng checkpoint `0637b13f7dc469d97c9827f73f9549d7ec90996c`; Python3.11/3.12 và mọi steps success.
Nghiệm thu tại baseline sạch `8e08969350ff9a8b23b99ba602400916421b7c28`;
phiên này chỉ 5 planning files, không chạy lại tests/Gemini hoặc yêu cầu CI mới.
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2-03.
Các đoạn sau là lịch sử.

**M2-01 DONE** — Tech Lead APPROVED ngày 2026-10-28; Financial Normalization v1.
Dependency M1-16 DONE; raw/Decimal/context nullable, provenance M1 giữ giới hạn.
[Spec](tasks/M2/M2-01.md), [API/evidence](../docs/financial-normalization-contract.md).
SHA được nghiệm thu `96e51c4736c67ef4f665ea21a16ba190bb89a798` khớp local/origin;
[CI40636889415](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40636889415)
completed/SUCCESS đúng SHA, mọi steps Python3.11/3.12 đã đối chiếu.
Implementation `471ea80a35f9968ba43b712d4806b54353136373`, 8 focused PASS giữ nguyên.
Phiên nghiệm thu chỉ 5 planning files; không chạy lại tests/Gemini hoặc yêu cầu CI mới.
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2-02.
Các đoạn sau là lịch sử.

**M1-16 DONE** — Tech Lead APPROVED có điều kiện trong phạm vi Research MVP.
Entrypoint chung OCR JSON/PDF/PNG, unified_document_v1 và quality router.
Existing BBS2025/page5:6 text/1 table/97 cells; native pages5/7/8:33 text/3 tables/335 cells.
Giữ native46 cell texts unresolved, tables3 unresolved, geometry0 verified;0 API mới.
10 focused +77 loader regression passed; [CI 40620923159](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40620923159)
SUCCESS đúng HEAD `d2df004e3cf347713028ba958abbbb56aec7cb20`, mọi steps Python3.11/3.12 đạt.
[Evidence](../docs/reviews/M1-16-evidence.md), [API/contract](../docs/unified-document-understanding.md).
Manifest/PNG replay không rehash PDF gốc; output chỉ đủ text_evidence, chưa chứng minh financial accuracy.
Phiên nghiệm thu chỉ planning, không chạy lại tests/replay/Gemini, không yêu cầu CI mới.
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2 hoặc web demo.
Các đoạn sau là lịch sử.

**M1-15 DONE** — Tech Lead APPROVED có điều kiện; PDF BBS2025 có24 trang, pilot5/5 thành công.
Text58/cell texts505 accepted, tables0/10 accepted; partial DU schema5/5,
raw loader/DU quality0/5. 5 requests/50541 tokens, provider failures0; source bất biến.
8 focused passed; [evidence](../docs/reviews/M1-15-evidence.md).
[CI 40618548302](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40618548302)
PASS đúng `c95e2be2982d5c86d9beb9508a8307455c96e53e`, mọi steps Python3.11/3.12 success.
Adapter chỉ partial text/schema; không full M1 compatibility hoặc production OCR accuracy.
Phiên nghiệm thu chỉ planning; không chạy lại Gemini/tests/pilot, không yêu cầu CI mới.
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2 hoặc web demo.
Các đoạn sau là lịch sử.

**M1-14 DONE** — Tech Lead APPROVED có điều kiện; offline4 pages/46 labels/18 values.
Common26: A/B24/26, C26/26; số6/6 cả ba; C tables0/4 accepted.
[Report](../docs/reviews/M1-14-evaluation.md); [CI 40615555237](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40615555237) PASS đúng `176844cec032c792152c82326a7935a8c31045f8`, Python3.11/3.12.
Hybrid là provisional architecture recommendation, không chứng minh accuracy vượt trội.
Giữ4 trang, nhãn chưa human second review, C chỉ2 trang, chưa full table/bbox ground truth.
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2 hoặc web demo.
Các đoạn sau là lịch sử.

**M1-13b DONE** — Tech Lead APPROVED có điều kiện; component validation, v2 OCR prompt và verified BED crop.
Replay baseline45/2/32 → new55/0/41 text/tables/cell texts; geometry unresolved.
18 focused passed;3 attempts/2 successes/1 crop timeout,10059 known tokens +unknown usage1.
[Spec](tasks/M1/M1-13b.md), [evidence](../docs/reviews/M1-13b-evidence.md).
[CI 40614067957](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40614067957) PASS đúng `d5b12de433b561d8d330b5b0024095d11a62b279`, Python3.11/3.12.
Giữ OCR mới0 tables accepted, geometry0 accepted, crop timeout, chưa accuracy toàn dataset.
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M1-14.
Các đoạn sau là lịch sử.

**M1-13a DONE** — Tech Lead APPROVED có điều kiện; Gateway nhận PNG bytes, verified image binding, corrected view riêng;
image-only Structured OCR pilot. 219 tests; live4 requests/28506 tokens; corrections0,
structured unresolved2 (invalid column indices), lỗi chữ vẫn bị bỏ sót, geometry chưa tin cậy.
[Spec](tasks/M1/M1-13a.md), [evidence](../docs/reviews/M1-13a-evidence.md).
[CI 40611646012](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40611646012) PASS đúng implementation `d8c2e6df215f234cd17e7ae8d03bb63c1ffc04a1`.
Giữ correction0, structured OCR0/2 valid, bbox chưa đáng tin; nghiệm thu chỉ planning.
Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M1-14.
Các đoạn sau là lịch sử.

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
Dừng trước send kế tiếp vì input-token reservation; 18 focused +146 regression passed.
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
