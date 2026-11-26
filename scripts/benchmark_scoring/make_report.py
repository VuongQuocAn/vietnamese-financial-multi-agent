"""Render the review report from the detailed score and request ledgers."""
import json,csv
from pathlib import Path
from decimal import Decimal
O=Path(__file__).resolve().parent
m=json.loads((O/'metrics.json').read_text(encoding='utf8'))
a=m['all600']
def pct(v):return f'{v*100:.2f}%'
def score(n,d):return f'{n}/{d} ({pct(n/d)})'
def hms(v):
    s=round(float(v));return f'{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}'
lines=['# EO-FROZEN-BENCHMARK-600-SCORING — REVIEW','',
'## 1. Phạm vi và khóa dữ liệu','',
'- Runtime đóng băng **A + SH-only**, gpt-4o-mini (snapshot quan sát: gpt-4o-mini-2024-07-18). Worktree triển khai: D:/DuAnCNTT/multi_agent_mh_recovery01, branch work/openai-release-fix-01. Checkout bàn giao: D:/DuAnCNTT/multi_agent.',
'- EO SHA-256: `f3132f39be917ad0f6b62c4289dd974ab2052f603720b53a7fc97ff64476b0f4`; CLI SHA-256: `4e7dfde529e7a7643455fa6e70b3e36761bf3fd0fc1813cf72febc62837f9e33`. Danh sách hash runtime trong freeze.json.',
'- Manifest và checkpoint COMPLETE: 600 ID duy nhất (200/200/200), 90 pilot đã khóa và 510 tiếp tục. Không thiếu, không trùng Final chính thức; 472 complete, 32 partial, 96 blocked. Lưu 600 đường dẫn/hash trong official-output-map.json. Đã đối chiếu 5.032 file raw với output-lock.json và khóa pilot trước khi mở Gold. Raw không sao chép hoặc sửa; các đường dẫn tương đối trong ZIP trỏ về thư mục nguồn EO-FROZEN-BENCHMARK-600 bên cạnh thư mục này.',
f'- Rubric Owner gửi, SHA-256 `{m["rubric_sha256"]}`; tất cả QA chấm Final thực tế, không lấy candidate thay Final. Chấm theo nhóm manifest kể cả route khác (61 QA: SH 42, MH 18, NR 1). BLOCKED tính 0. Không chỉnh runtime, guide, prompt, không chạy lại QA, API mới **0 USD**, không ablation.',
'- Phương pháp: SH dùng exact match theo loại và rà ngữ nghĩa/nguồn; NR Decimal exact trên proof thực sự phát hành, so toán hạng/tọa độ, biểu thức tương đương và hậu kiểm nghiệp vụ thủ công các trường hợp không khớp tự động; MH chấm từng ý Gold và đơn vị claim duy nhất, đối chiếu citation thuộc chính claim. Tách Full (không sai làm đổi đáp án) với strict Full (không sai bất kỳ khẳng định thực chất nào). Các đánh giá nguồn dựa trên JSON nguồn/trace local, không phải audit PDF độc lập. Phán định thủ công được lưu để Tech Lead tái kiểm; không tự gọi judge.',
'','## 2. Kết quả chính và mốc GPT RAG hybrid_rerank','',
'| Nhóm | EO nội dung | GPT RAG | Chênh số câu | Chênh điểm % |','|---|---:|---:|---:|---:|']
for t in ['SH','MH','NR']:
 r=m['rag_comparison'][t];lines.append(f'| {t} | {score(r["eo_correct"],200)} | {score(r["rag_correct"],200)} | {r["delta_count"]:+d} | {r["delta_pp"]:+.1f} |')
lines+=['',f'Tổng điểm nội dung: **{score(a["ALL"]["content_correct"],600)}**; Grounded FULL: **{score(a["ALL"]["grounded_full"],600)}**. SH là typed exact, MH là Full, NR là trị số exact; chỉ đối chiếu các định nghĩa này với mốc Owner cung cấp. Không có dữ liệu từng QA của RAG, không đối chiếu claim/proof/recovery RAG, và không thể quy chênh lệch cho riêng EO.','',
'### Tách pilot và 510 câu tiếp tục','',
'| Tập | Nhóm | N | Nội dung đúng | Grounded FULL | BLOCKED | Final chưa đủ/sai (không rỗng) |','|---|---|---:|---:|---:|---:|---:|']
for c in ['pilot90','remaining510','all600']:
 for t in ['SH','MH','NR','ALL']:
  r=m[c][t];lines.append(f'| {c} | {t} | {r["n"]} | {r["content_correct"]} | {r["grounded_full"]} | {r["blocked"]} | {r["wrong_or_incomplete_published"]} |')
lines+=['','### SH — nội dung, nguồn và bàn giao','',
'| Tập | Candidate đầu đúng | Final đúng | Final đúng có nguồn | Candidate đúng mất nội dung | Nội dung đúng nhưng nguồn không đạt | Final sai/thiếu |','|---|---:|---:|---:|---:|---:|---:|']
for c in ['pilot90','remaining510','all600']:
 r=m[c]['SH'];lines.append(f'| {c} | {r["candidate_correct"]}/{r["n"]} | {r["content_correct"]} | {r["grounded_full"]} | {r["correct_candidate_lost"]} | {r["correct_content_wrong_or_missing_source"]} | {r["wrong_or_incomplete_published"]} |')
lines+=['','Ba câu nội dung đúng nguồn không đạt: SH-0031 lấy từ phân phối lợi nhuận thay bảng biến động vốn yêu cầu; SH-0146 và SH-0174 trùng số gộp/thuần nhưng dùng sai chỉ tiêu. SH-0035 là đối chứng mất đáp án: candidate đúng từ T1 nhưng backend chặn do tên scope khác cách diễn đạt. SH có 12 Final chứa khẳng định sai, 13 Final không rỗng sai hoặc thiếu nội dung.',
'','### MH — Full, claim và nguồn','',
'| Tập | Full | Strict Full | P macro | R macro | F1 macro | Ý Gold đúng/tổng | Ý Gold đúng có nguồn/tổng | Claim có nguồn/tổng claim | Final có khẳng định sai |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for c in ['pilot90','remaining510','all600']:
 r=m[c]['MH'];lines.append(f'| {c} | {r["full"]}/{r["n"]} | {r["strict_full"]} | {pct(r["claim_precision_mean"])} | {pct(r["claim_recall_mean"])} | {pct(r["claim_f1_mean"])} | {r["correct_gold_count"]}/{r["gold_keypoint_count"]} ({pct(r["gold_correct_micro"])}) | {r["grounded_gold_count"]}/{r["gold_keypoint_count"]} ({pct(r["gold_grounded_micro"])}) | {r["grounded_claim_count"]}/{r["published_claim_count"]} | {r["false_final"]} |')
lines+=['','Macro tính trung bình theo QA, kể Final rỗng = 0. Tỷ lệ ý Gold ở bảng là micro theo tổng 512 ý; claim có nguồn micro theo 408 đơn vị claim, không phải số dòng Final. Claim trùng không đếm lại; claim ghép có thể chia thành đơn vị nguyên tử (số thứ tự raw claim có thể xuất hiện nhiều lần). File mh-claim-mapping.csv có một dòng cho mỗi ý Gold, claim thực tế, citation gắn với claim và điểm nguồn; mh-final-claim-units.csv cho mẫu số claim. Khi một claim chứa nhiều citation, danh sách là các citation gắn claim, không có nghĩa mọi citation đều chứng minh từng ý; ghi chú và cờ grounded xác định phán định.',
'','- **MH-0047:** ý 1/2 đúng đủ với T4R2 (ALT_2023 p39, doanh thu dịch vụ giảm) và T16R2 (p40, giá vốn dịch vụ tăng). Ý 3 đúng nội dung nhưng C2 chỉ gắn T17 p46 (bảng lĩnh vực năm 2023, không chứng minh tăng qua hai kỳ). Không mượn citation từ C1. Full 1, Grounded FULL 0, 2/3 ý Gold có nguồn.',
'- **MH-0086:** C1 gắn T1R2/T1 BED_2023 p22, chứng minh kỳ hạn 2023; không gắn BED_2025 p22. C2 gắn T1R2 và T153, chứng minh giá trị thu hồi hai năm tăng. Không mượn T153 của C2 để cấp nguồn cho kỳ hạn 2025 của C1. Full 1, Grounded FULL 0, 2/3 ý Gold có nguồn.',
'- MH có 5 case tạo proof (route NR); 3 proof được phát hành không trả đúng nhiệm vụ MH (MH-0113, MH-0202, MH-0206); 2 case BLOCKED (MH-0094, MH-0173). Đã chấm trên loại MH gốc, không đổi mẫu số.',
'','### NR — trị số, đơn vị, proof','',
'| Tập | Trị số exact | Đơn vị đúng | Cả hai | Dung sai* | Tạo proof | Proof đầu đúng | Có proof đúng (mọi lượt) | Proof đúng đến Final | Final sai trị số | Final sai nghiệp vụ proof |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for c in ['pilot90','remaining510','all600']:
 r=m[c]['NR'];lines.append(f'| {c} | {r["final_value_correct"]}/{r["n"]} | {r["final_unit_correct"]} | {r["final_value_unit_correct"]} | {r["rounding_tolerance"]} | {r["proof_generated"]} | {r["proof_correct_first"]} | {r["proof_correct_any"]} | {r["proof_correct_to_final"]} | {r["wrong_value_published"]} | {r["wrong_business_published"]} |')
lines+=['','* Dung sai một đơn vị làm tròn theo Gold, gồm cả exact; không tính vào điểm chính, không thay điểm đơn vị. NR 185/200 tạo được proof, 102/200 từng tạo proof đúng nghiệp vụ, 82/200 đưa proof đúng đến Final (cùng đúng trị số, đơn vị, nguồn). 20 câu có proof đúng nhưng không phát hành proof đúng. NR-0055 đúng cùng dòng cổ tức chi trên đúng báo cáo nhưng Verifier bác; NR-0019 P1 đúng, recovery P2 đổi sang báo cáo sai kỳ. NR-0064 sửa dấu bằng abs(diff) khiến số trùng nhưng không chứng minh đúng đại lượng có dấu. Chi tiết proof_checks từng ID trong evaluation.json.',
'','### Điểm pilot thay đổi so báo cáo gốc','',
'| ID | Chỉ số | Cũ | Mới | Lý do |','|---|---|---:|---:|---|']
with (O/'pilot-rescore-diff.csv').open(encoding='utf-8-sig') as f:
 for r in csv.DictReader(f):lines.append(f'| {r["id"]} | {r["metric"]} | {r["old"]} | {r["new"]} | {r["reason"]} |')
lines+=['','Pilot SH 22/30, MH 7/30, NR 14/30 nội dung không đổi. Grounded FULL pilot 38→36/90 vì hai citation MH trên (MH 4→2/30); đây cũng là kết quả strict đã ghi nhận trong lượt tiếp tục. Không đổi Final hay proof.',
'','## 3. Recovery và điểm mất đầu tiên','',
'| Nhóm | QA recovery | Cứu nội dung thành Final đủ nguồn | Cứu bàn giao kỹ thuật | Chỉ ngăn sai (không chứng minh cứu đủ) | Chỉ sửa proof, vẫn không Final | Đầu đã đúng | Không xác nhận cải thiện |','|---|---:|---:|---:|---:|---:|---:|---:|']
for t in ['SH','MH','NR','ALL']:
 r=a[t];c=r['recovery_categories'];lines.append(f'| {t} | {r["recovery_qa"]} | {c.get("content_rescue",0)} | {c.get("technical_handoff_rescue",0)} | {c.get("wrong_claim_or_proof_prevented",0)} | {c.get("proof_only_no_final",0)} | {c.get("already_correct_no_rescue",0)} | {c.get("no_confirmed_improvement",0)} |')
lines+=['','132 QA recovery; 0/132 xác nhận candidate sai/thiếu nội dung được sửa thành Final đúng đủ có nguồn. **3/132 cứu bàn giao**: SH-0001 từ alias BBS_2025 chưa cấp sang T2; SH-0061 EO 123 không bind sang EO 1 cùng F123; NR-0070 proof P1 đúng bị V bác vì nhầm quy tắc kỳ, P2 dùng dòng thuyết minh tương đương và được phát hành. 3 ca này không phải cải thiện nội dung. Không xác nhận ca chỉ thêm đúng một ý Gold mới vào Final; NR-0085/0109 cải thiện proof nhưng vẫn blocked. 30 ca có claim/proof sai ban đầu bị loại, không phải 30 ca được rescue, cũng không suy ra vòng recovery là nguyên nhân duy nhất. MH-0123 V loại quan hệ sai nhưng bỏ luôn quan hệ đúng lượt sửa; Final chỉ giữ chi phí phải trả. File recovery-audit.csv giữ candidate trước/sau, verdict và Final cho 132 ca.',
'','Lỗi đầu tiên phổ biến nhất theo phán định trace trong số không Grounded FULL: SH Reasoning 19/46 (Evidence 13, backend 10); MH Reasoning 92/175, Evidence 57; NR Reasoning 81/118, Verifier 18. Đây là phân loại chẩn đoán, không chứng minh nhân quả riêng module. Ví dụ NR-0187/0193 là lỗi provider (2 QA, 3 request không rõ usage); không gán vào thất bại nghiệp vụ. Các trường hợp đúng nội dung nhưng thiếu nguồn/proof, ý đúng MH chưa có citation phù hợp, proof đúng bị mất hoặc provider thiếu trace được gom 86 QA trong review-queue.csv (3 SH, 55 MH, 28 NR). Tất cả 600 đã có điểm theo rubric; danh sách này là ưu tiên review ngữ nghĩa/nguồn, không phải 86 QA chưa chấm.',
'','## 4. Token, thời gian, chi phí','',
'| Tập | Request | Input | Cached (nằm trong input) | Output | Total | USD đã ghi nhận | Unknown usage | E2E cộng dồn* | API cộng dồn đã đo |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for c in ['pilot90','remaining510','all600']:
 r=m[c]['ALL'];lines.append(f'| {c} | {r["requests"]:,} | {r["input_tokens"]:,} | {r["cached_input_tokens"]:,} | {r["output_tokens"]:,} | {r["total_tokens"]:,} | {r["cost_usd"]} | {r["unknown_usage_requests"]} | {hms(r["e2e_sum_s"])} | {hms(r["api_seconds_known"])} |')
lines+=['','* E2E là tổng thời lượng các result chính thức (không gồm khoảng nghỉ giữa batch). Một attempt dở SH-0021 có usage nhưng không có elapsed; một request không có seconds. Tổng mọi attempt có thời gian biết bằng tổng trên; thời gian chưa đo không giả lập. 3 request NR không nhận usage/response: chi phí đã biết là '+a['ALL']['cost_usd']+' USD, dự phòng upper bound '+a['ALL']['unknown_upper_usd']+' USD, tối đa theo dự phòng '+str(Decimal(a['ALL']['cost_usd'])+Decimal(a['ALL']['unknown_upper_usd']))+' USD. Không tính 0.00849420 USD lượt thử phát triển trước benchmark. Lượt scoring 0 USD. Ledger gốc 2.210 request, mỗi đường dẫn request duy nhất; tổng theo QA đối soát từ request, không cộng trùng result/log. Cached là tập con input. File chuẩn hóa để trống thiếu và có missing_reason.',
'','| Tập | Nhóm | E2E median (s) | E2E P95 (s) | Tokens | USD biết |','|---|---|---:|---:|---:|---:|']
for c in ['pilot90','remaining510','all600']:
 for t in ['SH','MH','NR','ALL']:
  r=m[c][t];lines.append(f'| {c} | {t} | {r["e2e_median_s"]:.2f} | {r["e2e_p95_s"]:.2f} | {r["total_tokens"]:,} | {r["cost_usd"]} |')
lines+=['','P95 nearest rank (ceil(0,95*N)), median thông thường, trên N result hoàn tất của từng tập/nhóm, kể BLOCKED. API time là tổng seconds request thực tế, không đồng nhất thời gian E2E.',
'','## 5. Bàn giao tái tạo','',
'- official-output-map.json, manifest-600.json, manifest.json, freeze.json, checkpoint.json, output-lock.json, pilot-output-lock.json, rubric gốc.',
'- qa-scores.csv và evaluation.json: đủ 600, Gold/Final/route/source trace/hash và điểm. mh-claim-mapping.csv, mh-final-claim-units.csv, pilot-rescore-diff.csv, recovery-audit.csv, review-queue.csv.',
'- usage-requests.csv (gốc), usage-requests-normalized.csv, usage-and-timing-by-qa.csv, usage-by-qa.csv, timing-by-qa.csv, các summary. metrics.json tổng hợp.',
'- Tái tạo: giải nén thư mục này cạnh EO-FROZEN-BENCHMARK-600; chạy `python score.py` rồi `python make_report.py`. score.py kiểm lại hash 600 result và đối chiếu ledger. review-packet.json lưu dữ liệu chấm compact và điểm SH cũ đã kiểm; sh-manual.json, mh-manual.json, nr-manual.json là nhận định hậu kiểm; nr-scoring.json được tạo bằng nr_score.py (SymPy). prepare_review.py chỉ cần khi tái tạo packet từ dữ liệu local đã khóa. Không gọi LLM.',
'','**Trạng thái REVIEW.** Quyết định tiếp theo thuộc Project Owner/Tech Lead: review bảng điểm và các ca biên; chưa ablation.']
(O/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print('report written')
