# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-13a DONE** — Tech Lead APPROVED có điều kiện; M1-13 DONE, M1-14 TODO.
- Verified original PNG bytes qua Gateway/Gemini, fail closed; corrected view giữ raw,
  không confirmed; image-only Structured OCR có output riêng, không ingestion mới.
- 219 focused/related tests passed; final focused9 sau cleanup; Ruff/planning/diff đạt.
- Live đúng hai trang M1-13/BCC14/BED39:4 requests,22531 input/5975 output/28506 total;
  unknown0/provider failures0; correction0, **structured unresolved2** (columns/index).
- Vision vẫn bỏ sót hai lỗi chữ biết trước; structured sửa đúng header nhưng vẫn thêm
  từ sai; bbox/axes không tin cậy. Không accuracy, không tự xác nhận số tài chính.
- Raw/image snapshots/manifest bất biến. Private artifacts ignored
  `artifacts/ocr-correction/M1-13a/`; không repeat API để cải thiện kết quả.
- Implementation `d8c2e6df215f234cd17e7ae8d03bb63c1ffc04a1`;
  [CI 40611646012](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40611646012) completed/success đúng SHA.
  Điều kiện CI đạt, REVIEW → DONE; giữ correction0, structured OCR0/2 valid, bbox chưa đáng tin.
- Phiên nghiệm thu chỉ planning; không sửa code/chạy lại Gemini/tests/pilot; một commit/push,
  không yêu cầu CI mới. Không task triển khai active.
- [Spec](tasks/M1/M1-13a.md), [evidence](../docs/reviews/M1-13a-evidence.md).
- Next action: **Chờ Tech Lead giao task tiếp theo; không tự bắt đầu M1-14.**
