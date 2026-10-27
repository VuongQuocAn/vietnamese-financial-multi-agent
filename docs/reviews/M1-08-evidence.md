# M1-08 — Evidence

- Scope: một core wrapper/registry, in-memory lock, explicit mappings, atomic quota/
  budget reservations, conservative reconciliation và zero retry/rotation. Contracts,
  Gateway/Gemini source không đổi; config committed chỉ synthetic aliases.
- Baseline sạch main/origin **07395250c118af4573efdcce1c34a56eda64f13f** /
  [CI 40463429448](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40463429448)
  success. M1-06/M1-07 DONE; user cho phép implementation/commit/push, dừng REVIEW.
- Local: **39 quota tests passed**, cùng **66 Gateway/Gemini regression tests passed**,
  tổng **105 passed**, zero skips. Ruff/planning/diff và example offline kiểm tra trước
  publication; full suite dành cho CI Python 3.11/3.12. Không API/key file/dataset.
- Implementation **f895d74ca4267abc6b3c740419890d800437dd76** /
  [CI 40466483190](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40466483190)
  success exact SHA, mọi steps Python 3.11/3.12 verified; mỗi job **1006 passed/11 skipped**.
  User nghiệm thu REVIEW → DONE ngày 27/10/2026; finalization chỉ docs/planning,
  không lặp local unit suite/live API. CI acceptance xác minh riêng sau push và báo cuối.
- Limits 15 RPM/250K TPM/500 RPD là configured/task-reported, không independently verified
  từng project trong phiên này; không private mappings trong evidence/config.
- Limitations: single process/shared guard, no restart recovery/global enforcement;
  explicit fresh-scope initialization và trusted caller bounds bắt buộc. Unknown cost
  giữ ceiling, money NOT_CONFIGURED nếu chưa bật. No pricing/FX/cache/rotation/live test.
- Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M1-09.
