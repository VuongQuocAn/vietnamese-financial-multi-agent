# GEN-02-Fix-A — QA Coverage & False Abstention Recovery

Ngày 09/11/2026, Asia/Bangkok. Baseline `6f682c3`, implementation chưa commit.
Status **IN_PROGRESS**; GEN-02 vẫn REVIEW. Không M8, OCR, Gemini live hoặc sửa H08.

## Targeted audit và fixes

| Case | Expected evidence/behavior | Before và earliest failure | General fix |
| --- | --- | --- | --- |
| H03 | BCC2025 separate revenue_yoy, current/comparative revenue trong cùng filing | M5 materialization thiếu prepared metric → internal_error | Chuẩn bị metadata catalog riêng trong bộ nhớ từ approved formula/version/digest và các operands duy nhất; bổ sung graph nodes/edges, giữ dữ liệu gốc. M4 tính Decimal, accounting/scope compatibility và lineage; M6/Ledger/M7 xử lý như metric có sẵn. Thiếu operands và thiếu preparation authority có capability reasons riêng. |
| H06 | BCC2024 PDF17/11, khấu hao phần mềm theo đường thẳng 3–8 năm | M5 đòi cụm “khấu hao phần mềm…” liên tục; source đặt subject trước predicate | Giữ noun phrase chính xác, cho đảo predicate/subject trong cùng câu; không dùng bag-of-words hoặc suy ra quan hệ mới. |
| H07 | BBS2025 PDF11/9, phương pháp khấu hao tài sản hữu hình | M5 chọn heading PDF10 có quality flag; bỏ paragraph PDF11 đã có trong neighbors | Xét paragraph liên quan trong bounded retrieval pool, ưu tiên candidate không có pdf_review flag; không bỏ flag hoặc chuyển INVESTIGATE thành ACCEPT. Câu phương pháp trước bảng giữ quotation và giới hạn excerpt, không bịa số thời gian của bảng. |
| H11 | BBS2025 PDF11/17–20 và PDF12/6, hai requirements độc lập | M5 bỏ bare conjunct “về vay…”; M7 cùng parser cũng bỏ ý và báo completed | Kế thừa document intent qua conjunct “về”, giữ noun conjunction, deduplicate tương đương; IDs xác định theo request. M7/Firewall tự đọc original question, không tin inventory M5. Test cố nâng partial thành answered bị BLOCK. |
| H12 | BCC2024 PDF18/5–11; giữ restriction Gross Margin | M5 coi câu dẫn có dấu hai chấm là heading, tách parent topic khỏi danh sách | Câu dẫn không là heading riêng; giữ parent heading + đủ năm điều kiện liên tục. Financial gate không đổi; document lane độc lập, phát hành useful partial. QA-01b C1 được chạy riêng. |

## Phương pháp và phạm vi

H03/H06/H07/H11/H12 đã công bố trong GEN-02, nay là development regression,
không gọi lại là blind. Before lấy đúng traces/oracles GEN-02 đã lưu; không tạo lại
40 câu hoặc sửa original frozen data. Chỉ hai vòng sửa–kiểm thử chính; một final pass
cho focused regression và6 fresh cases, khóa runtime trước execution. Fresh expected
lấy accepted source selectors và Decimal độc lập runtime, trước output; chưa phải human gold.

Giữ M5 → M4/BM25/EF-EG → M6 → Ledger → M7/Firewall. M6 literal quotation proof vẫn
replay original references, citations, continuity và source-quality. Metadata metric mới
không tự là verified; không đổi formula/accounting/scope approval. Accepted source và
ledger cũ read-only. Các ledger mới nằm riêng dưới artifacts task.

## Validation

Vòng1:25 existing tests PASS; targeted actual pipeline cho4 full +1 useful partial.
Vòng2/final focused tests:122 PASS, gồm6 mới; Ruff8 Python files PASS.
Một test mới ban đầu thất bại do test tự render forged presentation trước Firewall;
đã sửa fixture để dùng original rendering, runtime không cần sửa cho lỗi test này.
Planning checker mở rộng grammar cho ID GEN có suffix `-Fix-A`, giữ Task ID Owner giao.

Final results, fresh checks, source-quality control, ledger compatibility và CI sẽ
được ghi sau khi lượt validation hiện tại hoàn tất. Không tune theo fresh outputs.

Artifacts local `artifacts/evidence/GEN-02-Fix-A/`: `baseline.json`, `round-1/`,
`fix-lock.json`, `final-inputs/actual/`, `fresh/actual/`, `final-tests.log`,
`source-quality-control/`, `legacy-compatibility.json`. Mỗi actual JSON chứa answer,
fulfilled/unfulfilled requirements, agent/tool traces, evidence, M6/admission/M7/Firewall
và citations. Independent audit đối chiếu accepted records/facts, exact quotation,
Decimal và expected requirements, không lấy pipeline status làm kết luận.

## Limitations và điểm dừng

H08/Fix-B, OCR quality, PERF-01, WEB-02 và M8 ngoài phạm vi. Provenance tài chính
vẫn có page-level/uncertain caveats; không tuyên bố cell-level accuracy hoặc financial
quality toàn hệ thống từ engineering tests. Full evaluation dùng workingtree giữ nguyên
GEN-01a pending; CI được đối chiếu riêng với implementation SHA không chứa pending đó.

Next action: hoàn tất final validation và bàn giao Tech Lead ở REVIEW.
