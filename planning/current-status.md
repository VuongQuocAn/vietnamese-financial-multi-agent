# Trạng thái hiện tại

Cập nhật **2026-10-27** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-11a IN_PROGRESS**, bounded pilot hoàn tất; chờ publication/CI để REVIEW.
- M1-11 DONE, M1-12 TODO. Baseline HEAD/origin `e5ae508c69bbbe7e2543e8c9b5973cbaa5fa51b5`.
- Dry-run verified 19 OCR pages /3 symbols/14 strata, 17 pages có raw quality issues.
- Live smoke đạt; 5 real pages nhận response, 6 actual API requests tổng cộng,
  12307 input/176 output/12483 total tokens. 0 resolved/5 unresolved (4 quality/1 insufficient).
- Cache HIT 5 probes không API thêm; checkpoint HIT live 0, synthetic có verified resume.
- Dừng tại local pre-send input-token bound, 1 budget denial, 0 actual provider/schema errors.
  Original private report giữ nguyên; metrics interpretation riêng, runner có regression fix,
  không gọi lại API. Source snapshots không đổi.
- Owner xác nhận data export/free tier/quota applies selected key/model/no other apps.
  Một key index 0, một client; opaque project/account aliases, no rotation/retry.
- USD 0 estimate theo confirmed free tariff; actual billing unknown, guard money
  NOT_CONFIGURED; Google project ID/quota remaining không independently verified.
- 17 focused +146 related regression passed; final static checks trước publication.
- Raw/contracts/classifier/Gateway/keys bất biến; runtime chỉ ignored artifacts.
- Taxonomy provisional/text-only gate bảo thủ; live subset 1 symbol/5 years, không accuracy.
- [Spec](tasks/M1/M1-11a.md), [usage](../docs/classification-pilot.md),
  [evidence](../docs/reviews/M1-11a-evidence.md).
- Next action: **Commit/push M1-11a và xác minh exact-SHA CI trước REVIEW.**