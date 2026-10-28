# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-16 REVIEW** — Unified Document Understanding Pipeline, không tự DONE/M2/demo.
- Baseline `e80319975b1eeef79efc68fac5007980cb20a2a7`; main/tree sạch trước sửa.
- Entrypoint chung OCR JSON/PDF/PNG và persisted manifest/PNG replay.
- Existing BBS2025/page5:6 text/1 table/97 cells được giữ; table unresolved.
- Native pages5/7/8:33 text/3 tables/335 cells giữ đủ;289 cell texts accepted/46 unresolved.
- 3 native tables unresolved, geometry0 verified; không bbox/IDs giả;0 API mới.
- Hash nguồn đọc trước/sau khớp; manifest replay không rehash PDF gốc.
- 10 focused +77 loader regression passed; Ruff/planning/diff checks local đạt.
- [Evidence](../docs/reviews/M1-16-evidence.md), [API](../docs/unified-document-understanding.md).
- Một implementation commit/push; CI exact SHA xác minh sau push, báo cuối phiên.
- Next action: Tech Lead review implementation, CI exact SHA và giới hạn quality.
