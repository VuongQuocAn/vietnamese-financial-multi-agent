# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

- **M2-04b DONE** — Tech Lead APPROVED ngày 2026-10-28 trong phạm vi Research MVP Lean v3;
  nghiệm thu planning-only. M2-04a và các task trước giữ DONE, M2-05 giữ TODO.
- PDF BBS2025 chỉ trang5/7/8: B01/B02/B03 mapped đúng5/5/4, accepted đúng10/10/8,
  0 sai;28 Decimal,0 uncertain,108 unresolved. Baseline40:28 accepted/12 unresolved.
- Runtime không ManualReview; Gemini5 calls gồm2 recovery,0 transport retry;
  provenance PDF/ảnh/model/request/selectors, financial_fact_verified=false.
- Chỉ nghiệm thu3/24 trang của một PDF,một reviewer đánh giá sau chạy;
  chưa chứng minh accuracy toàn dataset hoặc verified financial facts.
- 70 targeted PASS; [API/evidence](../docs/automated-financial-extraction.md),
  [spec](tasks/M2/M2-04b.md), [issue](tasks/M2/issues/M2-04-numeric-linking.md).
- [Implementation](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/912916ed1318628750e160e28338a211e5fc2819);
  [CI40646568615](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40646568615)
  SUCCESS đúng SHA, mọi bước Python3.11/3.12 đã xác minh lại.
- Baseline nghiệm thu local/origin sạch `d8f92373c1bc32bcee5f22c3ff051e21cb022355`.
  Phiên này chỉ năm file planning, planning checker và diff check;
  không chạy lại Gemini/pytest/CI, không đổi implementation/tests/schema/nguồn.
  Không gán CI implementation cho SHA nghiệm thu planning-only.
- Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2-05.
