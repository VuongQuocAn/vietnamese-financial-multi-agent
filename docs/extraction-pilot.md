# Bounded Extraction Pilot — M1-04b

Runner nội bộ thuộc document_processing, không phải evaluation framework hoặc
versioned contract. Dùng nguyên validate_extraction và trust boundaries của
[M1-04a](extraction-validation.md); không OCR/LLM/API/Drive hoặc recovery.
[Spec](../planning/tasks/M1/M1-04b.md) chốt protocol trước đọc thêm dữ liệu thật.

## Lệnh và đầu vào

Cung cấp FINANCIAL_REPORT_DIR/FINANCIAL_OCR_DIR qua environment theo
[data config](dataset.md), cài package với .[dev]. Không tự đọc .env.

```powershell
python scripts/run_extraction_pilot.py
python scripts/run_extraction_pilot.py --freeze
python scripts/run_extraction_pilot.py --execute --run first
python scripts/run_extraction_pilot.py --execute --run second
```

Mặc định chỉ preflight, không ghi: dùng existing page_manifest M1-01 và
M1-03f plan/index/ledger tại artifact paths mặc định. Các flags --plan,
--inventory, --index, --ledger chỉ định evidence local cụ thể, không discovery.
Chỉ mode preflight/freeze dùng flags này; --execute luôn đọc frozen manifest.
Không recursive scan hoặc gọi lại full audit/verify expansion.

Frozen manifest/private results ở artifacts/extraction-validation/M1-04b bị ignore.
Không overwrite: canonical content bằng nhau thì idempotent, khác thì conflict.
Run label chỉ chữ thường/số/underscore/hyphen, tối đa 32 ký tự. Một writer trên
trusted filesystem; external concurrent writes/TOCTOU/hardlinks/aliases vẫn là
giới hạn hiện hữu, không coi runner là security sandbox.

## Sampling và provenance

Protocol bounded_extraction_pilot_v1 chọn trong giao inventory và approved plan.
Reserve các human ledger pages vào risk; chọn coverage mỗi stratum từ phần còn
lại theo diversity element types, cells rồi exact source reference. Bổ sung tối
đa một page chưa chọn/signal theo thứ tự spec. Không suy nhãn báo cáo từ tên file,
không coi symbol/year/page là global run ID. Duplicate source giống nhau dedup;
xung đột reject. Cùng page/binding không xuất hiện trong hai nhóm.

Trần 30 pages/500 crop-reference occurrences. Không thay trang lỗi hoặc candidate
vượt budget bằng trang thuận lợi hơn; omissions/missing strata lưu trong manifest.
Không có signal trong approved pool thì not_observed_in_candidate_metadata,
khác với chứng minh corpus không có signal đó. Pool M1-03f được chọn vì có crop
thiếu, do đó cả coverage cũng không phải mẫu ngẫu nhiên đại diện corpus.

Manifest giữ exact requests, approved mappings/image bindings, expected identities,
group/reasons, evidence inputs và selected snapshots. Fingerprints gồm SHA-256,
size/mtime/device/inode và cả file absence. So selected JSON/ảnh với snapshots đã
duyệt; không hash toàn 199 recovered outputs. Recovery entries được đối chiếu nhưng
chỉ selected PNG/sidecars được đọc/hash. Manifest digest không chứa chính nó.

## Execution và failure policy

Freeze xác minh cấu trúc/digest/config roots/approved bindings/snapshots trước ghi.
Execute đọc manifest frozen, không sampling lại. Kiểm tra input fingerprints trước
và sau, dùng validate_extraction từng page, giữ runtime reports đầy đủ: issues,
tokens, paths, source/ledger/image/crop statuses. Không fake UnderstandingResult.

Structural/input failures giữ record và expected-reference denominator; không
coi zero observed crops là zero expected refs. OSError từng page thành record
not_verified và vẫn chuyển human ledger labels đã bind; không in lỗi chứa path.
Quality/artifact issues thường không dừng pilot hoặc đóng human issues.
Unsafe references do resolver từ chối thành issue, không đọc target unsafe.

Manifest/source/evidence/binding mismatch, unsafe input snapshot, budget violation,
source_changed hoặc output conflict dừng toàn invocation. Unexpected runtime errors
dừng, không giả lập kết quả đạt. Không source write trong runner. Không tự sửa
ledger/index/bbox/mappings. Chỉ output root cố định được ghi; traversal và
symlink/junction bị từ chối. No-overwrite không thay thế việc quản lý một writer.

## Đơn vị thống kê và repeatability

Hai nhóm thống kê riêng. Selected/processed/failed và status counts dùng page;
availability/mapping dùng reference occurrence; issue_codes dùng issue occurrence;
pages_with_issue_code đếm mỗi code tối đa một lần/page. Mục other page-level là
hợp các pages có code ngoài allowlist, không cộng các page counts bị chồng lấp.
Không cộng pages/elements/references/issues thành chung một tỷ lệ hoặc quality score.

Expected references lấy inventory đã duyệt; observed từ validator; unverified là
phần chưa có runtime crop records vì page failure. not_verified giữ nguyên, không
valid hóa. Existing original tách reconstructed alternative; missing_unrecovered
cần đọc kèm mapping_status để phân biệt missing với unsafe/unmapped.

Canonical report không timestamp/run label; digest bao phủ membership ID, từng
record và aggregates. first/second cùng inputs phải bằng nhau; canonical-report
đã có mà khác content thì reject, không ghi đè hoặc chỉnh report cho khớp.
Public exporter chỉ fixed keys/enums với nonnegative integers; không đưa paths,
source IDs, per-file tokens/hashes, reviewer attribution hoặc OCR text vào evidence.
Private manifest/report digests chỉ đối chiếu local, public chỉ ghi equality/scope.

Pilot chứng minh repeatable engineering validation trên selected inputs nếu checks
đạt. Không chứng minh OCR accuracy, financial correctness, original equivalence,
Drive run identity, table completeness hoặc dataset-wide readiness. Kết quả và
khuyến nghị cụ thể ở [sanitized evidence](reviews/M1-04b-evidence.md).
