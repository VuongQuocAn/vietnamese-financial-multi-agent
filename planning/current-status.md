# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-15 DONE** — Tech Lead APPROVED có điều kiện; không task triển khai active.
- Baseline `160de34cd06c8d500c2159be6a93f0f964f594e4`, tree sạch lúc bắt đầu.
- PDF BBS 2025 thật 24 trang scan; chọn 5/7/8/14/15, render200 DPI giữ hashes.
- PDF/PNG ingestion; live5/5,58 text/505 cell texts accepted, tables0/10 accepted.
- Partial DU schema5/5, raw-loader/DU quality0/5; geometry unresolved624.
- 5 requests/50541 tokens, failures0; source bất biến;8 focused tests/local checks đạt.
- [Evidence](../docs/reviews/M1-15-evidence.md); [CI 40618548302](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40618548302)
  PASS đúng implementation `c95e2be2982d5c86d9beb9508a8307455c96e53e`, mọi steps Python3.11/3.12 success.
- Adapter chỉ partial text/schema; không full M1 compatibility hoặc production OCR accuracy.
- Nghiệm thu chỉ planning, không chạy lại Gemini/tests/pilot; không yêu cầu CI mới.
- Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2 hoặc web demo.
