# Master Task Registry

Nguồn trạng thái nhiệm vụ chính của repository. Cập nhật: **2026-10-26**
(Asia/Bangkok). Một dòng duy nhất cho mỗi Task ID; lịch sử bên dưới là bằng
chứng, không phải registry thứ hai. [Dashboard](progress.md),
[roadmap](roadmap.md), [handoff](handoff.md), [mẫu task](task-template.md).

## Quy tắc trạng thái và ID

- Chỉ dùng `TODO`, `READY`, `IN_PROGRESS`, `BLOCKED`, `REVIEW`, `DONE`.
- `TODO`: chưa làm; `READY`: dependencies đã DONE, specification/inputs/criteria
  đã đủ; READY không tự cấp phép bắt đầu task.
- `IN_PROGRESS`: đang triển khai; tối đa một task chính. `BLOCKED`: ghi nguyên
  nhân và hành động gỡ chặn trong spec/handoff. `REVIEW`: ghi phần chờ nghiệm thu.
- `DONE`: acceptance criteria và tests liên quan đạt, có commit hoặc bằng chứng
  tương đương được xác minh. Không coi tạo file hoặc trạng thái tài liệu là bằng chứng.
- Task ID bất biến; không tái sử dụng/đánh số lại. Task mới dùng số tiếp theo hoặc
  hậu tố con chưa dùng. Ưu tiên XS/S; xem xét chia M/L trước READY, không ước lượng
  giờ hoặc tokens thiếu cơ sở.
- `P0`: nền tảng cần trước; `P1`: bước tiếp theo; `P2`: backlog sau nền tảng.
  Đây là thứ tự ưu tiên, không phải lịch cam kết.
- M1-01 đến M1-04 giữ tên/phạm vi từ M0-03. M1-02, M1-03, M1-04 được phân rã
  bằng hậu tố a/b/c; task cha chỉ tổng hợp nghiệm thu, không phải task triển khai
  lớn song song với con. Cha DONE sau khi con và criteria của cha đạt.
- Backlog xa chỉ có mô tả đầu ra/criteria dự kiến trong roadmap. Phải chuẩn bị
  spec theo template và rà soát phạm vi trước READY; không tạo placeholder hàng loạt.

## Registry

| Task ID | Tên | Milestone | Status | Priority | Dependencies | Specification / phạm vi dự kiến | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M0-01 | Initialize Project Repository | M0 | DONE | P0 | - | [M0-01](tasks.md#m0-01-history) | [9eb4483](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/9eb4483f4be4029c014a3a9552dfb5a1a91c8fea) |
| M0-02 | Reorganize Financial Dataset & Commit to GitHub | M0 | DONE | P0 | M0-01 | [M0-02](tasks.md#m0-02-history) | [279e65a](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/279e65a38c44feca385b305e32e34be2c30510db) |
| M0-03 | Repository Housekeeping & Planning Synchronization | M0 | DONE | P0 | M0-02 | [M0-03](tasks.md#m0-03-history) | [c86b86e](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/c86b86eb95ef91251a53b3768ae5c52c2ed73514) |
| M0-04 | Project Task Tracking & Codex Handoff System | M0 | DONE | P0 | M0-03 | [M0-04](tasks/M0/M0-04.md) | [3c7d78c](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/3c7d78c6855467262beca6064d657bb23a7a2e3e) |
| M1-01 | Dataset Inventory & Provenance Review | M1 | DONE | P1 | M0-04 | [M1-01](tasks/M1/M1-01.md) | [dbfbb76](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/dbfbb760ec6c85391da47199edd52510fda216a8) |
| M1-02 | Data Contracts & Path Mapping Design | M1 | DONE | P1 | M1-01, M1-02a, M1-02b, M1-02c | [M1-02](roadmap.md#m1-02) | [3363a55](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/3363a557f4d1d1b5507ac408425f3e568f528a1b); ba contracts được duyệt |
| M1-02a | Raw OCR Contracts | M1 | DONE | P1 | M1-01 | [M1-02a](tasks/M1/M1-02a.md) | [08f3289](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/08f3289a47f021a97608b7e8d2885bd3656bc9c5) |
| M1-02b | Document Understanding Contracts | M1 | DONE | P1 | M1-02a | [M1-02b](tasks/M1/M1-02b.md) | [d4e6aca](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/d4e6aca312251055f452a009ef0d9072ad63d940), CI success; Tech Lead APPROVED 2026-10-26 |
| M1-02c | Path Mapping Contract | M1 | DONE | P1 | M1-01 | [M1-02c](tasks/M1/M1-02c.md) | [527d928](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/527d928935bb5d570e0a987279326dce4228d795), CI success; Tech Lead APPROVED 2026-10-26 |
| M1-03 | Configuration & Read-Only OCR Adapter | M1 | TODO | P1 | M1-02, M1-03a, M1-03b, M1-03c | [M1-03](roadmap.md#m1-03) | - |
| M1-03a | Central Data Configuration | M1 | DONE | P1 | M1-02 | [M1-03a](tasks/M1/M1-03a.md) | [5607cc0](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/5607cc05035871455df3bf249ff95a44e87b5d66), CI success; Tech Lead APPROVED 2026-10-26 |
| M1-03b | Read-Only Path Resolver | M1 | DONE | P1 | M1-03a | [M1-03b](tasks/M1/M1-03b.md) | [3cb32f8](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/commit/3cb32f8409a76d94747f0080186092a8f9ad1be6), CI success; Tech Lead APPROVED 2026-10-26 |
| M1-03c | Read-Only OCR Data Loader | M1 | TODO | P1 | M1-03b | [M1-03c](roadmap.md#m1-03c) | - |
| M1-04 | Extraction Quality Validation & Pilot | M1 | TODO | P1 | M1-03, M1-04a, M1-04b | [M1-04](roadmap.md#m1-04) | - |
| M1-04a | Extraction Structure Validators | M1 | TODO | P1 | M1-03 | [M1-04a](roadmap.md#m1-04a) | - |
| M1-04b | Bounded Extraction Pilot | M1 | TODO | P1 | M1-04a | [M1-04b](roadmap.md#m1-04b) | - |
| M1-05 | LLM Gateway Contract | M1 | TODO | P1 | M1-02 | [M1-05](roadmap.md#m1-05) | - |
| M1-06 | Shared LLM Gateway | M1 | TODO | P1 | M1-05, M1-03a | [M1-06](roadmap.md#m1-06) | - |
| M1-07 | Gemini Structured Output Adapter | M1 | TODO | P1 | M1-06 | [M1-07](roadmap.md#m1-07) | - |
| M1-08 | Quota and Budget Management | M1 | TODO | P1 | M1-06 | [M1-08](roadmap.md#m1-08) | - |
| M1-09 | LLM Response Cache | M1 | TODO | P1 | M1-06 | [M1-09](roadmap.md#m1-09) | - |
| M1-10 | Document Processing Checkpoints | M1 | TODO | P1 | M1-03, M1-02b | [M1-10](roadmap.md#m1-10) | - |
| M1-11 | Page and Document Classification | M1 | TODO | P1 | M1-04, M1-07, M1-08, M1-09, M1-10 | [M1-11](roadmap.md#m1-11) | - |
| M1-12 | Table Structure Reconstruction | M1 | TODO | P1 | M1-11 | [M1-12](roadmap.md#m1-12) | - |
| M1-13 | Evidence-Preserving OCR Correction | M1 | TODO | P1 | M1-12 | [M1-13](roadmap.md#m1-13) | - |
| M1-14 | Document Understanding Evaluation | M1 | TODO | P1 | M1-13 | [M1-14](roadmap.md#m1-14) | - |
| M2-01 | Financial Normalization Contracts | M2 | TODO | P2 | M1-14 | [M2-01](roadmap.md#m2-01) | - |
| M2-02 | Period Unit and Reporting Scope | M2 | TODO | P2 | M2-01 | [M2-02](roadmap.md#m2-02) | - |
| M2-03 | Statement Type Recognition | M2 | TODO | P2 | M2-02 | [M2-03](roadmap.md#m2-03) | - |
| M2-04 | Financial Item Mapping | M2 | TODO | P2 | M2-03 | [M2-04](roadmap.md#m2-04) | - |
| M2-05 | Deterministic Arithmetic Checks | M2 | TODO | P2 | M2-04 | [M2-05](roadmap.md#m2-05) | - |
| M2-06 | Accounting Relationship Checks | M2 | TODO | P2 | M2-05 | [M2-06](roadmap.md#m2-06) | - |
| M2-07 | Normalization Quality Gates | M2 | TODO | P2 | M2-06 | [M2-07](roadmap.md#m2-07) | - |
| M3-01 | Canonical and Provenance Contracts | M3 | TODO | P2 | M2-07 | [M3-01](roadmap.md#m3-01) | - |
| M3-02 | Canonical Financial Facts | M3 | TODO | P2 | M3-01 | [M3-02](roadmap.md#m3-02) | - |
| M3-03 | Text and Table Evidence | M3 | TODO | P2 | M3-01 | [M3-03](roadmap.md#m3-03) | - |
| M3-04 | EF-EG Nodes and Edges | M3 | TODO | P2 | M3-02, M3-03 | [M3-04](roadmap.md#m3-04) | - |
| M3-05 | Derived Metric Records | M3 | TODO | P2 | M3-04 | [M3-05](roadmap.md#m3-05) | - |
| M3-06 | Calculation Lineage | M3 | TODO | P2 | M3-05 | [M3-06](roadmap.md#m3-06) | - |
| M3-07 | Evidence Retrieval Interface | M3 | TODO | P2 | M3-06 | [M3-07](roadmap.md#m3-07) | - |
| M4-01 | Executable Tool Contracts | M4 | TODO | P2 | M3-07 | [M4-01](roadmap.md#m4-01) | - |
| M4-02 | Typed Financial Retrieval Tools | M4 | TODO | P2 | M4-01 | [M4-02](roadmap.md#m4-02) | - |
| M4-03 | Calculator and Formula Executor | M4 | TODO | P2 | M4-02 | [M4-03](roadmap.md#m4-03) | - |
| M4-04 | Evidence Retrieval Tools | M4 | TODO | P2 | M4-01 | [M4-04](roadmap.md#m4-04) | - |
| M4-05 | Question Answering Baseline | M4 | TODO | P2 | M4-03, M4-04, M1-07 | [M4-05](roadmap.md#m4-05) | - |
| M5-01 | Evidence Plan and Planner Contracts | M5 | TODO | P2 | M4-05 | [M5-01](roadmap.md#m5-01) | - |
| M5-02 | Evidence-Aware Query Planner | M5 | TODO | P2 | M5-01 | [M5-02](roadmap.md#m5-02) | - |
| M5-03 | Risk-Aware Supervisor | M5 | TODO | P2 | M5-02 | [M5-03](roadmap.md#m5-03) | - |
| M5-04 | Profitability Specialist | M5 | TODO | P2 | M5-03 | [M5-04](roadmap.md#m5-04) | - |
| M5-05 | Liquidity and Leverage Specialist | M5 | TODO | P2 | M5-03 | [M5-05](roadmap.md#m5-05) | - |
| M5-06 | Cash Flow and Earnings Quality Specialist | M5 | TODO | P2 | M5-03 | [M5-06](roadmap.md#m5-06) | - |
| M5-07 | Adaptive Routing Rules | M5 | TODO | P2 | M5-04, M5-05, M5-06 | [M5-07](roadmap.md#m5-07) | - |
| M5-08 | Agent and Tool Orchestration | M5 | TODO | P2 | M5-07 | [M5-08](roadmap.md#m5-08) | - |
| M6-01 | Candidate Claim Contracts | M6 | TODO | P2 | M5-08 | [M6-01](roadmap.md#m6-01) | - |
| M6-02 | Deterministic Financial Validators | M6 | TODO | P2 | M6-01 | [M6-02](roadmap.md#m6-02) | - |
| M6-03 | Evidence Critic | M6 | TODO | P2 | M6-01 | [M6-03](roadmap.md#m6-03) | - |
| M6-04 | Financial Logic Critic | M6 | TODO | P2 | M6-01 | [M6-04](roadmap.md#m6-04) | - |
| M6-05 | Verification Decisions | M6 | TODO | P2 | M6-02, M6-03, M6-04 | [M6-05](roadmap.md#m6-05) | - |
| M6-06 | Verified Claim Ledger | M6 | TODO | P2 | M6-05 | [M6-06](roadmap.md#m6-06) | - |
| M7-01 | Vietnamese QA Composer | M7 | TODO | P2 | M6-06 | [M7-01](roadmap.md#m7-01) | - |
| M7-02 | Report Outline Planner | M7 | TODO | P2 | M6-06 | [M7-02](roadmap.md#m7-02) | - |
| M7-03 | Grounded Report Writer | M7 | TODO | P2 | M7-02 | [M7-03](roadmap.md#m7-03) | - |
| M7-04 | Citation Rendering | M7 | TODO | P2 | M7-01, M7-03 | [M7-04](roadmap.md#m7-04) | - |
| M7-05 | Information Firewall and Output Validation | M7 | TODO | P2 | M7-04 | [M7-05](roadmap.md#m7-05) | - |
| M8-01 | Evaluation Dataset Protocol | M8 | TODO | P2 | M7-05 | [M8-01](roadmap.md#m8-01) | - |
| M8-02 | Controlled Baseline Experiments | M8 | TODO | P2 | M8-01 | [M8-02](roadmap.md#m8-02) | - |
| M8-03 | Interactive QA Metrics | M8 | TODO | P2 | M8-01 | [M8-03](roadmap.md#m8-03) | - |
| M8-04 | Report Generation Metrics | M8 | TODO | P2 | M8-01 | [M8-04](roadmap.md#m8-04) | - |
| M8-05 | Ablation Experiments | M8 | TODO | P2 | M8-02, M8-03, M8-04 | [M8-05](roadmap.md#m8-05) | - |
| M8-06 | Usage Latency and Cost Evaluation | M8 | TODO | P2 | M8-02 | [M8-06](roadmap.md#m8-06) | - |
| M8-07 | End-to-End Integration | M8 | TODO | P2 | M8-03, M8-04, M8-06 | [M8-07](roadmap.md#m8-07) | - |
| M8-08 | Application Demo | M8 | TODO | P2 | M8-07, M8-05 | [M8-08](roadmap.md#m8-08) | - |

## Lịch sử M0-01 đến M0-03 được bảo toàn

Phần dưới giữ nguyên nội dung lịch sử trước M0-04, chỉ thêm anchors để liên kết.
Các giới hạn riêng và câu lệnh dừng của task cũ chỉ áp dụng mốc tương ứng.
Trạng thái hiện tại luôn tra bảng Registry phía trên.

<a id="m0-01-history"></a>

## M0-01 — Kết quả và phạm vi lịch sử

- Đã tạo cấu trúc Python 3.11+, cấu hình môi trường, tài liệu, quy tắc làm việc,
  lint/format, smoke tests và CI.
- Initial commit: `9eb4483f4be4029c014a3a9552dfb5a1a91c8fea`; đã nằm trong lịch sử
  `origin/main`. Kết quả local đạt; CI trên nền tảng M0 đã được xác minh ở M0-02.
- Phạm vi riêng của task: chỉ skeleton, không triển khai OCR, Gemini/Gateway,
  EF-EG, Agent hoặc chức năng nghiệp vụ. Đây là giới hạn của task khởi tạo,
  không phải lệnh cấm triển khai các thành phần này trong task được giao sau đó.
- Task đã cho phép `git init`, initial commit, tạo repository private và push
  `main`. Quyền khởi tạo này không áp dụng mặc định cho task khác. Người dùng
  đã đổi repository sang public trước M0-02; không cần tạo lại repository.

<a id="m0-02-history"></a>

## M0-02 — Acceptance criteria đã xác minh

- [x] Di chuyển nguyên trạng hai dataset trong cùng ổ đĩa, không ghi đè đích.
- [x] Tạo `data/normalized/`, `data/canonical/`, giữ `data/samples/`.
- [x] Đối chiếu đủ 9.127 file, 2.327.680.425 byte và metadata trước/sau.
- [x] Hash 18 mẫu khớp; đọc 6 JSON và xác minh/giải mã 12 PNG thành công.
- [x] Bổ sung bốn biến đường dẫn và tài liệu ánh xạ Colab bên ngoài JSON gốc.
- [x] Cập nhật README, tài liệu dataset, AGENTS và planning.
- [x] Kiểm tra ignore rules, tập commit, lịch sử Git và phạm vi thay đổi.
- [x] Lint/format và 11 unit tests local đạt.
- [x] Commit đúng message: `279e65a38c44feca385b305e32e34be2c30510db`.
- [x] Commit đã có trên `origin/main`; xác minh lại trong M0-03.
- [x] [CI run 40207830248](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40207830248)
  thành công trên Python 3.11 và 3.12; không còn lỗi mở của M0-02.

Phạm vi riêng của M0-02: chỉ sắp xếp dữ liệu local, cấu hình đường dẫn, tài liệu
và commit/push. Không OCR lại, gọi Gemini, viết nghiệp vụ hoặc triển khai
DataPathResolver trong task này. Giới hạn đó được lưu ở đây; các quy tắc bảo toàn
dữ liệu và bảo mật lâu dài tiếp tục nằm trong [`AGENTS.md`](../AGENTS.md).

<a id="m0-03-history"></a>

## M0-03 — Acceptance criteria

- [x] Đối chiếu nhánh, working tree, local/remote commit và CI của M0-02.
- [x] Đồng bộ M0-01/M0-02 theo GitHub; bỏ blocker đã giải quyết khỏi trạng thái hiện tại.
- [x] Tách giới hạn task cũ khỏi AGENTS, giữ nguyên các nguyên tắc kiến trúc.
- [x] Bổ sung kế hoạch M1-01 đến M1-04 với trạng thái dự kiến, chưa bắt đầu.
- [x] Rà soát `.gitignore`, Git index và kiểm tra cấu hình TOML/YAML.
- [x] Lint, format và 11 unit tests local đạt.
- [x] Xác minh cuối cùng dữ liệu, phạm vi thay đổi và các file chuẩn bị commit.
- [x] Commit `chore(project): sync repository status and development roadmap`.
- [x] Push bình thường lên `origin/main` và đối chiếu kết quả GitHub/CI.

Commit nội dung M0-03 `99e1575167ec7fdf98132f8de49e4819348c7b16` đã push;
[CI run 40208727796](https://github.com/VuongQuocAn/vietnamese-financial-multi-agent/actions/runs/40208727796)
đạt trên Python 3.11 và 3.12. Trạng thái hoàn thành được ghi sau khi xác minh
commit và run này; không suy diễn từ kết quả kiểm thử local.

M0-03 chỉ housekeeping và đồng bộ tài liệu, không gọi Gemini, xử lý OCR hoặc
viết code nghiệp vụ. Dừng sau khi hoàn tất M0-03.
