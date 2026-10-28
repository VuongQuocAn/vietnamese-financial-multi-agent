# Trạng thái hiện tại

Cập nhật 2026-10-28 (Asia/Bangkok); nguồn [Registry](tasks.md).

- **M2-04 DONE; M2-04a IN_PROGRESS** chờ commit/push và CI exact implementation SHA.
- Gemini model gemini-3.5-flash-lite: 3 calls thành công, 0 retry. Pilot 40 ô: 6 accepted đúng, 0 sai, 12 rejected ngoài catalog, 22 unresolved. [Issue](tasks/M2/issues/M2-04-numeric-linking.md), [API/evidence](../docs/table-recovery.md).
- Một reviewer đối chiếu ảnh; binding, cấu trúc, geometry và OCR witness được kiểm tra. Geometry Gemini/OCR chưa tin cậy; không verified financial facts hoặc accuracy toàn dataset.
- 14 focused + 12 M2-04 regression PASS; Ruff, planning checker 83 và diff check PASS; hash 8 nguồn không đổi.
- Baseline HEAD/origin `c26e3bf3f84cd88d429be5275469c64ddc096c7b`; implementation chưa commit.
- Next action: Commit/push implementation và kiểm tra CI exact SHA, sau đó chuyển REVIEW.
