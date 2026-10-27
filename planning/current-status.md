# Trạng thái hiện tại

Cập nhật **2026-10-27** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-08 REVIEW — candidate chờ CI exact SHA/Tech Lead**; M1-06/M1-07 DONE.
- Baseline sạch main/origin **07395250c118af4573efdcce1c34a56eda64f13f** /
  [CI 40463429448](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40463429448) success.
- Guard quanh Gateway: registry/project-model buckets, explicit credential binding,
  atomic reservation một process, Pacific RPD/DST, conservative TPM và Decimal budget.
  Unknown giữ reservation, không retry/rotation; contract/Gateway/Gemini source không đổi.
- Quota targeted **39 passed**, Gateway/Gemini regression **66 passed**, tổng **105 passed**,
  zero skips. Ruff/planning/diff/example kiểm tra trước publication; full suite trên CI.
- Không đọc key thật, không live API/dataset; config committed chỉ synthetic aliases,
  limits task/user-reported có provenance, không tuyên bố verified từng project.
- [Spec](tasks/M1/M1-08.md), [API](../docs/llm-quota-budget.md),
  [evidence](../docs/reviews/M1-08-evidence.md). State một process, không restart recovery;
  explicit fresh-scope initialization và caller bounds bắt buộc. Money NOT_CONFIGURED
  nếu chưa bật budget, không pricing/FX/cache.
- Exact implementation SHA/CI xác minh sau push và báo cuối, không tự tham chiếu.
- Next action: **Tech Lead review M1-08 sau CI exact SHA thành công**. M1-09 TODO.
