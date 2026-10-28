# Trạng thái hiện tại

Cập nhật **2026-10-28** (Asia/Bangkok). Nguồn: [Registry](tasks.md).

- **M1-13a REVIEW** theo user; M1-13 DONE, M1-14 TODO.
- Verified original PNG bytes qua Gateway/Gemini, fail closed; corrected view giữ raw,
  không confirmed; image-only Structured OCR có output riêng, không ingestion mới.
- 219 focused/related tests passed; final focused9 sau cleanup; Ruff/planning/diff đạt.
- Live đúng hai trang M1-13/BCC14/BED39:4 requests,22531 input/5975 output/28506 total;
  unknown0/provider failures0; correction0, **structured unresolved2** (columns/index).
- Vision vẫn bỏ sót hai lỗi chữ biết trước; structured sửa đúng header nhưng vẫn thêm
  từ sai; bbox/axes không tin cậy. Không accuracy, không tự xác nhận số tài chính.
- Raw/image snapshots/manifest bất biến. Private artifacts ignored
  `artifacts/ocr-correction/M1-13a/`; không repeat API để cải thiện kết quả.
- Baseline `10b626f`; một implementation commit/push, CI exact SHA kiểm tra sau push;
  không publication commit. Exact SHA/CI ghi trong bàn giao cuối.
- [Spec](tasks/M1/M1-13a.md), [evidence](../docs/reviews/M1-13a-evidence.md).
- Next action: **Tech Lead nghiệm thu implementation và limitations pilot; không tự DONE/M1-14.**
