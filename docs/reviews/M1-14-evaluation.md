# M1-14 — Document Understanding Evaluation

28/10/2026, REVIEW; baseline acceptance `7ed1b808239d5a1240f79a167d6c06ac8b677da8`.
Offline replay, **0 API mới**, không sửa Gateway/OCR/contracts hoặc outputs cũ.
Implementation SHA và exact-SHA CI báo trong bàn giao cuối sau một commit/push;
không tạo publication commit chỉ để ghi SHA.

## Benchmark và cách chạy

Private ignored `artifacts/document-evaluation/M1-14/benchmark.json` chứa 4 pages,
46 snippets/cells (gồm 18 số nguyên VND), 36 nhãn vị trí trên 3 bảng.
Ảnh gốc: BCC/2021/page14 (văn bản + bảng chi nhánh), BED/2023/page39 (lương/thuê),
BBS/2021/page15 (tiền), BBS/2021/page18 (nợ xấu xoay ngang, header phức tạp).
Membership lấy từ frozen M1-12/M1-12a và M1-13b; không scan dataset.
Mỗi nhãn có source identity/page, image SHA-256, vùng mô tả, expected text,
verification `direct_image_review` và selectors cố định tới outputs.
Codex đã xem trực tiếp bốn ảnh; nhãn không lấy độ đồng thuận model làm truth.
Đây là visual review bởi Codex, **chưa có người gán nhãn độc lập**; chờ Tech Lead.
Nhãn/private source không commit theo AGENTS. Benchmark SHA-256:
`771ecdb67671419b01b9b08468e5f12f81c34b468bccda8a357464fba16158c2`.

```powershell
python -m vietnamese_financial_multi_agent.document_processing.evaluation artifacts/document-evaluation/M1-14/benchmark.json --output artifacts/document-evaluation/M1-14/replay.json
```

Output phải là file mới. Evaluator dùng thư viện chuẩn, kiểm tra hash tất cả
inputs trước đọc; đường dẫn tương đối theo `--root` (mặc định cwd).
Manifest là evaluation adapter nhỏ: JSON key/index selectors, không tìm output
theo expected value, không chọn candidate đọc gần nhãn nhất. Files giữ đủ raw,
persisted responses, correction views và ảnh; source/output cũ bất biến.

A: M1-12 DU tables và raw text. B: M1-12a reconstruction cùng 8 bảng;
hai text snippets BCC dùng raw qua correction view M1-13a có corrections rỗng.
C: M1-13b full-page structured outputs. Không dựng B/C cho trang thiếu output.
A/B là replay của các stage đã chạy, không tuyên bố một end-to-end run chung mới.

## So sánh công bằng

Text: NFC + gộp whitespace, giữ hoa/thường/dấu; CER/WER micro trên toàn reference
characters/words, kể cả snippet thiếu (deletion). Financial raw giữ nguyên string;
normalized chỉ nhận số nguyên và dấu chấm nhóm nghìn, giữ dấu âm, không đổi dấu
phẩy/decimal/ngoặc/dash thành giá trị. Financial subset nằm trong text denominator.
Thiếu binding trên trang có output vẫn tính missing, không bỏ khỏi denominator.

**Giao A/B/C = BCC14 + BED39: 26 nhãn, 6 số, 24 vị trí cells.**

| Metric trên cùng giao | A Existing OCR | B Hybrid | C Gemini-first |
| --- | ---: | ---: | ---: |
| Pages có output / 4 benchmark | 4/4 | 4/4 | 2/4 |
| Nhãn có output trên giao | 26/26 | 26/26 | 26/26 |
| Text Exact Match | 24/26 (92,31%) | 24/26 (92,31%) | 26/26 (100%) |
| CER / WER | 0,815% / 1,923% | 0,815% / 1,923% | 0% / 0% |
| Financial raw / normalized | 6/6 / 6/6 | 6/6 / 6/6 | 6/6 / 6/6 |
| Candidate row/column alignment | 24/24 | 24/24 | 24/24 |
| Page identity linkage có thể kiểm tra | 24/24 | 24/24 | 26/26 |
| Raw cell ID linkage | 24/24 | 24/24 | N/A |
| Classification / bbox / merged cells | N/A | N/A | N/A |

Hai text snippets raw A/B không có SourceAnchor, grounding N/A cho hai snippets;
không gọi missing metadata là sai nguồn. C có page identity + image hash;
không có raw cell ID, không chứng nhận bbox hoặc định vị cell trên ảnh.
Grounding kiểm tra observed anchors tới frozen identity/ID, không semantic truth.

**Coverage riêng, không dùng để xếp hạng A/B với C:**

| Metric trên mẫu sẵn có | A (4 pages) | B (4 pages) | C (2 pages) |
| --- | ---: | ---: | ---: |
| Text EM / coverage | 44/46 / 46/46 | 44/46 / 46/46 | 26/26 / 26/26 |
| CER / WER | 0,544% / 1,399% | 0,544% / 1,399% | 0% / 0% |
| Financial raw / normalized | 18/18 / 18/18 | 18/18 / 18/18 | 6/6 / 6/6 |
| Candidate alignment (partial, 3/2 tables) | 32/36 | 32/36 | 24/24 |
| Page / cell linkage có metadata | 44/44 / 44/44 | 44/44 / 44/44 | 26/26 / N/A |

Tách bốn khái niệm: `schema_valid` là provider response qua JSON Schema;
`structure_accepted` là local gate; `content_correct` là khớp nhãn ảnh;
`grounded` là source linkage như định nghĩa trên. JSON parse thành công không
tự thành schema_valid. Persisted A/B không lưu metadata JSON Schema tương ứng
nên N/A. C schema_valid **2/2**, nhưng structure_accepted **0/4 bảng**.
A/B structure_accepted **1/8 → 2/8 trên cùng 8 bảng**; số này là operational
validation, không accuracy cấu trúc có ground truth đầy đủ. C phân đoạn thành
4 bảng trên 2 trang, không so 0/4 với 1/8 như một denominator chung.
Không có nhãn full grid/merge/bbox; 36 vị trí chỉ là partial cell alignment.
4 pages gán nhãn B09 từ ảnh thuyết minh; chưa nối output classification tương ứng
trong adapter, accuracy N/A. B01/B02/B03 chưa có coverage.

## Ví dụ ảnh và operational evidence

- BCC header ảnh `BỈM SƠN`; A/B `BÍM SƠN`, C đúng. Dòng môi trường ảnh
  `về vấn đề môi trường`, A/B có `để` thừa, C bỏ đúng từ thừa. Hai snippets
  này được chọn do lỗi đã biết từ pilot, có selection bias.
- BED sáu số lương (hai năm × ba người) đúng ở cả A/B/C; ví dụ
  `281.360.000` và `309.441.300`. Không có bằng chứng cải thiện digit accuracy.
- BBS18 header `Giá gốc` nằm sau cột thời gian quá hạn; A/B giữ text đúng
  nhưng bốn chỉ số header được chọn lệch một cột so với logical grid trên ảnh.
  Rows data được chọn vẫn đúng. Không dùng text match để che lỗi cấu trúc.

Replay requests/tokens mới **0/0**. Historical M1-12a: 7 requests,
55.620 input +17.177 output =72.797 tokens trên 8 bảng (1 deterministic).
Correction M1-13a là stage riêng, không cộng vào run reconstruction.
M1-13b: 2 successful full-page requests, 10.059 known tokens; crop timeout
1 request/usage unknown, aggregate thực tế N/A. Không gán crop failure thành
output, không retry. Latency/cost comparable N/A; không có paired measurement.

## Kết luận và giới hạn

Đề xuất **Hybrid có kiểm soát**: giữ Existing OCR/provenance làm nền, dùng Gemini
vision tại vùng cần đọc lại, local gate và review trước khi đưa vào bước kế toán.
B tăng accepted tables 1→2 trên cùng 8 bảng, nhưng không sửa hai lỗi text đã biết;
C sửa hai lỗi này trên giao 26 labels nhưng cả 4 bảng vẫn unresolved.
Chưa đủ bằng chứng thay toàn pipeline bằng Gemini-first. Đây là đề xuất kiến trúc,
không thay implementation của các task DONE hoặc tự bắt đầu M2.

Purposive sample nhỏ; 18 số dễ đọc, chỉ 6 số trên giao, không phải accuracy dataset.
Nhãn không bao phủ toàn trang; không kiểm false positives ngoài labeled regions.
Header/paragraph và bảng chọn sẵn từ pilot, thiếu reports B01/B02/B03, thiếu
full-table/merge/bbox truth, thiếu human second review và paired latency/cost.
Private benchmark không có trong CI; CI dùng synthetic fixtures engineering.

Local: 8 focused tests, Ruff changed files, planning checker, diff check.
CI existing full unit suite Python3.11/3.12 kiểm tra exact implementation SHA sau push.
Next action: Tech Lead review nhãn, metrics và đề xuất Hybrid; giữ M1-14 REVIEW.
