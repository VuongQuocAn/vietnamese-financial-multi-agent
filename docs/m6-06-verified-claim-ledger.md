# M6-06 — Verified Claim Ledger

Status **REVIEW**, Owner giao04/11/2026; baseline main/origin
`9b807f370c144181588818c46de70e3d5f0fe485`. M6-01–05 DONE.

## Contracts và admission

`VerificationHistory` chứa exact `VerificationProofContext` từng attempt và
`VerificationLoopResult` được M6-05 lưu. Context giữ batch, validation, evidence,
logic và original legacy pairing khi cần. Admission tái chạy deterministic Judge
qua bounded loop, đối chiếu toàn bộ outcome. Direct yêu cầu một context/attempt;
revised yêu cầu parent REVISE, exact proposal/parent digest, child identity riêng
và fresh non-legacy M6-02/03/04. Chỉ final ACCEPT được admission.

`VerifiedClaim` giữ identity và full history; `accepted_claim`, `decision`,
`content`, `citations`, `caveats` là projections của final record. Không copy/đổi
trạng thái pending của CandidateClaim; verified chỉ ở outer VerifiedClaim.
Full typed calculation response chứa exact values, formula/version/digest,
operand bindings và lineage; citations giữ PDF page/anchor/provenance level.

ID `verified:<sha256>` bind source digest, original/accepted/parent candidate,
company/document/snapshot/period/kind, content digest và final decision digest/policy.
Payload SHA256 bổ sung bảo vệ full proof. Không semantic deduplication.

## Persistence và retrieval

`VerifiedClaimRepository(root).admit(history)` trả stored/idempotent/rejected;
same identity/different proof payload ném `LedgerConflict`, không overwrite.
`admit_many(histories)` kiểm từng proof và ghi một atomic snapshot cho batch;
rejected claim không chặn valid claim, còn payload conflict hủy toàn bộ lần ghi.
Single writer/root hoặc shared process lock; dùng `atomic_json` tạo
`verified-claims.json`, schema `verified_claim_ledger_v1`. Đọc lại validate typed
JSON, duplicate IDs, replay proof và so payload/identity/checksum; malformed hoặc
tampered snapshot fail closed. Decimal giữ wire strings theo contracts cũ.
Trong một instance, chỉ cache digest của full validated entry payload; đọc vẫn
parse typed JSON và đối chiếu digest. Payload thay đổi buộc replay lại; restart
không dùng cache cũ. Không cache mutable models hoặc dựa riêng file mtime.
Full batches được giữ vì Judge input/result digests bind cả batch; đây là proof
cần cho restart replay, không sao chép PDF/OCR hoặc lịch sử orchestration khác.

`VerifiedClaimLedger(repository).find_claims(VerifiedClaimQuery(...))` chỉ đọc;
filters AND theo company/document/snapshot/period/kind/item/reference/metric.
Trả typed matched/empty và toàn bộ matches có identity, thứ tự theo verified ID.
Không chọn snapshot, merge nguồn, tính số, gọi LLM hoặc fallback candidates.
Các returned models detached khỏi persistence; caller mutation không sửa ledger.

```python
repository = VerifiedClaimRepository(configured_ledger_root)
admission = repository.admit(history)  # exact saved contexts + M6-05 outcome
ledger = VerifiedClaimLedger(repository)
matches = ledger.find_claims(VerifiedClaimQuery(company_id=company_id, document_id=document_id))
for entry in matches.claims:
    content, citations, caveats = entry.content, entry.citations, entry.caveats
    calculation = entry.accepted_claim.calculation
    verification_identity = entry.identity.final_decision_sha256
```

Caller M6 giữ contexts tương ứng lúc Judge/loop chạy; ledger không tự tìm proof
hoặc truy xuất lại nguồn. M7 nhận facade và đọc final content; parent REVISE chỉ
nằm trong verification history, không thành một match độc lập.

## Validation

Local:140 ledger/M6-01–05 compatibility PASS trước batch/cache refinement;
22 final ledger tests PASS sau batch admission, metric-item filter và digest cache.
Ruff/planning/diff PASS. BBS replay, restart/query và protected hash checks PASS.
Accepted implementation tree `88ae91d40d5d4f0b4cf3f3526b96533b34a3d694`
đã push main; runtime được thêm tại162e438,88ae91d chỉ sửa format ví dụ trong docs.
[CI41823101329](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/41823101329)
completed/SUCCESS đúng88ae91d: Python3.12 lint/format/planning/focused tests SUCCESS;
Web smoke và full regression SKIPPED theo điều kiện workflow. CI đầu162e438
dừng ở markdown Python fence format; đã sửa, không đổi runtime/policy.
Targeted final tại `artifacts/evidence/M6-06-integrity-final/summary.json` PASS:
57/57 primary entries khớp exact original proof history/accepted claim/citations/
caveats;27 calculation lineages giữ nguyên,2 revised entries,8/8 typed query filters.
50 entries thuộc original normalized snapshots và7 thuộc recovery2022; không merge.
Đây là cold-read rồi query trên implementation cache cuối đúng88ae91d.
Proof replay kiểm tra
consistency theo policy và saved results; không xác thực độc lập upstream hoặc
PDF financial accuracy. Caveated ACCEPT không đồng nghĩa independent audit.

## Bounded BBS evaluation

Oracle `evaluation/m6-06-scenarios.json` được cố định trước chạy, SHA256
`90da62247fdf219261db683f99f3f2f922a3f7022724ec512fc6bb4d0f28f556`;
pin M6-05 oracle1190e69 và lấy expected decisions từ policy oracle đó, không dùng
ledger results làm nhãn. Inputs giữ nguyên accepted M6-05/BBS2021–2025/recovery2022,
saved M5/M6 mock/live results được phân nhóm; không chạy lại Gemini/OCR/extraction.
Chỉ mixed batch mới dùng fresh deterministic M6-02/03/04 với semantic budget0.

```powershell
.venv\Scripts\python.exe scripts/evaluate_m6_06_ledger.py --output artifacts/evidence/M6-06-ledger-final-v2
```

Output phải mới; run đã có không được overwrite. Full summary tại ignored
`artifacts/evidence/M6-06-ledger-final-v2/summary.json`; primary final-code integrity
tại `artifacts/evidence/M6-06-integrity-final/summary.json`.

| Chỉ số | Kết quả |
| --- | --- |
| Saved proof histories + mixed batch | 107 + 2 = 109 cases,109/109 đúng oracle |
| Main ledger | 58 entries stored;51 decisions rejected,không stored |
| Representative persisted BBS | 29/30 stored;fact-02-b03 quality insufficient bị reject đúng oracle |
| Direct/revised primary entries | 55 direct +2 accepted child;thêm1 valid metric từ mixed batch |
| Targeted controls | 27/27 PASS:4 valid stored,17 rejected,6 persistence/identity/query controls |
| Duplicate/payload conflict | 1 idempotent;1 conflict,không overwrite |
| Unsafe verified entries / false rejection | 0 / 0;admission precision theo oracle1.0 |
| Restart / original-recovery / metric separation / empty query | PASS;không chọn snapshot hoặc fallback |
| Final-code exact primary proof integrity | 57/57 entries;27 calculation lineages;2 revisions;8/8 filters |
| Protected artifacts/Web | 14.569 hashes unchanged |
| Gemini/OCR calls | 0/0 |

4 positive controls dùng roots riêng, không cộng vào58 unique entries của main
evaluation ledger.51 rejected replay cases cộng17 rejected targeted controls đều
không tạo unsafe entries; original REVISE chỉ giữ trong accepted child's history.
Full replay trước cache có2 grouped query checks, còn targeted final-code checks
kiểm8 filters riêng và đối chiếu history với proof gốc, không so một field với
chính field đó. Engineering/source-bound policy precision không phải independent
PDF financial accuracy hoặc bằng chứng lợi ích Multi-Agent end-to-end.

## Root causes và giới hạn

Replay từng entry khi nhập nhiều claims gây đọc/replay lặp trên snapshot lớn;
`admit_many` chuyển sang một atomic write cho batch. Read API vẫn kiểm file hiện
tại; digest cache chỉ bỏ replay cho full payload đã xác minh trong cùng instance.
Cold restart vẫn replay toàn bộ proof. Snapshot primary57 entries khoảng136MB;
full proof JSON có chi phí dung lượng/RAM và thời gian cold read, phù hợp bounded
local evaluation hiện tại, chưa đánh giá scaling.

Fixture tampered-source ban đầu gán vào frozen ObservationIdentity nên lỗi trước
khi tới gate; đã đổi sang model_copy identity, giữ frozen contract. CI đầu lỗi
format ví dụ Python trong Markdown, đã sửa exact fence và CI đúng88ae91d PASS.
Run `M6-06-ledger-final` được dừng sau7 metric imports để chuyển sang batch,
không overwrite outputs; `M6-06-ledger-final-v2` là full replay trước cache.
Targeted final integrity đọc lại primary ledger bằng implementation cache cuối;
không gọi việc này là fresh full replay của tất cả negative controls trên cache.

Checkpoint tiếp theo chỉ docs/planning [skip ci]; không gán CI88ae91d cho SHA
documentation mới. Chưa Tech Lead nghiệm thu hoặc tuyên bố toàn M6 hoàn thành.

Next action: Tech Lead review M6-06 và điều kiện hoàn thành M6; không tự bắt đầu M7.
