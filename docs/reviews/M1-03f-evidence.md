# M1-03f — Evidence checkpoint trước human visual approval

Ngày **2026-10-26**, Asia/Bangkok. Đây là checkpoint A/B/C của task
Controlled Table Crop Recovery Expansion, trạng thái **BLOCKED**. **Chưa thực thi expansion**;
human approval còn thiếu. Không phải báo cáo chất lượng OCR/tài chính.
Không publish ảnh, OCR text, source paths/bindings hoặc per-file hashes.

## A. Execution identity

| Thuộc tính | Kết quả |
| --- | --- |
| Task | M1-03f — Controlled Table Crop Recovery Expansion |
| Scope | Đúng 193 inventory-selected pages M1-01; riêng table.crop |
| M1-03e | Tech Lead APPROVED/DONE theo task giao |
| Acceptance SHA M1-03e | `ca607debe2148ab2a52c25c78f142f181cf35674` |
| CI acceptance | [40345846471](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40345846471), success mọi steps Python 3.11/3.12 đúng SHA |
| Implementation SHA M1-03f | `a91492e17a0644c8f9d7e4e655ba73dda26c79f0`, push/remote khớp |
| CI implementation | [40349513656](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40349513656), success mọi steps Python 3.11/3.12 đúng SHA |
| Python/Pillow local | 3.12.0 / 12.3.0, Windows |
| Recovery method/version | reconstructed_from_page_bbox / 1 |
| Equivalence to original | unverified |

M1-03 giữ DONE; không đổi dependencies M1-03/M1-04 và chưa bắt đầu M1-04a/b.

## B. Baseline và re-audit

| Metric | Baseline M1-03e | Local M1-03f |
| --- | ---: | ---: |
| Audit pages | 193 | 193 |
| Crop references audited | 1.557 | 1.557 |
| Existing original references | 985 | 985 |
| Original missing references | 572 | 572 |
| Eligible unique table.crop | 199 | 199 |
| Prior reconstructed PNG | 12 | 12 |
| Missing processed/color views | 288 | 288 |
| Missing non-table original crops | 85 | 85 |

Hai exact local mappings và 193 page bindings tái kiểm chứng, khớp private
M1-03e bindings. Mapping rejected/ambiguous/discovery failures 0; invalid bbox,
missing source image, dimension mismatch và unmapped/unsafe 0 trong eligible set.
Không scan 500 pages hoặc 8.063 crop PNG. Không gọi Drive/API/OCR/LLM.

## C. Existing pilot verification và human gate

12 PNG + 12 sidecars thực sự tồn tại. Full recovery IDs giữ nguyên canonical
metadata; method/version khớp. Reopen/decode, pixels với source bbox, dimensions,
source/output SHA-256 và sidecars: **12/12 đạt**. Rerun dry verification trả
**12 already_recovered**. Output bytes/size/mtime/inode trước/sau giữ nguyên.
Không reset hoặc viết lại PNG/sidecars cũ, original OCR references giữ nguyên.

Đã tạo **12** local source/bbox–crop sheets và review manifest trong
`artifacts/crop-recovery/M1-03f/review/`. Bbox được vẽ trên bản trình bày nguồn;
crop giữ tỷ lệ. Không publish sheets/financial images.

Human review: **approved 0, rejected 0, pending 12**. Chỉ có pending template
`visual-review-approval.template.json`, approved=false/reviewer=null/time=null.
Chưa có `visual-review-approval.json`. Template bind đúng 12 IDs/PNG hashes và
frozen plan_id. Pixel tests không được coi là human approval.

## D. Expansion planning và execution results

| Metric | Actual |
| --- | ---: |
| Existing original table.crop | 180 |
| Original table.crop vẫn missing | 199 |
| Eligible unique recovery IDs | 199 |
| Prior reconstructed_available | 12 |
| Missing_unrecovered eligible tables | 187 |
| New reconstructed PNG | 0 |
| Total reconstructed PNG | 12 |
| Expansion batches executed | 0 |
| Execution failures/conflicts | 0 / 0 |
| Skipped eligible candidates trong execution | N/A — chưa execute |
| Non-table/views giữ ngoài scope | 85 / 288 |

Dry-run toàn bộ eligible set: **12 already_recovered + 187 dry_run**. Local
execution plan có **8** batch dự kiến: 7 × 24 + 19 pending IDs. Không có lệnh
execute expansion nào được chạy trên dataset thật.

Default engine cap 12 giữ nguyên. Expansion coordinator chỉ dùng permit nội bộ
cho approved candidate IDs, total <=199 và independent batch cap <=24. Selection
round-robin theo mã/năm, deterministic, dedup ID/reference, không random hoặc bù
non-table/views. Frozen plan gồm inventory, bindings, all audit states và source
snapshots; discrepancy/change dừng thay vì tăng cap hoặc tự refresh approval.

Shared OS single-writer lock, exclusive PNG/sidecar writes và started/finished
checkpoints. Rerun sau batch hoàn tất chọn pending; clean interruption cần
`--resume` và revalidation, orphan/conflict/failed batch dừng để review.
Chức năng batch/resume được kiểm thử synthetic; chưa có real batch results.

## E. Integrity và downstream index

Hash/size/mtime/inode của **193 OCR JSON và 193 raw images** trước/sau khớp;
12 prior PNG/sidecar outputs cũng bất biến. Không ghi raw/processed, không đổi
original crop path hoặc OCR schema. Reconstructed alternative được ghi riêng,
không đổi missing original thành existing original.

Local recovery-index.jsonl hiện có 199 candidate records: 12 validated
reconstructed_available và 187 pending missing_unrecovered. Records có original
reference, page/element/field/bbox, source/output hashes, method/version,
validation/recovery status, relative output path và equivalence unverified.
Immutable index checkpoints và atomic JSONL projection; chưa tích hợp M1-04a.

Exporter mở rộng fixed aggregate allowlists của crop_evidence.py; chỉ strict
integers, booleans và known enum counts. Injection/private-field tests fail
closed hoặc loại bỏ fields không có kênh xuất. Không dùng string replacement
làm cơ chế sanitize. Dataset/PNG/private manifests vẫn bị Git ignore.

## F. Tests và remaining limitations

Full local Windows Python 3.12: **655 passed, 14 skipped**. Ruff lint và format
check đạt (**79 files**); planning validator **75 tasks** đạt; pip check không có
broken requirements. Expansion module: **35 passed, 1 skipped**; publication
module: **19 passed**. Implementation CI Python 3.11 và 3.12: mỗi job
**658 passed, 11 skipped**, Ruff/planning và mọi steps success; đã đọc job logs.
Linux chạy symlink tests, skip các native Windows syntax/junction tests. CI không
có pip check riêng; pip check ở đây là local. Publication tài liệu đi sau stable
implementation; CI của publication HEAD được kiểm tra riêng, không suy từ CI code.
Tests dùng synthetic PNG/tmp_path, không có real dataset trong CI và không phải
bằng chứng chất lượng tài chính. Native Windows junction và process-lock tests
đạt; skips gồm 12 symlink privilege, case-insensitive filesystem và FIFO Windows.

Coverage: default pilot cap/IDs, cap 199/batch 24, deterministic/dedup, approved
hashes/IDs/plan và rejected/missing approval, changed source/bbox/bindings,
no-overwrite/already-recovered, traversal/root overlap/symlink/native junction,
OS process lock/interruption, clean partial resume/incomplete sidecar,
failed batch stops next batch, contact sheets/source integrity, index provenance
và allowlisted publication. Real integration chỉ re-audit/verify/sheets/dry-run.

Giới hạn: unknown original preprocessing, unsupported color views, 85 non-table
crops chưa xử lý, original Drive/run byte identity chưa xác minh. Trusted local
filesystem; TOCTOU qua parents, hardlinks/mount/case/Unicode aliases và writers
không tuân thủ lock còn rủi ro. Lock không phải transaction/sandbox. Approval file
là attribution của người dùng, không phải chữ ký số. Artifact commands cần chạy
tuần tự. Encoder/Pillow version thay đổi có thể gây conflict, không được overwrite.

## G. Tech Lead decision và exact next action

**Chưa sẵn sàng final REVIEW**, chưa hoàn tất expansion hoặc final reconciliation.
M1-03f dừng checkpoint chờ human approval; M1-04a/b chưa được bắt đầu.
Sau gate, tiếp tục cùng task theo handoff, thực thi từng batch <=24, validate và
cập nhật kết quả thật rồi chuyển REVIEW cho Tech Lead.

**Exact next action: Người dùng xem đủ 12 local review sheets và ghi approval thật
khớp template trong visual-review-approval.json trước khi tạo thêm recovery PNG.**
