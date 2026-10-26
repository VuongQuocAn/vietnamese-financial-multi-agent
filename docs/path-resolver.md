# Read-Only Path Resolver — M1-03b

Public API thuộc `document_processing`:

```python
from vietnamese_financial_multi_agent.document_processing import resolve_path

result = resolve_path(request, config)
```

`request: PathMappingRequest` mang reference/provenance và source mappings do caller
phê duyệt; `config: core.DataConfig` mang local roots đã cấu hình. Output là
`PathMappingResult` v1, giữ contracts/schema cũ. Core không import document_processing.

## Lifecycle và root binding

1. `map_path_lexically(request)` thực hiện policy portable hiện hữu. Các status
   unsafe/unmapped/ambiguous dừng trước filesystem I/O. Không viết lại lexical logic.
2. Chỉ một candidate not_checked hợp lệ được bind bằng `config.get_root(root_key)`.
   Unknown/unconfigured key trả unsafe/root_binding_error; không thử root khác.
3. Tách suffix POSIX theo components và nối vào root. Quality validator xác minh
   suffix relative, không traversal, absolute/drive/UNC/stream injection. Không basename
   lookup, glob, scan hoặc tìm artifact từ source_ref.
4. Kiểm tra metadata từng ancestor của root, root và components hiện hữu của target.
   Root phải tồn tại và là directory; parent hiện hữu phải là directory. Root chưa
   có/không truy cập được là unsafe, vì chưa thể xác minh containment của binding.
5. Resolve root strict và target non-strict, so containment bằng `is_relative_to`,
   không dùng string prefix. Missing parent/target chỉ thành missing sau containment
   verified; symlink/reparse hoặc containment fail thành unsafe/rejected.
6. Target hiện hữu phải regular file, PNG cho raw/crop hoặc JSON cho OCR page
   (suffix check không phân biệt case). Extension chỉ là structural check, không
   chứng minh nội dung; resolver không mở/giải mã PNG/JSON. `os.access(..., R_OK)`
   là kiểm tra metadata bổ sung, không đảm bảo lần mở file kế tiếp sẽ thành công.
7. Mọi output qua structural và `validate_path_mapping_result` quality validation.
   Unsafe source/context vẫn được giữ nguyên để review; những lỗi quality nguồn
   được ghi issue, không sửa source cho hết lỗi.

## Status và issues

| Status | Runtime evidence |
| --- | --- |
| resolved | Unique candidate = confirmed_target; containment verified, existence exists; regular file và structural type/readability checks đạt |
| missing | Unique logical candidate, containment verified, existence missing; issue missing_target, không confirmed_target |
| unsafe | Có issue machine-readable, không confirmed_target; không bảo đảm target dùng được |
| unmapped/ambiguous | Giữ lexical result, không runtime checks hoặc chọn candidate |

Issues runtime: root_binding_error, invalid_runtime_root, root_unavailable,
root_not_directory, symlink_or_reparse_point, parent_not_directory,
runtime_containment_failed, target_not_regular_file, resource_extension_mismatch,
target_inaccessible, permission_denied, filesystem_error, missing_target.
PermissionError khác missing; các OSError/resolve loop không xác định trả unsafe.
Exception messages không được đưa vào result/log để tránh lộ configured local paths.

Original path, category, source_ref/source_location, anchor/bbox, crop_view và
candidate_page_image được copy sâu, giữ missing/null. Missing results giữ mapping ID,
root key và full relative suffix. Missing crop/color view chỉ báo missing, không recovery
hoặc sửa crop metadata. Synthetic placeholders trong tests không phải dữ liệu tài chính.

## Symlink, junction và root identity

Policy bảo thủ: từ chối mọi symlink và mọi Windows reparse point, kể cả link nằm
bên trong root, broken/loop/chain, root là link hoặc ancestor của root là link.
Dùng lstat + S_ISLNK và FILE_ATTRIBUTE_REPARSE_POINT, hỗ trợ Windows Python 3.11
không cần Path.is_junction (3.12). Điều này cũng từ chối reparse point không phải
junction, chẳng hạn cloud placeholder; caller cần local root không có reparse point.
Không mở rộng policy theo loại reparse tag hoặc triển khai secure descriptor API.

Input roots được phép overlap. Resolver chỉ dùng key trong candidate, không thay
source category hoặc chọn root dài hơn. Metadata samefile giữa selected root và
các configured roots khác sinh issue thông tin shared_root_identity nếu cùng location;
status vẫn có thể resolved. Root khác không tồn tại/không stat được không làm thay
đổi selected binding. Đây là đối chiếu số lượng roots cố định, không scan dataset.
Không chứng minh nguồn/run identity bằng filesystem location; trách nhiệm phê duyệt
mapping và cấu hình thuộc caller. Bind mounts, hard links, case/Unicode aliases,
Windows short names và filesystem aliases khác không được phát hiện đầy đủ.

## Giới hạn và giao tiếp M1-03c

Các lstat/resolve/access calls rời nhau: TOCTOU có thể xảy ra giữa checks hoặc sau
khi trả result. Không giữ descriptor/file handle, không bảo đảm chống adversarial
filesystem mutation. Result chỉ là snapshot metadata. os.access có giới hạn ACL,
network filesystem và danh tính process; lỗi khi loader thực sự đọc vẫn phải xử lý.
Filesystem case-insensitive có thể chấp nhận suffix case khác; resolver không scan
tên thật hoặc chuẩn hóa Unicode/case. Source root matching vẫn exact-case theo v1.

Contract v1 chỉ chứa logical target, không có field local path. M1-03c chỉ được dùng
confirmed_target của resolved result, bind lại key bằng cùng DataConfig và suffix
components khi mở file, kiểm tra lại containment/access theo policy tại thời điểm dùng.
Không dùng result cũ như quyền đọc vĩnh viễn hoặc suy ra content validity từ extension.
Thiết kế loader/secure-open cụ thể thuộc task sau; M1-03b không triển khai loader.
