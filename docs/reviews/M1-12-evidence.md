# M1-12 — Evidence

2026-10-27 (Asia/Bangkok). **M1-12 DONE — Tech Lead APPROVED**.
Cho phép REVIEW → DONE sau review implementation/source/tests/evidence và CI.
Baseline `0dd9bd1` main/origin sạch sau fetch; M1-11/M1-11b DONE.
User cho phép implement/test/commit/push; không đổi contracts/classifier/nguồn.

Deterministic API `reconstruct_table` trả UnderstoodTable DU v1; SpanEvidence là
runtime annotation bind exact raw cell. Grid/merges/placeholders/source checks,
không tạo/sửa nội dung. Không Gemini API: **0 requests, 0 tokens**.
Không checkpoint/cache mới; unresolved không được đánh verified.
[Usage/limitations](../table-reconstruction.md), [spec](../../planning/tasks/M1/M1-12.md).

Local môi trường .venv với dev tools: **14 focused +205 related regression =219 passed**
(DU contracts, OCR loader, classification). Ruff lint/format toàn repo đạt;
planning/diff đạt trước commit. Full local suite không chạy, CI phụ trách.
Thêm regression sau review code: duplicate tọa độ giữa các placeholders đã chú giải
vẫn phải unresolved, không được che conflict bằng cách gộp anchors.

Real validation: chỉ **4/23 frozen M1-04b pages**, indices 0/2/4/5 đã chốt ở spec;
3 mã/3 strata, 8 tables, **310 raw/output cells**, không span annotations thật.
**1 resolved/7 unresolved**. Cả 318 table/cell anchors được DU đối chiếu nguồn;
DU chỉ có 47 `empty_text`, không source linkage/status conflict.

| Issue | Occurrences |
| --- | ---: |
| metadata_bbox_conflict | 2265 |
| cell_bbox_out_of_bounds | 32 |
| missing_grid_positions | 5 |
| observed_empty_cell | 47 |

Occurrences không phải số bảng hoặc error rate; geometry conflicts đếm theo cặp.
8 selected JSON/evidence snapshots (4 JSON +4 evidence inputs) giữ hash/metadata;
manifest so sánh nội dung trước/sau; raw fingerprints trong RAM bất biến. Không
đọc/ghi ảnh/crops hoặc scan dataset. Report private ignored, không commit source.
Có tokens mã B09 trong OCR của 3 trang; 1 trang không quan sát các mã được ưu tiên.
Không mở rộng đọc pages để tìm B01/B02/B03; không coi token mã là nhãn đã nghiệm thu.

Không ground truth real rowspan/colspan; chỉ fixture synthetic có nhãn chứng minh
semantics. Không claim reconstruction accuracy/financial correctness hoặc OCR run
identity. Deterministic reconstruction bảo thủ, 2265 pairwise geometry conflicts;
strict geometry có thể abstain nhiều; missing trailing rows/cols cần shape
đã review; extras producer chưa chốt. Gemini-assisted và stage checkpoint deferred.

Implementation `01b235cc83f08e3df86ac8341370ee43ebc866e8` đã push main;
[CI 40514937586](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40514937586) **success exact SHA**: mọi steps ở Python 3.11/3.12,
bao gồm full unit suite, đã xác minh bằng run/job summary. Không đọc lại logs PASS.
Working tree sạch, HEAD/origin khớp trước checkpoint docs evidence cuối;
checkpoint này chỉ docs/planning, không đổi implementation hoặc rerun API/tests.

Nghiệm thu 27/10/2026: review checkpoint `c38df351a6f4d86393b69e57fe2e3b3a15a4da6b` /
[CI 40515264179](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40515264179) success exact SHA đã xác minh; HEAD/origin sau fetch khớp,
working tree sạch trước acceptance. Chỉ sửa bảy docs/planning files để ghi nhận DONE;
không thay source/tests/contracts/raw/artifacts/credentials hoặc rerun API/full local
suite. Checks acceptance đạt: Ruff lint/format, planning checker, git diff --check;
acceptance SHA/CI xác minh sau push và báo cuối, không tự tham chiếu commit.

**M1-12a — Gemini-Assisted Table Reconstruction** là follow-up đề xuất, TODO trong
[roadmap](../../planning/roadmap.md#m1-12a); chưa giao triển khai, scope/budget TBD.

Exact next action: Chờ Tech Lead giao task; không tự bắt đầu M1-12a hoặc M1-13.
