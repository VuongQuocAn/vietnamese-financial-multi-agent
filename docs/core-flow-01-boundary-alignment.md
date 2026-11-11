# CORE-FLOW-01 — Kết quả sửa truyền phép tính tới M7

Status: **REVIEW**. **CONDITIONAL READY trong phạm vi key rotation + projection**:
Q5 đã trả đúng hai mức giảm; Q4/Q6/Q7/Q8 chạy fresh cùng runtime. Q6 còn caveat
mâu thuẫn từ Specialist, cần Tech Lead review; không tuyên bố toàn hệ thống đạt
financial accuracy hoặc tự chuyển DONE.

## Thay đổi

- QA Gateway dùng FreeTierKeyPool hiện có cho Supervisor, Specialists, M6 và M7.
  HTTP429 đưa key vào cooldown theo Retry-After, chuyển key khả dụng; key thành công
  được dùng tiếp. Khi pool hết khả dụng, RequestGateway không retry lại pool đó.
  Ghi actual attempts/usage/cooldown bằng chỉ số key; không ghi credentials.
- Giữ quota ứng dụng chung, không giả định mỗi key có project/quota riêng. Project
  mapping chưa biết. Rotation thành công không chứng minh quota độc lập theo key.
  Storage QA mặc định `artifacts/qa-key-pool`, cấu hình qua `QA_GEMINI_POOL_ROOT`;
  cooldown tối thiểu qua `QA_GEMINI_COOLDOWN_SECONDS`, mặc định60giây. Quota ledger
  QA và Metadata/PDF ở scope storage riêng, không tuyên bố là quota toàn app.
- M7 nhận nguyên operands/operations/results/unit/steps đã ACCEPT trong reasoning
  calculation, bổ sung nhãn và kỳ gốc/kỳ mục tiêu theo đúng thứ tự inputs. Không
  thực thi phép tính mới. Giữ ký hiệu dấu và mẫu số, kể cả chained operations.
- Đối chiếu số nhận kết quả từng step đã ACCEPT, làm tròn như trước; cho phép
  diễn đạt kết quả âm thành “giảm8,66%”. Không chuyển thành “tăng8,66%”.
- Không đổi M5, M6, Ledger; không thêm validator, gate, agent, OCR hoặc task FIX.

## Live trên dữ liệu BBS thật

Baseline `f5baae3` + đúng4file sửa Gateway/M7; toàn bộ effective source hashes
khớp giữa Q5 và các lượt tích hợp. Fresh Ledger mỗi case; riêng Q8 dùng chung
Ledger và conversation hai lượt. Không replay câu trả lời cũ, không đổi questions.

| Case | Kết quả nội dung | Đánh giá |
| --- | --- | --- |
| Q5 | Tổng tài sản giảm 8,66%; nợ phải trả giảm 14,35% so với đầu năm; tỷ lệ nợ 59,06%, có giới hạn và nguồn PDF 5–6 | CORRECT_WITH_CAVEAT |
| Q4 | Doanh thu tăng 26,71%, lợi nhuận gộp giảm 10,84%, biên gộp năm 2025 là 7,21%; có nhận định biến động và nguồn PDF 7 | CORRECT_WITH_CAVEAT |
| Q6 | Cả hai Specialists sinh lời và thanh khoản/đòn bẩy chạy; tổng hợp đúng số liệu sinh lời, tài sản/nợ/vốn | PARTIAL về caveat: Specialist sinh lời nói thiếu bảng cân đối trong khi Specialist khác đã dùng bảng đó |
| Q7 | Dùng kỳ 2025 từ tài liệu; không khẳng định doanh thu tăng vì quản lý chi phí tốt hơn; nhận định qua M6 semantic | CORRECT_WITH_CAVEAT |
| Q8 | Lượt 1 trả 59,06%; lượt 2 hiểu “tỷ lệ đó”, nêu tỷ lệ nợ chưa đủ chứng minh mất khả năng thanh toán; nhận định qua M6 | CORRECT_WITH_CAVEAT |

Hai đoạn Q5 nguyên văn:

> Tại ngày 2025-12-31, tổng tài sản của BBS ghi nhận là 266.086.680.765 VND,
> giảm 8,66% so với mức 291.306.659.104 VND tại ngày 2025-01-01. [1][2]
>
> Về nợ phải trả, tổng số dư tại ngày 2025-12-31 là 157.146.559.558 VND,
> giảm 14,35% so với mức 183.476.510.255 VND tại ngày 2025-01-01. Đồng thời,
> tỷ lệ nợ phải trả trên tổng tài sản tại thời điểm cuối kỳ (ngày 2025-12-31)
> đạt 59,06%. [2][1]

Giới hạn Q5: chưa đủ dữ liệu về nguyên nhân biến động từng cấu phần, chưa đánh giá
chất lượng tài sản/nợ. Generic gap của M7 còn xuất hiện dù hai tỷ lệ đã được trả;
đây là hạn chế trình bày, không mất kết quả tính toán. Không sửa thêm trong lượt này.
Q6 caveat không phù hợp được giữ nguyên trong trace, không che giấu hoặc sửa M5/M6.
Nguồn còn scope unresolved/page-level như trước, chưa chứng minh source cell precision.

## Bằng chứng và validation

- Q5: 5 provider attempts, 12.361 known tokens / 1 unknown; key 0 gặp HTTP 429,
  key 1 thành công ở cả 4 tầng.
- Tích hợp Q4/Q6/Q7/Q8: 23 attempts, 77.496 known tokens / 2 unknown; key 0 gặp
  HTTP 429 rồi key 1 thành công. Một HTTP 503 được retry thành công trên cùng key.
  Tổng 28 attempts / 89.857 known tokens / 3 unknown; không áp cap tổng 4/8 calls
  hoặc chuyển API trả phí.
- Q5 và tích hợp: 0 M7 rejected segments, 0 fallback. Tất cả current-request ACCEPT IDs
  được giao M7; M7 được phép tóm tắt, không cần liệt kê mọi claim.
- Audit trọng tâm: 66 fact checks, 20 approved-metric checks, 14 percentage steps,
  152 citation bindings, 0 mismatch. Các checks có lặp giữa claims/cases, không phải
  252 dữ liệu độc lập. 4.204 protected files hashes unchanged ở mỗi run.
- 37 targeted tests PASS cho QA projection/numeric/rotation, metadata pool,
  extraction compatibility và M6 Lite; Ruff lint/format 6 file PASS; planning/diff
  checks PASS. Không chạy lại toàn bộ 201 tests local. CI chạy nhóm trọng tâm sau push.

Artifacts local ignored: `artifacts/evidence/CORE-FLOW-01/projection-q5-01/` và
`projection-integrated-01/`, gồm questions, answer nguyên văn từng lượt, M5 plan,
Specialists/tools, M6 decisions, Ledger identities, M7 payload/used claims và exact
citations. Provider attempts thật nằm trong `key-pool-events.json`; logical calls
trong `provider-events.json` không được đánh đồng với attempts sau rotation.
`projection-audit.json` và `projection-local-preservation.json` giữ audit/source
preservation. Câu trả lời đầy đủ ở từng `Q*-answer-and-trace.md`; IDs dài chỉ ở trace.

Implementation là commit chứa báo cáo này, parent `f5baae3`; SHA chính xác và CI
đúng SHA được xác minh sau push, ghi tại receipt local và bàn giao. Chỉ stage phần
thuộc task, giữ mọi local edits có trước. Evidence cũ còn nguyên trong Git/artifacts,
không gán kết quả live mới cho implementation cũ hoặc cho toàn bộ201tests.

Next action: Tech Lead review key rotation/projection và kết quả live, đặc biệt caveat Q6.
