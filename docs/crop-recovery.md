# Missing Crop Audit & Bounded Recovery — M1-03d

M1-03d đã được Tech Lead APPROVED engineering/synthetic/zero-output ngày
2026-10-26 và chuyển DONE. Các phần REVIEW/zero-output bên dưới giữ kết quả lịch
sử M1-03d. M1-03e bổ sung local verification/pilot theo scope mới được giao.

## Controlled expansion — M1-03f

M1-03e đã được Tech Lead APPROVED/DONE theo task giao 2026-10-26.
M1-03f chỉ mở rộng `table.crop`; không đổi Raw OCR/Path Mapping contracts.
Checkpoint hiện tại và số liệu thật tại [evidence M1-03f](reviews/M1-03f-evidence.md).
Human visual gate còn thiếu, chưa thực thi batch expansion.

`recover_crop()` giữ cap mặc định 12 và từ chối cap tùy ý. Coordinator nội bộ
`crop_expansion.execute_batch()` chỉ cấp permit cho full recovery IDs trong frozen
candidate plan, tổng <=199 và từng batch <=24 PNG mới. Payload tạo IDs giữ nguyên
method/version + `record.export()` như M1-03d/e. Không thêm fields expansion vào
canonical metadata hoặc sidecars cũ. Private permit là boundary nội bộ Python,
không phải cơ chế chống caller có quyền chạy code tùy ý.

Các lệnh dùng environment roots theo DataConfig (không tự đọc `.env`):

```powershell
.venv/Scripts/python scripts/expand_table_crop_recovery.py --plan
.venv/Scripts/python scripts/create_crop_review_sheet.py
.venv/Scripts/python scripts/expand_table_crop_recovery.py --dry-run
.venv/Scripts/python scripts/expand_table_crop_recovery.py --verify
```

Không có `--execute` thì không ghi recovery PNG; các lệnh vẫn có thể ghi local
manifests/index. Contact-sheet script ghi riêng ảnh review local; không sửa PNG
recovery hoặc source. Mỗi sheet có thumbnail source với bbox đỏ bên trái và crop
giữ tỷ lệ bên phải. Scaling chỉ dùng cho trình bày sheet.

Người dùng cần xem đủ 12 sheet trong `artifacts/crop-recovery/M1-03f/review/`.
Template `visual-review-approval.template.json` cố ý có `approved=false`, reviewer
và reviewed_at null. Sau khi thực sự review, người dùng tạo file local bị ignore
`visual-review-approval.json` cùng thư mục task, giữ nguyên plan_id, reviewed list
và từng recovery_id/png_sha256; ghi reviewer thật, reviewed_at ISO 8601 có timezone,
top-level approved=true/verdict=approved và verdict=approved cho cả 12 items.
Một rejection, mismatch, thiếu reviewer/time hoặc thiếu file đều chặn execution.
Approval là bản ghi người dùng trên trusted filesystem, không phải chữ ký số.

Sau approval và full checks đạt, mỗi lệnh chỉ chạy **một batch**:

```powershell
.venv/Scripts/python scripts/expand_table_crop_recovery.py --execute --batch-size 24
.venv/Scripts/python scripts/expand_table_crop_recovery.py --verify
```

Re-audit đúng 193 inventory pages, verify lại mappings/bindings/source snapshots,
mọi audit states và eligible list trước batch. `plan.json` ghi exclusive/idempotent;
source/bbox/bindings/inventory thay đổi thì dừng, không tự refresh approved plan.
Candidates dedup full recovery ID, từ chối reference trùng nhưng context khác;
thứ tự round-robin theo mã/năm ổn định. Execution plan local chia pending IDs
thành batch <=24; không bù bằng non-table hoặc views khác.

Pilot và expansion dùng chung OS lock `data/.crop-recovery.lock`: nonblocking
`msvcrt.locking` trên Windows, `fcntl.flock` trên POSIX. Giữ lock inode, không xóa
file lock; OS giải phóng lock khi process chết. Các writers ngoài workflow không
tuân thủ lock vẫn là giới hạn. Không chạy nhiều commands song song trên artifacts.

Started/finished manifests ghi exclusive, failed batch chặn các batch tiếp theo.
Sau interruption sạch, `--execute --resume` chỉ reconcile khi frozen plan/sources,
approval và mọi PNG/sidecar đều hợp lệ; checkpoint cũ ghi `interrupted_validated`
với completed/pending riêng, batch mới vẫn <=24 new PNG. Orphan PNG/sidecar, output
conflict hoặc batch failed không được tự xóa/ghi đè/retry; cần review nguyên nhân.
Chạy lại sau batch hoàn tất nhận diện already_recovered và chọn pending tiếp theo.

Mỗi batch reopen PNG, đối chiếu toàn bộ pixels/dimensions/hash/sidecar bằng engine,
kiểm tra source snapshots sau ghi và counts trước/sau. Local recovery-index.jsonl
phân biệt `reconstructed_available`/`missing_unrecovered`; existing originals giữ
trong audit với trạng thái riêng. Index gồm provenance, original reference,
element/field/bbox/page/source/output hashes/method/version và validation status;
equivalence luôn unverified. Immutable index checkpoints giữ lịch sử; projection
JSONL cập nhật bằng replace atomic. Chưa tích hợp adapter M1-04a.

Không commit sheets/PNG/index/bindings/full manifests/per-file hashes. Exporter
`scripts/export_crop_evidence.py --expansion <summary.json>` chỉ xuất fixed numeric,
boolean và enum allowlists qua `public_expansion_statistics()`, không redact bằng
string replacement. Trusted local filesystem/TOCTOU/hardlinks/mount aliases và
original preprocessing/Drive/run identity vẫn là giới hạn chưa giải quyết.

## Verified local mapping và real pilot — M1-03e

Adapter `local_crop_mapping` chỉ xét hai root markers đúng tên, trích full exact
prefix từ source thực tế, kiểm tra lexical bằng contract v1 và runtime resolver.
Marker discovery chưa đủ approval: từng suffix phải khớp context mã/năm/page
của inventory; mỗi prefix cần positive controls; collisions giữa prefixes bị
từ chối. Negative controls đổi mã/năm, giữ basename và phần suffix còn lại,
phải trả missing thay vì fallback. Không glob/search dataset hoặc basename-only.

Page binding dùng source manifest độc lập với metadata trang, exact raw suffix,
containment và dimensions đã decode khớp OCR. Đây là `verified_local_mapping` và
`verified_local_page_identity`; `original_drive_identity_verified=false`,
`run_identity=null`. Không xác minh ảnh byte-for-byte với Drive, nội dung tài
chính hoặc preprocessing gốc. `CropAuditRecord.verified_local_mapping_id` nối
audit với private bindings, không thay versioned contracts.

Hai environment keys input theo DataConfig phải được caller cấu hình. Chạy:

```powershell
.venv/Scripts/python scripts/verify_local_crop_pilot.py
.venv/Scripts/python scripts/verify_local_crop_pilot.py --execute
.venv/Scripts/python scripts/export_crop_evidence.py artifacts/crop-recovery/M1-03e/execute-summary.json
```

CLI chọn đúng inventory pages có missing warning (tối đa 193), verify lại bindings
và audit trước mọi lần execute. `--execute` chỉ chạy khi từng selected candidate
qua dry-run; luôn dùng `recover_crop`, cap 12. Rerun trong cùng run xác minh
already_recovered và giữ output snapshots. Full manifest/bindings local dưới
artifacts/crop-recovery/M1-03e/, binding ghi exclusive/idempotent; thay evidence
phải review conflict và chọn vị trí mới, không overwrite. Reproducibility cần
inventory và bản dataset local riêng; public CI chỉ dùng synthetic fixtures.

Dry-run thật không tạo recovery root; 2 mappings/193 bindings verified, audit
193 trang/1.557 references: existing 985, missing 572, unique/contextual 572/572,
unmapped/unsafe/ambiguous 0. 199 table candidates, 288 unsupported missing views,
85 non-table missing crops cần review. Pilot đã tạo 12 PNG, rerun 12 already_recovered;
pixels/dimensions/hash/provenance đạt. Nguồn 193 JSON + 193 ảnh hash/metadata không đổi.
Không có contact sheet hoặc ảnh thật trong Git. Đây là engineering verification,
không phải đánh giá chất lượng OCR/tài chính hoặc original crop equivalence.

`crop_evidence.public_statistics` chỉ cho fixed keys, strict nonnegative integers,
strict booleans và enum keys đã allowlist; không có kênh output cho paths, IDs,
per-file hashes hoặc OCR text. Unknown issue keys/giá trị string fail closed.
Full manifest không được publish trực tiếp; báo cáo chỉ lấy projection tổng hợp.

Task bổ sung độc lập sau M1-03 DONE. Audit chỉ đọc qua OCR Loader và Path
Resolver đã nghiệm thu. Không sửa Raw OCR/Path Mapping contracts, DataConfig,
JSON nguồn hoặc downstream crop references. Không gọi API/OCR/model.

## Original và reconstructed crop

Original crop là artifact OCR nguồn, có thể đã padding/resize/preprocess chưa
biết. Missing crop reference là một lượt khai báo field, không nhất thiết một
file duy nhất. Reconstructed crop là PNG cắt nguyên bbox từ ảnh trang, mang
method `reconstructed_from_page_bbox`, version `1`, equivalence `unverified`.
Không tuyên bố byte/pixel tương đương original đã mất hoặc OCR chính xác.

Chỉ `table.crop` có thể eligible. Seal/signature/region/checkbox/red_mark crop
cần review; black/red/blue/ink views là `unsupported_view`, không tạo heuristic
color transforms. Chỉ audit fields thực sự có trong source JSON.

## API và inputs được phê duyệt

Modules `document_processing.crop_audit` và `crop_recovery` là công cụ nội bộ,
không phải versioned public serialized contracts. `audit_page` nhận:

- Request OCR JSON cho `load_ocr_page`, DataConfig và approved PathRootMapping list.
- `expected_identity=(symbol, year, page)` từ manifest độc lập.
- `image_bindings={original_image_reference: (symbol, year, page)}` do caller
  phê duyệt từ bằng chứng nguồn độc lập; không suy ra filename/basename.
- `run_identity` nếu biết; thiếu thì ghi issue, giữ artifact/page context trong key.

Không có mapping được duyệt thì kết quả `unmapped`, không tự đoán Colab root từ
marker M1-01. Không có image binding thì `source_identity_unverified`, không auto
recovery. Caller declarations không phải bằng chứng xác thực nội dung ảnh/run.
Mọi source paths thật và mappings chỉ lưu artifacts local bị ignore.

`CropAuditRecord` giữ page/source/run, element index/ID/type/field, original path,
source image, bbox/dimensions, mapping status, eligibility, issues, dedup key,
path key và source image hash khi đã đọc. Mapping status và eligibility độc lập.
Hash canonical context dùng artifact + run + page + original path + element/
field/index, không gộp basename. Unique raw paths và contextual paths đếm riêng;
chưa biết run thì không khẳng định hai references là cùng original artifact.

`recover_crop(record, page_request, config, mappings, *, image_bindings,
output_root=None, dry_run=True, cap=12)` trả runtime manifest dict. Re-audit
nguồn, so record/hash trước crop; không dùng eligibility cũ như quyền ghi.
`select_pilot` dedup context, ưu tiên representative/pilot pages, round-robin
symbol theo thứ tự lexical deterministic; tối đa 12, không bù bằng loại crop khác.

## Validation và filesystem

Chỉ source ảnh PNG resolved qua approved roots; bytes tối đa 64 MiB và 40 triệu
pixels trước decode. Reuse bounded read policy nội bộ loader (revalidation,
lstat/fstat, O_RDONLY/O_NOFOLLOW khi có). Decode bằng Pillow, bomb warnings thành
errors; không thay giới hạn global. RGB/RGBA/L/LA/1/P giữ mode và pixels. Source
dimensions phải khớp OCR width/height. Bbox đúng bốn strict integers, không bool,
geometry dương, hoàn toàn trong ảnh; không round/scale/clip/detection_view transform.
Đọc/giải mã ảnh và `crop`/PNG theo [Pillow Image API](https://pillow.readthedocs.io/en/stable/reference/Image.html).
Pillow `>=11,<13` là dependency nhỏ; local kiểm tra 12.3.0, CI Python 3.11/3.12
cài từ package metadata, không thêm AI framework.

Chỉ root `project_root/data/recovered_crops/` đã được task duyệt. Root khác bị
từ chối; không thêm whitelist vào core. Kiểm tra absolute/no traversal, mọi
ancestor không symlink/reparse/junction, disjoint hai chiều với configured inputs,
data/raw, data/processed và hai vị trí dataset cũ. Không mkdir trong audit/dry-run.
`.gitignore` hiện có `/data/*` và `artifacts/` bảo vệ outputs/manifests.

Tên PNG SHA-256 đầy đủ từ method/version và canonical audit metadata, không đưa
element ID/path vào filename. `xb` exclusive creation, không overwrite hoặc xóa.
Sidecar JSON giữ recovery ID, source/output hash và method/version. Output đã có
chỉ `already_recovered` khi bytes/hash + sidecar khớp, nếu không `output_conflict`.
Reopen PNG, đối chiếu mode/pixels/dimensions/hash trước khi báo recovered; đọc lại
source hash sau write. PNG/sidecar lỗi hoặc thiếu giữ lại để review, retry báo
conflict thay vì xóa/sửa. Cap đếm PNG trong recovery root riêng (không scan dataset)
để invocation sau không vượt 12, kể cả outputs lỗi chiếm slot.

Policy là trusted local filesystem với **một writer**. Checks/open không atomic;
TOCTOU qua parent/root còn tồn tại, Windows không có O_NOFOLLOW. Hardlinks,
mount aliases, hostile metadata restoration và concurrent writers chưa được
chống đầy đủ. Không trình bày cap/checks như transaction hoặc sandbox bảo mật.
Pillow encode có thể thay đổi bytes giữa versions: rerun lúc đó báo conflict,
không ghi đè. Hash là hash file PNG, không phải chứng minh đúng tài chính.

## CLI và coverage thực tế

Sau khi cung cấp hai environment keys theo [DataConfig](dataset.md):

```powershell
.venv/Scripts/python scripts/audit_missing_crops.py
```

Mặc định không supplied bindings, không đoán source roots. `--bindings` nhận
JSON local với `mappings` (PathRootMapping list), `image_bindings` (JSON arrays
ba phần tử), `run_identity` optional. Phải được caller phê duyệt trước dùng.
`--execute` mới cho ghi PNG, tối đa 12 eligible table crops. Không dùng để tự mở
rộng pilot; chỉ thực thi phạm vi mẫu đã được duyệt. CLI ghi manifests vào
artifacts/crop-recovery; audit JSONL chứa paths thật không được commit.

M1-01 page_manifest/inventory_warnings khớp danh sách **193** trang, tổng **572**
lượt từng thiếu. Không chạy full inventory, không đọc JSONL/log thành OCR pages,
không quét 8.063 crops. Audit qua loader đủ 193/193 JSON, không structural failures;
hash SHA-256, size/mtime/inode trước/sau khớp trên đúng 193 JSON. Không đọc ảnh
trang/crop vì chưa có approved mapping. Kết quả ngày 2026-10-26:

| Chỉ số | Kết quả |
| --- | ---: |
| Crop reference occurrences audited | 1.557 |
| Unique source path strings | 1.553 |
| Unmapped | 1.557 |
| Existing/missing/unsafe/ambiguous đã xác nhận qua resolver | 0 mỗi loại |
| Requires review | 773 |
| Unsupported processed/color views | 784 |
| Eligible candidates sau dedup | 0 |
| Pilot selected/recovered/conflicts | 0/0/0 |

Missing references/unique missing paths **chưa xác định** do mappings chưa có;
summary machine-readable đếm 0 *confirmed missing*, không phải kết luận dataset
không thiếu crop. Không ép tổng audit bằng baseline 572: audit lấy mọi reference
trên tập 193 trang, gồm cả references trước đây đã có file. Baseline giữ nguyên.

| Type | crop | black | red | blue | ink |
| --- | ---: | ---: | ---: | ---: | ---: |
| table | 379 | 0 | 0 | 0 | 0 |
| signature | 94 | 94 | 94 | 94 | 94 |
| seal | 86 | 86 | 86 | 86 | 0 |
| seal_signature_region | 50 | 50 | 50 | 50 | 0 |
| red_mark | 164 | 0 | 0 | 0 | 0 |
| checkbox | 0 | 0 | 0 | 0 | 0 |

Checkpoint C là **zero-output pilot**: không eligible vì chưa có approved source
root/image identity bindings, không tạo recovery root. Selection rerun trên
manifest đảo thứ tự vẫn zero, audit hash giữ nguyên. Real output hashes/dimensions,
real image rerun và contact sheet: N/A vì không sinh ảnh. Không gọi synthetic
recovery là pilot dữ liệu thật hoặc bằng chứng OCR accuracy.

Artifacts local: `audit.jsonl`, `audit-summary.json`, `recovery.jsonl` (rỗng),
`page-failures.jsonl` (rỗng), `source-verification.json`, `pilot-summary.json`
trong `artifacts/crop-recovery/`. Không chép paths hoặc nội dung OCR vào docs.

## Kiểm thử và phần còn lại

Synthetic tests kiểm tra statuses, duplicates/runs/same basename, strict bbox,
source missing/identity/dimensions/decode/size/change, RGB/grayscale/Unicode,
expected pixels/hash, source integrity, traversal/root overlap, link/reparse/
native junction, exclusive race/conflict, output validation failure, rerun và
12-file cap thực sự. Windows symlink thiếu privilege skip rõ ràng; native junction
đã chạy local, CI Linux chạy symlink và skip native junction theo platform.

Missing mapping là giới hạn dữ liệu thực tế, không được tự phê duyệt trong task.
M1-03d dừng REVIEW; Tech Lead review implementation/coverage và quyết định có
duyệt source bindings, cho phép pilot có ảnh hoặc mở rộng recovery hay không.
Không bắt đầu M1-04a/b, không tự recovery 572 lượt.

Implementation `6e30ba67fa6b3cf7dd8f6e74021c0dbbad9343a6` đã push và remote khớp.
[CI 40315855062](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40315855062)
success đúng SHA/mọi step Python 3.11/3.12, mỗi job 578 passed/10 skipped.
Local Windows Python 3.12: full 575 passed/13 skipped, crop 57 passed/1 skipped;
Ruff lint/format 64 files, planning 73 tasks và pip check đạt. Không có datasets/
secrets trong staged/index; raw/processed không đổi. Dừng REVIEW.
