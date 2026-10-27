# M1-11a — Bounded Real Classification Pilot

Cập nhật 2026-10-27 (Asia/Bangkok); **M1-11a DONE — Tech Lead APPROVED**.
Tech Lead đã review implementation/source/tests/evidence/CI, cho phép REVIEW → DONE.
M1-11 DONE; không tự bắt đầu M1-12 hoặc task khác.

## Phạm vi và nguồn

Baseline HEAD/origin `e5ae508c69bbbe7e2543e8c9b5973cbaa5fa51b5` sạch/khớp sau fetch.
Tái sử dụng frozen M1-04b (23 pages), verified local plan/index/ledger binding và
selected OCR snapshots. Chọn 19 pages theo coverage trước/risk sau, phủ 3 symbols,
14 symbol/year strata. Không scan dataset, sửa raw/crops/PDF hoặc đổi M1-11/contracts.
Parent manifest có 14/15 strata; không bổ sung nguồn ngoài pool để lấp thiếu.

Raw OCR Loader đối chiếu identity/image từ approved binding; external source_ref là
exact verified OCR artifact locator, không dùng chung inventory ref làm document ID,
không tự tạo OCR run identity. Run identity gốc vẫn unverified. [Usage](../classification-pilot.md).
Các manifests/reports/checkpoints chỉ nằm trong ignored artifacts, không commit.

## Live authorization và điều kiện

Người dùng xác nhận quyền gửi mọi trang BCTC, tài khoản free tier, quota tham khảo
15 RPM/250000 TPM/500 RPD đúng cho selected credential/model, không ứng dụng khác dùng
API. Chọn duy nhất key index 0; không chuyển key/retry. Không public key/project IDs,
OCR text, per-file hashes hoặc local paths. Key file ignored/untracked và giữ nguyên.

Project/account là opaque local aliases bind selected key theo owner attestation;
không suy project ID hoặc claim độc lập xác minh Google quota remaining.
[Google Standard pricing](https://ai.google.dev/gemini-api/docs/pricing) đối chiếu ngày
27/10/2026 liệt kê input/output free cho model. USD 0 cap/estimated cost phụ thuộc
user-confirmed free tier và tariff; **actual provider billing unknown**. Guard money
status NOT_CONFIGURED được công khai; không giả actual LLMResponse.cost=0, không paid fallback.
[Quota áp dụng theo project](https://ai.google.dev/gemini-api/docs/rate-limits).

## Aggregate observations

| Chỉ số | Kết quả thực tế |
| --- | --- |
| Selected/dry-run pages | 19, 3 symbols, 14 strata; API calls 0 |
| Selected pages có OCR quality issues | 17/19 |
| Connectivity smoke | Thành công, synthetic input, đúng local schema/model |
| Actual Gemini requests | 6 = 1 smoke + 5 real page requests |
| Successful SDK responses | 6; không failed network request |
| Completed real pages | 5; 6 page attempts, gồm 1 local pre-send denial |
| Live coverage | 1 symbol, 5 năm/strata; subset dừng sớm, không đại diện 3 symbols |
| Resolved / unresolved (5 completed pages) | 0 / 5 |
| Common unresolved causes | ocr_quality_review: 4; insufficient_evidence: 1 |
| Schema / actual provider errors | 0 / 0 |
| Local budget denial | 1, input_token_limit trước khi gửi trang kế tiếp |
| Checkpoint hits live | 0 (không có resolved result đủ điều kiện lưu) |
| Cache hits live | 5 probes, không phát sinh API request mới |
| Evidence anchors checked | 8 source anchors đối chiếu DU quality validator với raw |
| Provider-reported usage | 12307 input, 176 output, 12483 total tokens |
| Unknown usage | 0 trong 6 actual responses |
| Input budget charge | 12307; request tiếp theo có conservative upper bound vượt phần còn lại |
| Estimated cost | USD 0 theo free-tier attestation/tariff; billing thực tế unknown |
| Source preservation | Selected OCR/evidence snapshots trước/sau khớp; không sửa nguồn |

Không cố dùng hết 20000 input tokens: pre-send reservation phải đủ bound cho request
tiếp theo. Dừng sớm ở 5 real pages thay vì 10–20 mục tiêu vì hard token cap, không mở rộng
hoặc truncate input để vượt gate. Starts cách nhau >=12,1s tại SDK boundary, guard RPM<=5,
RPD<=20; live marker exclusive chặn run mới/reset accounting sau restart.

### Đính chính thống kê sau live, không gọi lại API

Original private live report giữ nguyên. Nó đếm 6 classifier attempts thành processed/
unresolved và 1 provider_error vì local SDK-boundary denial được GeminiAdapter biểu diễn
thành provider_unavailable. Actual meter vẫn ghi 6/6 API responses thành công, 5 real calls,
failed requests 0, stop_reason=input_token_limit. Đây là lỗi phân nhóm thống kê của runner.

Đã sửa runner để tách attempted/completed pages, local budget denial, guard/provider/schema
và usage failures, kèm focused regression. Không sửa classifier/Gateway/adapter. Private
interpretation riêng loại đúng một slot chưa gửi API khỏi completed/provider denominator,
đối chiếu quality issue của slot đó; không ghi đè original report. Table trên dùng
observed counters và phép đối chiếu này, **không phải kết quả chạy lại corrected runner**.

## Validation và readiness trước M1-12

- 17 focused synthetic tests passed; 146 related regression tests passed. Fake SDK only,
  không keys/network trong unit tests. Ruff lint/format, planning/diff đạt; full local
  suite không chạy lại, CI đảm nhiệm.
- Synthetic kiểm tra resolved checkpoint HIT/resume không gọi LLM, unresolved cache HIT,
  failed smoke không gửi real data, schema/auth/quota failures, request/token/rate caps,
  source change và local denial không bị tính thành provider failure/completed page.
- Live xác minh API/model access/structured schema trên selected key; checkpoint live
  **chưa được xác minh bằng HIT**, synthetic test chỉ chứng minh engineering behavior.
- 4/5 completed pages bị OCR quality gate chặn; gate hiện kiểm tra mọi raw quality issue,
  kể cả issue ngoài classification evidence. Đây là dấu hiệu policy có thể quá bảo thủ,
  không chứng minh nên bỏ kiểm tra hoặc OCR/nhận diện label sai.
- Một trang insufficient_evidence; continuation/appendix/mất title/code vẫn cần human review.
  Taxonomy B01/B02/B03/B09 provisional; không nhãn tham chiếu độc lập, không confusion matrix
  hoặc accuracy. Anchors đã kiểm tra linkage/bbox, không chứng nhận đọc hiểu tài chính đúng.
- Tech Lead yêu cầu hai follow-up: **đánh giá lại OCR quality gate** và **loại bỏ giới hạn
  20.000 input tokens tùy ý ở pilot tiếp theo**. Chỉ ghi nhận trong acceptance; không sửa
  gate/cap trong code hiện tại, không thay kết quả lịch sử hoặc tự chạy pilot mới.
  Sampling order vẫn là limitation (live dừng sớm nên chỉ phủ 1 symbol).
  Engineering access đã verified; financial/dataset readiness và taxonomy approval vẫn TBD.

Implementation **063bd2935a47832d928a6869ea35a2bd0cf6f9f2** đã push;
[CI 40505711042](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40505711042)
success exact SHA. Đã kiểm tra headSha, jobs và mọi steps Python 3.11/3.12 success;
logs mỗi job **1130 passed/11 skipped**. CI chứng minh engineering checks, không rerun live.
Review checkpoint **ad2a1664faa33f54ccc90e4a0cbace41ab48fbc7** /
[CI 40506143468](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40506143468)
success exact SHA Python 3.11/3.12 đã kiểm tra lại trước acceptance.
Acceptance chỉ 7 docs/planning files; local Ruff/planning/diff, không unit/Gemini rerun,
không sửa production code/tests/contracts/API keys hoặc runtime artifacts.
Acceptance SHA/CI xác minh riêng sau push và báo cuối, không suy từ CI cũ hoặc tự tham chiếu.

Next action: Chờ Tech Lead giao việc; không tự bắt đầu M1-12 hoặc task khác.
