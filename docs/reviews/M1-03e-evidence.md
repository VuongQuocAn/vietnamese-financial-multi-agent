# M1-03e — Evidence nghiệm thu local mapping và real crop pilot

Ngày **2026-10-26**, Asia/Bangkok. Báo cáo gốc ở mốc REVIEW; Tech Lead đã
**APPROVED**, M1-03e **DONE** theo task M1-03f. Acceptance checkpoint
`ca607debe2148ab2a52c25c78f142f181cf35674`,
[CI 40345846471](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40345846471)
success đúng SHA/mọi steps Python 3.11/3.12. Các số liệu/lựa chọn review phía dưới
giữ kết quả lịch sử của pilot; mở rộng thuộc scope độc lập M1-03f và cần human gate.
Đây là báo cáo engineering trên dữ liệu local thật; không phải đánh giá độ chính
xác OCR hoặc tài chính. Không có ảnh, OCR text, paths nguồn hay per-file hashes
trong báo cáo này.

## A. Execution identity

| Thuộc tính | Giá trị đã kiểm tra |
| --- | --- |
| Task | M1-03e — Verified Local Mapping & Real Crop Recovery Pilot |
| Implementation SHA | `6c2b8c7738631b578c97b9b0d930b51ff69c6162` |
| CI implementation | [40342491992](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40342491992), success đúng SHA, mọi steps Python 3.11/3.12 |
| Python local | 3.12.0 |
| Platform local | Windows |
| Pillow local | 12.3.0 |
| Dataset scope | Đúng 193 trang có missing-crop warning trong inventory M1-01; BBS/BCC/BED |
| Method/version | `reconstructed_from_page_bbox` / `1`, engine `recover_crop()` M1-03d |
| Equivalence | `equivalent_to_original_crop = unverified` |

M1-03d đã DONE theo Tech Lead APPROVED tooling, safe bounded engine,
synthetic/security tests và zero-output pilot. Acceptance checkpoint
`1e7fe344c4991b99127448a5180bdcb4470c9a60`,
[CI 40340730395](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40340730395)
success đúng SHA. Approval đó không có nghĩa 572 lượt thiếu đã được phục hồi.
M1-03 giữ DONE; không thêm recovery tasks vào dependencies của task cha.

## B. Mapping verification

| Chỉ số | Kết quả |
| --- | ---: |
| Source-root candidates | 2 |
| Verified local mappings | 2 |
| Rejected mappings | 0 |
| Ambiguous/conflicting prefixes | 0 |
| Positive controls, reference checks | 1.178 |
| Positive controls, distinct exact targets | 1.174 |
| Nhóm mã/năm có positive controls, mỗi prefix | 14 |
| Negative controls | 4 |
| Verified local page image bindings | 193 |
| Discovery/image verification failures | 0 |

Hai nhóm ứng với markers `Financial_Report` và `Financial_Report_OCR`. Adapter
trích **full exact prefix** từ original paths, kiểm tra bằng Path Mapping v1 và
resolver hiện có. Không sử dụng substring rule, basename lookup, glob hoặc tìm
file gần giống. Không truy cập Google Drive.

Mỗi observed suffix phải giữ đúng mã/năm/page và cấu trúc con từ inventory.
Source OCR manifest context được đối chiếu độc lập với metadata trong page JSON;
raw target phải đúng full relative page suffix. File nằm trong configured root,
regular file, không traversal/drive/UNC injection hoặc symlink/reparse point;
actual decoded dimensions phải khớp OCR width/height. Các trường hợp không đủ
bằng chứng giữ unmapped/requires_review; không tự tạo run identity.

Positive controls gồm 193 raw page references và 985 existing crop references
(981 distinct crop targets); các reference lặp được ghi rõ bằng hai cách đếm.
Negative controls đổi mã hoặc năm, giữ basename và phần suffix còn lại: cả bốn
đều missing tại exact target, không fallback về file đã có ở nhóm gốc. Synthetic
tests còn kiểm tra trường hợp target cùng basename có thật ở mã/năm/page sai,
prefix collision, unknown root và root marker lồng nhau.

Bindings có mức `verified_local_page_identity`; mapping evidence có
`verified_local_mapping=true`. **`original_drive_identity_verified=false`** và
`run_identity=null`. Đây là xác minh vị trí/context/dimensions local; chưa chứng
minh byte identity với ảnh Drive ban đầu, OCR run identity tuyệt đối hoặc nội
dung trang đúng ngữ nghĩa tài chính. Private bindings tái lập giống hệt giữa
dry-run và execute, ghi exclusive/idempotent trong artifacts bị Git ignore.

## C. Re-audit missing crops

| Metric | Value |
| --- | ---: |
| Target pages | 193 |
| Pages audited | 193 |
| Page load failures | 0 |
| References audited | 1.557 |
| Existing | 985 |
| Missing | 572 |
| Unique missing source path strings | 572 |
| Contextual unique missing paths | 572 |
| Unmapped | 0 |
| Ambiguous | 0 |
| Unsafe | 0 |
| Eligible table crops | 199 |
| Unsupported missing processed/color views | 288 |
| Missing non-table original crops cần review | 85 |
| Invalid bbox trong missing table candidates | 0 |
| Missing source page images | 0 |
| Image dimension mismatch | 0 |
| Local page identity uncertainty | 0 |
| References với original OCR run identity chưa xác minh | 1.557 |

Baseline M1-01 **572 missing occurrences trên 193 trang** khớp re-audit; delta 0.
Số 1.557 là mọi crop references trên tập trang mục tiêu, gồm cả existing.
Trong lần chạy này, 572 occurrences cũng có 572 unique original path strings và
572 contextual keys; đây là kết quả đếm thực tế, không phải giả định về baseline
hoặc chứng minh original run identity. Tổng source strings của audit là 1.553.

| Crop field | References audited | Missing |
| --- | ---: | ---: |
| table.crop | 379 | 199 |
| signature.crop | 94 | 33 |
| signature.ink_view_crop | 94 | 33 |
| signature.black_view_crop | 94 | 33 |
| signature.red_view_crop | 94 | 33 |
| signature.blue_view_crop | 94 | 33 |
| seal.crop | 86 | 52 |
| seal.black_view_crop | 86 | 52 |
| seal.red_view_crop | 86 | 52 |
| seal.blue_view_crop | 86 | 52 |
| seal_signature_region.crop | 50 | 0 |
| seal_signature_region.black_view_crop | 50 | 0 |
| seal_signature_region.red_view_crop | 50 | 0 |
| seal_signature_region.blue_view_crop | 50 | 0 |
| red_mark.crop | 164 | 0 |

Issue counts: `missing_target` 572; `run_identity_unverified` 1.557;
`unverified_color_transformation` 288; `unverified_crop_region` 85.
Eligibility: not_needed 985, eligible_candidate 199, requires_review 85,
unsupported_view 288. Các existing processed views không cần recovery và được
đếm not_needed; không có tuyên bố đã tái tạo preprocessing của chúng.

## D. Real recovery pilot

| Chỉ số | Kết quả |
| --- | ---: |
| Candidates selected | 12 |
| Successful dry-run | 12 |
| Files recovered trong initial execute | 12 |
| Files already recovered trong initial execute | 0 |
| Conflicts | 0 |
| Failures | 0 |
| Reopened PNG/pixel/dimension/hash/provenance validations đạt | 12 |
| Rerun already_recovered | 12 |
| PNG files sau rerun | 12 |
| Source JSON files hash/metadata unchanged | 193/193 |
| Source raw images hash/metadata unchanged | 193/193 |

Pilot có BBS/BCC/BED mỗi mã 4 files, các năm 2021/2023/2025, từ 9 source pages,
ưu tiên representative/pilot manifests. Có 12 cặp output dimensions khác nhau;
width 1.380–1.980 pixels, height 98–1.252 pixels. Không bù số lượng bằng crop
signature/seal/color view. Không chạy full recovery.

Dry-run đã kiểm tra riêng trước execute và không tạo recovery root. Execute gọi
engine M1-03d, re-audit và kiểm tra source/bbox/dimensions lại; PNG được ghi
exclusive trong `data/recovered_crops/`, không overwrite. Mỗi local result có
original crop/page references, source context, bbox, source/output hashes,
output dimensions, method/version, status recovered và equivalence unverified;
audit nối mapping ID với private verification evidence. Sidecars giữ hashes và
method/version. Original OCR references giữ nguyên.

Mỗi PNG được mở lại, decode, so kích thước/mode và toàn bộ pixels với source
bbox, kiểm tra SHA-256 và sidecar/provenance. Rerun trả already_recovered cho cả
12, hash/size/mtime/inode của toàn bộ outputs giữ nguyên. Cap thực tế 12 files;
synthetic tests còn thử file thứ 13 và rerun sau khi đầy cap.

Source JSON và raw image bytes/hash/size/mtime/inode được đối chiếu trước/sau;
đều khớp trên đúng tập 193 + 193 files đã sử dụng. Không hash toàn dataset,
không scan 8.063 crop PNG, không sửa raw/processed. Không tạo contact sheet;
không publish ảnh tài chính hoặc per-file identifiers/hashes.

## E. Security, tests và giới hạn

| Kiểm tra | Kết quả thực tế |
| --- | --- |
| Local `.venv`, Windows Python 3.12 | 614 passed, 13 skipped |
| New local mapping tests | 26 passed |
| New publication/sanitization tests | 13 passed |
| Ruff check | Passed |
| Ruff format --check | 71 files formatted, passed |
| Planning validator | 74 tasks, passed |
| pip check local | No broken requirements found |
| CI Linux Python 3.11 | 617 passed, 10 skipped; mọi steps success |
| CI Linux Python 3.12 | 617 passed, 10 skipped; mọi steps success |

CI run ở A được tra theo exact implementation SHA; từng job/step và log test đã
kiểm tra. CI dùng synthetic fixtures, không có dataset hoặc real integration.
Pip check là local; workflow hiện tại không có step pip check riêng.

Windows skips gồm 11 symlink tests do thiếu privilege, case-insensitive filesystem
và FIFO unsupported. Native Windows junction test đạt. Linux thực thi các symlink
tests có hỗ trợ; native junction skip theo platform. Không diễn giải platform
skips như bằng chứng các tính năng chưa chạy đã đạt.

Tests kiểm tra extraction exact roots, hai marker riêng, positive/negative
controls, same basename sai context, unknown/ambiguous/colliding roots,
traversal/injection, wrong identity/dimensions/missing images, existing/missing
và unique counts, idempotent/conflicting bindings. Tests engine M1-03d tiếp tục
kiểm tra pixels/hash, invalid bbox, no raw/processed writes, links/junctions,
exclusive writes/no-overwrite, conflicts, source changes, rerun và cap 12.

Exporter `public_statistics` chỉ xuất fixed aggregate fields, strict integers,
booleans và enum keys; không serialize private paths/bindings/text/hashes.
Tests chèn paths/secrets vào private fields và giá trị/keys thống kê để xác minh
loại bỏ hoặc fail closed. Trước commit đã đối chiếu staged content với actual
private source prefixes, local absolute path và per-file identifiers/hashes;
không có leakage. Tracked data chỉ `data/samples/.gitkeep`; artifacts/recovered
files bị ignore.

Giới hạn còn lại: trusted local filesystem, một writer; TOCTOU giữa parent/root
checks và open, Windows thiếu O_NOFOLLOW, hardlinks/mount/case/Unicode aliases
và concurrent writers chưa được chống đầy đủ. Không đảm bảo transaction hoặc
sandbox đối kháng. Original preprocessing/padding/resize/color views chưa biết;
không scale/clip bbox hoặc khẳng định reconstructed crops tương đương original.

## F. Reproducibility và Tech Lead review

Inputs riêng cần có: configured roots `FINANCIAL_REPORT_DIR` và
`FINANCIAL_OCR_DIR`, bản dataset local, manifests M1-01 trong
`artifacts/dataset-inventory/` gồm page_manifest, inventory_warnings,
representative_pages và pilot_candidates. Không clone được private dataset từ Git.
Private paths/bindings không được chép vào public configuration.

```powershell
.venv/Scripts/python scripts/verify_local_crop_pilot.py
.venv/Scripts/python scripts/verify_local_crop_pilot.py --execute
.venv/Scripts/python scripts/export_crop_evidence.py artifacts/crop-recovery/M1-03e/execute-summary.json
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m pytest tests/unit
.venv/Scripts/python scripts/check_planning.py
.venv/Scripts/python -m pip check
```

Expected scope tối đa 193 inventory-selected pages và 12 eligible table outputs.
CLI tái kiểm chứng mapping/bindings/audit và dry-run trước ghi; private bindings
thay đổi sẽ conflict, không tự overwrite. Initial execute cho recovered 12;
execute lại cùng inputs/encoder cho already_recovered 12, không tạo thêm file.
Encoder/version hoặc evidence thay đổi có thể conflict, cần review; không xóa
hoặc rewrite existing outputs để né conflict. Summary ghi trạng thái invocation
hiện tại; số initial execute và rerun trong báo cáo này lấy từ lần chạy đã ghi nhận.

Full local artifacts tại `artifacts/crop-recovery/M1-03e/`: local-bindings,
audit, dry-run/execute summaries và manifests, source verification, rerun manifest.
Outputs riêng tại `data/recovered_crops/`. Chỉ aggregate projection được dùng
cho báo cáo, không công bố full audit hoặc source fingerprints.

- Đã xác minh: exact local mapping/context/dimensions, actual missing breakdown,
  bounded bbox recovery/pixels/hash/provenance/rerun và source integrity.
- Chưa xác minh: original Drive/run identity, original preprocessing equivalence,
  OCR text/financial correctness hoặc semantic page alignment độc lập bằng người.
- Có nên mở rộng recovery? Cần quyết định riêng của Tech Lead và scope mới;
  không suy quyền full recovery từ pilot 12 ảnh này.
- Manual review thêm: kiểm tra trực quan local source–bbox alignment của pilot,
  85 missing non-table crops và policy cho 288 processed/color views; không tự
  phục hồi các views hoặc non-table regions.
- Có thể bắt đầu M1-04a chưa? Các inputs engineering đã có để Tech Lead cân nhắc;
  M1-04a/b vẫn TODO, chưa được bắt đầu và cần chỉ thị riêng.

**Exact next action: Chờ Tech Lead review M1-03e qua GitHub.**
