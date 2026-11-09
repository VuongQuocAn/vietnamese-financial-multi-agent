# PERF-01 — Fast Path Optimization

Ngày09/11/2026 (Asia/Bangkok). Baseline `8478c98`; chờ implementation commit/CI.
Giữ pending GEN-01a/Web. Không OCR/Gemini, không sửa frozen GEN-02/evidence cũ.

Kết quả có giới hạn: source loading giảm rõ, nhưng **median force-refresh chậm hơn
14,3% trong mẫu này**; không đạt mục tiêu tăng tốc tổng thể. Không đề nghị coi ledger
cache là thành công về latency. Chờ Tech Lead đánh giá tradeoff trước nghiệm thu.

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

Lượt baseline đầu bị focused tests chạy đồng thời, nên bị loại khỏi so sánh. Giữ
nguyên traces/log và số đo trong `baseline.json/discarded_attempt`; đo xác nhận một
lần bằng source snapshot với hai module gốc lấy từ HEAD, không chạy tests đồng thời.
Final baseline/after đều tuần tự, cùng wrapper và điều kiện process/cache. Không
chọn lại câu hỏi, đổi sources/policy hoặc mở vòng tối ưu thứ ba.

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
| D01 fact | 33,129 | 33,322 | -0,6% | 5,383 | 6,524 | -21,2% |
| D05 metric | 29,564 | 38,333 | -29,7% | 5,895 | 6,785 | -15,1% |
| D17 document | 13,466 | 12,565 | 6,7% | 6,871 | 4,864 | 29,2% |
| D22 hai document requirements | 14,671 | 14,880 | -1,4% | 6,819 | 4,420 | 35,2% |
| D18 mixed | 90,669 | 78,349 | 13,6% | 46,422 | 37,185 | 19,9% |
| D23 partial-control | 69,404 | 62,337 | 10,2% | 38,469 | 32,888 | 14,5% |
| Median sáu cases | 31,346 | 35,828 | **-14,3%** | 6,845 | 6,655 | **2,8%** |

| Component / nhóm | Trước | Sau | Cải thiện |
| --- | ---: | ---: | ---: |
| Financial refresh median D01/D05 | 31,346 | 35,828 | -14,3% |
| Document refresh median D17/D22 | 14,068 | 13,722 | 2,5% |
| Document cache-hit median D17/D22 | 6,845 | 4,642 | 32,2% |
| Ledger query median / sáu refresh | 4,336 | 4,699 | **-8,4%** |
| Source list/load median / bốn refresh có document sources | 3,271 | 0,906 | 72,3% |
| Graph constructor median / D18,D23 refresh (inclusive source load) | 9,447 | 6,492 | 31,3% |
| Catalog initialization / một process | 14,347 | 8,287 | 42,2% |

Ví dụ root-cause baseline: D18 có8ledger queries/13,434s và4source-document loads/
6,540s; D22 có2source loads/2,434s. Ledger query không nhanh hơn sau thay đổi:
detached copies/current policy vẫn tốn thời gian. M5 của D05 cũng tăng13,322→17,186s;
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
Ruff changed files, planning/diff checks PASS. CI chưa xác minh tại bản report này.
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

Next action: xác minh CI đúng implementation SHA rồi chuyển REVIEW cho Tech Lead.
