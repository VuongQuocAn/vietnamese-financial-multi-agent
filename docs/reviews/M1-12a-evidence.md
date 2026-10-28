# M1-12a — Evidence

2026-10-28 (Asia/Bangkok). **REVIEW**, chờ Tech Lead; không DONE/M1-13.
Baseline `54d198e886fd41dcc8f9f84a26a40ed77b7a4088` = origin/main, tree sạch sau
fetch; M1-12 DONE. [Spec](../../planning/tasks/M1/M1-12a.md), [usage/policy](../table-assistance.md).

`TableReconstructor` tái sử dụng deterministic M1-12, DU v1, loader, Gateway,
Gemini Adapter, quota guard, cache và CheckpointStore. Không đổi contracts/raw/M1-12
artifacts. MeteredModels chỉ thêm optional caps: output512 cũ không đủ grid; defaults
classification giữ nguyên, regression đạt. Prediction không có text/value fields;
text/IDs/bbox output lấy từ raw, tất cả IDs phải xuất hiện đúng một lần.

| Cùng frozen membership | M1-12 | M1-12a |
| --- | ---: | ---: |
| Pages / tables / raw cells | 4 / 8 / 310 | 4 / 8 / 310 |
| Resolved / unresolved tables | 1 / 7 | **2 / 6** |
| DU output cells / source anchors checked | 310 / 318 | 310 / 318 |
| Cells / anchors trong resolved tables | 16 / 17 | 28 / 30 |
| Gemini requests | 0 | **7** |

Source anchors checked chỉ chứng minh linkage, không biến 282 cells của 6 unresolved
tables thành resolved. Không có live merge được accepted; merge semantics được kiểm
tra trên synthetic fixtures có nhãn, chưa ground truth thực tế/accuracy.

7 requests cho đúng 7 unresolved; deterministic resolved giữ nguyên/API0. Model cố định
**gemini-3.5-flash-lite**, text/layout mode, không crop/image binding. Full table
text/cell IDs/bbox/row-col/lines/metadata và OCR provenance; không truncate.
Credential index0, alias `pilot-selected-key-1`, project alias `pilot-selected-project`,
một credential, owner-attested free-only policy M1-11b được dùng lại, rpd giảm còn15.
RPM5/TPM250000, không tổng input cap; per-request bound100000/output cap16384.
Exclusive live marker; no retry/rotation/fallback; không dùng hết budget để gọi lại.

Usage SDK thực tế: **55.620 input +17.177 output =72.797 total tokens**;
requests7/guard admissions7/failures0/unknown usage0, không stop reason.
Guard monetary status **NOT_CONFIGURED**; billing/quota remaining/project ID chưa
independently verified. Không claim provider actual cost0.

Reuse probes khóa API: **7 cache HIT /1 checkpoint HIT**. Process offline riêng:
**1 checkpoint HIT, service0/API0**, không đọc credentials hoặc tạo SDK client.
Cache schema-valid prediction luôn revalidate; chỉ resolved lưu verified checkpoint.
Fingerprint phủ input/provenance/mapping, model, prompt, schema, policy/processing.

6 unresolved còn lại: **4 invalid_cell_coverage**, **1 unsupported_merge**,
**1 missing_grid_positions**. Audit predictions: ba bảng bỏ tổng17 observed empty raw
cells; một bảng lặp source ID. Không invented IDs trong live predictions; local gate
vẫn reject, giữ nguyên deterministic candidates đầy đủ. Fixture kiểm tra invented
IDs/values, data placeholders, collisions, invalid spans, source mismatch/provider/schema.

Bảng mới resolved có12 cells; deterministic chỉ chặn vì **8 cell bbox vượt bbox table**.
Các bbox vẫn valid/trong page; source linkage, coverage, grid positions/spans và local
spatial ordering đạt. Giữ warning aggregate `reviewed_cell_bbox_out_of_bounds` với count8,
không clamp hoặc sửa bbox. **2265 geometry conflicts** của 6 bảng unresolved vẫn giữ;
không blanket-disable geometry. Missing-grid issue occurrences có thể trùng baseline
và candidate; không dùng occurrence totals làm error rate.

**9 snapshots** (4 JSON +4 evidence inputs +M1-12 report), frozen manifest và raw
fingerprints trong RAM giữ nguyên trước/sau pilot/probes/offline resume. Không scan
dataset, API mở rộng hoặc sửa dữ liệu/ảnh/crops/credentials. Private records/predictions/
tokens locators/checkpoints chỉ tại ignored artifacts/table-reconstruction/M1-12a.

Local: **28 focused +233 related regression =261 passed** (M1-12, DU, classification/
pilot, cache/checkpoints). Ruff lint/format, planning checker và diff check đạt trước
commit. Sau regression source-rejection, focused28 được chạy lại: đạt; không lặp
233 regression không liên quan hoặc full local suite. Nhánh source rejection hạ đồng
bộ table/cells/anchors về unresolved, spans unknown, kể cả base deterministic resolved.
Pilot live tại `dbc1b0941cff2c863066eafffff6233912049017`; final code chỉ sửa trạng thái nhánh lỗi nguồn.
Đánh giá lại local cả8 persisted predictions trên final code: **8/8 DU outputs khớp,
API0**, 9 snapshots giữ nguyên (offline-revalidation.json). Không rerun live pilot/API
hoặc tests chỉ vì docs.
Implementation `c9095aab9554c24485e48d193ad2f42d294be6cf` đã push main;
[CI 40607679558](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40607679558) **success exact SHA**, mọi steps/full unit suite Python 3.11/3.12
đã xác minh qua summary, không đọc logs PASS. Checkpoint REVIEW cuối chỉ docs/planning;
SHA/CI của checkpoint này kiểm tra riêng sau push, không tự tham chiếu commit.

Limitations: chỉ same8 purposive tables, không ground truth; source run caller-bound;
text/layout mode và policy bảo thủ, Gemini coverage/merge/gap failures chưa sửa bằng
API reruns. Không provider/quota blocker; còn Tech Lead review engineering/policy.
Exact next action: Tech Lead review M1-12a; không DONE/M1-13.
