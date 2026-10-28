# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M2-03 REVIEW**; dependency M2-02 DONE đã xác minh/push.
- Resolver từng trang và inventory tài liệu không kế thừa nhãn; giữ raw/provenance/M1 status.
- [Spec](tasks/M2/M2-03.md), [API/evidence](../docs/statement-type-recognition.md).
- Local 11 focused +18 regression PASS; Ruff/planning82/diff PASS.
- Pilot8:6 resolved đúng/0 sai/1 uncertain/1 unresolved; đủ B01/B02/B03/B09.
- Hash7 nguồn không đổi; chỉ OCR text, không kiểm tra trực tiếp PDF/ảnh hoặc Gemini.
- Baseline ổn định e1c84783fea5487c1f2b1e8ae77c1ccbfcaf65e1; implementation chưa commit.
- Chờ CI exact SHA và Tech Lead nghiệm thu; không M2-04.
- Next action: Commit/push implementation và xác minh CI đúng SHA.
