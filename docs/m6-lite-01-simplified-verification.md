# M6-LITE-01 — Simplified Financial Claim Verification

Ngày11/11/2026, **REVIEW**, chờ Tech Lead nghiệm thu. Baseline `9a6aaac`.
Implementation chưa commit tại thời điểm lập báo cáo; SHA/CI cập nhật receipt local
sau push để giữ tối đa một implementation commit. Không tự nghiệm thu DONE.

## Kiến trúc thực tế

`m6_lite=False` giữ legacy. Bật flag: M5 candidates → kiểm tra deterministic độc lập
từng claim → tối đa một batch semantic Gemini cho claims còn cần ngữ nghĩa → một
quyết định cuối → existing Verified Ledger → existing M7. Chạy cùng M5/M7 Lite.
Document verification giữ nhánh hiện có; flag mới áp dụng financial claims.

Lite tái sử dụng financial validator, canonical retrieval, calculator replay và
EvidenceContextBuilder. Kiểm tra identity/company/document/snapshot/period, source
quality, số/Decimal/unit/scale, citation binding, formula/operands/result/lineage.
Dynamic calculation dùng tool replay hiện có, không thêm formula approval gate.
Derived relations có nội dung exact tool rendering được kiểm tra Python, không LLM.
Fact có thêm prose không tự ACCEPT toàn văn chỉ vì phần số đúng: chuyển semantic.

Interpretations: kiểm tra từng premise từ catalog độc lập; giữ kiểm tra phép tính,
bind số liệu với sources/results, chấp nhận biểu diễn số Việt/Anh. Nội dung so sánh,
nguyên nhân, mức độ kết luận và giới hạn do **một** semantic verifier đánh giá.
Không ép statement trùng mẫu câu. Các gate legacy đòi calculation/period-relation
cho mọi interpretation được thay bằng kiểm tra từng nguồn rồi semantic assessment;
không coi thiếu schema đó là bằng chứng claim sai. Conditional inference chưa đủ
căn cứ vẫn INVESTIGATE. Scope unresolved giữ caveat; requested scope chưa xác nhận
không ACCEPT. Labels của sources được đối chiếu vocabulary canonical hiện có.

Nhánh Lite không chạy Evidence Critic, Logic Critic, Verification Judge, Adaptive
Judge, revision/replan hoặc Planner coverage. Mỗi candidate có đúng một attempt.
Các trạng thái cuối dùng contracts hiện hữu: ACCEPT, INVESTIGATE, ABSTAIN.
Một claim hỏng/provider lỗi không xóa ACCEPT deterministic của claims khác.

Semantic payload chỉ có claim ID/text, câu hỏi/phạm vi, scalar facts, tóm tắt
calculations, assumptions/limitations; tối đa16000chars/32claims,2500output tokens.
Không full graph/OCR/Ledger, nested raw lineage hoặc Pydantic schema gửi provider.
Gateway chung, một call/runtime verification, không retry; malformed verdict chỉ
làm claim liên quan INVESTIGATE, không chặn các verdict độc lập hợp lệ.

## Ledger và API

`LiteProof`/`LiteVerificationHistory` ghi đúng batch/checks, semantic verdict/reason,
input digest và metadata thật; `LiteDecisionTrace` có policy `verification_lite_v1`.
Không tạo EvidenceCriticResult/LogicCriticResult hoặc giả approval bước chưa chạy.
Admission kiểm tra exact input/check/verdict bindings, replay single final decision,
chỉ lưu ACCEPT; sửa payload/decision làm replay thất bại. Identity/hash/storage/
query hiện có được tái sử dụng; historical records không migrate hoặc ghi đè.
Union history mở rộng backward compatible, legacy replay nguyên vẹn.

API giữ outcomes/provider usage/stage latency; thêm verification_mode/m6_lite với
counts deterministic/semantic/final decisions, reasons/citations và admitted IDs.
Foreign source/conflict được xử lý theo từng claim trong Lite. M7 không thay code
hoặc kiểm chứng ngữ nghĩa thêm. Assumptions/limitations/caveats giữ trong Ledger
và output. Flags không tự bật mặc định.

Files: `verification/lite_runtime.py`, `lite_contracts.py`, mở rộng tối thiểu
`decision_contracts.py`, `ledger_contracts.py`, `ledger.py`, `ledger_repository.py`;
API request/trace/pipeline; `tests/unit/test_m6_lite.py`, `scripts/evaluate_m6_lite.py`,
CI targeted list, planning/checker và báo cáo này. Không sửa M1–M5/M7 nghiệp vụ.

## Offline và tích hợp

3 focused tests PASS; nhóm30tests PASS gồm3Lite,4M5Lite,22Ledger và1legacy pipeline.
Các controls kiểm tra facts sai/số sai/citation thiếu/company-period-snapshot sai,
dynamic relation/proof tamper, causal rejection, semantic success, failure isolation,
provider exception không retry, Ledger admission/reload và M7 dùng semantic ACCEPT.
Fixtures unit là synthetic engineering controls, không thay đánh giá dữ liệu thật.

Exact staged tree tách khỏi local edits:30targeted PASS, Ruff check/format640files
PASS, planning125tasks PASS; working planning126tasks (gồm GEN-01a local) PASS;
diff check PASS. Staged code đã chạy lại BBS offline/fresh smoke và M7 semantic
release replay, cùng kết quả trên; không thêm live calls.17task files vào commit;
12preexisting modified files ngoài planning giữ exact bytes,3planning files chỉ
stage phần M6-LITE-01; các nghiệm thu/local planning trước đó giữ ngoài commit.

BBS thật từ M5-LITE-01 saved live responses qua **final offline replay**:
9candidates =5numeric+3original interpretations+1designed adversarial causal control.
Offline không provider:5ACCEPT/stored,4INVESTIGATE/rejected admission; reload5claims.
Đây là9claims chọn từ12replay candidates, không tuyên bố đã chạy toàn bộ12.

Fresh M5Lite→M6Lite→Ledger→M7Lite smoke BBS:3ACCEPT/newly stored,3verified IDs được
phát hành,1compact citation reference;0provider calls. Final `partial_verified_coverage`
được giữ, không tuyên bố câu trả lời đầy đủ. Replay release của live ACCEPTs không
network: M7 chọn và dùng2semantic claims tài sản/nợ, giữ citations/limitations.
Không gọi M7 live hoặc chạy lại M5 live; không OCR/extraction/EF-EG rebuild/M8.

## Gemini live và đánh giá ngữ nghĩa

Đúng **1/4** live calls, model `gemini-3.5-flash-lite`, success, không retry.
4882input characters (system+user),1908input+334output=**2242tokens**;
latency10,521s; monetary cost **unknown**, không suy thành0.
Batch9claims:5deterministic ACCEPT,4semantic candidates, Gemini3SUPPORTED và
1UNSUPPORTED →8ACCEPT/stored/reloaded,1ABSTAIN/rejected admission.

Ba original statements sau giữ nguyên từ M5 saved outputs; causal control được
thiết kế riêng, không phải kết quả M5 live:

1. `candidate:889b0e55fd7a79ed1660aded`:
   “Doanh thu thuần năm 2025 của BBS là 450,474,531,227 VND và năm 2024 là 355,507,372,286 VND.”
   Sources: BBS2025 PDF7, doanh thu2025/2024, selectors link4/link5.
   Raw `SUPPORTED`; reason: “Doanh thu thuần năm 2025 (450,474,531,227 VND) và năm 2024
   (355,507,372,286 VND) khớp chính xác với facts đã cho.” Final ACCEPT/stored.
2. `candidate:fc43f9cb1003866d421be39c`:
   “Tổng tài sản của BBS tại thời điểm 31/12/2025 đạt 266.086.680.765 VND. Chỉ có dữ liệu
   tổng tài sản tại một thời điểm năm 2025, thiếu dữ liệu so sánh với các năm trước.”
   Source: tài sản31/12/2025, PDF5/link40. Raw `SUPPORTED`; reason: “Tổng tài sản tại
   31/12/2025 là 266,086,680,765 VND khớp với facts và nhận định đi kèm về tính thiếu dữ
   liệu so sánh là hợp lý với phạm vi.” Final ACCEPT/stored.
3. `candidate:fff81cffeb388520603cc0d4`:
   “Tổng nợ phải trả của BBS tại thời điểm 31/12/2025 đạt 157.146.559.558 VND. Chỉ có dữ
   liệu tổng nợ phải trả tại một thời điểm năm 2025, thiếu dữ liệu so sánh với các năm trước.”
   Source: nợ31/12/2025, PDF6/link0. Raw `SUPPORTED`; reason: “Tổng nợ phải trả tại
   31/12/2025 là 157,146,559,558 VND khớp với facts và nhận định thiếu dữ liệu so sánh là đúng.”
   Final ACCEPT/stored.
4. Designed `m6-adversarial-causal-control`:
   “Doanh thu tăng vì doanh nghiệp quản lý chi phí xuất sắc.” Sources chỉ là hai
   doanh thu ở case1, không có bằng chứng quản lý chi phí. Raw `UNSUPPORTED`; reason:
   “Nhận định quy nguyên nhân doanh thu tăng là do quản lý chi phí xuất sắc vượt quá
   evidence, không được suy diễn nguyên nhân từ quan hệ số học.” Final ABSTAIN,
   admission rejected, không có Ledger ID.

Đánh giá theo evidence: các số khớp nguồn canonical, những giới hạn ở cases2/3
đúng **trong phạm vi nguồn đã cấp cho claim**, không là kết luận toàn catalog/PDF.
Control causal không có dữ liệu nguyên nhân nên loại là đúng. **0unsupported ACCEPT,
0unjustified rejection trong4semantic cases này**; không dùng CI để suy quality PASS.
Các positive live còn đơn giản (restatement/qualification); chưa chứng minh phân tích
sâu về nguyên nhân, CFO/PAT hoặc lợi ích Multi-Agent bằng benchmark đối chứng.

Traces ignored: `artifacts/evidence/M6-LITE-01/{offline,live,provider-events,
pipeline-smoke,semantic-m7-smoke}.json`. Có original candidates, exact inputs,
raw response/verdict/reason, final decisions, citations/checks, full IDs/admission.


## Candidate → verdict → Ledger mapping

| Candidate | Final | Ledger ID (prefix) |
| --- | --- | --- |
| `candidate:889b0e55fd7a79ed1660aded` | ACCEPT | `verified:eb1e232f9d347aa8` |
| `candidate:7cd7d4647464ad6a9c1bee57` | ACCEPT | `verified:dfbd7bd54e7f0a4f` |
| `candidate:bc13cb26bebe9761e9131a5a` | ACCEPT | `verified:709446167f5a1058` |
| `candidate:6f316076864eeb08d3f76b50` | ACCEPT | `verified:578191d8c0f82ad8` |
| `candidate:fc43f9cb1003866d421be39c` | ACCEPT | `verified:494b3ac0df8bab15` |
| `candidate:fff81cffeb388520603cc0d4` | ACCEPT | `verified:153652d74000ac5b` |
| `candidate:37663657fb14968dbe7421b2` | ACCEPT | `verified:cc5bf2f367d95ee5` |
| `candidate:eb85321eafb8cfc367d7fb9a` | ACCEPT | `verified:686e82a2394356a2` |
| `m6-adversarial-causal-control` | ABSTAIN | `none` |

Full64hex IDs và exact proof/admission mapping giữ trong `live.json`, không commit artifacts.

## Giới hạn và bàn giao

Chỉ BBS và một semantic batch; không đo financial accuracy toàn PDF hoặc dataset.
Provenance page-level/uncertain và reporting_scope_unresolved giữ nguyên, không nâng
thành cell-level hay khẳng định báo cáo hợp nhất/riêng lẻ. Numeric grammar cho direct
facts vẫn bảo thủ; interpretation số không có trong sources/results bị chặn Python.
Không mọi format/đơn vị/ngôn ngữ đều được hỗ trợ. Provider failure kiểm tra offline,
không có HTTP429/503 thật trong live call này. M7 live chưa chạy theo đúng scope.
Local edits ngoài task giữ nguyên; chỉ task files vào implementation commit.

Next action: Tech Lead nghiệm thu M6-LITE-01 và các giới hạn trên; không mở M6-LITE-02/M8.
