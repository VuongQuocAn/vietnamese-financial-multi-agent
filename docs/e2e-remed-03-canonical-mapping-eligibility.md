# E2E-REMED-03 — Canonical Mapping & Evidence Eligibility

Ngày17/11/2026 (Asia/Bangkok), **REVIEW**. Implementation
[`efc537ee6b92517465565a775681911b696ebf1f`](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/efc537ee6b92517465565a775681911b696ebf1f),
baseline origin/main5917ea9; worktree riêng bảo toàn local edits. Chỉ sửa tầng
import/catalog/context và runner; giữ M6/M7/Evidence Obligations/eligibility gates.

## RCA và thay đổi

- Importer từng bỏ toàn bảng khi một hàng lệch số cột. Nay chỉ bỏ hàng không
  căn chỉnh được, ghi `skipped_row_indices`, giữ hàng khớp header và pointer gốc.
  Không padding, dịch cột, đổi raw table hay coi thiếu số là0. Hàng không đều
  chưa đủ căn cứ vẫn không tạo fact; structural issues giữ nguyên.
- Catalog thiếu131: observation có đầy đủ số/kỳ/unit/provenance nhưng
  `canonical_item_id=None`, nên `json_fact_bound=False`. Bổ sung
  `b01.short_term_trade_receivables` từ nhãn phải thu khách hàng + mã131 + B01;
  giữ130 là tổng phải thu ngắn hạn. Label/code/statement bất đồng không mapping.
- Ordinal La Mã thay đổi theo cấu trúc bảng; khi có source code, bỏ ordinal
  trình bày rồi vẫn đối chiếu cả mã/nhãn/statement. Chuẩn hóa có giới hạn
  `&`→`và`, `cc dịch vụ`→`cung cấp dịch vụ`; không fuzzy match hoặc code-only mapping.
- **Đính chính RCA cũ cho NR0001:** bản JSON đã pin hiện tại có bảng B02 trang11
  hình chữ nhật, không ragged. Lỗi trực tiếp là tiêu đề nối kỳ tài chính chỉ được
  coi là mention, nên `statement_unresolved`, rồi nhãn viết tắt chưa mapping.
  Projection context nay nhận title đứng đầu dòng với suffix kỳ giải được,
  giữ pointer nguyên văn; mention tự do không thành statement. Không sửa lịch sử
  hoặc artifacts cũ để khớp nhận định trước.
- Không cần nới Financial Tools/Agent: gates đúng khi loại fact chưa mapping
  hoặc thiếu căn cứ. Sửa đầu vào và reimport làm facts đi qua gates hiện hữu.

## Offline và provenance

Reimport đúng2filings vào `artifacts/evidence/E2E-REMED-03/projection-final/`,
projection version `e2e-remed-03`; giữ document/source hashes, tạo snapshot mới,
không ghi đè full-final. Dùng importer, persistence, graph validator và fidelity
checker hiện có; runner có thể nhận corpus riêng và pin imported artifacts.

| Filing | Observations trước→sau | Mapped trước→sau | Usable qua JSON gate trước→sau |
| --- | ---: | ---: | ---: |
| BBS2025 |643→643|48→50|46→48|
| ADC2023 |616→656|18→38|18→36|

Financial Tools exact lookups:131 cuối2025 từ not_found→found;130 và tồn kho
vẫn riêng biệt. Doanh thu thuần2023/2022 từ not_found→found, đúng VND/scale1 và
hai kỳ riêng. M5 offline tạo2candidates131 ở hai mốc nguồn và1candidate doanh thu;
không là M6 approval. Calculator dùng nguồn khôi phục so sánh131>tồn kho và
tính tăng trưởng10,564892…% (làm tròn10,56%), không dùng Gold làm operands.

84eligible facts đều qua Financial Tools lookup. Graph/restart/fidelity đạt,
không orphan;1.299fact-value pointers và11.116source-pointer occurrences khớp
JSON gốc. Còn1.215observations không đủ gate, gồm unsupported mapping, thiếu
kỳ/unit/số hoặc quality conflict; reasons chồng lấp, không gọi tất cả là dữ liệu
thiếu thật. Không tự promote các observations này. Nguồn vẫn JSON-only,
page-level/uncertain, chưa PDF/financial verified.

3controls mới +34targeted compatibility **37PASS**: rows, mapping/code/statement,
period-suffixed titles, importer/corpus, JSON tools/calculation/M5, source tamper
và citations. Ruff/format/planning/diff đạt. Không fullsuite/fullCI/OCR/Gemini.
Ragged recovery có positive control; riêng số tăng của ADC trong2filings này
đến từ khôi phục B02 title/context và mapping, không gán cho ragged fix.

## Live retest và giới hạn

Đúng MH0001/NR0001 từ saved questions-only manifest, mỗi câu một lượt, code freeze
trước live. Qwen qua Gateway, cap20calls tổng/10mỗi câu,300s/request/60sprovider,
transport retries0. Không API judge hoặc prompt tuning/retest sau kết quả.
Gold chỉ hậu kiểm; không tính2câu thành accuracy Pilot45.

| QA | Trước→sau | M6 sau | Verified goal coverage trước→sau | Calls trước→sau |
| --- | --- | --- | --- | --- |
| MH0001 |provider_unavailable→verification_blocked|3ACCEPT|0/4→0/4|8→8|
| NR0001 |verification_blocked→completed_with_caveats|3ACCEPT|0/3→1/1|3→5|

Before lấy REMED-02 cho MH và REMED-01 cho NR. Hai câu trước0correct/2abstain,
sau **1correct/1abstain**, answer coverage0/2→1/2;7citations phát hành.
**13actual Qwen calls/97.536tokens/0unknown usage**,399,842s cộng wall
(MH208,906s; NR190,936s), không transport failure/retry. Không tuyên bố speedup
hoặc readiness từ2QA; goal sets do planner sinh khác nhau giữa hai lượt.

- MH: S7/S9 trỏ đúng131 và inventory_total cuối2025; Calculator so sánh đúng,
  M6 chấp nhận/lưu3claims. **Planning/Verification còn:** goal
  `goal_context_unresolved`, required indicators gồm cả inventory_gross/total,
  chưa có verified bindings cho mục tiêu so sánh. Document lane giữ
  `mixed_financial_document_unsupported`, không document candidate; không phát hành
  tên đối tượng từ raw note hoặc lấy3ACCEPT thay coverage. Demand vẫn chọn max
  trên một item/một kỳ, chưa là bằng chứng typed entity join hoàn chỉnh.
- NR: hai facts net_revenue đúng2023/2022 tới Specialist/Calculator; M6 chấp nhận
  3claims và hỗ trợ G1 nguyên câu hỏi; M7 phát hành **tăng10,56%**, đúng Gold,
  với7citations giữ caveat JSON-only. Raw Specialist prose từng ghi9,56%; existing
  deterministic calculation/render tạo10,56% trước M6, không phát hành raw sai.
  Goal trước gồm3mục, sau1mục nguyên câu hỏi; báo0/3→1/1 theo traces, không giả
  định hai phân rã tương đương hoặc chất lượng planning đã được giải quyết.

Audit cuối xác nhận186runtime files khớp frozen receipt/implementation;58source
JSON,14imported files cũ cùng catalog index,132files evidence task trước và80local
edits nguyên byte.34imported pins gồm projection mới/cũ/index bất biến qua live;
7released citations resolve đúng hash/pointer và bound admitted claims.
M6/M7/Evidence Obligations không đổi. Chỉ2filings dùng projection mới trong retest;
không âm thầm thay toàn corpus mặc định. Trace/projection/Gold giữ local, không commit.
Kiểm index còn132files ViFinBench đã được tracked từ baseline/lịch sử;
task này không thêm/sửa/stage chúng, không xóa local hoặc rewrite lịch sử.
Không có `.env`, API config hoặc secrets trong tập commit của task.

Evidence local: `artifacts/evidence/E2E-REMED-03/offline-comparison.json`,
`offline-arithmetic.json`, `qa-report.md`, `comparison.json`, `integrity-audit.json`
và `live-final/{receipt,provider,results,ledgers}`. Implementation và tài liệu
được commit/push main; xác minh remote trong `publication.json` tại bàn giao.

## Handoff

Next action: Tech Lead review mapping/eligibility và các giới hạn Planning/Verification
để đánh giá readiness trước khi quyết định tiếp tục Pilot45.
