# M6-06 — Verified Claim Ledger

Status **IN_PROGRESS**, Owner giao04/11/2026; baseline main/origin
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
Ruff/planning/diff PASS. BBS replay và restart/query/hash checks đang chạy;
CI chưa có kết quả. Proof replay kiểm tra
consistency theo policy và saved results; không xác thực độc lập upstream hoặc
PDF financial accuracy. Caveated ACCEPT không đồng nghĩa independent audit.

Next action: hoàn tất validation và bàn giao Tech Lead review M6-06.
