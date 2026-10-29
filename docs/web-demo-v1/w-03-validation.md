# W-03 — Final refinement evidence

Ngày 28/10/2026 (Asia/Bangkok), Research MVP Lean v3.
W-03 REVIEW, refinement auto-first/key rotation, không task mới.

Checkpoint housekeeping 2026-10-29 trên main ở phần10; các phần1–9 giữ bằng chứng
refinement trước merge, không dùng trạng thái PR draft cũ làm trạng thái hiện tại.

## 1. Git / PR / CI

Baseline refinement f617e68295f79de1c5702fe8c27f7b0fcfcea0b1.
Nhánh feat/w-03-pdf-upload-metadata, [PR #3](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/pull/3)
draft OPEN base W-02; PR #1/#2 OPEN. Không merge. Giữ next-env local ngoài stage.
Implementation/refinement SHA 7048d92ba7215191dd8a5c9c12b777085fb9c23d đã push,
ls-remote khớp. [CI40718128314](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40718128314)
SUCCESS exact implementation SHA, đã kiểm mọi steps của Python3.11/3.12 và Web.
Commit evidence tiếp theo chỉ docs/planning [skip ci], không gán CI cho SHA mới.
CI40710376652/b494788 là lịch sử baseline, không gán cho code refinement.

## 2. Key rotation

Chỉ GEMINI_API_KEY_FILE; regex hợp lệ/dedupe, dùng key thành công hiện tại.
429→cooldown max(default60,retry-after), auth/disabled key→tạm loại trong phiên,
thử key khác tối đa min(3,n). SDK 400 API_KEY_INVALID/EXPIRED/SERVICE_BLOCKED được
normalize thành authentication; RetryInfo được giữ thành retry-after an toàn.
Timeout/server error không tự retry speculative ở key khác.

Một pool dùng chung cap attempts RPM/RPD và token reservation TPM, kể cả rotated
attempts, không nhân quota theo số keys. Atomic counters chung trước call, giữ
qua restart, không key values. Không giả confirmed Google project mapping;
composition admission dùng core GuardResult/QuotaLimits/Reservation và existing
SharedLLMGateway/GeminiAdapter/CachedLLMService, core/M1–M2 không sửa.

User xác nhận Free Tier; theo [Google pricing](https://ai.google.dev/gemini-api/docs/pricing)
model hiện hành có Free Tier. Không tự đổi model/tier/bật billing. Key file/usage
không chứng minh billing từng project; cost unknown giữ nguyên, không ghi cost=0.

## 3. Auto-accept

Tên/năm hợp lệ, resolved, một giá trị nhất quán, raw text + source PDF page →
accepted=true/origin=auto, ready; không cần ticker/period/scope hoặc confirm.
accepted khác confirmed (chỉ user). Auto tăng revision và ghi acceptance_history.
User PATCH giữ suggestions, revision conflict, edits origin=user; retry không
ghi đè user values. Auto metadata được đánh giá lại khi retry, không giữ accepted
nếu nguồn mới chưa đủ. Legacy user-confirmed snapshots vẫn đọc tương thích.
Không ghi đè FinancialContext M1–M2; không financial extraction trong W-03.

Response invalid/thiếu core tiếp tục trang sau trong caps; nguồn resolved sau
có thể làm rõ cùng candidate uncertain. Nhiều giá trị mâu thuẫn giữ uncertain,
không chọn tùy tiện. Schema metadata_v2 flat cho serving, runtime strict validation
giữ nguyên; metadata adapter gộp batch thành một user turn có nhiều parts.

## 4. UI và đơn giản hóa

UI “Hệ thống đề xuất”, không provider/model; thông tin accepted hiển thị ngay,
origin auto/user rõ. Nút Chỉnh sửa thông tin mở form tùy chọn, thiếu core ưu tiên
Thử nhận diện lại. Desktop 1440/1366; mobile tối thiểu, không pixel-perfect.
Bỏ manual project/policy/fingerprint/accounting scope và consumed-scope marker
trong composition Web; xóa config example obsolete. Giữ PDF/secrets/size/path/
writer protections hiện có, không thêm security/auth framework. Tests cũ giữ,
chỉnh expectations và thêm ít regression cho rotation/auto core; CI không đổi.

## 5. Live Gemini smoke

PDF 2 trang được tạo bằng Pillow, không text layer (PDFium kiểm), không tài liệu
tài chính thật. Trang 1 cover; trang 2 in metadata của công ty tổng hợp. Không
có financial values. Qua HTTP upload/background worker/shared Gateway/provider thật.

Successful run: model requested/provider-reported gemini-3.5-flash-lite.
1 call thành công, analyzed_pages=[1,2], stop_reason=sufficient_evidence:
company_name=SYNTHETIC LOTUS RESEARCH COMPANY; reporting_year=2025;
stock_ticker=null; reporting_scope=separate; reporting_period=2025-12-31,
type=fiscal_year_end. Tên/năm/scope có raw text và nguồn PDF trang 2.
Document tự ready/origin auto/revision1, không user confirm. PATCH chỉnh tên
sau đó ready/origin user/revision2, giữ AI suggestions; PASS.

Usage provider: input2411/output394/total2805 tokens. Cost unknown.
Tổng phiên có 3 gateway/provider attempts: 2 request HTTP400 invalid_request
ban đầu (usage unknown), sau serving-schema flatten + coalesce user turn thì
1 successful run nêu trên. Không chứng minh riêng thay đổi nào là nguyên nhân
duy nhất của HTTP400. Không cố đốt quota để thử rotation; 429/auth được test fake.
Không gọi thêm live sau PASS và không benchmark M2-09.

Local ignored evidence: artifacts/w-03-refinement-live/6390bd8f-6d70-4aca-9440-0ea9321117b9/report.json.
Hai report lỗi cũng giữ local. Không commit PDF/rendered images/key/cache.
Đây là engineering/synthetic live integration, không metadata/financial accuracy
trên báo cáo thực hoặc dataset, không tuyệt đối verified financial facts.

## 6. Validation

Targeted Python upload/metadata/pool/API: 44 PASS, không full local regression.
Ruff check/format, TypeScript/ESLint/build, 8 targeted Playwright documents PASS
(ready không form bắt buộc 1440/1366, upload/drop/list/edit/retry/errors, mobile
layout giữ từ trước). Planning checker/diff/staged audit trước commit.
CI exact refinement SHA PASS: Python3.11/3.12 mỗi job1502 PASS/11 SKIP;
Web typecheck/lint/build và full browser suite13 PASS. Planning/diff/staged audit
PASS; không key/PDF/cache/counters/next-env hoặc protected module trong commit.
Không sửa/tắt CI, không gọi mock SDK là live pass.

## 7. Local demo

[Usage và lệnh chạy](w-03-usage.md). Backend đặt duy nhất key file rồi uvicorn;
frontend npm.cmd run dev. Không policy JSON/project ID/fingerprint/scope thủ công.
Live smoke opt-in: python scripts/smoke_web_metadata.py --live, có cap attempts.

## 8. Hạn chế

Project/billing không suy từ key; cap local không thấy usage ứng dụng khác,
provider vẫn enforce quota. Key cooldown/state in-memory, global counts durable;
cache TTL không là durable page replay. Một API process/worker, local single-user.
Partial/conflict cần retry hoặc user edit khi không đủ nguồn. Live chỉ synthetic
2 trang; chưa chứng minh accuracy báo cáo thật. W-04/W-05/M3 chưa triển khai.

## 9. Final status

**W-03 REVIEW**. Next action: Tech Lead nghiệm thu độc lập W-03.

## 10. Housekeeping sau W-03 — 2026-10-29

Người dùng cho phép merge tuần tự và thêm launcher, không W-04. Đã merge-commit
(không squash/force/delete branch), retarget PR#2/#3 sang main trước từng merge:

| PR | Merge SHA | CI main sau merge |
| --- | --- | --- |
| #1 | 167e8fa7d386bea1f9a2232eec86fc9e00399eee | [40790312165](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40790312165) SUCCESS |
| #2 | cb9efeb7057acab80eb7f500b422d101b327bdc6 | [40790598368](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40790598368) SUCCESS |
| #3 | 6dd0d1d7c3fd2d92e3fc62d091348eb832d3c28e | [40790882421](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40790882421) SUCCESS |

Trước PR#1: backport đúng formatting fence đã có ở W-02, commit5779d45,
[CI40789894796](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40789894796)
SUCCESS trên exact head. Không đưa known format failure lên main. PR#3 được
bỏ draft theo quyền merge được user cấp. Không tự đổi W-03 DONE.

dev.ps1: check Python/.venv/backend imports, Node24+/Next dependencies, key file
từ process env/root.env/fallback local; không prompt/print key. Root .env chỉ
parse dữ liệu, secrets chỉ vào backend. Hai process chung console, Ctrl+C cho
graceful shutdown rồi cleanup đúng PID tree/start time nếu còn; không kill theo
tên/port. Có port overrides/proxy/origin phù hợp, busy port fail trước launch.

Windows PowerShell syntax PASS; real one-command startup PASS. HTTP health trực
tiếp/proxy và trang web PASS. Upload PDF raster synthetic2 trang qua Next proxy
→ Gateway/Gemini thật1 call → ready/auto, tên/năm2025/scope riêng lẻ đúng nguồn;
model gemini-3.5-flash-lite, input2411/output383/total2794 tokens, cost unknown.
Không benchmark hoặc accuracy dataset. Report/PDF chỉ ở ignored artifacts.
Không chạy lại AI sau call thành công.

Ctrl+C PTY thật: Uvicorn báo shutdown complete, hai cổng3000/8000 không listener.
Busy-port test giữ listener có sẵn, không mở server. Custom ports8100/3100:
proxy health200, valid Origin nhận415 cho non-PDF, cross-site403; không AI call.
Chủ động dừng backend test: launcher tự dừng Next.js, không orphan/listener.
Không thêm Docker/auth/infra. Temporary worktree/stash/Next-generated AGENTS đã
cleanup; next-env khôi phục byte-for-byte và không stage. Git main sau merge
6dd0d1d; launcher/docs publication SHA/CI ghi sau push.
