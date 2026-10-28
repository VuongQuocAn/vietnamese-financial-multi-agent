# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M2-03 DONE** — Tech Lead APPROVED ngày 2026-10-28 trong phạm vi Research MVP; M2-02 DONE.
- Resolver từng trang và inventory tài liệu không kế thừa nhãn; giữ raw/provenance/M1 status.
- [Spec](tasks/M2/M2-03.md), [API/evidence](../docs/statement-type-recognition.md).
- Implementation `972d124ccd03d840375e37a3bbbcc62ed2eacb01`; [CI 40639663139](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40639663139) SUCCESS đúng SHA, Python3.11/3.12 và mọi steps đã xác minh lại.
- Baseline nghiệm thu sạch local/origin `063eca618f0ad3ab3d3539282c95d0e8e3e67c84`; chỉ docs/planning thay đổi từ implementation, code/tests/schema giữ nguyên.
- Bằng chứng trước nghiệm thu: 11 focused +18 regression PASS; pilot 8 trang có 6 resolved đúng, 0 sai, 1 uncertain, 1 unresolved; đủ B01/B02/B03/B09, hash7 nguồn không đổi.
- Pilot chỉ theo OCR text, chưa đối chiếu trực tiếp PDF/ảnh hoặc second reviewer; chưa chứng minh accuracy toàn dataset.
- Phiên nghiệm thu chỉ 5 planning files; planning checker82/diff check PASS, không chạy lại pytest/Gemini hoặc yêu cầu full CI mới. Không gán CI implementation cho commit planning mới.
- Next action: Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M2-04.
