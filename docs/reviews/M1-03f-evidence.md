# M1-03f — Evidence mở rộng table crop theo approval có điều kiện

Ngày **2026-10-27**, Asia/Bangkok. Trạng thái **REVIEW**, chờ Tech Lead nghiệm thu.
Đã thực thi và đối soát thật, chỉ trên đúng 193 inventory-selected pages.
Đây là bằng chứng engineering của bbox-faithful reconstruction, không phải
đánh giá chất lượng OCR/tài chính hoặc xác nhận bảng hoàn chỉnh.

## Approval thực tế và phạm vi

Người dùng xác nhận đã xem đủ 12 review sheets và Tech Lead APPROVED có điều kiện
trong chat ngày 2026-10-27. Đã tạo local `visual-review-approval.json` từ template:
giữ nguyên plan_id, 12 recovery IDs/PNG hashes, reviewed list và thứ tự items;
gate `validate_approval` đạt trước expansion. Không sửa pending template.

Approval **chỉ áp dụng cho bbox-faithful reconstruction**: cắt nguyên bbox OCR gốc.
Không sửa bbox, thêm padding, clamp, suy diễn phần bảng ngoài bbox hoặc coi crop
là bảng hoàn chỉnh. Không mở rộng sang signature/seal/region/checkbox/red_mark
hoặc black/red/blue/ink views. Không xác nhận equivalence với original crop đã mất.

Reviewer ghi đúng vai trò Tech Lead/user từ chat; không bịa danh tính cá nhân.
Timestamp ghi lúc tiếp nhận attestation có timezone, không giả định thời điểm
xem ảnh chính xác. Approval là attribution trên trusted filesystem, không phải chữ ký số.

## Quality issues chuyển cho M1-04a

| Review sheet | Issue do Tech Lead báo | Xử lý trong M1-03f |
| --- | --- | --- |
| 02 | Bbox chưa bao trọn bảng | Giữ nguyên bbox; crop không được coi là bảng hoàn chỉnh |
| 03 | Bbox chưa bao trọn bảng | Giữ nguyên bbox; crop không được coi là bảng hoàn chỉnh |
| 08 | Bbox chưa bao trọn bảng | Giữ nguyên bbox; crop không được coi là bảng hoàn chỉnh |
| 11 | Bbox chưa bao trọn bảng | Giữ nguyên bbox; crop không được coi là bảng hoàn chỉnh |
| 12 | Bbox chưa bao trọn bảng | Giữ nguyên bbox; crop không được coi là bảng hoàn chỉnh |

Local `visual-review-quality-issues.json` ghi đúng **5**
`source_bbox_incomplete_table`, status requires_review, follow-up M1-04a;
bind từng issue với recovery ID/hash/page/element/bbox nguồn. Sheet numbers là
thứ tự một-based trong review-manifest, khớp reviewed list của template.
Không sửa sidecars, canonical IDs hoặc versioned contracts.
M1-04a vẫn TODO; đây là input bàn giao, chưa triển khai validator/sửa bbox.

Human review bao phủ 12 pilot; 187 ảnh mới chỉ có kiểm chứng engineering,
chưa được trình bày là human-approved về nội dung hoặc độ đầy đủ bảng.

## Identity và baseline

| Thuộc tính | Kết quả |
| --- | --- |
| M1-03e acceptance | `ca607debe2148ab2a52c25c78f142f181cf35674`, Tech Lead APPROVED/DONE |
| M1-03f implementation | `a91492e17a0644c8f9d7e4e655ba73dda26c79f0` |
| CI implementation | [40349513656](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40349513656), success Python 3.11/3.12 |
| Baseline publication trước continuation | `e6403a0a4601470f5f46c6d74eb3c9323e4eba62`, fetch/local/remote khớp |
| Python / Pillow local | 3.12.0 / 12.3.0, Windows |
| Recovery method/version | reconstructed_from_page_bbox / 1 |
| Original crop equivalence / Drive/run identity | unverified |

Continuation dùng coordinator/engine đã có, không đổi production code, contracts,
canonical ID payload, dependencies hoặc task cha M1-03/M1-04.

## Batch execution và kết quả thật

| Batch | PNG mới | Tổng reconstructed sau verify | Pending eligible |
| --- | ---: | ---: | ---: |
| Pilot cũ | 0 | 12 | 187 |
| 1 | 24 | 36 | 163 |
| 2 | 24 | 60 | 139 |
| 3 | 24 | 84 | 115 |
| 4 | 24 | 108 | 91 |
| 5 | 24 | 132 | 67 |
| 6 | 24 | 156 | 43 |
| 7 | 24 | 180 | 19 |
| 8 | 19 | 199 | 0 |

Tổng **187 PNG mới + 187 sidecars mới**, giữ nguyên 12 PNG/12 sidecars pilot.
Mỗi batch <=24 mới, total cap 199; **8/8 batches completed**, conflicts/failures **0/0**.
Không skip eligible candidates hoặc tạo output cho loại/field ngoài table.crop.

Batch 1 chạy production CLI execute/verify. Batches 2–8 gọi cùng coordinator
`execute_batch`, giữ frozen-plan refresh trước/sau, approval, OS lock, caps,
exclusive writes và source-integrity callback; mỗi batch có lượt engine inspection
độc lập sau ghi. Không đổi approved plan hoặc bypass failed/interrupted guards.
Receipts continuation và engine started/finished giữ đầy đủ ở artifacts local.

## Source/output integrity và final reconciliation

- Hash/size/mtime/inode của **193 OCR JSON + 193 raw images** khớp frozen plan
  trước/sau từng batch và lúc đối soát cuối; không hash/scan toàn dataset.
- Mọi output trước từng batch giữ nguyên bytes/hash/size/mtime/inode; 12 pilot
  giữ nguyên recovery IDs/PNG hashes và sidecars so với checkpoint trước approval.
- Reopen/decode, so toàn bộ pixels với source bbox, mode/dimensions/hash và sidecars
  qua engine trước khi xác nhận mỗi batch. Bbox gốc giữ nguyên cho 199 outputs.
- Chuỗi snapshots giữa 8 receipts khớp; 187 engine-created IDs riêng biệt, đúng
  candidate set trừ 12 pilot. Không orphan PNG/sidecar hoặc output ngoài approved set.
- Fresh production CLI `--verify` cuối trả **199 already_recovered**, **0 dry_run**,
  **0 new_outputs**, **0 conflicts**; không ghi thêm recovery PNG.
- Local index có **199 validated reconstructed_available**, **0 missing_unrecovered**
  trong eligible set, cùng provenance và equivalence unverified.

**Original references không thay đổi**: audit vẫn 1.557 references, existing
original 985 / missing original 572. Có 180 existing original table.crop và
199 original table.crop vẫn missing; reconstructed alternatives không biến
original missing thành existing. Ngoài scope vẫn **85 non-table crops + 288 views**.

Local `approved-expansion-final-integrity.json` lưu proof tổng kết và snapshots.
`approved-final-summary.json` là input cho exporter. Không ghi đè
`final-integrity.json` checkpoint trước approval. [Statistics sanitized](M1-03f-statistics.json)
được tạo bằng fixed allowlist `public_expansion_statistics`; new_outputs=0 trong
file này là lượt verify cuối, không phải tổng 187 PNG đã tạo qua 8 batch.

## Checks, publication và giới hạn

Full local checks chạy sau khi ghi/validate approval và trước batch đầu:
**655 passed, 14 skipped**, Ruff lint/format **79 files**, planning **75 tasks**,
pip check đạt. Skips gồm quyền symlink, case-insensitive filesystem và FIFO Windows;
native junction/process-lock tests đạt. Synthetic tests không đo chất lượng tài chính.
Không thay production code sau full checks; kiểm tra tài liệu/staging lại trước push.
Publication CI cho continuation sẽ được ghi sau khi push và xác minh exact SHA.

Không commit PNG, review sheets, approval, per-file IDs/hashes, bindings,
full manifests/index hoặc OCR text/source paths. Tất cả giữ local bị Git ignore.
Public evidence chỉ gồm số liệu tổng hợp, điều kiện phê duyệt và commit/CI metadata.

Giới hạn giữ nguyên: original preprocessing/Drive/run equivalence chưa xác minh;
trusted local filesystem, TOCTOU/hardlinks/mount/case/Unicode aliases và writers
không dùng OS lock chưa được chống đầy đủ. Encoder thay đổi có thể gây conflict;
không overwrite. Năm bbox coverage issues không được giải quyết trong task này.

## Exact next action

Tech Lead nghiệm thu M1-03f ở trạng thái REVIEW, xem sanitized evidence và local
artifacts khi cần; không coi các crop có bbox thiếu là bảng hoàn chỉnh.
Không bắt đầu M1-04a/b hoặc xử lý signature/seal/color views.
