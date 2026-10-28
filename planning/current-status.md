# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-16 DONE** — Tech Lead APPROVED có điều kiện trong phạm vi Research MVP.
- Baseline `e80319975b1eeef79efc68fac5007980cb20a2a7`; main/tree sạch trước sửa.
- Entrypoint chung OCR JSON/PDF/PNG và persisted manifest/PNG replay.
- Existing BBS2025/page5:6 text/1 table/97 cells được giữ; table unresolved.
- Native pages5/7/8:33 text/3 tables/335 cells giữ đủ;289 cell texts accepted/46 unresolved.
- 3 native tables unresolved, geometry0 verified; không bbox/IDs giả;0 API mới.
- Hash nguồn đọc trước/sau khớp; manifest replay không rehash PDF gốc.
- 10 focused +77 loader regression passed; Ruff/planning/diff checks local đạt.
- [Evidence](../docs/reviews/M1-16-evidence.md), [API](../docs/unified-document-understanding.md).
- Implementation `7486a6140ac075b90d2c2454f6703b6a56186b1a`; thêm commit sửa format
  code fence Markdown do CI40620767512 phát hiện; code/tests/replay không đổi.
- [CI 40620923159](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40620923159)
  completed/SUCCESS đúng HEAD `d2df004e3cf347713028ba958abbbb56aec7cb20`;
  cả Python3.11/3.12 và mọi bước liên quan success.
- Output chỉ đủ text_evidence, chưa chứng minh financial accuracy.
- Phiên nghiệm thu chỉ planning; không chạy lại code/tests/replay/Gemini, không yêu cầu CI mới.
- Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2 hoặc web demo.
