# M6-PY-01 — Python Proof Verification

Trạng thái **DONE — Owner xác nhận hoàn thành ngày17/11/2026**.
Nghiệm thu implementation và evidence đã bàn giao tại `dd16592`, đã push main và
xác minh remote SHA; giữ nguyên các giới hạn đã báo. Phiên đóng chỉ cập nhật
tài liệu/tracking và kiểm planning/diff/Git, không sửa runtime hoặc chạy lại
tests/API/OCR/Gemini/PDF/full CI.
Implementation `95229f83be55ad43c8e61f2a88bcb7e59c5db6b9`, sau bản đầu `0eff5c7`;
baseline remote `cda39b0`. Worktree riêng bảo toàn local edits của checkout gốc.

M6 adapter đọc proof từ Workspace thành pending Python claim có version, giữ toàn
manifest và source citations. M6 rehydrate catalog, so code/input/execution digests,
raw/base values/scale, parser/context/provenance, chạy lại cùng image trong Docker
Worker và so exact Decimal. Tái sử dụng validators, Evidence Obligations và semantic
batch hiện có cho công thức/đơn vị/kỳ/goal. Ledger v2 đối chiếu saved replay, unit
proof, semantic digest và verified goal binding; v1 vẫn đọc được. M7 giữ nguyên;
không sửa M5-PY-01, Coordinator, Calculator hoặc worker.

Hai actual Qwen calls, **18.647tokens**, không retry/unknown, không gọi M5/M7 mới.
Dùng nguyên saved M5-PY-01 `live-final/rms.json` trên JSON/EF-EG BBS2025.

| Probe | Bằng chứng và kết quả cuối |
| --- | --- |
| RMS doanh thu2024/2025 | Hai operands `355507372286` và `450474531227`; independent Docker replay khớp `405778754393.2543044639216769104146 VND`. Qwen SUPPORTED/G3. M6 3ACCEPT → Ledger v2 3entries, gồm1Python → M7 phát hành3claims/8citations. |
| Wrong formula: bỏ `.sqrt()` | Code chạy/replay khớp `164656397516940999495662.5` nhưng dimension là VND², declared output VND. Final M6 **ABSTAIN**, `python_output_unit_mismatch`; Ledger **rejected**, không M7 release cho candidate này. |

Nguồn JSON trang7, value pointers `/blocks/3/table/rows/2/5` và
`/blocks/3/table/rows/2/4`; giữ row/header/unit/company citations và các giới hạn
`json_source_not_pdf_verified`, `source_reference_uncertain`, `page_level_only`.
Không kiểm lại PDF/OCR và không nâng nguồn thành financial_fact_verified.

Lỗi tìm được trong live: Qwen **false-positive** cho code bỏ căn bậc hai dù prompt
đã yêu cầu đọc code. Bản đầu `0eff5c7` đã admit sai vào ledger thử nghiệm riêng
`live-v1/wrong-ledger`; giữ nguyên evidence này, không coi là PASS. Sửa bằng check
chiều đơn vị AST tại M6: arithmetic straight-line, power/sqrt và ln/exp; không exec
host. Chưa hỗ trợ loops/comprehensions/solver tổng quát: giữ undetermined, không
ACCEPT. Check đơn vị không chứng minh định nghĩa tài chính hoặc phân biệt các công
thức cùng chiều; semantic vẫn cần, độ tin cậy Qwen là giới hạn nghiên cứu còn lại.

Để giữ cap2calls, bản cuối dùng lại **nguyên response live của ca đúng**, sau khi
assert model/messages/generation/output_spec/constraints bằng saved request. Code,
manifest, semantic payload không đổi; thêm deterministic unit check. Final replay
chạy Docker mới cho cả2ca, **0API calls**; ca sai bị deterministic block trước
semantic, không reuse false-positive. Đây là exact saved-semantic replay trên bản
cuối, không phải fresh live Qwen trên implementation `95229f8`.

M7 cuối là **partial_verified_coverage**: G3/RMS satisfied; G1/G2 source goals chưa
có verified support vì Qwen đòi mỗi source claim phải giải toàn RMS. Truth của hai
scalar vẫn ACCEPT theo validators hiện có. Không sửa M7 hoặc ép support để báo đủ
coverage. Answer còn giữ objective của saved task; chưa nghiệm thu chất lượng diễn đạt.

Evidence local tại `artifacts/evidence/M6-PY-01/`:

- `live-v1/provider-events.json`, `correct.json`, `wrong-formula.json`, `receipt.json`:
  hai actual calls và lỗi false-positive gốc.
- `final-replay/correct.json`, `wrong-formula.json`, `ledger/verified-claims.json`,
  `provider-events.json`, `receipt.json`: trace cuối và exact saved semantic reuse.
- `validation-summary.json`, `final-tests.xml`: kết quả tổng hợp/targeted tests.

Final receipt SHA khớp implementation; **185runtime hashes khớp,24JSON nguồn bất
biến**. **31targeted tests PASS** trên final implementation, gồm3Python controls,
22ledger và6M6/obligations compatibility. Controls kiểm code/operand/replay mismatch,
unavailable, wrong dimensions, semantic rejection, thiếu goal support, restart và
M7 citations; synthetic controls không là financial accuracy. Ruff/format/planning/
diff checks đạt; không fullCI/OCR/Gemini/PDF hoặc benchmark rộng.

Next action: chờ Owner/Tech Lead giao nhiệm vụ tiếp theo.
