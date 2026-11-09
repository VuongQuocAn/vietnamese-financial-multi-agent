# PERF-01 — Fast Path Optimization

Ngày09/11/2026 (Asia/Bangkok). Status **REVIEW**; baseline `8478c98`.
Implementation `de2d430bb59be9539ede5e772470dba8011483c1` đã push main;
[CI42565568084](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/42565568084)
SUCCESS đúng SHA, Python3.12 và Web smoke; full regression manual SKIPPED.
Giữ pending GEN-01a/Web. Không OCR/Gemini, không sửa frozen GEN-02/evidence cũ.

Kết quả có giới hạn: cache-hit median nhanh23,2%, document refresh nhanh23,7%, nhưng
**median force-refresh toàn nhóm chậm hơn4,5%**. Không đề nghị coi ledger cache là
thành công về latency. Chờ Tech Lead đánh giá tradeoff trước nghiệm thu.

## Phạm vi đo

Sáu câu persisted GEN-02 D01/D05/D17/D22/D18/D23: single fact, approved metric,
document QA, hai yêu cầu document, mixed QA và causal partial-control. Cùng approved
BBS2025 sources, policy và11claims QA-01b seed sao chép riêng cho mỗi phase.
Một process/phase, một initialization, tuần tự refresh rồi reuse mỗi case; request
`allow_gateway=false`, `execution_mode=deterministic`. Không dùng H08 corrected path.
Instrument `perf_counter`, stage traces và inclusive component wrappers; không cộng
parent/child timings. Catalog initialization không tính vào E2E request; chưa đo
riêng OS process/import startup. Cùng pending GEN-01a code ở cả hai lượt local;
CI kiểm tra implementation đã stage, không chứa các pending changes đó.

Hai baseline không dùng cho so sánh: lượt đầu trùng focused tests; lượt snapshot kế
tiếp không tìm đúng default trust-store root. Giữ traces/log và số đo trong
`baseline.json/discarded_attempts`. Baseline hợp lệ dùng hai module gốc từ `8478c98`,
không chạy tests đồng thời, cấu hình DOCUMENT_SOURCE_POLICY_ROOT tuyệt đối đến đúng
store mà after nạp mặc định. `policy-resolution-control.json` xác nhận cùng typed
policy digest/2reviews/1approval và file hash; không dùng policy rỗng làm baseline.
Baseline xác nhận được đo lại sau after vì lỗi đo lường; cột trước/sau chỉ hai biến
thể code. Cùng wrapper, seed, process/cache conditions và effective policy; không chọn
lại câu hỏi hoặc mở vòng tối ưu thứ ba. Đây là các phép đo lỗi được loại minh bạch,
không phải thêm vòng tìm tối ưu hoặc lấy lượt nhanh nhất.

## Hai điểm sửa có giới hạn

1. Ledger đọc/parse toàn snapshot và tính digest proof lặp lại ngay cả cùng bytes;
   query còn sao chép các claims ngoài scope. Reuse private parsed snapshot theo
   exact wire bytes, ghi nhận proof đã kiểm tra trong snapshot; lọc query trước khi
   trả detached copies. Vẫn kiểm tra current source policy ở mỗi read/lookup.
2. Document repository parse và validate toàn corpus cho mỗi source document trong
   composition. Reuse một private parsed snapshot theo exact bytes, chỉ copy records
   được chọn. Loader tiếp tục kiểm tra toàn bộ manifest pins, payload hashes,
   page/image/snapshot binding và tạo FTS/catalog; không cache approved composition.

## Cache và invalidation

Mỗi repository instance giữ tối đa một parsed snapshot + original bytes. Cache key
là toàn bộ bytes thực tế (không dùng mtime/size); lifetime đến lần bytes đổi hoặc
instance bị giải phóng. Vẫn đọc file và kiểm tra storage boundary mỗi lần. Missing,
deleted, external replacement và atomic admission/write đổi bytes sẽ invalidation;
write methods nhận deep copies, lần đọc sau nạp bytes vừa ghi. Restart không có
cache, chạy schema/identity/proof validation như trước.

Policy/release không nằm trong cache trust: không cache kết quả source eligibility.
Ledger kiểm tra `document_source_issues` hiện tại, bao gồm current store/root/pin,
review, approval/release, composition/snapshot và content/selector bindings. Claim
trước đó bị quarantine chưa được validation sẽ phải validate khi trở lại eligible.
Cache không chứa M6 decision mới hoặc M7 answer; request cache hiện hữu không đổi.

## Kết quả và validation

Đơn vị giây; số âm ở cột cuối nghĩa là chậm hơn. Mỗi case chỉ một lượt/mode.

| Case | Refresh trước | Refresh sau | Cải thiện | Cache-hit trước | Cache-hit sau | Cải thiện |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| D01 fact | 30,814 | 33,322 | -8,1% | 7,427 | 6,524 | 12,2% |
| D05 metric | 37,723 | 38,333 | -1,6% | 7,160 | 6,785 | 5,2% |
| D17 document | 16,910 | 12,565 | 25,7% | 8,701 | 4,864 | 44,1% |
| D22 hai document requirements | 19,080 | 14,880 | 22,0% | 8,626 | 4,420 | 48,8% |
| D18 mixed | 83,794 | 78,349 | 6,5% | 46,603 | 37,185 | 20,2% |
| D23 partial-control | 66,598 | 62,337 | 6,4% | 38,253 | 32,888 | 14,0% |
| Median sáu cases | 34,269 | 35,828 | **-4,5%** | 8,663 | 6,655 | **23,2%** |

| Component / nhóm | Trước | Sau | Cải thiện |
| --- | ---: | ---: | ---: |
| Financial refresh median D01/D05 | 34,269 | 35,828 | -4,5% |
| Document refresh median D17/D22 | 17,995 | 13,722 | 23,7% |
| Document cache-hit median D17/D22 | 8,663 | 4,642 | 46,4% |
| Ledger query median / sáu refresh | 4,541 | 4,699 | **-3,5%** |
| Source list/load median / bốn refresh có document sources | 3,653 | 0,906 | 75,2% |
| Graph constructor median / D18,D23 refresh (inclusive source load) | 9,309 | 6,492 | 30,3% |
| Catalog initialization / một process | 10,907 | 8,287 | 24,0% |

Ví dụ root-cause baseline: D18 có8ledger queries/12,110s và4source-document loads/
6,921s; D22 có2source loads/3,662s. Ledger query không nhanh hơn sau thay đổi:
detached copies/current policy vẫn tốn thời gian. M5 của D05 cũng tăng16,653→17,186s;
catalog initialization chênh lớn dù không phải mục tiêu sửa. Không đủ mẫu để tách
ảnh hưởng retention/copying, GC và nhiễu máy; không gán mọi chênh lệch cho tối ưu.
Graph timing giảm một phần do source loader bên trong, không phải bỏ graph validation.

Toàn bộ12responses khớp sau loại timing và transient M5 plan/origin-candidate IDs;
không loại verified claim IDs, M6 outcomes, evidence/citation identity hoặc content.
Answer text/classification, Decimal values, requirements, agent/tool traces, snapshot/
composition, M6/M7/Firewall giữ nguyên. Hai final ledgers13entries **byte-for-byte
identical**. Đây là tương đương baseline, không phải independent financial accuracy.

Local99focused tests đã PASS:98trong nhóm cuối +1test fixture đã sửa và chạy riêng.
Hai vòng implementation/test; failures là tests mới truy cập nhầm computed properties
không có trong wire JSON, không phải nới validation hoặc sửa financial policy.
Ruff changed files, planning/diff checks PASS. CI SUCCESS được xác minh bằng initial
run metadata đúng SHA và `gh run watch --exit-status` exit0; transcript cuối lưu cả
hai jobs và required steps PASS. Export JSON/log chi tiết sau đó bị GitHub API403
rate-limit; không suy số lượng CI tests từ local hoặc từ tên step.
Persisted H08 original/PDF30 claims bị filter ở cả cold/warm reads, old proof replay
bị reject;17legacy accepted proofs replay/restart exact. Tests còn kiểm tra policy
change sau warm cache, clean claim không bị ẩn, snapshot/composition/release mismatch,
same-size/same-mtime replacement, external writer/deletion và detached caller mutations.
38approved input hashes,4frozen GEN-02 files, current policy và8pending source/Web/
untracked hashes nguyên; pending planning/CI giữ riêng ngoài commit PERF-01.

Artifacts riêng tại `artifacts/evidence/PERF-01/`: baseline/after/comparison,
bottleneck-analysis,12traces mỗi phase, focused logs và persisted safety controls.

## Giới hạn

Sáu cases offline trên BBS2025/không provider không phải M8 benchmark hoặc independent
financial accuracy; BCC dùng riêng cho quarantine/legacy controls. D22 là nhiều yêu
cầu/trang trong cùng filing, không xác nhận QA cross-filing chưa được policy cho phép.
Không suy P95 toàn hệ thống. Catalog/graph construction, M5 resource copies,
M6 và M7 vẫn chạy theo contracts hiện hữu; không redesign hoặc bỏ verification để
đạt mục tiêu latency. H08 activation còn thiếu và PDF30 quarantine không thay đổi.
P2 đề xuất profiling detached copies/catalog retention trước khi quyết định tiếp tục
ledger optimization; chưa triển khai. Không tối ưu vòng ba để chạy theo target.

Next action: Tech Lead review.
